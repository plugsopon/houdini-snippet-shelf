"""Convert FX Template .cpio files into paste-able Python (hou asCode) + VEX, and round-trip verify.

Writes C:/.../scratchpad/fx_templates_export.json : [{name, version, category, notes, author, created,
thumbnail, script, vex:[{node, code}], check:{...}}]
"""
import hou, os, json, re, sys

ROOT = r"D:\OneDrive\FXTD\template\All\Plug"
OUT = r"C:\Users\Plug\AppData\Local\Temp\claude\P--Project-Dremzo-dremzo-web\f86d1fcf-968f-48e3-87d3-8ad88634a62f\scratchpad\fx_templates_export.json"
SKIP = set(sys.argv[1:])

HEADER = '''# ============================================================================
# FX Template: {name}  ({version})  - rebuilt as Python so it can be pasted
# anywhere (Windows > Python Shell). Original: {ctx}.cpio from the FX Template
# library. Notes: {notes}
#
# HOW TO USE: open a {ctx} network in the Network Editor (e.g. dive inside a
# {hint}), then paste this whole block into the Python Shell and press Enter.
# Nodes are created in that network. Set TARGET to force a network path.
# ============================================================================
import hou

TARGET = ""   # e.g. "/obj/geo1" ; "" = the network the Network Editor is showing

if TARGET:
    hou_parent = hou.node(TARGET)
else:
    _ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    hou_parent = _ne.pwd() if _ne else None
if hou_parent is None:
    raise hou.Error("Open a {ctx} network in the Network Editor, or set TARGET.")
if hou_parent.childTypeCategory().name() != "{ctx}":
    raise hou.Error("This template needs a {ctx} network, but %s holds %s nodes."
                    % (hou_parent.path(), hou_parent.childTypeCategory().name()))

'''

def container(ctx):
    obj = hou.node("/obj")
    if ctx == "Object":
        return obj
    if ctx == "Sop":
        return obj.createNode("geo", "tmp_sop")
    if ctx == "Dop":
        return obj.createNode("dopnet", "tmp_dop")
    raise RuntimeError("unsupported context " + ctx)

def snapshot(parent, names=None):
    """name -> (type, inputs, non-default evaluated parms) for comparison."""
    out = {}
    for n in parent.allSubChildren() if parent.path() != "/obj" else [c for top in parent.children() if (names is None or top.name() in names) for c in [top] + list(top.allSubChildren())]:
        key = n.path().replace(parent.path(), "", 1) if parent.path() != "/obj" else n.path()
        parms = {}
        for p in n.parms():
            try:
                if not p.isAtDefault():
                    v = p.eval()
                    parms[p.name()] = round(v, 5) if isinstance(v, float) else v
            except Exception:
                pass
        out[key] = (n.type().name(), [i.name() if i else None for i in n.inputs()], parms)
    return out

results = []
for tname in sorted(os.listdir(ROOT)):
    if tname in SKIP:
        continue
    tdir = os.path.join(ROOT, tname)
    for ver in sorted(os.listdir(tdir)):
        vdir = os.path.join(tdir, ver)
        cpios = [f for f in os.listdir(vdir) if f.lower().endswith(".cpio")]
        if not cpios:
            print("skip (no cpio):", tname, ver); continue
        ctx = os.path.splitext(cpios[0])[0]
        meta = {}
        jp = os.path.join(vdir, ctx + ".json")
        if os.path.exists(jp):
            meta = json.load(open(jp, encoding="utf8"))
        thumb = os.path.join(vdir, "thumbnail.jpg")

        hou.hipFile.clear(suppress_save_prompt=True)
        par = container(ctx)
        before = set(par.children())
        load_warn = ""
        try:
            par.loadItemsFromFile(os.path.join(vdir, cpios[0]))
        except hou.LoadWarning as w:
            load_warn = str(w).strip()[:300]
        tops = [n for n in par.children() if n not in before]
        other_items = [i for i in par.allItems() if not isinstance(i, hou.Node)]
        names = set(n.name() for n in tops)
        orig = snapshot(par, names if ctx == "Object" else None)

        # --- code: every top node, then wires between them -----------------
        body = []
        for n in tops:
            body.append("# ---- %s (%s) ----" % (n.name(), n.type().name()))
            body.append(n.asCode(brief=True, recurse=True, save_spare_parms=True, save_box_membership=False))
        wires = []
        for n in tops:
            for i, src in enumerate(n.inputs()):
                if src is not None and src in tops:
                    wires.append('hou_parent.node("%s").setInput(%d, hou_parent.node("%s"))' % (n.name(), i, src.name()))
        for n in tops:
            if n.isDisplayFlagSet() if hasattr(n, "isDisplayFlagSet") else False:
                wires.append('hou_parent.node("%s").setDisplayFlag(True)' % n.name())
        script = HEADER.format(name=tname, version=ver, ctx=ctx,
                               notes=(meta.get("notes", "") or "").replace("\n", " / "),
                               hint="Geometry node" if ctx == "Sop" else "/obj")
        script += "\n".join(body) + "\n\n# ---- connections between the template's top nodes ----\n" + "\n".join(wires) + "\n"
        script += 'print("FX template %s %s rebuilt in", hou_parent.path())\n' % (tname.replace('"', "'"), ver)

        vex = []
        for n in [n for t in tops for n in [t] + list(t.allSubChildren())]:
            for pn in ("snippet", "vexsnippet", "python"):
                p = n.parm(pn)
                if p is not None:
                    try:
                        code = p.unexpandedString()
                    except hou.OperationFailed:
                        code = p.evalAsString()
                    if code and code.strip():
                        vex.append({"node": n.path().replace(par.path() + "/", ""), "type": n.type().name(), "parm": pn,
                                    "lang": "python" if pn == "python" else "vex", "code": code})

        # --- round trip: rebuild from the script in a fresh scene -----------
        hou.hipFile.clear(suppress_save_prompt=True)
        par2 = container(ctx)
        g = {"hou": hou}
        check = {"ok": False}
        try:
            try:
                exec(script.replace('TARGET = ""', 'TARGET = "%s"' % par2.path()), g)
            except hou.LoadWarning:
                pass
            rebuilt = snapshot(par2, names if ctx == "Object" else None)
            missing = sorted(set(orig) - set(rebuilt))
            extra = sorted(set(rebuilt) - set(orig))
            diffs = []
            for k in orig:
                if k in rebuilt and orig[k] != rebuilt[k]:
                    a, b = orig[k], rebuilt[k]
                    what = "type" if a[0] != b[0] else "inputs" if a[1] != b[1] else "parms:" + ",".join(sorted(x for x in set(a[2]) | set(b[2]) if a[2].get(x) != b[2].get(x)))[:120]
                    diffs.append((k, what))
            check = {"ok": not missing and not extra and not diffs, "nodes": len(orig),
                     "missing": missing[:10], "extra": extra[:10], "diffs": diffs[:10],
                     "non_node_items_not_rebuilt": len(other_items)}
        except Exception as e:
            check = {"ok": False, "error": repr(e)[:300]}

        results.append({"name": tname, "version": ver, "category": ctx, "notes": meta.get("notes", ""),
                        "author": meta.get("author", "Plug"), "created": meta.get("created", ""),
                        "thumbnail": thumb if os.path.exists(thumb) else "", "script": script,
                        "vex": vex, "check": check, "load_warning": load_warn, "lines": script.count("\n")})
        if load_warn: print("   load warning:", load_warn.replace(chr(10)," ")[:160])
        print("%-50s %s %-6s nodes=%s ok=%s lines=%d vex=%d %s" % (tname[:50], ver, ctx, check.get("nodes"), check.get("ok"),
              script.count("\n"), len(vex), {k: v for k, v in check.items() if k in ("missing", "extra", "diffs", "error", "non_node_items_not_rebuilt") and v}))

json.dump(results, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
print("wrote", OUT)
