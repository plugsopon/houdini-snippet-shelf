"""brother_link - lets Claude (Brother) look at, and on request change, THIS Houdini session.

Start it from inside Houdini (Python Shell or a shelf tool):

    import os, sys; sys.path.insert(0, os.path.join(hou.getenv("FXAI_HOME"), "mcp", "houdini"))
    import brother_link; brother_link.start()

Stop it with brother_link.stop(). Quitting Houdini stops it as well.

- Listens on 127.0.0.1 only, on the first free port from 18820. Every request must
  carry a random token that only this user's files hold.
- Registers itself in %USERPROFILE%\\.houdini_brother\\sessions\\<pid>.json, so the
  MCP server can list every open Houdini and let Plug pick which one to talk to.
- Every request runs on Houdini's main thread (hdefereval), so it is as safe as
  typing in the Python Shell. Anything that changes the scene runs inside ONE
  undo group ("Brother: ..."), so a single Ctrl+Z takes it back.
- Frames are read with geometryAtFrame / evalAtFrame: looking never moves the playbar.
"""
import atexit, contextlib, io, json, math, os, secrets, socket, sys, threading, time, traceback

import hou

VERSION = 1
REG_DIR = os.path.join(os.path.expanduser("~"), ".houdini_brother", "sessions")
BASE_PORT = 18820
MAX_OUT = 200_000          # characters of stdout returned per request

_state = {"server": None, "thread": None, "port": None, "token": None, "reg": None}


# ----------------------------------------------------------------------------- main thread
def _on_main(fn):
    """Run fn on Houdini's main thread and return its result (or raise its error).
    It has to be the main thread: undo only records there (on a worker thread
    hou.undos.areEnabled() is False, so nothing Brother did could be undone)."""
    if hou.isUIAvailable():
        import hdefereval
        return hdefereval.executeInMainThreadWithResult(fn)
    if _state.get("pump") is None:               # hython without serve_forever: no main loop to hand to
        return fn()
    box = {"done": threading.Event()}
    _state["pump"].put((fn, box))
    box["done"].wait()
    if "error" in box:
        raise box["error"]
    return box["result"]


# ----------------------------------------------------------------------------- helpers
def _node(path):
    n = hou.node(path)
    if n is None:
        raise ValueError("node not found: %s" % path)
    return n


def _msgs(n):
    try:
        return {"errors": list(n.errors()), "warnings": list(n.warnings())}
    except hou.Error:
        return {"errors": [], "warnings": []}


def _parm_value(p, frame=None):
    try:
        v = p.evalAtFrame(frame) if frame is not None else p.eval()
    except hou.Error as e:
        return "<eval error: %s>" % e
    if isinstance(v, hou.Node):
        return v.path()
    if isinstance(v, str) and len(v) > 2000:
        return v[:2000] + "... (%d chars)" % len(v)
    return v


def _nondefault_parms(n, limit=80):
    out = {}
    for p in n.parms():
        try:
            if p.isAtDefault() or p.parmTemplate().type() == hou.parmTemplateType.FolderSet:
                continue
            entry = {"value": _parm_value(p)}
            try:
                entry["expression"] = p.expression()
            except hou.OperationFailed:
                pass
            if p.keyframes() and len(p.keyframes()) > 1:
                entry["keys"] = len(p.keyframes())
            out[p.name()] = entry
        except hou.Error:
            pass
        if len(out) >= limit:
            out["..."] = "more parms not shown"
            break
    return out


def _flags(n):
    f = {}
    for name in ("isDisplayFlagSet", "isRenderFlagSet", "isBypassed", "isTemplateFlagSet"):
        fn = getattr(n, name, None)
        if fn:
            try:
                if fn():
                    f[name.replace("is", "", 1).replace("FlagSet", "").replace("Set", "").lower()] = True
            except hou.Error:
                pass
    return f


def _geo(path, frame):
    n = _node(path)
    if not hasattr(n, "geometry"):
        raise ValueError("%s is not a SOP (it's %s)" % (path, n.type().category().name()))
    g = n.geometryAtFrame(frame) if frame is not None else n.geometry()
    if g is None:
        raise ValueError("%s has no geometry (errors: %s)" % (path, _msgs(n)["errors"]))
    return g


# ----------------------------------------------------------------------------- operations
def op_ping(args):
    return {"version": VERSION, "pid": os.getpid(), "hip": hou.hipFile.path(),
            "unsaved": hou.hipFile.hasUnsavedChanges(), "houdini": hou.applicationVersionString(),
            "license": hou.licenseCategory().name(), "ui": hou.isUIAvailable(), "frame": hou.frame()}


def op_scene(args):
    info = op_ping(args)
    info.update({"fps": hou.fps(), "range": list(hou.playbar.frameRange()),
                 "selected": [n.path() for n in hou.selectedNodes()]})
    if hou.isUIAvailable():
        ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
        info["network_editor"] = ne.pwd().path() if ne else None
        info["current_node"] = ne.currentNode().path() if ne and ne.currentNode() else None
    return info


def op_network(args):
    root = _node(args.get("path", "/obj"))
    depth = int(args.get("depth", 2))
    with_parms = bool(args.get("parms", False))

    def walk(n, d):
        rows = []
        for c in sorted(n.children(), key=lambda x: -x.position()[1]):
            row = {"path": c.path(), "type": c.type().name(),
                   "inputs": [i.path() if i else None for i in c.inputs()]}
            fl = _flags(c)
            if fl:
                row["flags"] = fl
            m = _msgs(c)
            if m["errors"] or m["warnings"]:
                row.update(m)
            if with_parms:
                row["parms"] = _nondefault_parms(c, 25)
            if c.children() and d < depth:
                row["children"] = walk(c, d + 1)
            elif c.children():
                row["children_count"] = len(c.children())
            rows.append(row)
        return rows
    return walk(root, 1)


def op_node(args):
    n = _node(args["path"])
    info = {"path": n.path(), "type": n.type().name(), "category": n.type().category().name(),
            "inputs": [i.path() if i else None for i in n.inputs()],
            "outputs": [o.path() for o in n.outputs()], "flags": _flags(n),
            "parms": _nondefault_parms(n)}
    info.update(_msgs(n))
    if "snippet" in info["parms"]:                     # VEX gets its own key, readable, once
        info["snippet"] = info["parms"].pop("snippet")["value"]
    try:
        info["cook_count"] = n.cookCount()
    except (hou.Error, AttributeError):
        pass
    for name in args.get("parm_names", []) or []:        # ask for default-valued parms by name
        p = n.parm(name) or n.parmTuple(name)
        info.setdefault("requested", {})[name] = (
            None if p is None else (list(p.eval()) if isinstance(p, hou.ParmTuple) else _parm_value(p)))
    return info


def op_problems(args):
    root = _node(args.get("path", "/"))
    rows = []
    for n in root.allSubChildren():
        m = _msgs(n)
        if m["errors"] or m["warnings"]:
            rows.append(dict(path=n.path(), type=n.type().name(), **m))
    return {"count": len(rows), "nodes": rows[:300]}


def op_geometry(args):
    frame = args.get("frame")
    g = _geo(args["path"], frame)
    samples = int(args.get("samples", 3))

    def attribs(cls, items):
        out = []
        for a in {"point": g.pointAttribs, "prim": g.primAttribs, "vertex": g.vertexAttribs,
                  "detail": g.globalAttribs}[cls]():
            row = {"name": a.name(), "type": a.dataType().name(), "size": a.size()}
            if a.isArrayType():
                row["array"] = True
            if cls == "detail":
                row["value"] = _jsonable(g.attribValue(a.name()))
            elif samples and items:
                row["first"] = [_jsonable(x.attribValue(a)) for x in items[:samples]]
            out.append(row)
        return out
    pts, prs = g.points(), g.prims()
    bb = g.boundingBox()
    prim_types = {}
    for p in prs[:20000]:
        prim_types[p.type().name()] = prim_types.get(p.type().name(), 0) + 1
    return {"path": args["path"], "frame": frame if frame is not None else hou.frame(),
            "points": len(pts), "prims": len(prs), "vertices": g.intrinsicValue("vertexcount"),
            "prim_types": prim_types,
            "bbox": {"min": list(bb.minvec()), "max": list(bb.maxvec()), "size": list(bb.sizevec())},
            "point_attribs": attribs("point", pts), "prim_attribs": attribs("prim", prs),
            "vertex_attribs": attribs("vertex", []), "detail_attribs": attribs("detail", []),
            "point_groups": [x.name() for x in g.pointGroups()],
            "prim_groups": [x.name() for x in g.primGroups()]}


def _jsonable(v):
    if isinstance(v, (hou.Vector2, hou.Vector3, hou.Vector4, hou.Quaternion)):
        return [round(x, 6) for x in v]
    if isinstance(v, (hou.Matrix3, hou.Matrix4)):
        return [[round(x, 6) for x in row] for row in v.asTupleOfTuples()]
    if isinstance(v, float):
        return round(v, 6) if math.isfinite(v) else str(v)
    if isinstance(v, (tuple, list)):
        return [_jsonable(x) for x in v]
    return v


def op_attrib(args):
    g = _geo(args["path"], args.get("frame"))
    cls = args.get("cls", "point")
    items = {"point": g.points, "prim": g.prims}[cls]()
    start, count = int(args.get("start", 0)), min(int(args.get("count", 20)), 2000)
    name = args["name"]
    if (g.findPointAttrib if cls == "point" else g.findPrimAttrib)(name) is None and name != "P":
        raise ValueError("no %s attribute %r" % (cls, name))
    rows = []
    for it in items[start:start + count]:
        v = it.position() if (name == "P" and cls == "point") else it.attribValue(name)
        rows.append([it.number(), _jsonable(v)])
    return {"total": len(items), "start": start, "values": rows}


def op_compare(args):
    """Nearest-neighbour point distance between two SOPs, both directions, per frame."""
    import numpy as np
    out = []
    cap = int(args.get("max_points", 20000))
    for f in args.get("frames") or [hou.frame()]:
        a = np.array(_geo(args["a"], f).pointFloatAttribValues("P"), dtype=np.float64).reshape(-1, 3)
        b = np.array(_geo(args["b"], f).pointFloatAttribValues("P"), dtype=np.float64).reshape(-1, 3)
        row = {"frame": f, "a_points": len(a), "b_points": len(b)}
        if len(a) == 0 or len(b) == 0:
            row["note"] = "empty"
            out.append(row)
            continue
        sampled = False
        if len(a) > cap or len(b) > cap:
            rng = np.random.default_rng(0)
            a = a[rng.choice(len(a), min(len(a), cap), replace=False)]
            b = b[rng.choice(len(b), min(len(b), cap), replace=False)]
            sampled = True

        def worst(x, y):
            best = np.empty(len(x))
            for i in range(0, len(x), 512):
                d = ((x[i:i + 512, None, :] - y[None, :, :]) ** 2).sum(-1)
                best[i:i + 512] = d.min(1)
            return float(np.sqrt(best.max())), float(np.sqrt(best).mean())
        row["a_to_b_max"], row["a_to_b_mean"] = worst(a, b)
        row["b_to_a_max"], row["b_to_a_mean"] = worst(b, a)
        if sampled:
            row["note"] = "sampled %d points per side - an upper bound is NOT guaranteed" % cap
        out.append(row)
    return out


def op_capture(args):
    """Flipbook one frame of the Scene Viewer to a PNG. GUI sessions only."""
    if not hou.isUIAvailable():
        raise RuntimeError("no UI in this session (hython) - nothing to capture")
    viewers = [t for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.SceneViewer]
    if not viewers:
        raise RuntimeError("no Scene Viewer pane open")
    shown = [t for t in viewers if t.isCurrentTab()]
    if not shown:
        # a Scene Viewer hidden behind another tab (Python Shell, ...) flipbooks nothing, silently
        raise RuntimeError("the Scene Viewer tab is hidden behind another tab - ask Plug to click "
                           "the Scene View tab, then try again")
    sv = shown[0]
    f = int(args.get("frame", hou.frame()))
    folder = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".houdini_brother")
    pattern = os.path.join(folder, "capture_%d_$F4.png" % os.getpid())
    path = pattern.replace("$F4", "%04d" % f)
    if os.path.exists(path):
        os.remove(path)
    s = sv.flipbookSettings().stash()
    s.frameRange((f, f))
    s.output(pattern)
    s.outputToMPlay(False)
    res = args.get("resolution")
    if res:
        s.useResolution(True)
        s.resolution(tuple(res))
    sv.flipbook(sv.curViewport(), s)
    if not os.path.exists(path):
        raise RuntimeError("the flipbook ran but wrote no image (%s)" % path)
    return {"file": path, "frame": f}


def op_run(args):
    """Run Python in this session. Inside ONE undo group, so Ctrl+Z reverts it.
    Assign to `result` to return a value; print() output is returned too."""
    code = args["code"]
    label = args.get("label") or "Brother: run python"
    ns = {"hou": hou, "result": None}
    buf = io.StringIO()
    with hou.undos.group(label), contextlib.redirect_stdout(buf):
        exec(compile(code, "<brother>", "exec"), ns)
    text = buf.getvalue()
    return {"stdout": text[-MAX_OUT:], "result": _safe_json(ns.get("result")),
            "undo_label": label}


def op_set_parm(args):
    n = _node(args["path"])
    p = n.parm(args["parm"]) or n.parmTuple(args["parm"])
    if p is None:
        raise ValueError("no parm %r on %s" % (args["parm"], n.path()))
    label = "Brother: %s/%s" % (n.name(), args["parm"])
    with hou.undos.group(label):
        before = list(p.eval()) if isinstance(p, hou.ParmTuple) else _parm_value(p)
        if args.get("expression"):
            p.setExpression(args["expression"])
        else:
            p.set(args["value"])
        after = list(p.eval()) if isinstance(p, hou.ParmTuple) else _parm_value(p)
    return {"before": before, "after": after, "undo_label": label}


def op_undo(args):
    """Undo Brother's last change - only if the top of the undo stack IS one of Brother's
    ("Brother: ..."), so this can never undo something Plug did himself."""
    if not hou.undos.areEnabled():
        raise RuntimeError("undo is disabled in this session")
    labels = hou.undos.undoLabels()
    if not labels:
        raise RuntimeError("nothing to undo")
    if not labels[0].startswith("Brother:"):
        raise RuntimeError("the last undo step is %r, not Brother's - not undoing Plug's work" % labels[0])
    hou.undos.performUndo()
    return {"undone": labels[0], "next_on_stack": (hou.undos.undoLabels() or [None])[0]}


def _safe_json(v):
    try:
        json.dumps(v)
        return v
    except TypeError:
        try:
            return _jsonable(v)
        except Exception:
            return repr(v)


OPS = {"ping": op_ping, "scene": op_scene, "network": op_network, "node": op_node,
       "problems": op_problems, "geometry": op_geometry, "attrib": op_attrib,
       "compare": op_compare, "capture": op_capture, "run": op_run, "set_parm": op_set_parm,
       "undo": op_undo}

if hou.isUIAvailable():                  # the virtual cursor only exists where there is a window
    import importlib
    import brother_cursor
    importlib.reload(brother_cursor)     # a reload of brother_link picks up cursor changes too
    OPS.update(brother_cursor.OPS)
    import brother_demo
    brother_demo.stop_all()              # a reload never leaves a demo runner behind
    importlib.reload(brother_demo)
    OPS.update(brother_demo.OPS)


# ----------------------------------------------------------------------------- "in control"
# Requests that only LOOK never dim the screen; everything that acts does.
_LOOK_OPS = {"ping", "scene", "network", "node", "problems", "geometry", "attrib", "compare",
             "capture", "screenshot", "pane_screenshot", "capture_pane", "cursor_hide",
             "demo_status", "demo_stop",          # stopping must not re-light the frame
             "action_status", "action_stop"}


def _is_control(name, args):
    if name in _LOOK_OPS:
        return False
    if name == "run" and "read-only" in str(args.get("label", "")).lower():
        return False
    return True


def _control(active):
    bc = sys.modules.get("brother_cursor")
    if bc is None or not hou.isUIAvailable():
        return
    try:
        bc.control(active)
    except Exception:                    # the frame is decoration - never fail a request over it
        pass


# ----------------------------------------------------------------------------- server
def _handle(conn):
    with conn:
        f = conn.makefile("rwb")
        for line in f:
            try:
                req = json.loads(line)
                if not secrets.compare_digest(str(req.get("token", "")), _state["token"]):
                    resp = {"ok": False, "error": "bad token"}
                else:
                    op = OPS.get(req.get("op"))
                    if op is None:
                        resp = {"ok": False, "error": "unknown op %r" % req.get("op")}
                    else:
                        args = req.get("args") or {}
                        ctl = _is_control(req.get("op"), args)

                        def work(op=op, args=args, ctl=ctl):
                            if ctl:
                                _control(True)
                            try:
                                return _safe_json(op(args))
                            finally:
                                if ctl:
                                    _control(False)
                        resp = {"ok": True, "result": _on_main(work)}
            except (ValueError, KeyError, RuntimeError) as e:          # expected: bad path, no UI...
                resp = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
            except Exception as e:
                resp = {"ok": False, "error": "%s: %s" % (type(e).__name__, e),
                        "trace": traceback.format_exc()[-4000:]}
            f.write((json.dumps(resp, default=repr) + "\n").encode("utf8"))
            f.flush()


def _serve(srv):
    while _state["server"] is srv:
        try:
            conn, _ = srv.accept()
        except OSError:
            break
        threading.Thread(target=_handle, args=(conn,), daemon=True).start()


def _write_registry():
    os.makedirs(REG_DIR, exist_ok=True)
    path = os.path.join(REG_DIR, "%d.json" % os.getpid())
    with open(path, "w", encoding="utf8") as fh:
        json.dump({"pid": os.getpid(), "port": _state["port"], "token": _state["token"],
                   "version": VERSION, "houdini": hou.applicationVersionString(),
                   "hip": hou.hipFile.path(), "started": time.time()}, fh)
    try:                                           # POSIX only: on Windows chmod just sets read-only; the file is private because it sits in the user profile
        os.chmod(path, 0o600)
    except OSError:
        pass
    _state["reg"] = path


def start(port=None, quiet=False):
    if _state["server"] is not None:
        if not quiet:
            print("brother_link already running on port %d" % _state["port"])
        return _state["port"]
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    for p in ([port] if port else range(BASE_PORT, BASE_PORT + 50)):
        try:
            srv.bind(("127.0.0.1", p))
            break
        except OSError:
            continue
    else:
        raise RuntimeError("no free port from %d" % BASE_PORT)
    srv.listen(4)
    _state.update(server=srv, port=srv.getsockname()[1], token=secrets.token_hex(16))
    _write_registry()
    t = threading.Thread(target=_serve, args=(srv,), daemon=True)
    t.start()
    _state["thread"] = t
    if not quiet:                       # printing pops the Houdini Console - silent when automatic
        print("brother_link: Brother can now see this session (%s) - port %d. brother_link.stop() to close."
              % (os.path.basename(hou.hipFile.path()), _state["port"]))
    return _state["port"]


def stop():
    srv, _state["server"] = _state["server"], None
    if srv is not None:
        try:
            srv.close()
        except OSError:
            pass
    if "brother_cursor" in sys.modules:
        try:
            sys.modules["brother_cursor"].remove()
        except Exception:
            pass
    if _state["reg"] and os.path.exists(_state["reg"]):
        os.remove(_state["reg"])
    _state["reg"] = None
    print("brother_link stopped")


def serve_forever():
    """For hython sessions: start, then run every request on THIS (main) thread until killed."""
    import queue
    _state["pump"] = queue.Queue()
    start()
    while _state["server"] is not None:
        try:
            fn, box = _state["pump"].get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            box["result"] = fn()
        except BaseException as e:
            box["error"] = e
        box["done"].set()


atexit.register(stop)
