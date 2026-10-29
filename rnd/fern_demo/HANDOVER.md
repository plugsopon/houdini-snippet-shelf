# Handover: fern field demo (2026-10-29)

From the Claude Code session that built it, to whoever continues (Codex). Read `README.md` in
this folder first for what the demo is and how to run it; this file is the state and the traps.

## What it is for

Plug records short videos of an AI building a Houdini network live. This demo is one of them: a
fern field where Crag walks through and ferns grow open near him and curl back up behind him.
Plug wants it to run without stalls and readable on camera. He gives the order by voice, e.g.
"เดโมเฟิร์น" / "run the fern demo".

## State (all measured on Plug's Houdini 21.0.671, pid 61532 at the time)

- Committed in this repo at `5756d85` (`rnd/fern_demo/`, MCP tools in `mcp/server.py`).
- Full rebuild: 30 nodes, no errors, no layout violations. Speed 8 / 600 chars/s ≈ 60 s;
  default 2.5 / 60 ≈ 3 min.
- Playback cook: **0.0105 s a frame** (was 0.137 s before the wind moved out of the loop).
- Fern size 0.21 (Plug halved it), 16 growth stages, seedling scale 0.15 → 1.
- Codex config (`~/.codex/config.toml`) has `houdini-live` registered. Codex must be restarted
  once to see `houdini_fern_demo` / `houdini_fern_demo_status`.

## How to run

- MCP: `houdini_fern_demo(speed=2.5, chars_per_second=60)`, then poll `houdini_fern_demo_status`.
- Shell: `python rnd/fern_demo/fern_demo.py [speed] [cps]`.
- Needs a Houdini where Plug ran `brother_link.start()`. Several open → set `HOUDINI_BROTHER_PID`.
- Esc in Houdini stops the build; the purple frame goes off on any exit.

## Plug's rules (do not break)

- **Layout:** top → bottom, left → right. A node is never above its input; no wire slants
  upward (horizontal at most). `build_visible.py` checks this in its final readback
  (`layout_violations` must be `[]`).
- **Build order is a story:** fern first (open, full size), then `stage_grow`, then walker and
  field, then the For-Each loop **last**, wrapped around the finished fern, then `stage_wind`,
  then instancing. Nodes that point at something not built yet get their link through `DEFER`
  in `field_plan.py` (no red error badges on camera).
- **Typed VEX has no comments** (`field_plan.bare()` strips them); the source keeps them.
- **Never save the hip.** Only `/obj/brother_fern_field` is deleted and rebuilt; other objects
  are only hidden. Never touch another person's Houdini.
- **No real OS mouse/keyboard input.** The cursor is Brother's overlay (`brother_cursor`);
  Houdini 21 ignores synthetic Qt drags, so moves/wires are animated with `setPosition`/`setInput`.

## Traps already hit

- **Anything time-dependent inside the For-Each loop re-cooks every stage every frame.** Wind
  inside it cost 0.137 s/frame; after the loop 0.01 s. Keep it after `stages_end`.
- The loop output is **unpacked**; `fern_instances` (Copy to Points 2.0) picks the stage with
  piece attribute `variant` and packs (`pack=1`). Re-packing inside the loop breaks this.
- A Merge's input port moves once its inputs connect: line nodes up **after** wiring. The Merge
  port key is `('multiinput', -1)`.
- Sweep reads its up vector as a **primitive** attribute and scales the ribbon by point `pscale`.
- `hou.copyNodesTo` returns copies in a different order — map by name.
- Git Bash mangles `/obj/...` arguments: set `MSYS_NO_PATHCONV=1`.
- Shell heredocs can eat backslashes in VEX/regex — write files with an editor tool.
- Never `importlib.reload(brother_cursor)` in a live Houdini (duplicate overlay); swap
  functions and repoint the OPS dicts instead. Never `hou.hda.reloadFile` there either (crash).
- Read-only bridge calls must have "read-only" in their label, or the control frame lights up.

## Open / ideas Plug has not decided

- Ferns at the same growth stage sway identically (the wind is on the 16 baked stages). A cheap
  fix: a small per-instance noise tilt on `orient` in `field_grow`.
- Growth has no lag: a fern closes the instant Crag moves away. A Solver would add a delay.
- `scene_merge` warns about mismatched attributes (Crag's own). Harmless.
- The shelf artifact page (see repo CLAUDE.md) does not mention this demo yet.
- Not yet triggered from Codex itself; only the MCP tool function was run directly.

## Files

`fern_plan.py` (one fern), `field_plan.py` (field, order, DEFER, spares), `build_visible.py`
(generic builder), `fern_demo.py` (one command), `bridge.py` (session + socket).
