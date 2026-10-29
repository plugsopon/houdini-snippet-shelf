"""Brother demo - the pure half (brother_demo_plan): held control frame, typing states, storyboard.

  python tests/test_demo_plan.py        (plain Python - no Houdini, no Qt, no scene)

Every check prints PASS/FAIL; exits 1 on any failure. The SABOTAGE section breaks each rule on
purpose and asserts the matching check goes red, so a check that can never fail is caught.
"""
import os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "mcp", "houdini"))
import brother_demo_plan as P

FAILS = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)


# ---------------------------------------------------------------- the held frame
def frame_rules(edge_target, should_hide):
    out = {}
    now = 1000.0
    out["request running -> on"] = edge_target(1, 0.0, 0.0, now) == 1.0
    out["just after a request -> still on (linger)"] = edge_target(0, now - 0.5, 0.0, now) == 1.0
    out["gap between tool calls, no hold -> off"] = edge_target(0, now - 3.0, 0.0, now) == 0.0
    out["gap between tool calls, held -> ON"] = edge_target(0, now - 3.0, now + 2.0, now) == 1.0
    out["hold expired -> off (no stuck frame)"] = edge_target(0, now - 30.0, now - 0.01, now) == 0.0
    out["idle overlay hides when not held"] = should_hide(now, now - 25, [], 0.0, 0.0)
    out["idle overlay never hides while held"] = not should_hide(now, now - 25, [], 0.0, now + 1)
    return out


for k, v in frame_rules(P.edge_target, P.should_hide).items():
    check("frame: " + k, v)

check("ttl clamped high", P.clamp_ttl(1e9) == P.HOLD_MAX)
check("ttl clamped low", P.clamp_ttl(-5) == P.HOLD_MIN)
check("ttl garbage -> default", P.clamp_ttl("x") == 5.0 and P.clamp_ttl(float("nan")) == 5.0)


# ---------------------------------------------------------------- typing states
def typing_rules(edit_steps):
    out = {}
    old, new = P.VARIANTS["camera"][0], P.VARIANTS["camera"][1]
    st = edit_steps(old, new)
    texts = [t for t, _ in st]
    out["ends on the new text"] = texts[-1] == new
    out["every state is ONE comment line"] = all(t.startswith(P.PREFIX) and "\n" not in t for t in texts)
    out["one keystroke apart"] = all(abs(len(a) - len(b)) == 1 for a, b in zip([old] + texts, texts))
    common = os.path.commonprefix([old, new])
    out["partial edit keeps the common start"] = all(t.startswith(common[:len(P.PREFIX)]) for t in texts) \
        and min(len(t) for t in texts) == len(common)
    st2 = edit_steps("", new)
    out["from empty: marker set as one chunk, then typed"] = st2[0][0] == P.PREFIX and st2[-1][0] == new \
        and all(len(b) - len(a) == 1 for (a, _), (b, _) in zip(st2, st2[1:]))
    st3 = edit_steps("", new, typo_at=5)
    t3 = [t for t, _ in st3]
    out["typo is typed then deleted"] = any(not new.startswith(t) for t in t3) and t3[-1] == new
    try:
        edit_steps("", "rm -rf")
        out["refuses non-comment text"] = False
    except ValueError:
        out["refuses non-comment text"] = True
    try:
        edit_steps("", "// a\nsystem('x')")
        out["refuses multi-line text"] = False
    except ValueError:
        out["refuses multi-line text"] = True
    return out


for k, v in typing_rules(P.edit_steps).items():
    check("typing: " + k, v)


# ---------------------------------------------------------------- storyboard
def story_rules(build_cycle):
    out = {}
    texts = {}
    all_steps = []
    for c in range(4):
        all_steps.append(build_cycle(c, texts))
    flat = [s for cyc in all_steps for s in cyc]
    kinds = {s["kind"] for s in flat}
    out["has focus/type/api_move/wire/unwire/pause"] = {"focus", "type", "api_move", "wire", "unwire", "pause"} <= kinds
    keys = set(P.NODES)
    out["touches only the three demo nodes"] = all(
        s.get(f) in keys for s in flat for f in ("key", "src", "dst") if f in s)
    out["wires form the chain camera->pose->mood"] = all(
        (s["src"], s["dst"]) in (("camera", "pose"), ("pose", "mood")) for s in flat if s["kind"] == "wire")
    out["cycle 0 never unwires (nothing wired yet)"] = not any(s["kind"] == "unwire" for s in all_steps[0])
    out["every typed text is an inert comment"] = all(
        t.startswith(P.PREFIX) and "\n" not in t and "`" not in t
        for s in flat if s["kind"] == "type" for t, _ in s["states"])
    out["positions finite"] = all(all(math.isfinite(v) for v in s["to"]) for s in flat if s["kind"] == "api_move")
    out["cycles vary the text"] = len({texts_c for texts_c in
                                       [tuple(s["states"][-1][0] for s in cyc if s["kind"] == "type") for cyc in all_steps]}) > 1
    secs = [P.cycle_seconds(c) for c in all_steps]
    out["a cycle plays in 8..40 s"] = all(8 <= t <= 40 for t in secs)
    print("     storyboard cycle seconds: %s" % [round(t, 1) for t in secs])
    return out


for k, v in story_rules(P.build_cycle).items():
    check("story: " + k, v)

names = [n for n, _ in P.NODES.values()]
check("node names are valid Houdini names", all(n.replace("_", "").isalnum() and not n[0].isdigit() for n in names))


# ---------------------------------------------------------------- sabotage
def red(rules, broken_fn, *args):
    return not all(rules(broken_fn, *args).values()) if args else not all(rules(broken_fn).values())


def bad_edge(depth, last, held_until, now, linger=1.2):         # the old rule: ignores holds
    return 1.0 if (depth > 0 or now - last < linger) else 0.0


def bad_edge_forever(depth, last, held_until, now, linger=1.2):  # never lets go
    return 1.0


def bad_hide(now, last_active, ripples, lvl, held_until, idle=20.0):
    return now - last_active > idle and not ripples and lvl == 0.0


def bad_steps_jump(old, new, typo_at=None):                      # sets the whole text at once
    return [(new, 0.0)]


def bad_steps_unsafe(old, new, typo_at=None):                    # types the "//" too
    return [(new[:i], 0.0) for i in range(1, len(new) + 1)]


def bad_cycle(cycle, texts):                                     # wires something foreign
    s = P.build_cycle(cycle, texts)
    return s + [{"kind": "wire", "src": "camera", "dst": "seedance_gen"}]


check("SABOTAGE hold ignored -> frame rules red", red(lambda e: frame_rules(e, P.should_hide), bad_edge))
check("SABOTAGE frame never released -> red", red(lambda e: frame_rules(e, P.should_hide), bad_edge_forever))
check("SABOTAGE hide while held -> red", red(lambda h: frame_rules(P.edge_target, h), bad_hide))
check("SABOTAGE whole-text jump -> typing red", red(typing_rules, bad_steps_jump))
check("SABOTAGE typed '//' -> typing red", red(typing_rules, bad_steps_unsafe))
check("SABOTAGE foreign node in story -> red", red(story_rules, bad_cycle))

print("\n%d failure(s)" % len(FAILS))
sys.exit(1 if FAILS else 0)
