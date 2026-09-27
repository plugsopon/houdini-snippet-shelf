# ============================================================================
# <Technique name>   v001   (paste into Houdini Python Shell)
#
# <What it builds and why, in 2-4 lines. Name the problem it solves.>
#
# HOW TO USE
#   1. Open a network in the Network Editor:
#        - a Geometry (SOP) network -> everything is built right there
#        - /obj                     -> a new GEO_NAME geo is created for it
#   2. Paste the whole thing into Windows > Python Shell and press Enter.
#
#   BUILD_DEMO = True  -> builds a small self-contained demo scene + the setup.
#   BUILD_DEMO = False -> adds the setup to YOUR nodes: set the names below
#                         (a name in the open network, or a full path).
#   Existing nodes are never changed or moved (only the display flag moves to
#   the new OUT node, and SET_DISPLAY = False turns even that off).
# ============================================================================

import hou

# ----------------------------- CONFIG ---------------------------------------
BUILD_DEMO   = True
TARGET       = ""            # "" = the network the Network Editor is showing; or a path
GEO_NAME     = "my_setup"    # geo created when the open network is /obj
SET_DISPLAY  = True          # move the display/render flag to the new OUT node

SOURCE_NODE  = "null1"       # BUILD_DEMO = False: the node the setup reads from
# ----------------------------------------------------------------------------


def current_network():
    """TARGET if set, else the network shown in the Network Editor."""
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
    """Build in net if it is a SOP network; at /obj level make a new geo for it."""
    cat = net.childTypeCategory().name()
    if cat == "Sop":
        return net
    if cat == "Object":
        return net.createNode("geo", GEO_NAME)
    raise hou.Error("Open a Geometry (SOP) network or /obj - %s holds %s nodes." % (net.path(), cat))


def find(name, net):
    """A name in the open network first, then a full path. Fails loudly, never guesses."""
    n = net.node(name) or hou.node(name)
    if n is None:
        raise hou.Error("Node not found: %r (looked in %s and as a full path)" % (name, net.path()))
    return n


net = sop_network(current_network())
ys = [c.position()[1] for c in net.children()]
top = (min(ys) - 2) if ys else 0          # build BELOW whatever is already there
created = []


def mk(type_name, name, x, y, parent=None):
    """Create a node at (x, top + y). Houdini appends 1, 2... if the name is taken."""
    n = (parent or net).createNode(type_name, name)
    n.setPosition(hou.Vector2(x, top + y))
    created.append(n)
    return n


if BUILD_DEMO:
    src = mk("box", "demo_box", 0, 0)
    # ... the rest of the demo scene, named demo_*
else:
    src = find(SOURCE_NODE, net)

# --- the setup itself --------------------------------------------------------
w = mk("attribwrangle", "SETUP_wrangle", 0, -1.2)
w.setInput(0, src)
w.parm("snippet").set(r'''
// VEX goes in a raw string so backslashes survive
v@P = v@P;
''')

out = mk("null", "OUT_setup", 0, -2.4)
out.setInput(0, w)
if SET_DISPLAY:                           # the only change a builder makes to existing state
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
print("<technique> built in %s (%d nodes) -> %s%s" % (
    net.path(), len(created), out.name(), " (display flag moved here)" if SET_DISPLAY else ""))
