# Shelf tool: "Brother Link" - click once to let Brother see THIS Houdini session, click again to close it.
# New Tool on any shelf -> Script tab -> paste this -> Language: Python.
import sys
p = r"P:\Project\Houdini Snippet Shelf\mcp\houdini"
if p not in sys.path:
    sys.path.insert(0, p)
import brother_link
if brother_link._state["server"] is None:
    port = brother_link.start()
    hou.ui.setStatusMessage("Brother Link ON - port %d (click again to close)" % port)
else:
    brother_link.stop()
    hou.ui.setStatusMessage("Brother Link OFF")
