"""houdini-live MCP server: lets Claude inspect (and, when asked, change) Plug's OPEN Houdini sessions.

Each Houdini that should be visible runs brother_link.start() (see mcp/README.md). This server
finds them through %USERPROFILE%\\.houdini_brother\\sessions\\*.json and talks to the one
selected with houdini_use_session. With only one session open it is used automatically.
"""
import glob, json, os, socket, sys, time

HOUDINI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "houdini")   # brother_link lives here

from mcp.server.fastmcp import FastMCP, Image

REG_DIR = os.path.join(os.path.expanduser("~"), ".houdini_brother", "sessions")
TIMEOUT = 120.0            # a heavy cook can take a while; the request runs on Houdini's main thread

mcp = FastMCP("houdini-live")
# the Houdini chat panel launches claude with HOUDINI_BROTHER_PID = its own Houdini, so a chat
# is always bound to the Houdini it was opened from - no houdini_use_session needed
_pin = os.environ.get("HOUDINI_BROTHER_PID")
_selected = {"pid": int(_pin) if _pin and _pin.isdigit() else None}


# ----------------------------------------------------------------------------- transport
def _pid_alive(pid):
    if sys.platform == "win32":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259                                      # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _call(reg, op, args=None, timeout=TIMEOUT):
    with socket.create_connection(("127.0.0.1", reg["port"]), timeout=timeout) as s:
        s.sendall((json.dumps({"token": reg["token"], "op": op, "args": args or {}}) + "\n").encode("utf8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            buf += chunk
    resp = json.loads(buf)
    if not resp.get("ok"):
        raise RuntimeError(resp.get("error", "unknown error") + ("\n" + resp["trace"] if resp.get("trace") else ""))
    return resp["result"]


def _sessions():
    """Live sessions; stale registry files (Houdini closed or crashed) are removed."""
    out = []
    for path in glob.glob(os.path.join(REG_DIR, "*.json")):
        try:
            reg = json.load(open(path, encoding="utf8"))
        except (OSError, ValueError):
            continue
        if not _pid_alive(reg.get("pid", -1)):
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        try:
            info = _call(reg, "ping", timeout=3)
        except OSError:
            info = None                 # alive but not answering (busy cooking, or link stopped)
        out.append((reg, info))
    return sorted(out, key=lambda x: x[0].get("started", 0))


def _current():
    ss = _sessions()
    if not ss:
        raise RuntimeError("No Houdini session is connected. In Houdini's Python Shell run:\n"
                           "  import sys; sys.path.insert(0, r\"%s\")\n"
                           "  import brother_link; brother_link.start()" % HOUDINI_DIR)
    if _selected["pid"] is not None:
        for reg, _ in ss:
            if reg["pid"] == _selected["pid"]:
                return reg
        gone = _selected["pid"]
        if not _pin:
            _selected["pid"] = None
        raise RuntimeError("The Houdini session (pid %s) is not connected - it may have closed or its "
                           "link stopped." % gone)
    if len(ss) == 1:
        return ss[0][0]
    raise RuntimeError("%d Houdini sessions are open - call houdini_sessions, then houdini_use_session "
                       "with the one Plug means." % len(ss))


def _run(op, args=None):
    reg = _current()
    res = _call(reg, op, args)
    return json.dumps(res, ensure_ascii=False, indent=1, default=str)


# ----------------------------------------------------------------------------- tools: sessions
@mcp.tool()
def houdini_sessions() -> str:
    """List every open Houdini session that has brother_link running: pid, hip file, unsaved flag,
    Houdini version, current frame, and which one is selected. Call this first when Plug has
    several Houdinis open, then houdini_use_session."""
    rows = []
    for reg, info in _sessions():
        rows.append({"pid": reg["pid"], "port": reg["port"],
                     "hip": (info or {}).get("hip", reg.get("hip")),
                     "unsaved": (info or {}).get("unsaved"), "houdini": reg.get("houdini"),
                     "frame": (info or {}).get("frame"), "answering": info is not None,
                     "selected": reg["pid"] == _selected["pid"],
                     "pinned_by_chat": bool(_pin) and str(reg["pid"]) == _pin})
    if not rows:
        return "No sessions. Plug needs to run brother_link.start() inside Houdini (see mcp/README.md)."
    return json.dumps(rows, ensure_ascii=False, indent=1)


@mcp.tool()
def houdini_use_session(session: str) -> str:
    """Select which open Houdini to talk to. `session` is a pid, or part of the hip file name
    (e.g. "emittingRBD_root"). Must match exactly one session."""
    ss = _sessions()
    hits = [(r, i) for r, i in ss if session == str(r["pid"])]
    if not hits:
        key = session.lower()
        hits = [(r, i) for r, i in ss if key in str((i or {}).get("hip", r.get("hip", ""))).lower()]
    if len(hits) != 1:
        return "%d sessions match %r: %s" % (len(hits), session,
                                             [((i or {}).get("hip", r.get("hip")), r["pid"]) for r, i in ss])
    _selected["pid"] = hits[0][0]["pid"]
    return "Using pid %d: %s" % (_selected["pid"], (hits[0][1] or {}).get("hip", hits[0][0].get("hip")))


# ----------------------------------------------------------------------------- tools: looking
@mcp.tool()
def houdini_scene() -> str:
    """The selected session: hip path, unsaved changes, frame, fps, frame range, selected nodes,
    the network the Network Editor shows and its current node. Start debugging here - it tells
    you what Plug is looking at."""
    return _run("scene")


@mcp.tool()
def houdini_network(path: str = "/obj", depth: int = 2, parms: bool = False) -> str:
    """Nodes under `path`: type, inputs, flags, errors/warnings, children up to `depth`.
    parms=True adds each node's non-default parms (bigger output)."""
    return _run("network", {"path": path, "depth": depth, "parms": parms})


@mcp.tool()
def houdini_node(path: str, parm_names: list[str] | None = None) -> str:
    """One node in detail: inputs, outputs, flags, errors, warnings, every non-default parm
    (value + expression), and the VEX snippet for wrangles. Parms at their default are hidden;
    ask for them by name in parm_names."""
    return _run("node", {"path": path, "parm_names": parm_names or []})


@mcp.tool()
def houdini_problems(path: str = "/") -> str:
    """Every node under `path` that currently has errors or warnings."""
    return _run("problems", {"path": path})


@mcp.tool()
def houdini_geometry(path: str, frame: float | None = None, samples: int = 3) -> str:
    """A SOP's geometry: point/prim/vertex counts, prim types, bounding box, every attribute
    (type, size, first `samples` values) and groups. `frame` evaluates another frame WITHOUT
    moving Plug's playbar."""
    return _run("geometry", {"path": path, "frame": frame, "samples": samples})


@mcp.tool()
def houdini_attrib(path: str, name: str, cls: str = "point", start: int = 0, count: int = 20,
                   frame: float | None = None) -> str:
    """Values of one attribute (cls = point or prim) for elements start..start+count."""
    return _run("attrib", {"path": path, "name": name, "cls": cls, "start": start,
                           "count": count, "frame": frame})


@mcp.tool()
def houdini_compare(a: str, b: str, frames: list[float] | None = None) -> str:
    """Nearest-neighbour point distance between two SOPs at each frame, both directions (max and
    mean). Point order does not matter. Use it to prove two setups give the same result."""
    return _run("compare", {"a": a, "b": b, "frames": frames})


@mcp.tool()
def houdini_viewport(frame: float | None = None) -> Image:
    """A picture of Plug's Scene Viewer (one flipbook frame) at the current or given frame."""
    res = json.loads(_run("capture", {"frame": frame} if frame is not None else {}))
    with open(res["file"], "rb") as fh:
        data = fh.read()
    try:
        # the flipbook's background is transparent; shown as-is it reads as a blank white image
        import io
        from PIL import Image as PILImage
        im = PILImage.open(io.BytesIO(data))
        if im.mode in ("RGBA", "LA"):
            bg = PILImage.new("RGB", im.size, (40, 44, 50))
            bg.paste(im, mask=im.getchannel("A"))
            buf = io.BytesIO()
            bg.save(buf, "PNG")
            data = buf.getvalue()
    except ImportError:
        pass
    return Image(data=data, format="png")


# ----------------------------------------------------------------------------- tools: changing
@mcp.tool()
def houdini_run_python(code: str, label: str) -> str:
    """Run Python inside the selected Houdini, with `hou` available. Assign to `result` to return a
    value; print() output comes back too. Runs as ONE undo group named `label` (write it as
    "Brother: <what>") so Plug can Ctrl+Z it. Only change the scene when Plug asked for it;
    for looking, prefer the read-only tools."""
    return _run("run", {"code": code, "label": label})


@mcp.tool()
def houdini_set_parm(path: str, parm: str, value: float | int | str | list | None = None,
                     expression: str | None = None) -> str:
    """Set one parm (or parm tuple) to a value, or give it an expression. One undo step.
    Returns the value before and after. Only when Plug asked for the change."""
    return _run("set_parm", {"path": path, "parm": parm, "value": value, "expression": expression})


# ----------------------------------------------------------------------------- tools: virtual cursor
@mcp.tool()
def houdini_screenshot() -> list:
    """The whole Houdini main window as an image. Its pixel coordinates are the coordinates
    houdini_pointer / houdini_click take: (0, 0) is the window's top-left corner.
    Look here first to find where a field or button is."""
    res = json.loads(_run("screenshot"))
    with open(res["file"], "rb") as fh:
        data = fh.read()
    return ["window %dx%d (click coordinates = image pixels)" % (res["width"], res["height"]),
            Image(data=data, format="png")]


@mcp.tool()
def houdini_pointer(x: float, y: float) -> str:
    """Glide Brother's visible cursor to (x, y) in window coordinates, without clicking.
    Plug's real mouse never moves. Returns which widget is under that point."""
    return _run("pointer", {"x": x, "y": y})


@mcp.tool()
def houdini_click(x: float, y: float, button: str = "left", double: bool = False) -> str:
    """Glide the visible cursor to (x, y) and click there (left/right/middle, optional double).
    Delivered as Qt events to the widget under the point - Plug's mouse is not used.
    Returns the widget clicked and which widget has keyboard focus afterwards."""
    return _run("click", {"x": x, "y": y, "button": button, "double": double})


@mcp.tool()
def houdini_type(text: str, delay: float = 0.02) -> str:
    """Type text into the widget that has keyboard focus (click the field first), one character
    at a time so Plug sees it typed. "\\n" presses Enter. Houdini records its own undo step for
    the edit (not a "Brother:" one), so houdini_undo won't reverse typing - Plug's Ctrl+Z will."""
    return _run("type", {"text": text, "delay": delay})


@mcp.tool()
def houdini_key(key: str) -> str:
    """Press one key or chord in the focused widget: "enter", "escape", "tab", "ctrl+a",
    "backspace", arrows..."""
    return _run("key", {"key": key})


@mcp.tool()
def houdini_create_node(type: str, x: float, y: float, name: str | None = None,
                        input: str | None = None) -> str:
    """Brother's cursor glides to (x, y) over a Network Editor, clicks, and a node of `type`
    (e.g. "null", "attribwrangle", "box") appears right under it, in the network that editor
    shows. Optional name, and `input` = a node to wire into its first input. One "Brother:"
    undo step. Get x, y from houdini_screenshot."""
    return _run("create_node", {"type": type, "x": x, "y": y, "name": name, "input": input})


@mcp.tool()
def houdini_click_node(path: str, double: bool = False) -> str:
    """Brother's cursor glides to a node found BY PATH (no screenshot needed) and clicks it;
    double=True dives inside. Switches/pans a Network Editor if the node isn't on screen.
    Returns which Parameter pane now shows the node and that pane's rect."""
    return _run("click_node", {"path": path, "double": double})


@mcp.tool()
def houdini_pane_screenshot(kind: str = "parm", pane: str | None = None,
                            node: str | None = None) -> list:
    """ONE pane, cropped - far smaller to read than the whole window. kind = parm | network |
    viewer; or pane = a pane tab name; or node = the Parameter pane showing that node.
    Click point = offset + pixel in this image."""
    res = json.loads(_run("pane_screenshot", {"kind": kind, "pane": pane, "node": node}))
    with open(res["file"], "rb") as fh:
        data = fh.read()
    return ["%s %s, offset %s (add it to a pixel here to get the click point)" %
            (res["type"], res["pane"], res["offset"]), Image(data=data, format="png")]


@mcp.tool()
def houdini_capture_pane(pane: str | None = None) -> list:
    """The Network Editor as Houdini actually drew it - works even when another window (e.g.
    Chrome) covers Houdini, and never raises, focuses or moves anything. pane = a pane tab name;
    default = the visible Network Editor. Refuses a hidden tab, a non-network pane, an unknown
    name, a minimised window or a black image. Returns the image plus pan/zoom, size, DPI and
    whether the pane was covered at the time. Use houdini_pane_screenshot to read other panes."""
    res = json.loads(_run("capture_pane", {"pane": pane}))
    with open(res["file"], "rb") as fh:
        data = fh.read()
    vb = res["pan_zoom_visibleBounds"]
    return ["%s %s %dx%d @%ddpi, net %s, view [%.2f %.2f %.2f %.2f], covered=%s, sha256 %s" %
            (res["pane_type"], res["pane"], res["width"], res["height"], res["dpi"], res["network"],
             vb[0], vb[1], vb[2], vb[3], res["occlusion"]["occluded"], res["sha256"][:16]),
            Image(data=data, format="png")]


@mcp.tool()
def houdini_set_parm_shown(path: str, parm: str, value: float | int | str | list | None = None,
                           expression: str | None = None, x: float | None = None,
                           y: float | None = None) -> str:
    """Like houdini_set_parm (exact, one undo step) but visible: the cursor clicks the node so
    its Parameter pane shows it, then points at the field (x, y from houdini_pane_screenshot)
    or at the pane, while the value changes."""
    return _run("set_parm_shown", {"path": path, "parm": parm, "value": value,
                                   "expression": expression, "x": x, "y": y})


@mcp.tool()
def houdini_cursor_hide() -> str:
    """Remove Brother's visible cursor from the Houdini window."""
    return _run("cursor_hide")


@mcp.tool()
def houdini_control_hold(action: str = "start", ttl: float = 8.0) -> str:
    """Keep the "Brother is in control" frame on BETWEEN tool calls. action = start | beat
    (renew) | stop. A hold always ends by itself ttl seconds (max 120) after the last renewal."""
    return _run("control_hold", {"action": action, "ttl": ttl})


@mcp.tool()
def houdini_drag(x0: float, y0: float, x1: float, y1: float, seconds: float = 0.8) -> str:
    """A real press -> move -> release with the cursor drawn along. NOTE: Houdini 21's Network
    Editor ignores synthetic drags (nodes don't move, wires don't connect) - check the result."""
    return _run("drag", {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "seconds": seconds})


# ----------------------------------------------------------------------------- tools: graph actions
# Houdini's Network Editor ignores injected mouse input, so these change the graph through hou
# while Brother's own cursor shows the action. Every result carries method = "api-backed (hou),
# not an input event". move/wire run as a JOB by default: they return at once with a job id,
# Houdini repaints while the node travels, and Plug's mouse/keyboard focus are never touched.
# Esc in Houdini, houdini_action_stop or the time budget cancel a job; a cancelled move puts
# the node back and a cancelled wire connects nothing. A finished one is one "Brother:" undo step.
@mcp.tool()
def houdini_select_node(path: str, add: bool = False) -> str:
    """Brother's cursor glides to the node and selects it (add=True keeps the current selection)."""
    return _run("select_node", {"path": path, "add": add})


@mcp.tool()
def houdini_move_node(path: str, x: float | None = None, y: float | None = None,
                      dx: float | None = None, dy: float | None = None, seconds: float = 0.8,
                      budget: float = 10.0, wait: bool = False) -> str:
    """Move a node to network position (x, y) - lower-left corner, like setPosition - or by
    (dx, dy), visibly. Default returns a job id: poll houdini_action_status. wait=True blocks
    (the node is then only drawn at its final place)."""
    args = {"path": path, "seconds": seconds, "budget": budget, "wait": wait}
    if x is not None or y is not None:
        if x is None or y is None:
            raise ValueError("give both x and y, or dx/dy")
        args.update(x=x, y=y)
    else:
        args.update(dx=dx or 0.0, dy=dy or 0.0)
    return _run("move_node", args)


@mcp.tool()
def houdini_wire_nodes(src: str, dst: str, input: int = 0, seconds: float = 0.7,
                       budget: float = 10.0, wait: bool = False) -> str:
    """Connect src's output to dst's input `input`, the cursor drawing the wire first. Default
    returns a job id: poll houdini_action_status for connected_to."""
    return _run("wire_nodes", {"src": src, "dst": dst, "input": input, "seconds": seconds,
                               "budget": budget, "wait": wait})


@mcp.tool()
def houdini_action_status(job: str) -> str:
    """A move/wire job's state (running | done | cancelled), why it was cancelled, and its result."""
    return _run("action_status", {"job": job})


@mcp.tool()
def houdini_action_stop(job: str | None = None) -> str:
    """Stop one running move/wire job, or every one when job is omitted."""
    return _run("action_stop", {"job": job} if job else {})


@mcp.tool()
def houdini_demo_start(cycles: int | None = None) -> str:
    """Start the local demo loop on the prompt Wrangles in /obj/BROTHER_DEMO_246_A (held frame,
    cursor, per-character typing, animated moves and wires). cycles=None loops until Stop
    (the STOP button, Esc, or houdini_demo_stop). Only when Plug asks for it."""
    return _run("demo_start", {"cycles": cycles})


@mcp.tool()
def houdini_demo_stop() -> str:
    """Stop the demo now; cleanup restores the view/selection and releases the frame."""
    return _run("demo_stop")


@mcp.tool()
def houdini_demo_status() -> str:
    """The demo's state, cycle, counts, stop reason/latency and any error."""
    return _run("demo_status")


_FERN = {"proc": None}
FERN_LOG = os.path.join(os.path.expanduser("~"), ".houdini_brother", "fern_demo.log")


@mcp.tool()
def houdini_fern_demo(speed: float = 2.5, chars_per_second: float = 60.0) -> str:
    """The recorded fern-field demo (rnd/fern_demo): deletes ONLY /obj/brother_fern_field, then
    rebuilds it node by node with the cursor, wires and typed VEX (fern with noise wind, seedling
    scale, For-Each growth stages built last, Crag walking through, Copy to Points), holds the
    purple frame (Esc stops it) and plays from frame 1. Runs in the background (~2-4 min); follow
    it with houdini_fern_demo_status. Only when Plug asks for the fern demo. Lower speed /
    chars_per_second = slower for recording."""
    import subprocess
    p = _FERN["proc"]
    if p and p.poll() is None:
        return "The fern demo is already running (pid %d)." % p.pid
    reg = _current()
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rnd", "fern_demo", "fern_demo.py")
    env = dict(os.environ, HOUDINI_BROTHER_PID=str(reg["pid"]), PYTHONUNBUFFERED="1", MSYS_NO_PATHCONV="1")
    log = open(FERN_LOG, "w", encoding="utf8")
    _FERN["proc"] = subprocess.Popen([sys.executable, script, str(speed), str(chars_per_second)],
                                     cwd=os.path.dirname(script), env=env, stdout=log, stderr=subprocess.STDOUT)
    return "Fern demo started in Houdini pid %s (speed %s, %s chars/s). Esc in Houdini stops it." % (
        reg["pid"], speed, chars_per_second)


@mcp.tool()
def houdini_fern_demo_status() -> str:
    """Whether the fern demo is still running, and the last lines of its log."""
    p = _FERN["proc"]
    state = "not started" if p is None else ("running" if p.poll() is None else "finished (exit %s)" % p.returncode)
    try:
        tail = open(FERN_LOG, encoding="utf8").read().splitlines()[-12:]
    except OSError:
        tail = []
    return state + ("\n" + "\n".join(tail) if tail else "")


@mcp.tool()
def houdini_undo() -> str:
    """Undo Brother's most recent change in the selected session. Refuses if the last undo step
    is not Brother's (its label doesn't start with "Brother:"), so Plug's own work is never undone."""
    return _run("undo")


if __name__ == "__main__":
    mcp.run()
