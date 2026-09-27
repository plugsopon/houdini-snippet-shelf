# ============================================================================
# Unborn-particle "follow live neighbours" rig  (paste into Houdini Python Shell)
#
# Problem: you take the LAST frame of a POP sim as a fixed point set and copy P
# from the live sim by id. Points whose id is not born yet have nothing to copy
# and hang in space. This rig moves every not-yet-born point to a smooth
# weighted average of the CURRENT positions of live particles that sit closest
# to it in the rest layout, so the lattice is deform-safe (Point Deform).
#
# HOW TO USE
#   1. Open the network you want in the Network Editor:
#        - a Geometry (SOP) network -> the rig is built right there
#        - /obj                     -> a new "follow_demo" geo is created for it
#   2. Paste the whole thing into Windows > Python Shell and press Enter.
#   It never edits your existing nodes.
#   Frames come from the playbar: the demo sim starts at the start frame and
#   the rest shape is the end frame (override with START_FRAME / END_FRAME /
#   REST_FRAME, or set LINK_TO_PLAYBAR = True to keep following the playbar).
# ============================================================================

import hou

# ----------------------------- CONFIG ---------------------------------------
# BUILD_DEMO = True  -> builds a test scene (grid -> anim -> POP sim) in the
#                       current network and rigs it.
# BUILD_DEMO = False -> rigs YOUR scene. Node names below are looked up in the
#                       current network first (full paths work too). If
#                       SIM_NODE is "" the first SELECTED node is used.
BUILD_DEMO   = True
TARGET       = ""   # "" = the network the Network Editor is showing; or a path

SIM_NODE     = ""   # live sim particles, every frame (needs i@id, f@age)
EMITTER_NODE = ""   # emitter in the SAME space as SIM_NODE ("" = none)
DEFORM_NODE  = ""   # geometry to deform, in REST pose ("" = auto scatter demo / skip)
REST_FRAME   = None # frame whose particle layout is the rest shape (None = END frame below)
# ----------------------------------------------------------------------------

# ---- frame range: use the scene's current start / end frame -----------------
START_FRAME     = None   # None = the playbar's start frame right now
END_FRAME       = None   # None = the playbar's end frame right now
LINK_TO_PLAYBAR = False  # True = write $FSTART / $FEND expressions instead of numbers

START_PARMS = ("startframe", "start_frame", "startFrame", "sim_start", "simstart")


def scene_frame_range():
    fs, fe = hou.playbar.frameRange()
    return (float(START_FRAME) if START_FRAME is not None else fs,
            float(END_FRAME) if END_FRAME is not None else fe)


def _is_driven(p):
    """Leave parms that already follow something (expression / keys) alone."""
    return len(p.keyframes()) > 0


def _put(p, value, expr):
    if LINK_TO_PLAYBAR:
        p.setExpression(expr, hou.exprLanguage.Hscript)
    else:
        p.set(value)


def apply_frame_range(nodes):
    """Set start-frame parms (solvers, DOP networks ...) and ROP / file cache
    ranges on `nodes` and everything inside them to the scene's frame range."""
    fs, fe = scene_frame_range()
    changed, skipped = [], []
    for top in nodes:
        for n in [top] + list(top.allSubChildren()):
            if n.isInsideLockedHDA():
                continue
            for name in START_PARMS:
                p = n.parm(name)
                if p is None:
                    continue
                if _is_driven(p):
                    skipped.append(p.path()); continue
                _put(p, fs, "$FSTART"); changed.append(p.path())
            f1, f2 = n.parm("f1"), n.parm("f2")
            if f1 is not None and f2 is not None and n.parm("trange") is not None:
                for p, v, e in ((f1, fs, "$FSTART"), (f2, fe, "$FEND")):
                    if _is_driven(p):
                        skipped.append(p.path())
                    else:
                        _put(p, v, e); changed.append(p.path())
    print("frame range %g-%g%s: set %d parm(s)%s" % (
        fs, fe, " (linked to playbar)" if LINK_TO_PLAYBAR else "", len(changed),
        (", left %d that already follow an expression" % len(skipped)) if skipped else ""))
    for c in changed:
        print("   set", c)
    return changed


def current_network():
    """TARGET if set, else the network shown in the Network Editor."""
    if TARGET:
        n = hou.node(TARGET)
        if n is None:
            raise hou.Error("TARGET not found: %s" % TARGET)
        return n
    ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor) if hou.isUIAvailable() else None
    if ne is None:
        raise hou.Error("No Network Editor found - open one, or set TARGET.")
    return ne.pwd()


def sop_network(net):
    """A SOP network to build in: net itself, or a new geo when net is /obj-level."""
    cat = net.childTypeCategory().name()
    if cat == "Sop":
        return net
    if cat == "Object":
        return net.createNode("geo", "follow_demo")
    raise hou.Error("Open a Geometry (SOP) network or /obj - %s holds %s nodes." % (net.path(), cat))


def find(name, net):
    """Look a node up relative to the current network first, then as a full path."""
    if not name:
        return None
    n = net.node(name) or hou.node(name)
    if n is None:
        raise hou.Error("Node not found: %r (looked in %s and as a full path)" % (name, net.path()))
    return n


def build_demo(geo):
    """grid -> anim (rises, tiny) -> popnet (source + wind) in SOP network geo. Returns (sim, emitter)."""
    ys = [c.position()[1] for c in geo.children()]
    top = (min(ys) - 2) if ys else 0          # start below whatever is already there
    grid = geo.createNode("grid", "demo_grid")
    anim = geo.createNode("xform", "demo_anim")
    anim.setInput(0, grid)
    anim.parm("scale").set(0.03)
    ty = anim.parm("ty")
    fs, fe = scene_frame_range()
    for fr, v in ((fs, 0.0), (fe, 3.3)):
        k = hou.Keyframe(); k.setFrame(fr); k.setValue(v); k.setExpression("linear()")
        ty.setKeyframe(k)
    dop = geo.createNode("dopnet", "demo_popnet")
    dop.setInput(0, anim)
    dop.parm("objname1").set("*") if dop.parm("objname1") else None
    obj = dop.createNode("popobject", "popobject")
    src = dop.createNode("popsource", "source_first_input")
    src.parm("usecontextgeo").set(2)          # first context geometry (the anim input)
    src.parm("constantrate").set(50)
    wind = dop.createNode("popwind", "popwind1")
    wind.setInput(0, src)
    wind.parm("windy").set(1); wind.parm("amp").set(1); wind.parm("swirlsize").set(0.67)
    merge = dop.createNode("merge", "wire_pops_into_here")
    merge.setInput(0, wind)
    solver = dop.createNode("popsolver", "popsolver")
    solver.setInput(0, obj); solver.setInput(2, merge)
    out = dop.createNode("output", "output")
    out.setInput(0, solver)
    out.setDisplayFlag(True)
    dop.layoutChildren()
    grid.setPosition(hou.Vector2(0, top)); anim.setPosition(hou.Vector2(0, top - 1)); dop.setPosition(hou.Vector2(0, top - 2))
    return dop, anim


here = current_network()
if BUILD_DEMO:
    sim, emitter = build_demo(sop_network(here))
    apply_frame_range([sim])   # demo POP network starts at the scene's start frame
    deform_src = None          # a scatter of the rest shape is built below
else:
    sim = find(SIM_NODE, here) if SIM_NODE else (hou.selectedNodes() or [None])[0]
    if sim is None:
        raise hou.Error("Set SIM_NODE or select the sim node first.")
    emitter = find(EMITTER_NODE, here)
    deform_src = find(DEFORM_NODE, here)
net = sim.parent()
base = sim.position()


def mk(type_name, name, dx, dy):
    n = net.createNode(type_name, name)
    n.setPosition(base + hou.Vector2(dx, dy))
    return n


def add_float(node, name, label, default, lo, hi):
    ptg = node.parmTemplateGroup()
    ptg.append(hou.FloatParmTemplate(name, label, 1, default_value=(default,), min=lo, max=hi))
    node.setParmTemplateGroup(ptg)


def add_int(node, name, label, default, lo, hi):
    ptg = node.parmTemplateGroup()
    ptg.append(hou.IntParmTemplate(name, label, 1, default_value=(default,), min=lo, max=hi))
    node.setParmTemplateGroup(ptg)


# 1) rest layout = sim held at REST_FRAME ------------------------------------
rest = mk("timeshift", "follow_rest", 3, -1)
rest.setInput(0, sim)
rest.parm("frame").deleteAllKeyframes()   # default is a $F expression; clear it
if REST_FRAME is None and LINK_TO_PLAYBAR:
    rest.parm("frame").setExpression("$FEND", hou.exprLanguage.Hscript)
else:
    rest.parm("frame").set(REST_FRAME if REST_FRAME is not None else scene_frame_range()[1])

# 2) per-frame info on the live sim: where the emitter is right now ----------
info = mk("attribwrangle", "follow_sim_info", 6, -1)
info.setInput(0, sim)
if emitter is not None:
    info.setInput(1, emitter)
info.parm("class").set(0)  # detail
info.parm("snippet").set(r'''
// anchor position: emitter centre if one is wired, else the live cloud centre
v@emitpos = npoints(1) > 0 ? getbbox_center(1) : getbbox_center(0);
''')

# 3) mark which rest points exist in the live sim this frame -----------------
mark = mk("attribwrangle", "follow_mark_born", 3, -2.5)
mark.setInput(0, rest)
mark.setInput(1, sim)
mark.parm("snippet").set(r'''
int src = idtopoint(1, i@id);
i@born  = src >= 0;
i@srcpt = src;
''')

# 4) live-only point cloud (rest-layout P) for fast neighbour search ---------
born = mk("attribwrangle", "follow_born_only", 6, -3.5)
born.setInput(0, mark)
born.parm("snippet").set('if (!i@born) removepoint(0, @ptnum);')   # no group parsing -> works in any version

# 5) the follow itself --------------------------------------------------------
fol = mk("attribwrangle", "follow_live", 3, -5)
fol.setInput(0, mark)
fol.setInput(1, info)   # live sim P / age + detail emitpos
fol.setInput(2, born)   # live-only cloud
add_float(fol, "blend_time", "Blend Time (s)", 0.5, 0, 5)
add_float(fol, "radius", "Closest Radius", 0.2, 0.001, 3)
add_float(fol, "anchor_weight", "Emitter Anchor Weight", 1.0, 0, 50)
add_int(fol, "max_neighbours", "Max Neighbours", 64, 8, 2048)   # 256 = smoother, 32 = faster
add_float(fol, "rest_frame", "Rest Frame", 1, 1, 1000)
fol.parm("rest_frame").setExpression('ch("../%s/frame")' % rest.name())
fol.parm("snippet").set(r'''
// Weighted CURRENT position of live neighbours; closest in the rest layout wins.
// Gaussian weight (radius = Closest Radius) is < 1e-4 beyond 3*radius, so only
// that radius is searched: cost ~ N * neighbours, not N * N.
// A newborn's vote fades in over Blend Time, so nothing jumps.
function vector neighbourPos(vector rest; int selfid; float radius; float fade;
                             float wa; int maxn; vector anchor) {
    float h = max(radius, 1e-4);
    int near[] = pcfind(2, "P", rest, 3 * h, maxn);
    vector sum = 0; float wsum = 0;
    foreach (int n; near) {
        if (point(2, "id", n) == selfid) continue;
        int s = point(2, "srcpt", n);
        vector nRest = point(2, "P", n);
        vector nNow  = point(1, "P", s);
        float d = distance(rest, nRest) / h;
        float w = exp(-d * d);
        if (fade > 0) w *= smooth(0, 1, point(1, "age", s) / fade);
        sum += nNow * w; wsum += w;
    }
    // emitter = constant-vote anchor: dominates while few particles are alive,
    // gets outvoted naturally as the sim fills up (keeps early frames steady)
    sum += anchor * wa; wsum += wa;
    return wsum > 0 ? sum / wsum : rest;
}

float blend   = chf("blend_time");
vector anchor = detail(1, "emitpos");
vector rest   = v@P;
vector taken  = neighbourPos(rest, i@id, chf("radius"), blend,
                             chf("anchor_weight"), chi("max_neighbours"), anchor);

if (i@born) {
    // ease from the borrowed pose into the real sim so birth never pops ...
    vector real = point(1, "P", i@srcpt);
    float age = point(1, "age", i@srcpt);
    float t = blend > 0 ? smooth(0, 1, age / blend) : 1;
    // ... and be fully on the sim by the rest frame, so the deform matches rest
    float restT = (chf("rest_frame") - 1) * @TimeInc;   // time = (frame-1)/fps
    if (blend > 0) t = max(t, smooth(restT - blend, restT, @Time));
    v@P = lerp(taken, real, t);
} else {
    v@P = taken;
}
''')

out = mk("null", "OUT_follow_live", 3, -6.2)
out.setInput(0, fol)
created = [rest, info, mark, born, fol, out]

if BUILD_DEMO:
    con = mk("connectadjacentpieces", "demo_connect", -3, -2.5)
    con.setInput(0, rest)
    con.parm("connecttype").set(2); con.parm("maxsearchpoints").set(28)
    sc = mk("scatter", "demo_scatter", -3, -3.7)
    sc.setInput(0, con)
    sc.parm("npts").set(100000)
    deform_src = mk("null", "demo_rest_geo", -3, -4.9)
    deform_src.setInput(0, sc)
    created += [con, sc, deform_src]

# 6) optional: Point Deform the rest geometry with the lattice ----------------
if deform_src is not None:
    pd = mk("pointdeform", "follow_pointdeform", 0, -7.4)
    pd.setInput(0, deform_src)
    pd.setInput(1, rest)
    pd.setInput(2, out)
    out_d = mk("null", "OUT_follow_deform", 0, -8.6)
    out_d.setInput(0, pd)
    out_d.setDisplayFlag(True)
    out_d.setRenderFlag(True)
    created += [pd, out_d]
else:
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

print("rest frame: %g" % rest.parm("frame").eval())
print("follow rig built in %s: %s" % (net.path(), ", ".join(n.name() for n in created)))
