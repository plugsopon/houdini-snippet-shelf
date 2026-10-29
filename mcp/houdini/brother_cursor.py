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

import brother_demo_plan

WHITE = QtGui.QColor(255, 255, 255)
BLACK = QtGui.QColor(0, 0, 0)
RED = QtGui.QColor(255, 30, 50)
CYAN = QtGui.QColor(0, 235, 255)
PINK = QtGui.QColor(243, 34, 133)
# The classic pixel arrow (B = edge, W = fill), used by the pixel styles.
ARROW = ("B..........", "BB.........", "BWB........", "BWWB.......", "BWWWB......",
         "BWWWWB.....", "BWWWWWB....", "BWWWWWWB...", "BWWWWWWWB..", "BWWWWWWWWB.",
         "BWWWWWWWWWB", "BWWWWWWBBBB", "BWWWBWWB...", "BWWBBWWB...", "BWB..BWWB..",
         "BB...BWWB..", "B.....BWWB.", "......BWWB.", ".......BB..")
SMOOTH = ((0, 0), (0, 22), (6, 17), (10, 26), (14, 24), (10, 15), (17, 15))

# ----------------------------------------------------------------------------- settings
# Chosen in AI > AI Settings (brother_ui) and kept in ~/.houdini_brother/cursor.json.
STYLES = {                     # name: (label, kind, fill, edge)
    "glitch_dark":  ("Glitch - black, white edge", "pixel",  BLACK, WHITE),
    "glitch_light": ("Glitch - white, black edge", "pixel",  WHITE, BLACK),
    "glitch_black": ("Glitch - all black",         "pixel",  BLACK, BLACK),
    "smooth_black": ("Smooth - black, white glow", "smooth", BLACK, BLACK),
    "smooth_white": ("Smooth - white, white glow", "smooth", WHITE, QtGui.QColor(30, 30, 34)),
    "smooth_pink":  ("Smooth - pink",              "smooth", PINK, WHITE),
    "dot":          ("Presenter dot",              "dot",    PINK, WHITE),
}
DEFAULTS = {"style": "glitch_dark", "glitch": "calm", "show_label": True, "label": "Brother",
            "scale": 2, "ripples": True,
            # the screen edges fade to this colour while Brother is driving Houdini
            "vignette": True, "vignette_color": "#000000", "vignette_strength": 0.8,
            "vignette_width": 90, "vignette_style": "mosh"}
SETTINGS_FILE = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"),
                             ".houdini_brother", "cursor.json")


def load_settings():
    s = dict(DEFAULTS)
    try:
        import json
        with open(SETTINGS_FILE, encoding="utf8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):               # a torn or hand-edited file must never stop the link
            s.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, ValueError, TypeError):
        pass
    if s["style"] not in STYLES:
        s["style"] = DEFAULTS["style"]
    return s


def save_settings(s):
    import json
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf8") as fh:
        json.dump({k: s[k] for k in DEFAULTS}, fh, indent=1)
    SETTINGS.clear(); SETTINGS.update(s)
    w = _ov.get("w")
    if w is not None:
        try:
            w.update()
        except RuntimeError:
            pass


SETTINGS = load_settings()


def make_edge_glitch(rect, amount=1.0):
    """A fresh set of torn slices for the glitch edge: (side, pos, thick, depth, colour-key)."""
    import random
    out = []
    for _ in range(random.randint(2, int(4 + 6 * amount))):
        side = random.choice("LRTB")
        span = rect.height() if side in "LR" else rect.width()
        out.append((side, random.uniform(0.0, span), random.choice((2, 2, 3, 5, 8, 14)),
                    random.uniform(18, 70 + 110 * amount), random.choice("rrccw")))
    return out


def paint_edges(p, rect, s=None, level=1.0, slices=(), split=1):
    """The 'Brother is driving' frame. Fade: each edge fades from the chosen colour to nothing.
    Glitch: the same fade plus a red and a cyan rim offset from each other (RGB split, like the
    glitch cursor) and torn slices that jump in from the edges."""
    s = s or SETTINGS
    base = QtGui.QColor(s["vignette_color"])
    if not base.isValid():
        base = QtGui.QColor(0, 0, 0)
    w = float(s["vignette_width"])
    a = max(0.0, min(1.0, float(s["vignette_strength"]) * level))
    solid = QtGui.QColor(base); solid.setAlphaF(a)
    clear = QtGui.QColor(base); clear.setAlphaF(0.0)
    mid = QtGui.QColor(base); mid.setAlphaF(a * 0.35)
    p.save()
    p.setRenderHint(QtGui.QPainter.Antialiasing, False)
    p.setPen(QtCore.Qt.NoPen)
    x0, y0, x1, y1 = rect.left(), rect.top(), rect.right() + 1, rect.bottom() + 1
    H, W = rect.height(), rect.width()
    for (ax, ay, bx, by), band in (((x0, 0, x0 + w, 0), QtCore.QRectF(x0, y0, w, H)),
                                   ((x1, 0, x1 - w, 0), QtCore.QRectF(x1 - w, y0, w, H)),
                                   ((0, y0, 0, y0 + w), QtCore.QRectF(x0, y0, W, w)),
                                   ((0, y1, 0, y1 - w), QtCore.QRectF(x0, y1 - w, W, w))):
        g = QtGui.QLinearGradient(ax, ay, bx, by)
        g.setColorAt(0.0, solid); g.setColorAt(0.45, mid); g.setColorAt(1.0, clear)
        p.fillRect(band, QtGui.QBrush(g))

    if s.get("vignette_style") == "glitch":
        def col(c, alpha):
            q = QtGui.QColor(c); q.setAlphaF(max(0.0, min(1.0, alpha * level)))
            return q
        k = 3 * split                                     # how far the two rims drift apart
        red, cyan, white = col(RED, 0.85), col(CYAN, 0.85), col(WHITE, 0.55)
        t = 3                                             # rim thickness
        # red rim hugs the top/left, cyan is pushed in from the bottom/right - the split
        p.fillRect(QtCore.QRectF(x0 + k, y0 + k, W - 2 * k, t), red)
        p.fillRect(QtCore.QRectF(x0 + k, y0 + k, t, H - 2 * k), red)
        p.fillRect(QtCore.QRectF(x0 + 2 * k, y1 - k - t, W - 3 * k, t), cyan)
        p.fillRect(QtCore.QRectF(x1 - k - t, y0 + 2 * k, t, H - 3 * k), cyan)
        # a faint white rim between them
        p.fillRect(QtCore.QRectF(x0 + 1, y0 + 1, W - 2, 1), col(WHITE, 0.25))
        p.fillRect(QtCore.QRectF(x0 + 1, y1 - 2, W - 2, 1), col(WHITE, 0.25))
        palette = {"r": red, "c": cyan, "w": white}
        for side, pos, thick, depth, ck in slices:        # torn slices jumping in from the edge
            c = palette[ck]
            ghost = cyan if ck == "r" else red
            if side == "L":
                r = QtCore.QRectF(x0, y0 + pos, depth, thick)
            elif side == "R":
                r = QtCore.QRectF(x1 - depth, y0 + pos, depth, thick)
            elif side == "T":
                r = QtCore.QRectF(x0 + pos, y0, thick, depth)
            else:
                r = QtCore.QRectF(x0 + pos, y1 - depth, thick, depth)
            p.fillRect(r.translated(k if side in "LR" else 0, 0 if side in "LR" else k), col(ghost, 0.45))
            p.fillRect(r, c)
    p.restore()


# ----------------------------------------------------------------------------- mosh edges
# A datamosh / pixel-stretch frame, after the smeared-light glitch look: light is STRETCHED in
# from each edge as streaks of uneven length (vertical top & bottom, horizontal left & right),
# bright at the screen edge and dying into the dark toward the middle. Mostly navy and electric
# blue, the odd red/orange/white; a colour-shifted copy is ADDED on top a few px off (RGB drift),
# slices tear sideways, and it slides and re-rolls while Brother is in control.
# The band images are built once per re-roll and cached; a frame only slides and tears them.
_MOSH_COLOURS = (                                    # (rgb, weight)
    ((4, 6, 22), 9), ((10, 22, 90), 8), ((22, 70, 210), 7), ((40, 130, 255), 6),
    ((0, 205, 255), 4), ((160, 230, 255), 2), ((255, 248, 235), 1.2), ((255, 50, 105), 2),
    ((215, 25, 55), 1.5), ((255, 125, 30), 1.4), ((255, 205, 110), 0.8), ((120, 40, 210), 1.5))


def _mosh_colour(rnd):
    tot = sum(w for _, w in _MOSH_COLOURS)
    r = rnd.uniform(0, tot)
    for c, w in _MOSH_COLOURS:
        r -= w
        if r <= 0:
            return c
    return _MOSH_COLOURS[0][0]


def _mosh_band(side, bw, bh, rnd):
    """One edge's streaks, alpha already fading toward the middle."""
    img = QtGui.QImage(bw, bh, QtGui.QImage.Format_ARGB32_Premultiplied)
    img.fill(QtCore.Qt.transparent)
    q = QtGui.QPainter(img)
    q.setPen(QtCore.Qt.NoPen)
    horiz = side in "TB"
    span, depth = (bw, bh) if horiz else (bh, bw)
    x = 0
    while x < span:
        run = rnd.choice((1, 1, 2, 2, 3, 4, 6, 9, 14))
        rgb = _mosh_colour(rnd)
        v = rnd.uniform(0.6, 1.25)
        c = QtGui.QColor(min(255, int(rgb[0] * v)), min(255, int(rgb[1] * v)), min(255, int(rgb[2] * v)))
        L = depth * (rnd.uniform(0.12, 1.0) ** 0.8)            # uneven streak length
        # gradient along the streak: bright at the edge -> full colour -> gone
        if side == "T":
            g = QtGui.QLinearGradient(0, 0, 0, L)
        elif side == "B":
            g = QtGui.QLinearGradient(0, bh, 0, bh - L)
        elif side == "L":
            g = QtGui.QLinearGradient(0, 0, L, 0)
        else:
            g = QtGui.QLinearGradient(bw, 0, bw - L, 0)
        hot = QtGui.QColor(min(255, c.red() + 60), min(255, c.green() + 60), min(255, c.blue() + 60))
        g.setColorAt(0.0, hot)
        g.setColorAt(0.25, c)
        mid = QtGui.QColor(c); mid.setAlpha(150)
        g.setColorAt(0.7, mid)
        end = QtGui.QColor(c); end.setAlpha(0)
        g.setColorAt(1.0, end)
        if horiz:
            r = QtCore.QRectF(x, 0 if side == "T" else bh - L, run, L)
        else:
            r = QtCore.QRectF(0 if side == "L" else bw - L, x, L, run)
        q.fillRect(r, QtGui.QBrush(g))
        if run >= 3 and rnd.random() < 0.18:                    # a hot core down the middle of the streak
            core = QtGui.QColor(255, 255, 255, rnd.randint(90, 200))
            if horiz:
                q.fillRect(QtCore.QRectF(x + run // 2, r.y(), 1, r.height() * 0.7), core)
            else:
                q.fillRect(QtCore.QRectF(r.x(), x + run // 2, r.width() * 0.7, 1), core)
        x += run
    q.end()
    return img


def make_mosh(rect, amount=1.0, seed=None):
    """A fresh mosh state: the tears + RGB drift. Bands are built lazily in paint_mosh."""
    import random
    rnd = random.Random(seed)
    W, H = int(rect.width()), int(rect.height())
    st = {"seed": rnd.random(), "bands": {}, "tears": [], "split": rnd.choice((2, 3, 5, 8)),
          "drift": 0.0}
    for _ in range(rnd.randint(2, int(3 + 5 * amount))):
        side = rnd.choice("TBLR")
        span = W if side in "TB" else H
        st["tears"].append((side, rnd.uniform(0, 0.9), rnd.uniform(0.04, 0.3),
                            rnd.uniform(-0.15, 0.15) * span))
    return st


def paint_mosh(p, rect, s, level, st):
    import random
    base = QtGui.QColor(s["vignette_color"])
    if not base.isValid():
        base = QtGui.QColor(0, 0, 0)
    depth = int(float(s["vignette_width"]) * 1.6)
    a = max(0.0, min(1.0, float(s["vignette_strength"]) * level))
    x0, y0 = rect.left(), rect.top()
    W, H = int(rect.width()), int(rect.height())
    k = st["split"]
    p.save()
    p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
    # the chosen colour first: a plain fade, so the streaks sit on darkness, not on the UI
    paint_edges(p, rect, dict(s, vignette_style="fade"), level)
    rnd = random.Random(st["seed"])
    for side in "TBLR":
        horiz = side in "TB"
        bw, bh = (W, depth) if horiz else (depth, H)
        key = (side, bw, bh)
        if key not in st["bands"]:
            st["bands"][key] = _mosh_band(side, bw, bh, rnd)
        band = st["bands"][key]
        span = bw if horiz else bh
        at = QtCore.QPointF(*{"T": (x0, y0), "B": (x0, y0 + H - bh), "L": (x0, y0),
                               "R": (x0 + W - bw, y0)}[side])
        slide = (st["drift"] * (1 if side in "TL" else -1)) % span

        def blit(offset, opacity, mode=QtGui.QPainter.CompositionMode_SourceOver, clip=None):
            p.save()
            p.setOpacity(opacity * a)
            p.setCompositionMode(mode)
            full = QtCore.QRectF(at.x(), at.y(), bw, bh)
            p.setClipRect(clip if clip is not None else full)
            for rep in (-1, 0, 1):                       # wrap-around while sliding
                o = rep * span + offset + slide
                p.drawImage(at + (QtCore.QPointF(o, 0) if horiz else QtCore.QPointF(0, o)), band)
            p.restore()

        blit(0, 1.0)
        blit(k * 2, 0.55, QtGui.QPainter.CompositionMode_Plus)          # RGB drift: an added, shifted copy
        for tside, where, thick, jump in st["tears"]:                   # slices torn sideways
            if tside != side:
                continue
            if horiz:
                clip = QtCore.QRectF(at.x(), at.y() + where * bh, bw, max(2.0, thick * bh))
            else:
                clip = QtCore.QRectF(at.x() + where * bw, at.y(), max(2.0, thick * bw), bh)
            blit(jump, 1.0, clip=clip)
    red = QtGui.QColor(RED); red.setAlphaF(0.75 * level)                # RGB-split rims
    cyan = QtGui.QColor(CYAN); cyan.setAlphaF(0.75 * level)
    p.fillRect(QtCore.QRectF(x0 + k, y0 + k, W - 2 * k, 2), red)
    p.fillRect(QtCore.QRectF(x0 + k, y0 + k, 2, H - 2 * k), red)
    p.fillRect(QtCore.QRectF(x0 + 2 * k, y0 + H - k - 2, W - 3 * k, 2), cyan)
    p.fillRect(QtCore.QRectF(x0 + W - k - 2, y0 + 2 * k, 2, H - 3 * k), cyan)
    p.restore()


_CTRL = {"depth": 0, "last": 0.0,     # depth > 0 while a controlling request is running
         "held_until": 0.0}           # a hold keeps the frame on BETWEEN requests until then


def hold(ttl=5.0):
    """Keep the control frame on for ttl seconds from now (clamped 0.5..120), whatever the
    request count says. A runner renews it every tick; if it dies without cleaning up, the
    frame can stay on at most ttl seconds - a hold never needs a release to end."""
    _CTRL["held_until"] = time.time() + brother_demo_plan.clamp_ttl(ttl)
    if SETTINGS["vignette"]:
        ov = _overlay()
        if ov.ctrl_level < 0.6:
            ov.ctrl_level = 0.6
            ov.repaint()
    return _CTRL["held_until"]


def release_hold():
    _CTRL["held_until"] = 0.0
    _CTRL["last"] = time.time()          # fade out normally (LINGER), not a hard cut


def held():
    return time.time() < _CTRL["held_until"]


# A TASK holds the control frame at full strength from its first step to its last - across every
# request, job and pause in between (Plug 29 Oct: the frame kept fading out while VEX was being
# typed) - and shows a banner saying Esc stops it. The runner beats it each step; a runner that dies
# without ending it lets the frame fade after `ttl` seconds. Esc anywhere in Houdini cancels it: the
# next beat reports cancelled and the runner stops.
_TASK = {"active": False, "label": "", "cancelled": False, "ttl": 20.0}


class _TaskEsc(QtCore.QObject):
    def eventFilter(self, obj, ev):
        if _TASK["active"] and ev.type() == QtCore.QEvent.KeyPress and ev.key() == QtCore.Qt.Key_Escape:
            _TASK["cancelled"] = True
            release_hold()
        return False


_TASK_ESC = {"f": None}


def op_task(args):
    """action = begin | beat | end. begin(label, ttl=20): frame on at full strength + Esc banner.
    beat: renew (returns cancelled=True once Esc was pressed - the runner must stop). end: frame off."""
    action = args.get("action", "beat")
    app = QtWidgets.QApplication.instance()
    if action == "begin":
        _TASK.update(active=True, cancelled=False, label=str(args.get("label") or ""),
                     ttl=float(args.get("ttl", 20.0)))
        if _TASK_ESC["f"] is None:
            _TASK_ESC["f"] = _TaskEsc()
            app.installEventFilter(_TASK_ESC["f"])
        hold(_TASK["ttl"])
        _overlay().show()
    elif action == "beat":
        if _TASK["active"] and not _TASK["cancelled"]:
            hold(_TASK["ttl"])
    elif action == "end":
        _TASK["active"] = False
        if _TASK_ESC["f"] is not None:
            app.removeEventFilter(_TASK_ESC["f"])
            _TASK_ESC["f"] = None
        release_hold()
    return {"active": _TASK["active"], "cancelled": _TASK["cancelled"],
            "seconds_left": round(max(0.0, _CTRL["held_until"] - time.time()), 2)}


def paint_task_banner(p, rect):
    """Plain white text, top centre, while a task is live - no box, no outline (Plug 29 Oct)."""
    text = "%s  \u2014  Press Esc to stop" % (_TASK["label"] or "Brother is working")
    f = QtGui.QFont(p.font()); f.setPointSizeF(11); f.setBold(True)
    p.setFont(f)
    r = QtCore.QRectF(rect.left(), rect.top() + 12, rect.width(), QtGui.QFontMetrics(f).height() + 8)
    p.setPen(WHITE)
    p.drawText(r, QtCore.Qt.AlignCenter, text)


def control(active):
    """brother_link calls this around every request that CHANGES something (click, type,
    create, set, a run that isn't read-only). The edges fade in at once - even a long cook that
    blocks the event loop shows it - and fade out ~1s after the last request ends."""
    # the count is kept whatever the setting says: turning the edges off mid-request used to skip
    # the matching decrement and leave them stuck on once turned back on
    _CTRL["depth"] = _CTRL["depth"] + 1 if active else max(0, _CTRL["depth"] - 1)
    _CTRL["last"] = time.time()
    if not SETTINGS["vignette"]:
        return
    ov = _overlay()
    if active and ov.ctrl_level < 0.6:
        ov.ctrl_level = 0.6
        ov.repaint()
    ov.last_active = time.time()


def paint_cursor(p, x, y, s=None, glitch=None, split=1):
    """Draw the cursor with its tip at (x, y). Shared by the overlay and the settings preview."""
    s = s or SETTINGS
    _, kind, fill, edge = STYLES[s["style"]]
    glitch = glitch or {}
    px = max(1, int(s["scale"]))
    x, y = round(x), round(y)
    p.save()
    if kind == "pixel":
        p.setRenderHint(QtGui.QPainter.Antialiasing, False)                 # crisp pixels
        p.setPen(QtCore.Qt.NoPen)

        def arrow(dx, dy, color_for):
            for r, row in enumerate(ARROW):
                gx = glitch.get(r, 0)
                for c, ch in enumerate(row):
                    col = color_for(ch)
                    if col is not None:
                        p.fillRect(x + dx + (c + gx) * px, y + dy + r * px, px, px, col)

        if s["glitch"] != "off":
            arrow(-px * split, 0, lambda ch: RED if ch != "." else None)    # red ghost, left
            arrow(px * split, px * split, lambda ch: CYAN if ch != "." else None)   # cyan, right/down
        arrow(0, 0, lambda ch: {"B": edge, "W": fill}.get(ch))
        for r, gx in glitch.items():                                        # torn scanline dashes
            if abs(gx) >= 3:
                p.fillRect(x - 8 * px, y + r * px, 5 * px, 1, WHITE)
        tag_at = QtCore.QPointF(x + 12 * px, y + 20 * px)
    elif kind == "smooth":
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        k = px / 2.0 * 1.2
        poly = QtGui.QPolygonF([QtCore.QPointF(x + dx * k, y + dy * k) for dx, dy in SMOOTH])
        p.setBrush(QtCore.Qt.NoBrush)
        for width, alpha in ((14, 0.06), (10, 0.10), (7, 0.16), (4.5, 0.26)):  # white glow
            g = QtGui.QColor(WHITE); g.setAlphaF(alpha)
            p.setPen(QtGui.QPen(g, width * k, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            p.drawPolygon(poly)
        p.setPen(QtGui.QPen(edge, 1.2)); p.setBrush(fill)
        p.drawPolygon(poly)
        tag_at = QtCore.QPointF(x + 16 * k, y + 24 * k)
    else:                                                                    # presenter dot
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        r = 5 * px
        x, y = x + r, y + r                                              # tip = top-left of the dot
        for grow, alpha in ((10, 0.08), (6, 0.16), (3, 0.3)):
            g = QtGui.QColor(fill); g.setAlphaF(alpha)
            p.setPen(QtCore.Qt.NoPen); p.setBrush(g)
            p.drawEllipse(QtCore.QPointF(x, y), r + grow, r + grow)
        p.setPen(QtGui.QPen(edge, 1.5)); p.setBrush(fill)
        p.drawEllipse(QtCore.QPointF(x, y), r, r)
        tag_at = QtCore.QPointF(x + r + 6, y + r + 2)
    text = str(s["label"]).strip()
    if s["show_label"] and text:                                            # name tag
        f = p.font(); f.setPointSize(8); f.setBold(True); p.setFont(f)
        tag = QtCore.QRectF(tag_at.x(), tag_at.y(), 8 + 7 * len(text), 16)
        p.setPen(QtCore.Qt.NoPen)
        if kind == "pixel":
            p.fillRect(tag, BLACK)
            k2 = split if s["glitch"] != "off" else 0
            if k2:
                p.setPen(RED); p.drawText(tag.translated(-k2, 0), QtCore.Qt.AlignCenter, text)
                p.setPen(CYAN); p.drawText(tag.translated(k2, 0), QtCore.Qt.AlignCenter, text)
            p.setPen(WHITE)
        else:
            bg = fill if kind == "dot" else (BLACK if fill.lightness() < 128 else WHITE)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            p.setBrush(bg); p.drawRoundedRect(tag, 4, 4)
            p.setPen(WHITE if bg.lightness() < 160 else BLACK)
        p.drawText(tag, QtCore.Qt.AlignCenter, text)
    p.restore()


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
        self.last_active = time.time()
        self.last_move = 0.0
        self.glitch, self.split = {}, 1
        self.has_cursor = False          # only draw the arrow once Brother has actually moved it
        self.ctrl_level = 0.0            # 0..1, eased - the edge fade's opacity
        self.edge_slices, self.edge_split = [], 1
        self.mosh = None
        self.wire = None                 # (QPointF, QPointF) - a wire being pulled, drawn only
        self._follow()
        main.installEventFilter(self)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)
        self.show()

    # the 30 ms animation only runs while the overlay is on screen
    def showEvent(self, e):
        self._timer.start(30)
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

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
        import random
        moving = now - self.last_move < 0.15
        amount = SETTINGS["glitch"] if STYLES[SETTINGS["style"]][1] == "pixel" else "off"
        rate = {"off": 0.0, "calm": 0.55 if moving else 0.12, "wild": 0.9 if moving else 0.4}[amount]
        if random.random() < rate:                               # a new glitch: 1-3 rows jump
            self.glitch = {random.randrange(len(ARROW)): random.choice((-3, -2, 2, 3, 4))
                           for _ in range(random.randint(1, 3))}
            self.split = random.choice((1, 1, 2, 3)) if moving else random.choice((1, 1, 1, 2))
        elif random.random() < 0.5:
            self.glitch, self.split = {}, 1
        self.ripples = [r for r in self.ripples if now - r[1] < 0.6]
        target = brother_demo_plan.edge_target(_CTRL["depth"], _CTRL["last"],
                                               _CTRL["held_until"], now)
        self.ctrl_level += (target - self.ctrl_level) * (0.25 if target > self.ctrl_level else 0.12)
        if self.ctrl_level < 0.005:
            self.ctrl_level = 0.0
        if self.ctrl_level > 0 and SETTINGS.get("vignette_style") == "mosh":
            amount = {"off": 0.3, "calm": 0.7, "wild": 1.3}[SETTINGS["glitch"]]
            if self.mosh is None or random.random() < 0.012 * (0.5 + amount):  # new streaks every few s (~56 ms to build)
                self.mosh = make_mosh(QtCore.QRectF(self.rect()), amount)
            else:
                self.mosh["drift"] += 1.5 + 3 * amount                       # the streaks slide
                if random.random() < 0.3 * amount:                           # ...and tear anew
                    fresh = make_mosh(QtCore.QRectF(self.rect()), amount)
                    self.mosh["tears"], self.mosh["split"] = fresh["tears"], fresh["split"]
        if self.ctrl_level > 0 and SETTINGS.get("vignette_style") == "glitch":
            if random.random() < 0.35:                   # the edge tears re-roll a few times a second
                self.edge_slices = make_edge_glitch(QtCore.QRectF(self.rect()),
                                                    {"off": 0.3, "calm": 0.7, "wild": 1.3}[SETTINGS["glitch"]])
                self.edge_split = random.choice((1, 1, 2, 3))
            elif random.random() < 0.25:
                self.edge_slices, self.edge_split = [], 1
        if self.ctrl_level == 0.0:
            self.mosh = None                                               # built once per showing, not per frame
        if brother_demo_plan.should_hide(now, self.last_active, self.ripples, self.ctrl_level,
                                         _CTRL["held_until"]):
            self.hide()                                                    # idle: fade out of the way
        self.update()

    def paintEvent(self, _):
        # guarded: a Python error while a QPainter is open crashes all of Houdini (signal 11)
        p = QtGui.QPainter(self)
        try:
            self._paint(p)
        except Exception as e:
            print("%s paint error: %s" % (type(self).__name__, e))
        finally:
            if p.isActive():
                p.end()

    def _paint(self, p):
        p.setCompositionMode(QtGui.QPainter.CompositionMode_Source)       # wipe the last frame: no trails
        p.fillRect(self.rect(), QtCore.Qt.transparent)
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        now = time.time()
        if SETTINGS["vignette"] and self.ctrl_level > 0:
            if SETTINGS.get("vignette_style") == "mosh":
                if self.mosh is None:
                    self.mosh = make_mosh(QtCore.QRectF(self.rect()))
                paint_mosh(p, QtCore.QRectF(self.rect()), SETTINGS, self.ctrl_level, self.mosh)
            else:
                paint_edges(p, QtCore.QRectF(self.rect()), SETTINGS, self.ctrl_level,
                            self.edge_slices, self.edge_split)
        for pt, t0 in (self.ripples if SETTINGS["ripples"] else ()):        # click ripples
            k = (now - t0) / 0.6
            c = QtGui.QColor(WHITE); c.setAlphaF(max(0.0, 0.8 * (1 - k)))
            p.setPen(QtGui.QPen(c, 3)); p.setBrush(QtCore.Qt.NoBrush)
            r = 6 + 26 * k
            p.drawEllipse(pt, r, r)
        if self.wire is not None:                                           # a wire being pulled
            a, b = self.wire
            for width, alpha in ((9, 0.12), (5, 0.25)):
                g = QtGui.QColor(WHITE); g.setAlphaF(alpha)
                p.setPen(QtGui.QPen(g, width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
                p.drawLine(a, b)
            p.setPen(QtGui.QPen(PINK, 2.5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
            p.drawLine(a, b)
            p.setBrush(PINK); p.drawEllipse(a, 4, 4)
        if _TASK["active"] and not _TASK["cancelled"]:
            paint_task_banner(p, QtCore.QRectF(self.rect()))
        if self.has_cursor:
            paint_cursor(p, self.pos_.x(), self.pos_.y(), SETTINGS, self.glitch, self.split)


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


def _glide(to, seconds=None, speed=1.0):
    ov = _overlay()
    a = QtCore.QPointF(ov.pos_)
    b = QtCore.QPointF(*to)
    dist = math.hypot(b.x() - a.x(), b.y() - a.y())
    seconds = seconds if seconds is not None else min(0.9, 0.25 + dist / 1800.0) / max(speed, 0.1)
    t0 = time.time()
    app = QtWidgets.QApplication.instance()
    while True:
        k = min(1.0, (time.time() - t0) / seconds) if seconds > 0 else 1.0
        e = ease_in_out_quint(k)                                            # ease in-out (strong)
        ov.pos_ = QtCore.QPointF(a.x() + (b.x() - a.x()) * e, a.y() + (b.y() - a.y()) * e)
        ov.last_active = ov.last_move = time.time()
        ov.has_cursor = True
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
    # A window a key just opened (Houdini's TAB menu is its own RE_Window, not a Qt popup)
    # owns the keyboard while it is up; then a Qt popup; then focus; then the last click.
    pw = _ov.get("popup")
    try:
        if pw is not None and pw.isVisible():
            return app, (_deepest(pw) or pw)
    except RuntimeError:
        pass
    _ov["popup"] = None
    w = app.activePopupWidget() or app.focusWidget() or _ov.get("last")
    if w is None:
        raise RuntimeError("nothing to type into - click the field first")
    return app, w


def _deepest(win):
    """The widget inside a window that actually draws/handles input (Houdini: RE_GLDrawable)."""
    c = win.childAt(win.rect().center())
    return c or win


def _new_windows(before):
    ov = _ov.get("w")
    return [w for w in QtWidgets.QApplication.topLevelWidgets()
            if w.isVisible() and w not in before and w is not ov and w is not _main()]


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
    before = set(QtWidgets.QApplication.topLevelWidgets())
    _send_key(app, w, key, "" if mods != QtCore.Qt.NoModifier or k in _KEYS else k, mods)
    _pump(0.35)
    opened = _new_windows(before)
    if opened:                                   # e.g. Tab opened the TAB menu: type into it next
        _ov["popup"] = opened[-1]
    return {"key": args["key"], "into": _describe(w),
            "opened": [_describe(_deepest(o)) for o in opened]}


def _network_editor_at(x, y):
    """The Network Editor pane under a main-window point, and that point in network coords.

    The whole main window is ONE OpenGL surface - panes are not Qt widgets - so Qt can't say
    which pane is where. qtScreenGeometry() can: it is the pane tab's rect on screen, toolbar
    included. screenBounds() is the network drawing area only, which is the BOTTOM part of that
    rect, and Houdini counts its pixels from the bottom-left (Qt from the top-left)."""
    mw = _main()
    gp = mw.mapToGlobal(QtCore.QPoint(int(x), int(y)))
    for ne in hou.ui.paneTabs():
        if ne.type() != hou.paneTabType.NetworkEditor or not ne.isCurrentTab():
            continue
        g = ne.qtScreenGeometry()
        w, h = ne.screenBounds().size()
        bottom = g.y() + g.height()
        lx, ly = gp.x() - g.x(), bottom - gp.y()
        if 0 <= lx <= w and 0 <= ly <= h:
            return ne, ne.posFromScreen(hou.Vector2(lx, ly))
    raise RuntimeError("(%d, %d) is not over a Network Editor's drawing area" % (x, y))


def op_create_node(args):
    """Glide to (x, y) in a Network Editor, click there, and create a node of `type` right
    under the cursor - as ONE 'Brother:' undo step. The TAB menu can't be used for this:
    Houdini opens it at Plug's REAL mouse position, so the node would land there instead.
    speed (default 1): >1 shortens the glide and the pauses by that factor."""
    x, y = args["x"], args["y"]
    speed = max(float(args.get("speed", 1.0)), 0.1)
    ov = _glide((x, y), speed=speed)
    ne, pos = _network_editor_at(x, y)
    ov.ripples.append((QtCore.QPointF(x, y), time.time()))
    _pump(0.15 / speed)
    parent = ne.pwd()
    with hou.undos.group("Brother: create %s" % args["type"]):
        n = parent.createNode(args["type"], args.get("name") or None)
        n.setPosition(pos - n.size() * 0.5)
        if args.get("input"):
            n.setInput(0, parent.node(args["input"]) or hou.node(args["input"]))
        n.setSelected(True, clear_all_selected=True)
    _pump(0.3 / speed)
    return {"created": n.path(), "type": n.type().name(), "network_pos": list(n.position()),
            "undo_label": "Brother: create %s" % args["type"]}


def op_cursor_hide(args):
    remove()
    return {"hidden": True}


# ----------------------------------------------------------------------------- hold + drag
def op_control_hold(args):
    """action = start | beat | stop. start/beat keep the control frame on for ttl seconds
    (default 8, max 120) so it does not drop between an AI's tool calls; stop lets it fade."""
    action = args.get("action", "start")
    if action == "stop":
        release_hold()
        return {"held": False}
    until = hold(args.get("ttl", 8.0))
    return {"held": True, "seconds_left": round(until - time.time(), 2)}


def net_point(ne, pos):
    """A network-space position -> main-window pixels (same mapping as _node_point, no pan)."""
    vb, (w, h) = ne.visibleBounds(), ne.screenBounds().size()
    s = ((pos[0] - vb.min()[0]) / (vb.max()[0] - vb.min()[0]) * w,
         (pos[1] - vb.min()[1]) / (vb.max()[1] - vb.min()[1]) * h)
    g = ne.qtScreenGeometry()
    p = _main().mapFromGlobal(QtCore.QPoint(int(g.x() + s[0]), int(g.y() + g.height() - s[1])))
    return (p.x(), p.y())


def drag_frames(a, b, seconds=0.8, wire=False):
    """A REAL drag: left press at a, a MouseMove every frame with the button held, release at b
    - Qt events to the widget under a, with the cursor drawn along. A generator: each yield is
    one frame, so a runner can stop between frames. The release is in `finally`: closing the
    generator early (Stop, Esc, an error) still lets the button go, so no input is left stuck."""
    ov = _overlay()
    w, _, _ = _target(*a)
    mw, app = _main(), QtWidgets.QApplication.instance()
    left, none = QtCore.Qt.LeftButton, QtCore.Qt.NoButton

    def send(kind, pt, btn, btns):
        gp = mw.mapToGlobal(QtCore.QPoint(int(pt[0]), int(pt[1])))
        lp = QtCore.QPointF(w.mapFromGlobal(gp))
        with hou.undos.disabler():
            app.sendEvent(w, QtGui.QMouseEvent(kind, lp, lp, QtCore.QPointF(gp), btn, btns,
                                               QtCore.Qt.NoModifier))

    pressed, last = False, a
    try:
        send(QtCore.QEvent.MouseMove, a, none, none)
        send(QtCore.QEvent.MouseButtonPress, a, left, left)
        pressed = True
        ov.ripples.append((QtCore.QPointF(*a), time.time()))
        t_end = time.time() + 0.08
        while time.time() < t_end:
            yield
        t0 = time.time()
        while True:
            k = min(1.0, (time.time() - t0) / seconds)
            e = ease_in_out_quint(k)
            last = (a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e)
            ov.pos_ = QtCore.QPointF(*last)
            ov.last_active = ov.last_move = time.time()
            ov.has_cursor = True
            ov.wire = None        # no pink guide (Plug 29 Oct); a real port drag shows Houdini's own wire
            send(QtCore.QEvent.MouseMove, last, none, left)
            ov.update()
            if k >= 1.0:
                break
            yield
    finally:
        if pressed:
            send(QtCore.QEvent.MouseButtonRelease, last, left, none)
        ov.wire = None
        ov.update()


def op_drag(args):
    """Press at (x0, y0), move with the button held, release at (x1, y1) - a real, visible
    drag (e.g. a node in a Network Editor). Reports what it pressed on; whether the target
    accepted it as a drag is for the caller to check (e.g. did the node move).
    In a Network Editor it selects / rubber-bands, but only moves a node when the editor is
    visible (not covered by another window) at the pointer - see "EVENT PATH, MEASURED" below.
    Use move_node / wire_nodes there; this stays for Qt-native widgets and event tests."""
    a, b = (args["x0"], args["y0"]), (args["x1"], args["y1"])
    _glide(a)
    w, _, _ = _target(*a)
    app = QtWidgets.QApplication.instance()
    for _ in drag_frames(a, b, float(args.get("seconds", 0.8)), bool(args.get("wire"))):
        app.processEvents(QtCore.QEventLoop.AllEvents, 10)
        time.sleep(0.012)
    _pump(0.2)
    return {"pressed": list(a), "released": list(b), "widget": _describe(w)}


# ----------------------------------------------------------------------------- panes by API
# Nodes and panes can be FOUND through hou, no picture needed: a pane tab knows its rect on
# screen (qtScreenGeometry), a Network Editor can turn a node position into a pixel
# (posToScreen), and a Parameter pane that shares a Network Editor's link group shows
# whatever is selected there. Only the fields INSIDE a Parameter pane have no API.
def _pane_rect(tab):
    """A pane tab's rect in main-window coordinates (the click space)."""
    g = tab.qtScreenGeometry()
    tl = _main().mapFromGlobal(QtCore.QPoint(g.x(), g.y()))
    return QtCore.QRect(tl.x(), tl.y(), g.width(), g.height())


def _current_tabs(kind):
    return [t for t in hou.ui.paneTabs() if t.type() == kind and t.isCurrentTab()]


def _editor_for(node):
    """A visible Network Editor showing node's parent network - switching one there if none
    already is (that is a visible jump, like clicking the path bar)."""
    parent = node.parent()
    eds = _current_tabs(hou.paneTabType.NetworkEditor)
    if not eds:
        raise RuntimeError("no Network Editor is open on this desktop")
    for ne in eds:
        if ne.pwd() == parent:
            return ne
    ne = eds[0]
    ne.setPwd(parent)
    _pump(0.2)
    return ne


def _node_point(ne, node):
    """Where a real press on `node` lands (its header, from the editor's own hit-test), in
    main-window pixels, panning the editor first if it is off screen. NOT pos+size*0.5 - that
    point is offset from the drawn tile (see _native_hits)."""
    px, _ = _native_anchor(ne, node, "body")
    return _px_to_main(ne, px)


def _editor_px(ne, pos):
    """Network position -> editor pixels (bottom-origin), mapped through visibleBounds (current
    even right after a pan, unlike posToScreen)."""
    vb, (w, h) = ne.visibleBounds(), ne.screenBounds().size()
    return ((pos[0] - vb.min()[0]) / (vb.max()[0] - vb.min()[0]) * w,
            (pos[1] - vb.min()[1]) / (vb.max()[1] - vb.min()[1]) * h)


def _px_to_main(ne, s):
    """Editor pixels (bottom-origin) -> main-window pixels (the overlay / click space)."""
    g = ne.qtScreenGeometry()
    return _main().mapFromGlobal(QtCore.QPoint(int(round(g.x() + s[0])),
                                               int(round(g.y() + g.height() - s[1]))))


def _native_hits(ne, node, step=2):
    """The editor's OWN hit items for `node`, from networkItemsInBox (the same hit-test a real
    click uses), as {(kind, index): [x0, y0, x1, y1]} in editor pixels, bottom-origin.
    Measured 2026-10-25: node.position()/size() through posToScreen is NOT where the tile is
    drawn (offset by ~15 px x / ~60 px y on a COP wrangle), and COP ports are dots in the bottom
    row (input left, output right), not the top/bottom edge centres - so press/anchor points come
    from here, never from pos+size*0.5."""
    lo, hi = _editor_px(ne, node.position()), _editor_px(ne, node.position() + node.size())
    h = max(8.0, hi[1] - lo[1])
    x0, x1, y0, y1 = int(lo[0] - h), int(hi[0] + h), int(lo[1] - 2 * h), int(hi[1] + h)
    out = {}
    for y in range(y0, y1, step):
        for x in range(x0, x1, step):
            # for_select=False: with True the editor leaves out connector items (ports)
            for it in ne.networkItemsInBox(hou.Vector2(x, y), hou.Vector2(x + step, y + step),
                                           for_select=False):
                if it[0] != node:
                    continue
                key = (it[1], it[2] if len(it) > 2 else -1)
                b = out.get(key)
                out[key] = [x, y, x + step, y + step] if b is None else \
                    [min(b[0], x), min(b[1], y), max(b[2], x + step), max(b[3], y + step)]
    return out


def _box_centre(b):
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


_DRAWN = {}      # node path -> (node's editor px when its hits were read, hits)


def _shift_hits(hits, frm, to):
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    return {k: [b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy] for k, b in hits.items()}


def _ensure_on_screen(ne, node):
    s = _editor_px(ne, node.position() + node.size() * 0.5)
    w, h = ne.screenBounds().size()
    if not (60 <= s[0] <= w - 60 and 60 <= s[1] <= h - 60):
        vb = ne.visibleBounds()
        vb.translate(node.position() + node.size() * 0.5 - vb.center())
        ne.setVisibleBounds(vb)
        _pump(0.2)


def _native_anchor(ne, node, kind="body", index=0):
    """Where a REAL press would land for `node`, from the editor's hit-test, in editor pixels
    (bottom-origin). kind: body (the node header, which drags/selects) | input | output.
    Returns (pixel, hit_kind) or raises if the editor reports no such item on screen.

    MEASURED: networkItemsInBox answers from the LAST PAINTED frame, and the editor only paints
    once the running Python call returns. So hits are read where the node is DRAWN; the item's
    offset from the node's drawn pixel is then re-applied to where the node is NOW (and to the
    view after any pan). A node moved earlier in the same call, before any paint, is therefore
    still anchored correctly as long as it was drawn somewhere on screen."""
    hits = _native_hits(ne, node)
    drawn = _DRAWN.get(node.path())
    if hits:
        _DRAWN[node.path()] = drawn = (tuple(_editor_px(ne, node.position())), hits)
    if drawn is None:
        _ensure_on_screen(ne, node)
        raise RuntimeError("the Network Editor has not drawn %s yet (not on screen when last "
                           "painted) - retry after Houdini repaints" % node.path())
    hits = _shift_hits(drawn[1], drawn[0], _editor_px(ne, node.position()))
    s = _editor_px(ne, node.position() + node.size() * 0.5)
    w, h = ne.screenBounds().size()
    if not (60 <= s[0] <= w - 60 and 60 <= s[1] <= h - 60):     # pan, then shift by the pan
        b0 = _editor_px(ne, node.position())
        _ensure_on_screen(ne, node)
        hits = _shift_hits(hits, b0, _editor_px(ne, node.position()))
    if kind == "body":
        for k in ("node", "preview", "connectorarea"):
            boxes = [b for (kk, _), b in hits.items() if kk == k]
            if boxes:
                return _box_centre(boxes[0]), k
    else:
        b = hits.get((kind, index))
        if b:
            return _box_centre(b), kind
    raise RuntimeError("the Network Editor reports no %s%s hit for %s (found: %s)"
                       % (kind, "" if kind == "body" else " %d" % index, node.path(),
                          sorted(set(k for k, _ in hits))))


def editor_visible_at(ne, px):
    """Is the editor itself visible at this editor pixel (not covered by another app's window)?
    hou's own isPosInside(pos, False) - the test the node-move handler uses: when it is False an
    event drag is treated as 'dragged out of the view' and the node does not move."""
    return bool(ne.isPosInside(hou.Vector2(*px), False))


def _parm_pane_for(ne, node):
    """The Parameter pane that shows `node` after it is selected in `ne`: one already on it,
    else one in the editor's link group, else any unpinned one."""
    panes = _current_tabs(hou.paneTabType.Parm)
    for pp in panes:
        if pp.currentNode() == node:
            return pp
    for pp in panes:
        if ne.linkGroup() != hou.paneLinkType.Pinned and pp.linkGroup() == ne.linkGroup():
            return pp
    for pp in panes:
        if not pp.isPin():
            return pp
    return None


def op_click_node(args):
    """Glide to a node and click it (double=True dives into it), found by path - no screenshot.
    Switches or pans a Network Editor first when the node isn't on screen."""
    node = hou.node(args["path"])
    if node is None:
        raise ValueError("no node %r" % args["path"])
    ne = _editor_for(node)
    p = _node_point(ne, node)
    res = op_click({"x": p.x(), "y": p.y(), "double": args.get("double", False)})
    pp = _parm_pane_for(ne, node)
    r = _pane_rect(pp) if pp is not None else None
    return {"node": node.path(), "clicked": res["clicked"], "network_editor": ne.name(),
            "parm_pane": pp.name() if pp is not None else None,
            "parm_pane_rect": [r.x(), r.y(), r.width(), r.height()] if r is not None else None}


def op_pane_screenshot(args):
    """Just one pane, cropped (much smaller for Brother to read than the whole window).
    kind = parm | network | viewer, or pane = a pane tab name. offset + a pixel in this
    image = the main-window point to click."""
    kinds = {"parm": hou.paneTabType.Parm, "network": hou.paneTabType.NetworkEditor,
             "viewer": hou.paneTabType.SceneViewer}
    if args.get("pane"):
        tabs = [t for t in hou.ui.paneTabs() if t.name() == args["pane"]]
    elif args.get("node"):                      # the Parameter pane showing this node
        node = hou.node(args["node"])
        tabs = [t for t in _current_tabs(hou.paneTabType.Parm) if t.currentNode() == node]
    else:
        tabs = _current_tabs(kinds[args.get("kind", "parm")])
    if not tabs:
        raise RuntimeError("no such pane is visible")
    tab = tabs[int(args.get("index", 0))]
    r = _pane_rect(tab)
    full = op_screenshot({})
    img = QtGui.QImage(full["file"]).copy(r)
    path = full["file"].replace(".png", "_%s.png" % tab.name())
    img.save(path, "PNG")
    return {"file": path, "pane": tab.name(), "type": tab.type().name(),
            "offset": [r.x(), r.y()], "width": r.width(), "height": r.height(),
            "shows": tab.currentNode().path() if tab.type() == hou.paneTabType.Parm and tab.currentNode() else None}


def op_capture_pane(args):
    """The Network Editor as Houdini drew it, EVEN WHEN another window covers it. Uses Win32
    PrintWindow(PW_RENDERFULLCONTENT) on Houdini's own window, so nothing is raised or focused
    and the cursor is untouched. Fails closed on a hidden/wrong/unknown pane or a black image.
    The result says whether the pane was covered at the time (`occlusion`)."""
    import importlib
    import brother_capture as bcap
    importlib.reload(bcap)
    folder = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".houdini_brother")
    try:
        meta, _img, _png = bcap.capture_pane(pane_name=args.get("pane") or None, save_dir=folder,
                                             tag="capture_%d" % os.getpid())
    except bcap.CaptureError as e:
        raise RuntimeError("capture refused: %s" % e)
    meta["file"] = meta.pop("path")
    return meta


def op_set_parm_shown(args):
    """Set a parm through the API - exact, one 'Brother:' undo step - while the cursor shows
    Plug where: it clicks the node (so its Parameter pane shows it), then glides to the field
    at (x, y) if Brother knows it (e.g. read from pane_screenshot), else to the pane itself."""
    node = hou.node(args["path"])
    if node is None:
        raise ValueError("no node %r" % args["path"])
    shown = op_click_node({"path": node.path()})
    _pump(0.2)
    if args.get("x") is not None:
        at = (args["x"], args["y"])
    elif shown["parm_pane_rect"]:
        x, y, w, h = shown["parm_pane_rect"]
        at = (x + min(w * 0.3, 220), y + 70)
    else:
        at = None
    if at:
        ov = _glide(at)
        ov.ripples.append((QtCore.QPointF(*at), time.time()))
    import sys
    res = sys.modules["brother_link"].op_set_parm(args)
    _pump(0.3)
    res.update({"parm_pane": shown["parm_pane"], "pointed_at": list(at) if at else None})
    return res


# ----------------------------------------------------------------------------- API-backed graph actions
# EVENT PATH, MEASURED (2026-10-25, Houdini 21.0.671, Windows, isolated /obj/BROTHER_INDEP_REG,
# OS cursor untouched, no setPosition in the test). This REPLACES an earlier note that said the
# editor ignores injected input - that was wrong (those tests ran inline, with no event-loop turn
# between press and release, and pressed at pos+size*0.5, which is not where the tile is drawn):
#   - QMouseEvent move/press/release sent to the RE_GLDrawable QWidget AS A JOB (frames between)
#     reaches nodegraph.handleEvent as mousedown/mousedrag/mouseup with selected=<node>/node,
#     dragging=1, lmb=1. A click on the native header SELECTS the node; a background drag makes a
#     working rubber-band selection.
#   - A press+drag on the header reaches NodeMouseHandler -> NodeMoveHandler, which then REFUSES
#     to move: MovableItemMoveHandler resets the drag to 0 whenever editor.isPosInside(mousepos,
#     False) is False, i.e. "the pointer has left the view" (drag-and-drop to another app). That
#     test asks the OS which window is visible at the point; with another app's window covering
#     Houdini there (measured: a maximized Chrome tab over the whole editor) it is False for every
#     pixel, so the node cannot move by event - by Houdini's design, not by blocked input.
#   - So a genuine event-driven node move needs the editor visible at the pointer. Bringing
#     Houdini forward would take Plug's focus, so Brother does not do it. The actions below change
#     the graph through hou (setSelected / setPosition / setInput) while Brother's own cursor
#     shows where, anchored on the editor's native hit-test: they are API-BACKED, and every
#     result says so in "method" and reports editor_visible_at_anchor.
_API = "api-backed (hou), not an input event"


class _EscWatch(QtCore.QObject):
    """Esc pressed anywhere in Houdini while an action runs -> cancel it."""
    def __init__(self):
        super().__init__()
        self.hit = False

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.KeyPress and ev.key() == QtCore.Qt.Key_Escape:
            self.hit = True
        return False


def _node_centre(node):
    return node.position() + node.size() * 0.5


def ease_in_out_quint(k):
    """Node moves ease hard in and out (Plug 29 Oct: smoothstep's 1.5x mid-speed read as a constant
    slide). Filmed: ~0.25 s of slow start, a fast middle, a slow settle."""
    return 16 * k ** 5 if k < 0.5 else 1 - (-2 * k + 2) ** 5 / 2


def move_frames(node, to_pos, seconds=0.8, anchor_px=None, trace=None):
    """Move `node` to network position `to_pos` (lower-left, like setPosition) visibly: the cursor
    grabs it and the NODE itself travels frame by frame. A generator - each yield is a frame. Done
    -> one 'Brother: move' undo step. Closed early (Esc, Stop, error) -> the node goes back to
    where it was and nothing is left in the undo history.
    anchor_px = the grab point in editor pixels (from _native_anchor); the cursor TIP keeps the
    same offset from the node all the way, so it never drifts off the tile it 'holds'."""
    ne = _editor_for(node)
    start = hou.Vector2(node.position())
    end = hou.Vector2(to_pos)
    if anchor_px is None:
        anchor_px, _ = _native_anchor(ne, node, "body")
    s0 = _editor_px(ne, start)
    off = (anchor_px[0] - s0[0], anchor_px[1] - s0[1])
    done = False
    try:
        t0 = time.time()
        while True:
            k = min(1.0, (time.time() - t0) / seconds) if seconds > 0 else 1.0
            e = ease_in_out_quint(k)
            p = start + (end - start) * e
            with hou.undos.disabler():
                node.setPosition(p)
            ov = _overlay()
            sp = _editor_px(ne, p)
            tip = _px_to_main(ne, (sp[0] + off[0], sp[1] + off[1]))
            ov.pos_ = QtCore.QPointF(tip)
            if trace is not None:
                trace.append({"k": round(k, 3), "pos": [round(p[0], 4), round(p[1], 4)],
                              "tip_main": [tip.x(), tip.y()], "grab_off_px": list(off)})
            ov.last_active = ov.last_move = time.time()
            ov.has_cursor = True
            ov.update()
            if k >= 1.0:
                break
            yield
        done = True
    finally:
        with hou.undos.disabler():
            node.setPosition(start)
        if done:                                   # one clean undo step: start -> end
            with hou.undos.group("Brother: move %s" % node.name()):
                node.setPosition(end)


def _run(frames, budget=10.0, on_frame=None):
    """Drive a frame generator on the main thread, bounded in time, cancellable with Esc.
    on_frame(i) is called after each frame (tests use it to record and to inject an Esc)."""
    app = QtWidgets.QApplication.instance()
    watch = _EscWatch()
    app.installEventFilter(watch)
    end = time.time() + budget
    reason = None
    try:
        for i, _ in enumerate(frames):
            app.processEvents(QtCore.QEventLoop.AllEvents, 10)
            if on_frame:
                on_frame(i)
            if watch.hit:
                reason = "esc"
            elif time.time() > end:
                reason = "time budget"
            if reason:
                frames.close()                    # runs the generator's finally: cleanup/undo
                break
            time.sleep(0.012)
    finally:
        frames.close()                            # an error mid-run cleans up the same way
        app.removeEventFilter(watch)
    return reason


# Houdini's Network Editor only REPAINTS once the running Python call returns - a node moved
# inside one call is drawn only at its final place (measured: ne.redraw() / hou.ui.triggerUpdate
# don't help mid-call). So by default an action runs as a JOB on Houdini's own event loop: the
# op returns at once, a QTimer advances one frame per tick, and Houdini paints between ticks -
# the node is seen travelling, and Plug's own input to Houdini keeps flowing meanwhile.
_JOBS = {}


class _Job(QtCore.QObject):
    def __init__(self, jid, frames, budget, report):
        super().__init__()
        self.jid, self.frames, self.report = jid, frames, report
        self.state, self.reason, self.t0, self.end = "running", None, time.time(), time.time() + budget
        self.watch = _EscWatch()
        QtWidgets.QApplication.instance().installEventFilter(self.watch)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(15)

    def stop(self, reason="stop"):
        if self.state == "running":
            self._finish(reason)

    def _tick(self):
        try:
            next(self.frames)
        except StopIteration:
            return self._finish(None)
        except Exception as e:                    # the generator's finally already cleaned up
            return self._finish("error: %s" % e)
        if self.watch.hit:
            self._finish("esc")
        elif time.time() > self.end:
            self._finish("time budget")

    def _finish(self, reason):
        self.timer.stop()
        try:
            self.frames.close()                   # runs the finally: restore or commit + undo
        finally:
            QtWidgets.QApplication.instance().removeEventFilter(self.watch)
            self.state, self.reason = ("cancelled" if reason else "done"), reason
            self.seconds = round(time.time() - self.t0, 3)


def _start(frames, budget, report):
    jid = "job%d" % (len(_JOBS) + 1)
    _JOBS[jid] = _Job(jid, frames, budget, report)
    return jid


def _job(jid):
    if jid not in _JOBS:
        raise ValueError("no job %r (known: %s)" % (jid, ", ".join(_JOBS) or "none"))
    return _JOBS[jid]


def op_action_status(args):
    j = _job(args["job"])
    out = {"job": j.jid, "state": j.state, "cancelled": j.reason, "method": _API}
    if j.state != "running":
        out.update(j.report())
        out["seconds"] = j.seconds
    return out


def op_action_stop(args):
    """Stop a running job (or every running job); its node goes back / no wire is made."""
    jobs = [_job(args["job"])] if args.get("job") else list(_JOBS.values())
    for j in jobs:
        j.stop(args.get("reason", "stop"))
    return {"stopped": [j.jid for j in jobs]}


def op_select_node(args):
    node = hou.node(args["path"])
    if node is None:
        raise ValueError("no node %r" % args["path"])
    ne = _editor_for(node)
    px, hit = _native_anchor(ne, node, "body")
    p = _px_to_main(ne, px)
    ov = _glide((p.x(), p.y()))
    ov.ripples.append((QtCore.QPointF(p.x(), p.y()), time.time()))
    with hou.undos.group("Brother: select %s" % node.name()):
        node.setSelected(True, clear_all_selected=not args.get("add"))
    _pump(0.2)
    return {"selected": [n.path() for n in hou.selectedNodes()], "method": _API,
            "anchor": {"editor_px": [round(px[0], 1), round(px[1], 1)], "hit": hit,
                       "main_px": [p.x(), p.y()]},
            "editor_visible_at_anchor": editor_visible_at(ne, px)}


def op_move_node(args):
    """Move a node to network position (x, y) - or by (dx, dy) - visibly. API-backed."""
    node = hou.node(args["path"])
    if node is None:
        raise ValueError("no node %r" % args["path"])
    before = list(node.position())
    to = hou.Vector2(args["x"], args["y"]) if "x" in args else \
        hou.Vector2(node.position()) + hou.Vector2(args.get("dx", 0), args.get("dy", 0))
    ne = _editor_for(node)
    px, hit = _native_anchor(ne, node, "body")
    p = _px_to_main(ne, px)
    _glide((p.x(), p.y())).ripples.append((QtCore.QPointF(p.x(), p.y()), time.time()))
    _pump(0.1)
    trace = []
    frames = move_frames(node, to, float(args.get("seconds", 0.8)), anchor_px=px, trace=trace)
    budget = float(args.get("budget", 10.0))
    anchor = {"editor_px": [round(px[0], 1), round(px[1], 1)], "hit": hit, "main_px": [p.x(), p.y()],
              "editor_visible_at_anchor": editor_visible_at(ne, px)}
    report = lambda: {"node": node.path(), "before": before, "after": list(node.position()),
                      "anchor": anchor, "frames": len(trace),
                      "tip_first": trace[0]["tip_main"] if trace else None,
                      "tip_last": trace[-1]["tip_main"] if trace else None,
                      "grab_off_px": trace[0]["grab_off_px"] if trace else None}
    if not args.get("wait"):                      # default: a job - poll action_status
        return dict(report(), job=_start(frames, budget, report), state="running", method=_API)
    reason = _run(frames, budget)
    _pump(0.2)
    return dict(report(), cancelled=reason, method=_API)


def op_wire_nodes(args):
    """Connect src's output to dst's input `input` (default 0), drawing the wire with the cursor
    from one to the other first. API-backed (setInput). Esc during the wire -> no connection."""
    src, dst = hou.node(args["src"]), hou.node(args["dst"])
    if src is None or dst is None:
        raise ValueError("no node %r / %r" % (args["src"], args["dst"]))
    idx = int(args.get("input", 0))
    ne = _editor_for(dst)
    # the REAL port dots from the editor's hit-test (COP: bottom row, input left / output right)
    oidx = int(args.get("output", 0))
    apx, _ = _native_anchor(ne, src, "output", oidx)
    s0 = _editor_px(ne, src.position())
    try:
        bpx, _ = _native_anchor(ne, dst, "input", idx)
    except RuntimeError:                              # Merge & co: one 'multiinput' port, no 'input N'
        bpx, _ = _native_anchor(ne, dst, "multiinput", -1)  # Houdini's key is ('multiinput', -1)
    s1 = _editor_px(ne, src.position())
    if s1 != s0:                                      # panned for dst: src's port moved with it
        apx = (apx[0] + s1[0] - s0[0], apx[1] + s1[1] - s0[1])
        w, h = ne.screenBounds().size()
        if not (0 <= apx[0] <= w and 0 <= apx[1] <= h):
            raise RuntimeError("src and dst do not fit in one view; zoom out first")
    ap, bp = _px_to_main(ne, apx), _px_to_main(ne, bpx)
    a, b = (ap.x(), ap.y()), (bp.x(), bp.y())
    speed = max(float(args.get("speed", 1.0)), 0.1)     # >1: faster glide + pull (default 1)
    _glide(a, speed=speed)

    # The wire being pulled is Houdini's OWN preview wire (the overlay shape nodegraphconnect draws
    # when a user drags from a port), not the old pink guide line (Plug 29 Oct).
    out_pos, out_dir = ne.itemOutputPos(src, oidx), ne.itemOutputDir(src, oidx)
    in_dir = ne.itemInputDir(dst, idx)
    wire_clr = hou.ui.colorFromName("GraphPreSelection")

    def frames():
        ov = _overlay()
        try:
            t0, secs = time.time(), float(args.get("seconds", 0.7)) / speed
            while True:
                k = min(1.0, (time.time() - t0) / secs)
                e = ease_in_out_quint(k)
                cur = (a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e)
                ed =(apx[0] + (bpx[0] - apx[0]) * e, apx[1] + (bpx[1] - apx[1]) * e)
                ne.setOverlayShapes([hou.NetworkShapeConnection(
                    out_pos, out_dir, ne.posFromScreen(hou.Vector2(*ed)), in_dir, wire_clr, 1.0)])
                ov.pos_ = QtCore.QPointF(*cur)
                ov.wire = None
                ov.last_active = ov.last_move = time.time()
                ov.has_cursor = True
                ov.update()
                if k >= 1.0:
                    break
                yield
            with hou.undos.group("Brother: wire %s -> %s" % (src.name(), dst.name())):
                dst.setInput(idx, src)
        finally:
            ne.setOverlayShapes([])
            ov.wire = None
            ov.update()
    def report():
        ins = dst.inputs()
        return {"dst": dst.path(), "input": idx,
                "connected_to": ins[idx].path() if len(ins) > idx and ins[idx] else None}
    budget = float(args.get("budget", 10.0))
    if not args.get("wait"):
        return dict(report(), job=_start(frames(), budget, report), state="running", method=_API)
    reason = _run(frames(), budget)
    _pump(0.2)
    return dict(report(), cancelled=reason, method=_API)


OPS = {"screenshot": op_screenshot, "pointer": op_pointer, "click": op_click, "type": op_type,
       "key": op_key, "cursor_hide": op_cursor_hide, "create_node": op_create_node,
       "click_node": op_click_node, "pane_screenshot": op_pane_screenshot,
       "set_parm_shown": op_set_parm_shown, "control_hold": op_control_hold, "drag": op_drag,
       "select_node": op_select_node, "move_node": op_move_node, "wire_nodes": op_wire_nodes,
       "action_status": op_action_status, "action_stop": op_action_stop,
       "capture_pane": op_capture_pane, "task": op_task}
