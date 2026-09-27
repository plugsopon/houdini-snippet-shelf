# ============================================================================
# FX Template: Surfacedist  (v001)  - rebuilt as Python so it can be pasted
# anywhere (Windows > Python Shell). Original: Sop.cpio from the FX Template
# library. Notes: Surfacedist
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


# ---- mountain1 (attribnoise::2.0) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/mountain1
hou_node = hou_parent.createNode("attribnoise::2.0", "mountain1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(-4.21321, -1.15947))
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

# Code for /obj/tmp_sop/mountain1/attribs parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("attribs")
hou_parm.deleteAllKeyframes()
hou_parm.set("P")


# Code for /obj/tmp_sop/mountain1/folder1 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("folder1")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain1/noiserange parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("noiserange")
hou_parm.deleteAllKeyframes()
hou_parm.set("zcentered")


# Code for /obj/tmp_sop/mountain1/amplitude parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("amplitude")
hou_parm.deleteAllKeyframes()
hou_parm.set(3.1699999999999999)


# Code for /obj/tmp_sop/mountain1/amplitudev parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("amplitudev")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.54000000000000004)


# Code for /obj/tmp_sop/mountain1/amplitudetype parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("amplitudetype")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain1/amplitudescalev parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm_tuple = hou_node.parmTuple("amplitudescalev")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((1, 1, 0))


# Code for /obj/tmp_sop/mountain1/folder7 parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("folder7")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain1/fractal parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("fractal")
hou_parm.deleteAllKeyframes()
hou_parm.set("hmfT")


# Code for /obj/tmp_sop/mountain1/oct parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("oct")
hou_parm.deleteAllKeyframes()
hou_parm.set(8)


# Code for /obj/tmp_sop/mountain1/rough parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("rough")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.40000000000000002)


# Code for /obj/tmp_sop/mountain1/remapramp2pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("remapramp2pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/mountain1/remapramp2value parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/mountain1")
hou_parm = hou_node.parm("remapramp2value")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/mountain1
hou_node = hou_parent.node("mountain1")
if hou_parent.node("circle1") is not None:
    hou_node.setInput(0, hou_parent.node("circle1"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- circle1 (circle) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/circle1
hou_node = hou_parent.createNode("circle", "circle1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(-4.21321, -0.159473))
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

# Code for /obj/tmp_sop/circle1/type parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/circle1")
hou_parm = hou_node.parm("type")
hou_parm.deleteAllKeyframes()
hou_parm.set("poly")


# Code for /obj/tmp_sop/circle1/divs parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/circle1")
hou_parm = hou_node.parm("divs")
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


# ---- remesh1 (remesh::2.0) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/remesh1
hou_node = hou_parent.createNode("remesh::2.0", "remesh1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(-4.21321, -2.15947))
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

# Code for /obj/tmp_sop/remesh1/targetsize parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/remesh1")
hou_parm = hou_node.parm("targetsize")
hou_parm.deleteAllKeyframes()
hou_parm.set(0.050000000000000003)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/remesh1
hou_node = hou_parent.node("remesh1")
if hou_parent.node("mountain1") is not None:
    hou_node.setInput(0, hou_parent.node("mountain1"), 0)
hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- group1 (groupcreate) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/group1
hou_node = hou_parent.createNode("groupcreate", "group1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(-4.21321, -3.15947))
hou_node.bypass(False)
hou_node.setDisplayFlag(False)
hou_node.hide(False)
hou_node.setHighlightFlag(True)
hou_node.setHardLocked(False)
hou_node.setSoftLocked(False)
hou_node.setSelectableTemplateFlag(False)
hou_node.setSelected(True)
hou_node.setRenderFlag(False)
hou_node.setTemplateFlag(False)
hou_node.setUnloadFlag(False)

# Code for /obj/tmp_sop/group1/groupname parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/group1")
hou_parm = hou_node.parm("groupname")
hou_parm.deleteAllKeyframes()
hou_parm.set("edge")


# Code for /obj/tmp_sop/group1/grouptype parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/group1")
hou_parm = hou_node.parm("grouptype")
hou_parm.deleteAllKeyframes()
hou_parm.set("point")


# Code for /obj/tmp_sop/group1/groupbase parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/group1")
hou_parm = hou_node.parm("groupbase")
hou_parm.deleteAllKeyframes()
hou_parm.set(0)


# Code for /obj/tmp_sop/group1/groupedges parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/group1")
hou_parm = hou_node.parm("groupedges")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/group1/unshared parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/group1")
hou_parm = hou_node.parm("unshared")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/group1
hou_node = hou_parent.node("group1")
if hou_parent.node("remesh1") is not None:
    hou_node.setInput(0, hou_parent.node("remesh1"), 0)
hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- attribwrangle1 (attribwrangle) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/attribwrangle1
hou_node = hou_parent.createNode("attribwrangle", "attribwrangle1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(-4.21621, -4.19937))
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

# Code for /obj/tmp_sop/attribwrangle1/snippet parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribwrangle1")
hou_parm = hou_node.parm("snippet")
hou_parm.deleteAllKeyframes()
hou_parm.set("int pt;\nfloat sd = surfacedist(0,'edge','P',@ptnum,pt,'edge');\n@sd = sd;")


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/attribwrangle1
hou_node = hou_parent.node("attribwrangle1")
if hou_parent.node("group1") is not None:
    hou_node.setInput(0, hou_parent.node("group1"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")

# ---- color1 (color) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/color1
hou_node = hou_parent.createNode("color", "color1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(-4.21321, -5.23727))
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

# Code for /obj/tmp_sop/color1/colortype parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/color1")
hou_parm = hou_node.parm("colortype")
hou_parm.deleteAllKeyframes()
hou_parm.set(3)


# Code for /obj/tmp_sop/color1/rampattribute parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/color1")
hou_parm = hou_node.parm("rampattribute")
hou_parm.deleteAllKeyframes()
hou_parm.set("sd")


# Code for /obj/tmp_sop/color1/ramp2pos parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/color1")
hou_parm = hou_node.parm("ramp2pos")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


# Code for /obj/tmp_sop/color1/ramp2c parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/color1")
hou_parm_tuple = hou_node.parmTuple("ramp2c")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((1, 1, 1))


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/color1
hou_node = hou_parent.node("color1")
if hou_parent.node("attribwrangle1") is not None:
    hou_node.setInput(0, hou_parent.node("attribwrangle1"), 0)
hou_node.setUserData("___toolid___", "sop_color")
hou_node.setUserData("___Version___", "")
hou_node.setUserData("___toolcount___", "2")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")


# ---- connections between the template's top nodes ----
hou_parent.node("mountain1").setInput(0, hou_parent.node("circle1"))
hou_parent.node("remesh1").setInput(0, hou_parent.node("mountain1"))
hou_parent.node("group1").setInput(0, hou_parent.node("remesh1"))
hou_parent.node("attribwrangle1").setInput(0, hou_parent.node("group1"))
hou_parent.node("color1").setInput(0, hou_parent.node("attribwrangle1"))
hou_parent.node("color1").setDisplayFlag(True)
apply_frame_range([n for n in hou_parent.children() if n not in _before])
print("FX template Surfacedist v001 rebuilt in", hou_parent.path())
