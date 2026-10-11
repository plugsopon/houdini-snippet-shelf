"""FX AI chat panel - the 10 Dremzo Code features, driven offscreen with a FAKE claude session.

  hython tests/test_chat_panel_features.py        (sets QT_QPA_PLATFORM=offscreen itself)

Never starts the CLI, never touches a live Houdini, writes only to a temp folder.
"""
import datetime, os, sys, tempfile, time, json
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

# ---------------------------------------------------------------- the list keeps its order when chats are only OPENED
# (2026-10-11: the CLI appends cost-state / mode / atis-latch lines - no timestamp - every time a
#  chat is resumed and closed; sorting by file mtime put each clicked chat on top as "1m")
LIST = os.path.join(TMP, "listproj"); os.makedirs(LIST)
def write_chat(sid, title, iso, extra_lines=0):
    with open(os.path.join(LIST, sid + ".jsonl"), "w", encoding="utf8") as fh:
        fh.write(json.dumps({"type": "user", "timestamp": iso, "message": {"content": title}}) + "\n")
        fh.write(json.dumps({"type": "assistant", "timestamp": iso, "message": {"content": [{"type": "text", "text": "ok"}]}}) + "\n")
        for i in range(extra_lines):
            fh.write(json.dumps({"type": "user", "timestamp": iso, "message": {"content": "more %d" % i}}) + "\n")
write_chat("old", "older chat", "2026-09-28T14:59:46Z")
write_chat("new", "newer chat", "2026-10-10T15:16:20Z", extra_lines=450)
bc.project_dir = lambda cwd: LIST
time.sleep(0.05)
with open(os.path.join(LIST, "old.jsonl"), "a", encoding="utf8") as fh:      # "opened" just now
    for t in ("atis-latch", "mode", "cost-state", "cost-state"):
        fh.write(json.dumps({"type": t, "sessionId": "old"}) + "\n")
order = [r[0] for r in bc.list_sessions("x")]
check("list: opening an old chat does not move it to the top", order == ["new", "old"], order)
old_ts = [r[2] for r in bc.list_sessions("x") if r[0] == "old"][0]
check("list: its age is its last message, not the open", abs(old_ts - bc._iso_ts("2026-09-28T14:59:46Z")) < 1, old_ts)
with open(os.path.join(LIST, "new.jsonl"), "a", encoding="utf8") as fh:      # line 453: past the old 400-line window
    fh.write(json.dumps({"type": "custom-title", "customTitle": "Renamed late", "sessionId": "new"}) + "\n")
check("list: a Rename at the end of a long chat is the title", dict((r[0], r[1]) for r in bc.list_sessions("x"))["new"] == "Renamed late")
with open(os.path.join(LIST, "new.jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "custom-title", "customTitle": "Renamed again", "sessionId": "new"}) + "\n")
check("list: the latest Rename wins (incremental scan)", dict((r[0], r[1]) for r in bc.list_sessions("x"))["new"] == "Renamed again")
bc._TITLES.clear()          # a Houdini restart: cold cache, both renames read in ONE scan
titles = dict((r[0], r[1]) for r in bc.list_sessions("x"))
check("list: after a restart the latest Rename still wins (one scan, two renames)", titles["new"] == "Renamed again", titles)
with open(os.path.join(LIST, "old.jsonl"), "a", encoding="utf8") as fh:      # a real new message
    fh.write(json.dumps({"type": "user", "timestamp": "2026-10-11T12:00:00Z", "message": {"content": "hi again"}}) + "\n")
check("list: a real new message DOES move it up", [r[0] for r in bc.list_sessions("x")][0] == "old")


def titles_now():
    return dict((r[0], r[1]) for r in bc.list_sessions("x"))


# a brand-new chat: the CLI writes two queue-operation lines ~30-120 ms before the first user line,
# and a refresh landing in that gap used to cache "no title" for good -> the chat vanished
fresh = os.path.join(LIST, "fresh.jsonl")
with open(fresh, "w", encoding="utf8") as fh:
    for op in ("enqueue", "dequeue"):
        fh.write(json.dumps({"type": "queue-operation", "operation": op, "timestamp": "2026-10-11T13:00:00Z"}) + "\n")
check("list: a chat with no message yet is not listed", "fresh" not in titles_now())
with open(fresh, "a", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": "2026-10-11T13:00:01Z", "message": {"content": "make me a pyro sim"}}) + "\n")
check("list: ...and appears once its first message lands (no restart needed)",
      titles_now().get("fresh") == "make me a pyro sim", titles_now())
line = json.dumps({"type": "custom-title", "customTitle": "Half then whole", "sessionId": "fresh"}) + "\n"
with open(fresh, "ab") as fh:
    fh.write(line[:25].encode())
titles_now()                 # a refresh while the rename is half on disk
with open(fresh, "ab") as fh:
    fh.write(line[25:].encode())
check("list: a Rename half-written at one refresh is read whole at the next", titles_now().get("fresh") == "Half then whole",
      titles_now())
with open(fresh, "a", encoding="utf8") as fh:      # JSON that is not an object
    fh.write('[1, {"timestamp": "2026-10-11T13:09:00Z"}]\n7\n"custom-title"\n')
try:
    got = titles_now().get("fresh")
except Exception as e:
    got = repr(e)
check("list: a JSON line that is not an object does not break the list", got == "Half then whole", got)
def iso_or_err(v):
    try:
        return bc._iso_ts(v)
    except Exception as e:
        return repr(e)


check("list: a naive pre-1970 timestamp is ignored, not an error", iso_or_err("1969-12-31T23:59:59") is None,
      iso_or_err("1969-12-31T23:59:59"))
try:
    ago_neg = bc.ChatPanel._ago(-1.0)
except Exception as e:
    ago_neg = repr(e)
check("list: a zoned pre-1970 timestamp is ignored too (it crashed the row's age on Windows)",
      iso_or_err("1969-12-31T23:59:59Z") is None and ago_neg == "", (iso_or_err("1969-12-31T23:59:59Z"), ago_neg))
try:
    fresh_ts = bc.last_activity(fresh)
except Exception as e:
    fresh_ts = repr(e)
cap = bc._ACTIVITY_SCAN_CAP
bc._ACTIVITY_SCAN_CAP = 1024 * 1024
with open(fresh, "a", encoding="utf8") as fh:      # a last line longer than the backward scan reaches
    fh.write(json.dumps({"type": "user", "timestamp": "2026-10-11T13:10:00Z", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t", "content": "A" * (1536 * 1024)}]}}) + "\n")
check("list: a giant last line keeps the chat's known time (no jump to the top)",
      abs(bc.last_activity(fresh) - bc._iso_ts("2026-10-11T13:00:01Z")) < 1 and fresh_ts == bc.last_activity(fresh),
      (fresh_ts, bc.last_activity(fresh)))
bc._ACTIVITY_SCAN_CAP = cap
bad = os.path.join(LIST, "badtitle.jsonl")     # a rename whose title is not a string
with open(bad, "w", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-04T10:00:00Z", "message": {"content": "fine"}}) + "\n")
    fh.write(json.dumps({"type": "custom-title", "customTitle": 12345, "sessionId": "badtitle"}) + "\n")
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-04T10:01:00Z", "message": "not a dict"}) + "\n")
try:
    ids = [r[0] for r in bc.list_sessions("x")]
except Exception as e:
    ids = repr(e)
check("list: one odd file does not empty the list (and keeps its own row)",
      isinstance(ids, list) and "old" in ids and "new" in ids and "badtitle" in ids, ids)
try:
    odd = bc.session_text("x", "badtitle")
except Exception as e:
    odd = repr(e)
check("search: an odd line shape does not break search", odd == "fine", odd)
os.remove(bad); titles_now()
gone = os.path.join(LIST, "gone.jsonl")         # deleted outside the panel, then a new chat reuses the name
write_chat("gone", "first life", "2026-09-02T10:00:00Z")
titles_now(); bc.session_text("x", "gone")
os.remove(gone); titles_now()
check("list: a chat deleted outside the panel is dropped from every cache",
      not any(gone in cc_ for cc_ in (bc._ACTIVITY, bc._TITLES, bc._SEARCH_CACHE)))
write_chat("gone", "second life", "2026-09-03T10:00:00Z", extra_lines=3)
check("list: ...so a new file under that name shows its own title and text",
      titles_now().get("gone") == "second life" and "first life" not in bc.session_text("x", "gone"))
time.sleep(0.05)
with open(gone, "w", encoding="utf8") as fh:    # rewritten in place, LONGER (not appended to)
    fh.write(json.dumps({"type": "queue-operation", "operation": "enqueue", "timestamp": "2026-09-05T10:00:00Z"}) + "\n")
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-05T10:00:01Z", "message": {"content": "third life " + "x" * 400}}) + "\n")
check("list: a chat rewritten in place (not appended) is read again",
      titles_now().get("gone", "").startswith("third life") and "second life" not in bc.session_text("x", "gone"),
      (titles_now().get("gone"), bc.session_text("x", "gone")[:40]))
os.remove(gone); titles_now()

# the first look at a chat finds its latest rename by searching backwards in blocks: right across
# every block edge, and skipping a rename line that is not valid
rs = os.path.join(LIST, "rscan.jsonl")
with open(rs, "w", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-03T09:00:00Z", "message": {"content": "rscan chat"}}) + "\n")
    for n_ in range(40):
        fh.write(json.dumps({"type": "assistant", "timestamp": "2026-09-03T09:01:00Z", "message": {"content": [
            {"type": "text", "text": "filler %d" % n_}]}}) + "\n")
        if n_ == 10:
            fh.write(json.dumps({"type": "custom-title", "customTitle": "R1", "sessionId": "rscan"}) + "\n")
        if n_ == 25:
            fh.write(json.dumps({"type": "custom-title", "customTitle": "R2", "sessionId": "rscan"}) + "\n")
    fh.write(json.dumps({"type": "custom-title", "customTitle": 5, "sessionId": "rscan"}) + "\n")
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-03T09:02:00Z", "message": {"content":
        'it said {"type":"custom-title","customTitle":"FAKE"} in text'}}) + "\n")
blk, got_rs = bc._RSCAN_BLOCK, []
for b_ in (23, 37, 64, 101, 997, 1 << 20):
    bc._RSCAN_BLOCK = b_
    bc._TITLES.pop(rs, None)
    got_rs.append(bc.session_title(rs))
bc._RSCAN_BLOCK = blk
check("list: the latest valid Rename is found on a first look, whatever the block edges", set(got_rs) == {"R2"}, got_rs)
# ...and that look must not lock the file: the CLI rewrites a transcript in place (to drop a line)
tried = []
_cto = bc._custom_title_of


def _rewrite_meanwhile(raw):
    try:
        with open(rs, "r+b") as fh_:
            data_ = fh_.read(); fh_.seek(0); fh_.truncate(0); fh_.write(data_)
        tried.append("ok")
    except OSError as e:
        tried.append(repr(e))
    return _cto(raw)


bc._custom_title_of = _rewrite_meanwhile
try:
    bc._TITLES.pop(rs, None)
    bc.session_title(rs)
finally:
    bc._custom_title_of = _cto
check("list: another program can rewrite a chat while the list reads it (no mmap lock)",
      bool(tried) and all(t_ == "ok" for t_ in tried), tried)
os.remove(rs); titles_now()

# search covers the whole chat (the old index stopped at 6 MB) and only what was SAID
big = os.path.join(LIST, "big.jsonl")
with open(big, "w", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-01T10:00:00Z", "message": {"content": "a long chat"}}) + "\n")
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-01T10:01:00Z", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "t1", "content": "B" * (6600 * 1024)}]}}) + "\n")
    fh.write(json.dumps({"type": "assistant", "timestamp": "2026-09-01T10:02:00Z", "message": {"content": [
        {"type": "text", "text": "the Zebrafinch solver is set"}]}}) + "\n")
txt = bc.session_text("x", "big")
check("search: text past 6 MB is found", "zebrafinch" in txt, len(txt))
check("search: matches what was said, not JSON keys or tool payloads", "tool_use_id" not in txt and "bbbb" not in txt)
with open(big, "a", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": "2026-09-01T10:03:00Z", "message": {"content": "สวัสดีครับ เพิ่มควัน"}}) + "\n")
check("search: a new line is indexed incrementally, Thai included", "เพิ่มควัน" in bc.session_text("x", "big"))
half = json.dumps({"type": "assistant", "timestamp": "2026-09-01T10:04:00Z", "message": {"content": [
    {"type": "text", "text": "the Quokkarail cache"}]}}) + "\n"
with open(big, "ab") as fh:
    fh.write(half[:60].encode())
bc.session_text("x", "big")                     # a search while the line is half on disk
with open(big, "ab") as fh:
    fh.write(half[60:].encode())
txt = bc.session_text("x", "big")
check("search: a line half-written at one search is found whole at the next, once",
      txt.count("quokkarail") == 1, txt.count("quokkarail"))

# ---------------------------------------------------------------- the list does not jump
for n in range(40):
    write_chat("c%02d" % n, "chat number %02d" % n, "2026-08-%02dT10:00:00Z" % (n % 28 + 1))
for c_ in list(p.convos):
    if c_.session is not None:
        c_.session.busy = False
p.resize(1300, 520); app.processEvents()
p.refresh_sessions(); app.processEvents()
bar = p.list.verticalScrollBar()
check("list: enough rows to scroll", bar.maximum() > 8, bar.maximum())
bar.setValue(bar.maximum() // 2); app.processEvents()
v0 = bar.value()
w0 = p.list.itemWidget(p.list.item(12))
builds = []
_orig_rebuild = p._rebuild_list
p._rebuild_list = lambda *a, **k: (builds.append(1), _orig_rebuild(*a, **k))
p.refresh_sessions(); app.processEvents()
check("list: a refresh that changes nothing rebuilds nothing", not builds and p.list.itemWidget(p.list.item(12)) is w0)
check("list: ...and leaves the scroll where it was", bar.value() == v0, (bar.value(), v0))
pos = QtCore.QPoint(60, 140)
under = p.list.itemAt(pos).data(QtCore.Qt.UserRole)
QTest.mouseClick(p.list.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos); app.processEvents()
check("list: a click opens the row under the mouse", p.cur.sid == under, (p.cur.sid, under))
check("list: ...the list does not scroll away (the same row is still under the mouse)",
      bar.value() == v0 and p.list.itemAt(pos).data(QtCore.Qt.UserRole) == under,
      (bar.value(), v0, p.list.itemAt(pos).data(QtCore.Qt.UserRole), under))
check("list: ...and it is the list's current row (arrow keys start there)",
      p.list.currentItem() is not None and p.list.currentItem().data(QtCore.Qt.UserRole) == under)
p.cur.session.busy = True                        # the chat starts working -> its mark changes -> a rebuild
del builds[:]
p.refresh_sessions(); app.processEvents()
check("list: a real change rebuilds", len(builds) == 1, builds)
check("list: ...and the rebuild keeps the scroll and the highlight", bar.value() == v0 and
      p.list.currentItem() is not None and p.list.currentItem().data(QtCore.Qt.UserRole) == under, (bar.value(), v0))


def title_x(sid):
    for i in range(p.list.count()):
        if p.list.item(i).data(QtCore.Qt.UserRole) == sid:
            return p.list.itemWidget(p.list.item(i)).findChild(QtWidgets.QLabel, "rowtitle").x()


idle = [r for r in bc.list_sessions("x") if r[0] != under][0][0]
check("list: a working chat's title does not shift sideways", title_x(under) == title_x(idle), (title_x(under), title_x(idle)))
del builds[:]
p.cur.session.busy = False
for _ in range(6):                               # a turn's burst of events
    p.convo_changed(p.cur)
QTest.qWait(200)
check("list: a burst of events is ONE refresh", len(builds) == 1, builds)
lab = p._ages[idle][0]; lab.setText("zzz"); p._refresh_ages()
check("list: ages update in place, without a rebuild", lab.text() != "zzz", lab.text())
bar.setValue(0); app.processEvents()
last = p.list.item(p.list.count() - 1)
p._pick_session(last); app.processEvents()      # Ctrl+Down style: the highlight moves off screen
r = p.list.visualItemRect(p.list.currentItem())
check("list: moving the highlight to a row out of view scrolls to it",
      p.list.viewport().rect().contains(r.center()), (r, p.list.viewport().rect()))
p.cur.fork = True; p.refresh_sessions(); app.processEvents()
check("list: an unsent fork highlights no row (it still carries the original's id)", not p.list.selectedItems())
p.cur.fork = False
p.refresh_sessions(); app.processEvents()          # settle: the highlight returns


def _row_item(sid):
    for i in range(p.list.count()):
        if p.list.item(i).data(QtCore.Qt.UserRole) == sid:
            return p.list.item(i)


def _row_label(sid, name):
    it = _row_item(sid)
    return p.list.itemWidget(it).findChild(QtWidgets.QLabel, name) if it is not None else None


def _onscreen(it):
    return it is not None and p.list.viewport().rect().intersects(p.list.visualItemRect(it))


def _scroll_away_from(sid):
    for v in (0, bar.maximum()):
        bar.setValue(v); app.processEvents()
        if not _onscreen(_row_item(sid)):
            return True
    return False


cur_sid = p.cur.sid
off = _scroll_away_from(cur_sid); v1 = bar.value()
p.refresh_sessions(); app.processEvents()
check("list: a refresh does not scroll back to the open chat after you scrolled away from it",
      off and bar.value() == v1, (off, bar.value(), v1))
off = _scroll_away_from(cur_sid); v1 = bar.value(); del builds[:]
with open(os.path.join(LIST, "fresh.jsonl"), "a", encoding="utf8") as fh:   # another chat is renamed
    fh.write(json.dumps({"type": "custom-title", "customTitle": "Renamed elsewhere", "sessionId": "fresh"}) + "\n")
p.refresh_sessions(); app.processEvents()
check("list: ...nor does a REBUILD (Qt's autoScroll on setCurrentItem pulled it back)",
      off and len(builds) == 1 and bar.value() == v1, (off, len(builds), bar.value(), v1))
other = [r[0] for r in bc.list_sessions("x") if r[0] not in (cur_sid,)][3]
oc = bc.Convo(p, resume=other, title="bg", model=None); p.convos.append(oc); oc.start()
off = _scroll_away_from(cur_sid); v1 = bar.value()
oc.session.busy = True; p.convo_changed(oc); QTest.qWait(150)          # a background chat starts working
oc.session.busy = False; oc.unread = "done"; p.convo_changed(oc); QTest.qWait(150)   # ...and finishes
check("list: a background chat starting and finishing does not move the list", bar.value() == v1, (bar.value(), v1))
# at 820 px a restore without doItemsLayout lands one row short; at 520 it does not
p.resize(1300, 820); app.processEvents()
bar.setValue(bar.maximum()); app.processEvents()
_vis = [p.list.item(i) for i in range(p.list.count()) if _onscreen(p.list.item(i))
        and not str(p.list.item(i).data(QtCore.Qt.UserRole)).startswith("::")]
p._pick_session(_vis[len(_vis) // 2]); app.processEvents()
cur_sid = p.cur.sid
bar.setValue(bar.maximum()); app.processEvents(); vb = bar.value()
p.cur.unread = "done"; del builds[:]
p.refresh_sessions(); app.processEvents()
check("list: a rebuild with the list scrolled to the very bottom keeps it there",
      len(builds) == 1 and bar.value() == vb, (len(builds), bar.value(), vb))
m = p._marks.get(cur_sid)
_col = lambda w: (w.ensurePolished(), w.palette().color(QtGui.QPalette.WindowText).name())[1] if w is not None else None
looks = (m.text() if m else None, _col(m), _col(_row_label(cur_sid, "rowtitle")), _col(_row_label(cur_sid, "rowage")))
check("list: a finished chat's dot, title and age take their colours from the panel CSS",
      looks == ("•", "#6aa5ff", "#ece9e3", "#77756f"), looks)
p.cur.unread = None; p.refresh_sessions(); app.processEvents()
bot = [p.list.item(i).data(QtCore.Qt.UserRole) for i in range(p.list.count())
       if not str(p.list.item(i).data(QtCore.Qt.UserRole)).startswith("::")][-1]
age0 = _row_label(bot, "rowage").text()
with open(os.path.join(LIST, bot + ".jsonl"), "a", encoding="utf8") as fh:   # older still: it stays the bottom row
    fh.write(json.dumps({"type": "user", "timestamp": "2026-07-01T10:00:00Z", "message": {"content": "x"}}) + "\n")
del builds[:]
p.refresh_sessions(); app.processEvents()
age1 = _row_label(bot, "rowage").text()
check("list: a chat whose last message time moved shows its new age (same rows, no rebuild)",
      not builds and age1 == p._ago(bc._iso_ts("2026-07-01T10:00:00Z")) and age1 != age0, (len(builds), age0, age1))
with open(os.path.join(LIST, cur_sid + ".jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "custom-title", "customTitle": "Renamed X", "sessionId": cur_sid}) + "\n")
p.refresh_sessions(); app.processEvents()
tl = _row_label(cur_sid, "rowtitle")
check("list: a Rename shows in the list", tl is not None and tl.text() == "Renamed X", tl.text() if tl else None)
# a working chat keeps getting messages with no event to refresh the list: its age stays "now"
now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
with open(os.path.join(LIST, cur_sid + ".jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "assistant", "timestamp": now_iso, "message": {"content": [{"type": "text", "text": "."}]}}) + "\n")
p.cur.session.busy = True
p._refresh_ages()
check("list: a working chat's age follows its newest message (no refresh needed)",
      _row_label(cur_sid, "rowage").text() == "now", _row_label(cur_sid, "rowage").text())
p.cur.session.busy = False; p.refresh_sessions(); app.processEvents()
QTest.qWait(1600)       # the 1500 ms refreshes scheduled by send() earlier must land first
reads = []
_ls = bc.list_sessions
bc.list_sessions = lambda *a, **k: (reads.append(1), _ls(*a, **k))[1]
for _ in range(6):
    p.convo_changed(p.cur)
QTest.qWait(200)
n_burst = len(reads); del reads[:]
p.convo_changed(p.cur); p.refresh_sessions(); QTest.qWait(200)
n_direct = len(reads)
bc.list_sessions = _ls
check("list: a burst of events reads the chat folder once", n_burst == 1, n_burst)
check("list: a direct refresh cancels the pending one", n_direct == 1, n_direct)
lab_a = next(iter(p._ages.values()))[0]; lab_a.setText("zzz")
p._ages_at = time.time() - 31
p._tick(); app.processEvents()
check("list: the tick refreshes the ages after 30 s", lab_a.text() != "zzz", lab_a.text())
# a click on a half-visible bottom row: Qt keeps it where it is, so must we
part = None
for v in range(0, bar.maximum() + 1):
    bar.setValue(v); app.processEvents()
    vr = p.list.viewport().rect()
    for i in range(p.list.count()):
        it = p.list.item(i); r = p.list.visualItemRect(it)
        if (r.top() < vr.bottom() < r.bottom() and not str(it.data(QtCore.Qt.UserRole)).startswith("::")
                and it.data(QtCore.Qt.UserRole) != p.cur.sid):
            part = it
            break
    if part is not None:
        break
if part is None:
    check("list: found a half-visible bottom row to click", False)
else:
    v2 = bar.value(); pos2 = QtCore.QPoint(60, p.list.visualItemRect(part).top() + 4); want = part.data(QtCore.Qt.UserRole)
    QTest.mouseClick(p.list.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos2); app.processEvents()
    check("list: clicking a half-visible bottom row opens it and does not scroll (no neighbour under the mouse)",
          p.cur.sid == want and bar.value() == v2 and p.list.itemAt(pos2).data(QtCore.Qt.UserRole) == want,
          (p.cur.sid, want, bar.value(), v2))
bar.setValue(bar.maximum()); app.processEvents()
p.search.setText("chat number"); p.refresh_sessions(); app.processEvents()
check("search: results open at the top, not at the old scroll position", bar.value() == 0, bar.value())
p.search.setText(""); p.refresh_sessions(); app.processEvents()
# a chat below the view gets a new message and jumps to the top: the rows on screen stay put
bar.setValue(bar.maximum() // 2); app.processEvents()
vis_now = p._visible_rows()
last_vis = vis_now[-1][1]
below = [p.list.item(i).data(QtCore.Qt.UserRole) for i in range(last_vis + 1, p.list.count())
         if not str(p.list.item(i).data(QtCore.Qt.UserRole)).startswith("::")][0]
pos3 = QtCore.QPoint(60, p.list.visualItemRect(p.list.item(vis_now[len(vis_now) // 2][1])).center().y())
under3 = p.list.itemAt(pos3).data(QtCore.Qt.UserRole)
now_iso2 = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
with open(os.path.join(LIST, below + ".jsonl"), "a", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": now_iso2, "message": {"content": "back to this one"}}) + "\n")
p.refresh_sessions(); app.processEvents()
first_row = [p.list.item(i).data(QtCore.Qt.UserRole) for i in range(p.list.count())
             if not str(p.list.item(i).data(QtCore.Qt.UserRole)).startswith("::")][0]
check("list: a chat below the view jumping to the top does not slide the rows under the mouse",
      first_row == below and p.list.itemAt(pos3).data(QtCore.Qt.UserRole) == under3,
      (first_row, below, p.list.itemAt(pos3).data(QtCore.Qt.UserRole), under3))
# a new chat: no row until its first message lands; when it appears, it scrolls into view
bar.setValue(bar.maximum()); app.processEvents()
p.new_session(); app.processEvents()
nc = p.cur
p.refresh_sessions(); app.processEvents()
with open(os.path.join(LIST, nc.sid + ".jsonl"), "w", encoding="utf8") as fh:
    fh.write(json.dumps({"type": "user", "timestamp": now_iso2, "message": {"content": "brand new chat"}}) + "\n")
p.refresh_sessions(); app.processEvents()
check("list: a new chat's row scrolls into view when it appears", _onscreen(_row_item(nc.sid)),
      (bar.value(), _row_item(nc.sid) is not None))
# open a search result far down, clear the search: the list lands on that chat
p.search.setText("chat number 0"); p.refresh_sessions(); app.processEvents()
res_rows = [p.list.item(i) for i in range(p.list.count()) if not str(p.list.item(i).data(QtCore.Qt.UserRole)).startswith("::")]
pick = res_rows[-1]; pick_sid = pick.data(QtCore.Qt.UserRole)
p._row_clicked(pick); app.processEvents()
p.search.setText(""); p.refresh_sessions(); app.processEvents()
check("search: clearing it shows the chat you opened from the results", p.cur.sid == pick_sid and _onscreen(_row_item(pick_sid)),
      (p.cur.sid, pick_sid, bar.value()))
p._rebuild_list = _orig_rebuild
p.resize(1300, 820); app.processEvents()
bc.project_dir = lambda cwd: PROJ


# ---------------------------------------------------------------- robustness (each check proven by breaking its fix)
import io, msvcrt
GAP = os.path.join(TMP, "gapproj"); os.makedirs(GAP)


def _w(path, objs, mode="w"):
    with open(path, mode, encoding="utf8", newline="\n") as fh:
        for o in objs:
            fh.write((o if isinstance(o, str) else json.dumps(o)) + "\n")


# a working chat whose file is not on disk yet reads "now" (not last_activity of a missing file)
nd = bc.Convo(p, title="Not on disk yet", model=None); p.convos.append(nd); nd.start(); nd.session.busy = True
p.refresh_sessions(); app.processEvents()
lab_nd = p._ages[nd.sid][0] if nd.sid in p._ages else None
if lab_nd is not None:
    lab_nd.setText("zzz"); p._refresh_ages()
check("list: a working chat with no file on disk yet reads 'now'",
      lab_nd is not None and lab_nd.text() == "now", lab_nd.text() if lab_nd is not None else "no row")
nd.session.busy = False; p.refresh_sessions(); app.processEvents()

bc.project_dir = lambda cwd: GAP

# a read that failed (file locked mid-read) is answered but not remembered
lk = os.path.join(GAP, "locked.jsonl")
_w(lk, [{"type": "user", "timestamp": "2026-09-10T10:00:00Z", "message": {"content": "locked once"}}])
holder = open(lk, "r+b"); n_lk = os.path.getsize(lk)
holder.seek(0); msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, n_lk)        # another process is writing
try:
    t_locked = bc.last_activity(lk)
finally:
    holder.seek(0); msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, n_lk); holder.close()
t_after = bc.last_activity(lk)
check("list: a read that hit a locked file is not cached (the next read finds the message time)",
      abs(t_after - bc._iso_ts("2026-09-10T10:00:00Z")) < 1, (t_locked, t_after))


# the line reader is linear: one long line costs about what the same bytes in short lines cost.
# A source that hands back at most 32 KB per read (as a pipe or a slow share may) makes a per-read
# re-copy show on an 8 MB line instead of needing a 64 MB file.
class _Trickle(io.BytesIO):
    def read(self, n=-1):
        return super().read(32 * 1024 if n is None or n < 0 else min(n, 32 * 1024))


def _read_secs(data):
    best = None
    for _ in range(3):
        rest = {"tail": b""}
        t0 = time.perf_counter()
        n = sum(1 for _ in bc._complete_lines(_Trickle(data), 0, rest))
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    return best, n


t_one, n_one = _read_secs(b"A" * (8 << 20) + b"\n")              # one 8 MB line
t_many, n_many = _read_secs((b"A" * 1023 + b"\n") * (8 << 10))   # the same 8 MB as 8192 lines
check("list: a long line is read in linear time (no re-copy per read)",
      n_one == 1 and n_many == 8192 and t_one < 3 * t_many + 0.02, (round(t_one, 4), round(t_many, 4)))

# after a restart (cold cache) the latest rename is found without splitting every line in Python
lg = os.path.join(GAP, "long.jsonl")
_w(lg, [{"type": "user", "timestamp": "2026-09-08T10:00:00Z", "message": {"content": "long chat"}},
        {"type": "custom-title", "customTitle": "Renamed early", "sessionId": "long"}] +
   [{"type": "assistant", "timestamp": "2026-09-08T10:01:00Z", "message": {"content": [{"type": "text", "text": "ok %d" % i}]}}
    for i in range(3000)])
_walked, _cl = [], bc._complete_lines


def _counting(fh, start, rest):
    for item in _cl(fh, start, rest):
        _walked.append(1)
        yield item


bc._complete_lines = _counting
try:
    bc._TITLES.pop(lg, None)
    t_lg = bc.session_title(lg)
finally:
    bc._complete_lines = _cl
check("list: a cold title read finds the rename without walking every line",
      t_lg == "Renamed early" and len(_walked) < 300, (t_lg, len(_walked)))

# the first-title scan parses only lines that can hold a title
ft = os.path.join(GAP, "firsttitle.jsonl")
_w(ft, [{"type": "progress", "timestamp": "2026-09-09T10:00:00Z", "data": {"step": i}} for i in range(60)] +
   [{"type": "user", "timestamp": "2026-09-09T10:01:00Z", "message": {"content": "the first question"}}])
_parsed, _o = [], bc._obj
bc._obj = lambda raw: (_parsed.append(1), _o(raw))[1]
try:
    got_ft = bc._first_title(ft)
finally:
    bc._obj = _o
check("list: the first-title scan does not parse lines that cannot hold a title",
      got_ft == ("the first question", True) and len(_parsed) <= 2, (got_ft, len(_parsed)))

# a file first cached while shorter than 256 bytes: its cached head grows with it, so a later
# in-place rewrite that keeps the first line but changes the next is still seen
yp = os.path.join(GAP, "young.jsonl")
l1 = {"type": "user", "timestamp": "2026-09-06T10:00:00Z", "message": {"content": "head one"}}
assert len(json.dumps(l1)) + 1 < 256
_w(yp, [l1])
bc.session_text("x", "young")
time.sleep(0.05)
_w(yp, [{"type": "assistant", "timestamp": "2026-09-06T10:01:00Z", "message": {"content": [{"type": "text", "text": "alphaword " * 30}]}}], "a")
bc.session_text("x", "young")
time.sleep(0.05)
_w(yp, [l1, {"type": "assistant", "timestamp": "2026-09-06T10:02:00Z", "message": {"content": [{"type": "text", "text": "gammaword " * 45}]}}])
ytxt = bc.session_text("x", "young")
check("search: a rewrite that keeps a young file's first line is still seen",
      "gammaword" in ytxt and "alphaword" not in ytxt, ytxt[:60])

# a line nested too deep to parse is skipped, not fatal
dp = os.path.join(GAP, "deep.jsonl")
_w(dp, ['{"type": "user", "message": {"content": ' + "[" * 5000 + "]" * 5000 + "}}",
        {"type": "user", "timestamp": "2026-09-07T10:00:00Z", "message": {"content": "deep but fine"}}])
try:
    dids = dict((r[0], r[1]) for r in bc.list_sessions("x"))
except Exception as e:
    dids = repr(e)
try:
    dtxt = bc.session_text("x", "deep")
except Exception as e:
    dtxt = repr(e)
check("list: a line nested too deep to parse keeps the chat's row and its search",
      isinstance(dids, dict) and dids.get("deep") == "deep but fine" and dtxt == "deep but fine",
      (dids if not isinstance(dids, dict) else dids.get("deep"), dtxt[:80]))

# a text block whose text is not a string
op = os.path.join(GAP, "oddtext.jsonl")
_w(op, [{"type": "user", "timestamp": "2026-09-07T11:00:00Z", "message": {"content": [{"type": "text", "text": 12345}]}},
        {"type": "assistant", "timestamp": "2026-09-07T11:01:00Z", "message": {"content": [{"type": "text", "text": {"a": 1}}]}},
        {"type": "user", "timestamp": "2026-09-07T11:02:00Z", "message": {"content": "odd text but fine"}}])
try:
    oids = dict((r[0], r[1]) for r in bc.list_sessions("x"))
except Exception as e:
    oids = repr(e)
try:
    otxt = bc.session_text("x", "oddtext")
except Exception as e:
    otxt = repr(e)
check("list: a text block whose text is not a string keeps the row and the search",
      isinstance(oids, dict) and oids.get("oddtext") == "odd text but fine" and otxt == "odd text but fine",
      (oids if not isinstance(oids, dict) else oids.get("oddtext"), otxt[:80]))

# the first user line's message is not an object
mp = os.path.join(GAP, "oddmsg.jsonl")
_w(mp, [{"type": "user", "timestamp": "2026-09-07T12:00:00Z", "message": "not a dict"},
        {"type": "user", "timestamp": "2026-09-07T12:01:00Z", "message": {"content": "first real message"}}])
try:
    mids = dict((r[0], r[1]) for r in bc.list_sessions("x"))
except Exception as e:
    mids = repr(e)
check("list: a first user line whose message is not an object does not drop the chat",
      isinstance(mids, dict) and mids.get("oddmsg") == "first real message",
      mids if not isinstance(mids, dict) else mids.get("oddmsg"))

bc.project_dir = lambda cwd: PROJ


# ---------------------------------------------------------------- Stop is not an error
cc = p.cur; cc.start(); cc.session.busy = True; cc.stopped = True; p.hide(); app.processEvents()
cc.on_event({"type": "result", "subtype": "error_during_execution", "is_error": True, "usage": {}})
notes = [w.text() for w in cc.scroll.widget().findChildren(QtWidgets.QLabel)]
check("Stop: no red error note, no error dot", not any(n.startswith("error:") for n in notes) and cc.unread == "done",
      (cc.unread, notes[-3:]))
p.show(); app.processEvents()

print("\n%d failed" % len(FAILS) if FAILS else "\nALL PASS")
sys.exit(1 if FAILS else 0)
