# houdini-live MCP

Lets Claude (Brother) look at Plug's **open** Houdini sessions to help debug, and change them when
Plug asks. Several Houdinis can be open at once; Brother lists them and Plug says which one.

```
Houdini (each session you want Brother to see)          Claude Code
  brother_link.start()  ── 127.0.0.1:18820+ ──►  mcp/server.py (houdini-live)
  registers ~/.houdini_brother/sessions/<pid>.json ◄── reads the list
```

## Turn it on in Houdini

Per session, in the Python Shell (or make the shelf button in `houdini/shelf_tool_toggle.py`):

```python
import sys; sys.path.insert(0, r"P:\Project\Houdini Snippet Shelf\mcp\houdini")
import brother_link; brother_link.start()
```

`brother_link.stop()` (or the shelf button again) closes it. Closing Houdini closes it too.
Nothing is running unless you start it.

## Claude Code side

`.mcp.json` at the repo root registers the server, so open Claude Code **in
`P:\Project\Houdini Snippet Shelf`** and approve `houdini-live` the first time. Needs
`pip install mcp` (already installed for Python 3.13).

## Tools

| Tool | Does |
|---|---|
| `houdini_sessions` / `houdini_use_session` | list open sessions; pick one by pid or part of the hip name (auto when only one) |
| `houdini_scene` | hip, unsaved, frame, range, selected nodes, what the Network Editor shows |
| `houdini_network`, `houdini_node`, `houdini_problems` | nodes, parms (value + expression), VEX, errors/warnings |
| `houdini_geometry`, `houdini_attrib` | counts, bbox, attributes, groups, values - at any frame |
| `houdini_compare` | nearest-neighbour point distance between two SOPs per frame |
| `houdini_viewport` | a picture of the Scene Viewer (flipbook one frame) |
| `houdini_set_parm`, `houdini_run_python` | change things - each call is ONE undo step labelled `Brother: ...` |
| `houdini_undo` | undo Brother's last step; refuses if the top of the stack is Plug's |

## Safety

- Listens on **127.0.0.1 only**; each request needs the session's random token (in the registry
  file, readable by this Windows user only).
- Every request runs on Houdini's **main thread** (`hdefereval`), like typing in the Python Shell.
- Reading uses `geometryAtFrame` / `evalAtFrame`: **looking never moves the playbar** (tested).
- Changes are one undo group each; `houdini_undo` only ever undoes a `Brother:` step (tested).
- `houdini_run_python` leaves a `Brother: <label>` entry on the undo stack even when it only
  reads - prefer the read tools for looking.

## Tested

- 2026-09-27, hython 21.0.671, two sessions at once: every tool through a real MCP client.
- 2026-09-27, Plug's GUI Houdini 21.0.671 Apprentice (test.hipnc): session list, scene, network,
  node, problems and the viewport capture - the main-thread (`hdefereval`) path works.
- `houdini_viewport` needs the Scene View tab to be the visible tab in its pane; a hidden one
  flipbooks nothing, and the tool now says so. The capture is at the camera's resolution with the
  Apprentice logo, flattened onto a dark background (the flipbook's background is transparent).
