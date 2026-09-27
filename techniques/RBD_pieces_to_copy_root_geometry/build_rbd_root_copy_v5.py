# ============================================================================
# RBD pieces -> copy the ROOT geometry   v005   (paste into Houdini Python Shell)
#
# Re-creates every simulated RBD piece by copying the ORIGINAL (root) piece with
# that piece's full transform (emission rotation + pscale + sim motion).
# Exact match with the sim, and the root geometry can be swapped (hi-res, a
# different model, extra attributes) without re-simulating.
#
# Two ways to read the sim (METHOD):
#   "packed" -> DOP Import "Fetch Geometry": packedfulltransform of each piece
#   "points" -> DOP Import "Create Points to Represent Objects": one point per
#               piece, rebuilt from restxform (emission transform) + pivot +
#               orient + P. Lighter: no geometry comes out of the sim.
#   "both"   -> builds both side by side (display flag on the points one).
#
# ADD_LOP = True also builds the Solaris version: a LOP network with the root
# pieces as prototypes (one prototype per piece, picked by the point's name) and
# a USD PointInstancer driven by the same target points.
#
# HOW TO USE
#   1. Open a network in the Network Editor:
#        - a Geometry (SOP) network -> everything is built right there
#        - /obj                     -> a new "rbd_root_copy" geo is created for it
#   2. Paste the whole thing into Windows > Python Shell and press Enter.
#
#   BUILD_DEMO = True  -> builds the WHOLE setup: the root pieces (ROOT_SOURCE),
#                         a scatter emitter that births pieces every frame, the
#                         Bullet RBD dopnet, and the root-copy chain on top.
#                         ROOT_SOURCE = "fracture" -> a box broken with RBD
#                         Material Fracture; every emitted point picks one
#                         random fracture piece (piece0 .. pieceN-1).
#                         ROOT_SOURCE = "colours"  -> 3 coloured copies of a box.
#   BUILD_DEMO = False -> only adds the root-copy chain to YOUR sim: set DOPNET
#                         and ROOT_PIECES (names in the open network or full paths).
#   Existing nodes are never changed.
# ============================================================================

import hou

# ----------------------------- CONFIG ---------------------------------------
BUILD_DEMO   = True
TARGET       = ""            # "" = the network the Network Editor is showing; or a path
METHOD       = "both"        # "packed" | "points" | "both"
ADD_LOP      = True          # also build the Solaris / USD PointInstancer version
ROOT_SOURCE  = "fracture"    # BUILD_DEMO: "fracture" (fractured box) | "colours" (3 coloured boxes)
EMIT_PER_FRAME = 3           # BUILD_DEMO: new pieces born every frame

DOPNET       = "dopnet1"     # BUILD_DEMO = False: your RBD dopnet
ROOT_PIECES  = "assemble3"   # BUILD_DEMO = False: root pieces with a "name" (piece0, piece1, ...)
OBJ_PATTERN  = "*rbd*"       # DOP objects to import ("*" would also pull in the ground plane)
STRIP_SUFFIX = True          # sim names like piece0_12 -> piece0 (emission-frame suffix)

START_FRAME  = None          # None = playbar start (sim start frame)
LINK_TO_PLAYBAR = False      # True = expression to $RFSTART instead of a fixed number
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


def sop_network(net):
    cat = net.childTypeCategory().name()
    if cat == "Sop":
        return net
    if cat == "Object":
        return net.createNode("geo", "rbd_root_copy")
    raise hou.Error("Open a Geometry (SOP) network or /obj - %s holds %s nodes." % (net.path(), cat))


def find(name, net):
    n = net.node(name) or hou.node(name)
    if n is None:
        raise hou.Error("Node not found: %r (looked in %s and as a full path)" % (name, net.path()))
    return n


def set_start_frame(node):
    """Point a sim's start frame at the playbar start (or START_FRAME)."""
    p = node.parm("startframe")
    if p is None:
        return
    if START_FRAME is None and LINK_TO_PLAYBAR:
        p.setExpression("$RFSTART")
    else:
        p.set(START_FRAME if START_FRAME is not None else hou.playbar.frameRange()[0])


net = sop_network(current_network())
ys = [c.position()[1] for c in net.children()]
top = (min(ys) - 2) if ys else 0          # build below whatever is already there
created = []


def mk(parent, type_name, name, x, y):
    n = parent.createNode(type_name, name)
    n.setPosition(hou.Vector2(x, top + y))
    created.append(n)
    return n


def mk_dop(parent, type_name, name, x, y):
    n = parent.createNode(type_name, name)
    n.setPosition(hou.Vector2(x, y))
    return n


if BUILD_DEMO:
    box = mk(net, "box", "demo_box", 0, 0)
    box.parm("type").set(1)                            # polygon mesh
    for p in ("divrate1", "divrate2", "divrate3"):
        box.parm(p).set(2)
    if ROOT_SOURCE == "fracture":
        # --- root pieces: the box fractured, cleaned, packed as piece0..pieceN-1 --
        frac = mk(net, "rbdmaterialfracture::3.0", "demo_fracture", 0, -1.2)
        frac.setInput(0, box)                          # default Concrete fracture
        cln = mk(net, "clean", "demo_clean", 0, -2.4)
        cln.setInput(0, frac)                          # 1st output = the fractured pieces
        cln.parm("dodelattribs").set(1)                # drop fracture attribs + groups; assemble renames
        cln.parm("dodelgroups").set(1)
        nrm = mk(net, "normal", "demo_normal", 0, -3.6)
        nrm.setInput(0, cln)
        nrm.parm("cuspangle").set(0)                   # hard edges on the cut faces
        root_in = nrm
    elif ROOT_SOURCE == "colours":
        # --- root pieces: one box, three colours -----------------------------------
        cols = []
        for i, rgb in enumerate(((0, 0, 1), (1, 0, 0), (0, 1, 0))):
            c = mk(net, "color", "demo_color%d" % (i + 1), -3 + 3 * i, -1.2)
            c.setInput(0, box)
            c.parmTuple("color").set(rgb)
            cols.append(c)
        mrg = mk(net, "merge", "demo_merge", 0, -2.4)
        for i, c in enumerate(cols):
            mrg.setInput(i, c)
        root_in = mrg
    else:
        raise hou.Error('ROOT_SOURCE must be "fracture" or "colours" - got %r' % ROOT_SOURCE)
    root = mk(net, "assemble", "ROOT_assemble", 0, -4.8)
    root.setInput(0, root_in)
    root.parm("pack_geo").set(1)                       # packed pieces named piece0, piece1, ...

    # --- emitter: new points every frame, random pscale + N, random piece name ---
    grid = mk(net, "grid", "demo_grid", 7, 0)
    sc = mk(net, "scatter::2.0", "demo_scatter", 7, -1.2)
    sc.setInput(0, grid)
    sc.parm("npts").set(EMIT_PER_FRAME)
    sc.parm("seed").setExpression("$FF")               # new positions every frame
    lift = mk(net, "xform", "demo_lift", 7, -2.4)
    lift.setInput(0, sc)
    lift.parm("ty").set(4.8)
    rs = mk(net, "attribrandomize", "demo_rand_pscale", 7, -3.6)
    rs.setInput(0, lift)
    rs.parm("name").set("pscale")
    rs.parm("minx").set(0.2)
    rs.parm("seed").setExpression("$F")
    rn = mk(net, "attribrandomize", "demo_rand_N", 7, -4.8)
    rn.setInput(0, rs)
    rn.parm("name").set("N")
    rn.parm("seed").setExpression("$F")
    nm = mk(net, "attribwrangle", "demo_piece_name", 7, -6)
    nm.setInput(0, rn)
    nm.setInput(1, root)                               # 2nd input: the root pieces, to count them
    nm.parm("snippet").set(r'''
// pick one of the root pieces at random (piece0 .. pieceN-1)
int num  = npoints(1);
int pick = min(int(floor(rand(@ptnum + @Frame * 17.31) * num)), num - 1);
s@name = 'piece' + itoa(pick);
''')

    cp_emit = mk(net, "copytopoints::2.0", "demo_emit_copy", 3.5, -7.2)
    cp_emit.setInput(0, root)
    cp_emit.setInput(1, nm)
    cp_emit.parm("useidattrib").set(1)                 # piece0 -> root piece0, ...
    cp_emit.parm("targetattribs").set(1)               # copy name (etc.) from the emit points
    cp_emit.parm("applyattribs1").set("*,^v,^Alpha,^N,^up,^pscale,^scale,^orient,^rot,^pivot,^trans,^transform")
    # the copies are already packed pieces; packing them again would nest them
    fr = mk(net, "attribwrangle", "demo_emit_frame_name", 3.5, -9.6)
    fr.setInput(0, cp_emit)
    fr.parm("snippet").set("s@name += '_' + itoa(@Frame);")   # unique name per emitted piece

    # --- Bullet RBD sim that adds the new pieces every frame -------------------
    dop = mk(net, "dopnet", "demo_rbd_dopnet", 3.5, -10.8)
    dop.setInput(0, fr)
    set_start_frame(dop)
    obj = mk_dop(dop, "rbdpackedobject", "rbdpackedobject1", 0, 0)
    obj.parm("geosource").set(1)                       # first context geometry
    obj.parm("createframe").setExpression("$F")        # re-create -> adds this frame's pieces
    sol = mk_dop(dop, "bulletrbdsolver", "bulletrbdsolver1", 0, -1)
    sol.setInput(0, obj)
    grav = mk_dop(dop, "gravity", "gravity1", 0, -2)
    grav.setInput(0, sol)
    ground = mk_dop(dop, "groundplane", "groundplane1", -3, -2)
    dm = mk_dop(dop, "merge", "merge1", -1.5, -3)
    dm.setInput(0, ground)
    dm.setInput(1, grav)
    dout = mk_dop(dop, "output", "output", -1.5, -4)
    dout.setInput(0, dm)
    dout.setDisplayFlag(True)
    x0, y0 = 0, -12.5
else:
    dop = find(DOPNET, net)
    root = find(ROOT_PIECES, net)
    x0, y0 = root.position()[0] - 0, root.position()[1] - top - 2

# --- LOP / Solaris: the same copy as a USD PointInstancer ---------------------
def build_lop(net, targets, root, x, y, tag=""):
    """targets: SOP points with name + transform (or orient/pscale).
    root: SOP root pieces, each with a name. Returns the SOP node that unpacks
    the instancer back to geometry (for checking against the Copy to Points)."""
    t_out = net.createNode("null", "LOP_targets" + tag)
    t_out.setInput(0, targets)
    t_out.setPosition(hou.Vector2(x, y))
    p_out = net.createNode("null", "LOP_prototypes" + tag)
    p_out.setInput(0, root)
    p_out.setPosition(hou.Vector2(x + 3, y))

    lop = net.createNode("lopnet", "LOP_instancing" + tag)
    lop.setPosition(hou.Vector2(x + 1.5, y - 1.2))
    si = lop.createNode("sopimport", "root_pieces")          # prims: /root_pieces/piece0, ...
    si.parm("soppath").set(si.relativePathTo(p_out))
    si.setPosition(hou.Vector2(3, 0))
    inst = lop.createNode("instancer", "instancer1")         # prim: /instancer1
    inst.setInput(1, si)                                     # prototypes come in the 2nd input
    inst.setPosition(hou.Vector2(0, -1.5))
    inst.parm("method").set("pointinstancer")
    inst.parm("transformsourcemode").set("extsop")           # target points from a SOP
    inst.parm("pointsoppath").set(inst.relativePathTo(t_out))
    inst.parm("protosourcemode").set("second")
    inst.parm("protopattern").set("/root_pieces/*")          # EVERY piece is its own prototype
    inst.parm("protoindexsrc").set("nameattr")               # point name picks the prototype
    inst.parm("nameattr").set("name")
    out = lop.createNode("null", "OUT_instances")
    out.setInput(0, inst)
    out.setPosition(hou.Vector2(0, -3))
    out.setDisplayFlag(True)

    # back to SOPs, only to check the result (import the instancer prim ONLY -
    # a Boundable pattern would also pull in the hidden prototype meshes)
    li = net.createNode("lopimport::2.0", "LOP_check_import" + tag)
    li.parm("loppath").set(li.relativePathTo(out))
    li.parm("primpattern").set("/instancer1")
    li.setPosition(hou.Vector2(x + 1.5, y - 2.4))
    uu = net.createNode("unpackusd::2.0", "LOP_check_unpackusd" + tag)
    uu.setInput(0, li)
    uu.parm("output").set("polygons")
    uu.parm("iterations").set(2)                             # instancer -> instances -> meshes
    uu.setPosition(hou.Vector2(x + 1.5, y - 3.6))
    return [t_out, p_out, lop, li, uu], uu


# --- the root copy -----------------------------------------------------------
if METHOD not in ("packed", "points", "both"):
    raise hou.Error('METHOD must be "packed", "points" or "both" - got %r' % METHOD)
STRIP = ('s@name = re_replace("_[0-9]+$", "", s@name);   // piece0_12 -> piece0\n' if STRIP_SUFFIX else "")

src = mk(net, "unpack", "ROOT_pieces", x0, y0)
src.setInput(0, root)
src.parm("transfer_attributes").set("name")
outs = []

if METHOD in ("packed", "both"):
    # A) packed: read each simulated piece's full transform off its packed prim
    imp = mk(net, "dopimport::2.0", "ROOT_sim_pieces", x0 + 4, y0)
    imp.parm("doppath").set(imp.relativePathTo(dop))
    imp.parm("objpattern").set(OBJ_PATTERN)          # default style = fetch packed geometry

    tgt = mk(net, "attribwrangle", "ROOT_targets", x0 + 4, y0 - 1.2)
    tgt.setInput(0, imp)
    tgt.parm("snippet").set(r'''
// One target point per simulated piece, carrying that piece's WHOLE transform:
// emission rotation + pscale + the sim's motion.
int prim = pointprims(0, @ptnum)[0];
matrix M = primintrinsic(0, "packedfulltransform", prim);
3@transform = matrix3(M);
v@P = set(getcomp(M, 3, 0), getcomp(M, 3, 1), getcomp(M, 3, 2));
''' + STRIP)

    clean = mk(net, "attribdelete", "ROOT_targets_clean", x0 + 4, y0 - 2.4)
    clean.setInput(0, tgt)
    clean.parm("negate").set(1)                      # keep only these point attributes
    clean.parm("ptdel").set("name transform v")

    pts = mk(net, "add", "ROOT_points_only", x0 + 4, y0 - 3.6)
    pts.setInput(0, clean)
    pts.parm("remove").set(1)                        # drop the packed prims, keep the points

    cp = mk(net, "copytopoints::2.0", "ROOT_copy", x0 + 2, y0 - 4.8)
    cp.setInput(0, src)
    cp.setInput(1, pts)
    cp.parm("useidattrib").set(1)                    # Piece Attribute = name
    out = mk(net, "null", "OUT_root_copy", x0 + 2, y0 - 6)
    out.setInput(0, cp)
    outs.append(out)

if METHOD in ("points", "both"):
    # B) points: one point per piece straight from the sim, no geometry imported
    pimp = mk(net, "dopimport::2.0", "ROOT_sim_points", x0 - 4, y0)
    pimp.parm("doppath").set(pimp.relativePathTo(dop))
    pimp.parm("objpattern").set(OBJ_PATTERN)
    pimp.parm("importstyle").set(1)                  # Create Points to Represent Objects
    pimp.parm("transferattributes").set("orient pivot restxform name v")

    ptgt = mk(net, "attribwrangle", "ROOT_point_targets", x0 - 4, y0 - 1.2)
    ptgt.setInput(0, pimp)
    ptgt.parm("snippet").set(r'''
// Rebuild each piece's full transform from the sim point alone:
//   restxform = emission rotation + pscale (3x3) and the rest position (row 3)
//   world     = (rest - pivot) * orient + P
matrix  X  = 4@restxform;
matrix3 A  = matrix3(X);
vector  rp = set(getcomp(X, 3, 0), getcomp(X, 3, 1), getcomp(X, 3, 2));
matrix3 R  = qconvert(p@orient);
3@transform = A * R;
v@P = (rp - v@pivot) * R + v@P;
''' + STRIP)

    pclean = mk(net, "attribdelete", "ROOT_point_targets_clean", x0 - 4, y0 - 2.4)
    pclean.setInput(0, ptgt)
    pclean.parm("negate").set(1)                     # orient/pivot must go, transform wins
    pclean.parm("ptdel").set("name transform v")

    pcp = mk(net, "copytopoints::2.0", "ROOT_copy_points", x0 - 2, y0 - 4.8)
    pcp.setInput(0, src)
    pcp.setInput(1, pclean)
    pcp.parm("useidattrib").set(1)
    pout = mk(net, "null", "OUT_root_copy_points", x0 - 2, y0 - 6)
    pout.setInput(0, pcp)
    outs.append(pout)

outs[-1].setDisplayFlag(True)
outs[-1].setRenderFlag(True)
print("RBD root copy (%s) built in %s (%d nodes) -> %s" % (METHOD, net.path(), len(created), ", ".join(o.name() for o in outs)))

if ADD_LOP:
    lop_targets = pclean if METHOD in ("points", "both") else pts
    nodes, lop_check = build_lop(net, lop_targets, src, x0 - 10, y0)
    created += nodes
    print("LOP instancing built -> %s (unpacked check: %s)" % (nodes[2].path(), lop_check.name()))
