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

## Review fixes (2026-09-28)

A three-part review (chat bugs, Houdini-side bugs, gaps against Claude Code) led to these fixes, each tested live on Haiku:

- **Model and mode belong to each conversation.** A new session always starts in "Ask first";
  it used to inherit whatever the previous one was set to, Bypass included. The menus show the
  real state: the CLI's `status.permissionMode` wins, and a refused switch is shown and reverted.
  Launched with `--allow-dangerously-skip-permissions` so Bypass can be chosen later — that flag
  only makes it selectable.
- **AskUserQuestion** gets a real question card (radio/checkbox + Other); the answers go back in
  `updatedInput.answers`. **ExitPlanMode** shows the plan as markdown with Approve + accept edits
  (`setMode acceptEdits`), Approve, and Keep planning (with feedback).
- Question cards **expire** on Stop, on the end of the turn, on `control_cancel_request`, or if
  claude exits. Unknown control requests (elicitation, ...) are answered with an error instead of
  hanging the turn.
- Switching sessions **never blocks** (no `waitForFinished` on the UI thread). A conversation with
  a turn, a question or background tasks (`task_started` / `task_notification` /
  `background_tasks_changed`) is not parked.
- `errorOccurred(FailedToStart)` ends the turn instead of leaving it busy forever. A session with
  no turns yet relaunches with `--session-id`, not `--resume` (that errored "No conversation found").
- Header: context-window % from `get_context_usage`, instead of a summed token count that meant
  nothing. A banner shows `rate_limit_event` warnings or rejections. Compaction, API retries and
  notifications appear as notes. `result.errors[]` is shown, not "error: None". The init line
  appears once, not every turn.
- History hides transcript stubs with no user turn.
- Cursor: the Mosh bands are cached per showing, not rebuilt every frame. The control counter is
  kept even while edges are off, so they can't get stuck on. A broken `cursor.json` can't stop
  brother_link. The overlay timer stops while hidden. The shelf's Preview Edges always pairs its
  calls.

## Round 2 (2026-09-28)

- **Rewind files to here** on each of your messages. Needs the launch flag
  `CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING` (re-inserted after `claude_env()` strips every
  `CLAUDE_*`) and `--replay-user-messages`. The echoed message's `uuid` is the rewind point.
  Trap: a /model or other local command is echoed too (`<local-command-stdout>...`), so the echo
  is matched to its bubble by TEXT, not by order. A dry run lists the files first. Only
  Write/Edit changes are tracked (not Bash).
- The model menu is filled from the CLI's `initialize` answer (Fable and Opus 1M included). The
  effort menu enables only the levels the current model supports (`--effort` at launch,
  `apply_flag_settings {effortLevel}` mid-session).
- History right-click: **Rename** (`rename_session`, which writes a `custom-title` line) and
  **Fork** (`--resume <id> --fork-session`; the fork names itself "Fork of ...").
- Images in tool results (screenshots, Read of a PNG) show as thumbnails; click to enlarge.
- Each agent streams into its own blocks (keyed by `parent_tool_use_id`), so parallel subagents
  can't write into each other's text. Subagent text is indented. Not yet tested live with real
  parallel subagents.
- The panel's corners were square on the left: the sidebar painted a square background over the
  panel's rounded border. The layout is now inset 1px and the sidebar has its own left radii.

## Round 3 — the Claude-app composer (2026-09-29)

- A composer box with image thumbnails inside, a round send button, and a project + git branch
  strip above it. Under it: **+** (files/photos Ctrl+U, folder, Houdini viewport, selected
  nodes, slash commands, Connectors ›, Plugins ›), the **mode** menu (Auto/Manual/Accept
  edits/Plan/Bypass, keys 1-5), the **model** menu (families + More models), an **Effort**
  slider (Faster↔Smarter, only the levels the model supports) and a **context ring**.
  `PopupMenu`, `DotSlider`, `EffortPopup`, `ContextRing` and `Thumb` live in brother_chat.py.
- The chat runs the **Claude desktop app's own CLI** (newest
  `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude-code\<ver>\claude.exe`;
  the app is MSIX, so a process outside the package, like Houdini, can't see the plain `%APPDATA%`
  path). The npm CLI (2.1.226) was too old for Opus 5.5 ("requires 2.1.280"). The npm CLI is the
  fallback.
- **Crash guard.** A Python exception inside a PySide `paintEvent` while a QPainter is open
  segfaults ALL of Houdini (signal 11 in `QPainter::end`). It happened once:
  `QPen(color, w, cap=...)` is not accepted by this PySide. Every custom paint (chat, cursor
  overlay, settings) now runs inside try/finally and only prints errors. Keep it that way.

## Voice input (2026-09-29)

The 🎙 button (or Ctrl+M) under the composer records from the Windows default microphone
(QtMultimedia `QAudioSource`, 16 kHz mono) and transcribes locally with **faster-whisper
large-v3-turbo on the GPU**, ~1 s per clip, Thai + English. Nothing is uploaded. The text is
inserted at the cursor; you still press Send.

- `brother_whisper.py` is a long-lived worker in the SYSTEM Python (not Houdini's). The model
  loads once, on first use.
- Install it with `pip install --target %USERPROFILE%\.houdini_brother\whisper faster-whisper
  nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"` (~2.3 GB) plus the model (~1.6 GB, Hugging Face
  cache).
- **Trap:** never install it with `--user` from a shell inside the Claude desktop app. It's an
  MSIX package, so its %APPDATA% is virtualised and a --user install lands where Houdini can't see
  it (`ModuleNotFoundError` in the worker).
- **Trap:** the worker's stdout is cp1252 under QProcess, so results are ASCII-escaped JSON.
  Otherwise every Thai transcript dies with a 'charmap' error while English works fine.
- A short list of Houdini terms (`VOICE_PROMPT`) is passed as the initial prompt, so words like
  VEX, FLIP and voxel come out spelled right.
