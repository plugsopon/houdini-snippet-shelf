# ============================================================================
# transform -> orient + scale   (paste into Houdini Python Shell)
#
# Select the node whose points carry 3@transform, then run. A wrangle
# "transform_to_orient" is inserted right after it, and every node that was
# wired to that node's output is re-wired to the wrangle.
# Nothing else is changed.
# ============================================================================
import hou

NODE   = ""      # "" = the first selected node; or a name in the open network / a full path
REWIRE = True    # False = only add the wrangle, keep the downstream wiring

SNIPPET = r'''
// 3@transform -> p@orient + v@scale (+ f@pscale when the scale is uniform)
// Houdini multiplies row vectors (v * M), so M = S * R  (scale first, then rotate).
matrix3 M = 3@transform;

// a mirrored transform (negative determinant) can't be a quaternion:
// flip the X row out first, give it back as a negative X scale
float flip = determinant(M) < 0 ? -1 : 1;
matrix3 F = set(flip, 0, 0,  0, 1, 0,  0, 0, 1);
M = F * M;

matrix3 R = polardecomp(M);          // pure rotation (the closest one if M has shear)
matrix3 S = M * transpose(R);        // what's left = scale (diagonal)
vector sc = set(getcomp(S, 0, 0) * flip, getcomp(S, 1, 1), getcomp(S, 2, 2));

p@orient = quaternion(R);

// uniform scale -> pscale only, otherwise scale; one of them stays 1 because
// Copy to Points multiplies pscale and scale together
if (flip > 0 && abs(sc.x - sc.y) < 1e-5 && abs(sc.x - sc.z) < 1e-5) {
    f@pscale = sc.x;
    v@scale  = {1, 1, 1};
} else {
    f@pscale = 1;
    v@scale  = sc;
}

removepointattrib(0, "transform");   // transform always wins over orient/scale
'''


def pick():
    if NODE:
        ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor) if hou.isUIAvailable() else None
        here = ne.pwd() if ne else hou.node("/obj")
        n = here.node(NODE) or hou.node(NODE)
        if n is None:
            raise hou.Error("Node not found: %r" % NODE)
        return n
    sel = hou.selectedNodes()
    if not sel:
        raise hou.Error("Select the node with 3@transform first (or set NODE).")
    return sel[0]


src = pick()
if src.type().category().name() != "Sop":
    raise hou.Error("%s is not a SOP node." % src.path())
downstream = [(c.outputNode(), c.inputIndex()) for c in src.outputConnections()]
w = src.parent().createNode("attribwrangle", "transform_to_orient")
w.setInput(0, src)
w.parm("snippet").set(SNIPPET)
w.setPosition(src.position() + hou.Vector2(0, -1))
if REWIRE:
    for node, idx in downstream:
        node.setInput(idx, w)
w.setSelected(True, clear_all_selected=True)
if src.isDisplayFlagSet():
    w.setDisplayFlag(True)
print("inserted %s (%d downstream input(s) re-wired)" % (w.path(), len(downstream) if REWIRE else 0))
