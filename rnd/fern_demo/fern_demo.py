"""ONE-COMMAND DEMO for recording: rebuild the walking-through-ferns field visibly in the open Houdini
(the one running brother_link; HOUDINI_BROTHER_PID picks one when several are open).
  1. deletes ONLY /obj/brother_fern_field (Brother's own demo network) - nothing else is touched
  2. Scene Viewer to the front, only the field object displayed, camera framed on the field
  3. build_visible.py field_plan  - node by node, VEX typed, purple frame held, Esc stops it,
     viewport follows the node just built (story order: fern -> loop -> walker -> field)
  4. frame 1, timeline plays: Crag walks, ferns open near him and curl back up behind him
Usage: python fern_demo.py [speed=2.5] [chars_per_second=60]
HIP is never saved. Other objects are only hidden (display flag), not changed."""
import json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bridge import call, PID

SPEED = sys.argv[1] if len(sys.argv) > 1 else "2.5"
CPS = sys.argv[2] if len(sys.argv) > 2 else "60"
GEO = "/obj/brother_fern_field"


def run(code, label, to=30):
    r = call(PID, "run", {"code": code, "label": label}, to)[0]
    if not r.get("ok"):
        raise RuntimeError(json.dumps(r)[:600])
    return r["result"]["result"]


print("prepare", run('''
import hou
old = hou.node(%r)
with hou.undos.group("Brother: fern demo - clear the old field"):
    if old:
        old.destroy()
    geo = hou.node("/obj").createNode("geo", %r)
for o in hou.node("/obj").children():
    o.setDisplayFlag(o == geo)
sv = [t for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.SceneViewer][0]
sv.setIsCurrentTab()
vp = sv.curViewport()
vp.frameBoundingBox(hou.BoundingBox(-3.2, 0.0, -2.6, 3.2, 2.2, 6.6))
dc = vp.defaultCamera(); pv = dc.pivot()
dc.setTranslation(hou.Vector3(pv[0], pv[1], pv[2] + 7.0))
hou.setFrame(1)
result = {"geo": geo.path(), "shown": [o.name() for o in hou.node("/obj").children() if o.isDisplayFlagSet()]}
''' % (GEO, GEO.split("/")[-1]), "Brother: fern demo - prepare"))

env = dict(os.environ, MSYS_NO_PATHCONV="1", HOUDINI_BROTHER_PID=PID)
t0 = time.time()
rc = subprocess.run([sys.executable, os.path.join(HERE, "build_visible.py"), "field_plan", GEO, SPEED, CPS, "--follow"],
                    cwd=HERE, env=env).returncode
print("build %s in %.0f s" % ("finished" if rc == 0 else "STOPPED (rc=%d)" % rc, time.time() - t0))
if rc == 0:
    print("play", run('''
import hou
hou.setFrame(1)
hou.playbar.setRealTime(True)
hou.playbar.play()
result = "playing from frame 1"
''', "Brother: fern demo - play"))
