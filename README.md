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

## Houdini scene files - `hip/`

- `hip/emittingRBD/` - the emitting-RBD work: original file, the rest-pose fix, the root
  copy, the LOP fix, and `emittingRBD_fracture_v5.hipnc` (builder v005 on the fractured box).
- `hip/particles/` - the unborn-particles follow-live tests.
- `hip/underwater/` - Underwater.hipnc (April). Its cobweb / hand .abc files and the hand
  texture were already missing before the move; they were never in TestHou.
- Each folder keeps `backup/` (Houdini's own backups) and `geo/` (file caches, found
  through `$HIP/geo`). Both stay on disk but are NOT in git - `geo/` is ~2.6 GB.
- Moved here from `C:\Users\Plug\Desktop\TestHou\` on 2026-09-27. Houdini's recent-files
  list still points at the old path; open them from here.
