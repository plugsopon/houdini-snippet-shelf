"""Helpers for checking Houdini work headlessly with hython.

CLI (run with hython, from a cwd that is NOT a folder full of loose .py files):
  hython hou_tools.py dump    FILE.hipnc [/obj/geo1]      network: types, inputs, flags, non-default parms
  hython hou_tools.py refs    FILE.hipnc                  every file reference, and whether it exists on disk
  hython hou_tools.py compare FILE.hipnc NODE_A NODE_B [frames...]   nearest-neighbour point distance

In a test script:
  sys.path.insert(0, r"<this folder>"); from hou_tools import *
  run_script(path, {"BUILD_DEMO   = True": "BUILD_DEMO   = False"})   # exec a paste-able script with edits
  before = child_names(geo); ...; new = new_children(geo, before)     # nodes a script created
  compare(node_a, node_b, frames=(5, 20, 40))                          # prints + returns worst distances
  for prim, m in packed_transforms(node): angle_deg(axis_of(m, 1), n)   # orientation checks
"""
import glob, os, sys

import hou


def run_script(path, replace=None):
    """Exec a paste-able Python Shell script, after literal find/replace edits of its CONFIG.
    Every find string must exist exactly once, so a renamed CONFIG line fails loudly."""
    code = open(path, encoding="utf8").read()
    for a, b in (replace or {}).items():
        n = code.count(a)
        if n != 1:
            raise RuntimeError("expected %r once in %s, found %d" % (a, os.path.basename(path), n))
        code = code.replace(a, b)
    exec(compile(code, path, "exec"), {"hou": hou, "__name__": "__main__"})


def child_names(net):
    return set(c.name() for c in net.children())


def new_children(net, before):
    """Nodes created since `before` - never look a new node up by its intended name:
    if that name was taken Houdini silently appends 1 (rbd_root_copy -> rbd_root_copy1)."""
    return [c for c in net.children() if c.name() not in before]


def node_or_die(path):
    n = hou.node(path) if isinstance(path, str) else path
    if n is None:
        hint = ""
        if isinstance(path, str) and ":" in path:
            hint = (" - Git Bash rewrote the node path into a Windows path; "
                    "prefix the command with MSYS_NO_PATHCONV=1 or run it from PowerShell")
        raise SystemExit("node not found: %r%s" % (path, hint))
    return n


def compare(a, b, frames=(1,), label=""):
    """Worst nearest-neighbour distance between the points of two SOPs, both directions.
    Point ORDER is not compared (copies, unpacks and USD round-trips reorder points), so
    never sort-and-zip: sorting by coordinates pairs the wrong points and reports a
    false error. Point COUNT is reported separately."""
    a, b = node_or_die(a), node_or_die(b)
    worst = 0.0
    for f in frames:
        hou.setFrame(f)
        pa = [p.position() for p in a.geometry().points()]
        pb = [p.position() for p in b.geometry().points()]
        if not pa or not pb:
            print("%-12s f%-4s %s=%d %s=%d  (empty - nothing compared)" % (label, f, a.name(), len(pa), b.name(), len(pb)))
            worst = float("inf")
            continue
        ab = max(min((x - y).length() for y in pb) for x in pa)
        ba = max(min((x - y).length() for y in pa) for x in pb)
        worst = max(worst, ab, ba)
        flag = "" if len(pa) == len(pb) else "  COUNT MISMATCH"
        print("%-12s f%-4s %s=%d %s=%d  worst=%.7f/%.7f%s" % (label, f, a.name(), len(pa), b.name(), len(pb), ab, ba, flag))
    return worst


def packed_transforms(sop):
    """(prim, hou.Matrix4) for every packed prim, from its full transform.
    Test with isinstance: in H21 `prim.type() == hou.primType.PackedPrim` is False for
    copytopoints' packed prims, so a type() check silently finds nothing."""
    sop = node_or_die(sop)
    return [(p, hou.Matrix4(p.intrinsicValue("packedfulltransform")))
            for p in sop.geometry().prims() if isinstance(p, hou.PackedPrim)]


def axis_of(m, axis=1):
    """Local axis (0=X, 1=Y, 2=Z) of a transform, in world space, unit length.
    Houdini multiplies row vectors, so the axis is a ROW of the 3x3 part."""
    return hou.Vector3([m.at(axis, 0), m.at(axis, 1), m.at(axis, 2)]).normalized()


def angle_deg(a, b):
    """Angle between two directions in degrees, clamped so 1.0000001 doesn't raise."""
    import math
    d = max(-1.0, min(1.0, hou.Vector3(a).normalized().dot(hou.Vector3(b).normalized())))
    return math.degrees(math.acos(d))


def dump(node, depth=0, out=None):
    """Print a network: name [type] inputs, flags, and every non-default parm (truncated)."""
    for c in sorted(node.children(), key=lambda x: -x.position()[1]):
        ins = [i.name() if i else None for i in c.inputs()]
        flags = ("D" if getattr(c, "isDisplayFlagSet", lambda: False)() else "") + \
                ("R" if getattr(c, "isRenderFlagSet", lambda: False)() else "")
        print("  " * depth + "%s [%s] in=%s %s" % (c.name(), c.type().name(), ins, flags))
        vals = []
        for p in c.parms():
            try:
                if p.isAtDefault() or p.parmTemplate().type() == hou.parmTemplateType.FolderSet:
                    continue
                v = p.expression() if p.keyframes() else p.eval()
                s = str(v).replace("\n", "\\n")
                vals.append("%s=%s" % (p.name(), s[:100] + ("..." if len(s) > 100 else "")))
            except hou.Error:
                pass
        if vals:
            print("  " * depth + "    " + " | ".join(vals[:25]))
        if c.children():
            dump(c, depth + 1)


def refs():
    """Every file reference in the loaded hip, evaluated at frame 1, and whether it exists.
    Render-gallery .db files and $F caches that simply were never written show as MISSING
    too - read the path before calling anything broken."""
    rows = []
    for parm, ref in hou.fileReferences():
        if parm is None or ref.startswith(("opdef:", "oplib:")):
            continue
        try:
            v = parm.evalAtFrame(1)
        except hou.Error:
            continue
        if not v or not any(k in v for k in ("/", "\\")):
            continue
        ok = os.path.exists(v) or bool(glob.glob(v.replace("$F", "*")))
        rows.append((ok, parm.path(), ref, v))
        print("%s %s | %s -> %s" % ("OK     " if ok else "MISSING", parm.path(), ref, v))
    return rows


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    if len(sys.argv) < 3 or sys.argv[1] not in ("dump", "refs", "compare"):
        sys.exit(__doc__)
    hou.hipFile.load(sys.argv[2], suppress_save_prompt=True, ignore_load_warnings=True)
    if sys.argv[1] == "dump":
        dump(node_or_die(sys.argv[3] if len(sys.argv) > 3 else "/obj"))
    elif sys.argv[1] == "refs":
        print("HIP =", hou.text.expandString("$HIP"))
        refs()
    else:
        fr = [float(x) for x in sys.argv[5:]] or [1]
        compare(sys.argv[3], sys.argv[4], fr)
