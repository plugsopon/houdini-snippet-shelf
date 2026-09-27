"""houdini-live MCP server: lets Claude inspect (and, when asked, change) Plug's OPEN Houdini sessions.

Each Houdini that should be visible runs brother_link.start() (see mcp/README.md). This server
finds them through %USERPROFILE%\\.houdini_brother\\sessions\\*.json and talks to the one
selected with houdini_use_session. With only one session open it is used automatically.
"""
import glob, json, os, socket, sys, time

from mcp.server.fastmcp import FastMCP, Image

REG_DIR = os.path.join(os.path.expanduser("~"), ".houdini_brother", "sessions")
TIMEOUT = 120.0            # a heavy cook can take a while; the request runs on Houdini's main thread

mcp = FastMCP("houdini-live")
_selected = {"pid": None}


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
                           "  import sys; sys.path.insert(0, r\"P:\\Project\\Houdini Snippet Shelf\\mcp\\houdini\")\n"
                           "  import brother_link; brother_link.start()")
    if _selected["pid"] is not None:
        for reg, _ in ss:
            if reg["pid"] == _selected["pid"]:
                return reg
        gone, _selected["pid"] = _selected["pid"], None
        raise RuntimeError("The selected session (pid %s) is gone. Call houdini_sessions and pick again." % gone)
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
                     "selected": reg["pid"] == _selected["pid"]})
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
def houdini_cursor_hide() -> str:
    """Remove Brother's visible cursor from the Houdini window."""
    return _run("cursor_hide")


@mcp.tool()
def houdini_undo() -> str:
    """Undo Brother's most recent change in the selected session. Refuses if the last undo step
    is not Brother's (its label doesn't start with "Brother:"), so Plug's own work is never undone."""
    return _run("undo")


if __name__ == "__main__":
    mcp.run()
