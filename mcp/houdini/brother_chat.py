"""brother_chat - Claude Code inside Houdini (AI > Chat...).

A dark overlay panel over Houdini's main window that drives the locally installed `claude` CLI
the same way Dremzo Desktop does: the real claude.exe, run headless with
`--input-format stream-json --output-format stream-json`, authenticated by the machine's own
Claude login (CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`) - no API key, no direct API
calls. Everything Claude Code does comes with it: tools, skills, slash commands, CLAUDE.md,
hooks, MCP, subagents, sessions on disk.

Protocol, measured against claude 2.1.226 (not from docs):
  in   {"type":"user","message":{"role":"user","content":[{"type":"text","text":...}, image...]}}
       {"type":"control_request","request_id":ID,"request":{"subtype":"initialize"|"interrupt"|
        "set_permission_mode","mode":M|"set_model","model":M}}
       {"type":"control_response","response":{"subtype":"success","request_id":ID,
        "response":{"behavior":"allow","updatedInput":{...}} | {"behavior":"deny","message":...}}}
  out  system/init, stream_event (content_block_start/delta/stop...), assistant, user (tool
       results), control_request can_use_tool (because of --permission-prompt-tool stdio),
       control_response (initialize answers with the slash-command list), result (cost/usage).
One process stays alive across turns; a session switch starts a new one with --resume.

The houdini-live MCP server (this repo's .mcp.json) is passed with --mcp-config, so the model
can inspect and drive THIS Houdini through brother_link - with the cursor and the screen edges.
"""
import base64, datetime, glob, json, os, re, shutil, sys, time, uuid

import hou
from PySide6 import QtCore, QtGui, QtWidgets

REPO = r"P:\Project\Houdini Snippet Shelf"
MCP_CONFIG = os.path.join(REPO, ".mcp.json")
MODELS = (("Default", None), ("Opus", "opus"), ("Sonnet", "sonnet"), ("Haiku", "haiku"))
MODES = (("Manual", "default"), ("Accept edits", "acceptEdits"), ("Plan", "plan"),
         ("Bypass permissions", "bypassPermissions"))
# the mode picker, same order, words and shortcuts as the Claude app
MODE_ROWS = (("auto", "Auto", "Claude handles permission decisions", "Recommended"),
             ("default", "Manual", "Always ask before making changes", None),
             ("acceptEdits", "Accept edits", "Automatically accept all file edits", None),
             ("plan", "Plan", "Create a plan before making changes", None),
             ("bypassPermissions", "Bypass permissions", "Accepts all permissions", None))
MODEL_ORDER = ("opus", "fable", "sonnet", "haiku")
LOOK_TOOLS = ("sessions", "use_session", "scene", "network", "node", "problems", "geometry",
              "attrib", "compare", "viewport", "screenshot", "pane_screenshot")
_open = {"w": None}


# ============================================================================ CLI plumbing
def _desktop_cli():
    """The CLI the Claude desktop app keeps up to date itself (%APPDATA%/Claude/claude-code/<ver>/).
    It is usually newer than the npm install - Opus 5.5 needs >= 2.1.280 - and it is what the Claude
    app itself runs, so its model list matches the app's."""
    # the app is an MSIX package: its %APPDATA% is virtualised under LOCALAPPDATA/Packages, and
    # only processes inside the package see the plain path - Houdini sees the real one
    roots = [os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code")]
    roots += glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "Claude_*",
                                    "LocalCache", "Roaming", "Claude", "claude-code"))
    best = None
    for d in [d for r in roots for d in glob.glob(os.path.join(r, "*"))]:
        try:
            ver = tuple(int(x) for x in os.path.basename(d).split("."))
        except ValueError:
            continue
        # <ver>/claude.exe until 2.1.28x, then <ver>/<build hash>/claude.exe - check both, or the
        # lookup finds nothing and quietly falls back to the npm CLI (too old for Opus 5.5)
        for exe in [os.path.join(d, "claude.exe")] + glob.glob(os.path.join(d, "*", "claude.exe")):
            if os.path.exists(exe):
                key = (ver, os.path.getmtime(exe))
                if best is None or key > best[0]:
                    best = (key, exe)
    return best[1] if best else None


def claude_exe():
    """The newest real claude.exe: the desktop app's copy, else the one behind the npm shim
    (list args, no shell - a prompt passes verbatim)."""
    exe = _desktop_cli()
    if exe:
        return exe
    which = shutil.which("claude")
    if which:
        exe = os.path.join(os.path.dirname(which), "node_modules", "@anthropic-ai", "claude-code",
                           "bin", "claude.exe")
        if os.path.exists(exe):
            return exe
    npm = os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "@anthropic-ai",
                       "claude-code", "bin", "claude.exe")
    if os.path.exists(npm):
        return npm
    return which


def claude_env():
    """Houdini's environment minus Claude-Code child markers (a child that inherits CLAUDECODE /
    CLAUDE_CODE_SESSION_ID etc. thinks it is a nested SDK child and fails with "Not logged in")
    - but KEEP the login, CLAUDE_CODE_OAUTH_TOKEN. setx writes the user registry, which a
    Houdini started earlier doesn't see, so read it from there when missing. Same as Desktop."""
    env = QtCore.QProcessEnvironment()
    for k, v in os.environ.items():
        if k == "CLAUDE_CODE_OAUTH_TOKEN" or (k != "CLAUDECODE" and not k.startswith("CLAUDE_")):
            env.insert(k, v)
    # Houdini points PYTHONHOME at its own Python 3.11. Inherited by the MCP server (a system
    # Python 3.13) it can't even find its stdlib and houdini-live shows "failed". Drop Houdini's
    # Python and its bin dirs from what the CLI and its children see.
    for k in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP"):
        env.remove(k)
    hfs = os.path.normcase(os.environ.get("HFS", "")).replace("/", "\\")
    keep = [d for d in env.value("PATH").split(os.pathsep)
            if d and not ("side effects software" in d.lower() or "sideef~1" in d.lower()
                          or (hfs and os.path.normcase(d).replace("/", "\\").startswith(hfs)))]
    env.insert("PATH", os.pathsep.join(keep))
    if not env.contains("CLAUDE_CODE_OAUTH_TOKEN"):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                env.insert("CLAUDE_CODE_OAUTH_TOKEN", winreg.QueryValueEx(k, "CLAUDE_CODE_OAUTH_TOKEN")[0])
        except OSError:
            pass
    return env


def project_dir(cwd):
    """Where claude keeps this cwd's transcripts: every non-alphanumeric char becomes '-'."""
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", re.sub(r"[^A-Za-z0-9]", "-", cwd))


def _text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
    return "\n".join(out)


def list_sessions(cwd, limit=60):
    """Past sessions for this cwd, newest first: (session_id, title, mtime)."""
    rows = []
    for path in glob.glob(os.path.join(project_dir(cwd), "*.jsonl")):
        sid = os.path.splitext(os.path.basename(path))[0]
        title = None
        try:
            with open(path, encoding="utf8", errors="replace") as fh:
                for n, line in enumerate(fh):
                    if n > 400:
                        break
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    if o.get("type") in ("custom-title", "summary") and (o.get("customTitle") or o.get("summary")):
                        title = o.get("customTitle") or o.get("summary")
                        break
                    if title is None and o.get("type") == "user" and not o.get("isMeta"):
                        t = _text_of((o.get("message") or {}).get("content")).strip()
                        if t and not t.startswith("<") and not t.startswith("Caveat:"):
                            title = t
        except OSError:
            continue
        if title is None:            # no user turn (a stub a closing process left behind): not a session
            continue
        rows.append((sid, title.splitlines()[0][:80], os.path.getmtime(path)))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows[:limit]


STATE_FILE = os.path.join(os.path.expanduser("~"), ".houdini_brother", "chat_state.json")
TRASH_DIR = os.path.join(os.path.expanduser("~"), ".houdini_brother", "trash")


def load_state():
    """Pinned / archived chats - this machine only, like Dremzo Code's sidebar state."""
    try:
        with open(STATE_FILE, encoding="utf8") as fh:
            st = json.load(fh)
        if isinstance(st, dict):
            return {"pinned": list(st.get("pinned") or []), "archived": list(st.get("archived") or [])}
    except (OSError, ValueError):
        pass
    return {"pinned": [], "archived": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf8") as fh:
        json.dump(st, fh, indent=1)


_SEARCH_CACHE = {}          # path -> (mtime, lowercased text)


def session_text(cwd, sid):
    """A chat's transcript, lowercased, for search across chats (cached by mtime)."""
    path = os.path.join(project_dir(cwd), sid + ".jsonl")
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return ""
    hit = _SEARCH_CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with open(path, encoding="utf8", errors="replace") as fh:
            txt = fh.read(6 * 1024 * 1024)
    except OSError:
        txt = ""
    try:                      # the jsonl escapes non-ASCII; undo that so Thai matches too
        txt = txt.encode("ascii", "backslashreplace").decode("unicode_escape", "replace")
    except Exception:
        pass
    txt = txt.lower()
    _SEARCH_CACHE[path] = (mt, txt)
    return txt


def load_transcript(cwd, sid):
    """A resumed session's earlier turns, as events the panel can replay."""
    path = os.path.join(project_dir(cwd), sid + ".jsonl")
    events = []
    try:
        with open(path, encoding="utf8", errors="replace") as fh:
            for line in fh:
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("isMeta") or o.get("isSidechain"):
                    continue
                msg = o.get("message") or {}
                if o.get("type") == "user":
                    c = msg.get("content")
                    if isinstance(c, str):
                        if not c.startswith("<"):
                            events.append(("user", {"text": c, "uuid": o.get("uuid")}))
                    else:
                        for b in c or []:
                            if b.get("type") == "text" and not b.get("text", "").startswith("<"):
                                events.append(("user", {"text": b["text"], "uuid": o.get("uuid")}))
                            elif b.get("type") == "tool_result":
                                events.append(("tool_result", b))
                elif o.get("type") == "assistant":
                    for b in msg.get("content") or []:
                        if b.get("type") == "text":
                            events.append(("text", b.get("text", "")))
                        elif b.get("type") == "tool_use":
                            events.append(("tool_use", b))
    except OSError:
        pass
    return events


def houdini_context():
    """What the model should know about the Houdini it lives in."""
    bl = sys.modules.get("brother_link")
    port = bl._state.get("port") if bl and bl._state.get("server") is not None else None
    return (
        "You are Brother, running INSIDE Plug's live SideFX Houdini %s session (pid %d, hip %s), "
        "opened from Houdini's AI > Chat panel. Plug is a senior FX TD. The houdini-live MCP tools "
        "(mcp__houdini-live__houdini_*) are already bound to THIS session%s - no need to pick one "
        "with houdini_use_session. Inspect it with them, and change it only when asked - one "
        "'Brother:' undo group per change, never save the hip file. "
        "Prefer houdini_click_node / houdini_set_parm_shown so Plug sees the cursor work. Reply in "
        "the language Plug writes in (Thai -> Thai, refer to yourself as Brother)."
        % (hou.applicationVersionString(), os.getpid(), hou.hipFile.path(),
           (" via brother_link on port %d" % port) if port else " (the link is starting)"))


class ClaudeSession(QtCore.QObject):
    """One live `claude -p` process in stream-json mode."""
    event = QtCore.Signal(dict)
    ended = QtCore.Signal(int, str)

    def __init__(self, cwd, resume=None, model=None, mode="default", parent=None, session_id=None,
                 effort=None, fork=False):
        super().__init__(parent)
        self.cwd, self.resume, self.model, self.mode = cwd, resume, model, mode
        self.effort, self.fork = effort, fork
        self.init = {}                    # the initialize answer: commands, models, ...
        self.session_id = resume or session_id or str(uuid.uuid4())
        self.proc = None
        self.buf = b""
        self.commands = []
        self.busy = False
        self.parked = False               # closed on purpose: its exit is not news
        self._err = b""

    def start(self):
        exe = claude_exe()
        if not exe:
            raise RuntimeError("claude CLI not found - install Claude Code (npm i -g @anthropic-ai/claude-code)")
        args = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--include-partial-messages", "--permission-prompt-tool", "stdio",
                # echo each user message back with its uuid: the rewind point for that message
                "--replay-user-messages",
                # makes Bypass selectable from the mode menu later; it does NOT turn it on
                "--allow-dangerously-skip-permissions",
                "--permission-mode", self.mode, "--append-system-prompt", houdini_context()]
        if self.resume and self.fork:
            args += ["--resume", self.resume, "--fork-session"]
        else:
            args += ["--resume", self.resume] if self.resume else ["--session-id", self.session_id]
        if self.model:
            args += ["--model", self.model]
        if self.effort:
            args += ["--effort", self.effort]
        if os.path.exists(MCP_CONFIG):
            args += ["--mcp-config", MCP_CONFIG,
                     # looking at the scene never needs a click; changing it still asks
                     "--allowedTools", ",".join("mcp__houdini-live__houdini_" + t for t in LOOK_TOOLS)]
        hip_dir = os.path.dirname(hou.hipFile.path())
        if os.path.isdir(hip_dir):
            args += ["--add-dir", hip_dir]
        p = QtCore.QProcess(self)
        p.setProgram(exe)
        p.setArguments(args)
        p.setWorkingDirectory(self.cwd)
        env = claude_env()
        env.insert("CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING", "true")   # what makes rewind possible
        env.insert("HOUDINI_BROTHER_PID", str(os.getpid()))   # the MCP tools talk to THIS Houdini, always
        # the Artifact / ArtifactComments / ArtifactData tools are only offered to the desktop app's
        # entrypoint; without this the chat can't publish the Snippet Shelf page (v006/v007 sat
        # unpublished for that reason). claude_env() strips CLAUDE_*, so set it here.
        env.insert("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")
        p.setProcessEnvironment(env)
        p.readyReadStandardOutput.connect(self._read)
        p.readyReadStandardError.connect(self._read_err)
        p.finished.connect(self._finished)
        p.errorOccurred.connect(self._error)
        self.proc = p
        p.start()
        self.control("initialize", hooks=None)           # answers with the slash-command list

    def _read_err(self):
        try:
            self._err = (self._err + bytes(self.proc.readAllStandardError()))[-4000:]
        except RuntimeError:
            pass

    def _finished(self, code, _status=None):
        # a bound method, not a lambda: Qt drops it with the object, so a process that exits after
        # its session was deleted can no longer call into a dead C++ object
        self.busy = False
        try:
            self.ended.emit(code, "" if self.parked else self._err.decode("utf8", "replace"))
        except RuntimeError:
            pass

    def _error(self, err):
        # FailedToStart never emits finished - without this the turn stays "busy" forever
        if err == QtCore.QProcess.FailedToStart:
            self.busy = False
            try:
                self.ended.emit(-1, "could not start claude (%s)" % self.proc.program())
            except RuntimeError:
                pass

    def running(self):
        try:
            return self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning
        except RuntimeError:
            return False

    def _write(self, obj):
        if self.running():
            self.proc.write((json.dumps(obj) + "\n").encode("utf8"))
            return True
        return False

    def control(self, subtype, **kw):
        rid = "hou-%s" % uuid.uuid4().hex[:10]
        req = {"subtype": subtype}
        req.update(kw)
        self._write({"type": "control_request", "request_id": rid, "request": req})
        return rid

    def send(self, text, images=()):
        content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}
                   for mt, data in images]
        content.append({"type": "text", "text": text})
        if not self._write({"type": "user", "message": {"role": "user", "content": content}}):
            self.ended.emit(-1, "claude is not running - the message was not sent")
            return False
        self.busy = True
        return True

    def answer_permission(self, request_id, allow, tool_input=None, message="", permissions=None):
        if allow:
            resp = {"behavior": "allow", "updatedInput": tool_input or {}}
            if permissions:
                resp["updatedPermissions"] = permissions
        else:
            resp = {"behavior": "deny", "message": message or "Plug denied this in the Houdini chat panel."}
        return self._write({"type": "control_response", "response": {"subtype": "success",
                                                                     "request_id": request_id, "response": resp}})

    def refuse(self, request_id, why):
        """Any control request we can't serve gets an answer, so the turn doesn't wait forever."""
        self._write({"type": "control_response", "response": {"subtype": "error", "request_id": request_id,
                                                              "error": why}})

    def _read(self):
        try:
            self.buf += bytes(self.proc.readAllStandardOutput())
        except RuntimeError:
            return
        *lines, self.buf = self.buf.split(b"\n")
        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                o = json.loads(raw.decode("utf8", "replace"))
            except ValueError:
                continue
            if o.get("type") == "system" and o.get("subtype") == "init":
                self.session_id = o.get("session_id") or self.session_id
            if o.get("type") == "control_response":
                r = (o.get("response") or {}).get("response") or {}
                if r.get("commands"):
                    self.commands = r["commands"]
                if r.get("models"):
                    self.init = r
            if o.get("type") == "result":
                self.busy = False
            self.event.emit(o)

    def stop(self):
        """Close stdin and let claude exit on its own. Never waits on the UI thread (a blocking
        wait froze all of Houdini on every session switch); a straggler is killed later."""
        if not self.running():
            return
        self.parked = True
        try:
            self.proc.closeWriteChannel()
        except RuntimeError:
            return
        proc = self.proc

        def _kill():
            try:
                if proc.state() != QtCore.QProcess.NotRunning:
                    proc.kill()
            except RuntimeError:
                pass
        QtCore.QTimer.singleShot(4000, _kill)


# =========================================================================== widgets
CSS = """
* { font-family: "Leelawadee UI"; }
#panel { background: #262624; border: 1px solid #3a3935; border-radius: 12px; }
#side { background: #1f1e1d; border-right: 1px solid #2f2e2b;
        border-top-left-radius: 11px; border-bottom-left-radius: 11px; }
#titlebar { border-bottom: 1px solid #2f2e2b; }
QLabel { color: #ece9e3; font-size: 13px; }
QLabel#brand { color: #ece9e3; font-size: 15px; font-weight: 600; }
QLabel#brandmark { color: #ff4f9a; font-size: 15px; font-weight: 700; }
QLabel#title { color: #ece9e3; font-size: 13px; font-weight: 600; }
QLabel#section { color: #77756f; font-size: 12px; }
QLabel#dim { color: #77756f; font-size: 12px; }
QLabel#chip { background: #30302e; color: #a6a39d; border-radius: 6px; padding: 1px 8px; font-size: 12px; }
QLabel#kbd { color: #77756f; border: 1px solid #3a3935; border-radius: 5px; padding: 0 5px; font-size: 11px; }
QPushButton { background: #30302e; color: #ece9e3; border: 1px solid #3a3935; border-radius: 8px;
              padding: 5px 10px; font-size: 13px; }
QPushButton:hover { background: #353532; border-color: #4a4944; }
QPushButton#primary { background: #ece9e3; color: #1c1b1a; border-color: #ece9e3; font-weight: 600; }
QPushButton#stop { background: #3a1e1c; color: #e5675f; border-color: #6a2b26; font-weight: 600; }
QPushButton#flat { background: transparent; border: none; color: #a6a39d; padding: 3px 6px; }
QPushButton#flat:hover { color: #ece9e3; background: #353532; }
QPushButton#nav { background: transparent; border: none; color: #ece9e3; text-align: left;
                  padding: 6px 10px; border-radius: 8px; font-size: 13px; }
QPushButton#nav:hover { background: #353532; }
QPushButton#icon { background: transparent; border: none; color: #a6a39d; border-radius: 7px;
                   padding: 0; font-size: 14px; min-width: 28px; min-height: 28px; }
QPushButton#icon:hover { background: #353532; color: #ece9e3; }
QComboBox { background: #30302e; color: #ece9e3; border: 1px solid #3a3935; border-radius: 8px;
            padding: 3px 8px; font-size: 13px; }
QComboBox QAbstractItemView { background: #2a2927; color: #ece9e3; selection-background-color: #353532; }
QListWidget { background: transparent; border: none; color: #ece9e3; font-size: 13px; outline: 0; }
QListWidget::item { border-radius: 8px; margin: 1px 0; }
QListWidget::item:selected { background: #30302e; }
QListWidget::item:hover { background: #353532; }
QPlainTextEdit#composer { background: transparent; color: #ece9e3; border: none; padding: 2px; font-size: 14px; }
QFrame#composerBox { background: #30302e; border: 1px solid #3a3935; border-radius: 16px; }
QFrame#ctxStrip { background: #1f1e1d; border: 1px solid #2f2e2b; border-bottom: none;
                  border-top-left-radius: 12px; border-top-right-radius: 12px; }
QPushButton#bar { background: transparent; border: none; color: #a6a39d; padding: 4px 8px; border-radius: 7px; font-size: 13px; }
QPushButton#bar:hover { background: #353532; color: #ece9e3; }
QPushButton#round { background: #30302e; color: #ece9e3; border: none; border-radius: 15px; font-size: 14px; }
QPushButton#round:hover { background: #353532; }
QPushButton#send { background: #ece9e3; color: #1c1b1a; border: none; border-radius: 15px; font-size: 15px; font-weight: 700; }
QPushButton#send:disabled { background: #3a3935; color: #77756f; }
QPushButton#stopr { background: #30302e; color: #ece9e3; border: 1px solid #3a3935; border-radius: 15px; font-size: 11px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #3d3c38; border-radius: 4px; min-height: 30px; margin: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QTextBrowser { background: transparent; border: none; color: #ece9e3; font-size: 14px; }
QFrame#user { background: #30302e; border-radius: 14px; }
QFrame#card { background: transparent; border: none; }
QFrame#card QLabel { color: #a6a39d; }
QFrame#perm { background: #1f1e1d; border: 1px solid #3a3935; border-radius: 12px; }
QFrame#think { background: transparent; border: none; }
"""
MONO = "Consolas, 'Cascadia Mono', monospace"


class AutoText(QtWidgets.QTextBrowser):
    """A text block that grows to fit (markdown), with no scrollbar of its own."""
    def __init__(self, markdown="", color=None, mono=False, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)                    # we route links: copy:N copies a code block
        self.anchorClicked.connect(self._link)
        self._codes = []
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.document().setDocumentMargin(2)
        if color:
            self.setStyleSheet("color:%s;" % color)
        if mono:
            f = QtGui.QFont("Consolas"); f.setPointSize(9); self.setFont(f)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self._md = ""
        self.mono = mono
        self.set_text(markdown)

    def set_text(self, text):
        self._md = text
        if self.mono:
            self.setPlainText(text)
        else:
            self.setHtml(self._with_code_blocks(text))
        self._fit()

    # Qt's markdown renders a fenced block as an ordinary paragraph, so code read like prose.
    # Fenced blocks become real code blocks: dark box, monospace, language label, Copy.
    _FENCE = re.compile(r"```([^\n`]*)\n(.*?)(?:\n?```|\Z)", re.S)

    def _with_code_blocks(self, text):
        self._codes = []
        out, pos = [], 0
        for m in self._FENCE.finditer(text):
            out.append(_md_html(text[pos:m.start()]))
            lang, code = m.group(1).strip(), m.group(2)
            self._codes.append(code)
            out.append(
                "<table width='100%%' cellspacing='0' cellpadding='0' bgcolor='#1c1b1a' "
                "style='margin-top:6px;margin-bottom:10px;border:1px solid #2f2e2b;'>"
                "<tr><td bgcolor='#1c1b1a' style='padding:5px 12px;border-bottom:1px solid #2f2e2b;'>"
                "<table width='100%%' cellspacing='0' cellpadding='0'><tr>"
                "<td><span style='color:#77756f;font-size:11px;'>%s</span></td>"
                "<td align='right'><a href='copy:%d' style='color:#6aa5ff;font-size:11px;"
                "text-decoration:none;'>Copy</a></td></tr></table>"
                "</td></tr><tr><td style='padding:8px 10px;'>"
                "<pre style='font-family:Consolas,\"Cascadia Mono\",monospace;font-size:12px;color:#ece9e3;"
                "margin:0;'>%s</pre></td></tr></table>" % (_esc(lang or "code"), len(self._codes) - 1, _esc(code)))
            pos = m.end()
        out.append(_md_html(text[pos:]))
        return "".join(out)

    def _link(self, url):
        u = url.toString()
        if u.startswith("copy:"):
            try:
                QtWidgets.QApplication.clipboard().setText(self._codes[int(u[5:])])
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Copied")
            except (ValueError, IndexError):
                pass
        else:
            QtGui.QDesktopServices.openUrl(url)

    def append_text(self, delta):
        self.set_text(self._md + delta)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.document().setTextWidth(self.viewport().width())
        self._fit()

    def _fit(self, *_):
        self.setFixedHeight(int(self.document().size().height()) + 6)


def _md_html(md):
    """Markdown -> the <body> part of Qt's own HTML for it."""
    if not md.strip():
        return ""
    d = QtGui.QTextDocument(); d.setMarkdown(md)
    # inline `code`: Qt asks for a generic 'monospace' that Windows maps to a proportional font
    # inline `code`: Qt uses the app's "fixed" font, which Houdini sets to a proportional face
    # (Segoe UI) - swap it for a real monospace with a faint background, like Claude's
    fixed = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont).family()
    h = d.toHtml()
    for fam in {fixed, "monospace", "Courier New"}:
        h = h.replace("font-family:'%s';" % fam,
                      "font-family:'Consolas'; background-color:#30302e; color:#f0c6d4;")
    i, j = h.find("<body"), h.rfind("</body>")
    return h[h.find(">", i) + 1:j] if i >= 0 and j > i else h


def _short(v, n=90):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + "..."


TOOL_KEY = {"Read": "file_path", "Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
            "Bash": "command", "PowerShell": "command", "Glob": "pattern", "Grep": "pattern", "WebFetch": "url",
            "WebSearch": "query", "Agent": "description", "Task": "description", "Skill": "skill"}


class ToolCard(QtWidgets.QFrame):
    """One tool call: a one-line summary that expands to the full input and the result."""
    def __init__(self, name, tool_id, depth=0, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.name, self.tool_id, self.partial = name, tool_id, ""
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(4)
        head = QtWidgets.QHBoxLayout(); lay.addLayout(head)
        self.dot = QtWidgets.QLabel("●"); self.dot.setStyleSheet("color:#d9a548;font-size:9px;")
        head.addWidget(self.dot)
        label = name.replace("mcp__houdini-live__", "houdini:").replace("mcp__", "")
        self.title = QtWidgets.QLabel(label); self.title.setStyleSheet("color:#a6a39d;font-size:13px;")
        head.addWidget(self.title)
        self.summary = QtWidgets.QLabel(""); self.summary.setObjectName("dim")
        self.summary.setStyleSheet("color:#77756f;font-family:Consolas;font-size:12px;")
        head.addWidget(self.summary, 1)
        self.toggle = QtWidgets.QPushButton("›", objectName="flat"); head.addWidget(self.toggle)
        self.toggle.setToolTip("Show the input and the result")
        self.body = QtWidgets.QWidget(); self.body.hide()
        bl = QtWidgets.QVBoxLayout(self.body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(4)
        self.input_view = AutoText(mono=True, color="#a6a39d"); bl.addWidget(self.input_view)
        self.result_view = AutoText(mono=True, color="#5fb87a"); self.result_view.hide(); bl.addWidget(self.result_view)
        lay.addWidget(self.body)
        self.extra = QtWidgets.QWidget()                      # diffs / todos show here, always open
        self.extra_lay = QtWidgets.QVBoxLayout(self.extra); self.extra_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.extra); self.extra.hide()
        self.toggle.clicked.connect(self._flip)
        if depth:
            self.setStyleSheet("QFrame#card{margin-left:%dpx;}" % (18 * depth))

    def _flip(self):
        on = not self.body.isVisible()
        self.body.setVisible(on)
        self.toggle.setText("⌄" if on else "›")

    def mousePressEvent(self, e):            # click anywhere on the line, like Dremzo Code's .step
        if e.position().y() < 26:
            self._flip()
        super().mousePressEvent(e)

    def add_partial(self, s):
        self.partial += s
        self.summary.setText(_short(self.partial, 70))

    def set_input(self, inp):
        key = TOOL_KEY.get(self.name)
        if key and isinstance(inp, dict) and key in inp:
            self.summary.setText(_short(inp[key]))
        elif isinstance(inp, dict) and inp:
            self.summary.setText(_short(inp))
        self.input_view.set_text(json.dumps(inp, indent=1, ensure_ascii=False))
        if self.name in ("Edit", "MultiEdit") and isinstance(inp, dict):
            edits = inp.get("edits") or [inp]
            html = []
            for e in edits:
                for line in str(e.get("old_string", "")).splitlines()[:30]:
                    html.append("<div style='background:#3a1418;color:#ffb0b8'>- %s</div>" % _esc(line))
                for line in str(e.get("new_string", "")).splitlines()[:30]:
                    html.append("<div style='background:#12301c;color:#a8f0b8'>+ %s</div>" % _esc(line))
            self._extra_html("<div style='font-family:%s;font-size:11px'>%s</div>" % (MONO, "".join(html)))
        if self.name == "TodoWrite" and isinstance(inp, dict):
            marks = {"completed": "☑", "in_progress": "◐", "pending": "☐"}
            rows = ["<div>%s %s</div>" % (marks.get(t.get("status"), "☐"),
                                          ("<s>%s</s>" if t.get("status") == "completed" else "%s") % _esc(t.get("content", "")))
                    for t in inp.get("todos", [])]
            self._extra_html("".join(rows))

    def _add_image(self, data):
        """A screenshot or a Read image: a thumbnail, click for full width."""
        img = QtGui.QImage.fromData(base64.b64decode(data))
        if img.isNull():
            return
        lab = QtWidgets.QLabel(); lab.setCursor(QtCore.Qt.PointingHandCursor)
        lab.setToolTip("Click to enlarge / shrink")
        state = {"big": False}

        def show():
            w = max(200, self.width() - 30) if state["big"] else 320
            lab.setPixmap(QtGui.QPixmap.fromImage(img).scaledToWidth(min(w, img.width()), QtCore.Qt.SmoothTransformation))

        def toggle(_e):
            state["big"] = not state["big"]; show()
        lab.mousePressEvent = toggle
        show()
        self.extra_lay.addWidget(lab); self.extra.show()

    def _extra_html(self, html):
        t = QtWidgets.QTextBrowser(); t.setHtml(html)
        t.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        t.document().documentLayout().documentSizeChanged.connect(
            lambda s, t=t: t.setFixedHeight(min(320, int(s.height()) + 6)))
        self.extra_lay.addWidget(t); self.extra.show()

    def set_result(self, content, is_error):
        text = _text_of(content) if not isinstance(content, str) else content
        for b in content if isinstance(content, list) else []:
            src = b.get("source") if isinstance(b, dict) and b.get("type") == "image" else None
            if src and src.get("type") == "base64":
                self._add_image(src.get("data", ""))
        self.result_view.set_text(text[:6000] + ("\n..." if len(text) > 6000 else ""))
        self.result_view.setStyleSheet("color:%s;" % ("#e5675f" if is_error else "#5fb87a"))
        self.result_view.show()
        self.dot.setStyleSheet("color:%s;" % ("#e5675f" if is_error else "#5fb87a"))


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class EditedCard(QtWidgets.QFrame):
    """'Edited N files  +A -D' after a turn, one row per file; a row opens its diff, Open opens the file."""
    def __init__(self, edited, parent=None):
        super().__init__(parent)
        self.setObjectName("edited")
        self.setStyleSheet("QFrame#edited{border:1px solid #3a3935;border-radius:12px;background:transparent;}")
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        ta = sum(r["add"] for r in edited.values()); td = sum(r["del"] for r in edited.values())
        head = QtWidgets.QLabel("Edited %d file%s &nbsp;<span style='color:#5fb87a'>+%d</span> "
                                "<span style='color:#e5675f'>-%d</span>" % (len(edited), "s" if len(edited) > 1 else "", ta, td))
        head.setStyleSheet("padding:8px 12px;font-size:13px;color:#ece9e3;"); lay.addWidget(head)
        for path, r in sorted(edited.items()):
            row = QtWidgets.QFrame(); row.setStyleSheet("QFrame{border-top:1px solid #2f2e2b;}")
            rl = QtWidgets.QVBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(0)
            top = QtWidgets.QHBoxLayout(); top.setContentsMargins(12, 5, 8, 5); rl.addLayout(top)
            b = QtWidgets.QPushButton("%s   %s" % (os.path.basename(path), os.path.dirname(path)), objectName="flat")
            b.setStyleSheet("text-align:left;color:#ece9e3;border:none;")
            b.setToolTip("Show the changes")
            top.addWidget(b, 1)
            n = QtWidgets.QLabel("<span style='color:#5fb87a'>+%d</span> <span style='color:#e5675f'>-%d</span>"
                                 % (r["add"], r["del"])); n.setStyleSheet("border:none;"); top.addWidget(n)
            o = QtWidgets.QPushButton("Open", objectName="flat"); o.setStyleSheet("border:none;")
            o.clicked.connect(lambda _=False, p=path: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(p)))
            top.addWidget(o)
            diff = AutoText(""); diff.setHtml("<div style='font-family:Consolas;font-size:11px'>%s</div>"
                                              % (r["html"] or "<i>new file</i>")); diff.hide()
            diff.setStyleSheet("border:none;background:#1c1b1a;")
            rl.addWidget(diff)
            b.clicked.connect(lambda _=False, d=diff: d.setVisible(not d.isVisible()))
            lay.addWidget(row)


class _Card(QtWidgets.QFrame):
    """A question from Claude that waits for Plug. Expires when the turn ends without an answer."""
    def __init__(self, req, answer, parent=None):
        super().__init__(parent)
        self.setObjectName("perm")
        self.req, self.r, self.answer = req, req["request"], answer
        self.rid = req["request_id"]
        self.live = True
        self.lay = QtWidgets.QVBoxLayout(self); self.lay.setContentsMargins(12, 10, 12, 10); self.lay.setSpacing(6)
        self.buttons = []

    def button(self, row, text, fn, primary=False):
        b = QtWidgets.QPushButton(text, objectName="primary" if primary else "")
        b.clicked.connect(fn)
        row.addWidget(b); self.buttons.append(b)
        return b

    def done(self, text):
        self.live = False
        for w in self.buttons:
            w.setEnabled(False)
        note = QtWidgets.QLabel(text); note.setObjectName("dim"); self.lay.addWidget(note)

    def send(self, allow, text, **kw):
        if not self.live:
            return
        ok = self.answer(self.rid, allow, **kw)
        self.done(text if ok else "Not delivered - claude has stopped")

    def expire(self, why="Expired - the turn ended before an answer"):
        if self.live:
            self.done(why)
            self.setStyleSheet("QFrame#perm{border-color:#3a3935;background:#1f1e1d;}")


SUGG_WHERE = {"session": "this session", "localSettings": "this project, saved to .claude/settings.local.json",
              "projectSettings": "this project, saved to .claude/settings.json", "userSettings": "all projects"}


class PermissionCard(_Card):
    def __init__(self, req, answer, parent=None):
        super().__init__(req, answer, parent)
        r = self.r
        name = r.get("display_name") or r.get("tool_name")
        who = " (subagent)" if r.get("agent_id") else ""
        self.lay.addWidget(QtWidgets.QLabel("<b>Brother wants to use %s%s</b>" % (_esc(name), who)))
        desc = r.get("description") or _short(r.get("input"), 300)
        d = QtWidgets.QLabel(_esc(desc)); d.setWordWrap(True); d.setObjectName("dim"); self.lay.addWidget(d)
        if r.get("decision_reason"):
            why = QtWidgets.QLabel(_esc(r["decision_reason"])); why.setWordWrap(True); why.setObjectName("dim")
            self.lay.addWidget(why)
        row = QtWidgets.QHBoxLayout(); self.lay.addLayout(row)
        self.keys = {}                       # "1"/"2"/"3" -> button, like Dremzo Code's approvals
        self.keys["1"] = self.button(row, "Allow   1", lambda: self.send(True, "Allowed once", tool_input=r.get("input")), True)
        sugg = r.get("permission_suggestions")
        if sugg:
            wheres = {x.get("destination") for x in sugg if isinstance(x, dict)}
            where = " / ".join(SUGG_WHERE.get(w, w) for w in wheres if w) or "this session"
            b = self.button(row, "Always allow", lambda: self.send(True, "Always allowed - " + where,
                                                                   tool_input=r.get("input"), permissions=sugg))
            b.setToolTip("Remembered for: " + where)
            b.setText("Always allow   2"); self.keys["2"] = b
        self.keys["3"] = self.button(row, "Deny   3", lambda: self.send(False, "Denied", message=self.fb.text().strip()))
        self.fb = QtWidgets.QLineEdit(); self.fb.setPlaceholderText("or tell Brother what to do instead, then Deny")
        self.fb.setStyleSheet("background:#1f1e1d;color:#ece9e3;border:1px solid #3a3935;border-radius:6px;padding:4px;")
        self.fb.returnPressed.connect(lambda: self.send(False, "Denied", message=self.fb.text().strip()))
        row.addWidget(self.fb, 1)


class QuestionCard(_Card):
    """AskUserQuestion: Claude asks Plug to pick. The answers go back inside updatedInput."""
    def __init__(self, req, answer, parent=None):
        super().__init__(req, answer, parent)
        inp = self.r.get("input") or {}
        self.qs = []
        self.lay.addWidget(QtWidgets.QLabel("<b>Brother has a question</b>"))
        for q in inp.get("questions") or []:
            box = QtWidgets.QFrame(); bl = QtWidgets.QVBoxLayout(box); bl.setContentsMargins(0, 4, 0, 4); bl.setSpacing(3)
            head = q.get("header")
            t = QtWidgets.QLabel(("<span style='color:#d9a548'>%s</span>  " % _esc(head) if head else "") + _esc(q.get("question", "")))
            t.setWordWrap(True); bl.addWidget(t)
            group = QtWidgets.QButtonGroup(box); group.setExclusive(not q.get("multiSelect"))
            opts = []
            for o in q.get("options") or []:
                w = (QtWidgets.QCheckBox if q.get("multiSelect") else QtWidgets.QRadioButton)(o.get("label", ""))
                w.setStyleSheet("color:#ece9e3;")
                if o.get("description"):
                    w.setToolTip(o["description"])
                group.addButton(w); bl.addWidget(w); opts.append(w)
                if o.get("description"):
                    dl = QtWidgets.QLabel(_esc(o["description"])); dl.setObjectName("dim"); dl.setWordWrap(True)
                    dl.setContentsMargins(22, 0, 0, 0); bl.addWidget(dl)
            other = QtWidgets.QLineEdit(); other.setPlaceholderText("Other...")
            other.setStyleSheet("background:#1f1e1d;color:#ece9e3;border:1px solid #3a3935;border-radius:6px;padding:4px;")
            bl.addWidget(other)
            self.lay.addWidget(box)
            self.qs.append((q, opts, other))
        row = QtWidgets.QHBoxLayout(); self.lay.addLayout(row)
        self.button(row, "Answer", self._submit, True)
        self.button(row, "Skip", lambda: self.send(False, "Skipped",
                                                   message="Plug skipped the question - decide sensibly or ask differently."))
        row.addStretch(1)

    def _submit(self):
        answers = {}
        for q, opts, other in self.qs:
            picked = [w.text() for w in opts if w.isChecked()]
            if other.text().strip():
                picked.append(other.text().strip())
            if picked:
                answers[q.get("question", "")] = ", ".join(picked)
        if not answers:
            return
        inp = dict(self.r.get("input") or {})
        inp["answers"] = answers
        self.send(True, "Answered: " + "; ".join(answers.values()), tool_input=inp)


class PlanCard(_Card):
    """ExitPlanMode: the plan, readable, with the three choices Claude Code offers."""
    def __init__(self, req, answer, parent=None):
        super().__init__(req, answer, parent)
        inp = self.r.get("input") or {}
        self.lay.addWidget(QtWidgets.QLabel("<b>Brother's plan - ready to start?</b>"))
        self.lay.addWidget(AutoText(inp.get("plan") or _short(inp, 2000)))
        row = QtWidgets.QHBoxLayout(); self.lay.addLayout(row)
        self.button(row, "Approve + accept edits", lambda: self.send(
            True, "Approved - edits accepted automatically", tool_input=inp,
            permissions=[{"type": "setMode", "mode": "acceptEdits", "destination": "session"}]), True)
        self.button(row, "Approve", lambda: self.send(True, "Approved - each edit still asks", tool_input=inp))
        self.button(row, "Keep planning", lambda: self.send(
            False, "Keep planning", message=self.fb.text().strip() or "Plug wants to keep planning."))
        self.fb = QtWidgets.QLineEdit(); self.fb.setPlaceholderText("what to change in the plan...")
        self.fb.setStyleSheet("background:#1f1e1d;color:#ece9e3;border:1px solid #3a3935;border-radius:6px;padding:4px;")
        row.addWidget(self.fb, 1)


def make_card(req, answer):
    name = (req.get("request") or {}).get("tool_name")
    return {"AskUserQuestion": QuestionCard, "ExitPlanMode": PlanCard}.get(name, PermissionCard)(req, answer)


class Composer(QtWidgets.QPlainTextEdit):
    submit = QtCore.Signal()
    escape = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("composer")
        self.setPlaceholderText("Ask Brother...   Enter to send, Shift+Enter for a new line, / for commands")
        self.setMinimumHeight(44); self.setMaximumHeight(160)
        self.images = []                                        # [(media_type, base64)]

    submit_now = QtCore.Signal()

    def keyPressEvent(self, e):
        panel = self.parent_panel()
        k, mods = e.key(), e.modifiers()
        # the / popup: arrows move, Tab / Enter pick (it used to be click-only)
        if panel is not None and panel.slash.isVisible() and panel.slash.count():
            if k in (QtCore.Qt.Key_Down, QtCore.Qt.Key_Up):
                r = panel.slash.currentRow() + (1 if k == QtCore.Qt.Key_Down else -1)
                panel.slash.setCurrentRow(max(0, min(panel.slash.count() - 1, r))); return
            if k in (QtCore.Qt.Key_Tab, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                panel._slash_pick(panel.slash.currentItem() or panel.slash.item(0)); return
            if k == QtCore.Qt.Key_Escape:
                panel.slash.hide(); return
        # 1 / 2 / 3 answer the approval card on screen while the box is empty
        if (panel is not None and not self.toPlainText() and not (mods & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier))
                and e.text() in ("1", "2", "3")):
            card = panel.live_permission()
            if card is not None and e.text() in card.keys:
                card.keys[e.text()].click(); return
        if k in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and (mods & QtCore.Qt.ControlModifier):
            self.submit_now.emit(); return
        if k in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not (mods & QtCore.Qt.ShiftModifier):
            self.submit.emit(); return
        if e.key() == QtCore.Qt.Key_Escape:
            self.escape.emit(); return
        if e.key() == QtCore.Qt.Key_Backspace and not self.toPlainText() and self.images:
            self.images = []; self.parent_panel().refresh_chips(); return
        super().keyPressEvent(e)

    # drag-and-drop: renders and photos become attachments, other files an @path, node paths text
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasImage() or e.mimeData().hasText():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        if self.take_drop(e.mimeData()):
            e.acceptProposedAction()
        else:
            super().dropEvent(e)

    def take_drop(self, md):
        panel = self.parent_panel()
        if md.hasUrls() and any(u.isLocalFile() for u in md.urls()):
            for u in md.urls():
                if not u.isLocalFile():
                    continue
                p = u.toLocalFile()
                ext = os.path.splitext(p)[1].lower().lstrip(".")
                if ext in ("png", "jpg", "jpeg", "webp", "gif") and os.path.getsize(p) < 20 * 1024 * 1024:
                    mt = "image/jpeg" if ext in ("jpg", "jpeg") else "image/%s" % ext
                    with open(p, "rb") as fh:
                        self.images.append((mt, base64.b64encode(fh.read()).decode()))
                elif panel is not None:
                    panel._mention(p)
            if panel is not None:
                panel.refresh_chips()
            self.setFocus()
            return True
        if md.hasImage():
            self.insertFromMimeData(md); return True
        if md.hasText():
            self.insertPlainText(md.text()); self.setFocus(); return True
        return False

    def insertFromMimeData(self, md):                           # paste an image straight in
        if md.hasImage():
            img = QtGui.QImage(md.imageData())
            ba = QtCore.QByteArray(); buf = QtCore.QBuffer(ba); buf.open(QtCore.QIODevice.WriteOnly)
            img.save(buf, "PNG")
            self.images.append(("image/png", base64.b64encode(bytes(ba)).decode()))
            self.parent_panel().refresh_chips()
            return
        super().insertFromMimeData(md)

    def parent_panel(self):
        w = self.parent()
        while w is not None and not isinstance(w, ChatPanel):
            w = w.parent()
        return w


# ============================================================================ the panel
class Convo(QtCore.QObject):
    """One conversation: its own claude process, feed, model and permission mode. Several can
    run at once; the panel only decides which one is on screen."""

    def __init__(self, panel, resume=None, title="New session", model=None, fork=False, effort=None):
        super().__init__(panel)
        self.fork = fork
        self.effort = effort
        self.init_info = None
        self.bubbles = []                 # user bubbles still waiting for their uuid (rewind point)
        self.streams = {}                 # parent_tool_use_id -> {"text","think","tool"}: one per agent
        self.panel = panel
        self.title = title
        self.session = None
        self.sid = resume
        self.has_history = bool(resume)   # only a conversation with turns on disk can be --resume'd
        self.model = model
        self.mode = "default"             # every conversation starts asking first
        self.cards = {}
        self.asks = {}                    # request_id -> live question card
        self.ctrl = {}                    # our control request_id -> what it was
        self.tasks = {}                   # background task_id -> description
        self.cur_text = self.cur_think = self.cur_tool = None
        self.context = None               # (used, max) from get_context_usage
        self.api_source = None            # "none" = signed in with the subscription, not an API key
        self.announced = None
        self.follow = True
        self.queue = []                   # (text, images) sent while a turn was running
        self.unread = None                # None | "done" | "error" - finished while not looked at
        self.turn_t0 = None               # when the running turn started (the "Working Ns" line)
        self.working_w = None
        self.edited = {}                  # path -> {"add", "del", "html"} for the "Edited N files" card
        self.edit_ids = {}                # tool_use_id -> (path, add, del)
        self.scroll = QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        host = QtWidgets.QWidget(objectName="feedhost")
        # a bare "background:transparent;" here cascades to every child and wiped the user bubble's fill
        host.setStyleSheet("QWidget#feedhost{background:transparent;}")
        # one 760px column in the middle, like Dremzo Code's .log-inner
        hl = QtWidgets.QHBoxLayout(host); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)
        col = QtWidgets.QWidget(); col.setMaximumWidth(760)
        col.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        hl.addStretch(1); hl.addWidget(col, 100); hl.addStretch(1)
        self.feed = QtWidgets.QVBoxLayout(col); self.feed.setContentsMargins(28, 24, 28, 40); self.feed.setSpacing(14)
        self.feed.addStretch(1)
        self.scroll.setWidget(host)
        sb = self.scroll.verticalScrollBar()
        sb.rangeChanged.connect(lambda _a, mx: self.follow and sb.setValue(mx))
        sb.valueChanged.connect(lambda v: setattr(self, "follow", v >= sb.maximum() - 30))
        # "Jump to latest" floats over the log while you're scrolled up (Dremzo Code's log-below)
        self.jump = QtWidgets.QPushButton("↓  Jump to latest", self.scroll)
        self.jump.setStyleSheet("QPushButton{background:#2a2927;color:#ece9e3;border:1px solid #3a3935;"
                                "border-radius:14px;padding:5px 14px;font-size:12px;}"
                                "QPushButton:hover{background:#353532;}")
        self.jump.hide()
        self.jump.clicked.connect(self.to_bottom)
        sb.rangeChanged.connect(lambda *_: self._place_jump())
        sb.valueChanged.connect(lambda *_: self._place_jump())
        self.scroll.installEventFilter(self)

    def to_bottom(self):
        self.follow = True
        sb = self.scroll.verticalScrollBar(); sb.setValue(sb.maximum())

    def _place_jump(self):
        sb = self.scroll.verticalScrollBar()
        show = sb.maximum() > 0 and sb.value() < sb.maximum() - 120
        if show:
            self.jump.adjustSize()
            self.jump.move((self.scroll.width() - self.jump.width()) // 2, self.scroll.height() - self.jump.height() - 14)
            self.jump.raise_()
        self.jump.setVisible(show)

    def eventFilter(self, obj, ev):
        if obj is self.scroll and ev.type() == QtCore.QEvent.Resize:
            self._place_jump()
        return False

    # ---------------------------------------------------------------- the "Working Ns" line
    def _working(self, on):
        if on and self.working_w is None:
            self.working_w = QtWidgets.QLabel()
            self.working_w.setStyleSheet("color:#a6a39d;font-size:13px;")
            self.feed.insertWidget(self.feed.count() - 1, self.working_w)
            self.tick_working()
        elif not on and self.working_w is not None:
            self.working_w.deleteLater(); self.working_w = None
            self.turn_t0 = None

    def tick_working(self, phase=0):
        if self.working_w is None:
            return
        secs = int(time.time() - (self.turn_t0 or time.time()))
        took = ("%dm %02ds" % (secs // 60, secs % 60)) if secs >= 60 else "%ds" % secs
        dots = "".join("<span style='color:%s'>●</span>" % ("#ff4f9a" if i == phase % 3 else "#5a3346") for i in range(3))
        self.working_w.setText("%s&nbsp;&nbsp;Working %s &nbsp;·&nbsp; <span style='color:#77756f'>Esc to stop</span>"
                               % (dots, took))

    # ---------------------------------------------------------------- state
    @property
    def busy(self):
        return bool(self.session is not None and self.session.busy)

    @property
    def waiting(self):
        return any(c.live for c in self.asks.values())

    @property
    def working(self):
        """Anything still going on: a turn, a question, or background tasks."""
        return self.busy or self.waiting or bool(self.tasks)

    def _expire_asks(self, why=None):
        for c in self.asks.values():
            c.expire(why) if why else c.expire()
        self.asks = {}

    # ---------------------------------------------------------------- process
    def start(self):
        if self.session is not None and self.session.running() and not self.session.parked:
            return
        old = self.session
        if old is not None:
            for sig, slot in ((old.event, self.on_event), (old.ended, self.on_ended)):
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self.session = ClaudeSession(self.panel.cwd, self.sid if self.has_history else None, self.model,
                                     self.mode, self, session_id=None if self.fork else self.sid,
                                     effort=self.effort, fork=self.fork)
        self.session.event.connect(self.on_event)
        self.session.ended.connect(self.on_ended)
        _ensure_link()
        try:
            self.session.start()
            if not self.fork:
                self.sid = self.session.session_id
            # a fork gets its new id from system/init; after that it is a normal session
        except RuntimeError as e:
            self.add_note(str(e), "#e5675f")

    def park(self):
        """Leaving an idle conversation: end its process (it resumes on the next message).
        Never while a turn, a question or a background task is still going."""
        if self.session is not None and not self.working:
            self.session.stop()

    def send(self, text, imgs, queue_if_busy=True):
        if queue_if_busy and (self.busy or self.waiting):
            # Dremzo Code's queue: shown above the composer, sent when the turn ends
            self.queue.append((text, list(imgs)))
            self.panel.refresh_queue()
            return
        self.start()
        self.add_user(text, len(imgs))
        if self.session.send(text, imgs):
            self.has_history = True
            self.turn_t0 = time.time()
            self.edited, self.edit_ids = {}, {}
            self._working(True)
        self.follow = True
        self.panel.convo_changed(self)

    def control(self, what, subtype, **kw):
        self.start()
        rid = self.session.control(subtype, **kw)
        self.ctrl[rid] = what
        return rid

    def set_mode(self, mode):
        if mode == self.mode:
            return
        if self.session is not None and self.session.running() and not self.session.parked:
            self.control(("mode", mode), "set_permission_mode", mode=mode)
        else:
            self.mode = mode              # applied at the next launch

    def set_effort(self, effort):
        self.effort = effort
        if self.session is not None and self.session.running() and not self.session.parked:
            self.control(("effort", effort), "apply_flag_settings", settings={"effortLevel": effort})

    def rename(self, title):
        self.title = title
        self.control(("rename", title), "rename_session", title=title)

    def rewind(self, bubble):
        """Put the files Claude edited back the way they were before this message."""
        if not bubble.uuid:
            return
        self.pending_rewind = bubble
        self.control(("rewind?", bubble.uuid), "rewind_files", user_message_id=bubble.uuid, dry_run=True)

    def set_model(self, model):
        self.model = model
        if self.session is not None and self.session.running() and not self.session.parked:
            self.control(("model", model), "set_model", model=model or "default")

    # ---------------------------------------------------------------- feed
    def _add(self, w):
        i = self.feed.indexOf(self.working_w) if self.working_w is not None else -1
        self.feed.insertWidget(i if i >= 0 else self.feed.count() - 1, w)
        return w

    # ---------------------------------------------------------------- 5. files Claude edited this turn
    def _track_edit(self, name, tool_id, inp):
        if name not in ("Write", "Edit", "MultiEdit", "NotebookEdit") or not isinstance(inp, dict):
            return
        path = inp.get("file_path") or inp.get("notebook_path")
        if not path or tool_id in self.edit_ids:
            return
        if name == "Write":
            add, dele, edits = len(str(inp.get("content", "")).splitlines()), 0, []
        else:
            edits = inp.get("edits") or [inp]
            add = sum(len(str(e.get("new_string", "")).splitlines()) for e in edits)
            dele = sum(len(str(e.get("old_string", "")).splitlines()) for e in edits)
        html = []
        for e in edits:
            for line in str(e.get("old_string", "")).splitlines()[:40]:
                html.append("<div style='background:#3a1e1c;color:#f0b0aa'>- %s</div>" % _esc(line))
            for line in str(e.get("new_string", "")).splitlines()[:40]:
                html.append("<div style='background:#173222;color:#a8e0b8'>+ %s</div>" % _esc(line))
        rec = self.edited.setdefault(path, {"add": 0, "del": 0, "html": ""})
        rec["add"] += add; rec["del"] += dele; rec["html"] += "".join(html)
        self.edit_ids[tool_id] = (path, add, dele)

    def _untrack_edit(self, tool_id):
        got = self.edit_ids.pop(tool_id, None)
        if got and got[0] in self.edited:
            rec = self.edited[got[0]]
            rec["add"] -= got[1]; rec["del"] -= got[2]
            if rec["add"] <= 0 and rec["del"] <= 0:
                del self.edited[got[0]]

    def add_note(self, text, color="#77756f"):
        l = QtWidgets.QLabel(text); l.setWordWrap(True); l.setStyleSheet("color:%s;font-size:11px;" % color)
        return self._add(l)

    def add_user(self, text, n_images=0, uuid_=None):
        f = QtWidgets.QFrame(objectName="user")
        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(14, 9, 14, 4); lay.setSpacing(0)
        body = AutoText(text + (("\n\n*+%d image(s)*" % n_images) if n_images else ""), color="#ece9e3")
        lay.addWidget(body)
        probe = QtGui.QTextDocument(); probe.setDefaultFont(body.font()); probe.setHtml(body.toHtml())
        f.setMaximumWidth(int(probe.idealWidth()) + 40)
        rw = QtWidgets.QPushButton("Rewind files to here", objectName="flat")
        rw.setToolTip("Undo the file edits Claude made from this message on (the conversation stays)")
        rw.clicked.connect(lambda: self.rewind(f))
        lay.addWidget(rw, 0, QtCore.Qt.AlignRight)
        f.uuid = uuid_
        f.sent_text = text.strip()
        f.rewind_btn = rw
        rw.setVisible(bool(uuid_))
        if not uuid_:
            self.bubbles.append(f)
        self.streams = {}
        row = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0)
        rl.addStretch(22); rl.addWidget(f, 78)           # right-aligned, never wider than 78%
        self._add(row)
        return f

    def add_text(self, text="", depth=0):
        t = AutoText(text, color="#a6a39d" if depth else None)
        if depth:
            t.setStyleSheet("color:#a6a39d;border-left:2px solid #3a3935;padding-left:6px;margin-left:%dpx;" % (18 * depth))
        self.cur_text = self._add(t)
        return t

    def add_think(self, depth=0):
        """Thinking, folded to one line like Claude Code; click to read it."""
        f = QtWidgets.QFrame(objectName="think")
        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(10 + 18 * depth, 0, 0, 0); lay.setSpacing(2)
        b = QtWidgets.QPushButton("Thinking...", objectName="flat")
        b.setStyleSheet("text-align:left;font-style:italic;")
        lay.addWidget(b, 0, QtCore.Qt.AlignLeft)
        t = AutoText("", color="#77756f"); t.hide(); lay.addWidget(t)
        b.clicked.connect(lambda: t.setVisible(not t.isVisible()))
        self._add(f)
        self.cur_think = t
        return t

    def add_tool(self, name, tool_id, depth=0):
        c = self._add(ToolCard(name, tool_id, depth))
        if tool_id:
            self.cards[tool_id] = c
        self.cur_text = None
        return c

    def load(self, sid):
        for kind, v in load_transcript(self.panel.cwd, sid):
            if kind == "user":
                self.add_user(v["text"], uuid_=v.get("uuid"))
            elif kind == "text":
                self.add_text(v)
            elif kind == "tool_use":
                self.add_tool(v.get("name", "?"), v.get("id")).set_input(v.get("input"))
            elif kind == "tool_result":
                c = self.cards.get(v.get("tool_use_id"))
                if c:
                    c.set_result(v.get("content"), v.get("is_error"))
        self.cur_text = None
        self.add_note("Resumed - continuing this session.")

    # ---------------------------------------------------------------- events from claude
    def _answer(self, *a, **kw):
        ok = self.session.answer_permission(*a, **kw)
        self.panel.convo_changed(self)
        return ok

    def _system(self, o):
        st = o.get("subtype")
        if o.get("permissionMode") and o["permissionMode"] != self.mode:
            self.mode = o["permissionMode"]           # plan approved, EnterPlanMode, ...: the truth
            self.panel.convo_changed(self)
        if st == "init":
            self.init_info = o
            self.sid = o.get("session_id") or self.sid
            if self.fork:                              # the fork now has its own id - a normal session
                self.fork = False
                self.has_history = True
                self.rename(self.title)                # else it shows the original's name twice
            if self.session is not None and self.session.init:
                self.panel.set_models(self.session.init.get("models") or [])
            self.api_source = o.get("apiKeySource")
            mcp = ", ".join("%s %s" % (m.get("name"), m.get("status")) for m in o.get("mcp_servers") or [])
            line = "claude %s  model %s  %s  mcp: %s" % (
                o.get("claude_code_version", ""), o.get("model"),
                "subscription" if self.api_source == "none" else "api key (%s)" % self.api_source, mcp or "none")
            if line != self.announced:                # init comes every turn - say it once
                self.announced = line
                self.add_note(line)
            self.panel.convo_changed(self)
        elif st == "status":
            if o.get("status") == "compacting":
                self.add_note("Compacting the conversation...")
            elif o.get("compact_error"):
                self.add_note("Compact failed: %s" % o["compact_error"], "#e5675f")
        elif st == "compact_boundary":
            m = o.get("compact_metadata") or {}
            self.add_note("──  Conversation compacted (%s, was %s tokens)  ──" % (
                m.get("trigger", "?"), _k(m.get("pre_tokens") or 0)), "#6aa5ff")
            self.ask_context()
        elif st == "api_retry":
            self.add_note("API busy - retry %s/%s in %.0fs (%s)" % (
                o.get("attempt"), o.get("max_retries"), (o.get("retry_delay_ms") or 0) / 1000.0,
                o.get("error_status") or o.get("error") or ""), "#d9a548")
        elif st == "notification" and o.get("text"):
            self.add_note(o["text"], "#d9a548")
        elif st == "task_started":
            tid = o.get("task_id")
            if tid:
                self.tasks[tid] = o.get("description") or o.get("summary") or "background task"
                self.panel.convo_changed(self)
        elif st == "task_notification":
            tid = o.get("task_id")
            if tid and o.get("status") not in ("running", "pending", None):
                self.tasks.pop(tid, None)
                if o.get("summary"):
                    self.add_note("Background task %s: %s" % (o.get("status"), _short(o["summary"], 200)))
                self.panel.convo_changed(self)
        elif st == "background_tasks_changed":
            running = {}
            for t in o.get("tasks") or []:
                if isinstance(t, dict) and t.get("status") in ("running", "pending"):
                    running[t.get("task_id") or t.get("id")] = t.get("description") or "background task"
            self.tasks = running
            self.panel.convo_changed(self)

    def ask_context(self):
        if self.session is not None and self.session.running() and not self.session.parked:
            self.ctrl[self.session.control("get_context_usage")] = ("context",)

    def _control_response(self, o):
        r = o.get("response") or {}
        what = self.ctrl.pop(r.get("request_id"), None)
        if what is None:
            return
        if r.get("subtype") == "error":
            if what[0] == "mode":
                self.add_note("Could not switch to %s: %s" % (what[1], r.get("error")), "#e5675f")
            elif what[0] == "model":
                self.add_note("Could not switch model: %s" % r.get("error"), "#e5675f")
            else:
                self.add_note("%s failed: %s" % (what[0].rstrip("?"), r.get("error")), "#e5675f")
            self.panel.convo_changed(self)             # the menus fall back to the real state
            return
        body = r.get("response") or {}
        if what[0] == "rewind?":
            b = getattr(self, "pending_rewind", None)
            files = body.get("filesChanged") or []
            if not body.get("canRewind") or not files:
                self.add_note("Nothing to rewind from that message%s." % (
                    (" (%s)" % body["error"]) if body.get("error") else ""), "#d9a548")
                return
            names = "\n".join("  " + os.path.basename(f) for f in files[:12])
            ok = QtWidgets.QMessageBox.question(
                self.panel, "Rewind files",
                "Put %d file(s) back the way they were before this message?\n\n%s\n\n+%s / -%s lines. "
                "The conversation itself stays." % (len(files), names, body.get("insertions", 0), body.get("deletions", 0)))
            if ok == QtWidgets.QMessageBox.Yes:
                self.control(("rewind", what[1]), "rewind_files", user_message_id=what[1], dry_run=False)
            return
        if what[0] == "rewind":
            self.add_note("Files rewound to before that message." if body.get("canRewind", True)
                          else "Rewind failed: %s" % body.get("error"), "#6aa5ff")
            return
        if what[0] == "rename":
            self.panel.refresh_sessions()
        if what[0] == "mode":
            self.mode = body.get("mode") or what[1]
        elif what[0] == "context" and body.get("maxTokens"):
            self.context = (body.get("totalTokens") or 0, body["maxTokens"])
        self.panel.convo_changed(self)

    def on_event(self, o):
        t = o.get("type")
        depth = 1 if o.get("parent_tool_use_id") else 0
        if t == "system":
            self._system(o)
        elif t == "control_response":
            if self.session is not None and self.session.init:
                self.panel.set_models(self.session.init.get("models") or [])   # the answer to initialize
            self._control_response(o)
        elif t == "control_cancel_request":
            c = self.asks.pop(o.get("request_id"), None)
            if c:
                c.expire("Cancelled by Claude")
            self.panel.convo_changed(self)
        elif t == "rate_limit_event":
            self.panel.rate_limit(o.get("rate_limit_info") or {})
        elif t == "stream_event":
            # each agent (main = None, subagents by parent_tool_use_id) streams into its OWN blocks,
            # so parallel subagents can't write into each other's text
            st = self.streams.setdefault(o.get("parent_tool_use_id"), {"text": None, "think": None, "tool": None})
            ev = o.get("event") or {}
            et = ev.get("type")
            if et == "content_block_start":
                cb = ev.get("content_block") or {}
                if cb.get("type") == "text":
                    st["text"] = self.add_text("", depth)
                elif cb.get("type") == "thinking":
                    st["think"] = self.add_think(depth)
                elif cb.get("type") == "tool_use":
                    st["tool"] = self.add_tool(cb.get("name", "?"), cb.get("id"), depth)
            elif et == "content_block_delta":
                d = ev.get("delta") or {}
                if d.get("type") == "text_delta":
                    if st["text"] is None:
                        st["text"] = self.add_text("", depth)
                    st["text"].append_text(d.get("text", ""))
                elif d.get("type") == "thinking_delta":
                    if st["think"] is None:
                        st["think"] = self.add_think(depth)
                    st["think"].append_text(d.get("thinking", ""))
                elif d.get("type") == "input_json_delta" and st["tool"] is not None:
                    st["tool"].add_partial(d.get("partial_json", ""))
            elif et == "message_start":
                st["think"] = None
                st["text"] = None
        elif t == "assistant":
            st = self.streams.get(o.get("parent_tool_use_id")) or {}
            for b in (o.get("message") or {}).get("content") or []:
                if b.get("type") == "tool_use":
                    c = self.cards.get(b.get("id")) or self.add_tool(b.get("name", "?"), b.get("id"), depth)
                    c.set_input(b.get("input"))
                    self._track_edit(b.get("name"), b.get("id"), b.get("input"))
                elif b.get("type") == "text" and st.get("text") is None and b.get("text"):
                    self.add_text(b["text"], depth)   # no partials came (e.g. a subagent) - show whole
        elif t == "user":
            content = (o.get("message") or {}).get("content") or []
            results = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_result"]
            if o.get("isReplay") and not results and o.get("uuid") and self.bubbles:
                # our own message echoed back = its rewind point. Match by TEXT: a /model or other
                # local command is echoed too (<local-command-stdout>...) and must not take the slot
                txt = _text_of(content if isinstance(content, list) else [{"type": "text", "text": content}]).strip()
                for f in self.bubbles:
                    if f.sent_text and f.sent_text == txt:
                        self.bubbles.remove(f)
                        f.uuid = o["uuid"]
                        f.rewind_btn.show()
                        break
            for b in results:
                c = self.cards.get(b.get("tool_use_id"))
                if c:
                    c.set_result(b.get("content"), b.get("is_error"))
                if b.get("is_error"):
                    self._untrack_edit(b.get("tool_use_id"))
            st = self.streams.get(o.get("parent_tool_use_id"))
            if st:
                st["text"] = None
        elif t == "control_request":
            req = o.get("request") or {}
            if req.get("subtype") == "can_use_tool":
                card = make_card(o, self._answer)
                self.asks[o.get("request_id")] = card
                self._add(card)
                self.panel.notify(self, "Waiting for your answer - %s" % (
                    req.get("display_name") or req.get("tool_name") or "a question"))
            else:                                        # elicitation, hooks, ...: answer, never hang
                self.session.refuse(o.get("request_id"), "not supported by the Houdini chat panel")
                self.add_note("Claude asked for '%s', which this panel can't show yet - declined." % req.get("subtype"),
                              "#d9a548")
            self.panel.convo_changed(self)
        elif t == "result":
            u = o.get("usage") or {}
            tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                      + u.get("cache_creation_input_tokens", 0))
            # a Stop ends the turn with error_during_execution - that's Plug's choice, not an error
            stopped, self.stopped = getattr(self, "stopped", False), False
            failed = bool(o.get("is_error")) and not stopped
            if stopped:
                pass                                         # interrupt() already wrote "Stopped."
            elif failed:
                why = "; ".join(str(e) for e in (o.get("errors") or [])) or o.get("result") or o.get("subtype")
                if o.get("api_error_status"):
                    why = "%s (HTTP %s)" % (why, o["api_error_status"])
                self.add_note("error: %s" % why, "#e5675f")
            else:
                self.add_note("done  %.1fs   %s in / %s out" % ((o.get("duration_ms") or 0) / 1000.0,
                                                               _k(tokens), _k(u.get("output_tokens", 0))))
            self.cur_text = self.cur_think = self.cur_tool = None
            self.streams = {}
            self._working(False)
            if self.edited:
                self._add(EditedCard(self.edited))
                self.edited, self.edit_ids = {}, {}
            self._expire_asks()
            self.ask_context()
            if not self.panel.looking_at(self):
                self.unread = "error" if failed else "done"
            if not stopped:
                self.panel.notify(self, "Error - open the chat to see why" if failed else "Finished")
            self.panel.convo_changed(self, finished=True)

    def on_ended(self, code, err):
        self._working(False)
        self._expire_asks("Expired - claude stopped")
        self.tasks = {}
        if code not in (0, None) and err.strip():
            self.add_note("claude exited (%s): %s" % (code, err.strip()[-600:]), "#e5675f")
        self.panel.convo_changed(self)



POPUP_CSS = """
* { font-family: "Leelawadee UI"; }
QFrame#pop { background: #2a2927; border: 1px solid #3a3935; border-radius: 12px; }
QLabel { color: #ece9e3; font-size: 13px; background: transparent; }
QLabel#hdr { color: #77756f; font-size: 12px; }
QLabel#desc { color: #77756f; font-size: 12px; }
QLabel#key { color: #77756f; font-size: 12px; }
QLabel#check { color: #ece9e3; font-size: 13px; }
QLabel#badge { background: #353532; color: #a6a39d; border-radius: 5px; padding: 1px 6px; font-size: 11px; }
QWidget#row { border-radius: 8px; }
QWidget#row:hover { background: #353532; }
QFrame#sep { background: #2f2e2b; max-height: 1px; min-height: 1px; }
"""

def _safe_paint(widget, fn):
    """Paint with a guard. A Python exception while a QPainter is open takes all of Houdini down
    with signal 11 (it happened: a bad QPen keyword in the context ring), so the painter is always
    ended and the error only printed."""
    p = QtGui.QPainter(widget)
    try:
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        fn(p)
    except Exception as e:                      # never let it reach Qt
        print("brother_chat paint error in %s: %s" % (type(widget).__name__, e))
    finally:
        p.end()


class _Row(QtWidgets.QWidget):
    def __init__(self, r, menu):
        super().__init__()
        self.setObjectName("row"); self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.r, self.menu = r, menu
        self.setCursor(QtCore.Qt.PointingHandCursor)
        lay = QtWidgets.QHBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(8)
        if r.get("icon"):
            ic = QtWidgets.QLabel(r["icon"]); ic.setFixedWidth(16); ic.setObjectName("desc"); lay.addWidget(ic)
        col = QtWidgets.QVBoxLayout(); col.setSpacing(1); lay.addLayout(col, 1)
        top = QtWidgets.QHBoxLayout(); top.setSpacing(6); col.addLayout(top)
        top.addWidget(QtWidgets.QLabel(r["label"]))
        if r.get("badge"):
            top.addWidget(QtWidgets.QLabel(r["badge"], objectName="badge"))
        top.addStretch(1)
        if r.get("desc"):
            col.addWidget(QtWidgets.QLabel(r["desc"], objectName="desc"))
        if r.get("checked"):
            lay.addWidget(QtWidgets.QLabel("✓", objectName="check"))
        if r.get("key"):
            lay.addWidget(QtWidgets.QLabel(r["key"], objectName="key"))
        if r.get("sub"):
            lay.addWidget(QtWidgets.QLabel("›", objectName="key"))
        if r.get("disabled"):
            self.setEnabled(False)
            for w in self.findChildren(QtWidgets.QLabel):
                w.setStyleSheet("color:#77756f;")
        self.setToolTip(r.get("tip", ""))

    def enterEvent(self, e):
        if self.r.get("sub"):
            self.menu.open_sub(self)
        super().enterEvent(e)

    def mouseReleaseEvent(self, e):
        self.menu.trigger(self.r, self)


class PopupMenu(QtWidgets.QFrame):
    """The Claude-app style menu: rounded, a small grey header, rows with a description, a check on
    the current one, a number shortcut, and submenus that open to the side."""
    def __init__(self, rows, header=None, width=280, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(POPUP_CSS)
        self.rows, self.sub = rows, None
        outer = QtWidgets.QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        box = QtWidgets.QFrame(objectName="pop"); outer.addWidget(box)
        lay = QtWidgets.QVBoxLayout(box); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(1)
        if header:
            h = QtWidgets.QLabel(header, objectName="hdr"); h.setContentsMargins(10, 4, 10, 4); lay.addWidget(h)
        for r in rows:
            if r == "-":
                lay.addWidget(QtWidgets.QFrame(objectName="sep")); continue
            lay.addWidget(_Row(r, self))
        self.setFixedWidth(width)

    def show_at(self, anchor, align="left", above=True):
        self.adjustSize()
        g = anchor.mapToGlobal(QtCore.QPoint(0, 0))
        x = g.x() if align == "left" else g.x() + anchor.width() - self.width()
        y = g.y() - self.height() - 6 if above else g.y() + anchor.height() + 6
        scr = QtGui.QGuiApplication.screenAt(g)
        if scr is not None:
            a = scr.availableGeometry()
            x = max(a.left() + 4, min(x, a.right() - self.width() - 4))
            if y < a.top():
                y = g.y() + anchor.height() + 6
        self.move(x, y)
        self.show()
        self.setFocus()

    def trigger(self, r, row):
        if r.get("disabled"):
            return
        if r.get("sub"):
            self.open_sub(row); return
        self.close()
        if r.get("do"):
            r["do"]()

    def open_sub(self, row):
        if self.sub is not None:
            try:
                self.sub.close()
            except RuntimeError:
                pass
        rows = row.r["sub"]() if callable(row.r["sub"]) else row.r["sub"]
        self.sub = PopupMenu(rows or [{"label": "Nothing here", "disabled": True}], width=row.r.get("sub_width", 300))
        self.sub.adjustSize()
        g = row.mapToGlobal(QtCore.QPoint(row.width() + 8, -6))
        self.sub.move(g); self.sub.show()

    def keyPressEvent(self, e):
        t = e.text()
        if t.isdigit():
            for r in self.rows:
                if r != "-" and r.get("key") == t:
                    self.trigger(r, None); return
        if e.key() == QtCore.Qt.Key_Escape:
            self.close(); return
        super().keyPressEvent(e)

    def closeEvent(self, e):
        if self.sub is not None:
            try:
                self.sub.close()
            except RuntimeError:
                pass
        super().closeEvent(e)


class DotSlider(QtWidgets.QWidget):
    """Faster <-> Smarter: a dotted track with a white thumb, one stop per effort level."""
    changed = QtCore.Signal(int)

    def __init__(self, n, value, parent=None):
        super().__init__(parent)
        self.n, self.value = max(2, n), value
        self.setFixedHeight(26); self.setMinimumWidth(190)
        self.setCursor(QtCore.Qt.PointingHandCursor)

    def _x(self, i):
        pad = 12
        return pad + (self.width() - 2 * pad) * i / (self.n - 1)

    def paintEvent(self, _):
        _safe_paint(self, self._paint)

    def _paint(self, p):
        h = self.height()
        track = QtCore.QRectF(2, h / 2 - 7, self.width() - 4, 14)
        p.setPen(QtCore.Qt.NoPen); p.setBrush(QtGui.QColor("#2f2e2b")); p.drawRoundedRect(track, 7, 7)
        if self.value >= 0:
            fill = QtCore.QRectF(2, h / 2 - 7, self._x(self.value) + 8, 14)
            p.setBrush(QtGui.QColor("#4a4944")); p.drawRoundedRect(fill, 7, 7)
        p.setBrush(QtGui.QColor("#77756f"))
        for i in range(self.n):
            p.drawEllipse(QtCore.QPointF(self._x(i), h / 2), 1.6, 1.6)
        if self.value >= 0:
            p.setBrush(QtGui.QColor("#ece9e3"))
            p.drawRoundedRect(QtCore.QRectF(self._x(self.value) - 6, h / 2 - 9, 12, 18), 4, 4)

    def _set_from(self, x):
        best = min(range(self.n), key=lambda i: abs(self._x(i) - x))
        if best != self.value:
            self.value = best; self.update(); self.changed.emit(best)

    def mousePressEvent(self, e):
        self._set_from(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons() & QtCore.Qt.LeftButton:
            self._set_from(e.position().x())


class EffortPopup(QtWidgets.QFrame):
    def __init__(self, levels, current, on_pick, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setStyleSheet(POPUP_CSS)
        self.levels, self.on_pick = levels, on_pick
        outer = QtWidgets.QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        box = QtWidgets.QFrame(objectName="pop"); outer.addWidget(box)
        lay = QtWidgets.QVBoxLayout(box); lay.setContentsMargins(14, 12, 14, 14); lay.setSpacing(10)
        top = QtWidgets.QHBoxLayout(); lay.addLayout(top)
        top.addWidget(QtWidgets.QLabel("Effort", objectName="hdr"))
        self.name = QtWidgets.QLabel(); top.addWidget(self.name); top.addStretch(1)
        q = QtWidgets.QLabel("ⓘ", objectName="hdr")
        q.setToolTip("How long the model thinks before it answers.\nLower is faster; higher is smarter "
                     "on hard problems and uses more of your plan.")
        top.addWidget(q)
        ends = QtWidgets.QHBoxLayout(); lay.addLayout(ends)
        ends.addWidget(QtWidgets.QLabel("Faster", objectName="desc")); ends.addStretch(1)
        ends.addWidget(QtWidgets.QLabel("Smarter", objectName="desc"))
        idx = levels.index(current) if current in levels else -1
        self.slider = DotSlider(len(levels), idx)
        self.slider.changed.connect(self._moved)
        lay.addWidget(self.slider)
        self._label(idx)
        self.setFixedWidth(260)

    def _label(self, i):
        self.name.setText(self.levels[i].capitalize() if i >= 0 else "Default")

    def _moved(self, i):
        self._label(i)
        self.on_pick(self.levels[i])

    show_at = PopupMenu.show_at

    def keyPressEvent(self, e):
        if e.key() in (QtCore.Qt.Key_Left, QtCore.Qt.Key_Right):
            i = max(0, min(len(self.levels) - 1, self.slider.value + (1 if e.key() == QtCore.Qt.Key_Right else -1)))
            self.slider.value = i; self.slider.update(); self._moved(i); return
        if e.key() in (QtCore.Qt.Key_Escape, QtCore.Qt.Key_Return):
            self.close(); return
        super().keyPressEvent(e)


class ContextRing(QtWidgets.QWidget):
    """How full the context window is, as a small ring (grey -> amber -> red)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self.pct = None

    def set(self, pct, tip):
        self.pct = pct; self.setToolTip(tip); self.update()

    def paintEvent(self, _):
        _safe_paint(self, self._paint)

    def _paint(self, p):
        r = QtCore.QRectF(2.5, 2.5, 13, 13)
        p.setPen(QtGui.QPen(QtGui.QColor("#3a3935"), 2.2)); p.drawEllipse(r)
        if self.pct:
            col = "#e5675f" if self.pct > 85 else "#d9a548" if self.pct > 65 else "#6aa5ff"
            pen = QtGui.QPen(QtGui.QColor(col), 2.2); pen.setCapStyle(QtCore.Qt.RoundCap)
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(360 * 16 * min(100.0, self.pct) / 100.0))


class Thumb(QtWidgets.QLabel):
    """An attached image inside the composer, with an x on hover."""
    def __init__(self, data, on_remove, parent=None):
        super().__init__(parent)
        self.setFixedSize(112, 112)
        img = QtGui.QImage.fromData(base64.b64decode(data))
        pm = QtGui.QPixmap.fromImage(img).scaled(112, 112, QtCore.Qt.KeepAspectRatioByExpanding,
                                                 QtCore.Qt.SmoothTransformation)
        out = QtGui.QPixmap(112, 112); out.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(out); p.setRenderHint(QtGui.QPainter.Antialiasing)
        path = QtGui.QPainterPath(); path.addRoundedRect(QtCore.QRectF(0.5, 0.5, 111, 111), 10, 10)
        p.setClipPath(path)
        p.drawPixmap((112 - pm.width()) // 2, (112 - pm.height()) // 2, pm)
        p.setClipping(False); p.setPen(QtGui.QPen(QtGui.QColor("#3a3935"), 1)); p.drawPath(path); p.end()
        self.setPixmap(out)
        self.x = QtWidgets.QPushButton("×", self, objectName="round")
        self.x.setFixedSize(22, 22); self.x.setStyleSheet("border-radius:11px;font-size:13px;")
        self.x.move(112 - 26, 4); self.x.hide(); self.x.clicked.connect(on_remove)

    def enterEvent(self, e):
        self.x.show(); super().enterEvent(e)

    def leaveEvent(self, e):
        self.x.hide(); super().leaveEvent(e)


def _git_branch(cwd):
    try:
        import subprocess
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True,
                           text=True, timeout=3, creationflags=0x08000000)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""



# ============================================================================ voice input
WHISPER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brother_whisper.py")
VOICE_PROMPT = ("Houdini, SOP, DOP, VEX, VOP, wrangle, attribute, pyro, FLIP, vellum, RBD, voxel, "
                "Karma, solver, node, parm, Brother")


def _system_python():
    """A Python that is NOT Houdini's: faster-whisper lives in the user's own install."""
    env = claude_env()
    for d in env.value("PATH").split(os.pathsep):
        exe = os.path.join(d, "python.exe")
        if d and os.path.exists(exe) and "windowsapps" not in d.lower():
            return exe, env
    return shutil.which("py"), env


class WhisperWorker(QtCore.QObject):
    """The long-lived brother_whisper.py process: the model loads once, then each clip is ~1s."""
    ready = QtCore.Signal(str)
    result = QtCore.Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc, self.buf, self.is_ready, self.pending = None, b"", False, []

    def start(self):
        if self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning:
            return
        exe, env = _system_python()
        env.remove("PYTHONNOUSERSITE")
        self.proc = QtCore.QProcess(self)
        self.proc.setProcessEnvironment(env)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._died)
        self.proc.start(exe or "python", ["-u", WHISPER_SCRIPT])

    def _died(self, *_):
        was_ready, self.is_ready = self.is_ready, False
        err = bytes(self.proc.readAllStandardError()).decode("utf8", "replace").strip().splitlines()
        if not was_ready or self.pending:         # never came up, or died holding a clip
            self.pending = []
            self.ready.emit("worker stopped: " + (err[-1] if err else "no output"))

    def transcribe(self, wav):
        self.start()
        req = {"wav": wav, "prompt": VOICE_PROMPT}
        if self.is_ready:
            self.proc.write((json.dumps(req) + "\n").encode("utf8"))
        else:
            self.pending.append(req)                # sent as soon as the model has loaded

    def _read(self):
        self.buf += bytes(self.proc.readAllStandardOutput())
        *lines, self.buf = self.buf.split(b"\n")
        for raw in lines:
            try:
                o = json.loads(raw.decode("utf8", "replace"))
            except ValueError:
                continue
            if "ready" in o:
                self.is_ready = bool(o["ready"])
                self.ready.emit(o.get("device") or o.get("error") or "")
                for req in self.pending:
                    self.proc.write((json.dumps(req) + "\n").encode("utf8"))
                self.pending = []
            else:
                self.result.emit(o)


class MicRecorder(QtCore.QObject):
    """Raw PCM from the default microphone into a .wav (QtMultimedia QAudioSource)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.src, self.io, self.data, self.fmt = None, None, bytearray(), None

    def start(self):
        from PySide6 import QtMultimedia
        dev = QtMultimedia.QMediaDevices.defaultAudioInput()
        if dev.isNull():
            raise RuntimeError("no microphone found")
        fmt = QtMultimedia.QAudioFormat()
        fmt.setSampleRate(16000); fmt.setChannelCount(1); fmt.setSampleFormat(QtMultimedia.QAudioFormat.Int16)
        if not dev.isFormatSupported(fmt):
            fmt = dev.preferredFormat()
        self.fmt, self.data = fmt, bytearray()
        self.src = QtMultimedia.QAudioSource(dev, fmt, self)
        self.io = self.src.start()
        self.io.readyRead.connect(self._pull)
        self.device_name = dev.description()

    def _pull(self):
        try:
            self.data += bytes(self.io.readAll())
        except RuntimeError:
            pass

    def level(self):
        """Loudness of the last ~0.1s, 0..1 - so the button can show the mic is actually hearing."""
        import array
        if not self.data or self.fmt is None:
            return 0.0
        from PySide6 import QtMultimedia
        if self.fmt.sampleFormat() != QtMultimedia.QAudioFormat.Int16:
            return 0.5
        tail = bytes(self.data[-3200:])
        a = array.array("h", tail[: len(tail) // 2 * 2])
        return min(1.0, (max((abs(x) for x in a), default=0) / 12000.0))

    def stop(self, path):
        """Write what was heard to `path`; returns its length in seconds."""
        import array, wave
        from PySide6 import QtMultimedia
        self._pull()
        if self.src is not None:
            self.src.stop()
        f, raw = self.fmt, bytes(self.data)
        sf = f.sampleFormat()
        if sf == QtMultimedia.QAudioFormat.Float:           # whisper reads 16-bit wav fine; convert
            a = array.array("f", raw[: len(raw) // 4 * 4])
            raw = array.array("h", (max(-32768, min(32767, int(x * 32767))) for x in a)).tobytes()
            width = 2
        elif sf == QtMultimedia.QAudioFormat.Int32:
            a = array.array("i", raw[: len(raw) // 4 * 4])
            raw = array.array("h", (x >> 16 for x in a)).tobytes()
            width = 2
        elif sf == QtMultimedia.QAudioFormat.UInt8:
            width = 1
        else:
            width = 2
        with wave.open(path, "wb") as w:
            w.setnchannels(f.channelCount()); w.setsampwidth(width); w.setframerate(f.sampleRate())
            w.writeframes(raw)
        return len(raw) / float(width * f.channelCount() * f.sampleRate())


SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class EdgeGrip(QtWidgets.QWidget):
    """An invisible strip along one edge (or a corner) of a frameless window. Hover shows the
    resize cursor; dragging hands the resize to the OS, so it feels like any other window."""
    T, C = 6, 14                                           # edge thickness, corner size
    E = QtCore.Qt.Edge
    EDGES = (E.LeftEdge, E.RightEdge, E.TopEdge, E.BottomEdge,
             E.TopEdge | E.LeftEdge, E.TopEdge | E.RightEdge,
             E.BottomEdge | E.LeftEdge, E.BottomEdge | E.RightEdge)

    def __init__(self, win, edges):
        super().__init__(win)
        self.win, self.edges = win, QtCore.Qt.Edges(edges)
        E = QtCore.Qt.Edge
        l, r, t, b = (bool(self.edges & x) for x in (E.LeftEdge, E.RightEdge, E.TopEdge, E.BottomEdge))
        self.setCursor(QtCore.Qt.SizeFDiagCursor if (t and l) or (b and r) else
                       QtCore.Qt.SizeBDiagCursor if (t and r) or (b and l) else
                       QtCore.Qt.SizeHorCursor if (l or r) else QtCore.Qt.SizeVerCursor)
        self.lrtb = (l, r, t, b)
        self._start = None
        self.place(); self.raise_()

    def place(self):
        W, H, T, C = self.win.width(), self.win.height(), self.T, self.C
        l, r, t, b = self.lrtb
        if (l or r) and (t or b):                          # corner
            self.setGeometry(0 if l else W - C, 0 if t else H - C, C, C)
        elif l or r:
            self.setGeometry(0 if l else W - T, C, T, H - 2 * C)
        else:
            self.setGeometry(C, 0 if t else H - T, W - 2 * C, T)
        self.raise_()

    def mousePressEvent(self, e):
        if e.button() != QtCore.Qt.LeftButton:
            return
        h = self.win.windowHandle()
        if h is not None and h.startSystemResize(self.edges):
            return
        self._start = (e.globalPosition().toPoint(), QtCore.QRect(self.win.geometry()))   # fallback

    def mouseMoveEvent(self, e):
        if self._start is None:
            return
        p0, g = self._start
        d = e.globalPosition().toPoint() - p0
        l, r, t, b = self.lrtb
        mw, mh = self.win.minimumWidth() or 520, self.win.minimumHeight() or 360
        g = QtCore.QRect(g)
        if l: g.setLeft(min(g.left() + d.x(), g.right() - mw))
        if r: g.setRight(max(g.right() + d.x(), g.left() + mw))
        if t: g.setTop(min(g.top() + d.y(), g.bottom() - mh))
        if b: g.setBottom(max(g.bottom() + d.y(), g.top() + mh))
        self.win.setGeometry(g)

    def mouseReleaseEvent(self, e):
        self._start = None


class FindBar(QtWidgets.QFrame):
    """Ctrl+F: find in the chat on screen. Enter / Shift+Enter step, Esc closes."""
    def __init__(self, panel, parent):
        super().__init__(parent)
        self.panel = panel
        self.setObjectName("findbar")
        self.setStyleSheet("QFrame#findbar{background:#2b2a28;border:1px solid #3a3935;border-radius:10px;}"
                           "QLineEdit{background:transparent;border:none;color:#ece9e3;font-size:13px;}")
        l = QtWidgets.QHBoxLayout(self); l.setContentsMargins(10, 4, 6, 4); l.setSpacing(4)
        self.edit = QtWidgets.QLineEdit(); self.edit.setPlaceholderText("Find in chat"); self.edit.setFixedWidth(200)
        l.addWidget(self.edit)
        self.count = QtWidgets.QLabel(objectName="dim"); l.addWidget(self.count)
        for txt, fn in (("↑", lambda: self.step(-1)), ("↓", lambda: self.step(1)), ("✕", self.close_bar)):
            b = QtWidgets.QPushButton(txt, objectName="flat"); b.clicked.connect(fn); l.addWidget(b)
        self.edit.textChanged.connect(self.search)
        self.edit.returnPressed.connect(lambda: self.step(-1 if QtWidgets.QApplication.keyboardModifiers()
                                                          & QtCore.Qt.ShiftModifier else 1))
        self.hits, self.i, self.widgets = [], -1, []

    def place(self):
        self.adjustSize()
        p = self.parent()
        self.move(p.width() - self.width() - 18, 52)
        self.raise_()

    def open(self):
        self.show(); self.place(); self.edit.setFocus(); self.edit.selectAll()
        self.search()

    def close_bar(self):
        self._clear(); self.hide(); self.panel.composer.setFocus()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close_bar(); return
        super().keyPressEvent(e)

    def _clear(self):
        for w in self.widgets:
            try:
                w.setExtraSelections([])
            except RuntimeError:
                pass
        self.hits, self.i, self.widgets = [], -1, []

    def search(self):
        self._clear()
        q = self.edit.text()
        c = self.panel.cur
        if not q or c is None:
            self.count.setText(""); return
        host = c.scroll.widget()
        ws = [w for w in host.findChildren(AutoText) if w.isVisibleTo(host)]
        ws.sort(key=lambda w: w.mapTo(host, QtCore.QPoint(0, 0)).y())
        for w in ws:
            cur = w.document().find(q)
            found = False
            while not cur.isNull():
                self.hits.append((w, QtGui.QTextCursor(cur))); found = True
                cur = w.document().find(q, cur)
            if found:
                self.widgets.append(w)
        self.step(1)

    def step(self, d):
        if not self.hits:
            self.count.setText("0" if self.edit.text() else ""); return
        self.i = (self.i + d) % len(self.hits)
        by = {}
        for n, (w, cur) in enumerate(self.hits):
            sel = QtWidgets.QTextEdit.ExtraSelection(); sel.cursor = cur
            sel.format.setBackground(QtGui.QColor("#ff4f9a" if n == self.i else "#5a4a1e"))
            if n == self.i:
                sel.format.setForeground(QtGui.QColor("#ffffff"))
            by.setdefault(w, []).append(sel)
        for w, sels in by.items():
            w.setExtraSelections(sels)
        w, cur = self.hits[self.i]
        c = self.panel.cur
        c.follow = False
        y = w.mapTo(c.scroll.widget(), w.cursorRect(cur).topLeft()).y()
        c.scroll.ensureVisible(0, y, 0, 120)
        self.count.setText("%d/%d" % (self.i + 1, len(self.hits)))


class ChatPanel(QtWidgets.QWidget):
    def __init__(self, main):
        super().__init__(main, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.main = main
        self.cwd = REPO
        self.convos = []                     # every conversation opened in this Houdini
        self.cur = None
        self.default_model = None            # what a new session starts on: the last one picked
        self.models = {}                     # model value -> the CLI's description of it
        self.model_list = []
        self._spin = 0
        # Dremzo Code's stack: Segoe UI for Latin, Leelawadee UI for Thai (Segoe UI has no Thai, and
        # Qt's own fallback picks a font that renders Thai about half the size)
        f = QtGui.QFont(); f.setFamilies(["Segoe UI", "Leelawadee UI", "Tahoma"]); f.setPixelSize(14)
        self.setFont(f)
        self.setStyleSheet(CSS)
        self._build()
        self.setMinimumSize(640, 420)
        self.resize(min(1100, main.width() - 80), min(760, main.height() - 80))
        c = main.geometry().center()
        self.move(c - QtCore.QPoint(self.width() // 2, self.height() // 2))
        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(110)
        self.new_session()

    @property
    def session(self):
        return self.cur.session if self.cur is not None else None

    # ---------------------------------------------------------------- layout
    def _build(self):
        outer = QtWidgets.QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        panel = QtWidgets.QFrame(objectName="panel"); outer.addWidget(panel)
        # 1px inset so children sit inside the panel's rounded border instead of painting over it
        root = QtWidgets.QHBoxLayout(panel); root.setContentsMargins(1, 1, 1, 1); root.setSpacing(0)

        side = QtWidgets.QFrame(objectName="side"); side.setFixedWidth(260); root.addWidget(side)
        sl = QtWidgets.QVBoxLayout(side); sl.setContentsMargins(6, 10, 6, 0); sl.setSpacing(2)
        top = QtWidgets.QHBoxLayout(); top.setContentsMargins(8, 0, 4, 6); top.setSpacing(8); sl.addLayout(top)
        top.addWidget(QtWidgets.QLabel(">_", objectName="brandmark"))
        top.addWidget(QtWidgets.QLabel("FX AI", objectName="brand")); top.addStretch(1)
        sbtn = QtWidgets.QPushButton("⌕", objectName="icon"); sbtn.setToolTip("Search chats (Ctrl+K)")
        sbtn.clicked.connect(self.focus_search); top.addWidget(sbtn)
        self.search = QtWidgets.QLineEdit(); self.search.setPlaceholderText("Search chats")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet("QLineEdit{background:#30302e;color:#ece9e3;border:1px solid #3a3935;"
                                  "border-radius:8px;padding:5px 9px;margin:0 6px 6px 6px;}")
        self.search.hide()
        self._search_t = QtCore.QTimer(self); self._search_t.setSingleShot(True); self._search_t.setInterval(220)
        self._search_t.timeout.connect(self.refresh_sessions)
        self.search.textChanged.connect(lambda *_: self._search_t.start())
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+K"), self, activated=self.focus_search)
        nb = QtWidgets.QPushButton("✎   New chat", objectName="nav"); nb.clicked.connect(self.new_session)
        nrow = QtWidgets.QHBoxLayout(); nrow.setSpacing(0); nrow.addWidget(nb, 1)
        kb = QtWidgets.QLabel("Ctrl+N", objectName="kbd"); kb.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        nrow.addWidget(kb); nrow.addSpacing(8); sl.addLayout(nrow)
        sl.addWidget(self.search)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+N"), self, activated=self.new_session)
        sl.addSpacing(6)
        self.state = load_state()
        self.show_archived = False
        self.list = QtWidgets.QListWidget(); self.list.itemClicked.connect(self._pick_session)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._history_menu)
        self.list.setToolTip("Right-click a chat to rename or fork it")
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        sl.addWidget(self.list, 1)
        foot = QtWidgets.QFrame(); foot.setStyleSheet("border-top:1px solid #2f2e2b;")
        fl = QtWidgets.QHBoxLayout(foot); fl.setContentsMargins(10, 9, 8, 9)
        self.cwd_label = QtWidgets.QLabel(objectName="dim"); self.cwd_label.setStyleSheet("border:none;")
        hip = os.path.basename(hou.hipFile.path())
        self.cwd_label.setText("Houdini  ·  %s" % hip); self.cwd_label.setToolTip("cwd  %s" % self.cwd)
        fl.addWidget(self.cwd_label, 1); sl.addWidget(foot)

        mainw = QtWidgets.QWidget(); root.addWidget(mainw, 1)
        mcol = QtWidgets.QVBoxLayout(mainw); mcol.setContentsMargins(0, 0, 0, 0); mcol.setSpacing(0)
        tb = QtWidgets.QFrame(objectName="titlebar"); tb.setFixedHeight(44); mcol.addWidget(tb)
        head = QtWidgets.QHBoxLayout(tb); head.setContentsMargins(14, 0, 8, 0); head.setSpacing(10)
        self.head_title = QtWidgets.QLabel("New chat", objectName="title"); head.addWidget(self.head_title, 0, QtCore.Qt.AlignVCenter)
        self.head_chip = QtWidgets.QLabel("▭  %s" % os.path.basename(self.cwd.rstrip("\\/")), objectName="chip")
        self.head_chip.setToolTip(self.cwd); head.addWidget(self.head_chip, 0, QtCore.Qt.AlignVCenter)
        head.addStretch(1)
        self.max_btn = QtWidgets.QPushButton("⤢", objectName="icon")
        self.max_btn.setToolTip("Expand to fill the screen (or double-click the header)")
        self.max_btn.clicked.connect(self.toggle_max)
        head.addWidget(self.max_btn)
        self._normal_geo = None
        hide = QtWidgets.QPushButton("✕", objectName="icon"); hide.setToolTip("Hide (the chat keeps running)")
        hide.clicked.connect(self.hide); head.addWidget(hide)

        main = QtWidgets.QVBoxLayout(); main.setContentsMargins(0, 0, 0, 14); main.setSpacing(0)
        mcol.addLayout(main, 1)
        self.mainw = mainw
        self.findbar = FindBar(self, mainw); self.findbar.hide()
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.findbar.open)
        for keys, step in (("Ctrl+Tab", 1), ("Ctrl+Shift+Tab", -1), ("Alt+Down", 1), ("Alt+Up", -1)):
            QtGui.QShortcut(QtGui.QKeySequence(keys), self, activated=lambda st=step: self.step_chat(st))

        self.limit_bar = QtWidgets.QLabel(); self.limit_bar.setWordWrap(True); self.limit_bar.hide()
        self.limit_bar.setStyleSheet("background:#2a2010;color:#d9a548;border:1px solid #6a5418;"
                                     "border-radius:6px;padding:5px 8px;font-size:12px;")
        self.stack = QtWidgets.QStackedWidget()
        self.stack.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
        main.addWidget(self.stack, 1)

        # the composer: one 760px column in the middle, like Dremzo Code's .composer-wrap
        # its own widget with a FIXED height (= its content): as a bare layout it was handed a share
        # of the chat's height and the composer box ballooned once the queue strip showed
        wrapc = QtWidgets.QWidget(); wrapc.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        wrap_row = QtWidgets.QHBoxLayout(wrapc); wrap_row.setContentsMargins(0, 0, 0, 0); main.addWidget(wrapc)
        wrapw = QtWidgets.QWidget(); wrapw.setMaximumWidth(760)
        wrapw.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        wrap_row.addStretch(1); wrap_row.addWidget(wrapw, 100); wrap_row.addStretch(1)
        wrap = QtWidgets.QVBoxLayout(wrapw); wrap.setContentsMargins(28, 0, 28, 0); wrap.setSpacing(0)
        wrap.addWidget(self.limit_bar); wrap.addSpacing(4)
        self.queue_box = QtWidgets.QFrame(); self.queue_box.setObjectName("queueBox")
        self.queue_box.setStyleSheet("QFrame#queueBox{background:#1f1e1d;border:1px solid #2f2e2b;border-radius:12px;}")
        self.queue_lay = QtWidgets.QVBoxLayout(self.queue_box); self.queue_lay.setContentsMargins(10, 6, 6, 6)
        self.queue_lay.setSpacing(2); self.queue_box.hide()
        wrap.addWidget(self.queue_box); wrap.addSpacing(6)

        # project + branch bar sitting on top of the composer ("dremzo-web  staging")
        strip_row = QtWidgets.QHBoxLayout(); strip_row.setContentsMargins(10, 0, 10, 0); wrap.addLayout(strip_row)
        strip = QtWidgets.QFrame(objectName="ctxStrip"); strip_row.addWidget(strip)
        sl2 = QtWidgets.QHBoxLayout(strip); sl2.setContentsMargins(14, 7, 14, 7); sl2.setSpacing(10)
        self.proj_label = QtWidgets.QLabel()
        self.proj_label.setStyleSheet("color:#a6a39d;font-family:%s;font-size:12px;" % MONO)
        sl2.addWidget(self.proj_label); sl2.addStretch(1)
        self.tasks_label = QtWidgets.QLabel(objectName="dim"); sl2.addWidget(self.tasks_label)
        self._refresh_project()

        # the composer box: thumbnails on top, text, and the round send button inside
        box = QtWidgets.QFrame(objectName="composerBox"); wrap.addWidget(box)
        bl = QtWidgets.QVBoxLayout(box); bl.setContentsMargins(12, 10, 10, 8); bl.setSpacing(6)
        self.thumbs = QtWidgets.QWidget(); self.thumbs_lay = QtWidgets.QHBoxLayout(self.thumbs)
        self.thumbs_lay.setContentsMargins(0, 0, 0, 0); self.thumbs_lay.setSpacing(8)
        self.thumbs.hide(); bl.addWidget(self.thumbs)
        row = QtWidgets.QHBoxLayout(); bl.addLayout(row); self.composer_row = row
        self.composer = Composer()
        self.composer.submit.connect(self.send)
        self.composer.submit_now.connect(self.send_now)
        self.setAcceptDrops(True)
        self.composer.escape.connect(self.interrupt)
        self.composer.textChanged.connect(self._slash_popup)
        self.composer.textChanged.connect(self._fit_composer)
        self.composer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        row.addWidget(self.composer, 1)
        QtCore.QTimer.singleShot(0, self._fit_composer)
        # send / stop live at the right end of the bottom row (built below), like Dremzo Code
        self.send_btn = QtWidgets.QPushButton("↑", objectName="send"); self.send_btn.setFixedSize(30, 30)
        self.send_btn.setToolTip("Send (Enter)"); self.send_btn.clicked.connect(self.send)
        self.stop_btn = QtWidgets.QPushButton("■", objectName="stopr"); self.stop_btn.setFixedSize(30, 30)
        self.stop_btn.setToolTip("Stop (Esc)"); self.stop_btn.clicked.connect(self.interrupt); self.stop_btn.hide()
        self.chips = QtWidgets.QLabel(objectName="dim"); self.chips.hide()     # kept for older callers

        # the bar under it: + | mode ............ model | effort | context ring
        bar = QtWidgets.QHBoxLayout(); bar.setSpacing(2); bl.addLayout(bar)
        self.plus_btn = QtWidgets.QPushButton("+", objectName="bar"); self.plus_btn.setFixedWidth(28)
        self.plus_btn.setStyleSheet("font-size:16px;"); self.plus_btn.setToolTip("Add files, folders, commands...")
        self.plus_btn.clicked.connect(self._plus_menu); bar.addWidget(self.plus_btn)
        self.mic_btn = QtWidgets.QPushButton("🎙", objectName="bar"); self.mic_btn.setMinimumWidth(30)
        self.mic_btn.setToolTip("Dictate (Ctrl+M) - click to start, click again to stop. Thai and English.\n"
                                "Runs Whisper on this machine; nothing is uploaded.")
        self.mic_btn.clicked.connect(self._mic_toggle); bar.addWidget(self.mic_btn)
        self.mic, self.whisper, self.mic_t0 = None, None, 0.0
        self.mic_timer = QtCore.QTimer(self); self.mic_timer.timeout.connect(self._mic_tick)
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+M"), self, activated=self._mic_toggle)
        self.mode_btn = QtWidgets.QPushButton("Manual", objectName="bar"); self.mode_btn.clicked.connect(self._mode_menu)
        bar.addWidget(self.mode_btn)
        bar.addStretch(1)
        self.status = QtWidgets.QLabel(objectName="dim"); bar.addWidget(self.status)
        self.model_btn = QtWidgets.QPushButton("Default", objectName="bar"); self.model_btn.clicked.connect(self._model_menu)
        bar.addWidget(self.model_btn)
        self.effort_btn = QtWidgets.QPushButton("Default", objectName="bar"); self.effort_btn.clicked.connect(self._effort_menu)
        self.effort_btn.setToolTip("Effort"); bar.addWidget(self.effort_btn)
        self.ring = ContextRing(); bar.addSpacing(4); bar.addWidget(self.ring); bar.addSpacing(6)
        bar.addWidget(self.send_btn); bar.addWidget(self.stop_btn)
        # resize from any edge or corner, like a normal window (see EdgeGrip) - no corner grip
        self.grips = [EdgeGrip(self, e) for e in EdgeGrip.EDGES]
        self.cost = QtWidgets.QLabel()            # replaced by the ring; kept so nothing old breaks
        QtGui.QShortcut(QtGui.QKeySequence("Ctrl+U"), self, activated=self.attach_files)

        self.slash = QtWidgets.QListWidget(self)
        self.slash.setWindowFlags(QtCore.Qt.ToolTip)
        self.slash.setStyleSheet("QListWidget{background:#2a2927;border:1px solid #3a3935;color:#ece9e3;font-size:12px;}")
        self.slash.itemClicked.connect(self._slash_pick)
        self._drag = None

    def resizeEvent(self, e):
        super().resizeEvent(e)
        for g in getattr(self, "grips", []):
            g.place()
        if getattr(self, "findbar", None) is not None:
            self.findbar.place()

    # 4. drop anywhere on the panel, not only on the text box
    def dragEnterEvent(self, e):
        md = e.mimeData()
        if md.hasUrls() or md.hasImage() or md.hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        if self.composer.take_drop(e.mimeData()):
            e.acceptProposedAction()

    # ---------------------------------------------------------------- 2. notifications
    def looking_at(self, c):
        return c is self.cur and self.isVisible() and self.isActiveWindow()

    def notify(self, c, text):
        """Plug isn't looking at this chat: flash Houdini in the taskbar and pop a Windows toast."""
        if self.looking_at(c):
            return
        try:
            QtWidgets.QApplication.alert(self.main, 0)
            if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
                if getattr(self, "_tray", None) is None:
                    icon = QtWidgets.QApplication.windowIcon()
                    if icon.isNull():
                        icon = self.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation)
                    self._tray = QtWidgets.QSystemTrayIcon(icon, self)
                    self._tray.messageClicked.connect(self._open_notified)
                    self._tray_hide = QtCore.QTimer(self); self._tray_hide.setSingleShot(True)
                    self._tray_hide.timeout.connect(self._tray.hide)
                self._notified = c
                self._tray.show()
                self._tray.showMessage("FX AI  ·  %s" % _short(c.title, 50), text,
                                       QtWidgets.QSystemTrayIcon.Information, 6000)
                self._tray_hide.start(20000)
        except Exception as e:                       # a notification must never break a turn
            print("FX AI notify failed: %s" % e)

    def _open_notified(self):
        c = getattr(self, "_notified", None)
        self.show(); self.raise_(); self.activateWindow()
        if c is not None and c in self.convos:
            self._show(c)

    # ---------------------------------------------------------------- 1. the queue
    def refresh_queue(self):
        while self.queue_lay.count():
            w = self.queue_lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        q = self.cur.queue if self.cur is not None else []
        for i, (text, imgs) in enumerate(q):
            row = QtWidgets.QWidget(); rl = QtWidgets.QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)
            lab = QtWidgets.QLabel("Queued  ·  " + _short(text.replace("\n", " "), 80) + ("   +%d image(s)" % len(imgs) if imgs else ""))
            lab.setStyleSheet("color:#a6a39d;font-size:12.5px;"); lab.setToolTip(text)
            rl.addWidget(lab, 1)
            now = QtWidgets.QPushButton("Send now", objectName="flat"); now.setToolTip("Stop the current turn and send this (Ctrl+Enter)")
            now.clicked.connect(lambda _=False, i=i: self.queue_send_now(i)); rl.addWidget(now)
            x = QtWidgets.QPushButton("✕", objectName="flat"); x.setToolTip("Remove from the queue")
            x.clicked.connect(lambda _=False, i=i: self.queue_remove(i)); rl.addWidget(x)
            self.queue_lay.addWidget(row)
        self.queue_box.setVisible(bool(q))

    def queue_remove(self, i):
        if self.cur is not None and 0 <= i < len(self.cur.queue):
            del self.cur.queue[i]
        self.refresh_queue()

    def queue_send_now(self, i):
        c = self.cur
        if c is None or not (0 <= i < len(c.queue)):
            return
        c.queue.insert(0, c.queue.pop(i))
        self.refresh_queue()
        if c.busy:
            self.interrupt()                  # the queue flushes the moment the turn stops

    def _flush_queues(self):
        for c in self.convos:
            if c.queue and not c.busy and not c.waiting and c.session is not None:
                text, imgs = c.queue.pop(0)
                c.send(text, imgs, queue_if_busy=False)
                if c is self.cur:
                    self.refresh_queue()

    def send_now(self):
        """Ctrl+Enter: send even while a turn runs - stop it first, then this goes."""
        if self.cur is not None and self.cur.busy and self.composer.toPlainText().strip():
            text = self.composer.toPlainText().strip(); imgs = list(self.composer.images)
            self.cur.queue.insert(0, (text, imgs))
            self.composer.clear(); self.composer.images = []; self.refresh_chips()
            self.refresh_queue(); self.interrupt()
        else:
            self.send()

    def live_permission(self):
        if self.cur is None:
            return None
        live = [c for c in self.cur.asks.values() if c.live and isinstance(c, PermissionCard)]
        return live[-1] if live else None

    # ---------------------------------------------------------------- 6 / 8 / 10. sidebar
    def focus_search(self):
        self.search.show(); self.search.setFocus(); self.search.selectAll()

    def step_chat(self, step):
        sids = [self.list.item(i).data(QtCore.Qt.UserRole) for i in range(self.list.count())]
        sids = [s for s in sids if s and not str(s).startswith("::")]
        if not sids:
            return
        cur = self.cur.sid if self.cur is not None else None
        i = sids.index(cur) if cur in sids else -1
        sid = sids[(i + step) % len(sids)]
        for n in range(self.list.count()):
            if self.list.item(n).data(QtCore.Qt.UserRole) == sid:
                self._pick_session(self.list.item(n)); return

    def set_flag(self, sid, key, on):
        lst = self.state[key]
        if on and sid not in lst:
            lst.append(sid)
        if not on and sid in lst:
            lst.remove(sid)
        save_state(self.state)
        self.refresh_sessions()

    def delete_session(self, sid, title):
        """Moves the transcript to ~/.houdini_brother/trash (not a permanent delete)."""
        r = QtWidgets.QMessageBox.question(self, "Delete chat", "Delete \"%s\"?\n\nIt goes to %s and can be moved back."
                                           % (_short(title, 60), TRASH_DIR))
        if r != QtWidgets.QMessageBox.Yes:
            return
        c = self._convo_for(sid)
        if c is not None:
            if c.session is not None:
                c.session.stop()
            self.convos.remove(c)
            self.stack.removeWidget(c.scroll); c.scroll.deleteLater()
            if self.cur is c:
                self.cur = None
        os.makedirs(TRASH_DIR, exist_ok=True)
        base = os.path.join(project_dir(self.cwd), sid)
        for src in (base + ".jsonl", base):
            if os.path.exists(src):
                shutil.move(src, os.path.join(TRASH_DIR, os.path.basename(src)))
        for key in ("pinned", "archived"):
            if sid in self.state[key]:
                self.state[key].remove(sid)
        save_state(self.state)
        if self.cur is None:
            self.new_session()
        else:
            self.refresh_sessions()

    def toggle_max(self):
        """Fill the screen the panel is on; again to go back to the size it had."""
        if self._normal_geo is None:
            self._normal_geo = QtCore.QRect(self.geometry())
            scr = self.screen() or QtGui.QGuiApplication.primaryScreen()
            self.setGeometry(scr.availableGeometry())
            self.max_btn.setText("⤡"); self.max_btn.setToolTip("Restore the previous size")
        else:
            self.setGeometry(self._normal_geo)
            self._normal_geo = None
            self.max_btn.setText("⤢"); self.max_btn.setToolTip("Expand to fill the screen (or double-click the header)")
        for g in getattr(self, "grips", []):
            g.setVisible(self._normal_geo is None)       # nothing to drag while filling the screen

    def mouseDoubleClickEvent(self, e):
        if e.position().y() < 48:
            self.toggle_max()

    # frameless: drag by the header (the OS moves it - snaps and all - when it can)
    def mousePressEvent(self, e):
        if e.position().y() < 48 and e.button() == QtCore.Qt.LeftButton:
            h = self.windowHandle()
            if h is not None and h.startSystemMove():
                return
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & QtCore.Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    # ---------------------------------------------------------------- conversations
    def _convo_for(self, sid):
        for c in self.convos:
            if sid and c.sid == sid and not c.fork:
                return c
        return None

    def _show(self, c):
        if self.cur is not None and self.cur is not c:
            self.cur.park()
        if self.stack.indexOf(c.scroll) < 0:
            self.stack.addWidget(c.scroll)
        self.cur = c
        c.unread = None
        self.stack.setCurrentWidget(c.scroll)
        self.refresh_queue()
        if self.findbar.isVisible():
            self.findbar.search()
        self.convo_changed(c)
        self.refresh_sessions()
        self.composer.setFocus()

    def new_session(self):
        # reuse an untouched new session instead of stacking empty ones
        for c in self.convos:
            if c.title == "New session" and not c.working and c.feed.count() <= 3 and c.mode == "default":
                self._show(c); return
        c = Convo(self, model=self.default_model)
        self.convos.append(c)
        c.add_note("New session in %s - Brother can see and drive this Houdini." % self.cwd)
        c.start()
        self._show(c)

    def _pick_session(self, item):
        sid = item.data(QtCore.Qt.UserRole)
        if sid == "::archived":
            self.show_archived = not self.show_archived; self.refresh_sessions(); return
        if not sid or str(sid).startswith("::"):
            return
        c = self._convo_for(sid)
        if c is None:                               # first time opened this Houdini: replay + resume
            c = Convo(self, resume=sid, title=item.data(QtCore.Qt.UserRole + 1) or "Session",
                      model=self.default_model)
            self.convos.append(c)
            c.load(sid)
            c.start()
        self._show(c)

    def set_models(self, models):
        """The model list comes from the CLI's own answer to initialize, not a hardcoded one."""
        if not models or self.model_list:
            return
        self.model_list = models
        self.models = {(m.get("value") if m.get("value") != "default" else None): m for m in models}
        if self.cur is not None:
            self.convo_changed(self.cur)

    def _model_name(self, value):
        """'Opus 5.5' - the versioned name, as the Claude app shows it."""
        m = self.models.get(value)
        if m:
            head = (m.get("description") or "").split(" · ")[0].strip()
            return head or m.get("displayName") or (value or "Default")
        return {None: "Default"}.get(value, value or "Default")

    def _levels(self):
        m = self.models.get(self.cur.model if self.cur else None) or {}
        if m and not m.get("supportsEffort"):
            return []
        return m.get("supportedEffortLevels") or ["low", "medium", "high", "xhigh", "max"]

    def _refresh_project(self):
        br = _git_branch(self.cwd)
        self.proj_label.setText("%s   %s" % (os.path.basename(self.cwd.rstrip("\\/")), br))
        self.proj_label.setToolTip(self.cwd)

    # ---------------------------------------------------------------- the bar's menus
    def _mode_menu(self):
        if self.cur is None:
            return
        rows = []
        for n, (v, label, desc, badge) in enumerate(MODE_ROWS, 1):
            rows.append({"label": label, "desc": desc, "badge": badge, "checked": self.cur.mode == v,
                         "key": str(n), "do": (lambda v=v: self._pick_mode(v))})
        PopupMenu(rows, header="Mode", width=290, parent=self).show_at(self.mode_btn)

    def _pick_mode(self, v):
        self.cur.set_mode(v)
        self.convo_changed(self.cur)       # the real mode shows until the switch is confirmed

    def _model_menu(self):
        if self.cur is None:
            return
        cur = self.cur.model
        main, more = [], []
        fam = {}
        for m in self.model_list or [{"value": v or "default", "displayName": l} for l, v in MODELS]:
            v = m.get("value"); v = None if v == "default" else v
            f = (m.get("displayName") or "").split(" ")[0].lower()
            plain = "(" not in (m.get("displayName") or "")
            if v is not None and f in MODEL_ORDER and plain and f not in fam:
                fam[f] = v; main.append(v)
            else:
                more.append(v)
        main.sort(key=lambda v: MODEL_ORDER.index(
            ((self.models.get(v) or {}).get("displayName") or "").split(" ")[0].lower()))
        rows = []
        for n, v in enumerate(main, 1):
            rows.append({"label": self._model_name(v), "checked": cur == v, "key": str(n),
                         "tip": (self.models.get(v) or {}).get("description", ""),
                         "do": (lambda v=v: self._pick_model(v))})

        def more_rows():
            out = []
            for v in more:
                m = self.models.get(v) or {}
                out.append({"label": m.get("displayName") or self._model_name(v),
                            "desc": (m.get("description") or "").split(" · ")[0], "checked": cur == v,
                            "do": (lambda v=v: self._pick_model(v))})
            return out
        if more:
            rows += ["-", {"label": "More models", "sub": more_rows, "sub_width": 280}]
        PopupMenu(rows, width=220, parent=self).show_at(self.model_btn, align="right")

    def _pick_model(self, v):
        self.default_model = v
        self.cur.set_model(v)
        levels = self._levels()
        if self.cur.effort and self.cur.effort not in levels:
            self.cur.effort = None           # the new model can't do that effort level
        self.convo_changed(self.cur)

    def _effort_menu(self):
        if self.cur is None or not self._levels():
            return
        EffortPopup(self._levels(), self.cur.effort, self._pick_effort, parent=self).show_at(self.effort_btn, align="right")

    def _pick_effort(self, e):
        self.cur.set_effort(e)
        self.convo_changed(self.cur)

    def _plus_menu(self):
        c = self.cur
        info = (c.init_info if c is not None else None) or {}

        def connectors():
            rows = []
            for m in info.get("mcp_servers") or []:
                st = m.get("status", "")
                rows.append({"label": m.get("name", "?").replace("plugin:", ""),
                             "desc": st, "checked": st == "connected", "disabled": st != "connected"})
            return rows or [{"label": "Send a message first to load them", "disabled": True}]

        def plugins():
            rows = []
            for pl in info.get("plugins") or []:
                name = pl.get("name") if isinstance(pl, dict) else str(pl)
                rows.append({"label": name, "desc": (pl.get("path", "") if isinstance(pl, dict) else "")[-40:]})
            return rows or [{"label": "No plugins loaded", "disabled": True}]
        rows = [{"icon": "📎", "label": "Add files or photos", "key": "Ctrl+U", "do": self.attach_files},
                {"icon": "🗀", "label": "Add folder", "do": self.attach_folder},
                {"icon": "▣", "label": "Houdini viewport", "do": self.attach_viewport},
                {"icon": "◇", "label": "Selected nodes", "do": self.attach_selection},
                {"icon": "/", "label": "Slash commands", "do": self._open_slash},
                "-",
                {"icon": "⧉", "label": "Connectors", "sub": connectors, "sub_width": 300},
                {"icon": "✦", "label": "Plugins", "sub": plugins, "sub_width": 300}]
        PopupMenu(rows, width=250, parent=self).show_at(self.plus_btn)

    # ---------------------------------------------------------------- voice
    def _mic_toggle(self):
        if self.mic is not None:
            self._mic_stop(); return
        if self.whisper is None:
            self.whisper = WhisperWorker(self)
            self.whisper.ready.connect(self._whisper_ready)
            self.whisper.result.connect(self._whisper_result)
        self.whisper.start()                         # warm the model while Plug talks
        self.mic = MicRecorder(self)
        try:
            self.mic.start()
        except Exception as e:
            self.mic = None
            self.add_note("Microphone: %s" % e, "#e5675f"); return
        self.mic_t0 = time.time()
        self.mic_btn.setStyleSheet("color:#e5675f;font-weight:700;")
        self.mic_btn.setToolTip("Listening on %s - click (or Ctrl+M) to stop" % self.mic.device_name)
        self.mic_timer.start(100)

    def _mic_tick(self):
        if self.mic is None:
            return
        t = int(time.time() - self.mic_t0)
        lv = self.mic.level()
        bars = "▁▂▃▄▅▆▇"[min(6, int(lv * 7))]
        self.mic_btn.setText("● %d:%02d %s" % (t // 60, t % 60, bars))

    def _mic_stop(self):
        self.mic_timer.stop()
        path = os.path.join(os.environ.get("TEMP", "."), "brother_dictation_%d.wav" % int(time.time() * 1000))
        try:
            secs = self.mic.stop(path)
        except Exception as e:
            secs = 0; self.add_note("Microphone: %s" % e, "#e5675f")
        self.mic = None
        self.mic_btn.setStyleSheet("")
        if secs < 0.3:
            self.mic_btn.setText("🎙"); return
        self.mic_btn.setText("… transcribing")
        self.mic_btn.setEnabled(False)
        self._pending_wav = path
        self.whisper.transcribe(path)

    def _whisper_ready(self, device):
        if device not in ("cuda", "cpu"):
            self.add_note("Voice input could not start: %s  (setup: see brother_whisper.py)" % device, "#e5675f")
            self.mic_btn.setText("🎙"); self.mic_btn.setEnabled(True)

    def _whisper_result(self, o):
        self.mic_btn.setText("🎙"); self.mic_btn.setEnabled(True)
        try:
            os.remove(getattr(self, "_pending_wav", ""))
        except OSError:
            pass
        if not o.get("ok"):
            self.add_note("Voice input: %s" % o.get("error"), "#e5675f"); return
        text = (o.get("text") or "").strip()
        if not text:
            self.add_note("Didn't catch anything - check the mic in Windows sound settings.", "#d9a548"); return
        cur = self.composer.toPlainText()
        self.composer.insertPlainText(("" if not cur or cur.endswith((" ", "\n")) else " ") + text)
        self.composer.setFocus()

    def _open_slash(self):
        self.composer.setPlainText("/")
        self.composer.moveCursor(QtGui.QTextCursor.End)
        self.composer.setFocus()

    def _fit_composer(self):
        """Exactly as tall as its text. One line: the text and the send button share one centre
        line. Several lines: the box grows and the button drops to the bottom, like the Claude app."""
        c = self.composer
        lines = max(1, int(round(c.document().size().height())))    # plain-text layout counts lines
        pad = int(2 * c.document().documentMargin()) + 2 * c.frameWidth() + 4
        h = min(160, lines * c.fontMetrics().lineSpacing() + pad)
        c.setFixedHeight(max(28, h))


    def _effort_changed(self):
        pass

    def _history_menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        sid, title = it.data(QtCore.Qt.UserRole), it.data(QtCore.Qt.UserRole + 1)
        m = QtWidgets.QMenu(self)
        m.setStyleSheet("QMenu{background:#2a2927;color:#ece9e3;border:1px solid #3a3935;}"
                        "QMenu::item:selected{background:#353532;}")
        if not sid or str(sid).startswith("::"):
            return
        pinned, archived = sid in self.state["pinned"], sid in self.state["archived"]
        pin = m.addAction("Unpin" if pinned else "Pin to top")
        ren = m.addAction("Rename...")
        fork = m.addAction("Fork - continue in a copy")
        m.addSeparator()
        arc = m.addAction("Unarchive" if archived else "Archive")
        dele = m.addAction("Delete...")
        got = m.exec(self.list.mapToGlobal(pos))
        if got is pin:
            self.set_flag(sid, "pinned", not pinned); return
        if got is arc:
            self.set_flag(sid, "archived", not archived); return
        if got is dele:
            self.delete_session(sid, title); return
        if got is ren:
            new, ok = QtWidgets.QInputDialog.getText(self, "Rename session", "Title:", text=title)
            if ok and new.strip():
                c = self._convo_for(sid)
                if c is None:
                    c = Convo(self, resume=sid, title=title, model=self.default_model)
                    self.convos.append(c); c.load(sid)
                c.rename(new.strip())
                self._show(c)
        elif got is fork:
            c = Convo(self, resume=sid, title="Fork of " + (title or "session"), model=self.default_model,
                      fork=True)
            self.convos.append(c)
            c.load(sid)
            c.add_note("Forked - this is a new session; the original is untouched.", "#6aa5ff")
            c.start()
            self._show(c)

    def convo_changed(self, c, finished=False):
        """Any conversation's state moved: refresh the list marks, and the header if it's on screen."""
        if finished and c.title == "New session":
            for sid, title, _m in list_sessions(self.cwd, limit=20):
                if sid == c.sid:
                    c.title = title
        self.refresh_sessions()
        if c is not self.cur:
            return
        self.head_title.setText(c.title)
        # the bar always shows the on-screen conversation's REAL mode, model and effort
        self.mode_btn.setText(dict((v, l) for v, l, _d, _b in MODE_ROWS).get(c.mode, c.mode))
        self.model_btn.setText(self._model_name(c.model))
        levels = self._levels()
        self.effort_btn.setVisible(bool(levels))
        self.effort_btn.setText((c.effort or "default").capitalize())
        self.stop_btn.setVisible(c.busy)
        self.send_btn.setVisible(not c.busy)
        if c.context:
            used, mx = c.context
            pct = 100.0 * used / mx
            self.ring.set(pct, "Context  %d%%\n%s of %s tokens%s" % (
                round(pct), _k(used), _k(mx), "\nClaude will compact soon - or type /compact" if pct > 65 else ""))
        else:
            self.ring.set(None, "Context - after the first reply")
        self.tasks_label.setText("%d background task%s" % (len(c.tasks), "s" if len(c.tasks) > 1 else "")
                                 if c.tasks else "")
        self.tasks_label.setToolTip("\n".join(c.tasks.values()))
        self.status.setText("")

    def rate_limit(self, info):
        """Plan usage from the CLI: warn before the limit, say plainly when it's hit."""
        st = info.get("status")
        if st not in ("allowed_warning", "rejected"):
            self.limit_bar.hide(); return
        kind = {"five_hour": "5-hour", "seven_day": "weekly", "seven_day_opus": "weekly Opus"}.get(
            info.get("rateLimitType"), info.get("rateLimitType") or "plan")
        when = ""
        if info.get("resetsAt"):
            try:
                when = " - resets %s" % datetime.datetime.fromtimestamp(float(info["resetsAt"])).strftime("%a %H:%M")
            except (TypeError, ValueError, OSError):
                pass
        used = info.get("utilization")
        pct = (" (%d%% used)" % round(float(used) * 100)) if isinstance(used, (int, float)) and used <= 1 else ""
        if st == "rejected":
            self.limit_bar.setText("Claude %s limit reached%s%s. Messages will wait until then." % (kind, pct, when))
        else:
            self.limit_bar.setText("Getting close to the Claude %s limit%s%s." % (kind, pct, when))
        self.limit_bar.show()

    def refresh_sessions(self):
        sel = self.cur.sid if self.cur is not None else None
        rows = list_sessions(self.cwd)
        on_disk = {sid for sid, _t, _m in rows}
        # live conversations not written to disk yet go on top
        live = [(c.sid, c.title, time.time()) for c in self.convos if c.sid and c.sid not in on_disk and c.working]
        allrows = live + rows
        q = self.search.text().strip().lower() if hasattr(self, "search") else ""
        if q:                                    # 6. title or anything said in the chat
            allrows = [r for r in allrows if q in (r[1] or "").lower() or q in session_text(self.cwd, r[0])]
        pinned = [r for r in allrows if r[0] in self.state["pinned"]]
        archived = [r for r in allrows if r[0] in self.state["archived"] and r[0] not in self.state["pinned"]]
        rest = [r for r in allrows if r not in pinned and r not in archived]
        self.list.clear()
        plan = []
        if pinned:
            plan += [("::head", "Pinned", None)] + pinned
        plan += [("::head", ("Results" if q else "Chats"), None)] + rest
        if archived:
            plan += [("::archived", "%s Archived (%d)" % ("▾" if self.show_archived else "▸", len(archived)), None)]
            if self.show_archived:
                plan += archived
        for sid, title, mtime in plan:
            if str(sid).startswith("::"):
                it = QtWidgets.QListWidgetItem(); it.setData(QtCore.Qt.UserRole, sid)
                if sid == "::head":
                    it.setFlags(QtCore.Qt.NoItemFlags)
                self.list.addItem(it); it.setSizeHint(QtCore.QSize(10, 30))
                lab = QtWidgets.QLabel(title); lab.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
                lab.setStyleSheet("color:#77756f;font-size:12px;padding:8px 0 0 12px;background:transparent;")
                self.list.setItemWidget(it, lab)
                continue
            c = self._convo_for(sid)
            mark = ""
            if c is not None and c.waiting:
                mark = "?  "
            elif c is not None and c.working:
                mark = SPIN[self._spin % len(SPIN)] + "  "
            elif c is not None and c.unread:
                mark = ("!" if c.unread == "error" else "•") + "  "
            it = QtWidgets.QListWidgetItem()
            it.setData(QtCore.Qt.UserRole, sid)
            it.setData(QtCore.Qt.UserRole + 1, title)
            it.setData(QtCore.Qt.UserRole + 2, "wait" if mark.startswith("?") else
                       "spin" if (mark and mark[:1] not in "•!") else "")
            it.setToolTip(("Waiting for your answer - " if mark.startswith("?") else
                           "Working... - " if mark else "") + sid)
            if mark.startswith("?"):
                it.setForeground(QtGui.QColor("#d9a548"))
            elif mark:
                it.setForeground(QtGui.QColor("#ff4f9a"))
            self.list.addItem(it)
            it.setSizeHint(QtCore.QSize(10, 32))
            self.list.setItemWidget(it, self._row(mark, title, mtime, it))
            if sid == sel:
                it.setSelected(True)

    @staticmethod
    def _ago(t):
        d = max(0, time.time() - t)
        return ("now" if d < 60 else "%dm" % (d // 60) if d < 3600 else "%dh" % (d // 3600) if d < 86400
                else "%dd" % (d // 86400) if d < 7 * 86400 else datetime.datetime.fromtimestamp(t).strftime("%d %b"))

    def _row(self, mark, title, mtime, it):
        """One chat in the sidebar: a live dot or spinner, the title, its age on the right."""
        w = QtWidgets.QWidget(); w.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        w.setStyleSheet("background:transparent;")
        l = QtWidgets.QHBoxLayout(w); l.setContentsMargins(10, 0, 10, 0); l.setSpacing(8)
        m = QtWidgets.QLabel(mark.strip()); m.setFixedWidth(12 if mark else 0)
        col = {"?": "#d9a548", "•": "#6aa5ff", "!": "#e5675f"}.get(mark[:1], "#ff4f9a")
        m.setStyleSheet("color:%s;font-size:%s;font-weight:700;" % (col, "16px" if mark[:1] in "•!" else "12px"))
        if mark[:1] == "•":
            m.setToolTip("Finished while you were away")
        t = QtWidgets.QLabel(); t.setStyleSheet("color:#ece9e3;font-size:13px;")
        f = QtGui.QFont(self.font()); f.setPixelSize(13)            # the size the stylesheet draws it at
        t.setText(QtGui.QFontMetrics(f).elidedText(title, QtCore.Qt.ElideRight, 150 if mark else 165))
        a = QtWidgets.QLabel(self._ago(mtime)); a.setStyleSheet("color:#77756f;font-size:12px;")
        l.addWidget(m); l.addWidget(t, 1); l.addWidget(a)
        it.setData(QtCore.Qt.UserRole + 3, m)
        return w

    def _tick(self):
        """Spin the marks on working conversations, tick the Working line, flush queues."""
        self._flush_queues()
        if not any(c.working for c in self.convos):
            return
        self._spin += 1
        if self.cur is not None and self._spin % 4 == 0:
            self.cur.tick_working(self._spin // 4)
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(QtCore.Qt.UserRole + 2) == "spin":
                lab = it.data(QtCore.Qt.UserRole + 3)
                if lab is not None:
                    try:
                        lab.setText(SPIN[self._spin % len(SPIN)])
                    except RuntimeError:          # the row was rebuilt meanwhile
                        pass

    # ---------------------------------------------------------------- sending
    def send(self):
        text = self.composer.toPlainText().strip()
        if not text and not self.composer.images:
            return
        self.slash.hide()
        if text in ("/clear", "/new"):
            self.composer.clear(); self.new_session(); return
        if text.startswith("/model "):
            m = text.split(None, 1)[1].strip()
            self.cur.set_model(None if m == "default" else m); self.cur.add_note("model -> %s" % m)
            self.composer.clear(); self.convo_changed(self.cur); return
        imgs = list(self.composer.images)
        self.cur.send(text, imgs)            # queued (and shown above the box) if a turn is running
        self.composer.clear(); self.composer.images = []; self.refresh_chips()
        QtCore.QTimer.singleShot(1500, self.refresh_sessions)     # the transcript file appears on disk

    def interrupt(self):
        if self.cur is not None and self.cur.busy:
            self.session.control("interrupt")
            self.cur.stopped = True
            self.cur._expire_asks("Cancelled - you stopped the turn")
            self.cur.add_note("Stopped.", "#e5675f")
            self.convo_changed(self.cur)

    def add_note(self, text, color="#77756f"):
        return self.cur.add_note(text, color)

    # ---------------------------------------------------------------- attachments
    def refresh_chips(self):
        """Attached images as thumbnails inside the composer box."""
        while self.thumbs_lay.count():
            w = self.thumbs_lay.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for n, (_mt, data) in enumerate(self.composer.images):
            self.thumbs_lay.addWidget(Thumb(data, lambda n=n: self._drop_image(n)))
        self.thumbs_lay.addStretch(1)
        self.thumbs.setVisible(bool(self.composer.images))

    def _drop_image(self, n):
        if 0 <= n < len(self.composer.images):
            del self.composer.images[n]
        self.refresh_chips()

    def attach_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Add files or photos", self.cwd)
        for p in paths:
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            if ext in ("png", "jpg", "jpeg", "webp", "gif"):
                mt = "image/jpeg" if ext in ("jpg", "jpeg") else "image/%s" % ext
                with open(p, "rb") as fh:
                    self.composer.images.append((mt, base64.b64encode(fh.read()).decode()))
            else:                                # anything else: point Claude at it by path
                self._mention(p)
        self.refresh_chips()

    attach_image = attach_files

    def attach_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Add folder", self.cwd)
        if d:
            self._mention(d)

    def _mention(self, path):
        self.composer.insertPlainText(("" if not self.composer.toPlainText() or self.composer.toPlainText().endswith(" ")
                                       else " ") + "@" + path.replace("\\", "/") + " ")
        self.composer.setFocus()

    def attach_viewport(self):
        bl = sys.modules.get("brother_link")
        try:
            res = bl.OPS["capture"]({})
            img = QtGui.QImage(res["file"])
            flat = QtGui.QImage(img.size(), QtGui.QImage.Format_RGB32); flat.fill(QtGui.QColor(40, 44, 50))
            p = QtGui.QPainter(flat); p.drawImage(0, 0, img); p.end()
            ba = QtCore.QByteArray(); buf = QtCore.QBuffer(ba); buf.open(QtCore.QIODevice.WriteOnly)
            flat.save(buf, "PNG")
            self.composer.images.append(("image/png", base64.b64encode(bytes(ba)).decode()))
            self.refresh_chips()
        except Exception as e:
            self.add_note("Viewport capture failed: %s (open a Scene View tab)" % e, "#e5675f")

    def attach_selection(self):
        sel = [n.path() for n in hou.selectedNodes()]
        if not sel:
            self.add_note("No nodes selected."); return
        self.composer.insertPlainText(("\n" if self.composer.toPlainText() else "") +
                                      "Selected nodes: " + ", ".join(sel))

    # ---------------------------------------------------------------- slash commands
    def _slash_popup(self):
        text = self.composer.toPlainText()
        if not text.startswith("/") or " " in text or "\n" in text or self.session is None:
            self.slash.hide(); return
        q = text[1:].lower()
        cmds = [{"name": "clear", "description": "Start a new session"},
                {"name": "model", "description": "Switch model: /model opus|sonnet|haiku"}] + (self.session.commands or [])
        hits = [c for c in cmds if c.get("name", "").lower().startswith(q)][:10]
        if not hits:
            self.slash.hide(); return
        self.slash.clear()
        for c in hits:
            it = QtWidgets.QListWidgetItem("/%s   %s" % (c["name"], _short(c.get("description", ""), 60)))
            it.setData(QtCore.Qt.UserRole, c["name"]); self.slash.addItem(it)
        g = self.composer.mapToGlobal(QtCore.QPoint(0, 0))
        h = min(260, 24 * len(hits) + 6)
        self.slash.setGeometry(g.x(), g.y() - h - 4, 460, h)
        self.slash.show()

    def _slash_pick(self, item):
        self.composer.setPlainText("/%s " % item.data(QtCore.Qt.UserRole))
        self.composer.moveCursor(QtGui.QTextCursor.End)
        self.slash.hide(); self.composer.setFocus()

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.interrupt() if (self.cur and self.cur.busy) else self.hide()
        else:
            super().keyPressEvent(e)


def _k(n):
    return "%.1fk" % (n / 1000.0) if n >= 1000 else str(n)


def _ensure_link():
    """The MCP tools reach this Houdini through brother_link - start it if Plug hasn't."""
    try:
        import brother_link
        if brother_link._state.get("server") is None:
            brother_link.start(quiet=True)
    except Exception:
        pass


def show_chat():
    w = _open["w"]
    try:
        if w is not None:
            w.show(); w.raise_(); w.activateWindow(); w.composer.setFocus()
            return w
    except RuntimeError:
        pass
    _open["w"] = ChatPanel(hou.qt.mainWindow())
    _open["w"].show()
    return _open["w"]
