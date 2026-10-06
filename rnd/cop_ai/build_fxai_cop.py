"""Build the FX AI Copernicus HDAs + a demo scene (run with hython, NOT in Plug's live Houdini).

  hython build_fxai_cop.py [--live]     --live also presses Generate once (costs one Seedream call)

Writes:
  ~/Documents/houdini21.0/otls/cop_fxai.hdanc   - FX AI Angle + FX AI Generate (loads on next Houdini start)
  <repo>/hip/cop_ai/fxai_cop_demo.hipnc          - File -> FX AI Angle -> FX AI Generate
"""
import os
import shutil
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OTL = os.path.join(os.path.expanduser("~"), "Documents", "houdini21.0", "otls", "cop_fxai.hdanc").replace("\\", "/")
HIPDIR = os.path.join(REPO, "hip", "cop_ai").replace("\\", "/")
SAMPLE_SRC = r"P:\Project\Dremzo\temp\seedream5-rnd\input_product.jpg"
MODULE = open(os.path.join(HERE, "fxai_cop_module.py"), encoding="utf8").read()

F, S, I, M, B, L, T = (hou.FloatParmTemplate, hou.StringParmTemplate, hou.IntParmTemplate,
                       hou.MenuParmTemplate, hou.ButtonParmTemplate, hou.LabelParmTemplate,
                       hou.ToggleParmTemplate)


def subnet(net, name, n_in):
    s = net.createNode("subnet", name)
    s.parm("inputs").set(n_in)
    s.parm("outputs").set(1)
    for i in range(n_in):
        s.parm("inputlabel%d" % (i + 1)).set("image" if i == 0 else "ref %d" % i)
        s.parm("inputtype%d" % (i + 1)).set(4)          # RGBA
    s.parm("outputlabel1").set("image")
    s.parm("outputtype1").set(4)
    return s


def strmenu(name, label, items, labels, default):
    return S(name, label, 1, default_value=(default,), menu_items=items, menu_labels=labels,
             menu_type=hou.menuType.Normal)


def make_asset(s, type_name, label, ptg, icon, module=None):
    # leave the subnet's own inputs/outputs multiparms in place - they define the connectors -
    # but hide them from the artist
    for n in ("inputs", "outputs"):
        t = ptg.find(n)
        if t:
            t.hide(True); ptg.replace(n, t)
    a = s.createDigitalAsset(name=type_name, hda_file_name=OTL, description=label,
                             min_num_inputs=1, max_num_inputs=len(s.inputLabels()),
                             ignore_external_references=True)
    d = a.type().definition()
    d.setParmTemplateGroup(ptg)          # spare parms on the build node do NOT carry into the asset
    d.setIcon(icon)
    if module:
        d.addSection("PythonModule", module)
        d.setExtraFileOption("PythonModule/IsPython", True)
    secs = d.sections()
    if "Tools.shelf" in secs:            # put both nodes under one TAB-menu folder
        txt = secs["Tools.shelf"].contents()
        import re
        txt = re.sub(r"<toolSubmenu>.*?</toolSubmenu>", "<toolSubmenu>FX AI</toolSubmenu>", txt)
        secs["Tools.shelf"].setContents(txt)
    a.matchCurrentDefinition()
    return a


def build_angle(net):
    s = subnet(net, "fxai_angle_build", 1)
    s.node("outputs").setInput(0, s.node("inputs"), 0)
    ptg = s.parmTemplateGroup()
    ptg.append(L("info", "Camera angle for FX AI Generate", column_labels=(
        "Passes the image through. FX AI Generate reads these values from every Angle node above it.",)))
    ptg.append(F("azimuth", "Orbit (deg)", 1, default_value=(30,), min=-180, max=180,
                 help="+ = clockwise around the subject, 90 = side, 180 = from behind"))
    ptg.append(F("elevation", "Elevation (deg)", 1, default_value=(0,), min=-60, max=60,
                 help="+ = camera higher, looking down; - = hero low angle"))
    ptg.append(strmenu("distance", "Distance", ("keep", "close", "medium", "wide"),
                       ("Keep", "Close-up", "Medium", "Wide"), "keep"))
    ptg.append(S("extra", "Extra camera words", 1, default_value=("",)))
    return make_asset(s, "fxai_angle", "FX AI Angle", ptg, "VIEW_camera")


def build_generate(net):
    s = subnet(net, "fxai_generate_build", 4)
    res = s.createNode("file", "result")
    res.parm("aovs").set(1); res.parm("aov1").set("C"); res.parm("type1").set(2)   # fixed RGB output, file or not
    res.parm("filename").setExpression('chs("../result_file")', hou.exprLanguage.Hscript)
    res.parm("videoframemethod").set(1)                               # by frame
    res.parm("videoframe").setExpression("$F", hou.exprLanguage.Hscript)
    sw = s.createNode("switch", "show") if hou.nodeType(hou.copNodeTypeCategory(), "switch") else None
    if sw is not None:
        sw.setInput(0, s.node("inputs"), 0)                           # nothing generated yet -> pass the input
        sw.setInput(1, res, 0)
        sw.parm("input").setExpression('strlen(chs("../result_file")) > 0', hou.exprLanguage.Hscript)
        s.node("outputs").setInput(0, sw, 0)
    else:
        s.node("outputs").setInput(0, res, 0)
    s.layoutChildren()

    ptg = s.parmTemplateGroup()
    ptg.append(strmenu("model", "Model", ("seedream5", "seedance25"),
                       ("Seedream 5 Pro  (image)", "Seedance 2.5  (video)"), "seedream5"))
    ptg.append(S("prompt", "Prompt", 1, default_value=("",),
                 tags={"editor": "1", "editorlines": "4-10"}))
    g = hou.FolderParmTemplate("img", "Image (Seedream)", folder_type=hou.folderType.Simple)
    g.addParmTemplate(strmenu("size", "Size", ("1K", "2K", "4K"), ("1K", "2K", "4K"), "2K"))
    g.setConditional(hou.parmCondType.HideWhen, '{ model != "seedream5" }')
    ptg.append(g)
    g = hou.FolderParmTemplate("vid", "Video (Seedance)", folder_type=hou.folderType.Simple)
    g.addParmTemplate(strmenu("resolution", "Resolution", ("480p", "720p", "1080p"),
                              ("480p", "720p", "1080p"), "480p"))
    g.addParmTemplate(I("duration", "Duration (s)", 1, default_value=(5,), min=3, max=12))
    g.setConditional(hou.parmCondType.HideWhen, '{ model != "seedance25" }')
    ptg.append(g)
    ptg.append(I("seed", "Seed (0 = random)", 1, default_value=(0,), min=0, max=99999))
    ptg.append(B("generate", "Generate", script_callback="hou.phm().generate(kwargs)",
                 script_callback_language=hou.scriptLanguage.Python,
                 help="Calls the API in the background - you can keep working"))
    ptg.append(S("status", "Status", 1, default_value=("idle",)))
    ptg.append(S("result_file", "Result", 1, default_value=("",), string_type=hou.stringParmType.FileReference,
                 help="Pick any older v###.png/.mp4 here to view it again"))
    ptg.append(B("preview", "Preview prompt", script_callback="hou.phm().preview_prompt(kwargs)",
                 script_callback_language=hou.scriptLanguage.Python))
    ptg.append(S("prompt_preview", "Sent prompt", 1, default_value=("",),
                 tags={"editor": "1", "editorlines": "3-8"}))
    h = hou.FolderParmTemplate("adv", "Internal", folder_type=hou.folderType.Collapsible)
    h.addParmTemplate(T("is_video", "Result is video", default_value=False))
    h.addParmTemplate(S("history", "History (json)", 1, default_value=("[]",),
                        tags={"editor": "1", "editorlines": "3-10"}))
    ptg.append(h)
    return make_asset(s, "fxai_generate", "FX AI Generate (Seedream / Seedance)", ptg, "SHELF_generic",
                      module=MODULE)


def main():
    live = "--live" in sys.argv
    if os.path.exists(OTL):
        try:
            hou.hda.uninstallFile(OTL)
        except hou.OperationFailed:
            pass                          # not loaded in this hython
        os.remove(OTL)
    os.makedirs(HIPDIR, exist_ok=True)
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hipFile.setName(HIPDIR + "/fxai_cop_demo.hipnc")

    net = hou.node("/obj").createNode("copnet", "fxai_cop")
    angle = build_angle(net); angle.destroy()
    gen = build_generate(net); gen.destroy()
    hou.hda.installFile(OTL)

    sample = HIPDIR + "/sample_product.jpg"
    if not os.path.exists(sample):
        shutil.copyfile(SAMPLE_SRC, sample)
    f = net.createNode("file", "load_image")
    f.parm("filename").set("$HIP/sample_product.jpg")
    f.parm("addaovs").pressButton()
    a = net.createNode("fxai_angle", "angle_side")
    a.setInput(0, f, 0)
    a.parm("azimuth").set(45); a.parm("elevation").set(15)
    g = net.createNode("fxai_generate", "seedance_gen")
    g.setInput(0, a, 0)
    g.parm("prompt").set("The reference image shows a cosmetic product on a set.")
    g.setDisplayFlag(True)
    net.layoutChildren()
    hou.hipFile.save()
    print("hda:", OTL)
    print("hip:", hou.hipFile.path())
    print("prompt:", g.hdaModule().build_prompt(g))

    if live:
        g.hdaModule().generate({"node": g}, blocking=True)
        print("status:", g.evalParm("status"))
        print("result:", g.evalParm("result_file"))
        lay = g.layer()
        print("output layer:", lay.bufferResolution() if lay else None)
        hou.hipFile.save()


main()
