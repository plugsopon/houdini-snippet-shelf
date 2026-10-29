"""brother_demo - the "Brother is working" demo loop inside Houdini, played by Houdini itself.

One explicit start (op demo_start) plays the storyboard from brother_demo_plan on the three
prompt Wrangles in /obj/BROTHER_DEMO_246_A, cycle after cycle, until Stop:
  * the control frame is HELD the whole time (renewed every tick, ttl 4 s) - it never drops
    between steps, and if this runner ever dies the frame still ends within 4 s;
  * the virtual cursor glides to each node, "presses", carries it, "releases";
  * prompts are typed into the snippet one character at a time, with partial edits.

What is real and what is animated - said plainly, because it matters:
  * Houdini 21's Network Editor does NOT accept synthetic Qt drags (tested 2026-10-25: a real
    press -> 40 moves -> release on a node's body moved nothing, and the same on a wire port
    connected nothing; Plug's real mouse is never moved, so there is no other way in). So a
    node move here is node.setPosition() every frame along the cursor's path, and a wire is a
    line the overlay draws from the output port to the cursor, then setInput() on "release".
    The motion is continuous and synced to the cursor; it is NOT Houdini's own drag.
  * Typing is parm.set() once per character while the cursor points at the Parameter pane,
    not key events (keys sent to the wrong widget could fire Network Editor hotkeys).
  * Animation frames are kept off the undo stack (hou.undos.disabler) - a loop would push
    hundreds of steps. The one-time rename IS a normal "Brother:" undo step.

Stop: the floating STOP button, the Esc key (anywhere in Houdini), op demo_stop, Houdini
quitting, or any error. Latency: one tick (15 ms) to notice + the cleanup below. Cleanup always
runs (finally): the generator is closed, the overlay wire cleared, the hold released, the STOP
button and the Esc filter removed, and every Network Editor's network, view and current node,
the node selection and the frame are put back as they were at start. Nothing is saved,
reloaded or deleted; the scene stays honestly dirty.
"""
import time, traceback

import hou
from PySide6 import QtCore, QtWidgets

import brother_demo_plan as plan

TICK_MS = 15
HOLD_TTL = 4.0

_run = {"r": None}


def _bc():
    import sys
    return sys.modules["brother_cursor"]


def _app():
    return QtWidgets.QApplication.instance()


def _frames(seconds):
    t_end = time.time() + seconds
    while time.time() < t_end:
        yield


class _EscFilter(QtCore.QObject):
    def __init__(self, runner):
        super().__init__()
        self.runner = runner

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.KeyPress and ev.key() == QtCore.Qt.Key_Escape:
            self.runner.request_stop("esc")
        return False                     # never swallow Plug's key


class _Runner(object):
    def __init__(self, cycles):
        self.cycles = cycles             # None = loop until Stop
        self.cycle = 0
        self.step = None
        self.state = "starting"
        self.error = None
        self.stop_reason = None
        self.t_start = time.time()
        self.t_stop_req = None
        self.t_done = None
        self.counts = {"focus": 0, "type_chars": 0, "api_move": 0, "wire": 0, "unwire": 0}
        self.snap = None
        self.ne = None
        self.it = None
        self.timer = None
        self.button = None
        self.esc = None
        self.texts = {}

    # -------------------------------------------------------------- lifecycle
    def start(self):
        net = hou.node(plan.DEMO_NET)
        if net is None:
            raise RuntimeError("no demo network %s" % plan.DEMO_NET)
        self.nodes = _prepare_nodes(net)
        eds = [t for t in hou.ui.paneTabs()
               if t.type() == hou.paneTabType.NetworkEditor and t.isCurrentTab()]
        if not eds:
            raise RuntimeError("no Network Editor is open")
        self.snap = _snapshot(eds)
        self.ne = eds[0]
        self.parms = {k: _snippet_parm(n) for k, n in self.nodes.items()}
        self.texts = {k: p.eval() for k, p in self.parms.items()}
        bc = _bc()
        bc.hold(HOLD_TTL)
        self.button = _stop_button(self)
        self.esc = _EscFilter(self)
        _app().installEventFilter(self.esc)
        _app().aboutToQuit.connect(self._on_quit)
        self.quit_hooked = True
        self.ne.setPwd(net)
        self.ne.setVisibleBounds(hou.BoundingRect(*plan.FRAME))
        self.it = self._play()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)
        self.state = "running"

    def request_stop(self, reason):
        if self.t_stop_req is None:
            self.t_stop_req = time.time()
            self.stop_reason = reason

    def _on_quit(self):
        self.request_stop("houdini quitting")
        self._finish(restore=False)

    def _tick(self):
        if self.state != "running":
            return
        try:
            _bc().hold(HOLD_TTL)
            if self.t_stop_req is not None:
                return self._finish()
            next(self.it)
        except StopIteration:
            self.stop_reason = self.stop_reason or "cycles done"
            self._finish()
        except Exception as e:
            self.error = "%s: %s" % (type(e).__name__, e)
            self.trace = traceback.format_exc()[-3000:]
            self.stop_reason = self.stop_reason or "error"
            self._finish()

    def _finish(self, restore=True):
        if self.state in ("stopping", "stopped"):
            return
        self.state = "stopping"
        notes = []
        for name, fn in (
                ("timer", lambda: self.timer and self.timer.stop()),
                ("generator", lambda: self.it and self.it.close()),       # runs every finally inside
                ("wire", lambda: _clear_wire()),
                ("hold", lambda: _bc().release_hold()),
                ("esc", lambda: self.esc and _app().removeEventFilter(self.esc)),
                ("quit_hook", lambda: getattr(self, "quit_hooked", False)
                 and _app().aboutToQuit.disconnect(self._on_quit)),
                ("button", lambda: self.button and (self.button.close(), self.button.deleteLater())),
                ("restore", lambda: restore and self.snap and _restore(self.snap))):
            try:
                fn()
            except Exception as e:                      # one failed step never skips the rest
                notes.append("%s: %s" % (name, e))
        self.cleanup_notes = notes
        self.t_done = time.time()
        self.state = "stopped"

    def status(self):
        lat = None
        if self.t_stop_req is not None and self.t_done is not None:
            lat = round((self.t_done - self.t_stop_req) * 1000, 1)
        return {"state": self.state, "cycle": self.cycle, "step": self.step,
                "seconds": round((self.t_done or time.time()) - self.t_start, 2),
                "counts": dict(self.counts), "stop_reason": self.stop_reason,
                "stop_latency_ms": lat, "error": self.error,
                "cleanup_notes": getattr(self, "cleanup_notes", None),
                "held": _bc().held(),
                "nodes": {k: n.path() for k, n in getattr(self, "nodes", {}).items()},
                "how": {"api_move": "api-animated setPosition synced to cursor (native drag not accepted by H21 net editor)",
                        "wire": "overlay line + setInput on release (native wire not accepted)",
                        "typing": "parm.set per character"}}

    # -------------------------------------------------------------- the storyboard
    def _play(self):
        while self.cycles is None or self.cycle < self.cycles:
            for s in plan.build_cycle(self.cycle, self.texts):
                self.step = s["kind"]
                yield from getattr(self, "_do_" + s["kind"])(s)
            self.cycle += 1

    def _point(self, node):
        c = node.position() + node.size() * 0.5
        return _bc().net_point(self.ne, (c[0], c[1]))

    def _glide_to(self, to, seconds=None):
        bc = _bc()
        ov = bc._overlay()
        a = (ov.pos_.x(), ov.pos_.y())
        dist = ((to[0] - a[0]) ** 2 + (to[1] - a[1]) ** 2) ** 0.5
        seconds = seconds if seconds is not None else min(0.8, 0.22 + dist / 1800.0)
        t0 = time.time()
        while True:
            k = min(1.0, (time.time() - t0) / seconds)
            e = k * k * (3 - 2 * k)
            _cursor((a[0] + (to[0] - a[0]) * e, a[1] + (to[1] - a[1]) * e))
            if k >= 1.0:
                return
            yield

    def _do_pause(self, s):
        yield from _frames(s["seconds"])

    def _do_focus(self, s):
        node = self.nodes[s["key"]]
        yield from self._glide_to(self._point(node))
        _ripple(self._point(node))
        with hou.undos.disabler():
            node.setSelected(True, clear_all_selected=True)
            node.setCurrent(True)
        self.counts["focus"] += 1
        yield from _frames(0.15)
        pp = _bc()._parm_pane_for(self.ne, node)            # point at the Parameter pane
        if pp is not None:
            r = _bc()._pane_rect(pp)
            yield from self._glide_to((r.x() + min(r.width() * 0.35, 260), r.y() + min(r.height() * 0.45, 220)))

    def _do_type(self, s):
        parm = self.parms[s["key"]]
        for text, wait in s["states"]:
            with hou.undos.disabler():
                parm.set(text)
            self.texts[s["key"]] = text
            self.counts["type_chars"] += 1
            yield from _frames(wait)
            yield

    def _do_api_move(self, s):
        node = self.nodes[s["key"]]
        start = node.position()
        to = hou.Vector2(*s["to"])
        yield from self._glide_to(self._point(node))
        _ripple(self._point(node))                          # "press"
        yield from _frames(0.08)
        t0, secs = time.time(), 0.85
        while True:
            k = min(1.0, (time.time() - t0) / secs)
            e = k * k * (3 - 2 * k)
            with hou.undos.disabler():
                node.setPosition(start + (to - start) * e)
            _cursor(self._point(node))                      # the cursor carries the node
            if k >= 1.0:
                break
            yield
        _ripple(self._point(node))                          # "release"
        self.counts["api_move"] += 1
        yield from _frames(0.1)

    def _port(self, node, out):
        p, sz = node.position(), node.size()
        x = p[0] + sz[0] - 0.06 if out else p[0] + 0.06
        return _bc().net_point(self.ne, (x, p[1] + 0.25))

    def _do_wire(self, s):
        src, dst = self.nodes[s["src"]], self.nodes[s["dst"]]
        a, b = self._port(src, True), self._port(dst, False)
        yield from self._glide_to(a)
        _ripple(a)
        ov = _bc()._overlay()
        try:
            t0, secs = time.time(), 0.8
            while True:
                k = min(1.0, (time.time() - t0) / secs)
                e = k * k * (3 - 2 * k)
                pt = (a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e)
                ov.wire = (QtCore.QPointF(*a), QtCore.QPointF(*pt))
                _cursor(pt)
                if k >= 1.0:
                    break
                yield
        finally:
            ov.wire = None
            ov.update()
        with hou.undos.disabler():
            dst.setInput(0, src)
        _ripple(b)
        self.counts["wire"] += 1
        yield from _frames(0.12)

    def _do_unwire(self, s):
        dst = self.nodes[s["dst"]]
        if not dst.inputs():
            return
        b = self._port(dst, False)
        yield from self._glide_to(b)
        _ripple(b)
        with hou.undos.disabler():
            dst.setInput(0, None)
        self.counts["unwire"] += 1
        yield from _frames(0.12)


# ----------------------------------------------------------------------------- helpers
def _cursor(pt):
    ov = _bc()._overlay()
    ov.pos_ = QtCore.QPointF(*pt)
    ov.last_active = ov.last_move = time.time()
    ov.has_cursor = True
    ov.update()


def _ripple(pt):
    _bc()._overlay().ripples.append((QtCore.QPointF(*pt), time.time()))


def _clear_wire():
    ov = _bc()._ov.get("w")
    if ov is not None:
        ov.wire = None
        ov.update()


def _snippet_parm(node):
    """The code field of a wrangle: COP wrangles (H21 Copernicus) name it 'vexsnippet',
    SOP/attrib wrangles 'snippet'. Refuse anything else rather than type into a random field."""
    for name in ("vexsnippet", "snippet"):
        p = node.parm(name)
        if p is not None:
            return p
    raise RuntimeError("%s has no wrangle snippet parm" % node.path())


def _prepare_nodes(net):
    """{key: node}. Renames the rehearsal's demo_wrangle_N once (one 'Brother:' undo step);
    refuses if a target name is taken by anything that is not ours."""
    out, todo = {}, []
    for key, (name, old) in plan.NODES.items():
        n = net.node(name)
        if n is None:
            o = net.node(old)
            if o is None:
                raise RuntimeError("neither %s nor %s in %s" % (name, old, net.path()))
            todo.append((key, o, name))
        else:
            out[key] = n
    for key, n in list(out.items()) + [(k, o) for k, o, _ in todo]:
        if n.type().name() != "wrangle":
            raise RuntimeError("%s is a %s, not a Wrangle - not touching it" % (n.path(), n.type().name()))
    if todo:
        with hou.undos.group("Brother: name demo prompt nodes"):
            for key, o, name in todo:
                o.setName(name)
                out[key] = o
    return out


def _snapshot(eds):
    return {"eds": [(t, t.pwd(), t.visibleBounds(), t.currentNode()) for t in eds],
            "sel": list(hou.selectedNodes()), "frame": hou.frame()}


def _restore(snap):
    with hou.undos.disabler():
        for t, pwd, vb, cur in snap["eds"]:
            t.setPwd(pwd)
            if cur is not None:
                try:
                    t.setCurrentNode(cur, False)
                except hou.Error:
                    pass
            t.setVisibleBounds(vb)
        hou.clearAllSelected()
        for n in snap["sel"]:
            try:
                n.setSelected(True)
            except hou.ObjectWasDeleted:
                pass
        if hou.frame() != snap["frame"]:
            hou.setFrame(snap["frame"])


def _stop_button(runner):
    mw = hou.qt.mainWindow()
    b = QtWidgets.QPushButton("■  STOP Brother demo   (Esc)", mw)
    b.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    b.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
    b.setStyleSheet("QPushButton{background:#f32285;color:white;font-weight:bold;padding:8px 18px;"
                    "border:2px solid white;border-radius:6px} QPushButton:hover{background:#ff4fa0}")
    b.clicked.connect(lambda: runner.request_stop("stop button"))
    b.adjustSize()
    tl = mw.mapToGlobal(QtCore.QPoint(0, 0))
    b.move(tl.x() + (mw.width() - b.width()) // 2, tl.y() + 8)
    b.show()
    return b


# ----------------------------------------------------------------------------- ops
def op_demo_start(args):
    r = _run["r"]
    if r is not None and r.state in ("starting", "running", "stopping"):
        raise RuntimeError("the demo is already running - stop it first")
    cycles = args.get("cycles")
    r = _Runner(int(cycles) if cycles is not None else None)
    _run["r"] = r
    try:
        r.start()
    except Exception as e:
        r.error = "%s: %s" % (type(e).__name__, e)
        r.stop_reason = "start failed"
        r._finish()
        raise
    return r.status()


def op_demo_stop(args):
    r = _run["r"]
    if r is None:
        return {"state": "never started"}
    r.request_stop(args.get("reason", "demo_stop"))
    if r.state == "running":
        r._finish()
    return r.status()


def op_demo_status(args):
    r = _run["r"]
    return r.status() if r is not None else {"state": "never started"}


def stop_all():
    """For brother_link's shutdown / a module reload: never leave a runner behind."""
    r = _run["r"]
    if r is not None and r.state == "running":
        r.request_stop("shutdown")
        r._finish()


OPS = {"demo_start": op_demo_start, "demo_stop": op_demo_stop, "demo_status": op_demo_status}
