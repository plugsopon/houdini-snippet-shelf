"""brother_cursor - a visible, virtual cursor that Brother drives inside Houdini's main window.

Plug's real mouse is never moved. The cursor is a transparent overlay drawn on top of the
main window; clicks and typing are delivered as Qt events to whatever widget sits under the
cursor, so the result is the same as Plug doing it by hand.

Coordinates are LOGICAL pixels of the main window: (0, 0) = its top-left corner, the same
space as the image houdini_screenshot returns.

Every function here runs on Houdini's main thread (brother_link hands it over). Animations
pump the Qt event loop while they run, so the UI keeps repainting.
"""
import math, os, time

import hou
from PySide6 import QtCore, QtGui, QtWidgets

PINK = QtGui.QColor(243, 34, 133)
_ov = {"w": None, "last": None}      # last = widget Brother last clicked


# ----------------------------------------------------------------------------- overlay
class _Overlay(QtWidgets.QWidget):
    """A SEPARATE transparent window laid exactly over Houdini's main window.

    It must not be a child widget: Houdini paints its panes with OpenGL, and a translucent
    child on top of that turned the whole main window black and left cursor trails (seen on
    the first GUI run). As its own top-level window the transparency is done by the Windows
    compositor, the way screen recorders draw their cursor, and Houdini's drawing is untouched.
    """
    def __init__(self, main):
        super().__init__(main, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint |
                         QtCore.Qt.WindowTransparentForInput | QtCore.Qt.WindowDoesNotAcceptFocus |
                         QtCore.Qt.NoDropShadowWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)       # never steal focus from Houdini
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)   # never steal Plug's clicks
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.main = main
        self.pos_ = QtCore.QPointF(main.width() * 0.5, main.height() * 0.5)
        self.ripples = []            # [(point, start_time)]
        self.label = "Brother"
        self.last_active = time.time()
        self._follow()
        main.installEventFilter(self)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)
        self.show()

    def _follow(self):
        """Sit exactly on top of the main window (same global rect) - so overlay coordinates
        ARE main-window coordinates."""
        tl = self.main.mapToGlobal(QtCore.QPoint(0, 0))
        self.setGeometry(QtCore.QRect(tl, self.main.size()))

    def eventFilter(self, obj, ev):                                       # follow moves / resizes
        if ev.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Move, QtCore.QEvent.WindowStateChange):
            self._follow()
        return False

    def _tick(self):
        now = time.time()
        self.ripples = [r for r in self.ripples if now - r[1] < 0.6]
        if now - self.last_active > 20 and not self.ripples:               # idle: fade out of the way
            self.hide()
        self.update()

    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        p.setCompositionMode(QtGui.QPainter.CompositionMode_Source)       # wipe the last frame: no trails
        p.fillRect(self.rect(), QtCore.Qt.transparent)
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        now = time.time()
        for pt, t0 in self.ripples:                                        # click ripples
            k = (now - t0) / 0.6
            c = QtGui.QColor(PINK); c.setAlphaF(max(0.0, 0.7 * (1 - k)))
            p.setPen(QtGui.QPen(c, 3)); p.setBrush(QtCore.Qt.NoBrush)
            r = 6 + 26 * k
            p.drawEllipse(pt, r, r)
        x, y = self.pos_.x(), self.pos_.y()                                 # the arrow
        arrow = QtGui.QPolygonF([QtCore.QPointF(x + dx, y + dy) for dx, dy in
                                 ((0, 0), (0, 22), (6, 17), (10, 26), (14, 24), (10, 15), (17, 15))])
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1.6))
        p.setBrush(PINK)
        p.drawPolygon(arrow)
        f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f)      # name tag
        tag = QtCore.QRectF(x + 16, y + 24, 8 + 7 * len(self.label), 16)
        p.setPen(QtCore.Qt.NoPen); p.setBrush(PINK); p.drawRoundedRect(tag, 4, 4)
        p.setPen(QtGui.QColor(255, 255, 255)); p.drawText(tag, QtCore.Qt.AlignCenter, self.label)


def _main():
    return hou.qt.mainWindow()


def _overlay():
    w = _ov["w"]
    try:
        if w is not None and w.parent() is _main():
            w._follow(); w.show(); w.raise_(); w.last_active = time.time()
            return w
    except RuntimeError:            # the C++ side was deleted
        pass
    _ov["w"] = _Overlay(_main())
    return _ov["w"]


def remove():
    w, _ov["w"] = _ov["w"], None
    if w is not None:
        try:
            w.deleteLater()
        except RuntimeError:
            pass


def _pump(seconds):
    end = time.time() + seconds
    app = QtWidgets.QApplication.instance()
    while time.time() < end:
        app.processEvents(QtCore.QEventLoop.AllEvents, 10)
        time.sleep(0.008)


def _glide(to, seconds=None):
    ov = _overlay()
    a = QtCore.QPointF(ov.pos_)
    b = QtCore.QPointF(*to)
    dist = math.hypot(b.x() - a.x(), b.y() - a.y())
    seconds = seconds if seconds is not None else min(0.9, 0.25 + dist / 1800.0)
    t0 = time.time()
    app = QtWidgets.QApplication.instance()
    while True:
        k = min(1.0, (time.time() - t0) / seconds) if seconds > 0 else 1.0
        e = k * k * (3 - 2 * k)                                             # ease in-out
        ov.pos_ = QtCore.QPointF(a.x() + (b.x() - a.x()) * e, a.y() + (b.y() - a.y()) * e)
        ov.last_active = time.time()
        ov.update()
        app.processEvents(QtCore.QEventLoop.AllEvents, 10)
        if k >= 1.0:
            break
        time.sleep(0.008)
    return ov


def _target(x, y):
    """Widget under a main-window point (the overlay is invisible to hit-testing) + its local point."""
    mw = _main()
    pt = QtCore.QPoint(int(x), int(y))
    if not mw.rect().contains(pt):
        raise RuntimeError("(%d, %d) is outside Houdini's main window" % (x, y))
    # childAt asks the MAIN WINDOW's own widget tree, so the overlay (a separate window
    # lying on top) can never be the answer the way it could be for QApplication.widgetAt
    w = mw.childAt(pt) or mw
    gp = mw.mapToGlobal(pt)
    return w, w.mapFromGlobal(gp), gp


def _describe(w):
    names = []
    while w is not None and len(names) < 4:
        names.append("%s%s" % (type(w).__name__, ("(%s)" % w.objectName()) if w.objectName() else ""))
        w = w.parentWidget()
    return " < ".join(names)


# ----------------------------------------------------------------------------- operations
def op_screenshot(args):
    """The whole main window as a PNG, in logical pixels (the click coordinate space)."""
    mw = _main()
    ov = _ov["w"]
    hidden = False
    if ov is not None and ov.isVisible() and not args.get("with_cursor"):
        ov.hide(); hidden = True
        _pump(0.05)
    # QWidget.grab() comes back black: Houdini draws its panes with OpenGL, which a widget
    # grab can't read. Grab the SCREEN pixels where the window is instead - that sees
    # everything, but also anything lying on top of Houdini at that moment.
    tl = mw.mapToGlobal(QtCore.QPoint(0, 0))
    pm = mw.screen().grabWindow(0, tl.x() - mw.screen().geometry().x(),
                                tl.y() - mw.screen().geometry().y(), mw.width(), mw.height())
    if hidden:
        ov.show()
    img = pm.toImage().scaled(mw.width(), mw.height(), QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
    folder = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".houdini_brother")
    path = os.path.join(folder, "window_%d.png" % os.getpid())
    img.save(path, "PNG")
    return {"file": path, "width": mw.width(), "height": mw.height(),
            "device_pixel_ratio": pm.devicePixelRatio()}


def op_pointer(args):
    ov = _glide((args["x"], args["y"]), args.get("seconds"))
    try:
        w, _, _ = _target(args["x"], args["y"])
        under = _describe(w)
    except RuntimeError as e:
        under = str(e)
    return {"at": [ov.pos_.x(), ov.pos_.y()], "under": under}


def op_click(args):
    x, y = args["x"], args["y"]
    button = {"left": QtCore.Qt.LeftButton, "right": QtCore.Qt.RightButton,
              "middle": QtCore.Qt.MiddleButton}[args.get("button", "left")]
    double = bool(args.get("double"))
    ov = _glide((x, y))
    w, lp, gp = _target(x, y)
    _ov["last"] = w
    lpf, gpf = QtCore.QPointF(lp), QtCore.QPointF(gp)
    app = QtWidgets.QApplication.instance()

    def send(kind, btns):
        ev = QtGui.QMouseEvent(kind, lpf, lpf, gpf, button, btns, QtCore.Qt.NoModifier)
        app.sendEvent(w, ev)

    app.sendEvent(w, QtGui.QMouseEvent(QtCore.QEvent.MouseMove, lpf, lpf, gpf, QtCore.Qt.NoButton,
                                       QtCore.Qt.NoButton, QtCore.Qt.NoModifier))
    for i in range(2 if double else 1):
        send(QtCore.QEvent.MouseButtonPress, button)
        ov.ripples.append((QtCore.QPointF(x, y), time.time()))
        _pump(0.06)
        send(QtCore.QEvent.MouseButtonRelease, QtCore.Qt.NoButton)
        if double and i == 0:
            send(QtCore.QEvent.MouseButtonDblClick, button)
            send(QtCore.QEvent.MouseButtonRelease, QtCore.Qt.NoButton)
            break
        _pump(0.05)
    _pump(0.25)
    fw = app.focusWidget()
    return {"clicked": [x, y], "widget": _describe(w), "focus_now": _describe(fw) if fw else None}


_KEYS = {"enter": QtCore.Qt.Key_Return, "return": QtCore.Qt.Key_Return, "tab": QtCore.Qt.Key_Tab,
         "escape": QtCore.Qt.Key_Escape, "esc": QtCore.Qt.Key_Escape, "backspace": QtCore.Qt.Key_Backspace,
         "delete": QtCore.Qt.Key_Delete, "left": QtCore.Qt.Key_Left, "right": QtCore.Qt.Key_Right,
         "up": QtCore.Qt.Key_Up, "down": QtCore.Qt.Key_Down, "home": QtCore.Qt.Key_Home, "end": QtCore.Qt.Key_End}
_MODS = {"ctrl": QtCore.Qt.ControlModifier, "shift": QtCore.Qt.ShiftModifier, "alt": QtCore.Qt.AltModifier}


def _key_target():
    """Where keys go. Qt only reports a focus widget while Houdini is the ACTIVE window, and
    Plug is usually in another app while Brother works - so fall back to the widget Brother
    last clicked (Houdini's own UI layer routes the keys to the field inside it)."""
    app = QtWidgets.QApplication.instance()
    w = app.focusWidget() or _ov.get("last")
    if w is None:
        raise RuntimeError("nothing to type into - click the field first")
    return app, w


def _send_key(app, w, key, text="", mods=QtCore.Qt.NoModifier):
    app.sendEvent(w, QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, mods, text))
    app.sendEvent(w, QtGui.QKeyEvent(QtCore.QEvent.KeyRelease, key, mods, text))


def op_type(args):
    """Type text into the focused widget, one character at a time, so it is seen being typed."""
    text = args["text"]
    delay = float(args.get("delay", 0.02))
    app, w = _key_target()
    for ch in text:
        if ch == "\n":
            _send_key(app, w, QtCore.Qt.Key_Return, "\r")
        elif ch == "\t":
            _send_key(app, w, QtCore.Qt.Key_Tab, "\t")
        else:
            # letters/digits get their real key code; anything else is delivered as text only
            key = ord(ch.upper()) if ch.isascii() and ch.isalnum() else (
                QtCore.Qt.Key_Space if ch == " " else QtCore.Qt.Key_unknown)
            _send_key(app, w, key, ch)
        _pump(delay)
    return {"typed": len(text), "into": _describe(w)}


def op_key(args):
    """A single key or chord, e.g. "enter", "ctrl+a", "escape"."""
    parts = [s.strip().lower() for s in args["key"].split("+")]
    mods = QtCore.Qt.NoModifier
    for m in parts[:-1]:
        mods |= _MODS[m]
    k = parts[-1]
    key = _KEYS.get(k) or QtGui.QKeySequence(k.upper())[0].key()
    app, w = _key_target()
    _send_key(app, w, key, "" if mods != QtCore.Qt.NoModifier or k in _KEYS else k, mods)
    _pump(0.1)
    return {"key": args["key"], "into": _describe(w)}


def op_cursor_hide(args):
    remove()
    return {"hidden": True}


OPS = {"screenshot": op_screenshot, "pointer": op_pointer, "click": op_click, "type": op_type,
       "key": op_key, "cursor_hide": op_cursor_hide}
