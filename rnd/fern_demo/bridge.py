"""Talk to an open Houdini that runs brother_link (same wire protocol as mcp/server.py).

The session is HOUDINI_BROTHER_PID when set, otherwise the only live one in
~/.houdini_brother/sessions. Several open and none named -> refuse, listing them."""
import glob, json, os, socket, sys, time

REG = os.path.join(os.path.expanduser("~"), ".houdini_brother", "sessions")


def _alive(pid):
    if sys.platform == "win32":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return code.value == 259
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def pick_pid():
    want = os.environ.get("HOUDINI_BROTHER_PID")
    if want:
        return str(want)
    live = []
    for path in glob.glob(os.path.join(REG, "*.json")):
        try:
            reg = json.load(open(path, encoding="utf8"))
        except (OSError, ValueError):
            continue
        if _alive(reg.get("pid", -1)):
            live.append(str(reg["pid"]))
    if len(live) == 1:
        return live[0]
    if not live:
        sys.exit("No Houdini is connected. In Houdini's Python Shell run brother_link.start() first.")
    sys.exit("Several Houdini sessions are open (%s) - set HOUDINI_BROTHER_PID to the one to use." % ", ".join(live))


PID = pick_pid()


def call(pid, op, args=None, timeout=10.0):
    reg = json.load(open(os.path.join(REG, "%s.json" % pid), encoding="utf8"))
    t0 = time.time()
    with socket.create_connection(("127.0.0.1", reg["port"]), timeout=timeout) as s:
        s.sendall((json.dumps({"token": reg["token"], "op": op, "args": args or {}}) + "\n").encode())
        buf = b""
        while not buf.endswith(b"\n"):
            c = s.recv(1 << 20)
            if not c:
                break
            buf += c
    return json.loads(buf), round(time.time() - t0, 3)
