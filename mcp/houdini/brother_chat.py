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
        rows.append((sid, (title or "(empty session)").splitlines()[0][:80], os.path.getmtime(path)))
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
                            events.append(("user", c))
                    else:
                        for b in c or []:
                            if b.get("type") == "text" and not b.get("text", "").startswith("<"):
                                events.append(("user", b["text"]))
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

    def __init__(self, cwd, resume=None, model=None, mode="default", parent=None):
        super().__init__(parent)
        self.cwd, self.resume, self.model, self.mode = cwd, resume, model, mode
        self.session_id = resume or str(uuid.uuid4())
        self.proc = None
        self.buf = b""
        self.commands = []
        self.busy = False
        self._err = b""

    def start(self):
        exe = claude_exe()
        if not exe:
            raise RuntimeError("claude CLI not found - install Claude Code (npm i -g @anthropic-ai/claude-code)")
        args = ["-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                "--include-partial-messages", "--permission-prompt-tool", "stdio",
                "--permission-mode", self.mode, "--append-system-prompt", houdini_context()]
        args += ["--resume", self.resume] if self.resume else ["--session-id", self.session_id]
        if self.model:
            args += ["--model", self.model]
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
        p.setProcessEnvironment(claude_env())
        p.readyReadStandardOutput.connect(self._read)
        p.readyReadStandardError.connect(lambda: setattr(self, "_err", (self._err + bytes(p.readAllStandardError()))[-4000:]))
        p.finished.connect(self._finished)
        p.start()
        self.proc = p
        self.control("initialize", hooks=None)           # answers with the slash-command list

    def _finished(self, code, _status=None):
        # a bound method, not a lambda: Qt drops it with the object, so a process that exits after
        # its session was deleted can no longer call into a dead C++ object
        self.busy = False
        try:
            self.ended.emit(code, self._err.decode("utf8", "replace"))
        except RuntimeError:
            pass

    def _write(self, obj):
        if self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning:
            self.proc.write((json.dumps(obj) + "\n").encode("utf8"))

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
        self.busy = True
        self._write({"type": "user", "message": {"role": "user", "content": content}})

    def answer_permission(self, request_id, allow, tool_input=None, message="", permissions=None):
        if allow:
            resp = {"behavior": "allow", "updatedInput": tool_input or {}}
            if permissions:
                resp["updatedPermissions"] = permissions
        else:
            resp = {"behavior": "deny", "message": message or "Plug denied this in the Houdini chat panel."}
        self._write({"type": "control_response", "response": {"subtype": "success",
                                                              "request_id": request_id, "response": resp}})

    def _read(self):
        self.buf += bytes(self.proc.readAllStandardOutput())
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
            if o.get("type") == "result":
                self.busy = False
            self.event.emit(o)

    def running(self):
        try:
            return self.proc is not None and self.proc.state() != QtCore.QProcess.NotRunning
        except RuntimeError:
            return False

    def stop(self):
        if self.running():
            try:
                self.proc.finished.disconnect(self._finished)
            except (RuntimeError, TypeError):
                pass
            try:
                self.proc.closeWriteChannel()
                if not self.proc.waitForFinished(1500):
                    self.proc.kill()
            except RuntimeError:
                pass


# ============================================================================ widgets
CSS = """
#panel { background: #141418; border: 1px solid #34343c; border-radius: 12px; }
#side { background: #101014; border-right: 1px solid #26262c; }
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
            "Bash": "command", "Glob": "pattern", "Grep": "pattern", "WebFetch": "url",
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

    def _extra_html(self, html):
        t = QtWidgets.QTextBrowser(); t.setHtml(html)
        t.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        t.document().documentLayout().documentSizeChanged.connect(
            lambda s, t=t: t.setFixedHeight(min(320, int(s.height()) + 6)))
        self.extra_lay.addWidget(t); self.extra.show()

    def set_result(self, content, is_error):
        text = _text_of(content) if not isinstance(content, str) else content
        self.result_view.set_text(text[:6000] + ("\n..." if len(text) > 6000 else ""))
        self.result_view.setStyleSheet("color:%s;" % ("#ff9aa6" if is_error else "#9ad0a0"))
        self.result_view.show()
        self.dot.setStyleSheet("color:%s;" % ("#ff5a6a" if is_error else "#3ad07a"))


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class PermissionCard(QtWidgets.QFrame):
    def __init__(self, req, answer, parent=None):
        super().__init__(parent)
        self.setObjectName("perm")
        r = req["request"]
        lay = QtWidgets.QVBoxLayout(self); lay.setContentsMargins(12, 10, 12, 10); lay.setSpacing(6)
        name = r.get("display_name") or r.get("tool_name")
        lay.addWidget(QtWidgets.QLabel("<b>Brother wants to use %s</b>" % _esc(name)))
        desc = r.get("description") or _short(r.get("input"), 200)
        d = QtWidgets.QLabel(_esc(desc)); d.setWordWrap(True); d.setObjectName("dim"); lay.addWidget(d)
        row = QtWidgets.QHBoxLayout(); lay.addLayout(row)
        self.buttons = []

        def done(text):
            for b in self.buttons:
                b.setEnabled(False)
            note = QtWidgets.QLabel(text); note.setObjectName("dim"); lay.addWidget(note)

        yes = QtWidgets.QPushButton("Allow", objectName="primary")
        yes.clicked.connect(lambda: (answer(req["request_id"], True, r.get("input")), done("Allowed once")))
        row.addWidget(yes); self.buttons.append(yes)
        sugg = r.get("permission_suggestions")
        if sugg:
            always = QtWidgets.QPushButton("Allow for this session")
            always.clicked.connect(lambda: (answer(req["request_id"], True, r.get("input"), permissions=sugg),
                                            done("Allowed for this session")))
            row.addWidget(always); self.buttons.append(always)
        no = QtWidgets.QPushButton("Deny")
        no.clicked.connect(lambda: (answer(req["request_id"], False), done("Denied")))
        row.addWidget(no); self.buttons.append(no)
        row.addStretch(1)


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
    """One conversation: its own claude process and its own feed. Several can run at once;
    the panel only decides which one is on screen."""

    def __init__(self, panel, resume=None, title="New session"):
        super().__init__(panel)
        self.panel = panel
        self.title = title
        self.session = None
        self.sid = resume
        self.cards = {}
        self.cur_text = self.cur_think = self.cur_tool = None
        self.total_cost = 0.0
        self.tokens = 0
        self.api_source = None            # "none" = signed in with the subscription, not an API key
        self.waiting = False              # a permission question is open
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

    # ---------------------------------------------------------------- process
    @property
    def busy(self):
        return bool(self.session is not None and self.session.busy)

    def start(self):
        if self.session is not None and self.session.running():
            return
        old = self.session
        self.session = ClaudeSession(self.panel.cwd, self.sid, self.panel.model_box.currentData(),
                                     self.panel.mode_box.currentData(), self)
        self.session.event.connect(self.on_event)
        self.session.ended.connect(self.on_ended)
        if old is not None:
            old.deleteLater()
        _ensure_link()
        try:
            self.session.start()
            self.sid = self.session.session_id
        except RuntimeError as e:
            self.add_note(str(e), "#ff8a9a")

    def park(self):
        """Leaving an idle conversation: end its process (it resumes on the next message)."""
        if self.session is not None and not self.session.busy and not self.waiting:
            self.session.stop()

    def send(self, text, imgs):
        self.start()
        self.add_user(text, len(imgs))
        self.session.send(text, imgs)
        self.follow = True
        self.panel.convo_changed(self)

    # ---------------------------------------------------------------- feed
    def _add(self, w):
        self.feed.insertWidget(self.feed.count() - 1, w)
        return w

    def add_note(self, text, color="#80808c"):
        l = QtWidgets.QLabel(text); l.setWordWrap(True); l.setStyleSheet("color:%s;font-size:11px;" % color)
        return self._add(l)

    def add_user(self, text, n_images=0):
        f = QtWidgets.QFrame(objectName="user")
        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(12, 8, 12, 8)
        lay.addWidget(AutoText(text + (("\n\n*+%d image(s)*" % n_images) if n_images else ""), color="#ffffff"))
        self.cur_text = None
        return self._add(f)

    def add_text(self, text=""):
        self.cur_text = self._add(AutoText(text))
        return self.cur_text

    def add_think(self):
        """Thinking, folded to one line like Claude Code; click to read it."""
        f = QtWidgets.QFrame(objectName="think")
        lay = QtWidgets.QVBoxLayout(f); lay.setContentsMargins(10, 0, 0, 0); lay.setSpacing(2)
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
                self.add_user(v)
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
        self.waiting = False
        self.session.answer_permission(*a, **kw)
        self.panel.convo_changed(self)

    def on_event(self, o):
        t = o.get("type")
        depth = 1 if o.get("parent_tool_use_id") else 0
        if t == "system" and o.get("subtype") == "init":
            self.sid = o.get("session_id") or self.sid
            self.api_source = o.get("apiKeySource")
            mcp = ", ".join("%s %s" % (m.get("name"), m.get("status")) for m in o.get("mcp_servers") or [])
            self.add_note("claude %s  model %s  %s  mcp: %s" % (
                o.get("claude_code_version", ""), o.get("model"),
                "subscription" if self.api_source == "none" else "api key (%s)" % self.api_source, mcp or "none"))
            self.panel.convo_changed(self)
        elif t == "stream_event":
            ev = o.get("event") or {}
            et = ev.get("type")
            if et == "content_block_start":
                cb = ev.get("content_block") or {}
                if cb.get("type") == "text":
                    self.add_text("")
                elif cb.get("type") == "thinking":
                    self.add_think()
                elif cb.get("type") == "tool_use":
                    self.cur_tool = self.add_tool(cb.get("name", "?"), cb.get("id"), depth)
            elif et == "content_block_delta":
                d = ev.get("delta") or {}
                if d.get("type") == "text_delta":
                    (self.cur_text or self.add_text("")).append_text(d.get("text", ""))
                elif d.get("type") == "thinking_delta":
                    (self.cur_think or self.add_think()).append_text(d.get("thinking", ""))
                elif d.get("type") == "input_json_delta" and self.cur_tool is not None:
                    self.cur_tool.add_partial(d.get("partial_json", ""))
            elif et == "message_start":
                self.cur_think = None
        elif t == "assistant":
            for b in (o.get("message") or {}).get("content") or []:
                if b.get("type") == "tool_use":
                    c = self.cards.get(b.get("id")) or self.add_tool(b.get("name", "?"), b.get("id"), depth)
                    c.set_input(b.get("input"))
                elif b.get("type") == "text" and self.cur_text is None and b.get("text"):
                    self.add_text(b["text"])          # no partials came (e.g. a subagent) - show whole
        elif t == "user":
            for b in (o.get("message") or {}).get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = self.cards.get(b.get("tool_use_id"))
                    if c:
                        c.set_result(b.get("content"), b.get("is_error"))
            self.cur_text = None
        elif t == "control_request" and (o.get("request") or {}).get("subtype") == "can_use_tool":
            self.waiting = True
            self._add(PermissionCard(o, self._answer))
            self.panel.convo_changed(self)
        elif t == "result":
            self.total_cost = o.get("total_cost_usd") or self.total_cost
            u = o.get("usage") or {}
            tokens = (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                      + u.get("cache_creation_input_tokens", 0))
            self.tokens += tokens + u.get("output_tokens", 0)
            self.add_note("%s  %.1fs   %s in / %s out" % ("done" if not o.get("is_error") else "error: %s" % o.get("result"),
                                                         (o.get("duration_ms") or 0) / 1000.0,
                                                         _k(tokens), _k(u.get("output_tokens", 0))),
                          "#80808c" if not o.get("is_error") else "#ff8a9a")
            self.cur_text = self.cur_think = self.cur_tool = None
            self.waiting = False
            self.panel.convo_changed(self, finished=True)

    def on_ended(self, code, err):
        self.waiting = False
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
        root = QtWidgets.QHBoxLayout(panel); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        side = QtWidgets.QFrame(objectName="side"); side.setFixedWidth(230); root.addWidget(side)
        sl = QtWidgets.QVBoxLayout(side); sl.setContentsMargins(10, 12, 10, 10); sl.setSpacing(8)
        t = QtWidgets.QLabel("Brother", objectName="title"); sl.addWidget(t)
        nb = QtWidgets.QPushButton("+  New session", objectName="primary"); nb.clicked.connect(self.new_session)
        sl.addWidget(nb)
        sl.addWidget(QtWidgets.QLabel("HISTORY", objectName="dim"))
        self.list = QtWidgets.QListWidget(); self.list.itemClicked.connect(self._pick_session)
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
        self.mode_box = QtWidgets.QComboBox()
        for label, v in MODES:
            self.mode_box.addItem(label, v)
        self.mode_box.currentIndexChanged.connect(self._mode_changed)
        head.addWidget(self.mode_box)
        self.cost = QtWidgets.QLabel("", objectName="dim"); head.addWidget(self.cost)
        hide = QtWidgets.QPushButton("Hide", objectName="flat"); hide.clicked.connect(self.hide)
        head.addWidget(hide)

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
            if sid and c.sid == sid:
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
            if c.title == "New session" and not c.busy and c.feed.count() <= 3:
                self._show(c); return
        c = Convo(self)
        self.convos.append(c)
        c.add_note("New session in %s - Brother can see and drive this Houdini." % self.cwd)
        c.start()
        self._show(c)

    def _pick_session(self, item):
        sid = item.data(QtCore.Qt.UserRole)
        c = self._convo_for(sid)
        if c is None:                               # first time opened this Houdini: replay + resume
            c = Convo(self, resume=sid, title=item.data(QtCore.Qt.UserRole + 1) or "Session")
            self.convos.append(c)
            c.load(sid)
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
        self.stop_btn.setVisible(c.busy)
        self.send_btn.setText("Queue" if c.busy else "Send")
        # token count only - no dollar figure (the plan is not billed per call)
        self.cost.setText("%s tok" % _k(c.tokens) if c.tokens else "")
        self.cost.setToolTip("Tokens used in this session" + (" - on your Claude plan" if c.api_source == "none" else ""))
        if c.session is not None and c.session.model:
            self.status.setText("%s  %s" % (c.session.model or "default", self.mode_box.currentData()))

    def refresh_sessions(self):
        sel = self.cur.sid if self.cur is not None else None
        rows = list_sessions(self.cwd)
        on_disk = {sid for sid, _t, _m in rows}
        # live conversations not written to disk yet go on top
        live = [(c.sid, c.title, time.time()) for c in self.convos if c.sid and c.sid not in on_disk and c.busy]
        self.list.clear()
        for sid, title, mtime in live + rows:
            c = self._convo_for(sid)
            mark = ""
            if c is not None and c.waiting:
                mark = "?  "
            elif c is not None and c.busy:
                mark = SPIN[self._spin % len(SPIN)] + "  "
            it = QtWidgets.QListWidgetItem("%s%s\n%s" % (mark, title, datetime.datetime.fromtimestamp(mtime).strftime("%d %b %H:%M")))
            it.setData(QtCore.Qt.UserRole, sid)
            it.setData(QtCore.Qt.UserRole + 1, title)
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
        if not any(c.busy for c in self.convos):
            return
        self._spin += 1
        for i in range(self.list.count()):
            it = self.list.item(i)
            c = self._convo_for(it.data(QtCore.Qt.UserRole))
            if c is not None and c.busy and not c.waiting:
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
            self.cur.start(); self.session.control("set_model", model=m); self.cur.add_note("model -> %s" % m)
            self.composer.clear(); return
        imgs = list(self.composer.images)
        self.cur.send(text, imgs)
        self.composer.clear(); self.composer.images = []; self.refresh_chips()
        QtCore.QTimer.singleShot(1500, self.refresh_sessions)     # the transcript file appears on disk

    def interrupt(self):
        if self.cur is not None and self.cur.busy:
            self.session.control("interrupt")
            self.cur.add_note("Stopped.", "#ff8a9a")

    def _model_changed(self):
        if self.session is not None and self.session.running():
            self.session.control("set_model", model=self.model_box.currentData() or "default")

    def _mode_changed(self):
        if self.session is not None and self.session.running():
            self.session.control("set_permission_mode", mode=self.mode_box.currentData())
            self.status.setText("mode: %s" % self.mode_box.currentText())

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
