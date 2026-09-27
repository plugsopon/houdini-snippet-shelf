# ============================================================================
# FX Template: Subframe for changing Topology  (v001)  - rebuilt as Python so it can be pasted
# anywhere (Windows > Python Shell). Original: Sop.cpio from the FX Template
# library. Notes: Subframe for changing Topology
#
# HOW TO USE: open a Sop network in the Network Editor (e.g. dive inside a
# Geometry node), then paste this whole block into the Python Shell and press Enter.
# Nodes are created in that network. Set TARGET to force a network path.
# Start-frame parms (solvers, DOP networks) and ROP / file-cache ranges are set
# to the scene's current frame range; parms that already use an expression stay.
# ============================================================================
import hou

TARGET = ""   # e.g. "/obj/geo1" ; "" = the network the Network Editor is showing

if TARGET:
    hou_parent = hou.node(TARGET)
else:
    _ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    hou_parent = _ne.pwd() if _ne else None
if hou_parent is None:
    raise hou.Error("Open a Sop network in the Network Editor, or set TARGET.")
if hou_parent.childTypeCategory().name() != "Sop":
    raise hou.Error("This template needs a Sop network, but %s holds %s nodes."
                    % (hou_parent.path(), hou_parent.childTypeCategory().name()))

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

_before = set(hou_parent.children())


# ---- mountain2 (attribnoise::2.0) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/mountain2
hou_node = hou_parent.createNode("attribnoise::2.0", "mountain2", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -7.47621))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/mountain2/attribs parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("attribs")
hou_parm.deleteAllKeyframes()
hou_parm.set("P")


# Code for /obj/tmp_sop/mountain2/folder1 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("folder1")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain2/noiserange parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("noiserange")
hou_parm.deleteAllKeyframes()
hou_parm.set("zcentered")


# Code for /obj/tmp_sop/mountain2/amplitude parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("amplitude")
hou_parm.deleteAllKeyframes()
hou_parm.set(1.29)


# Code for /obj/tmp_sop/mountain2/folder7 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("folder7")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain2/folder6 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("folder6")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain2/animated parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("animated")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain2/fractal parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("fractal")
hou_parm.deleteAllKeyframes()
hou_parm.set("hmfT")


# Code for /obj/tmp_sop/mountain2/oct parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("oct")
hou_parm.deleteAllKeyframes()
hou_parm.set(8)


# Code for /obj/tmp_sop/mountain2/rough parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("rough")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.40000000000000002)


# Code for /obj/tmp_sop/mountain2/remapramp2pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("remapramp2pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain2/remapramp2value parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain2")
hou_parm = hou_node.parm("remapramp2value")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/mountain2
hou_node = hou_parent.node("mountain2")
if hou_parent.node("pointsfromvolume1") is not None:
    hou_node.setInput(0, hou_parent.node("pointsfromvolume1"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- pointvelocity1 (pointvelocity) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/pointvelocity1
hou_node = hou_parent.createNode("pointvelocity", "pointvelocity1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -8.47621))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/pointvelocity1/framerange parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/pointvelocity1")
hou_parm_tuple = hou_node.parmTuple("framerange")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/pointvelocity1/velapproximation parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/pointvelocity1")
hou_parm = hou_node.parm("velapproximation")
hou_parm.deleteAllKeyframes()
hou_parm.set("Forward Difference")


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/pointvelocity1
hou_node = hou_parent.node("pointvelocity1")
if hou_parent.node("mountain2") is not None:
    hou_node.setInput(0, hou_parent.node("mountain2"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- pointsfromvolume1 (pointsfromvolume) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/pointsfromvolume1
hou_node = hou_parent.createNode("pointsfromvolume", "pointsfromvolume1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -6.47621))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/pointsfromvolume1/particlesep parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/pointsfromvolume1")
hou_parm = hou_node.parm("particlesep")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.02)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/pointsfromvolume1
hou_node = hou_parent.node("pointsfromvolume1")
if hou_parent.node("sphere1") is not None:
    hou_node.setInput(0, hou_parent.node("sphere1"), 0)
hou_node.setUserData("___toolid___", "dynamics_flipbox")
hou_node.setUserData("___Version___", "2")
hou_node.setUserData("___toolcount___", "1")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("2")

# ---- pointvelocity2 (pointvelocity) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/pointvelocity2
hou_node = hou_parent.createNode("pointvelocity", "pointvelocity2", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -10.4762))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/pointvelocity2/framerange parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/pointvelocity2")
hou_parm_tuple = hou_node.parmTuple("framerange")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/pointvelocity2
hou_node = hou_parent.node("pointvelocity2")
if hou_parent.node("attribute1") is not None:
    hou_node.setInput(0, hou_parent.node("attribute1"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- particlefluidsurface1 (particlefluidsurface::3.0) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/particlefluidsurface1
hou_node = hou_parent.createNode("particlefluidsurface::3.0", "particlefluidsurface1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -11.4762))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/particlefluidsurface1/transferattribs parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("transferattribs")
hou_parm.deleteAllKeyframes()
hou_parm.set("v2 v vorticity rest rest2")


# Code for /obj/tmp_sop/particlefluidsurface1/doerode parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("doerode")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dodilate\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dodilate\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dodilate\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dodilate\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/particlefluidsurface1/erodeoffset parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("erodeoffset")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilateoffset\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilateoffset\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilateoffset\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilateoffset\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/particlefluidsurface1/erodemask parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("erodemask")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilatemask\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilatemask\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilatemask\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("ch(\"dilatemask\")", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/particlefluidsurface1/folder7 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("folder7")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/folder6 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("folder6")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/folder4 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("folder4")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/folder5 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("folder5")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/velvisramp1c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("velvisramp1c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 0, 0.89999997615814209))


# Code for /obj/tmp_sop/particlefluidsurface1/velvisramp2pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("velvisramp2pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.50579148530960083)


# Code for /obj/tmp_sop/particlefluidsurface1/velvisramp2c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("velvisramp2c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 0.90000000000000002, 0.90000000000000002))


# Code for /obj/tmp_sop/particlefluidsurface1/velvisramp3pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("velvisramp3pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/velvisramp3c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("velvisramp3c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((1, 1, 1))


# Code for /obj/tmp_sop/particlefluidsurface1/vorticityvisramp1c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("vorticityvisramp1c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 0, 0.89999997615814209))


# Code for /obj/tmp_sop/particlefluidsurface1/vorticityvisramp2pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("vorticityvisramp2pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.5)


# Code for /obj/tmp_sop/particlefluidsurface1/vorticityvisramp2c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("vorticityvisramp2c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 0.89999997615814209, 0.89999997615814209))


# Code for /obj/tmp_sop/particlefluidsurface1/vorticityvisramp3pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("vorticityvisramp3pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/vorticityvisramp3c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("vorticityvisramp3c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((1, 1, 1))


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp1c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("maskvisramp1c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0.20000000000000001, 0, 1))


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp2pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("maskvisramp2pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.25)


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp2c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("maskvisramp2c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 0.84999999999999998, 1))


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp3pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("maskvisramp3pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.5)


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp3c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("maskvisramp3c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 1, 0.10000000149011612))


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp4pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("maskvisramp4pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.75)


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp4c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("maskvisramp4c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0.94999999999999996, 1, 0))


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp5pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm = hou_node.parm("maskvisramp5pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/particlefluidsurface1/maskvisramp5c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/particlefluidsurface1")
hou_parm_tuple = hou_node.parmTuple("maskvisramp5c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((1, 0, 0))


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/particlefluidsurface1
hou_node = hou_parent.node("particlefluidsurface1")
if hou_parent.node("pointvelocity2") is not None:
    hou_node.setInput(0, hou_parent.node("pointvelocity2"), 0)
hou_node.setUserData("wirestyle", "rounded")
hou_node.setUserData("___toolid___", "dynamics_flipbox")
hou_node.setUserData("___Version___", "")
hou_node.setUserData("___toolcount___", "1")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- sphere1 (sphere) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/sphere1
hou_node = hou_parent.createNode("sphere", "sphere1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -5.47621))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/sphere1/type parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/sphere1")
hou_parm = hou_node.parm("type")
hou_parm.deleteAllKeyframes()
hou_parm.set("polymesh")


# Code for /obj/tmp_sop/sphere1/rad parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/sphere1")
hou_parm_tuple = hou_node.parmTuple("rad")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0.5, 0.5, 0.5))


# Code for /obj/tmp_sop/sphere1/rows parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/sphere1")
hou_parm = hou_node.parm("rows")
hou_parm.deleteAllKeyframes()
hou_parm.set(48)


# Code for /obj/tmp_sop/sphere1/cols parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/sphere1")
hou_parm = hou_node.parm("cols")
hou_parm.deleteAllKeyframes()
hou_parm.set(50)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- attribute1 (attribute) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/attribute1
hou_node = hou_parent.createNode("attribute", "attribute1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0834, -9.47621))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/attribute1/frompt0 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribute1")
hou_parm = hou_node.parm("frompt0")
hou_parm.deleteAllKeyframes()
hou_parm.set("v")


# Code for /obj/tmp_sop/attribute1/topt0 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribute1")
hou_parm = hou_node.parm("topt0")
hou_parm.deleteAllKeyframes()
hou_parm.set("v2")


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/attribute1
hou_node = hou_parent.node("attribute1")
if hou_parent.node("pointvelocity1") is not None:
    hou_node.setInput(0, hou_parent.node("pointvelocity1"), 0)
hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- timeshift1 (timeshift) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/timeshift1
hou_node = hou_parent.createNode("timeshift", "timeshift1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -12.4762))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(True)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/timeshift1/frame parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/timeshift1")
hou_parm = hou_node.parm("frame")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$F", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$F", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$F", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$F", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/timeshift1/time parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/timeshift1")
hou_parm = hou_node.parm("time")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$T", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$T", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$T", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$T", hou.exprLanguage.Hscript)
hou_parm.setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/timeshift1/frange parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/timeshift1")
hou_parm_tuple = hou_node.parmTuple("frange")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/timeshift1/trange parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/timeshift1")
hou_parm_tuple = hou_node.parmTuple("trange")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$TSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$TSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$TSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$TEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$TEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$TEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/timeshift1
hou_node = hou_parent.node("timeshift1")
if hou_parent.node("particlefluidsurface1") is not None:
    hou_node.setInput(0, hou_parent.node("particlefluidsurface1"), 0)
hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- attribwrangle3 (attribwrangle) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/attribwrangle3
hou_node = hou_parent.createNode("attribwrangle", "attribwrangle3", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0838, -13.5161))
hou_node.bypass(False)
hou_node.setDisplayFlag(True)
hou_node.hide(False)
hou_node.setHighlightFlag(False)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(True)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/attribwrangle3/snippet parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribwrangle3")
hou_parm = hou_node.parm("snippet")
hou_parm.deleteAllKeyframes()
hou_parm.set("float frame = @Frame;\nfloat whole_frame = rint(@Frame);      \n\nfloat back = ceil(frame)-frame;\nf@back =back;\nfloat forward = frame-floor(frame);\nf@forward = forward;\n\nif(frame<whole_frame) v@P-=v@v*@TimeInc*back;\nif(frame>=whole_frame) v@P+=v@v2*@TimeInc*forward;")


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/attribwrangle3
hou_node = hou_parent.node("attribwrangle3")
if hou_parent.node("timeshift1") is not None:
    hou_node.setInput(0, hou_parent.node("timeshift1"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- rop_alembic1 (rop_alembic) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/rop_alembic1
hou_node = hou_parent.createNode("rop_alembic", "rop_alembic1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(47.0868, -14.554))
hou_node.bypass(False)
hou_node.hide(False)
hou_node.setLocked(False)
hou_node.setSelected(True)

# Code for /obj/tmp_sop/rop_alembic1/f parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/rop_alembic1")
hou_parm_tuple = hou_node.parmTuple("f")

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FSTART", hou.exprLanguage.Hscript)
hou_parm_tuple[0].setKeyframe(hou_keyframe)

# Code for first keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for last keyframe.
# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)

# Code for keyframe.
hou_keyframe = hou.Keyframe()
hou_keyframe.setTime(0)
hou_keyframe.setExpression("$FEND", hou.exprLanguage.Hscript)
hou_parm_tuple[1].setKeyframe(hou_keyframe)


# Code for /obj/tmp_sop/rop_alembic1/stdswitcher1 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/rop_alembic1")
hou_parm = hou_node.parm("stdswitcher1")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/rop_alembic1/motionBlur parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/rop_alembic1")
hou_parm = hou_node.parm("motionBlur")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/rop_alembic1/samples parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/rop_alembic1")
hou_parm = hou_node.parm("samples")
hou_parm.deleteAllKeyframes()
hou_parm.set(3)


# Code for /obj/tmp_sop/rop_alembic1/shutter parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/rop_alembic1")
hou_parm_tuple = hou_node.parmTuple("shutter")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((-0.25, 0.25))


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/rop_alembic1
hou_node = hou_parent.node("rop_alembic1")
if hou_parent.node("attribwrangle3") is not None:
    hou_node.setInput(0, hou_parent.node("attribwrangle3"), 0)
hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()



# ---- connections between the template's top nodes ----
hou_parent.node("mountain2").setInput(0, hou_parent.node("pointsfromvolume1"))
hou_parent.node("pointvelocity1").setInput(0, hou_parent.node("mountain2"))
hou_parent.node("pointsfromvolume1").setInput(0, hou_parent.node("sphere1"))
hou_parent.node("pointvelocity2").setInput(0, hou_parent.node("attribute1"))
hou_parent.node("particlefluidsurface1").setInput(0, hou_parent.node("pointvelocity2"))
hou_parent.node("attribute1").setInput(0, hou_parent.node("pointvelocity1"))
hou_parent.node("timeshift1").setInput(0, hou_parent.node("particlefluidsurface1"))
hou_parent.node("attribwrangle3").setInput(0, hou_parent.node("timeshift1"))
hou_parent.node("rop_alembic1").setInput(0, hou_parent.node("attribwrangle3"))
hou_parent.node("attribwrangle3").setDisplayFlag(True)
apply_frame_range([n for n in hou_parent.children() if n not in _before])
print("FX template Subframe for changing Topology v001 rebuilt in", hou_parent.path())
