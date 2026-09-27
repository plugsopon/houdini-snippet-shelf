# Houdini Snippet Shelf — notes for Claude

Plug's personal Houdini techniques (not Dremzo). Plug is an FX TD; reply in Thai, refer to
yourself as "Brother" in Thai sentences. He pastes scripts at Framestore on Houdini 20.5; home
tests run on 21.0.671 Apprentice (hython path in the houdini-hython-verify skill).

Skills in `.claude/skills/` — use them:
- `houdini-builder-script` — writing any paste-able Python that creates nodes
- `houdini-hython-verify` — checking scripts / .hipnc files headlessly before handing them over
- `houdini-shelf-publish` — adding a technique or version to the shelf (artifact + folder + git)

Live Houdini (`houdini-live` MCP, see mcp/README.md): only reaches a session where Plug ran
`brother_link.start()` himself. If several are open, ask which one (or match the hip name he
mentions) and `houdini_use_session` it. Debug by LOOKING first (scene → problems → node →
geometry/compare) and report findings. Change his scene only when he asks, with a
`Brother: <what>` label, one change per call, and say what to Ctrl+Z (or `houdini_undo`).
Never save his hip through the MCP.

Layout: see README.md. Never overwrite Plug's .hipnc files. Outside the MCP, never touch his
running Houdini (hython is a separate process).
