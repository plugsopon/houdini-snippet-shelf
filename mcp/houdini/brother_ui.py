"""brother_ui - the AI menu's "AI Settings..." panel: a dark overlay popup over Houdini's main
window where Plug picks Brother's cursor (style, glitch, size, name tag, click ripples) and
starts/stops the brother_link connection. Every change applies to the live cursor at once and
is saved to ~/.houdini_brother/cursor.json (brother_cursor.save_settings).

Opened from Houdini's main menu bar: AI > AI Settings...  (MainMenuCommon.xml in this folder,
installed by install_menu.py).
"""
import random, sys, time

import hou
from PySide6 import QtCore, QtGui, QtWidgets

import brother_cursor as bc

_open = {"w": None}

CSS = """
#panel { background: #17171b; border: 1px solid #3a3a42; border-radius: 12px; }
QLabel { color: #d8d8de; font-size: 12px; }
QLabel#title { color: #ffffff; font-size: 17px; font-weight: 700; }
QLabel#section { color: #8a8a96; font-size: 11px; font-weight: 700; padding-top: 6px; }
QLabel#hint { color: #8a8a96; font-size: 11px; }
QPushButton { background: #26262c; color: #e6e6ea; border: 1px solid #3a3a42; border-radius: 6px;
              padding: 6px 12px; font-size: 12px; }
QPushButton:hover { border-color: #6a6a78; }
QPushButton:checked { background: #ffffff; color: #000000; border-color: #ffffff; }
QPushButton#tile { padding: 4px; }
QPushButton#tile:checked { background: #26262c; color: #ffffff; border: 2px solid #00ebff; }
QLineEdit { background: #0f0f12; color: #ffffff; border: 1px solid #3a3a42; border-radius: 6px;
            padding: 5px 8px; font-size: 12px; }
QCheckBox { color: #d8d8de; font-size: 12px; spacing: 8px; }
"""


class _Preview(QtWidgets.QWidget):
    """Draws the cursor with given settings, glitching like the real one."""
    def __init__(self, settings_fn, size, tip, bg="#0f0f12", parent=None):
        super().__init__(parent)
        self.settings_fn, self.tip, self.bg = settings_fn, tip, QtGui.QColor(bg)
        self.setFixedSize(*size)
        self.glitch, self.split = {}, 1
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    def step(self):
        s = self.settings_fn()
        pixel = bc.STYLES[s["style"]][1] == "pixel"
        rate = {"off": 0, "calm": 0.25, "wild": 0.7}[s["glitch"]] if pixel else 0
        if random.random() < rate:
            self.glitch = {random.randrange(len(bc.ARROW)): random.choice((-3, -2, 2, 3, 4))
                           for _ in range(random.randint(1, 3))}
            self.split = random.choice((1, 1, 2, 3))
        elif random.random() < 0.5:
            self.glitch, self.split = {}, 1
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen); p.setBrush(self.bg)
        p.drawRoundedRect(QtCore.QRectF(self.rect()), 8, 8)
        bc.paint_cursor(p, self.tip[0], self.tip[1], self.settings_fn(), self.glitch, self.split)


class SettingsPanel(QtWidgets.QWidget):
    def __init__(self, main):
        super().__init__(main, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.main = main
        self.s = dict(bc.SETTINGS)
        self.setStyleSheet(CSS)

        outer = QtWidgets.QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        panel = QtWidgets.QFrame(objectName="panel"); outer.addWidget(panel)
        shadow = QtWidgets.QGraphicsDropShadowEffect(blurRadius=40, offset=QtCore.QPointF(0, 8))
        shadow.setColor(QtGui.QColor(0, 0, 0, 180)); panel.setGraphicsEffect(shadow)
        lay = QtWidgets.QVBoxLayout(panel); lay.setContentsMargins(22, 18, 22, 18); lay.setSpacing(10)

        head = QtWidgets.QHBoxLayout()
        head.addWidget(QtWidgets.QLabel("AI Settings", objectName="title"))
        head.addStretch(1)
        close = QtWidgets.QPushButton("Close"); close.clicked.connect(self.close)
        head.addWidget(close)
        lay.addLayout(head)

        # --- live preview + the styles
        body = QtWidgets.QHBoxLayout(); body.setSpacing(16); lay.addLayout(body)
        left = QtWidgets.QVBoxLayout(); body.addLayout(left)
        left.addWidget(QtWidgets.QLabel("CURSOR", objectName="section"))
        grid = QtWidgets.QGridLayout(); grid.setSpacing(8); left.addLayout(grid)
        self.tiles = QtWidgets.QButtonGroup(self)
        self.previews = []
        for n, (name, (label, kind, _, _)) in enumerate(bc.STYLES.items()):
            b = QtWidgets.QPushButton(objectName="tile", checkable=True)
            b.setFixedSize(118, 96)
            v = QtWidgets.QVBoxLayout(b); v.setContentsMargins(6, 6, 6, 6); v.setSpacing(2)
            pv = _Preview(lambda name=name: dict(self.s, style=name, show_label=False, scale=2),
                          (104, 62), (44, 12), bg="#2b2b2b")   # Houdini's own grey, so dark styles read true
            v.addWidget(pv, 0, QtCore.Qt.AlignHCenter)
            t = QtWidgets.QLabel(label.replace(" - ", "\n"), objectName="hint")
            t.setAlignment(QtCore.Qt.AlignCenter); t.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            v.addWidget(t)
            b.setChecked(name == self.s["style"])
            b.clicked.connect(lambda _=False, name=name: self.set("style", name))
            self.tiles.addButton(b); grid.addWidget(b, n // 4, n % 4)
            self.previews.append(pv)
        left.addStretch(1)

        right = QtWidgets.QVBoxLayout(); right.setSpacing(8); body.addLayout(right)
        right.addWidget(QtWidgets.QLabel("PREVIEW", objectName="section"))
        self.big = _Preview(lambda: self.s, (230, 150), (70, 30), bg="#2b2b2b")
        right.addWidget(self.big)
        self.previews.append(self.big)

        right.addWidget(QtWidgets.QLabel("GLITCH", objectName="section"))
        right.addLayout(self._segmented("glitch", (("Off", "off"), ("Calm", "calm"), ("Wild", "wild"))))
        right.addWidget(QtWidgets.QLabel("SIZE", objectName="section"))
        right.addLayout(self._segmented("scale", (("Small", 1), ("Medium", 2), ("Large", 3))))

        right.addWidget(QtWidgets.QLabel("NAME TAG", objectName="section"))
        self.show_tag = QtWidgets.QCheckBox("Show a name next to the cursor")
        self.show_tag.setChecked(bool(self.s["show_label"]))
        self.show_tag.toggled.connect(lambda v: (self.set("show_label", v), self.tag_text.setEnabled(v)))
        right.addWidget(self.show_tag)
        self.tag_text = QtWidgets.QLineEdit(self.s["label"]); self.tag_text.setMaxLength(24)
        self.tag_text.setEnabled(bool(self.s["show_label"]))
        self.tag_text.textChanged.connect(lambda t: self.set("label", t))
        right.addWidget(self.tag_text)
        self.rip = QtWidgets.QCheckBox("Ripple where it clicks")
        self.rip.setChecked(bool(self.s["ripples"])); self.rip.toggled.connect(lambda v: self.set("ripples", v))
        right.addWidget(self.rip)
        right.addStretch(1)

        # --- connection
        lay.addWidget(QtWidgets.QLabel("CONNECTION", objectName="section"))
        conn = QtWidgets.QHBoxLayout(); lay.addLayout(conn)
        self.status = QtWidgets.QLabel(); conn.addWidget(self.status, 1)
        self.link_btn = QtWidgets.QPushButton(); self.link_btn.clicked.connect(self.toggle_link)
        conn.addWidget(self.link_btn)
        test = QtWidgets.QPushButton("Show me the cursor"); test.clicked.connect(self.demo)
        conn.addWidget(test)
        self.refresh_link()

        self.timer = QtCore.QTimer(self); self.timer.timeout.connect(self._tick); self.timer.start(60)
        self.adjustSize()
        mw = main.geometry()
        self.move(mw.center() - QtCore.QPoint(self.width() // 2, self.height() // 2))
        self._drag = None

    # frameless: drag anywhere on the background to move it
    def mousePressEvent(self, e):
        self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & QtCore.Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def _segmented(self, key, options):
        row = QtWidgets.QHBoxLayout(); row.setSpacing(4)
        group = QtWidgets.QButtonGroup(self)
        for text, value in options:
            b = QtWidgets.QPushButton(text, checkable=True)
            b.setChecked(self.s[key] == value)
            b.clicked.connect(lambda _=False, v=value: self.set(key, v))
            group.addButton(b); row.addWidget(b)
        return row

    def set(self, key, value):
        self.s[key] = value
        bc.save_settings(dict(self.s))          # live cursor follows at once

    def _tick(self):
        for pv in self.previews:
            pv.step()
        if int(time.time() * 2) % 4 == 0:
            self.refresh_link()

    def refresh_link(self):
        bl = sys.modules.get("brother_link")
        port = bl._state.get("port") if bl and bl._state.get("server") is not None else None
        if port:
            self.status.setText("Brother is connected to this session  -  port %d" % port)
            self.link_btn.setText("Disconnect")
        else:
            self.status.setText("Brother can't see this session yet")
            self.link_btn.setText("Connect")

    def toggle_link(self):
        import brother_link
        if brother_link._state.get("server") is not None:
            brother_link.stop()
        else:
            brother_link.start()
        self.refresh_link()

    def demo(self):
        """Glide the real cursor around the main window once, so the choice is seen in place."""
        mw = self.main
        w, h = mw.width(), mw.height()
        for fx, fy in ((0.3, 0.35), (0.62, 0.55), (0.45, 0.7), (0.5, 0.45)):
            ov = bc._glide((w * fx, h * fy), 0.5)
            ov.ripples.append((QtCore.QPointF(w * fx, h * fy), time.time()))
            bc._pump(0.25)

    def closeEvent(self, e):
        self.timer.stop()
        _open["w"] = None
        super().closeEvent(e)


def show_settings():
    w = _open["w"]
    try:
        if w is not None:
            w.raise_(); w.activateWindow()
            return w
    except RuntimeError:
        pass
    _open["w"] = SettingsPanel(hou.qt.mainWindow())
    _open["w"].show()
    return _open["w"]
