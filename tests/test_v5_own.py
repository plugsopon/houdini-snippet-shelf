import hou, sys
v5, userfile = sys.argv[1], sys.argv[2]
hou.hipFile.load(userfile, suppress_save_prompt=True, ignore_load_warnings=True)
code = open(v5, encoding="utf8").read()
for a, b in {'BUILD_DEMO   = True': 'BUILD_DEMO   = False', 'TARGET       = ""': 'TARGET       = "/obj/geo1"',
             'DOPNET       = "dopnet1"': 'DOPNET       = "demo_rbd_dopnet1"', 'ROOT_PIECES  = "assemble3"': 'ROOT_PIECES  = "ROOT_assemble1"'}.items():
    assert a in code, a; code = code.replace(a, b, 1)
g = hou.node("/obj/geo1"); before = set(c.name() for c in g.children())
exec(compile(code, v5, "exec"), {"hou": hou, "__name__": "__main__"})
print("new:", sorted(set(c.name() for c in g.children()) - before))
up = g.createNode("unpack", "TEST_u"); up.setInput(0, g.node("ROOT_sim_pieces3"))
new = [c.name() for c in g.children() if c.name() not in before]
cp = [x for x in new if x.startswith("OUT_root_copy_points")][0]; lc = [x for x in new if x.startswith("LOP_check_unpackusd")][0]
for f in (5, 20, 40):
    hou.setFrame(f)
    a = [p.position() for p in up.geometry().points()]; b = [p.position() for p in g.node(cp).geometry().points()]; c = [p.position() for p in g.node(lc).geometry().points()]
    print(f, len(a), len(b), len(c), "%.6f %.6f" % (max(min((x-y).length() for y in a) for x in b), max(min((x-y).length() for y in b) for x in c)))
