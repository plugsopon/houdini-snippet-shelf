# ============================================================================
# FX Template: My First Shot  (v002)  - rebuilt as Python so it can be pasted
# anywhere (Windows > Python Shell). Original: Object.cpio from the FX Template
# library. Notes: Good v2
#
# HOW TO USE: open a Object network in the Network Editor (e.g. dive inside a
# /obj), then paste this whole block into the Python Shell and press Enter.
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
    raise hou.Error("Open a Object network in the Network Editor, or set TARGET.")
if hou_parent.childTypeCategory().name() != "Object":
    raise hou.Error("This template needs a Object network, but %s holds %s nodes."
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


# ---- geo1 (geo) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj")

# Code for /obj/geo1
hou_node = hou_parent.createNode("geo", "geo1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(2.1616, -0.682319))
hou_node.setSelectableInViewport(True)
hou_node.showOrigin(False)
hou_node.useXray(False)
hou_node.setDisplayFlag(True)
hou_node.hide(False)
hou_node.setSelected(True)

hou_parm_template_group = hou.ParmTemplateGroup()
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("stdswitcher4", "Transform", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
hou_parm_template.setTags({"sidefx::switcher": "stdswitcher"})
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("xOrd", "Transform Order", menu_items=(["srt","str","rst","rts","tsr","trs"]), menu_labels=(["Scale Rot Trans","Scale Trans Rot","Rot Scale Trans","Rot Trans Scale","Trans Scale Rot","Trans Rot Scale"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.setJoinWithNext(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("rOrd", "Rotate Order", menu_items=(["xyz","xzy","yxz","yzx","zxy","zyx"]), menu_labels=(["Rx Ry Rz","Rx Rz Ry","Ry Rx Rz","Ry Rz Rx","Rz Rx Ry","Rz Ry Rx"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.hideLabel(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("t", "Translate", 3, default_value=([0, 0, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"autoscope": "1111111111111111111111111111111", "script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 0)", "script_action_help": "Select an object to match the translation with.", "script_action_icon": "BUTTONS_match_transform"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("r", "Rotate", 3, default_value=([0, 0, 0]), min=0, max=360, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"autoscope": "1111111111111111111111111111111", "script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 1)", "script_action_help": "Select an object to match the rotation with.", "script_action_icon": "BUTTONS_match_rotation"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("s", "Scale", 3, default_value=([1, 1, 1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"autoscope": "1111111111111111111111111111111", "script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 2)", "script_action_help": "Select an object to match the scale with.", "script_action_icon": "BUTTONS_match_scale"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("p", "Pivot Translate", 3, default_value=([0, 0, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 3)", "script_action_help": "Select an object to match the pivot with.", "script_action_icon": "BUTTONS_match_pivot"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("pr", "Pivot Rotate", 3, default_value=([0, 0, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 4)", "script_action_help": "Select an object to match the pivot rotation with.", "script_action_icon": "BUTTONS_match_pivot_rotation"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("scale", "Uniform Scale", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("pre_xform", "Modify Pre-Transform", menu_items=(["clean","cleantrans","cleanrot","cleanscales","extract","reset"]), menu_labels=(["Clean Transform","Clean Translates","Clean Rotates","Clean Scales","Extract Pre-transform","Reset Pre-transform"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("keeppos", "Keep Position When Parenting", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("childcomp", "Child Compensation", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("constraints_on", "Enable Constraints", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("constraints_path", "Constraints", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ constraints_on == 0 }")
hou_parm_template2.setTags({"opfilter": "!!CHOP", "oprelative": ".", "script_action": "import objecttoolutils\nobjecttoolutils.constraintsMenu(kwargs)", "script_action_help": "", "script_action_icon": "BUTTONS_add_constraints"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("lookatpath", "Look At", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template2.setTags({"opfilter": "!!OBJ!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("lookupobjpath", "Look Up Object", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template2.setTags({"opfilter": "!!OBJ!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("lookup", "Look At Up Vector", 1, default_value=(["on"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["off","on","quat","pos","obj"]), menu_labels=(["Don't Use Up Vector","Use Up Vector","Use Quaternions","Use Global Position","Use Up Object"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("pathobjpath", "Path Object", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template2.setTags({"opfilter": "!!SOP!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("roll", "Roll", 1, default_value=([0]), min=-360, max=360, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Angle, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("pos", "Position", 1, default_value=([0]), min=0, max=10, min_is_strict=True, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("uparmtype", "Parameterization", menu_items=(["uniform","arc"]), menu_labels=(["Uniform","Arc Length"]), default_value=1, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("pathorient", "Orient Along Path", 1, default_value=([1]), min=0, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("up", "Orient Up Vector", 3, default_value=([0, 1, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Vector, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("bank", "Auto-Bank factor", 1, default_value=([0]), min=-1, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("stdswitcher4_1", "Render", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
hou_parm_template.setTags({"sidefx::switcher": "stdswitcher"})
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("shop_materialpath", "Material", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"opfilter": "!!CUSTOM/MATERIAL!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("shop_materialopts", "Options", menu_items=([]), menu_labels=([]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Mini, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("tdisplay", "Display", default_value=False)
hou_parm_template2.hideLabel(True)
hou_parm_template2.setJoinWithNext(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("display", "Display", 1, default_value=([1]), min=0, max=1, min_is_strict=True, max_is_strict=True, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("viewportlod", "Display As", menu_items=(["full","points","box","centroid","hidden","subd"]), menu_labels=(["Full Geometry","Point Cloud","Bounding Box","Centroid","Hidden","Subdivision Surface / Curves"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.setHelp("Choose how the object's geometry should be rendered in the viewport")
hou_parm_template2.setTags({"spare_category": "Render"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vm_rendervisibility", "Render Visibility", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["*","primary","primary|shadow","-primary","-diffuse","-diffuse&-reflect&-refract",""]), menu_labels=(["Visible to all","Visible only to primary rays","Visible only to primary and shadow rays","Invisible to primary rays (Phantom)","Invisible to diffuse rays","Invisible to secondary rays","Invisible (Unrenderable)"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace)
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "rendervisibility", "spare_category": "Render"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vm_rendersubd", "Render Polygons As Subdivision (Mantra)", default_value=False)
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "rendersubd", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vm_subdstyle", "Subdivision Style", 1, default_value=(["mantra_catclark"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["mantra_catclark","osd_catclark"]), menu_labels=(["Mantra Catmull-Clark","OpenSubdiv Catmull-Clark"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "subdstyle", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vm_subdgroup", "Subdivision Group", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "subdgroup", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("vm_osd_quality", "Open Subdiv Quality", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 vm_subdstyle != osd_catclark }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "osd_quality", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("vm_osd_vtxinterp", "OSD Vtx Interp", 1, default_value=([2]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["No vertex interpolation","Edges only","Edges and Corners"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 vm_subdstyle != osd_catclark }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "osd_vtxinterp", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("vm_osd_fvarinterp", "OSD FVar Interp", 1, default_value=([4]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2","3","4","5"]), menu_labels=(["Smooth everywhere","Sharpen corners only","Sharpen edges and corners","Sharpen edges and propagated corners","Sharpen all boundaries","Bilinear interpolation"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 vm_subdstyle != osd_catclark }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "osd_fvarinterp", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0", "Shading", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("categories", "Categories", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("A list of tags which can be used to select the object")
hou_parm_template3.setTags({"spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("reflectmask", "Reflection Mask", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReferenceList, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("Objects that will be reflected on this object.")
hou_parm_template3.setTags({"opexpand": "1", "opfilter": "!!OBJ/GEOMETRY!!", "oprelative": "/obj", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("refractmask", "Refraction Mask", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReferenceList, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("Objects that will be refracted on this object.")
hou_parm_template3.setTags({"opexpand": "1", "opfilter": "!!OBJ/GEOMETRY!!", "oprelative": "/obj", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("lightmask", "Light Mask", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReferenceList, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("Lights that illuminate this object.")
hou_parm_template3.setTags({"opexpand": "1", "opfilter": "!!OBJ/LIGHT!!", "oprelative": "/obj", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("lightcategories", "Light Selection", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("vm_lpetag", "LPE Tag", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "lpetag", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("vm_volumefilter", "Volume Filter", 1, default_value=(["box"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["box","gaussian","bartlett","catrom","hanning","blackman","sinc"]), menu_labels=(["Box Filter","Gaussian","Bartlett (triangle)","Catmull-Rom","Hanning","Blackman","Sinc (sharpening)"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "filter", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_volumefilterwidth", "Volume Filter Width", 1, default_value=([1]), min=0.001, max=5, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "filterwidth", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_matte", "Matte shading", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "matte", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_rayshade", "Raytrace Shading", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "rayshade", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0_1", "Sampling", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.MenuParmTemplate("geo_velocityblur", "Geometry Velocity Blur", menu_items=(["off","on","accelblur"]), menu_labels=(["No Velocity Blur","Velocity Blur","Acceleration Blur"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ allowmotionblur == 0 }")
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("geo_accelattribute", "Acceleration Attribute", 1, default_value=(["accel"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setConditional(hou.parmCondType.HideWhen, "{ geo_velocityblur != accelblur }")
hou_parm_template3.setTags({"spare_category": "Sampling"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0_2", "Dicing", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_shadingquality", "Shading Quality", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "shadingquality", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_flatness", "Dicing Flatness", 1, default_value=([0.05]), min=0, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "flatness", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_raypredice", "Ray Predicing", 1, default_value=([0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["Disable Predicing","Full Predicing","Precompute Bounds"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "raypredice", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_curvesurface", "Shade Curves As Surfaces", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "curvesurface", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0_3", "Geometry", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_rmbackface", "Backface Removal", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "rmbackface", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("shop_geometrypath", "Procedural Shader", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"opfilter": "!!SHOP/GEOMETRY!!", "oprelative": ".", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_forcegeometry", "Force Procedural Geometry Output", default_value=True)
hou_parm_template3.setTags({"spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_rendersubdcurves", "Render Polygon Curves As Subdivision (Mantra)", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "rendersubdcurves", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_renderpoints", "Render As Points (Mantra)", 1, default_value=([2]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["No Point Rendering","Render Only Points","Render Unconnected Points"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "renderpoints", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_renderpointsas", "Render Points As (Mantra)", 1, default_value=([0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1"]), menu_labels=(["Spheres","Circles"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ vm_renderpoints == 0 }")
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "renderpointsas", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_usenforpoints", "Use N For Point Rendering", default_value=False)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ vm_renderpoints == 0 }")
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "usenforpoints", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_pointscale", "Point Scale", 1, default_value=([1]), min=0, max=10, min_is_strict=True, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ vm_renderpoints == 0 }")
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "pointscale", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_pscalediameter", "Treat Point Scale as Diameter Instead of Radius", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "pscalediameter", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_metavolume", "Metaballs as Volume", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "metavolume", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_coving", "Coving", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["Disable Coving","Coving for displacement/sub-d","Coving for all primitives"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "coving", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("vm_materialoverride", "Material Override", 1, default_value=(["compact"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["none","full","compact"]), menu_labels=(["Disabled","Evaluate for Each Primitve/Point","Evaluate Once"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_overridedetail", "Ignore Geometry Attribute Shaders", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "overridedetail", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_procuseroottransform", "Proc Use Root Transform", default_value=True)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "procuseroottransform", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("stdswitcher4_2", "Misc", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
hou_parm_template.setTags({"sidefx::switcher": "stdswitcher"})
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("use_dcolor", "Set Wireframe Color", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("dcolor", "Wireframe Color", 3, default_value=([1, 1, 1]), min=0, max=1, min_is_strict=True, max_is_strict=True, look=hou.parmLook.ColorSquare, naming_scheme=hou.parmNamingScheme.RGBA)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("picking", "Viewport Selecting Enabled", default_value=True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("pickscript", "Select Script", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.FileReference, file_type=hou.fileType.Any, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace)
hou_parm_template2.setTags({"filechooser_mode": "read"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("caching", "Cache Object Transform", default_value=True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vport_shadeopen", "Shade Open Curves In Viewport", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vport_displayassubdiv", "Display as Subdivision in Viewport", default_value=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("vport_onionskin", "Onion Skinning", menu_items=(["off","xform","on"]), menu_labels=(["Off","Transform only","Full Deformation"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
hou_node.setParmTemplateGroup(hou_parm_template_group)
# Code for /obj/geo1/t parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/geo1")
hou_parm_tuple = hou_node.parmTuple("t")
hou_parm_tuple.setAutoscope((True, True, True))


# Code for /obj/geo1/r parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/geo1")
hou_parm_tuple = hou_node.parmTuple("r")
hou_parm_tuple.setAutoscope((True, True, True))


# Code for /obj/geo1/s parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/geo1")
hou_parm_tuple = hou_node.parmTuple("s")
hou_parm_tuple.setAutoscope((True, True, True))


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- geo2 (geo) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj")

# Code for /obj/geo2
hou_node = hou_parent.createNode("geo", "geo2", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(1.56122, 0.349576))
hou_node.setSelectableInViewport(True)
hou_node.showOrigin(False)
hou_node.useXray(False)
hou_node.setDisplayFlag(True)
hou_node.hide(False)
hou_node.setSelected(True)

hou_parm_template_group = hou.ParmTemplateGroup()
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("stdswitcher4", "Transform", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
hou_parm_template.setTags({"sidefx::switcher": "stdswitcher"})
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("xOrd", "Transform Order", menu_items=(["srt","str","rst","rts","tsr","trs"]), menu_labels=(["Scale Rot Trans","Scale Trans Rot","Rot Scale Trans","Rot Trans Scale","Trans Scale Rot","Trans Rot Scale"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.setJoinWithNext(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("rOrd", "Rotate Order", menu_items=(["xyz","xzy","yxz","yzx","zxy","zyx"]), menu_labels=(["Rx Ry Rz","Rx Rz Ry","Ry Rx Rz","Ry Rz Rx","Rz Rx Ry","Rz Ry Rx"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.hideLabel(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("t", "Translate", 3, default_value=([0, 0, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"autoscope": "1111111111111111111111111111111", "script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 0)", "script_action_help": "Select an object to match the translation with.", "script_action_icon": "BUTTONS_match_transform"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("r", "Rotate", 3, default_value=([0, 0, 0]), min=0, max=360, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"autoscope": "1111111111111111111111111111111", "script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 1)", "script_action_help": "Select an object to match the rotation with.", "script_action_icon": "BUTTONS_match_rotation"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("s", "Scale", 3, default_value=([1, 1, 1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"autoscope": "1111111111111111111111111111111", "script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 2)", "script_action_help": "Select an object to match the scale with.", "script_action_icon": "BUTTONS_match_scale"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("p", "Pivot Translate", 3, default_value=([0, 0, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 3)", "script_action_help": "Select an object to match the pivot with.", "script_action_icon": "BUTTONS_match_pivot"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("pr", "Pivot Rotate", 3, default_value=([0, 0, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.setTags({"script_action": "import objecttoolutils\nobjecttoolutils.matchTransform(kwargs, 4)", "script_action_help": "Select an object to match the pivot rotation with.", "script_action_icon": "BUTTONS_match_pivot_rotation"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("scale", "Uniform Scale", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("pre_xform", "Modify Pre-Transform", menu_items=(["clean","cleantrans","cleanrot","cleanscales","extract","reset"]), menu_labels=(["Clean Transform","Clean Translates","Clean Rotates","Clean Scales","Extract Pre-transform","Reset Pre-transform"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("keeppos", "Keep Position When Parenting", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("childcomp", "Child Compensation", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("constraints_on", "Enable Constraints", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("constraints_path", "Constraints", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ constraints_on == 0 }")
hou_parm_template2.setTags({"opfilter": "!!CHOP", "oprelative": ".", "script_action": "import objecttoolutils\nobjecttoolutils.constraintsMenu(kwargs)", "script_action_help": "", "script_action_icon": "BUTTONS_add_constraints"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("lookatpath", "Look At", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template2.setTags({"opfilter": "!!OBJ!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("lookupobjpath", "Look Up Object", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template2.setTags({"opfilter": "!!OBJ!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("lookup", "Look At Up Vector", 1, default_value=(["on"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["off","on","quat","pos","obj"]), menu_labels=(["Don't Use Up Vector","Use Up Vector","Use Quaternions","Use Global Position","Use Up Object"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("pathobjpath", "Path Object", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.hide(True)
hou_parm_template2.setTags({"opfilter": "!!SOP!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("roll", "Roll", 1, default_value=([0]), min=-360, max=360, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Angle, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("pos", "Position", 1, default_value=([0]), min=0, max=10, min_is_strict=True, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("uparmtype", "Parameterization", menu_items=(["uniform","arc"]), menu_labels=(["Uniform","Arc Length"]), default_value=1, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("pathorient", "Orient Along Path", 1, default_value=([1]), min=0, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("up", "Orient Up Vector", 3, default_value=([0, 1, 0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Vector, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("bank", "Auto-Bank factor", 1, default_value=([0]), min=-1, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("stdswitcher4_1", "Render", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
hou_parm_template.setTags({"sidefx::switcher": "stdswitcher"})
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("shop_materialpath", "Material", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"opfilter": "!!CUSTOM/MATERIAL!!", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("shop_materialopts", "Options", menu_items=([]), menu_labels=([]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Mini, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("tdisplay", "Display", default_value=False)
hou_parm_template2.hideLabel(True)
hou_parm_template2.setJoinWithNext(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("display", "Display", 1, default_value=([1]), min=0, max=1, min_is_strict=True, max_is_strict=True, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("viewportlod", "Display As", menu_items=(["full","points","box","centroid","hidden","subd"]), menu_labels=(["Full Geometry","Point Cloud","Bounding Box","Centroid","Hidden","Subdivision Surface / Curves"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.setHelp("Choose how the object's geometry should be rendered in the viewport")
hou_parm_template2.setTags({"spare_category": "Render"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vm_rendervisibility", "Render Visibility", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["*","primary","primary|shadow","-primary","-diffuse","-diffuse&-reflect&-refract",""]), menu_labels=(["Visible to all","Visible only to primary rays","Visible only to primary and shadow rays","Invisible to primary rays (Phantom)","Invisible to diffuse rays","Invisible to secondary rays","Invisible (Unrenderable)"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace)
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "rendervisibility", "spare_category": "Render"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vm_rendersubd", "Render Polygons As Subdivision (Mantra)", default_value=False)
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "rendersubd", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vm_subdstyle", "Subdivision Style", 1, default_value=(["mantra_catclark"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["mantra_catclark","osd_catclark"]), menu_labels=(["Mantra Catmull-Clark","OpenSubdiv Catmull-Clark"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "subdstyle", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vm_subdgroup", "Subdivision Group", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "subdgroup", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("vm_osd_quality", "Open Subdiv Quality", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 vm_subdstyle != osd_catclark }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "osd_quality", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("vm_osd_vtxinterp", "OSD Vtx Interp", 1, default_value=([2]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["No vertex interpolation","Edges only","Edges and Corners"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 vm_subdstyle != osd_catclark }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "osd_vtxinterp", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("vm_osd_fvarinterp", "OSD FVar Interp", 1, default_value=([4]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2","3","4","5"]), menu_labels=(["Smooth everywhere","Sharpen corners only","Sharpen edges and corners","Sharpen edges and propagated corners","Sharpen all boundaries","Bilinear interpolation"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ vm_rendersubd == 0 vm_subdstyle != osd_catclark }")
hou_parm_template2.setTags({"mantra_class": "object", "mantra_name": "osd_fvarinterp", "spare_category": "Geometry"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0", "Shading", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("categories", "Categories", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("A list of tags which can be used to select the object")
hou_parm_template3.setTags({"spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("reflectmask", "Reflection Mask", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReferenceList, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("Objects that will be reflected on this object.")
hou_parm_template3.setTags({"opexpand": "1", "opfilter": "!!OBJ/GEOMETRY!!", "oprelative": "/obj", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("refractmask", "Refraction Mask", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReferenceList, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("Objects that will be refracted on this object.")
hou_parm_template3.setTags({"opexpand": "1", "opfilter": "!!OBJ/GEOMETRY!!", "oprelative": "/obj", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("lightmask", "Light Mask", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReferenceList, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setHelp("Lights that illuminate this object.")
hou_parm_template3.setTags({"opexpand": "1", "opfilter": "!!OBJ/LIGHT!!", "oprelative": "/obj", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("lightcategories", "Light Selection", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("vm_lpetag", "LPE Tag", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "lpetag", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("vm_volumefilter", "Volume Filter", 1, default_value=(["box"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["box","gaussian","bartlett","catrom","hanning","blackman","sinc"]), menu_labels=(["Box Filter","Gaussian","Bartlett (triangle)","Catmull-Rom","Hanning","Blackman","Sinc (sharpening)"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "filter", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_volumefilterwidth", "Volume Filter Width", 1, default_value=([1]), min=0.001, max=5, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "filterwidth", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_matte", "Matte shading", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "matte", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_rayshade", "Raytrace Shading", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "rayshade", "spare_category": "Shading"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0_1", "Sampling", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.MenuParmTemplate("geo_velocityblur", "Geometry Velocity Blur", menu_items=(["off","on","accelblur"]), menu_labels=(["No Velocity Blur","Velocity Blur","Acceleration Blur"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ allowmotionblur == 0 }")
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("geo_accelattribute", "Acceleration Attribute", 1, default_value=(["accel"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setConditional(hou.parmCondType.HideWhen, "{ geo_velocityblur != accelblur }")
hou_parm_template3.setTags({"spare_category": "Sampling"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0_2", "Dicing", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_shadingquality", "Shading Quality", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "shadingquality", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_flatness", "Dicing Flatness", 1, default_value=([0.05]), min=0, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "flatness", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_raypredice", "Ray Predicing", 1, default_value=([0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["Disable Predicing","Full Predicing","Precompute Bounds"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "raypredice", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_curvesurface", "Shade Curves As Surfaces", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "curvesurface", "spare_category": "Dicing"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder0_3", "Geometry", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_rmbackface", "Backface Removal", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "rmbackface", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("shop_geometrypath", "Procedural Shader", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"opfilter": "!!SHOP/GEOMETRY!!", "oprelative": ".", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_forcegeometry", "Force Procedural Geometry Output", default_value=True)
hou_parm_template3.setTags({"spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_rendersubdcurves", "Render Polygon Curves As Subdivision (Mantra)", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "rendersubdcurves", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_renderpoints", "Render As Points (Mantra)", 1, default_value=([2]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["No Point Rendering","Render Only Points","Render Unconnected Points"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "renderpoints", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_renderpointsas", "Render Points As (Mantra)", 1, default_value=([0]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1"]), menu_labels=(["Spheres","Circles"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ vm_renderpoints == 0 }")
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "renderpointsas", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_usenforpoints", "Use N For Point Rendering", default_value=False)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ vm_renderpoints == 0 }")
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "usenforpoints", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("vm_pointscale", "Point Scale", 1, default_value=([1]), min=0, max=10, min_is_strict=True, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1)
hou_parm_template3.setConditional(hou.parmCondType.DisableWhen, "{ vm_renderpoints == 0 }")
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "pointscale", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_pscalediameter", "Treat Point Scale as Diameter Instead of Radius", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "pscalediameter", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_metavolume", "Metaballs as Volume", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "metavolume", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.IntParmTemplate("vm_coving", "Coving", 1, default_value=([1]), min=0, max=10, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=(["0","1","2"]), menu_labels=(["Disable Coving","Coving for displacement/sub-d","Coving for all primitives"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "coving", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("vm_materialoverride", "Material Override", 1, default_value=(["compact"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["none","full","compact"]), menu_labels=(["Disabled","Evaluate for Each Primitve/Point","Evaluate Once"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template3.setTags({"spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_overridedetail", "Ignore Geometry Attribute Shaders", default_value=False)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "overridedetail", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.ToggleParmTemplate("vm_procuseroottransform", "Proc Use Root Transform", default_value=True)
hou_parm_template3.setTags({"mantra_class": "object", "mantra_name": "procuseroottransform", "spare_category": "Geometry"})
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("stdswitcher4_2", "Misc", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
hou_parm_template.setTags({"sidefx::switcher": "stdswitcher"})
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("use_dcolor", "Set Wireframe Color", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FloatParmTemplate("dcolor", "Wireframe Color", 3, default_value=([1, 1, 1]), min=0, max=1, min_is_strict=True, max_is_strict=True, look=hou.parmLook.ColorSquare, naming_scheme=hou.parmNamingScheme.RGBA)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("picking", "Viewport Selecting Enabled", default_value=True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("pickscript", "Select Script", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.FileReference, file_type=hou.fileType.Any, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace)
hou_parm_template2.setTags({"filechooser_mode": "read"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("caching", "Cache Object Transform", default_value=True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vport_shadeopen", "Shade Open Curves In Viewport", default_value=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vport_displayassubdiv", "Display as Subdivision in Viewport", default_value=False)
hou_parm_template2.hide(True)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("vport_onionskin", "Onion Skinning", menu_items=(["off","xform","on"]), menu_labels=(["Off","Transform only","Full Deformation"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
hou_node.setParmTemplateGroup(hou_parm_template_group)
# Code for /obj/geo2/t parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/geo2")
hou_parm_tuple = hou_node.parmTuple("t")
hou_parm_tuple.setAutoscope((True, True, True))


# Code for /obj/geo2/r parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/geo2")
hou_parm_tuple = hou_node.parmTuple("r")
hou_parm_tuple.setAutoscope((True, True, True))


# Code for /obj/geo2/s parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/geo2")
hou_parm_tuple = hou_node.parmTuple("s")
hou_parm_tuple.setAutoscope((True, True, True))


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()



# ---- connections between the template's top nodes ----
hou_parent.node("geo1").setDisplayFlag(True)
hou_parent.node("geo2").setDisplayFlag(True)
apply_frame_range([n for n in hou_parent.children() if n not in _before])
print("FX template My First Shot v002 rebuilt in", hou_parent.path())
