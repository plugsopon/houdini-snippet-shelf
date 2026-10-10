"""FX AI chat panel - the 10 Dremzo Code features, driven offscreen with a FAKE claude session.

  hython tests/test_chat_panel_features.py        (sets QT_QPA_PLATFORM=offscreen itself)

Never starts the CLI, never touches a live Houdini, writes only to a temp folder.
"""
import os, sys, tempfile, time, json
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mcp", "houdini"))
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtTest import QTest
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
import brother_chat as bc

TMP = tempfile.mkdtemp(prefix="fxai_test_")
bc.STATE_FILE = os.path.join(TMP, "chat_state.json")
bc.TRASH_DIR = os.path.join(TMP, "trash")
PROJ = os.path.join(TMP, "proj"); os.makedirs(PROJ)
bc.project_dir = lambda cwd: PROJ
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "   " + str(info)))
    if not ok:
        FAILS.append(name)


class FakeSession:
    def __init__(self):
        self.busy, self.sent, self.ctrls, self.answers = False, [], [], []
        self.commands = [{"name": "compact", "description": "Compact"}, {"name": "cost", "description": "Cost"}]
        self.parked, self.init = False, None

    def send(self, text, imgs=()):
        self.sent.append(text); self.busy = True; return True

    def control(self, subtype, **kw):
        self.ctrls.append(subtype)
        if subtype == "interrupt":
            # the real CLI answers an interrupt with result/error_during_execution (measured
            # 2026-10-10 against 2.1.288) - asynchronously, so emit it on the next event loop turn
            def done():
                self.busy = False
                self.owner.on_event({"type": "result", "subtype": "error_during_execution",
                                     "is_error": True, "usage": {}})
            QtCore.QTimer.singleShot(0, done)
        return "r%d" % len(self.ctrls)

    def running(self):
        return True

    def stop(self):
        pass

    def answer_permission(self, rid, allow, **kw):
        self.answers.append((rid, allow)); return True

    def refuse(self, *a):
        pass


def fake_start(self):
    if self.session is None:
        self.session = FakeSession(); self.session.owner = self
        self.sid = self.sid or ("sid-%d" % id(self))


bc.Convo.start = fake_start
bc.Convo.ask_context = lambda self: None
ALERTS = []
QtWidgets.QApplication.alert = staticmethod(lambda w, ms=0: ALERTS.append(w))

main = QtWidgets.QMainWindow(); main.resize(1500, 900)
p = bc.ChatPanel(main); p.resize(1300, 820); p.show(); app.processEvents()
p.timer.stop()              # drive _tick by hand so the queue flushes when the test says
c = p.cur
c.start()
fs = c.session


def tick(n=3):
    for _ in range(n):
        p._tick(); app.processEvents()


# ---------------------------------------------------------------- 1. queue
p.composer.setPlainText("first"); p.send()
check("1 send goes out when idle", fs.sent == ["first"], fs.sent)
p.composer.setPlainText("second"); p.send()
p.composer.setPlainText("third"); p.send()
check("1 sends while busy are queued, not sent", fs.sent == ["first"] and len(c.queue) == 2, (fs.sent, c.queue))
check("1 queue strip is shown", p.queue_box.isVisibleTo(p))
p.queue_send_now(1)
check("1 send now moves it to the front and stops the turn", c.queue[0][0] == "third" and "interrupt" in fs.ctrls)
tick()
check("1 queue flushes when the turn stops", fs.sent[-1] == "third" and len(c.queue) == 1, (fs.sent, c.queue))
p.queue_remove(0)
check("1 remove empties the queue + hides strip", not c.queue and not p.queue_box.isVisibleTo(p))
p.composer.setPlainText("urgent"); p.send_now()
tick()
check("1 Ctrl+Enter path: interrupts and sends", fs.sent[-1] == "urgent", fs.sent)

# ---------------------------------------------------------------- 9. working line + jump
check("9 Working line exists while busy", c.working_w is not None)
c.turn_t0 = time.time() - 65; c.tick_working(1)
check("9 Working line shows elapsed", "Working 1m 05s" in c.working_w.text(), c.working_w.text())

# ---------------------------------------------------------------- 5. edited files + 3/2 unread + notify
c.on_event({"type": "assistant", "message": {"content": [
    {"type": "tool_use", "id": "e1", "name": "Edit",
     "input": {"file_path": "C:/x/foo.py", "old_string": "a\nb", "new_string": "a\nb\nc"}},
    {"type": "tool_use", "id": "e2", "name": "Write", "input": {"file_path": "C:/x/bar.vfl", "content": "1\n2\n3\n4"}},
    {"type": "tool_use", "id": "e3", "name": "Edit", "input": {"file_path": "C:/x/bad.py", "old_string": "z", "new_string": "y"}}]}})
c.on_event({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "e3", "is_error": True, "content": "no"}]}})
p.hide(); app.processEvents()
fs.busy = False
c.on_event({"type": "result", "usage": {}, "duration_ms": 1200})
cards = c.scroll.widget().findChildren(bc.EditedCard)
check("5 'Edited N files' card after the turn", len(cards) == 1)
txt = " ".join(l.text() for l in cards[0].findChildren(QtWidgets.QLabel)) if cards else ""
check("5 counts the 2 successful files, not the failed one", "Edited 2 files" in txt and "+7" in txt and "-2" in txt, txt)
check("9 Working line gone after the turn", c.working_w is None)
check("3 finished while hidden -> unread", c.unread == "done", c.unread)
check("2 taskbar flashed when hidden", len(ALERTS) >= 1)
p.show(); app.processEvents()

# ---------------------------------------------------------------- 6 / 8 / 3 sidebar
now = time.time()
for sid, title in (("aaa", "Pyro shelf smoke"), ("bbb", "RBD copy points"), (c.sid, "Current chat")):
    with open(os.path.join(PROJ, sid + ".jsonl"), "w", encoding="utf8") as fh:
        fh.write(json.dumps({"type": "user", "message": {"content": "%s - packedfulltransform" % title}}) + "\n")
c.unread = "done"
p.refresh_sessions(); app.processEvents()


def rows():
    out = []
    for i in range(p.list.count()):
        it = p.list.item(i)
        w = p.list.itemWidget(it)
        labs = [l.text() for l in w.findChildren(QtWidgets.QLabel)] if w is not None and not isinstance(w, QtWidgets.QLabel) else [w.text() if w else ""]
        out.append((it.data(QtCore.Qt.UserRole), labs))
    return out


r = rows()
check("3 unread dot on the finished chat", any(sid == c.sid and "•" in labs[0] for sid, labs in r), r)
p.search.setText("rbd"); p.refresh_sessions()
check("6 search by title", [s for s, _ in rows() if not str(s).startswith("::")] == ["bbb"], rows())
p.search.setText("packedfulltransform"); p.refresh_sessions()
check("6 search by chat content", len([s for s, _ in rows() if not str(s).startswith("::")]) == 3, rows())
p.search.setText(""); p.refresh_sessions()
p.set_flag("aaa", "pinned", True)
r = rows()
check("8 pinned section on top", r[0][1] == ["Pinned"] and r[1][0] == "aaa", r[:3])
p.set_flag("bbb", "archived", True)
check("8 archived hidden behind a toggle", "bbb" not in [s for s, _ in rows()] and any(s == "::archived" for s, _ in rows()))
p.show_archived = True; p.refresh_sessions()
check("8 toggle shows archived", "bbb" in [s for s, _ in rows()])
QtWidgets.QMessageBox.question = staticmethod(lambda *a, **k: QtWidgets.QMessageBox.Yes)
p.delete_session("bbb", "RBD copy points")
check("8 delete moves the transcript to trash", os.path.exists(os.path.join(bc.TRASH_DIR, "bbb.jsonl"))
      and not os.path.exists(os.path.join(PROJ, "bbb.jsonl")))
check("8 state saved to disk", json.load(open(bc.STATE_FILE))["pinned"] == ["aaa"])

# ---------------------------------------------------------------- 7. find in chat
c.add_text("hello world, and hello again")
c.add_text("nothing here")
app.processEvents()
p.findbar.open(); p.findbar.edit.setText("hello"); app.processEvents()
check("7 find counts hits", p.findbar.count.text() == "1/2", p.findbar.count.text())
p.findbar.step(1)
check("7 find steps", p.findbar.count.text() == "2/2", p.findbar.count.text())
QTest.keyClick(p.findbar.edit, QtCore.Qt.Key_Escape); app.processEvents()
check("7 Esc closes the find bar", not p.findbar.isVisible())

# ---------------------------------------------------------------- 4. drag and drop
png = os.path.join(TMP, "render.png"); QtGui.QImage(8, 8, QtGui.QImage.Format_RGB32).save(png)
md = QtCore.QMimeData(); md.setUrls([QtCore.QUrl.fromLocalFile(png), QtCore.QUrl.fromLocalFile(os.path.join(TMP, "x.hipnc"))])
open(os.path.join(TMP, "x.hipnc"), "w").close()
p.composer.clear(); p.composer.images = []
p.composer.take_drop(md); app.processEvents()
check("4 dropped image becomes an attachment", len(p.composer.images) == 1)
check("4 dropped other file becomes an @path", "@" in p.composer.toPlainText() and "x.hipnc" in p.composer.toPlainText(),
      p.composer.toPlainText())
md2 = QtCore.QMimeData(); md2.setText("/obj/rbd_root_copy/PACKED_points")
p.composer.clear(); p.composer.take_drop(md2)
check("4 dropped node path becomes text", p.composer.toPlainText() == "/obj/rbd_root_copy/PACKED_points")
p.composer.images = []; p.refresh_chips()

# ---------------------------------------------------------------- 10. keys
p.composer.clear(); p.composer.setFocus()
QTest.keyClicks(p.composer, "/c"); app.processEvents()
check("10 / popup opens", p.slash.isVisible() and p.slash.count() >= 2, p.slash.count())
QTest.keyClick(p.composer, QtCore.Qt.Key_Down); QTest.keyClick(p.composer, QtCore.Qt.Key_Return); app.processEvents()
check("10 arrow + Enter picks in the / popup", p.composer.toPlainText().startswith("/c") and
      p.composer.toPlainText().endswith(" ") and not p.slash.isVisible(), p.composer.toPlainText())
p.composer.clear()
c.session = fs; fs.busy = True
c.on_event({"type": "control_request", "request_id": "q1", "request": {
    "subtype": "can_use_tool", "tool_name": "Bash", "input": {"command": "ls"}}})
app.processEvents()
c._answer = lambda rid, allow, **kw: fs.answers.append((rid, allow)) or True
card = p.live_permission(); card.answer = c._answer
check("10 approval card has 1/3 keys", card is not None and set(card.keys) >= {"1", "3"})
p.composer.setFocus(); QTest.keyClick(p.composer, QtCore.Qt.Key_3); app.processEvents()
check("10 key 3 denies", fs.answers and fs.answers[-1] == ("q1", False), fs.answers)
fs.busy = False
before = c
p.step_chat(1); app.processEvents()
check("10 next chat switches", p.cur is not before)

# ---------------------------------------------------------------- Stop is not an error
cc = p.cur; cc.start(); cc.session.busy = True; cc.stopped = True; p.hide(); app.processEvents()
cc.on_event({"type": "result", "subtype": "error_during_execution", "is_error": True, "usage": {}})
notes = [w.text() for w in cc.scroll.widget().findChildren(QtWidgets.QLabel)]
check("Stop: no red error note, no error dot", not any(n.startswith("error:") for n in notes) and cc.unread == "done",
      (cc.unread, notes[-3:]))
p.show(); app.processEvents()

print("\n%d failed" % len(FAILS) if FAILS else "\nALL PASS")
sys.exit(1 if FAILS else 0)
