# ---- patch: replace follow_born_only (Blast) with a wrangle ----------------
# Works on the network the Network Editor is showing (and everything inside it).
# Set TARGET to a path to patch somewhere else.
import hou

TARGET = ""   # "" = the network the Network Editor is showing

if TARGET:
    here = hou.node(TARGET)
else:
    ne = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor) if hou.isUIAvailable() else None
    here = ne.pwd() if ne else None
if here is None:
    raise hou.Error("Open the network with the rig in the Network Editor, or set TARGET.")

old = [n for n in [here] + list(here.allSubChildren())
       if n.name() == "follow_born_only" and n.type().name() == "blast"]
if not old:
    raise hou.Error("No Blast called follow_born_only in %s - nothing to patch." % here.path())
for b in old:
    net = b.parent()
    src = b.inputs()[0]
    w = net.createNode("attribwrangle", "follow_born_only_w")
    w.setPosition(b.position())
    w.setInput(0, src)
    w.parm("snippet").set('if (!i@born) removepoint(0, @ptnum);')
    for con in b.outputConnections():
        con.outputNode().setInput(con.inputIndex(), w)
    b.destroy()
    w.setName("follow_born_only")
    print("patched", w.path())
