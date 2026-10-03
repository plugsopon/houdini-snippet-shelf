# ============================================================================
# Recompute orient from a cache -> LOP PointInstancer   (paste into Houdini Python Shell)
#
# For when all you have is the CACHED geometry of the sim and no sim points.
# Rebuilds one point per piece with P + orient, then instances the rest pieces
# on those points in LOPs. Two modes, picked from the cache itself:
#   - PACKED cache (heavy RBD): orient + scale come straight from each packed
#     prim's packedfulltransform. Nothing is unpacked per frame; only the rest
#     frame is unpacked once for the prototypes.
#   - POLYGON cache (unpacked pieces with a name): Extract Transform with Use
#     Piece Attribute compares every frame to the rest frame.
#
# The two things that make it wrong if left alone:
#   - Prototypes must sit at the origin, around the pivot the points rotate
#     about: packed -> the prim's own pivot (transform set to identity, P = 0,
#     then unpack); polygons -> Extract Transform's pivot (rest centre).
#   - USD prim names cannot hold "-" (piece0-0-0 becomes piece0_0_0), so the
#     instancer finds no prototype by name and skips every instance. Both
#     sides get the same cleaned name.
#
# HOW TO USE
#   1. Open the Geometry network that holds the cache (or set TARGET).
#   2. Set CACHE_NODE (and REST_FRAME), paste into Windows > Python Shell.
#   New nodes are created (ORIENT_* / PACKED_*, LOP_*); existing nodes are not changed.
# ============================================================================

import hou

# ----------------------------- CONFIG ---------------------------------------
TARGET       = ""            # "" = the network the Network Editor is showing
CACHE_NODE   = "filecache1"  # cached sim: packed prims, or polygons, with a piece name
PIECE_ATTR   = "name"        # attribute that names each piece (prim, or point on packed)
REST_FRAME   = 1             # frame where the pieces are at rest (not yet moved)
ADD_LOP      = True          # also build the LOP PointInstancer + a check back in SOPs
# ----------------------------------------------------------------------------


def current_network():
    if TARGET:
        n = hou.node(TARGET)
        if n is None:
            raise hou.Error("TARGET not found: %s" % TARGET)
        return n
    ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor) if hou.isUIAvailable() else None
    if ne is None:
        raise hou.Error("No Network Editor found - open one, or set TARGET.")
    return ne.pwd()


def find(name, net):
    n = net.node(name) or hou.node(name)
    if n is None:
        raise hou.Error("Node not found: %r (looked in %s and as a full path)" % (name, net.path()))
    return n


net = current_network()
if net.childTypeCategory().name() != "Sop":
    raise hou.Error("Open the Geometry (SOP) network that holds %s - %s is not one." % (CACHE_NODE, net.path()))
cache = find(CACHE_NODE, net)
geo = cache.geometry()
if geo is None:
    raise hou.Error("%s has no geometry (cook error?): %s" % (cache.path(), "; ".join(cache.errors())))
PACKED = any(isinstance(p, hou.PackedPrim) for p in geo.prims())
if geo.findPrimAttrib(PIECE_ATTR) is None and not (PACKED and geo.findPointAttrib(PIECE_ATTR)):
    raise hou.Error("%s has no %r attribute on its pieces - set PIECE_ATTR." % (cache.path(), PIECE_ATTR))

ys = [c.position()[1] for c in net.children()]
top = min(ys) - 2
x0 = cache.position()[0]
created = []


def mk(type_name, name, x, y, parent=None):
    n = (parent or net).createNode(type_name, name)
    n.setPosition(hou.Vector2(x0 + x, top + y))
    created.append(n)
    return n


CLEAN_NAME = r"""
// USD prim names allow only letters, digits and _ (piece0-0-0 -> piece0_0_0)
nm = re_replace("[^A-Za-z0-9_]", "_", nm);
if (re_match("^[0-9]", nm)) nm = "_" + nm;
"""
A = {"a": PIECE_ATTR, "clean": CLEAN_NAME}

rest = mk("timeshift", "ORIENT_rest", -3, -1.2)              # the pieces at rest
rest.setInput(0, cache)
rest.parm("frame").deleteAllKeyframes()
rest.parm("frame").set(REST_FRAME)

if PACKED:
    # every frame: one point per packed prim, nothing unpacked
    pts = mk("attribwrangle", "PACKED_points", 0, -2.4)
    pts.setInput(0, cache)
    pts.parm("snippet").set(r"""
// orient (+ scale) straight from the packed prim; P is already the moved pivot
int pr = pointprims(0, @ptnum)[0];
matrix m4 = primintrinsic(0, "packedfulltransform", pr);   // read as 4x4 first: matrix3(primintrinsic(..))
matrix3 m = matrix3(m4);                                   // would read the 16 values as a 3x3
vector s = set(length(set(m.xx, m.xy, m.xz)), length(set(m.yx, m.yy, m.yz)), length(set(m.zx, m.zy, m.zz)));
scale(m, 1.0 / s);
p@orient = quaternion(m);
v@scale = s;   // write on EVERY point: a partial write leaves 0 (instance vanishes) elsewhere
string nm = haspointattrib(0, "%(a)s") ? point(0, "%(a)s", @ptnum) : prim(0, "%(a)s", pr);
%(clean)s
s@%(a)s = nm;
removeprim(0, pr, 0);
""" % A)
    # rest frame only: drop the packed transform -> unpack gives (piece - pivot)
    zero = mk("attribwrangle", "PACKED_protos_origin", -3, -2.4)
    zero.setInput(0, rest)
    zero.parm("snippet").set(r"""
int pr = pointprims(0, @ptnum)[0];
matrix3 I = ident();
setprimintrinsic(0, "transform", pr, I);
v@P = {0, 0, 0};
""")
    protos = mk("unpack", "PACKED_protos_unpack", -3, -3.6)  # cooks once (rest frame only)
    protos.setInput(0, zero)
    protos.parm("transfer_attributes").set(PIECE_ATTR)
else:
    ext = mk("extracttransform", "ORIENT_extract", 0, -2.4)  # one point per piece: P orient pivot name
    ext.setInput(0, rest)
    ext.setInput(1, cache)
    ext.parm("usepieceattrib").set(1)
    ext.parm("pieceattrib").set(PIECE_ATTR)
    ext.parm("pieceattribclass").set(0)                      # Primitive

    pts = mk("attribwrangle", "ORIENT_points", 0, -3.6)
    pts.setInput(0, ext)
    pts.parm("snippet").set(r"""
// prototypes are centred at the origin, so pivot is not needed any more
removepointattrib(0, "pivot");
string nm = s@%(a)s;
%(clean)s
s@%(a)s = nm;
""" % A)

    protos = mk("attribwrangle", "ORIENT_protos", -3, -3.6)  # rest pieces, each at the origin
    protos.setInput(0, rest)
    protos.setInput(1, ext)
    protos.parm("snippet").set(r"""
// move every rest point by its piece's pivot so the piece sits at the origin
int pr = pointprims(0, @ptnum)[0];
string piece = prim(0, "%(a)s", pr);
int ip = findattribval(1, "point", "%(a)s", piece);
v@P -= point(1, "pivot", ip);
""" % A)

path = mk("attribwrangle", "ORIENT_protos_path", -3, -4.8)   # one USD prim per piece, same clean name
path.setInput(0, protos)
path.parm("class").set(1)                                    # Primitives
path.parm("snippet").set(r"""
string nm = s@%(a)s;
%(clean)s
s@path = nm;
""" % A)

t_out = mk("null", "OUT_orient_points", 0, -6)
t_out.setInput(0, pts)
p_out = mk("null", "OUT_orient_protos", -3, -6)
p_out.setInput(0, path)

if ADD_LOP:
    lop = mk("lopnet", "LOP_orient_instancing", -1.5, -7.2)
    si = lop.createNode("sopimport", "root_pieces")          # prims: /root_pieces/piece0_0_0, ...
    si.parm("soppath").set(si.relativePathTo(p_out))
    si.setPosition(hou.Vector2(3, 0))
    inst = lop.createNode("instancer", "instancer1")         # prim: /instancer1
    inst.setInput(1, si)
    inst.setPosition(hou.Vector2(0, -1.5))
    inst.parm("method").set("pointinstancer")
    inst.parm("transformsourcemode").set("extsop")
    inst.parm("pointsoppath").set(inst.relativePathTo(t_out))
    inst.parm("protosourcemode").set("second")
    inst.parm("protopattern").set("/root_pieces/*")          # EVERY piece is its own prototype
    inst.parm("protoindexsrc").set("nameattr")
    inst.parm("nameattr").set(PIECE_ATTR)
    out = lop.createNode("null", "OUT_instances")
    out.setInput(0, inst)
    out.setPosition(hou.Vector2(0, -3))
    out.setDisplayFlag(True)

    li = mk("lopimport::2.0", "LOP_orient_check_import", -1.5, -8.4)
    li.parm("loppath").set(li.relativePathTo(out))
    li.parm("primpattern").set("/instancer1")                # not the hidden prototype meshes
    uu = mk("unpackusd::2.0", "LOP_orient_check_unpackusd", -1.5, -9.6)
    uu.setInput(0, li)
    uu.parm("output").set("polygons")
    uu.parm("iterations").set(2)                             # instancer -> instances -> meshes

print("Orient from %s cache built in %s (%d nodes) -> %s, %s%s" % (
    "packed" if PACKED else "polygon", net.path(), len(created), t_out.name(), p_out.name(),
    (" + LOP_orient_instancing" if ADD_LOP else "")))
