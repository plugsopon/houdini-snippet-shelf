"""Fiddlehead / unfurling fern - the network plan, shared by the quick API build (prototype) and the
visible build. Layout follows Plug's rule: top -> bottom, left -> right; every node sits BELOW its
inputs, no wire ever slants upward. Columns: 0 = stem, 1 = leaf spine + leaves, 2 = leaf points.

Method (SideFX forum 'KineFX additive rotation of joints', CGWiki 'Curve Unroll'):
 - straight line -> resample -> Rig Doctor (joints: name + localtransform)
 - Rig Attribute Wrangle: rotate every joint's localtransform about X; the bend grows toward the tip
   (snail-shell spiral) and a front travels base -> tip over time so the coil pays out
 - Compute Transform: world transforms + P from the edited local transforms
 - leaves: every Nth joint becomes a leaf point (golden-angle phyllotaxis, own timing), a straight
   leaf spine is copied to them, and a primitive wrangle re-lays each spine as its own spiral that
   uncurls (and grows) on its own clock, then Sweep makes a leaf-shaped ribbon.
"""

STEM_CURL = r'''// Fiddlehead coil on a KineFX skeleton (Rig Attribute Wrangle, run over points).
// Every joint bends a little about its local X; the bend grows toward the tip, so the
// fully curled stem is a snail-shell spiral. A front travels from base to tip over time:
// joints behind it straighten, so the coil pays out bit by bit.
float u = float(@ptnum) / max(1, npoints(0) - 1);
float t = smooth(chf("start"), chf("end"), @Time);          // 0..1, eased
float soft = chf("soft");
float front = lerp(-soft, 1.0, t);
float curled = smooth(front, front + soft, u);              // 1 = still coiled
float bend = radians(chf("max_bend")) * pow(u, chf("tightness"));
rotate(4@localtransform, bend * curled, {1, 0, 0});
'''

STEM_WIDTH = r'''// Stem gets thinner toward the tip (polywire reads pscale).
float u = float(@ptnum) / max(1, npoints(0) - 1);
@pscale = lerp(1.0, 0.25, u);
'''

LEAF_SETUP = r'''// The leaf spine: a straight line along local +X, 0..1 in leaf length.
f@lu = float(@ptnum) / max(1, npoints(0) - 1);
'''

LEAF_POINTS = r'''// Leaf roots on the stem: every Nth joint, golden-angle around the stem,
// each with its own clock (lt) that starts when the stem's uncoiling front passes it.
int every = chi("every");
if (@ptnum % every != 0 || @ptnum < chi("skip") || @ptnum > npoints(0) - chi("skip_tip")) {
    removepoint(0, @ptnum);
    return;
}
float u = float(@ptnum) / max(1, npoints(0) - 1);
// same clock as stem_curl (channel-referenced spare parms keep them in sync)
float t = smooth(chf("start"), chf("end"), @Time);
float soft = chf("soft");
float front = lerp(-soft, 1.0 + chf("leaf_dur"), t);       // runs past the tip so tip leaves open too
float lt = clamp((front - u) / chf("leaf_dur"), 0, 1);
f@lt = smooth(0, 1, lt);

// frame: joint world rotation (Z = toward the next joint), turned around the stem by the
// golden angle, then tilted so the leaf points out and up
matrix3 m = 3@transform;
vector4 q = quaternion(m);
q = qmultiply(q, quaternion(radians(137.508 * (@ptnum / every)), {0, 0, 1}));
q = qmultiply(q, quaternion(radians(-chf("tilt")), {0, 1, 0}));
p@orient = q;
@pscale = chf("leaf_size") * lerp(1.0, 0.45, u) * fit01(f@lt, 0.05, 1.0);
'''

LEAF_UNFURL = r'''// Each copied leaf spine (one primitive per leaf) is re-laid as its own spiral in the leaf's
// frame, read from its target point on input 1 (orient / pscale / P / lt). lt = 0: rolled up
// like a snail shell; lt = 1: straight. The bend grows toward the leaf tip, like the stem.
int tp = @primnum;
vector root = point(1, "P", tp);
vector4 q = point(1, "orient", tp);
float ps = point(1, "pscale", tp);
float lt = point(1, "lt", tp);
int pts[] = primpoints(0, @primnum);
int n = len(pts);
float seg = 1.0 / max(1, n - 1);
float curl = radians(chf("leaf_curl")) * (1.0 - lt);
vector p = 0;
float ang = 0;
for (int i = 0; i < n; i++) {
    float lu = float(i) / max(1, n - 1);
    if (i > 0) {
        ang += curl * pow(lu, chf("leaf_tight"));
        p += set(cos(ang), sin(ang), 0) * seg;
    }
    setpointattrib(0, "P", pts[i], qrotate(q, p * ps) + root);
    setpointattrib(0, "pscale", pts[i], ps);          // Sweep scales the ribbon width by pscale
}
// Sweep reads the up vector per CURVE (a primitive attribute) and carries it along: the leaf's own
// local Y, so the blade spreads sideways (local Z) whatever the curl.
setprimattrib(0, "up", @primnum, qrotate(q, {0, 1, 0}));
'''


WIND = r'''// Wind without a sim: a moving noise field pushes every point of the baked fern stages.
// The push grows with height (h*h), so the base stays planted; stem and leaves read the same
// field, so a leaf root moves with the stem it sits on.
float h = clamp(@P.y / chf("height"), 0.0, 1.0);
float s = @Time * chf("speed");
vector nz = noise(@P * chf("freq") + set(s, 0.0, s * 0.5));
nz -= {0.5, 0.5, 0.5};
float gust = noise(s * 0.3);
nz.x += chf("gust") * (gust - 0.5);
@P += nz * chf("amp") * h * h;
'''

SPARE = {   # node -> [(name, label, default, min, max)]
    "stem_curl": [("start", "Start (s)", 0.2, 0, 10), ("end", "End (s)", 4.0, 0, 10),
                  ("soft", "Softness", 0.25, 0.01, 1), ("max_bend", "Max bend (deg/joint)", 28.0, 0, 90),
                  ("tightness", "Tightness", 1.6, 0.1, 5)],
    "leaf_points": [("every", "Every Nth joint", 6, 1, 20), ("skip", "Skip base joints", 10, 0, 60),
                    ("skip_tip", "Skip tip joints", 6, 0, 60), ("leaf_dur", "Leaf open (front)", 0.25, 0.01, 1),
                    ("tilt", "Tilt (deg)", 35.0, -90, 90), ("leaf_size", "Leaf size", 0.9, 0, 5),
                    ("start", "Start (s)", None, 0, 10), ("end", "End (s)", None, 0, 10), ("soft", "Softness", None, 0, 1)],
    "WIND": [("amp", "Wind strength", 0.9, 0, 3), ("freq", "Wind size (freq)", 0.6, 0, 5),
                  ("speed", "Wind speed", 0.8, 0, 5), ("gust", "Gust", 0.5, 0, 2), ("height", "Fern height", 4.0, 0.1, 20)],
    "leaf_unfurl": [("leaf_curl", "Leaf curl (deg/seg)", 55.0, 0, 120), ("leaf_tight", "Leaf tightness", 1.6, 0.1, 5)],
}
LINKS = {("leaf_points", "start"): "stem_curl/start", ("leaf_points", "end"): "stem_curl/end",
         ("leaf_points", "soft"): "stem_curl/soft"}

# name, type, col, row, inputs [(input_idx, src)], parms, snippet
NODES = [
    ("stem_line", "line", 0, 0, [], {"dist": 4.0, "points": 2, "dirx": 0, "diry": 1, "dirz": 0}, None),
    ("stem_resample", "resample", 0, 1, [(0, "stem_line")], {"length": 0.05}, None),
    ("stem_skeleton", "kinefx::rigdoctor", 0, 2, [(0, "stem_resample")],
     {"initmissingnames": 1, "inittransforms": 1, "reorienttochild": 1}, None),
    ("stem_curl", "kinefx::rigattribwrangle", 0, 3, [(0, "stem_skeleton")], {}, STEM_CURL),
    ("stem_world", "kinefx::computetransform", 0, 4, [(0, "stem_curl")], {}, None),
    ("stem_width", "attribwrangle", 0, 5, [(0, "stem_world")], {}, STEM_WIDTH),
    ("stem_tube", "polywire", 0, 6, [(0, "stem_width")], {"radius": 0.045, "usescaleattrib": 1, "div": 6}, None),

    ("leaf_line", "line", 1, 0, [], {"dist": 1.0, "points": 2, "dirx": 1, "diry": 0, "dirz": 0}, None),
    ("leaf_resample", "resample", 1, 1, [(0, "leaf_line")], {"length": 0.05}, None),
    ("leaf_setup", "attribwrangle", 1, 2, [(0, "leaf_resample")], {}, LEAF_SETUP),

    ("leaf_points", "attribwrangle", 2, 5, [(0, "stem_world")], {}, LEAF_POINTS),
    ("leaf_copy", "copytopoints::2.0", 1, 6, [(0, "leaf_setup"), (1, "leaf_points")], {"transform": 0}, None),
    ("leaf_unfurl", "attribwrangle", 1, 7, [(0, "leaf_copy"), (1, "leaf_points")], {"class": 1}, LEAF_UNFURL),
    ("leaf_sweep", "sweep::2.0", 1, 8, [(0, "leaf_unfurl")],
     {"surfaceshape": "ribbon", "cols": 3, "width": 0.42, "applyscale": 1, "upvectortype": "attrib", "upvectorattrib": "up",
      "attribsfrombackbone": "* ^P ^N ^up ^pscale ^scale ^orient ^rot ^pivot ^trans ^transform ^lu"}, None),

    # the stem keeps only P (KineFX + uv attribs would not match the leaves at the merge)
    ("stem_clean", "attribdelete", 0, 8, [(0, "stem_tube")],
     {"doptdel": 1, "ptdel": "* ^P", "dovtxdel": 1, "vtxdel": "*"}, None),
    ("fern_merge", "merge", 0, 9, [(0, "stem_clean"), (1, "leaf_sweep")], {}, None),
    ("OUT", "null", 0, 10, [(0, "fern_merge")], {}, None),
]
LEAF_RAMP = ([0.0, 0.25, 0.7, 1.0], [0.15, 1.0, 0.6, 0.0])   # sweep scale along the leaf: leaf outline
COL_X, ROW_Y = 3.6, 1.15
