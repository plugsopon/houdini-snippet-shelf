"""Visible build of a network PLAN (a module with NODES, SPARE, LINKS, optional EXPRS / RAMPS /
TASK_LABEL / DISPLAY, COL_X, ROW_Y) into a fresh geo: each node created with Brother's cursor at its
planned spot (top -> bottom, left -> right), wired with the eased wire pull, lined up under its input,
parameters set, and every VEX snippet typed into the pinned Parameter pane - with the purple control
frame held for the whole build (Esc stops it). Refuses a non-empty network. HIP never saved.
Usage: python build_visible.py <plan module> <geo path> [speed=4] [chars_per_second=90] [--resume]"""
import json, sys, time
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge import call, PID
import importlib

args = [a for a in sys.argv[1:] if not a.startswith("--")]
P = importlib.import_module(args[0])
GEO = args[1]
SPEED = float(args[2]) if len(args) > 2 else 4.0
CPS = float(args[3]) if len(args) > 3 else 90.0
EXPRS = getattr(P, "EXPRS", {})
RAMPS = getattr(P, "RAMPS", {"leaf_sweep": ("scaleramp",) + tuple(getattr(P, "LEAF_RAMP", ((), ())))})


class Cancelled(Exception):
    pass


def beat():
    """Keep the purple control frame at full strength; raise if Plug pressed Esc."""
    if call(PID, "task", {"action": "beat"}, 5)[0]["result"]["cancelled"]:
        call(PID, "action_stop", {}, 5)
        raise Cancelled()


def run(code, label, to=30):
    beat()
    r = call(PID, "run", {"code": code, "label": label}, to)[0]
    if not r.get("ok"):
        raise RuntimeError(json.dumps(r)[:900])
    return r["result"]["result"]


COL = {n[0]: n[2] for n in P.NODES}
OFFSET = r'''
import hou, sys
n, src = hou.node(%r), hou.node(%r)
ne = sys.modules["brother_cursor"]._editor_for(n)
result = ne.itemOutputPos(src, 0)[0] - ne.itemInputPos(n, 0)[0]
'''


def wait_job(jid):
    while True:
        time.sleep(0.05)
        s = run("import sys\nresult = sys.modules['brother_cursor'].op_action_status({'job': %r})" % jid,
                "Brother: read-only job status", 5)
        if s["state"] != "running":
            return s


cols = max(n[2] for n in P.NODES) + 1
rows = max(n[3] for n in P.NODES) + 1
call(PID, "task", {"action": "begin", "label": getattr(P, "TASK_LABEL", "Brother is building the network"), "ttl": 20}, 5)
import atexit                      # the frame goes off however this ends: done, error, Esc, sys.exit
atexit.register(lambda: call(PID, "task", {"action": "end"}, 5))
_hook = sys.excepthook
sys.excepthook = lambda t, v, tb: print("stopped: Esc pressed in Houdini") if t is Cancelled else _hook(t, v, tb)
existing = run('''
import hou
geo = hou.node(%r) or hou.node("/obj").createNode("geo", %r)
ne = [t for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.NetworkEditor and t.isCurrentTab()][0]
ne.setPwd(geo)
# fit the WHOLE layout: grow whichever side is short so the rect has the pane's own aspect
x0, y0, x1, y1 = -2.6, -%f - 1.6, %f + 0.4, 2.2       # margin: anchors pan when within 60 px of an edge
w, h = ne.screenBounds().size()
aspect = w / h
if (x1 - x0) / (y1 - y0) > aspect:
    grow = (x1 - x0) / aspect - (y1 - y0); y0 -= grow / 2; y1 += grow / 2
else:
    grow = (y1 - y0) * aspect - (x1 - x0); x0 -= grow / 2; x1 += grow / 2
ne.setVisibleBounds(hou.BoundingRect(x0, y0, x1, y1))
result = [c.name() for c in geo.children()]
''' % (GEO, GEO.split("/")[-1], rows * P.ROW_Y + 0.6, (cols - 1) * P.COL_X + 2.4), "Brother: open geo")
RESUME = "--resume" in sys.argv
if existing and not RESUME:
    sys.exit("refusing: %s already has %s (use --resume to continue a stopped build)" % (GEO, ", ".join(existing)))
time.sleep(0.6)

TYPE = r'''
import hou, sys, time
from PySide6 import QtCore
bc = sys.modules["brother_cursor"]
n = hou.node(%(path)r)
pps = [t for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.Parm]
pp = ([t for t in pps if t.isPin()] or pps)[0]
pp.setCurrentNode(n)
r = bc._pane_rect(pp)
at = (r.x() + r.width() * 0.45, r.y() + r.height() * 0.42)
ov = bc._glide(at, speed=%(speed)f)
ov.ripples.append((QtCore.QPointF(*at), time.time()))
text, parm = %(text)r, n.parm("snippet")
def frames():
    done = False
    try:
        t0 = time.time()
        while True:
            k = min(len(text), int((time.time() - t0) * %(cps)f))
            with hou.undos.disabler():
                parm.set(text[:k])
            if k >= len(text):
                break
            yield
        done = True
    finally:
        with hou.undos.disabler():
            parm.set("")
        if done:
            with hou.undos.group("Brother: type VEX in %%s" %% n.name()):
                parm.set(text)
result = bc._start(frames(), 120.0, lambda: {"typed": parm.eval() == text})
'''

PARMS = r'''
import hou, json
n = hou.node(%(path)r)
parms, spare, links, ramp, exprs = json.loads(%(data)r)
with hou.undos.group("Brother: set parms on " + n.name()):
    for k, v in parms.items():
        n.parm(k).set(v)
    for pname, label, default, lo, hi in spare:
        isint = isinstance(lo, int) and isinstance(hi, int) and (default is None or isinstance(default, int))
        tmpl = (hou.IntParmTemplate if isint else hou.FloatParmTemplate)(pname, label, 1, min=lo, max=hi,
                default_value=(default if default is not None else 0,))
        g = n.parmTemplateGroup(); g.append(tmpl); n.setParmTemplateGroup(g)
    for pname, target in links:
        n.parm(pname).setExpression('ch("../%%s")' %% target)
    for pname, expr in exprs:
        n.parm(pname).setExpression(expr)
    if ramp:
        rparm, keys, vals = ramp
        n.parm(rparm).set(hou.Ramp([hou.rampBasis.CatmullRom] * len(keys), keys, vals))
result = n.name()
'''

t0 = time.time()
for name, typ, col, row, ins, parms, snip in P.NODES:
    path = "%s/%s" % (GEO, name)
    if RESUME and name in existing:
        have = run("import hou\nn = hou.node(%r)\nresult = {str(i): (n.inputs()[i].name() if len(n.inputs()) > i and n.inputs()[i] else None) for i in range(4)}" % path, "Brother: read-only")
        missing = [(i, s_) for i, s_ in ins if have.get(str(i)) != s_]
        if not missing:
            print("exists  %-14s" % name, flush=True)
            continue
        ins = missing
        made = path
    else:
        made = None
    made = made or run('''
import hou, sys
bc = sys.modules["brother_cursor"]
ne = [t for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.NetworkEditor and t.isCurrentTab()][0]
x, y = ne.posToScreen(hou.Vector2(%f, %f))
p = bc._px_to_main(ne, (x, y))
result = bc.op_create_node({"x": p.x(), "y": p.y(), "type": %r, "name": %r, "speed": %f})["created"]
''' % (col * P.COL_X, -row * P.ROW_Y, typ, name, SPEED), "Brother: create " + name)
    if made != path:
        sys.exit("stopping: asked for %s, Houdini made %s" % (path, made))
    line = "created %-14s" % name
    for idx, src in ins:
        time.sleep(0.12)
        r = run("import sys\nresult = sys.modules['brother_cursor'].op_wire_nodes({'src': %r, 'dst': %r, 'input': %d, 'speed': %f})"
                % ("%s/%s" % (GEO, src), path, idx, SPEED), "Brother: wire %s -> %s" % (src, name))
        s = wait_job(r["job"])
        line += "  in%d<-%s%s" % (idx, src, "" if s.get("connected_to") else " (FAILED)")
    # after wiring: a Merge's port only settles once its inputs are connected
    first = [s_ for i, s_ in ins if i == 0 and COL[s_] == col]
    if first:                          # input 0 straight under its source's output (no leaning wire)
        dx = run(OFFSET % (path, "%s/%s" % (GEO, first[0])), "Brother: read-only port offset")
        if abs(dx) > 0.005:
            jid = run("import sys\nresult = sys.modules['brother_cursor'].op_move_node({'path': %r, 'dx': %f, 'dy': 0, 'seconds': 0.35})['job']"
                      % (path, dx), "Brother: line up " + name)
            wait_job(jid)
    spare = P.SPARE.get(name, [])
    links = [[k[1], v] for k, v in P.LINKS.items() if k[0] == name]
    ramp = RAMPS.get(name)
    exprs = [[k[1], v] for k, v in EXPRS.items() if k[0] == name]
    if parms or spare or links or ramp or exprs:
        run(PARMS % {"path": path, "data": json.dumps([parms, spare, links, ramp, exprs])}, "Brother: set parms on " + name)
    if snip:
        jid = run(TYPE % {"path": path, "speed": SPEED, "cps": CPS, "text": snip}, "Brother: type VEX in " + name)
        line += "  typed %d lines: %s" % (snip.count("\n"), wait_job(jid).get("typed"))
    for target, dparms, dexprs in getattr(P, "DEFER", {}).get(name, []):
        run(PARMS % {"path": "%s/%s" % (GEO, target),
                     "data": json.dumps([dparms, [], [], None, [[k, v] for k, v in dexprs.items()]])},
            "Brother: link " + target)
        line += "  linked %s" % target
    if "--follow" in sys.argv and not typ.startswith("block_begin"):   # viewport shows what was just built
        run("import hou\nhou.node(%r).setDisplayFlag(True)\nresult = 1" % path, "Brother: display " + name)
    print(line, flush=True)

print("final", json.dumps(run('''
import hou
geo = hou.node(%r)
geo.node(%r).setDisplayFlag(True); geo.node(%r).setRenderFlag(True)
kids = geo.children()
for n in kids:                     # a block_begin made before its block_end keeps a stale "Invalid sop" error
    if n.type().name().startswith("block_begin"):
        n.cook(force=True)
bad = [(n.name(), i.name()) for n in kids for i in n.inputs() if i and not i.position()[1] > n.position()[1]]
result = {"nodes": len(kids), "errors": {n.name(): n.errors()[:1] for n in kids if n.errors()},
          "layout_violations": bad, "hip_unsaved": hou.hipFile.hasUnsavedChanges()}
''' % (GEO, getattr(P, "DISPLAY", "OUT"), getattr(P, "DISPLAY", "OUT")), "Brother: build readback")))
print("%.1f s" % (time.time() - t0))
