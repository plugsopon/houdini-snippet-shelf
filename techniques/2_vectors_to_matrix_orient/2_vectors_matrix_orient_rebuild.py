# ============================================================================
# FX Template: Convert_2 Vectors_to_Mat_2_Vectors_to_Orient  (v001)  - rebuilt as Python so it can be pasted
# anywhere (Windows > Python Shell). Original: Sop.cpio from the FX Template
# library. Notes: Convert  / 2 Vectors to Mat / 2 Vectors to Orient
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


# ---- add1 (add) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/add1
hou_node = hou_parent.createNode("add", "add1", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(12.7017, -1.21282))
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

# Code for /obj/tmp_sop/add1/points parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/add1")
hou_parm = hou_node.parm("points")
hou_parm.deleteAllKeyframes()
hou_parm.set(1)


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

hou_node.setUserData("___Version___", "21.0.671")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("21.0.671")
# Update the parent node.
hou_parent = hou_node


# Restore the parent and current nodes.
hou_parent = hou_parent.parent()
hou_node = hou_node.parent()


# ---- attribwrangle2 (attribwrangle) ----
# Initialize parent node variable.
if locals().get("hou_parent") is None:
    hou_parent = hou.node("/obj/tmp_sop")

# Code for /obj/tmp_sop/attribwrangle2
hou_node = hou_parent.createNode("attribwrangle", "attribwrangle2", run_init_scripts=False, load_contents=True, exact_type_name=True)
hou_node.move(hou.Vector2(12.6987, -2.17601))
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

hou_parm_template_group = hou.ParmTemplateGroup()
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("folder1", "Code", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("group", "Group", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="opmenu -l -a attribvop1 bindgroup", item_generator_script_language=hou.scriptLanguage.Hscript, menu_type=hou.menuType.StringToggle)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "script_action": "import soputils\nkwargs['geometrytype'] = kwargs['node'].parmTuple('grouptype')\nkwargs['inputindex'] = 0\nsoputils.selectGroupParm(kwargs)", "script_action_help": "Select geometry from an available viewport.", "script_action_icon": "BUTTONS_reselect"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("grouptype", "Group Type", menu_items=(["guess","vertices","edges","points","prims"]), menu_labels=(["Guess from Group","Vertices","Edges","Points","Primitives"]), default_value=0, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.MenuParmTemplate("class", "Run Over", menu_items=(["detail","primitive","point","vertex","number"]), menu_labels=(["Detail (only once)","Primitives","Points","Vertices","Numbers"]), default_value=2, icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False, is_button_strip=False, strip_uses_icons=False)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("vex_numcount", "Number Count", 1, default_value=([10]), min=0, max=10000, min_is_strict=True, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ class != number }")
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.IntParmTemplate("vex_threadjobsize", "Thread Job Size", 1, default_value=([1024]), min=1, max=10000, min_is_strict=True, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.Base1, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal, menu_use_token=False)
hou_parm_template2.setConditional(hou.parmCondType.HideWhen, "{ class != number }")
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("folder_generatedparms_snippet", "Generated Channel Parameters", folder_type=hou.folderType.Simple, default_value=0, ends_tab_group=False)
hou_parm_template2.setTags({"group_type": "simple", "sidefx::look": "blank"})
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("N", "N", 3, default_value=([0, 0, 0]), min=0, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.FloatParmTemplate("up", "Up", 3, default_value=([0, 0, 0]), min=0, max=1, min_is_strict=False, max_is_strict=False, look=hou.parmLook.Regular, naming_scheme=hou.parmNamingScheme.XYZW)
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("snippet", "VEXpression", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="import vexpressionmenu\n\nreturn vexpressionmenu.buildSnippetMenu('attribwrangle/snippet', kwargs=kwargs)", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.StringReplace)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "editor": "1", "editorlang": "VEX", "editorlines": "8-30", "script_action": "import vexpressionmenu\n\nnode = kwargs['node']\nparmname = 'snippet'\n\nvexpressionmenu.createSpareParmsFromChCalls(node, parmname)", "script_action_help": "Creates spare parameters for each unique call of ch() ", "script_action_icon": "BUTTONS_create_parm_from_ch"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("exportlist", "Attributes to Create", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vex_strict", "Enforce Prototypes", default_value=False, default_expression='off', default_expression_language=hou.scriptLanguage.Hscript)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "script_callback": ""})
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
# Code for parameter template
hou_parm_template = hou.FolderParmTemplate("folder1_1", "Bindings", folder_type=hou.folderType.Tabs, default_value=0, ends_tab_group=False)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("autobind", "Autobind by Name", default_value=True, default_expression='on', default_expression_language=hou.scriptLanguage.Hscript)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("bindings", "Number of Bindings", folder_type=hou.folderType.MultiparmBlock, default_value=0, ends_tab_group=False)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "multistartoffset": "1"})
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("bindname#", "Attribute Name", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("bindparm#", "VEX Parameter", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("groupautobind", "Autobind Groups by Name", default_value=True, default_expression='on', default_expression_language=hou.scriptLanguage.Hscript)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.FolderParmTemplate("groupbindings", "Group Bindings", folder_type=hou.folderType.MultiparmBlock, default_value=0, ends_tab_group=False)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "multistartoffset": "1"})
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("bindgroupname#", "Group Name", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.addParmTemplate(hou_parm_template3)
# Code for parameter template
hou_parm_template3 = hou.StringParmTemplate("bindgroupparm#", "VEX Parameter", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.addParmTemplate(hou_parm_template3)
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vex_cwdpath", "Evaluation Node Path", 1, default_value=(["."]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.NodeReference, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "oprelative": "."})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vex_outputmask", "Export Parameters", 1, default_value=(["*"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vex_updatenmls", "Update Normals If Displaced", default_value=False, default_expression='off', default_expression_language=hou.scriptLanguage.Hscript)
hou_parm_template2.setTags({"autoscope": "0000000000000000", "script_callback": ""})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vex_matchattrib", "Attribute to Match", 1, default_value=(["id"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.ToggleParmTemplate("vex_inplace", "Compute Results In Place", default_value=False, default_expression='off', default_expression_language=hou.scriptLanguage.Hscript)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vex_selectiongroup", "Output Selection Group", 1, default_value=([""]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=([]), menu_labels=([]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
# Code for parameter template
hou_parm_template2 = hou.StringParmTemplate("vex_precision", "VEX Precision", 1, default_value=(["auto"]), naming_scheme=hou.parmNamingScheme.Base1, string_type=hou.stringParmType.Regular, menu_items=(["auto","32","64"]), menu_labels=(["Auto","32-bit","64-bit"]), icon_names=([]), item_generator_script="", item_generator_script_language=hou.scriptLanguage.Python, menu_type=hou.menuType.Normal)
hou_parm_template2.setTags({"autoscope": "0000000000000000"})
hou_parm_template.addParmTemplate(hou_parm_template2)
hou_parm_template_group.append(hou_parm_template)
# Code for parameter template
hou_parm_template = hou.ToggleParmTemplate("vex_strictvariables", "Standard Variable Names Only", default_value=True, default_expression='on', default_expression_language=hou.scriptLanguage.Hscript)
hou_parm_template.setScriptCallbackLanguage(hou.scriptLanguage.Python)
hou_parm_template.setTags({"autoscope": "0000000000000000", "script_callback_language": "python"})
hou_parm_template_group.append(hou_parm_template)
hou_node.setParmTemplateGroup(hou_parm_template_group)
# Code for /obj/tmp_sop/attribwrangle2/snippet parm 
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribwrangle2")
hou_parm = hou_node.parm("snippet")
hou_parm.deleteAllKeyframes()
hou_parm.set("v@N = chv('N');\nv@up = chv('up');\n\n// 2 vectors to orient\np@orient = quaternion(maketransform(v@N, v@up));\n\n// 2 vectors to mat\nmatrix3 xform1 = maketransform(v@N, v@up);\n3@xform1 = xform1;\n\n//Oriet to Mat\nmatrix3 xform2 = qconvert(p@orient);\n3@xform2 = xform2;")


# Code for /obj/tmp_sop/attribwrangle2/N parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribwrangle2")
hou_parm_tuple = hou_node.parmTuple("N")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 0, 1))


# Code for /obj/tmp_sop/attribwrangle2/up parm tuple
if locals().get("hou_node") is None:
    hou_node = hou.node("/obj/tmp_sop/attribwrangle2")
hou_parm_tuple = hou_node.parmTuple("up")
hou_parm_tuple.deleteAllKeyframes()
hou_parm_tuple.set((0, 1, 0))


hou_node.setExpressionLanguage(hou.exprLanguage.Hscript)

# Code to establish connections for /obj/tmp_sop/attribwrangle2
hou_node = hou_parent.node("attribwrangle2")
if hou_parent.node("add1") is not None:
    hou_node.setInput(0, hou_parent.node("add1"), 0)
hou_node.setUserData("___Version___", "")
if hasattr(hou_node, "syncNodeVersionIfNeeded"):
    hou_node.syncNodeVersionIfNeeded("")


# ---- connections between the template's top nodes ----
hou_parent.node("attribwrangle2").setInput(0, hou_parent.node("add1"))
hou_parent.node("attribwrangle2").setDisplayFlag(True)
apply_frame_range([n for n in hou_parent.children() if n not in _before])
print("FX template Convert_2 Vectors_to_Mat_2_Vectors_to_Orient v001 rebuilt in", hou_parent.path())
