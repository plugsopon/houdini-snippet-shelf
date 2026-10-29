"""Occlusion-independent capture of a Houdini Network Editor pane (run INSIDE Houdini).

Method: Win32 PrintWindow(root_hwnd, PW_CLIENTONLY|PW_RENDERFULLCONTENT) - DWM renders the window's
own redirection surface into a memory DC, so a window covering Houdini does not appear in the
result. No focus, no raise, no cursor, no SendInput, no hooks. Read-only GDI calls only.

The pane is cropped from the window image with qtScreenGeometry -> client coords (DPI-scaled).
Every capture carries metadata and FAILS CLOSED on: unknown/hidden/not-a-network pane, a black or
blank image, a minimised window, or a crop outside the window.

    import brother_capture as bcap
    meta, img, png = bcap.capture_pane()                     # current Network Editor
    meta, img, png = bcap.capture_pane(pane_name="panetab7")

This is a real screenshot of the pane as Houdini last drew it - not a graph export and not a
cached frame. It needs a non-minimised window (DWM must hold a surface); it cannot show a tab
that is not the current one, because such a tab has no pixels.
Proof run: temp/houdini-template-demo/indep_control/geom/self_capture/acceptance.json
"""
import ctypes, ctypes.wintypes as W, hashlib, os, time, sys

import hou
from PySide6 import QtGui, QtCore, QtWidgets

_u = ctypes.windll.user32
_g = ctypes.windll.gdi32
_P = ctypes.c_void_p
for _f, _r, _a in (("GetAncestor", W.HWND, [W.HWND, W.UINT]), ("GetClientRect", W.BOOL, [W.HWND, ctypes.POINTER(W.RECT)]),
                   ("ClientToScreen", W.BOOL, [W.HWND, ctypes.POINTER(W.POINT)]), ("GetDC", _P, [W.HWND]),
                   ("ReleaseDC", ctypes.c_int, [W.HWND, _P]), ("PrintWindow", W.BOOL, [W.HWND, _P, W.UINT]),
                   ("IsIconic", W.BOOL, [W.HWND]), ("GetDpiForWindow", W.UINT, [W.HWND]),
                   ("WindowFromPoint", W.HWND, [W.POINT]), ("GetForegroundWindow", W.HWND, []),
                   ("GetCursorPos", W.BOOL, [ctypes.POINTER(W.POINT)])):
    getattr(_u, _f).restype, getattr(_u, _f).argtypes = _r, _a
for _f, _r, _a in (("CreateCompatibleDC", _P, [_P]), ("CreateCompatibleBitmap", _P, [_P, ctypes.c_int, ctypes.c_int]),
                   ("SelectObject", _P, [_P, _P]), ("DeleteObject", W.BOOL, [_P]), ("DeleteDC", W.BOOL, [_P]),
                   ("GetDIBits", ctypes.c_int, [_P, _P, W.UINT, W.UINT, _P, _P, W.UINT])):
    getattr(_g, _f).restype, getattr(_g, _f).argtypes = _r, _a

PW_CLIENTONLY, PW_RENDERFULLCONTENT = 1, 2
METHOD = "win32 PrintWindow(PW_CLIENTONLY|PW_RENDERFULLCONTENT) of Houdini's root window, cropped to the pane"


class _BIH(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD),
                ("biBitCount", W.WORD), ("biCompression", W.DWORD), ("biSizeImage", W.DWORD),
                ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG), ("biClrUsed", W.DWORD),
                ("biClrImportant", W.DWORD)]


class CaptureError(RuntimeError):
    pass


def root_hwnd():
    mw = hou.qt.mainWindow()
    return _u.GetAncestor(W.HWND(int(mw.winId())), 2)


def print_window(hwnd):
    """Whole client area of hwnd as a QImage, rendered by DWM (independent of what covers it)."""
    if _u.IsIconic(hwnd):
        raise CaptureError("window is minimised - DWM has no surface to render")
    r = W.RECT()
    _u.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        raise CaptureError("empty client rect %dx%d" % (w, h))
    hdc = _u.GetDC(hwnd)
    mdc = _g.CreateCompatibleDC(hdc)
    bmp = _g.CreateCompatibleBitmap(hdc, w, h)
    old = _g.SelectObject(mdc, bmp)
    try:
        ok = _u.PrintWindow(hwnd, mdc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
        if not ok:
            raise CaptureError("PrintWindow returned 0 (err %d)" % ctypes.GetLastError())
        bih = _BIH(ctypes.sizeof(_BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        _g.SelectObject(mdc, old)                       # GetDIBits wants the bitmap NOT selected
        lines = _g.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
        if lines != h:
            raise CaptureError("GetDIBits read %d of %d lines" % (lines, h))
        img = QtGui.QImage(buf.raw, w, h, w * 4, QtGui.QImage.Format_RGB32).copy()
    finally:
        _g.DeleteObject(bmp)
        _g.DeleteDC(mdc)
        _u.ReleaseDC(hwnd, hdc)
    return img, (w, h)


def image_stats(img, step=7):
    img = img.convertToFormat(QtGui.QImage.Format_RGB32)
    n = s = dark = 0
    seen = set()
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            p = img.pixel(x, y)
            seen.add(p & 0xFFFFFF)
            c = QtGui.QColor(p)
            v = (c.red() + c.green() + c.blue()) / 3.0
            s += v; n += 1; dark += v < 4
    return {"mean": round(s / max(n, 1), 2), "black_frac": round(dark / max(n, 1), 4), "distinct_colors": len(seen)}


def _find_pane(pane_name):
    tabs = [t for t in hou.ui.paneTabs()]
    if pane_name is None:
        cur = [t for t in tabs if t.type() == hou.paneTabType.NetworkEditor and t.isCurrentTab()]
        if not cur:
            raise CaptureError("no visible Network Editor pane tab")
        return cur[0]
    hit = [t for t in tabs if t.name() == pane_name]
    if not hit:
        raise CaptureError("no pane tab named %r" % pane_name)
    t = hit[0]
    if t.type() != hou.paneTabType.NetworkEditor:
        raise CaptureError("pane %r is a %s, not a Network Editor" % (pane_name, t.type().name()))
    if not t.isCurrentTab():
        raise CaptureError("pane %r is a hidden (non-current) tab - it has no pixels on screen to render" % pane_name)
    return t


def occlusion_at(rect):
    """Read-only: is Houdini the window on top at the pane's centre + corners? (for the record only)"""
    x, y, w, h = rect
    pts = {"centre": (x + w // 2, y + h // 2), "top_left": (x + 8, y + 8), "bottom_right": (x + w - 8, y + h - 8)}
    root = root_hwnd()
    out = {}
    for k, (px, py) in pts.items():
        hw = _u.WindowFromPoint(W.POINT(px, py))
        out[k] = bool(hw) and _u.GetAncestor(hw, 2) == root
    return {"houdini_on_top": out, "occluded": not all(out.values())}


def os_snapshot():
    cur = W.POINT()
    _u.GetCursorPos(ctypes.byref(cur))
    fg = _u.GetForegroundWindow()
    return {"foreground_hwnd": int(fg or 0), "foreground_is_houdini": _u.GetAncestor(fg, 2) == root_hwnd() if fg else False,
            "os_cursor": [cur.x, cur.y]}


def capture_pane(pane_name=None, save_dir=None, tag="cap"):
    t0 = time.time()
    os_before = os_snapshot()
    ne = _find_pane(pane_name)
    g = ne.qtScreenGeometry()
    rect = (g.x(), g.y(), g.width(), g.height())
    hwnd = root_hwnd()
    img, (cw, ch) = print_window(hwnd)
    o = W.POINT(0, 0)
    _u.ClientToScreen(hwnd, ctypes.byref(o))
    dpi = _u.GetDpiForWindow(hwnd) or 96
    sc = dpi / 96.0
    scr = QtWidgets.QApplication.instance().screenAt(QtCore.QPoint(g.x() + 1, g.y() + 1))
    dpr = scr.devicePixelRatio() if scr else 1.0
    # qtScreenGeometry is in Qt logical px; the bitmap is in physical px of the client area
    cx, cy = int(round(g.x() * dpr)) - o.x, int(round(g.y() * dpr)) - o.y
    pw, ph = int(round(g.width() * dpr)), int(round(g.height() * dpr))
    if cx < 0 or cy < 0 or cx + pw > cw or cy + ph > ch:
        raise CaptureError("pane rect %r is outside the window client area %dx%d (origin %d,%d)" % (rect, cw, ch, o.x, o.y))
    crop = img.copy(cx, cy, pw, ph)
    st = image_stats(crop)
    if st["black_frac"] > 0.9 or st["distinct_colors"] < 8:
        raise CaptureError("capture is black/blank (%r) - refusing to call it a screenshot" % st)
    ba = QtCore.QByteArray()
    buf = QtCore.QBuffer(ba); buf.open(QtCore.QIODevice.WriteOnly); crop.save(buf, "PNG"); buf.close()
    png = bytes(ba)
    vb = ne.visibleBounds()
    meta = {"method": METHOD, "pane": ne.name(), "pane_type": ne.type().name(), "network": ne.pwd().path(),
            "pan_zoom_visibleBounds": [vb.min()[0], vb.min()[1], vb.max()[0], vb.max()[1]],
            "screen_bounds": list(ne.screenBounds().max()), "qt_screen_geometry": list(rect),
            "client_origin": [o.x, o.y], "client_size": [cw, ch], "crop": [cx, cy, pw, ph],
            "dpi": dpi, "dpi_scale": sc, "devicePixelRatio": dpr, "width": crop.width(), "height": crop.height(),
            "sha256": hashlib.sha256(png).hexdigest(), "stats": st,
            "houdini_version": hou.applicationVersionString(), "hip": hou.hipFile.path(),
            "selected": [n.path() for n in hou.selectedNodes()],
            "occlusion": occlusion_at(rect), "os_before": os_before, "os_after": os_snapshot(),
            "ms": round((time.time() - t0) * 1000, 1), "t": round(t0, 3)}
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        p = os.path.join(save_dir, "%s.png" % tag)
        open(p, "wb").write(png)
        meta["path"] = p
    return meta, crop, png
