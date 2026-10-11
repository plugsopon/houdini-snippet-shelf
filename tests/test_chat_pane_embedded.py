import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen"); os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, r"P:\Project\Houdini Snippet Shelf\mcp\houdini")
from PySide6 import QtWidgets, QtCore
from PySide6.QtTest import QTest
app = QtWidgets.QApplication(sys.argv)
import hou, brother_chat as bc
hou.pypanel.installFile(r"P:\Project\Houdini Snippet Shelf\mcp\houdini\fx_ai.pypanel")
it = hou.pypanel.interfaceByName("fx_ai_chat")
print("pypanel:", it.name(), "|", it.label())
bc.Convo.start = lambda self: None
main = QtWidgets.QMainWindow(); main.resize(1500, 900)
host = QtWidgets.QWidget(); lay = QtWidgets.QVBoxLayout(host); lay.setContentsMargins(0, 0, 0, 0)
w = bc.ChatPanel(main, embedded=True); lay.addWidget(w)
host.resize(620, 700); host.show(); [app.processEvents() for _ in range(6)]
fails = []
def ck(n, ok):
    print(("PASS " if ok else "FAIL ") + n); ok or fails.append(n)
ck("embedded is a plain child widget (no Tool window)", not (w.windowFlags() & QtCore.Qt.Tool) and w.window() is host)
ck("no edge grips", w.grips == [])
ck("close/maximise hidden", not w.max_btn.isVisible())
ck("narrow pane folds the sidebar", not w.side.isVisible())
host.resize(1100, 700); [app.processEvents() for _ in range(4)]
ck("wide pane shows the sidebar", w.side.isVisible())
w.toggle_side(manual=True); host.resize(1200, 700); [app.processEvents() for _ in range(3)]
ck("manual toggle wins over auto", not w.side.isVisible())
w.toggle_side(manual=True)
QTest.keyClick(w, QtCore.Qt.Key_Escape); app.processEvents()
ck("Esc does not hide the pane", w.isVisible())
w.grab().save(r"C:\Users\Plug\AppData\Local\Temp\cop_rnd\pane_wide.png")
w._side_auto = True; host.resize(560, 700); [app.processEvents() for _ in range(4)]
w.grab().save(r"C:\Users\Plug\AppData\Local\Temp\cop_rnd\pane_narrow.png")
w.shutdown(); ck("shutdown stops the timer", not w.timer.isActive())
print("ALL PASS" if not fails else "%d failed" % len(fails))
