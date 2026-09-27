---
name: houdini-hython-verify
description: Use when a Houdini builder script, VEX wrangle or .hipnc fix needs checking before it is handed to Plug, when debugging one of his .hip files ("ช่วยดูไฟล์นี้หน่อย"), or when a claim like "matches the sim" / "0 error" needs a number behind it.
---

# Verifying Houdini work with hython

## Overview

Plug pastes what Brother gives him straight into Houdini, often at Framestore where he can't debug. So every script and fix gets run in hython and measured before it reaches him. A claim without a measured number is not done.

hython: `C:\Program Files\Side Effects Software\Houdini 21.0.671\bin\hython.exe` (Apprentice, H21). Plug's office runs **20.5**, which is untested; say so in every reply.

Helpers live in `hou_tools.py` next to this file (add this folder to `sys.path`; in a copy of the repo use that copy's path).

## Safety rules

- **Never touch Plug's running Houdini.** hython is a separate process; only ever load files into it.
- **Never overwrite his .hipnc.** Save a fix as a NEW file next to it (`<name>_<what>.hipnc`) and say which one. `hou.hipFile.save` overwrites silently, and suffixes like `_fixed` / `_lopfix` may already exist, so `assert not os.path.exists(path)` before saving and pick another suffix if it does.
- Before moving or renaming any .hipnc, check no Houdini process is running (`Get-Process | ? ProcessName -match 'houdini|happrentice'`).

## Quick reference

```
hython hou_tools.py dump    FILE.hipnc /obj/geo1            # what is in the network
hython hou_tools.py refs    FILE.hipnc                      # file refs that exist / are missing
hython hou_tools.py compare FILE.hipnc NODE_A NODE_B 5 20 40  # worst point distance
```

A test script, for builders and fixes:
```python
import sys; sys.path.insert(0, r"P:\Project\Houdini Snippet Shelf\.claude\skills\houdini-hython-verify")
from hou_tools import *
hou.hipFile.clear(suppress_save_prompt=True); hou.playbar.setFrameRange(1, 40)
obj = hou.node("/obj"); before = child_names(obj)
run_script(r"...\build_x.py", {'TARGET       = ""': 'TARGET       = "/obj"'})   # CONFIG edits must match exactly once
geo = new_children(obj, before)[0]                     # never hou.node("/obj/<intended name>")
truth = geo.createNode("unpack"); truth.setInput(0, geo.node("ROOT_sim_pieces"))
compare(truth, geo.node("OUT_root_copy"), (5, 20, 40), "packed")
```
Orientation (copies aligned to N, RBD rotations): pack the copies, then `packed_transforms(sop)` gives each piece's `Matrix4`. `axis_of(m, 1)` is its world +Y, and `angle_deg(a, b)` measures the angle to the expected direction. Report the max and the mean in degrees.

On Plug's own file, load it (`hou.hipFile.load(path, suppress_save_prompt=True, ignore_load_warnings=True)`) instead of `clear()`, and read the real node names from `dump` first. His files often hold several runs of a builder, so names carry suffixes (`ROOT_pieces3`, `ROOT_point_targets_clean1`) and a script's CONFIG defaults usually don't exist there. `dump` hides parms at their default values; query a specific one with `node.parm("x").eval()`.

**Pick the reference before comparing.** First prove the reference is right, e.g. Copy to Points against the unpacked sim pieces, which should be ~0. Use the chain that has the display flag or that Plug wired up himself. If there are several (packed / points), compare against each.

**Tolerances.** Pure SOP copies of the same transforms: ≤ 1e-6. Anything through USD / LOPs: ~1e-4 to 6e-4, and it grows with distance from the origin. So always include the LAST frames, and report what you measured instead of quoting an older bound.

Test in BOTH modes of a builder: `BUILD_DEMO = True` in an empty scene, and `False` on the real .hipnc Plug sent.

## Traps that bite

| Symptom | Cause / fix |
|---|---|
| hython crashes on import, `inspect`/`json` errors | cwd holds a loose `inspect.py` etc. that shadows stdlib. Run from `C:\Users\Plug`, never from the scratchpad |
| `node not found: 'C:/Program Files/Git/obj/...'` | Git Bash rewrote a node path given as a CLI argument. Prefix `MSYS_NO_PATHCONV=1` or use PowerShell. Paths inside a test script are unaffected |
| Packed prims "not found" | `prim.type() == hou.primType.PackedPrim` is False for copytopoints prims in H21. Use `isinstance(p, hou.PackedPrim)` (`packed_transforms` does) |
| Script file starts with `\ufeff`, `SyntaxError` | PowerShell `Set-Content -Encoding UTF8` wrote a BOM. Write files with the Write tool or bash |
| New `copytopoints` has no `applyattribs1` parm | Multiparm is empty until `targetattribs` is set; set it first |
| Test reads the OLD node | Name was taken, Houdini made `name1`. Use `new_children` |
| Big "error" between two matching setups | Sorted-and-zipped points. Use `compare` (nearest neighbour) |
| USD / LOP result off by ~0.0005 | Expected: USD stores orientations in half precision. Report it, don't chase it (see Tolerances) |
| `MISSING` gallery `.db` or `$F` cache in `refs` | Never written; not broken. Check the file existed before any move |

## Reporting

Report to Plug in Thai. Give point counts and the worst distance for each mode and frame checked. Say which scene the check ran on, and add "ยังไม่ได้ลองกับ 20.5".
