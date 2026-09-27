---
name: houdini-shelf-publish
description: Use when adding a new technique, a new version, or a changed file to Plug's Houdini Snippet Shelf, or when he says "เพิ่มเข้า Snippet Shelf" / "add this to the shelf" after a Houdini fix, VEX snippet or builder script.
---

# Publishing to the Houdini Snippet Shelf

## Overview

The shelf exists in THREE places and they must move together:

| Where | Holds |
|---|---|
| Artifact https://claude.ai/artifact/3qTbGYMJKu4Y8174uEWovB | every version of every technique (the source of truth) |
| `P:\Project\Houdini Snippet Shelf\page\houdini-snippet-shelf.html` | the page as last published |
| `P:\Project\Houdini Snippet Shelf\techniques\` + GitHub `plugsopon/houdini-snippet-shelf` (private) | latest version of each technique, as files |

Plug can also edit on the page itself, so the live artifact may be newer than the repo. Always start from the live artifact.

All data edits go through `shelf.py` (next to this file). Never hand-edit the `lib-data` JSON: a `<` must become `\u003c`, and a bad escape silently breaks the page. `shelf.py` also strips the artifact service's page shell (`<!doctype html>…<body>` … `</body></html>`) that an `Artifact` read wraps around the page. Publishing that shell would nest one more every time. Pass it Windows paths.

## Steps

1. **Write and test the code first** (REQUIRED SUB-SKILL: houdini-hython-verify). Nothing untested goes on the shelf. If Plug tested it himself and gives the result, put that in `tested` (e.g. `"Plug · Houdini 20.5"`) and say so in the notes.
2. **Read the live artifact:** `Artifact` action `read`, url above. Note the saved file path it reports (`...artifact-16f65d8e-<version>.html`).
3. **Write a spec** (JSON, e.g. in the scratchpad):
   ```json
   {"technique": {"id": "rbd-copy-from-root"},
    "version": {"v": "auto", "notes": "v006: <what changed + measured result>",
                "append_previous_notes": true,
                "files": [{"id": "rbd-root-copy-builder", "title": "...", "lang": "python",
                           "context": "Python Shell", "tested": "Houdini 21.0.671 · <scene>",
                           "description": "...", "notes": "...", "code_file": "build_v6.py"}]}}
   ```
   - Existing technique: under `technique`, only `id` is needed. The previous version's files are carried over. A file with the same `id` is replaced. A new `id` is added and needs the FULL entry shown above; `"position": 1` places it second (0-based, default last). `"remove_files": ["id"]` drops one.
   - Renaming a technique (`name`) renames its `techniques/` folder. After export, `git rm -r` the old folder that `export` reports as no longer in the page. Never change an `id`.
   - New technique: add `name`, `category`, `type` (`Sop`/`Object`/...), optional `insert_after`.
   - `python shelf.py list <page.html>` shows ids, categories and file ids.
4. **Build:** `python shelf.py add <live.html> spec.json "P:\Project\Houdini Snippet Shelf\page\houdini-snippet-shelf.html"`
5. **Check:** `python shelf.py diff <live.html> <page.html>` must list ONLY the technique you touched.
6. **Publish:** `Artifact` publish, `file_path` = the page file, `url` = the artifact url, a short `label`. No `icon`, no `capabilities` (the stored ones carry over).
7. **Export + push:**
   ```
   python shelf.py export "P:\Project\Houdini Snippet Shelf\page\houdini-snippet-shelf.html" "P:\Project\Houdini Snippet Shelf"
   git -C "P:\Project\Houdini Snippet Shelf" add page techniques hip
   git -C "P:\Project\Houdini Snippet Shelf" commit -m "<technique>: <version> - <what>"
   git -C "P:\Project\Houdini Snippet Shelf" push
   ```
   New `.hipnc` scenes for the technique go in `hip\<topic>\` and are committed too.
8. **Reply to Plug in Thai.** Say what's in the version and the measured result. Say it is untested in 20.5, since he pastes at Framestore on 20.5.

## Writing the notes

Plug reads the shelf in Thai. Put the notes, descriptions and file notes in Thai; keep the code comments in English. Each version's notes open with what changed in that version, then give the measured result (the numbers from the hython check), then which Houdini version it was tested in. Every claim in the notes is either measured (give the number) or labelled as reasoning ("ตามทฤษฎี, ยังไม่ได้วัด").

## Common mistakes

| Mistake | Result |
|---|---|
| Building from the repo page instead of the live artifact | Plug's own page edits are overwritten |
| Publishing without `url` | A second, separate artifact is created |
| Updating the page but not `techniques/` or git | Folder and GitHub go stale |
| `"v": "v005"` when v005 exists | `shelf.py` refuses; use `auto` |
| Forgetting `append_previous_notes` | The history in the notes stops at this version |
| `git add -A` | Sweeps in stray scratch files; add `page techniques hip` by name |
