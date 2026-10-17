"""FX AI chat - several Claude accounts (brother_accounts), driven offscreen with a FAKE claude.

  hython tests/test_chat_accounts.py        (sets QT_QPA_PLATFORM=offscreen itself)

Never starts the CLI, never touches a live Houdini or the real ~/.houdini_brother/accounts.json:
the store, the chat state and the transcripts all go to a temp folder.
"""
import os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mcp", "houdini"))
from PySide6 import QtWidgets, QtCore
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import brother_accounts as ACC
import brother_chat as bc

TMP = tempfile.mkdtemp(prefix="fxai_acct_test_")
ACC.HOME = TMP
ACC.FILE = os.path.join(TMP, "accounts.json")
bc.STATE_FILE = os.path.join(TMP, "chat_state.json")
bc.TRASH_DIR = os.path.join(TMP, "trash")
PROJ = os.path.join(TMP, "proj"); os.makedirs(PROJ)
bc.project_dir = lambda cwd: PROJ
FAILS = []
TOK_PUI = "sk-ant-oat01-" + "p" * 60
TOK_CHAYA = "sk-ant-oat01-" + "c" * 60


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "   " + str(info)))
    if not ok:
        FAILS.append(name)


# ---------------------------------------------------------------- store
pui = ACC.add("Pui", TOK_PUI)
chaya = ACC.add("Chaya", "  " + TOK_CHAYA + "\n")          # pasted with whitespace
check("store: token is not in the file in clear", TOK_PUI not in open(ACC.FILE).read())
check("store: tokens decrypt back (whitespace trimmed)", ACC.token_for(pui) == TOK_PUI and ACC.token_for(chaya) == TOK_CHAYA)
check("store: built-in first, added after", [a["id"] for a in ACC.accounts()] == ["computer", pui, chaya])

# ---------------------------------------------------------------- the process environment
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "machine-token"
os.environ["ANTHROPIC_API_KEY"] = "sk-inherited"
bc.mcp_config = lambda: None
seen = []
orig_start = QtCore.QProcess.start
QtCore.QProcess.start = lambda self, *a: seen.append(self.processEnvironment())
try:
    for aid in (pui, ACC.BUILTIN):
        s = bc.ClaudeSession(PROJ, account=aid)
        s.start()
finally:
    QtCore.QProcess.start = orig_start
env_pui, env_pc = seen
check("env: an added account runs on its own token", env_pui.value("CLAUDE_CODE_OAUTH_TOKEN") == TOK_PUI,
      env_pui.value("CLAUDE_CODE_OAUTH_TOKEN")[:20])
check("env: an inherited API key can't override the account", not env_pui.contains("ANTHROPIC_API_KEY"))
check("env: This computer keeps the machine's login", env_pc.value("CLAUDE_CODE_OAUTH_TOKEN") == "machine-token")
check("env: transcripts stay in ~/.claude (no CLAUDE_CONFIG_DIR)", not env_pui.contains("CLAUDE_CONFIG_DIR"))
del os.environ["ANTHROPIC_API_KEY"]


# ---------------------------------------------------------------- the panel, with a fake claude
class FakeSession:
    def __init__(self, account):
        self.account = account
        self.busy, self.sent, self.ctrls = False, [], []
        self.commands, self.parked, self.init = [], False, None

    def send(self, text, imgs=()):
        self.sent.append(text); self.busy = True; return True

    def control(self, subtype, **kw):
        self.ctrls.append(subtype); return "r%d" % len(self.ctrls)

    def running(self):
        return not self.parked

    def stop(self):
        self.parked = True

    def refuse(self, *a):
        pass


SESSIONS = []


def fake_start(self):
    """Same account choice as the real Convo.start, then a fake process."""
    if self.session is None or self.session.parked:
        self.account = ACC.resolve(self.account_choice, exclude=self.tried) or ACC.resolve(self.account_choice)
        self.session = FakeSession(self.account); self.session.owner = self
        SESSIONS.append(self.session)
        self.sid = self.sid or ("sid-%d" % id(self))


bc.Convo.start = fake_start
bc.Convo.ask_context = lambda self: None
QtWidgets.QApplication.alert = staticmethod(lambda w, ms=0: None)
main = QtWidgets.QMainWindow(); main.resize(1500, 900)
p = bc.ChatPanel(main); p.resize(1300, 820); p.show(); app.processEvents()
p.timer.stop()
c = p.cur


def notes(convo):
    out = []
    for i in range(convo.feed.count()):
        w = convo.feed.itemAt(i).widget()
        if w is None:
            continue
        for x in [w] + w.findChildren(QtWidgets.QWidget):
            if isinstance(x, QtWidgets.QLabel):
                out.append(x.text())
            elif isinstance(x, QtWidgets.QTextEdit):          # AutoText bubbles
                out.append(x.toPlainText())
    return " | ".join(out)


def finish(convo, limit=False, msg="Claude AI usage limit reached"):
    s = convo.session
    s.busy = False
    if limit:
        convo.on_event({"type": "rate_limit_event", "rate_limit_info": {
            "status": "rejected", "rateLimitType": "five_hour", "resetsAt": time.time() + 7200}})
        convo.on_event({"type": "result", "is_error": True, "result": msg, "usage": {}})
    else:
        convo.on_event({"type": "result", "usage": {}, "duration_ms": 10})
    for _ in range(3):
        app.processEvents()


check("bar: one account shows its name", p.account_btn.text() == "This computer" or "Auto" in p.account_btn.text(),
      p.account_btn.text())
p.convo_changed(c)
check("bar: Auto shows which account it is on", p.account_btn.text() == "Auto  ·  This computer", p.account_btn.text())

ACC.move(pui, -5)                                  # Pui first: Auto uses Pui
p.composer.setPlainText("hello"); p.send(); app.processEvents()
check("auto: first message runs on the top account", c.session.account == pui and c.session.sent == ["hello"],
      (c.session.account, c.session.sent))

# ---------------------------------------------------------------- auto-switch on a limit
first = c.session
finish(c, limit=True)
check("switch: the account is remembered as out of quota", bool(ACC.limited_until(pui)))
check("switch: a new process on the next account", c.session is not first and c.session.account == ACC.BUILTIN,
      c.session.account)
check("switch: the same message is sent again", c.session.sent == ["hello"], c.session.sent)
check("switch: a note says what happened", "switched to This computer" in notes(c), notes(c)[-300:])
check("switch: the message isn't shown twice", notes(c).count("hello") == 1, notes(c).count("hello"))
check("switch: no error dot for a handled switch", c.unread != "error")
p.convo_changed(c)
check("switch: the bar shows the new account", "This computer" in p.account_btn.text(), p.account_btn.text())

finish(c)
p.composer.setPlainText("next one"); p.send(); app.processEvents()
check("switch: later messages skip the limited account", c.session.account == ACC.BUILTIN and
      c.session.sent[-1] == "next one", (c.session.account, c.session.sent))

# the second account also runs out -> the third
finish(c, limit=True)
check("switch: walks on to the next account", c.session.account == chaya and c.session.sent == ["next one"],
      (c.session.account, c.session.sent))
# and the last one too -> nothing left
finish(c, limit=True)
check("switch: every account out -> says so, no loop", "Every account is out of quota" in notes(c) and
      c.session.account == chaya, notes(c)[-200:])

# ---------------------------------------------------------------- pinned account, auto-switch off
for aid in (pui, ACC.BUILTIN, chaya):
    ACC.clear_limited(aid)
p.new_session(); app.processEvents(); c2 = p.cur
p._pick_account(chaya)
check("pin: picking an account pins the chat", c2.account_choice == chaya)
check("pin: the bar shows the pinned name", p.account_btn.text() == "Chaya", p.account_btn.text())
p.composer.setPlainText("pinned"); p.send(); app.processEvents()
check("pin: the message runs on the pinned account", c2.session.account == chaya, c2.session.account)
finish(c2)
p._pick_account(pui); p.composer.setPlainText("moved"); p.send(); app.processEvents()
check("pin: changing account relaunches on the new one", c2.session.account == pui and c2.session.sent == ["moved"],
      (c2.session.account, c2.session.sent))
ACC.set_auto_switch(False)
finish(c2, limit=True)
check("off: with auto-switch off the chat stays put", c2.session.account == pui and c2.session.sent == ["moved"])
check("off: the limit is shown as an error", "usage limit" in notes(c2).lower())
ACC.set_auto_switch(True)

# a limit message without a rate_limit_event is still recognised
ACC.clear_limited(pui)
p.composer.setPlainText("again"); p.send(); app.processEvents()
c2.session.busy = False
c2.on_event({"type": "result", "is_error": True, "result": "You've hit your limit · resets 5pm", "usage": {}})
for _ in range(3):
    app.processEvents()
check("switch: a limit seen only in the result text also switches", c2.session.account != pui, c2.session.account)

# an ordinary error is NOT a limit
before = c2.session
c2.session.busy = False
c2.on_event({"type": "result", "is_error": True, "result": "Some tool crashed", "usage": {}})
app.processEvents()
check("switch: an ordinary error doesn't switch", c2.session is before)

# ---------------------------------------------------------------- menu + dialog + removal
p._account_menu(); app.processEvents()
pops = [w for w in app.topLevelWidgets() if isinstance(w, bc.PopupMenu) and w.isVisible()]
labels = [r["label"] for r in pops[-1].rows if r != "-"] if pops else []
check("menu: Auto, every account, the switch toggle and Manage", labels[:4] == ["Auto", "Pui", "This computer", "Chaya"]
      and "Manage accounts..." in labels, labels)
for w in pops:
    w.close()
d = bc.AccountsDialog(p)
check("dialog: lists every account", d.list.count() == 3, d.list.count())
d.list.setCurrentRow(0)
check("dialog: the top one can't move up", not d.b_up.isEnabled())
d.list.setCurrentRow(1)
check("dialog: This computer can't be removed", not d.b_del.isEnabled())
d.close()
p._pick_account(chaya)
ACC.remove(chaya)
orig = bc.AccountsDialog.exec
bc.AccountsDialog.exec = lambda self: 0
p.manage_accounts()
bc.AccountsDialog.exec = orig
check("remove: a chat pinned to a removed account goes back to Auto", c2.account_choice == ACC.AUTO, c2.account_choice)

for c_ in p.convos:
    c_.session = None
print("\nALL PASS" if not FAILS else "\n%d FAILED: %s" % (len(FAILS), ", ".join(FAILS)))
sys.exit(1 if FAILS else 0)
