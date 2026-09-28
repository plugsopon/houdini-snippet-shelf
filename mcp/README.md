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
| `houdini_screenshot` | the whole Houdini window; its pixels are the click coordinates |
| `houdini_pointer`, `houdini_click`, `houdini_type`, `houdini_key`, `houdini_cursor_hide` | Brother's own pink cursor: glides, clicks, types into fields (GUI only) |
| `houdini_create_node` | cursor glides to a spot in a Network Editor, clicks, and the node appears right under it (optional name + input) - one `Brother:` undo step |
| `houdini_click_node` | cursor finds a node BY PATH (no screenshot) - switches/pans a Network Editor if needed - and clicks it; `double` dives in. Returns the Parameter pane that now shows it |
| `houdini_pane_screenshot` | ONE pane cropped (parm / network / viewer, or the pane showing a node) - a fraction of the whole-window image; `offset` + pixel = click point |
| `houdini_set_parm_shown` | exact API set (one undo step) while the cursor clicks the node and points at the field (x,y from a pane crop) or at its pane |

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
- Virtual cursor (2026-09-28, Plug's GUI Houdini): glide, click into a wrangle's VEXpression,
  Ctrl+A, type two lines, click away -> the `snippet` parm held exactly the typed text.
  Learnt on the way, both now in the code: `QWidget.grab()` of the main window is black
  (Houdini draws with OpenGL), so screenshots grab the screen; and a translucent CHILD widget
  over Houdini blacked out the whole window with cursor trails, so the cursor is its own
  top-level transparent window laid over Houdini. Keys go to the last clicked widget because Qt
  reports no focus widget while Houdini isn't the active app.
- Typing is recorded by Houdini's own undo (not a `Brother:` step), so `houdini_undo` won't
  reverse it; Plug's Ctrl+Z does.
- `houdini_create_node` (2026-09-28, Plug's GUI Houdini): a null created under the cursor tip,
  wired to volumewrangle1. Not via the TAB menu on purpose: Houdini opens that menu at Plug's
  REAL mouse position, and it is a native RE_Window that Qt can't route keys into. The whole
  main window is one OpenGL surface (panes are not Qt widgets), so the pane is located with
  `NetworkEditor.qtScreenGeometry()`; its drawing area is the bottom `screenBounds()` part,
  counted from the bottom-left.

### Where the cursor gets its coordinates

- **Nodes: from the API.** `qtScreenGeometry()` gives each pane's rect; a Network Editor's `visibleBounds()` maps a node
  position to a pixel. Compute it from `visibleBounds` yourself - `posToScreen()` keeps answering for the OLD view until
  Houdini repaints, so right after a pan it pointed 170px off and the click landed on the timeline (moved the frame).
- **Parameter pane fields: from a picture.** Houdini draws them itself on its one OpenGL surface; neither Qt nor `hou` can
  say where a field is. A Parm pane that shares a Network Editor's link group shows what is selected there, so after
  `click_node` Brother knows WHICH pane to crop (`pane_screenshot node=...`). A scrolled-away field still needs scrolling.

- **Screenshots read the SCREEN, not Houdini.** `QWidget.grab()` of Houdini's OpenGL panes is black, so every
  screenshot grabs the screen pixels where Houdini sits - if another window covers it (a browser, Claude),
  the picture is THAT window. Clicks by path (`click_node`) and API sets still work; picture-based navigation
  needs Houdini uncovered. Brother never raises Houdini itself: that would steal Plug's focus.
- **Desktop `AI_Control`** (2026-09-28): Scene View | Network Editor | Parameters full height, the editor and the
  Parameters pane in link Group1. Made with `desk add` + `Pane.splitHorizontally()`; saved only when Plug
  uses Desktop > Save Current Desktop (there is no API for that).

### AI menu + AI Settings (2026-09-28)

- `mcp/houdini/MainMenuCommon.xml` adds an **AI** menu after Help: *AI Settings...*, Connect /
  Disconnect Brother, Hide Brother's cursor. `install_menu.py` copies it into the Houdini pref
  folder (refuses to overwrite a different file). **Houdini reads menu files at start-up** -
  `hou.ui.updateMainMenuBar()` did not pick up a new top-level menu; restart once.
- *AI Settings...* (`brother_ui.py`) is a frameless dark panel over the main window: 7 cursor
  styles with live previews (glitch pixel x3, smooth x3, presenter dot), glitch Off/Calm/Wild,
  size, name tag on/off + its text, click ripples, and the link status with Connect/Disconnect.
  Changes apply to the live cursor at once and persist in `~/.houdini_brother/cursor.json`.
- The panel is its own top-level window, so Brother's cursor cannot click inside it
  (`_target` only searches Houdini's main window).

- **Edges fade while Brother drives** (2026-09-28): brother_link wraps every request that ACTS
  (anything but the look-only ops, and `run` whose label says read-only) in
  `brother_cursor.control()`. The overlay paints the four window edges fading from the chosen
  colour, in at once, out ~1s after the last request. Colour/strength/width in AI Settings.
  Hot-update note: never `reload(brother_link)` in a live session - it resets `_state`
  (server + token) and drops the connection; graft new functions onto the module instead.

### AI > Chat... - Claude Code inside Houdini (2026-09-28)

`mcp/houdini/brother_chat.py`. Drives the machine's own `claude` CLI exactly like Dremzo Desktop:
the real claude.exe behind the npm shim, `-p --input-format stream-json --output-format
stream-json --verbose --include-partial-messages --permission-prompt-tool stdio`, authenticated
by the machine's Claude login (`CLAUDE_CODE_OAUTH_TOKEN`, read from the user registry if Houdini
started before `setx`). One QProcess per session, alive across turns; cwd = this repo, the hip's
folder via `--add-dir`, houdini-live via `--mcp-config` with its look-only tools pre-allowed.

Protocol measured against claude 2.1.226 (the docs-summary agent's shapes were WRONG - e.g. it
claimed a `user_message` input type): input `{"type":"user","message":{...}}`; control requests
`initialize` (answers with the slash-command list), `interrupt`, `set_permission_mode`,
`set_model`; permission asks arrive as `control_request/can_use_tool` and are answered with a
`control_response` carrying `{"behavior":"allow","updatedInput":...}` or `deny`.

Traps:
- **Houdini sets PYTHONHOME to its Python 3.11.** Inherited by the MCP server (system Python
  3.13) it cannot find its stdlib and houdini-live shows `failed` in system/init while every
  other server connects. `claude_env()` drops PYTHONHOME/PYTHONPATH and Houdini's PATH dirs.
- Strip `CLAUDECODE` / `CLAUDE_*` (except the token) or the child thinks it is a nested SDK child
  and answers "Not logged in" (Desktop learned this 2026-06-20).

## FX AI shelf tab

`mcp/houdini/fx_ai.shelf` is the "FX AI" tab in the left shelf dock (`shelf_set_1`): Chat,
Settings, Connect, Disconnect, Hide Cursor, Preview Edges. Icons are the SVGs in
`mcp/houdini/icons/`, referenced by absolute repo path — on another machine, fix the paths or
copy the icons into `$HOUDINI_USER_PREF_DIR/config/Icons`. Install by copying the `.shelf` into
`$HOUDINI_USER_PREF_DIR/toolbar/`, then add the tab via the dock's "+" menu. The main-menu
label is now "FX AI" (needs a Houdini restart to show).

## Chat: several sessions at once

Each conversation (`Convo` in `brother_chat.py`) has its own `claude` process and its own feed.
Switching in History never stops a running one. A working session shows a spinner in the list,
and one waiting on a permission question shows `?` in amber. An idle session you leave has its
process closed; it resumes (`--resume`) on the next message. Earlier, switching deleted the
running session and crashed with `Internal C++ object (ClaudeSession) already deleted` — the
process-finished handler is now a bound method, disconnected in `stop()`.

The header shows only the session's token count - no dollar figure (Plug's call, 2026-09-28).
