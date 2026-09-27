---
name: houdini-builder-script
description: Use when writing a Python Shell script that creates Houdini nodes for Plug - a "rebuild everything" builder, a patch that inserts or rewires nodes, or any "paste this and it builds the setup" request (เหมือน FX Template).
---

# Paste-able Houdini builder scripts

## Overview

Plug pastes these into **Windows > Python Shell**, often at Framestore on 20.5 with no way to debug. So every builder behaves the same way (the FX Template convention). It installs into whatever network he has open, never edits his nodes, and prints what it made.

Start from `builder_template.py` next to this file. Don't write the scaffold from memory.

## The contract

1. **Header block**: name + version, what it builds and why, HOW TO USE (open a network, paste), what `BUILD_DEMO` True/False do, and "Existing nodes are never changed or moved."
2. **CONFIG block** at the top, one setting per line, aligned `NAME   = value   # comment`. Tests edit these lines by exact text, so keep the spacing stable between versions.
   - `BUILD_DEMO`: True builds a small self-contained demo scene (nodes named `demo_*`) plus the setup. False attaches to Plug's nodes.
   - `TARGET = ""`: the network open in the Network Editor (`current_network()`). A path overrides it.
   - Node inputs (`DOPNET`, `ROOT_PIECES`, ...) resolve through `find()`: first a name in the open network, then a full path. They fail loudly and never guess.
3. **Where it builds**: `sop_network()`. In a SOP network, build right there. At `/obj`, create one new geo. Anything else raises a clear error.
4. **Placement**: every node goes BELOW the lowest existing node (`top = min(y) - 2`), through `mk()`. Nothing is ever moved, renamed, rewired or deleted, unless the script is explicitly a patch. A patch says so in its header and touches only what it names.
5. **Naming**: the main chain uses a prefix (`ROOT_`, `LOP_`, ...). Outputs are `OUT_*` nulls.
6. **Display flag, the one allowed change**: with `SET_DISPLAY = True` (the default), the last `OUT_*` gets the display and render flags, which takes them off whatever node had them. That is the only effect on existing nodes a builder may have. Keep it behind the CONFIG switch, and say in the final print which node now has the flag.
7. **VEX** goes into a wrangle as a raw string `r'''...'''`.
8. **Plug's input may not be polygons** (packed, NURBS, a VDB). When the setup reads a surface, either convert it inside the builder (`unpack`, `convert`), or check it and raise a clear error. Never let it silently produce nothing.
9. **Python**: Houdini-agnostic, so it works in 20.5 and 21. No f-strings with `=`, no walrus, only `hou` APIs present in both. Guard version-specific parms with `if node.parm("x"):`.
10. **Ends with one `print`**: where it built, the node count, and the output names.

## Parm gotchas (seen for real)

| Node / parm | Gotcha |
|---|---|
| `copytopoints::2.0` `applyattribs1` | Doesn't exist until `targetattribs` is set |
| `dopimport::2.0` `objpattern` | `*` also imports the ground plane; use `*rbd*` |
| `dopimport` `doppath` | Set with `imp.relativePathTo(dop)`, not `net.relativePathTo` |
| `timeshift` `frame` | Has a `$F` expression; `deleteAllKeyframes()` before `set()` |
| LOP `instancer` | `protopattern="/<sopimport>/*"`, `protoindexsrc="nameattr"`, `nameattr="name"` |
| `unpackusd::2.0` | Instancers need `iterations=2`, `output="polygons"` |
| Node type versions | Use the explicit `::2.0` / `::3.0` names you tested with |
| Menu parms (`normal` `type`, `sphere` `type`, `torus` `type`) | Set by token, not index: `"typepoint"`, `"polymesh"`, `"poly"`. Read the tokens with `parm.parmTemplate().menuItems()` |
| `scatter::2.0` + point attribs (N, uv) | Don't count on scatter carrying them. Look them up in a wrangle: `xyzdist(1, P, prim, uv)` then `primuv(1, "N", prim, uv)` |
| Orient from N | `dihedral({0,1,0}, n)` aligns local +Y to N; spin around N with `qmultiply(quaternion(angle, n), ...)` |

## Done means

Verified with houdini-hython-verify (REQUIRED SUB-SKILL), in both `BUILD_DEMO` modes, with a measured number. Then published with houdini-shelf-publish if Plug wants it on the shelf.
