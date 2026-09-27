import hou, sys
v5, userfile, outfile = sys.argv[1], sys.argv[2], sys.argv[3]
def run(path, repl):
    code = open(path, encoding="utf8").read()
    for a, b in repl.items():
        assert a in code, a
        code = code.replace(a, b, 1)
    exec(compile(code, path, "exec"), {"hou": hou, "__name__": "__main__"})
def sim_vs(net, dop_name, copy_name, label):
    # every simulated packed piece's points vs the root copy (nearest neighbour both ways)
    for f in (5, 20, 40):
        hou.setFrame(f)
        imp = net.node(copy_name).geometry()
        a = [p.position() for p in imp.points()]
        return_ = None
    pass
def nn(net, ref, got, label, frames=(5, 20, 40)):
    for f in frames:
        hou.setFrame(f)
        a = [p.position() for p in net.node(ref).geometry().points()]
        b = [p.position() for p in net.node(got).geometry().points()]
        w = max(min((x - y).length() for y in a) for x in b) if a and b else -1
        w2 = max(min((x - y).length() for y in b) for x in a) if a and b else -1
        print("%-14s f%-3d %s=%-5d %s=%-5d worst=%.6f/%.6f" % (label, f, ref, len(a), got, len(b), w, w2))

# 2) the same builder inside Plug's file (new geo, his geo1 untouched) + saved copy
hou.hipFile.load(userfile, suppress_save_prompt=True, ignore_load_warnings=True)
before = set(c.name() for c in hou.node("/obj").children())
run(v5, {'TARGET       = ""': 'TARGET       = "/obj"'})
m = [c for c in hou.node("/obj").children() if c.name() not in before][0]
print("new geo:", m.path())
up = m.createNode("unpack", "TEST_sim_unpacked"); up.setInput(0, m.node("ROOT_sim_pieces"))
nn(m, "TEST_sim_unpacked", "OUT_root_copy_points", "in-file pts", (5, 20, 40))
nn(m, "OUT_root_copy_points", "LOP_check_unpackusd", "in-file LOP", (20,))
up.destroy()
m.setPosition(hou.node("/obj/geo1").position() + hou.Vector2(3, 0))
hou.hipFile.save(outfile)
print("saved", outfile)
