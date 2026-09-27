# ============================================================================
# Copy pieces as a USD PointInstancer in LOPs   (paste into Houdini Python Shell)
#
# Takes the target points of a Copy to Points (each point: name + transform, or
# orient/pscale) and the root pieces (each with a name) and builds the Solaris
# version: a LOP network with ONE prototype per piece, picked by the point's
# name, plus a LOP Import -> Unpack USD back in SOPs to check the result.
#
# The two things that make it wrong if left at their defaults:
#   - Prototype Primitives = the whole SOP import  -> every instance gets ALL
#     pieces. It must be /<sopimport>/* so each piece is its own prototype,
#     and Prototype Index = Name Attribute so a point named piece3 gets piece3.
#   - LOP Import pattern %type:Boundable also matches the hidden prototype
#     meshes. Import the instancer prim only.
#
# HOW TO USE
#   1. Open the Geometry network that holds the two SOP nodes (or set TARGET).
#   2. Set TARGETS_NODE and ROOT_NODE below, paste into Windows > Python Shell.
#   New nodes are created (LOP_*); existing nodes are not changed.
# ============================================================================

import hou

# ----------------------------- CONFIG ---------------------------------------
TARGET       = ""                           # "" = the network the Network Editor is showing
TARGETS_NODE = "ROOT_point_targets_clean"   # points: name + transform (e.g. from the RBD root copy)
ROOT_NODE    = "ROOT_pieces"                # root pieces, each with a name
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


net = current_network()
if net.childTypeCategory().name() != "Sop":
    raise hou.Error("Open the Geometry (SOP) network that holds %s - %s is not one." % (TARGETS_NODE, net.path()))
targets = find(TARGETS_NODE, net)
root = find(ROOT_NODE, net)
pos = targets.position()
nodes, check = build_lop(net, targets, root, pos[0] - 8, pos[1] - 2)
print("LOP instancing built in %s -> %s (unpacked check: %s)" % (net.path(), nodes[2].path(), check.name()))
