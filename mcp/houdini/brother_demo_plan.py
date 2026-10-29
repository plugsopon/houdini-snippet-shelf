"""brother_demo_plan - the PURE half of the Brother demo: no hou, no Qt, so it can be tested
anywhere (tests/test_demo_plan.py).

Three things live here:
  * edge_target / clamp_ttl - when the "Brother is in control" frame must be on. A hold keeps
    it on between requests (an AI thinking between tool calls); a hold always has a deadline,
    so a runner that dies without cleaning up can only leave the frame on for ttl seconds.
  * edit_steps - the text states a prompt field goes through while it is typed character by
    character, including partial edits (keep the common start, backspace the rest, retype).
    Every state stays a single VEX comment line, so a cook between keystrokes never errors.
  * build_cycle - the storyboard of one demo cycle as a list of plain step dicts. brother_demo
    plays them; nothing here touches a scene.
"""
import math

HOLD_MAX = 120.0          # a hold can never ask for more than this (seconds)
HOLD_MIN = 0.5
LINGER = 1.2              # the frame stays on this long after the last controlling request

PREFIX = "// "            # every prompt is one comment line: inert VEX, nothing executes

# node key -> (Houdini node name, the name it had in the 246 rehearsal)
NODES = {
    "camera": ("Camera_Prompt", "demo_wrangle_1"),
    "pose":   ("Model_Pose_Prompt", "demo_wrangle_2"),
    "mood":   ("Mood_and_Tone_Prompt", "demo_wrangle_3"),
}
ORDER = ("camera", "pose", "mood")
DEMO_NET = "/obj/BROTHER_DEMO_246_A"

VARIANTS = {
    "camera": ("// Camera: slow push-in, 50mm, eye level, soft key from left",
               "// Camera: slow push-in, 85mm, low angle, rim light from behind",
               "// Camera: locked-off wide, 24mm, overhead, window light"),
    "pose":   ("// Model pose: three-quarter turn, chin down, hand near collarbone",
               "// Model pose: three-quarter turn, looking over shoulder, relaxed hands",
               "// Model pose: seated, leaning forward, product held at chest"),
    "mood":   ("// Mood and tone: warm golden hour, creamy highlights, calm",
               "// Mood and tone: cool morning blue, crisp shadows, fresh",
               "// Mood and tone: warm golden hour, film grain, nostalgic"),
}

# network-space positions (a node's lower-left corner), alternated per cycle
LAYOUTS = (
    {"camera": (-5.0, 0.6), "pose": (-1.6, -0.9), "mood": (1.8, -2.4)},
    {"camera": (-4.6, -2.2), "pose": (-1.2, -0.6), "mood": (2.2, 1.0)},
)
FRAME = (-8.0, -4.6, 6.0, 3.4)     # visible bounds while the demo runs (xmin, ymin, xmax, ymax)

# seconds per primitive - the storyboard's clock
CHAR = 0.028                        # one typed character
BACKSPACE = 0.016
TYPO_FIX = 0.12                     # pause on a wrong character before deleting it
PAUSE = 0.45


def clamp_ttl(ttl):
    try:
        ttl = float(ttl)
    except (TypeError, ValueError):
        ttl = 5.0
    if math.isnan(ttl):
        ttl = 5.0
    return min(max(ttl, HOLD_MIN), HOLD_MAX)


def edge_target(depth, last, held_until, now, linger=LINGER):
    """1.0 = the control frame must be fully on, 0.0 = it may fade out."""
    if depth > 0 or now - last < linger or now < held_until:
        return 1.0
    return 0.0


def should_hide(now, last_active, ripples, ctrl_level, held_until, idle=20.0):
    """The overlay hides itself when idle - never while a hold is live."""
    return (now - last_active > idle and not ripples and ctrl_level == 0.0
            and now >= held_until)


def edit_steps(old, new, typo_at=None):
    """Every text state from `old` to `new`, one keystroke apart.

    Keeps the longest common start (a partial edit), backspaces the rest, then types the new
    tail. typo_at = an index into the typed tail where one wrong character is typed and
    deleted again. Every state starts with PREFIX, so it stays a comment."""
    if not new.startswith(PREFIX):
        raise ValueError("prompt text must be a comment line starting with %r" % PREFIX)
    if "\n" in new or "\r" in new:
        raise ValueError("prompt text must be a single line")
    states = []                                          # (text, seconds to wait after it)
    if not old.startswith(PREFIX) or "\n" in old:
        # empty / foreign text: the comment marker is set as ONE chunk, never typed - a lone
        # "/" would be a VEX syntax error for the cook in between
        old = PREFIX
        states.append((PREFIX, CHAR))
    k = 0
    while k < min(len(old), len(new)) and old[k] == new[k]:
        k += 1                                           # both start with PREFIX, so k >= 3
    cur = old
    while len(cur) > k:
        cur = cur[:-1]
        states.append((cur, BACKSPACE))
    tail = new[k:]
    for i, ch in enumerate(tail):
        if typo_at is not None and i == typo_at and ch.isalpha():
            wrong = "x" if ch.lower() != "x" else "z"
            states.append((cur + wrong, TYPO_FIX))
            states.append((cur, BACKSPACE))
        cur = cur + ch
        states.append((cur, CHAR))
    return states


def text_for(key, cycle):
    v = VARIANTS[key]
    return v[cycle % len(v)]


def build_cycle(cycle, current_texts):
    """The steps of demo cycle `cycle`. current_texts: {key: text in the field now}.

    Step kinds:
      focus  key            glide to the node, select it (Parameter pane shows it)
      type   key, states    per-character text states for its snippet
      api_move key, to      move the node by setPosition (NOT a native drag) to network position `to`
      wire   src, dst       connect src -> dst input 0
      unwire dst            drop dst input 0
      pause  seconds
    """
    layout = LAYOUTS[cycle % len(LAYOUTS)]
    steps = []
    if cycle > 0:
        steps += [{"kind": "unwire", "dst": "mood"}, {"kind": "unwire", "dst": "pose"}]
    steps.append({"kind": "api_move", "key": "camera", "to": layout["camera"]})
    prev = None
    for key in ORDER:
        if key != "camera":
            steps.append({"kind": "api_move", "key": key, "to": layout[key]})
            steps.append({"kind": "wire", "src": prev, "dst": key})
        new = text_for(key, cycle)
        typo = (len(new) - len(PREFIX)) // 3 if (cycle + ORDER.index(key)) % 2 == 0 else None
        steps.append({"kind": "focus", "key": key})
        steps.append({"kind": "type", "key": key,
                      "states": edit_steps(current_texts.get(key, ""), new, typo_at=typo)})
        current_texts[key] = new
        prev = key
    steps.append({"kind": "pause", "seconds": PAUSE * 2})
    return steps


GLIDE = 0.55           # a cursor glide (seconds, average)
DRAG = 0.9
WIRE = 0.9


def cycle_seconds(steps):
    """Rough playback time of a cycle (the storyboard clock)."""
    t = 0.0
    for s in steps:
        k = s["kind"]
        if k == "type":
            t += sum(w for _, w in s["states"])
        elif k == "focus":
            t += GLIDE + 0.2
        elif k == "api_move":
            t += GLIDE + DRAG
        elif k == "wire":
            t += GLIDE + WIRE
        elif k == "unwire":
            t += GLIDE + 0.2
        elif k == "pause":
            t += s["seconds"]
    return t
