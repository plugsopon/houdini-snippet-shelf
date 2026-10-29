"""Fern field plan: Crag walks through scattered ferns; each fern's growth = its distance to Crag.
The fern itself is fern_plan's network (with noise wind on its curves), scaled from a seedling to
full size by its own grow value, and baked into N growth stages by a For-Each (count) loop that is
built LAST, around the finished fern. The loop is time-independent, so it cooks once; noise wind
then moves the baked stages every frame, before Copy to Points packs one fern per field point. Field points pick the stage that matches their distance.
Columns: 0 walker / output, 1 field points + instancing, 2-4 the fern, 3 the loop metadata.
Top -> bottom, left -> right; no wire slants up. Typed VEX carries no comments (Plug: they slow
the recording down); the source strings keep them for whoever reads this file."""
import re

import fern_plan as F

STAGES = 16
COL_X, ROW_Y = F.COL_X, F.ROW_Y
TASK_LABEL = "Brother is building the fern field"

FIELD_GROW = r'''// How open is the fern at this spot? Ground distance to the nearest point of the walker:
// close -> open, far -> coiled up again. variant = which baked growth stage to copy here.
int n = npoints(1);
float d = 1e9;
for (int i = 0; i < n; i++) {
    vector q = point(1, "P", i);
    d = min(d, length(set(q.x - @P.x, 0.0, q.z - @P.z)));
}
f@dist = d;
f@grow = 1.0 - smooth(chf("open_radius"), chf("closed_radius"), d);
i@variant = int(rint(f@grow * (chi("stages") - 1)));
@pscale = chf("size") * fit01(rand(@ptnum + 3.1), 0.8, 1.2);
p@orient = quaternion(radians(rand(@ptnum + 7.7) * 360.0), {0, 1, 0});
'''
STAGE_GROW = r'''// A closed fern is a small seedling; it grows to full size as it opens.
float g = chf("grow");
@P *= lerp(chf("seedling"), 1.0, g * g * (3.0 - 2.0 * g));
'''
STAGE_TAG = r'''// Which growth stage this packed fern is (matches the field points' variant).
i@variant = detail(1, "iteration", 0);
'''
STEM_CURL = F.STEM_CURL.replace(
    'float t = smooth(chf("start"), chf("end"), @Time);          // 0..1, eased',
    'float t = chf("grow");                                     // 0 coiled .. 1 open (per loop stage)')
LEAF_POINTS = F.LEAF_POINTS.replace('float t = smooth(chf("start"), chf("end"), @Time);',
                                    'float t = chf("grow");                       // same stage as stem_curl')
assert STEM_CURL != F.STEM_CURL and LEAF_POINTS != F.LEAF_POINTS


def bare(vex):
    """The VEX as typed on camera: no // comments, no blank lines."""
    out = []
    for line in vex.splitlines():
        code = re.sub(r"\s*//.*$", "", line).rstrip()
        if code:
            out.append(code)
    return "\n".join(out) + "\n"


FERN_COL, FERN_ROW = 2, 1
fern = []
for name, typ, col, row, ins, parms, snip in F.NODES:
    name2 = "fern_OUT" if name == "OUT" else name
    ins2 = [(i, "fern_OUT" if s == "OUT" else s) for i, s in ins]
    snip2 = {"stem_curl": STEM_CURL, "leaf_points": LEAF_POINTS}.get(name, snip)
    fern.append((name2, typ, col + FERN_COL, row + FERN_ROW, ins2, parms, snip2))
R = max(r for _, _, _, r, _, _, _ in fern)          # fern_OUT's row

# Build order = the story: the fern (open, full size), its growth scale, the walker and the field,
# then the For-Each loop wrapped around the fern, then the instancing. Positions don't depend on it.
NODES = fern + [
    ("stage_grow", "attribwrangle", FERN_COL, R + 1, [(0, "fern_OUT")], {}, STAGE_GROW),
    ("walker", "testgeometry_crag", 0, 0, [], {}, None),
    ("field_grid", "grid", 1, 0, [], {"sizex": 6.0, "sizey": 9.0, "tz": 2.0}, None),
    ("field_scatter", "scatter::2.0", 1, 1, [(0, "field_grid")], {"npts": 140, "relaxiterations": 20}, None),
    ("field_grow", "attribwrangle", 1, 2, [(0, "field_scatter"), (1, "walker")], {}, FIELD_GROW),
    ("stages_begin", "block_begin", 2, 0, [], {"method": "input"}, None),
    ("stage_meta", "block_begin", 3, 0, [], {"method": "metadata"}, None),
    ("stage_tag", "attribwrangle", FERN_COL, R + 2, [(0, "stage_grow"), (1, "stage_meta")], {"class": 1}, STAGE_TAG),
    ("stages_end", "block_end", FERN_COL, R + 3, [(0, "stage_tag")],
     {"itermethod": "count", "method": "merge", "iterations": STAGES,
      "blockpath": "../stages_begin", "templatepath": "../stages_begin"}, None),
    ("stage_wind", "attribwrangle", FERN_COL, R + 4, [(0, "stages_end")], {}, F.WIND),
    ("fern_instances", "copytopoints::2.0", 1, R + 5, [(0, "stage_wind"), (1, "field_grow")],
     {"useidattrib": 1, "idattrib": "variant", "pack": 1}, None),
    ("scene_merge", "merge", 0, R + 6, [(0, "walker"), (1, "fern_instances")], {}, None),
    ("OUT", "null", 0, R + 7, [(0, "scene_merge")], {}, None),
]
NODES = [(n, t, c, r, i, p, bare(s) if s else s) for n, t, c, r, i, p, s in NODES]

SPARE = dict(F.SPARE)
SPARE["stage_wind"] = SPARE.pop("WIND")
SPARE["stem_curl"] = SPARE["stem_curl"] + [("grow", "Grow (0 coiled - 1 open)", 1.0, 0.0, 1.0)]
SPARE["leaf_points"] = SPARE["leaf_points"] + [("grow", "Grow", None, 0.0, 1.0)]
SPARE["stage_grow"] = [("grow", "Grow", None, 0.0, 1.0), ("seedling", "Seedling size", 0.15, 0.0, 1.0)]
SPARE["field_grow"] = [("open_radius", "Fully open within", 0.35, 0.0, 5.0),
                       ("closed_radius", "Coiled beyond", 1.1, 0.0, 10.0),
                       ("size", "Fern size", 0.21, 0.0, 2.0),
                       ("stages", "Stages", STAGES, 2, 100)]
LINKS = dict(F.LINKS)
LINKS[("leaf_points", "grow")] = "stem_curl/grow"
LINKS[("stage_grow", "grow")] = "stem_curl/grow"
EXPRS = {}
# Set once the node they point at exists (the loop is built last): no error badges along the way.
DEFER = {"stages_end": [
    ("stages_begin", {"blockpath": "../stages_end"}, {}),
    ("stage_meta", {"blockpath": "../stages_end"}, {}),
    ("stem_curl", {}, {"grow": 'detail("../stage_meta", "iteration", 0) / max(1, ch("../stages_end/iterations") - 1)'}),
    ("field_grow", {}, {"stages": 'ch("../stages_end/iterations")'}),
]}
RAMPS = {"leaf_sweep": ("scaleramp",) + F.LEAF_RAMP}
DISPLAY = "OUT"
