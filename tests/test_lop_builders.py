import hou, sys
v4, standalone, userfile = sys.argv[1], sys.argv[2], sys.argv[3]

def run(path, repl):
    code = open(path, encoding="utf8").read()
    for a, b in repl.items():
        assert a in code, a
        code = code.replace(a, b, 1)
    exec(compile(code, path, "exec"), {"hou": hou, "__name__": "__main__"})

def nn(net, sop_name, lop_name, label):
    for f in (5, 20, 40):
        hou.setFrame(f)
        a = [p.position() for p in net.node(sop_name).geometry().points()]
        b = [p.position() for p in net.node(lop_name).geometry().points()]
        w = max(min((x - y).length() for y in a) for x in b) if a and b else -1
        w2 = max(min((x - y).length() for y in b) for x in a) if a and b else -1
        print("%-10s f%-3d sop=%-5d lop=%-5d worst=%.5f/%.5f" % (label, f, len(a), len(b), w, w2))

# 1) whole setup from an empty scene, LOP included
hou.hipFile.clear(suppress_save_prompt=True)
hou.playbar.setFrameRange(1, 48)
run(v4, {'TARGET       = ""': 'TARGET       = "/obj"'})
n = hou.node("/obj/rbd_root_copy")
nn(n, "OUT_root_copy_points", "LOP_check_unpackusd", "V4 demo")
print("lopnet:", [c.name() for c in n.node("LOP_instancing").children()], "errors:", n.node("LOP_instancing/instancer1").errors())

# 2) standalone on Plug's file (fractured root pieces)
hou.hipFile.load(userfile, suppress_save_prompt=True, ignore_load_warnings=True)
run(standalone, {'TARGET       = ""': 'TARGET       = "/obj/geo1"',
                 'TARGETS_NODE = "ROOT_point_targets_clean"': 'TARGETS_NODE = "ROOT_point_targets_clean1"',
                 'ROOT_NODE    = "ROOT_pieces"': 'ROOT_NODE    = "ROOT_pieces3"'})
g = hou.node("/obj/geo1")
nn(g, "OUT_root_copy_points1", "LOP_check_unpackusd", "USER lop")
