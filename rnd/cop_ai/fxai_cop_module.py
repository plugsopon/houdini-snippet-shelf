"""FX AI Generate - PythonModule for the Copernicus HDA (RND, 2026-10-06).

Press Generate on the node and it will:
  1. write every wired input to $HIP/fxai_cop/<node>/in_<n>.png (read straight from the layer),
  2. build the prompt: the node's Prompt + the camera angle of any FX AI Angle node upstream,
  3. call Replicate in a background thread - Houdini keeps working while it runs,
  4. save the result to $HIP/fxai_cop/<node>/v###.png|mp4 and point the node's File COP at it.

Models: Seedream 5 Pro (image) and Seedance 2.5 (video, read back frame by frame).
The Replicate token is read from, in order: $REPLICATE_API_TOKEN,
~/.houdini_brother/replicate_token.txt, the Dremzo repo's .env.local. It is never printed.
"""
import base64
import json
import os
import threading
import time
import traceback
import urllib.request
import uuid

import hou

MODELS = {
    "seedream5": {"slug": "bytedance/seedream-5-pro", "kind": "image", "ext": ".png"},
    "seedance25": {"slug": "bytedance/seedance-2.5", "kind": "video", "ext": ".mp4"},
}
API = "https://api.replicate.com/v1"
ENV_FILE = os.environ.get("FXAI_ENV_FILE", "")   # optional: a .env file holding REPLICATE_API_TOKEN=
_running = {}           # node session id -> True while a job is in flight


# ------------------------------------------------------------------ token
def _token():
    t = os.environ.get("REPLICATE_API_TOKEN", "").strip()
    if t:
        return t
    p = os.path.join(os.path.expanduser("~"), ".houdini_brother", "replicate_token.txt")
    if os.path.isfile(p):
        t = open(p, encoding="utf8").read().strip()
        if t:
            return t
    if ENV_FILE and os.path.isfile(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf8"):
            if line.startswith("REPLICATE_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    raise hou.Error("No Replicate token: set REPLICATE_API_TOKEN or write it to "
                    "~/.houdini_brother/replicate_token.txt")


# ------------------------------------------------------------------ angle
# ------------------------------------------------------------------ prompt wrangles
def _is_prompt_node(n):
    """A Wrangle wired into FX AI Generate is a prompt, not an image."""
    return "wrangle" in n.type().name() and (n.parm("vexsnippet") or n.parm("snippet")) is not None


def prompt_text(n):
    """The Wrangle's snippet as prompt text. Plain text works (the Wrangle shows a VEX error, the
    generator doesn't care); writing it as // comment lines keeps the Wrangle error-free."""
    raw = (n.parm("vexsnippet") or n.parm("snippet")).eval()
    lines = []
    for line in raw.replace("/*", "").replace("*/", "").splitlines():
        line = line.strip()
        if line.startswith("//"):
            line = line[2:].strip()
        if line:
            lines.append(line)
    return " ".join(lines)


def _connections(node):
    return sorted(node.inputConnections(), key=lambda c: c.inputIndex())


def _image_connections(node):
    return [c for c in _connections(node) if not _is_prompt_node(c.inputNode())]


def _angle_nodes(node):
    """FX AI Angle nodes upstream of the first image input, nearest first."""
    imgs = _image_connections(node)
    out, seen, cur = [], set(), imgs[0].inputNode() if imgs else None
    while cur is not None and cur.sessionId() not in seen:
        seen.add(cur.sessionId())
        if "fxai_angle" in cur.type().name():
            out.append(cur)
        ins = [i for i in cur.inputs() if i is not None]
        cur = ins[0] if ins else None
    return out


def angle_text(a):
    """Camera wording for one FX AI Angle node (the Seedream 5 RND phrasing)."""
    az, el = a.evalParm("azimuth"), a.evalParm("elevation")
    dist = a.evalParm("distance")
    parts = []
    if abs(az) >= 1:
        side = "clockwise" if az > 0 else "counter-clockwise"
        parts.append("camera orbited %d degrees %s around the subject" % (abs(round(az)), side))
        if abs(az) >= 165:
            parts.append("we now see it from directly behind")
        elif abs(az) >= 110:
            parts.append("a rear three-quarter view")
        elif abs(az) >= 70:
            parts.append("a full side profile")
        elif abs(az) >= 20:
            parts.append("a three-quarter view")
    if abs(el) >= 1:
        parts.append("camera %s %d degrees %s eye level, %s" % (
            "raised" if el > 0 else "lowered", abs(round(el)), "above" if el > 0 else "below",
            "looking down at the subject" if el > 0 else "a hero low angle looking up"))
    if dist != "keep":
        parts.append({"close": "a close-up, the subject fills the frame",
                      "medium": "a medium shot",
                      "wide": "a wide shot, much more of the surroundings visible"}[dist])
    extra = a.evalParm("extra").strip()
    if extra:
        parts.append(extra)
    return "; ".join(parts)


def build_prompt(node):
    wired = [prompt_text(c.inputNode()) for c in _connections(node) if _is_prompt_node(c.inputNode())]
    p = " ".join([t for t in wired if t] + [node.evalParm("prompt").strip()]).strip()
    angles = [t for t in (angle_text(a) for a in reversed(_angle_nodes(node))) if t]
    if angles:
        p += (" Re-render this EXACT same scene and the EXACT same subject, photographed from a "
              "different camera position: " + "; then ".join(angles) + ". Keep the subject's identity "
              "perfectly: same proportions, same material, same label text. Photorealistic.")
    return p.strip()


def preview_prompt(kwargs):
    node = kwargs["node"]
    with hou.undos.disabler():
        node.parm("prompt_preview").set(build_prompt(node))


# ------------------------------------------------------------------ export inputs
def _job_dir(node):
    d = hou.text.expandString("$HIP/fxai_cop/%s" % node.name())
    os.makedirs(d, exist_ok=True)
    return d


def _write_png(layer, path):
    """Write a COP layer to an 8-bit sRGB PNG from its own pixels. Saving through rop_image is
    refused above 1920x1080 in Apprentice; reading the buffer is not."""
    import struct, zlib
    import numpy as np
    w, h = layer.bufferResolution()
    c = layer.channelCount()
    a = np.frombuffer(layer.allBufferElements(), dtype=np.float32).reshape(h, w, c)[::-1]   # bottom-up
    if c == 1:
        a = np.repeat(a, 3, axis=2)
    a = np.clip(a[:, :, :3], 0.0, 1.0)
    a = np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)       # linear -> sRGB
    px = (a * 255 + 0.5).astype(np.uint8)
    raw = b"".join(b"\x00" + px[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    return w, h


def _export_inputs(node, d):
    files = []
    for con in _image_connections(node):
        src = con.inputNode()
        lay = src.layer(con.outputIndex())
        if lay is None:
            raise hou.Error("Input %d (%s) has no image - does it cook?" % (con.inputIndex(), src.path()))
        path = os.path.join(d, "in_%d.png" % con.inputIndex()).replace("\\", "/")
        _write_png(lay, path)
        files.append(path)
    if not files:
        raise hou.Error("Wire an image in (a Wrangle counts as the prompt, not an image).")
    return files


# ------------------------------------------------------------------ http (background thread, no hou)
def _req(url, tok, data=None, headers=None, method=None):
    h = {"Authorization": "Bearer " + tok}
    h.update(headers or {})
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    with urllib.request.urlopen(r, timeout=180) as resp:
        return resp.read()


def _upload(path, tok):
    bnd = uuid.uuid4().hex
    body = (("--%s\r\nContent-Disposition: form-data; name=\"content\"; filename=\"%s\"\r\n"
             "Content-Type: image/png\r\n\r\n" % (bnd, os.path.basename(path))).encode()
            + open(path, "rb").read() + ("\r\n--%s--\r\n" % bnd).encode())
    j = json.loads(_req(API + "/files", tok, body, {"Content-Type": "multipart/form-data; boundary=" + bnd}))
    return j["urls"]["get"]


def _run(job, report):
    tok = _token()
    report("uploading %d image(s)..." % len(job["inputs"]))
    urls = [_upload(p, tok) for p in job["inputs"]]
    m = MODELS[job["model"]]
    if m["kind"] == "image":
        inp = {"prompt": job["prompt"], "image_input": urls, "size": job["size"],
               "aspect_ratio": "match_input_image"}
    else:
        inp = {"prompt": job["prompt"], "image": urls[0], "duration": job["duration"],
               "resolution": job["resolution"], "aspect_ratio": "adaptive"}
    if job["seed"] > 0:
        inp["seed"] = job["seed"]
    report("calling %s..." % m["slug"])
    t0 = time.time()
    p = json.loads(_req("%s/models/%s/predictions" % (API, m["slug"]), tok, json.dumps({"input": inp}).encode(),
                        {"Content-Type": "application/json", "Prefer": "wait=60"}))
    while p.get("status") in ("starting", "processing"):
        report("%s... %ds" % (p["status"], time.time() - t0))
        time.sleep(3)
        p = json.loads(_req(p["urls"]["get"], tok))
    if p.get("status") != "succeeded":
        raise RuntimeError("%s: %s" % (p.get("status"), str(p.get("error"))[:300]))
    url = p["output"][0] if isinstance(p["output"], list) else p["output"]
    report("downloading...")
    data = urllib.request.urlopen(url, timeout=300).read()
    with open(job["out"], "wb") as f:
        f.write(data)
    return time.time() - t0


# ------------------------------------------------------------------ main-thread updates
def _on_main(fn, *a):
    try:
        import hdefereval
        hdefereval.executeDeferred(lambda: fn(*a))
    except ImportError:          # hython: no event loop, just call it
        fn(*a)


def _set_status(node, text):
    try:
        with hou.undos.disabler():
            node.parm("status").set(text)
    except hou.ObjectWasDeleted:
        pass


def _finish(node, job, secs):
    try:
        with hou.undos.disabler():
            node.parm("result_file").set(job["out"])
            node.parm("is_video").set(MODELS[job["model"]]["kind"] == "video")
            log = json.loads(node.parm("history").eval() or "[]")
            log.append({"file": job["out"], "model": job["model"], "prompt": job["prompt"],
                        "secs": round(secs, 1), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            node.parm("history").set(json.dumps(log, indent=1))
            node.parm("status").set("done in %.0fs: %s" % (secs, os.path.basename(job["out"])))
        node.node("result").parm("reload").pressButton()
    except hou.ObjectWasDeleted:
        pass


# ------------------------------------------------------------------ the button
def generate(kwargs, blocking=False):
    node = kwargs["node"]
    sid = node.sessionId()
    if _running.get(sid):
        raise hou.Error("This node is already generating.")
    model = node.evalParm("model")
    d = _job_dir(node)
    inputs = _export_inputs(node, d)
    if MODELS[model]["kind"] == "video" and len(inputs) > 1:
        inputs = inputs[:1]                                  # Seedance takes one first frame
    n = 1
    while os.path.exists(os.path.join(d, "v%03d%s" % (n, MODELS[model]["ext"]))):
        n += 1
    job = {"model": model, "inputs": inputs, "prompt": build_prompt(node),
           "size": node.evalParm("size"), "resolution": node.evalParm("resolution"),
           "duration": int(node.evalParm("duration")), "seed": int(node.evalParm("seed")),
           "out": os.path.join(d, "v%03d%s" % (n, MODELS[model]["ext"])).replace("\\", "/")}
    with hou.undos.disabler():
        node.parm("prompt_preview").set(job["prompt"])

    def work():
        _running[sid] = True
        try:
            secs = _run(job, lambda s: _on_main(_set_status, node, s))
            _on_main(_finish, node, job, secs)
        except Exception as e:
            traceback.print_exc()
            _on_main(_set_status, node, "FAILED: %s" % e)
        finally:
            _running.pop(sid, None)

    if blocking:
        work()
    else:
        threading.Thread(target=work, daemon=True).start()
        _set_status(node, "started...")
