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
MODES = (("Ask first", "default"), ("Accept edits", "acceptEdits"), ("Plan", "plan"),
         ("Bypass", "bypassPermissions"))
LOOK_TOOLS = ("sessions", "use_session", "scene", "network", "node", "problems", "geometry",
              "attrib", "compare", "viewport", "screenshot", "pane_screenshot")
_open = {"w": None}


# ============================================================================ CLI plumbing
def claude_exe():
    """The real claude.exe behind the npm shim (list args, no shell - a prompt passes verbatim)."""
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
        "(mcp__houdini-live__houdini_*) talk to THIS session%s: inspect it with them, and change it "
        "only when asked - one 'Brother:' undo group per change, never save the hip file. If "
        "houdini_sessions lists several sessions, call houdini_use_session with pid %d first. "
        "Prefer houdini_click_node / houdini_set_parm_shown so Plug sees the cursor work. Reply in "
        "the language Plug writes in (Thai -> Thai, refer to yourself as Brother)."
        % (hou.applicationVersionString(), os.getpid(), hou.hipFile.path(),
           (" via brother_link on port %d" % port) if port else " (brother_link is not running - "
           "tell Plug to use AI > Connect Brother to this session)", os.getpid()))


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
#panel { background: #141418; border: 1px solid #34343c; border-radius: 12px; }
#side { background: #101014; border-right: 1px solid #26262c;
        border-top-left-radius: 11px; border-bottom-left-radius: 11px; }
QLabel { color: #d8d8de; font-size: 12px; }
QLabel#title { color: #fff; font-size: 15px; font-weight: 700; }
QLabel#dim { color: #80808c; font-size: 11px; }
QPushButton { background: #24242a; color: #e6e6ea; border: 1px solid #36363e; border-radius: 6px;
              padding: 5px 10px; font-size: 12px; }
QPushButton:hover { border-color: #6a6a78; }
QPushButton#primary { background: #ffffff; color: #000; border-color: #fff; font-weight: 700; }
QPushButton#stop { background: #3a1016; color: #ff8a9a; border-color: #6a1a26; font-weight: 700; }
QPushButton#flat { background: transparent; border: none; color: #9a9aa6; padding: 3px 6px; }
QPushButton#flat:hover { color: #fff; }
QComboBox { background: #1c1c22; color: #e6e6ea; border: 1px solid #36363e; border-radius: 6px;
            padding: 3px 8px; font-size: 12px; }
QComboBox QAbstractItemView { background: #1c1c22; color: #e6e6ea; selection-background-color: #2e2e38; }
QListWidget { background: transparent; border: none; color: #c8c8d0; font-size: 12px; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; }
QListWidget::item:selected { background: #26262e; color: #fff; }
QListWidget::item:hover { background: #1c1c22; }
QPlainTextEdit#composer { background: #0d0d10; color: #fff; border: 1px solid #36363e; border-radius: 8px;
                          padding: 8px; font-size: 13px; }
QScrollArea { background: transparent; border: none; }
QTextBrowser { background: transparent; border: none; color: #e4e4ea; font-size: 13px; }
QFrame#user { background: #22222a; border-radius: 10px; }
QFrame#card { background: #18181e; border: 1px solid #2c2c34; border-radius: 8px; }
QFrame#perm { background: #1e1a10; border: 1px solid #6a5418; border-radius: 8px; }
QFrame#think { background: transparent; border-left: 2px solid #3a3a46; }
"""
MONO = "Consolas, 'Cascadia Mono', monospace"


class AutoText(QtWidgets.QTextBrowser):
    """A text block that grows to fit (markdown), with no scrollbar of its own."""
    def __init__(self, markdown="", color=None, mono=False, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(True)
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
            self.setMarkdown(text)
        self._fit()

    def append_text(self, delta):
        self.set_text(self._md + delta)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.document().setTextWidth(self.viewport().width())
        self._fit()

    def _fit(self, *_):
        self.setFixedHeight(int(self.document().size().height()) + 6)


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
        self.dot = QtWidgets.QLabel("●"); self.dot.setStyleSheet("color:#e6b422;")
        head.addWidget(self.dot)
        label = name.replace("mcp__houdini-live__", "houdini:").replace("mcp__", "")
        self.title = QtWidgets.QLabel("<b>%s</b>" % label)
        head.addWidget(self.title)
        self.summary = QtWidgets.QLabel(""); self.summary.setObjectName("dim")
        head.addWidget(self.summary, 1)
        self.toggle = QtWidgets.QPushButton("details", objectName="flat"); head.addWidget(self.toggle)
        self.body = QtWidgets.QWidget(); self.body.hide()
        bl = QtWidgets.QVBoxLayout(self.body); bl.setContentsMargins(0, 0, 0, 0); bl.setSpacing(4)
        self.input_view = AutoText(mono=True, color="#b8b8c4"); bl.addWidget(self.input_view)
        self.result_view = AutoText(mono=True, color="#9ad0a0"); self.result_view.hide(); bl.addWidget(self.result_view)
        lay.addWidget(self.body)
        self.extra = QtWidgets.QWidget()                      # diffs / todos show here, always open
        self.extra_lay = QtWidgets.QVBoxLayout(self.extra); self.extra_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.extra); self.extra.hide()
        self.toggle.clicked.connect(lambda: self.body.setVisible(not self.body.isVisible()))
        if depth:
            self.setStyleSheet("QFrame#card{margin-left:%dpx;}" % (18 * depth))

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
        self.result_view.setStyleSheet("color:%s;" % ("#ff9aa6" if is_error else "#9ad0a0"))
        self.result_view.show()
        self.dot.setStyleSheet("color:%s;" % ("#ff5a6a" if is_error else "#3ad07a"))


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
            self.setStyleSheet("QFrame#perm{border-color:#3a3a42;background:#16161a;}")


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
        self.button(row, "Allow", lambda: self.send(True, "Allowed once", tool_input=r.get("input")), True)
        sugg = r.get("permission_suggestions")
        if sugg:
            wheres = {x.get("destination") for x in sugg if isinstance(x, dict)}
            where = " / ".join(SUGG_WHERE.get(w, w) for w in wheres if w) or "this session"
            b = self.button(row, "Always allow", lambda: self.send(True, "Always allowed - " + where,
                                                                   tool_input=r.get("input"), permissions=sugg))
            b.setToolTip("Remembered for: " + where)
        self.button(row, "Deny", lambda: self.send(False, "Denied", message=self.fb.text().strip()))
        self.fb = QtWidgets.QLineEdit(); self.fb.setPlaceholderText("or tell Brother what to do instead, then Deny")
        self.fb.setStyleSheet("background:#0d0d10;color:#ddd;border:1px solid #36363e;border-radius:6px;padding:4px;")
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
            t = QtWidgets.QLabel(("<span style='color:#ffb84d'>%s</span>  " % _esc(head) if head else "") + _esc(q.get("question", "")))
            t.setWordWrap(True); bl.addWidget(t)
            group = QtWidgets.QButtonGroup(box); group.setExclusive(not q.get("multiSelect"))
            opts = []
            for o in q.get("options") or []:
                w = (QtWidgets.QCheckBox if q.get("multiSelect") else QtWidgets.QRadioButton)(o.get("label", ""))
                w.setStyleSheet("color:#e6e6ea;")
                if o.get("description"):
                    w.setToolTip(o["description"])
                group.addButton(w); bl.addWidget(w); opts.append(w)
                if o.get("description"):
                    dl = QtWidgets.QLabel(_esc(o["description"])); dl.setObjectName("dim"); dl.setWordWrap(True)
                    dl.setContentsMargins(22, 0, 0, 0); bl.addWidget(dl)
            other = QtWidgets.QLineEdit(); other.setPlaceholderText("Other...")
            other.setStyleSheet("background:#0d0d10;color:#ddd;border:1px solid #36363e;border-radius:6px;padding:4px;")
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
        self.fb.setStyleSheet("background:#0d0d10;color:#ddd;border:1px solid #36363e;border-radius:6px;padding:4px;")
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
        self.setFixedHeight(84)
        self.images = []                                        # [(media_type, base64)]

    def keyPressEvent(self, e):
        if e.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not (e.modifiers() & QtCore.Qt.ShiftModifier):
            self.submit.emit(); return
        if e.key() == QtCore.Qt.Key_Escape:
            self.escape.emit(); return
        if e.key() == QtCore.Qt.Key_Backspace and not self.toPlainText() and self.images:
            self.images = []; self.parent_panel().refresh_chips(); return
        super().keyPressEvent(e)

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
        self.scroll = QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        host = QtWidgets.QWidget(); host.setStyleSheet("background:transparent;")
        self.feed = QtWidgets.QVBoxLayout(host); self.feed.setContentsMargins(0, 0, 6, 0); self.feed.setSpacing(8)
        self.feed.addStretch(1)
        self.scroll.setWidget(host)
        sb = self.scroll.verticalScrollBar()
        sb.rangeChanged.connect(lambda _a, mx: self.follow and sb.setValue(mx))
        sb.valueChanged.connect(lambda v: setattr(self, "follow", v >= sb.maximum() - 30))

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
            self.add_note(str(e), "#ff8a9a")

    def park(self):
        """Leaving an idle conversation: end its process (it resumes on the next message).
        Never while a turn, a question or a background task is still going."""
        if self.session is not None and not self.working:
            self.session.stop()

    def send(self, text, imgs):
        self.start()
        self.add_user(text, len(imgs))
        if self.session.send(text, imgs):
            self.has_history = True
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
        self.feed.insertWidget(self.feed.count() - 1, w)
        return w

    def add_note(self, text, color="#80808c"):
        l = QtWidgets.QLabel(text); l.setWordWrap(True); l.setStyleSheet("color:%s;font-size:11px;" % color)
        return self._add(l)

    def add_user(self, text, n_images=0, uuid_=None):
        f = QtWidgets.QFrame(objectName="user")
        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(12, 8, 12, 4); lay.setSpacing(0)
        lay.addWidget(AutoText(text + (("\n\n*+%d image(s)*" % n_images) if n_images else ""), color="#ffffff"))
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
        return self._add(f)

    def add_text(self, text="", depth=0):
        t = AutoText(text, color="#b8b8c8" if depth else None)
        if depth:
            t.setStyleSheet("color:#b8b8c8;border-left:2px solid #34343e;padding-left:6px;margin-left:%dpx;" % (18 * depth))
        self.cur_text = self._add(t)
        return t

    def add_think(self, depth=0):
        """Thinking, folded to one line like Claude Code; click to read it."""
        f = QtWidgets.QFrame(objectName="think")
        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(10 + 18 * depth, 0, 0, 0); lay.setSpacing(2)
        b = QtWidgets.QPushButton("Thinking...", objectName="flat")
        b.setStyleSheet("text-align:left;font-style:italic;")
        lay.addWidget(b, 0, QtCore.Qt.AlignLeft)
        t = AutoText("", color="#7a7a88"); t.hide(); lay.addWidget(t)
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
                self.add_note("Compact failed: %s" % o["compact_error"], "#ff8a9a")
        elif st == "compact_boundary":
            m = o.get("compact_metadata") or {}
            self.add_note("──  Conversation compacted (%s, was %s tokens)  ──" % (
                m.get("trigger", "?"), _k(m.get("pre_tokens") or 0)), "#9a9aff")
            self.ask_context()
        elif st == "api_retry":
            self.add_note("API busy - retry %s/%s in %.0fs (%s)" % (
                o.get("attempt"), o.get("max_retries"), (o.get("retry_delay_ms") or 0) / 1000.0,
                o.get("error_status") or o.get("error") or ""), "#ffb84d")
        elif st == "notification" and o.get("text"):
            self.add_note(o["text"], "#ffb84d")
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
                self.add_note("Could not switch to %s: %s" % (what[1], r.get("error")), "#ff8a9a")
            elif what[0] == "model":
                self.add_note("Could not switch model: %s" % r.get("error"), "#ff8a9a")
            else:
                self.add_note("%s failed: %s" % (what[0].rstrip("?"), r.get("error")), "#ff8a9a")
            self.panel.convo_changed(self)             # the menus fall back to the real state
            return
        body = r.get("response") or {}
        if what[0] == "rewind?":
            b = getattr(self, "pending_rewind", None)
            files = body.get("filesChanged") or []
            if not body.get("canRewind") or not files:
                self.add_note("Nothing to rewind from that message%s." % (
                    (" (%s)" % body["error"]) if body.get("error") else ""), "#ffb84d")
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
                          else "Rewind failed: %s" % body.get("error"), "#9a9aff")
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
            st = self.streams.get(o.get("parent_tool_use_id"))
            if st:
                st["text"] = None
        elif t == "control_request":
            req = o.get("request") or {}
            if req.get("subtype") == "can_use_tool":
                card = make_card(o, self._answer)
                self.asks[o.get("request_id")] = card
                self._add(card)
            else:                                        # elicitation, hooks, ...: answer, never hang
                self.session.refuse(o.get("request_id"), "not supported by the Houdini chat panel")
                self.add_note("Claude asked for '%s', which this panel can't show yet - declined." % req.get("subtype"),
                              "#ffb84d")
            self.panel.convo_changed(self)
        elif t == "result":
            u = o.get("usage") or {}
            tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                      + u.get("cache_creation_input_tokens", 0))
            if o.get("is_error"):
                why = "; ".join(str(e) for e in (o.get("errors") or [])) or o.get("result") or o.get("subtype")
                if o.get("api_error_status"):
                    why = "%s (HTTP %s)" % (why, o["api_error_status"])
                self.add_note("error: %s" % why, "#ff8a9a")
            else:
                self.add_note("done  %.1fs   %s in / %s out" % ((o.get("duration_ms") or 0) / 1000.0,
                                                               _k(tokens), _k(u.get("output_tokens", 0))))
            self.cur_text = self.cur_think = self.cur_tool = None
            self.streams = {}
            self._expire_asks()
            self.ask_context()
            self.panel.convo_changed(self, finished=True)

    def on_ended(self, code, err):
        self._expire_asks("Expired - claude stopped")
        self.tasks = {}
        if code not in (0, None) and err.strip():
            self.add_note("claude exited (%s): %s" % (code, err.strip()[-600:]), "#ff8a9a")
        self.panel.convo_changed(self)


SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ChatPanel(QtWidgets.QWidget):
    def __init__(self, main):
        super().__init__(main, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.main = main
        self.cwd = REPO
        self.convos = []                     # every conversation opened in this Houdini
        self.cur = None
        self._spin = 0
        self.setStyleSheet(CSS)
        self._build()
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

        side = QtWidgets.QFrame(objectName="side"); side.setFixedWidth(230); root.addWidget(side)
        sl = QtWidgets.QVBoxLayout(side); sl.setContentsMargins(10, 12, 10, 10); sl.setSpacing(8)
        t = QtWidgets.QLabel("Brother", objectName="title"); sl.addWidget(t)
        nb = QtWidgets.QPushButton("+  New session", objectName="primary"); nb.clicked.connect(self.new_session)
        sl.addWidget(nb)
        sl.addWidget(QtWidgets.QLabel("HISTORY", objectName="dim"))
        self.list = QtWidgets.QListWidget(); self.list.itemClicked.connect(self._pick_session)
        self.list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._history_menu)
        self.list.setToolTip("Right-click a session to rename or fork it")
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(QtCore.Qt.ElideRight)
        sl.addWidget(self.list, 1)
        self.cwd_label = QtWidgets.QLabel("cwd  %s" % self.cwd, objectName="dim"); self.cwd_label.setWordWrap(True)
        sl.addWidget(self.cwd_label)

        main = QtWidgets.QVBoxLayout(); main.setContentsMargins(14, 10, 14, 12); main.setSpacing(8)
        root.addLayout(main, 1)
        head = QtWidgets.QHBoxLayout(); main.addLayout(head)
        self.head_title = QtWidgets.QLabel("New session", objectName="title"); head.addWidget(self.head_title, 1)
        self.model_box = QtWidgets.QComboBox()
        for label, v in MODELS:
            self.model_box.addItem(label, v)
        self.model_box.currentIndexChanged.connect(self._model_changed)
        head.addWidget(self.model_box)
        self.effort_box = QtWidgets.QComboBox()
        self.effort_box.setToolTip("How hard the model thinks (effort)")
        self.effort_box.addItem("effort: auto", None)
        for e in ("low", "medium", "high", "xhigh", "max"):
            self.effort_box.addItem("effort: " + e, e)
        self.effort_box.currentIndexChanged.connect(self._effort_changed)
        head.addWidget(self.effort_box)
        self.mode_box = QtWidgets.QComboBox()
        for label, v in MODES:
            self.mode_box.addItem(label, v)
        self.mode_box.currentIndexChanged.connect(self._mode_changed)
        head.addWidget(self.mode_box)
        self.cost = QtWidgets.QLabel("", objectName="dim"); head.addWidget(self.cost)
        hide = QtWidgets.QPushButton("Hide", objectName="flat"); hide.clicked.connect(self.hide)
        head.addWidget(hide)

        self.limit_bar = QtWidgets.QLabel(); self.limit_bar.setWordWrap(True); self.limit_bar.hide()
        self.limit_bar.setStyleSheet("background:#2a2010;color:#ffcf7a;border:1px solid #6a5418;"
                                     "border-radius:6px;padding:5px 8px;font-size:12px;")
        main.addWidget(self.limit_bar)

        self.stack = QtWidgets.QStackedWidget()
        main.addWidget(self.stack, 1)

        self.chips = QtWidgets.QLabel(objectName="dim"); main.addWidget(self.chips); self.chips.hide()
        self.composer = Composer()
        self.composer.submit.connect(self.send)
        self.composer.escape.connect(self.interrupt)
        self.composer.textChanged.connect(self._slash_popup)
        main.addWidget(self.composer)
        row = QtWidgets.QHBoxLayout(); main.addLayout(row)
        for text, fn in (("Attach image", self.attach_image), ("Viewport", self.attach_viewport),
                         ("Selected nodes", self.attach_selection)):
            b = QtWidgets.QPushButton(text, objectName="flat"); b.clicked.connect(fn); row.addWidget(b)
        row.addStretch(1)
        self.status = QtWidgets.QLabel(objectName="dim"); row.addWidget(self.status)
        self.stop_btn = QtWidgets.QPushButton("Stop", objectName="stop"); self.stop_btn.clicked.connect(self.interrupt)
        self.stop_btn.hide(); row.addWidget(self.stop_btn)
        self.send_btn = QtWidgets.QPushButton("Send", objectName="primary"); self.send_btn.clicked.connect(self.send)
        row.addWidget(self.send_btn)
        grip = QtWidgets.QSizeGrip(self); row.addWidget(grip, 0, QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight)

        self.slash = QtWidgets.QListWidget(self)
        self.slash.setWindowFlags(QtCore.Qt.ToolTip)
        self.slash.setStyleSheet("QListWidget{background:#1c1c22;border:1px solid #36363e;color:#ddd;font-size:12px;}")
        self.slash.itemClicked.connect(self._slash_pick)
        self._drag = None

    # frameless: drag by the header
    def mousePressEvent(self, e):
        if e.position().y() < 48:
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
        self.stack.setCurrentWidget(c.scroll)
        self.convo_changed(c)
        self.refresh_sessions()
        self.composer.setFocus()

    def new_session(self):
        # reuse an untouched new session instead of stacking empty ones
        for c in self.convos:
            if c.title == "New session" and not c.working and c.feed.count() <= 3 and c.mode == "default":
                self._show(c); return
        c = Convo(self, model=self.model_box.currentData())
        self.convos.append(c)
        c.add_note("New session in %s - Brother can see and drive this Houdini." % self.cwd)
        c.start()
        self._show(c)

    def _pick_session(self, item):
        sid = item.data(QtCore.Qt.UserRole)
        c = self._convo_for(sid)
        if c is None:                               # first time opened this Houdini: replay + resume
            c = Convo(self, resume=sid, title=item.data(QtCore.Qt.UserRole + 1) or "Session",
                      model=self.model_box.currentData())
            self.convos.append(c)
            c.load(sid)
            c.start()
        self._show(c)

    def set_models(self, models):
        """The model menu comes from the CLI's own list (initialize), not a hardcoded one."""
        if not models or getattr(self, "_models_from_cli", False):
            return
        self._models_from_cli = True
        self.models = {(m.get("value") if m.get("value") != "default" else None): m for m in models}
        cur = self.cur.model if self.cur else None
        self.model_box.blockSignals(True)
        self.model_box.clear()
        for m in models:
            v = m.get("value")
            self.model_box.addItem(m.get("displayName") or v, None if v == "default" else v)
            self.model_box.setItemData(self.model_box.count() - 1, m.get("description") or "", QtCore.Qt.ToolTipRole)
        if self.model_box.findData(cur) < 0 and cur:
            self.model_box.addItem(cur, cur)
        self.model_box.blockSignals(False)
        self._set_combo(self.model_box, cur)
        self._sync_effort()

    def _sync_effort(self):
        """Only the effort levels the on-screen model supports."""
        c = self.cur
        m = getattr(self, "models", {}).get(c.model if c else None)
        levels = m.get("supportedEffortLevels") if m else None
        ok = bool(m.get("supportsEffort")) if m else True
        for i in range(1, self.effort_box.count()):
            v = self.effort_box.itemData(i)
            item = self.effort_box.model().item(i)
            item.setEnabled(ok and (levels is None or v in levels))
        self.effort_box.setEnabled(ok)
        self._set_combo(self.effort_box, c.effort if c else None)

    def _effort_changed(self):
        if self.cur is not None:
            self.cur.set_effort(self.effort_box.currentData())

    def _history_menu(self, pos):
        it = self.list.itemAt(pos)
        if it is None:
            return
        sid, title = it.data(QtCore.Qt.UserRole), it.data(QtCore.Qt.UserRole + 1)
        m = QtWidgets.QMenu(self)
        m.setStyleSheet("QMenu{background:#1c1c22;color:#e6e6ea;border:1px solid #36363e;}"
                        "QMenu::item:selected{background:#2e2e38;}")
        ren = m.addAction("Rename...")
        fork = m.addAction("Fork - continue in a copy")
        got = m.exec(self.list.mapToGlobal(pos))
        if got is ren:
            new, ok = QtWidgets.QInputDialog.getText(self, "Rename session", "Title:", text=title)
            if ok and new.strip():
                c = self._convo_for(sid)
                if c is None:
                    c = Convo(self, resume=sid, title=title, model=self.model_box.currentData())
                    self.convos.append(c); c.load(sid)
                c.rename(new.strip())
                self._show(c)
        elif got is fork:
            c = Convo(self, resume=sid, title="Fork of " + (title or "session"), model=self.model_box.currentData(),
                      fork=True)
            self.convos.append(c)
            c.load(sid)
            c.add_note("Forked - this is a new session; the original is untouched.", "#9a9aff")
            c.start()
            self._show(c)

    @staticmethod
    def _set_combo(box, value):
        i = box.findData(value)
        if i >= 0 and i != box.currentIndex():
            box.blockSignals(True)
            box.setCurrentIndex(i)
            box.blockSignals(False)

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
        # the menus always show the on-screen conversation's REAL model and mode
        self._set_combo(self.model_box, c.model)
        self._set_combo(self.mode_box, c.mode)
        self._sync_effort()
        self.stop_btn.setVisible(c.busy)
        self.send_btn.setText("Queue" if c.busy else "Send")
        if c.context:
            used, mx = c.context
            pct = 100.0 * used / mx
            self.cost.setText("context %d%%" % round(pct))
            self.cost.setStyleSheet("color:%s;font-size:11px;" % ("#ff8a9a" if pct > 85 else "#ffb84d" if pct > 65 else "#80808c"))
            self.cost.setToolTip("%s of %s tokens in the context window%s" % (
                _k(used), _k(mx), "\nClaude will compact soon - or type /compact" if pct > 65 else ""))
        else:
            self.cost.setText("")
        bits = [c.model or "default model", dict((v, l) for l, v in MODES).get(c.mode, c.mode)]
        if c.tasks:
            bits.append("%d background task%s" % (len(c.tasks), "s" if len(c.tasks) > 1 else ""))
        self.status.setText("   ".join(bits))
        self.status.setToolTip("\n".join(c.tasks.values()))

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
        self.list.clear()
        for sid, title, mtime in live + rows:
            c = self._convo_for(sid)
            mark = ""
            if c is not None and c.waiting:
                mark = "?  "
            elif c is not None and c.working:
                mark = SPIN[self._spin % len(SPIN)] + "  "
            it = QtWidgets.QListWidgetItem("%s%s\n%s" % (mark, title, datetime.datetime.fromtimestamp(mtime).strftime("%d %b %H:%M")))
            it.setData(QtCore.Qt.UserRole, sid)
            it.setData(QtCore.Qt.UserRole + 1, title)
            it.setData(QtCore.Qt.UserRole + 2, "wait" if mark.startswith("?") else "spin" if mark else "")
            it.setToolTip(("Waiting for your answer - " if mark.startswith("?") else
                           "Working... - " if mark else "") + sid)
            if mark.startswith("?"):
                it.setForeground(QtGui.QColor("#ffb84d"))
            elif mark:
                it.setForeground(QtGui.QColor("#ff4f9a"))
            self.list.addItem(it)
            if sid == sel:
                it.setSelected(True)

    def _tick(self):
        """Spin the marks on working conversations."""
        if not any(c.working for c in self.convos):
            return
        self._spin += 1
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(QtCore.Qt.UserRole + 2) == "spin":
                lines = it.text().split("\n", 1)
                lines[0] = SPIN[self._spin % len(SPIN)] + lines[0][1:]
                it.setText("\n".join(lines))

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
        self.cur.send(text, imgs)
        self.composer.clear(); self.composer.images = []; self.refresh_chips()
        QtCore.QTimer.singleShot(1500, self.refresh_sessions)     # the transcript file appears on disk

    def interrupt(self):
        if self.cur is not None and self.cur.busy:
            self.session.control("interrupt")
            self.cur._expire_asks("Cancelled - you stopped the turn")
            self.cur.add_note("Stopped.", "#ff8a9a")
            self.convo_changed(self.cur)

    def _model_changed(self):
        if self.cur is not None:
            self.cur.set_model(self.model_box.currentData())
            if self.cur.effort and self.cur.effort not in (
                    (getattr(self, "models", {}).get(self.cur.model) or {}).get("supportedEffortLevels") or [self.cur.effort]):
                self.cur.effort = None           # the new model can't do that effort level
            self.convo_changed(self.cur)

    def _mode_changed(self):
        if self.cur is not None:
            self.cur.set_mode(self.mode_box.currentData())
            self.convo_changed(self.cur)          # shows the real mode until the switch is confirmed

    def add_note(self, text, color="#80808c"):
        return self.cur.add_note(text, color)

    # ---------------------------------------------------------------- attachments
    def refresh_chips(self):
        n = len(self.composer.images)
        self.chips.setText("%d image(s) attached - Backspace in an empty box clears them" % n if n else "")
        self.chips.setVisible(bool(n))

    def attach_image(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Attach images", "", "Images (*.png *.jpg *.jpeg *.webp *.gif)")
        for p in paths:
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            mt = "image/jpeg" if ext in ("jpg", "jpeg") else "image/%s" % ext
            with open(p, "rb") as fh:
                self.composer.images.append((mt, base64.b64encode(fh.read()).decode()))
        self.refresh_chips()

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
            self.add_note("Viewport capture failed: %s (open a Scene View tab)" % e, "#ff8a9a")

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
            brother_link.start()
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
