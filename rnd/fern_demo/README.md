# Fern field demo (for recording)

Brother builds, live in Plug's open Houdini, a fern that grows from a straight curve: a KineFX
Rig Attribute Wrangle coils it into a snail-shell spiral and pays it out, leaves are copied to
points and uncurl, and a closed fern is a small seedling that scales up as it opens. A For-Each
loop bakes 16 growth stages around the finished fern (time-independent, so it cooks once), then a
noise field sways every stage each frame (no sim); Crag walks through a scattered field and each fern opens as he comes near and curls back
up behind him.

Every node is created with the virtual cursor at its planned spot (top to bottom, left to right,
no wire slanting up), wired with the eased wire pull, VEX typed into the Parameter pane without
comments, the viewport following the node just built. The purple frame is held the whole time;
**Esc** in Houdini stops it. Only `/obj/brother_fern_field` is deleted and rebuilt; other objects
are hidden, never changed. The hip is never saved.

## Run it

Needs a Houdini where `brother_link.start()` is running (see `mcp/README.md`).

- From Codex / Claude: call the `houdini_fern_demo` tool (houdini-live MCP), then
  `houdini_fern_demo_status`. Say for example "เดโมเฟิร์น" / "run the fern demo".
- From a shell: `python rnd/fern_demo/fern_demo.py [speed=2.5] [chars_per_second=60]`
  (set `HOUDINI_BROTHER_PID` when several Houdinis are open).

Speed 2.5 / 60 chars/s takes about 3 minutes; 8 / 600 about 60 s.

## Files

| file | what |
|---|---|
| `fern_plan.py` | the single fern network: stem coil, width, wind, leaves |
| `field_plan.py` | the field: fern + seedling scale, walker, field points, loop built last, instancing, build order |
| `build_visible.py` | generic visible builder for any plan module (`NODES`, `SPARE`, `LINKS`, `EXPRS`, `DEFER`, `RAMPS`) |
| `fern_demo.py` | one command: clear, frame the viewer, build, play |
| `bridge.py` | finds the Houdini session and talks to brother_link |

Tunables live as spare parms on the nodes: `stage_wind` (strength, size, speed, gust),
`stage_grow` (seedling size), `field_grow` (open / coiled radius, fern size).
Playback cooks about 0.01 s a frame. Keep the wind AFTER the loop: inside it, every frame re-cooks
all 16 stages (measured 0.137 s a frame with the wind on the curves inside the loop).
