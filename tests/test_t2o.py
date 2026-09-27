import hou, sys
code = open(sys.argv[1], encoding="utf8").read()
geo = hou.node("/obj").createNode("geo", "t2o")
box = geo.createNode("box"); box.parm("type").set(1)
g = geo.createNode("grid"); sc = geo.createNode("scatter::2.0"); sc.setInput(0, g); sc.parm("npts").set(60)
mk = geo.createNode("attribwrangle", "make_xform"); mk.setInput(0, sc)
mk.parm("snippet").set('''
vector4 q = sample_orientation_uniform(rand(@ptnum + {3,7,11}));
float mode = @ptnum % 4;
vector s = mode == 0 ? set(0.3,0.3,0.3) : mode == 1 ? fit01(rand(@ptnum+{1,2,3}),0.1,0.6) : mode == 2 ? set(-0.4,0.2,0.3) : set(0.5,0.5,0.5);
v@want_s = s; p@want_q = q;
matrix3 S = ident(); S = set(s.x,0,0, 0,s.y,0, 0,0,s.z);
3@transform = S * qconvert(q);
''')
ref = geo.createNode("copytopoints::2.0", "ref"); ref.setInput(0, box); ref.setInput(1, mk)
# run the insert script with mk selected; ref is downstream -> gets rewired too, so build a second copy first
cmp = geo.createNode("copytopoints::2.0", "cmp"); cmp.setInput(0, box)
mk.setSelected(True, clear_all_selected=True)
exec(compile(code, "ins", "exec"), {"hou": hou, "__name__": "__main__"})
w = geo.node("transform_to_orient")
print("ref now wired to:", ref.inputs()[1].name(), "| errors:", w.errors())
cmp.setInput(1, w)
ref.setInput(1, mk)   # keep ref on the original transform
a = [p.position() for p in ref.geometry().points()]; b = [p.position() for p in cmp.geometry().points()]
print("points", len(a), len(b), "max err %.7f" % max((x - y).length() for x, y in zip(a, b)))
pts = w.geometry().points()
print("attribs:", [x.name() for x in w.geometry().pointAttribs()])
for p in pts[:4]:
    print(p.number(), "pscale %.3f" % p.attribValue("pscale"), "scale", [round(v, 3) for v in p.attribValue("scale")], "want", [round(v, 3) for v in p.attribValue("want_s")])
