# Houdini Snippet Shelf

Plug's Houdini techniques: paste-able Python builders and VEX wrangles, each tested in
Houdini 21.0.671 (Apprentice). Not yet tried in 20.5.

Online (log in to claude.ai): https://claude.ai/artifact/3qTbGYMJKu4Y8174uEWovB
The page holds EVERY version of every technique. This folder holds the latest one.

## Folders

- `techniques/` - one folder per technique, latest version only. Each has a README.md
  (notes, where to paste each file, what it was tested with) plus the .py / .vfl files.
  - `RBD_pieces_to_copy_root_geometry/` - copy the root pieces onto an RBD sim (packed or
    points), fractured-box builder v005, LOP / USD PointInstancer version.
  - `transform_to_orient_scale/` - 3@transform -> orient + scale / pscale.
  - `Unborn_particles_to_follow_live/` - not-yet-born particles follow live neighbours.
  - `2_vectors_to_matrix_orient/`, `Subframe_for_changing_topology/`,
    `Surface_distance_from_an_edge_group/`, `My_First_Shot/` - from the FX Template tool.
- `tests/` - hython scripts that re-run the checks. Run with
  `"C:\Program Files\Side Effects Software\Houdini 21.0.671\bin\hython.exe" tests\<file>.py <args>`
  (the arguments are listed at the top of each script: the builder file and the .hipnc to test).
- `page/houdini-snippet-shelf.html` - the shelf page as last published (Version 18).
- `page/build/` - what the page is built from (template, JS parts, rebuild script, FX Template export).
- `page/history/` - earlier builds of the page.

## Houdini scene files

The .hipnc files stay where Houdini opens them:
`C:\Users\Plug\Desktop\TestHou\` (emittingRBD\ and the particle tests).
