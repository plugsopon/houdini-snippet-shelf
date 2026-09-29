"""brother_whisper - local speech-to-text for the FX AI chat's mic button.

Runs in the SYSTEM Python (not Houdini's), as a long-lived worker the chat starts on first use, so
the model loads once. faster-whisper + large-v3-turbo on the GPU (CUDA libs from the
nvidia-cublas-cu12 / nvidia-cudnn-cu12 wheels), falling back to CPU int8. Nothing leaves the
machine.

Protocol (JSON lines):
  out  {"ready": true, "device": "cuda"}                         once the model is loaded
  in   {"wav": "C:/.../clip.wav", "prompt": "optional vocabulary"}
  out  {"ok": true, "text": "...", "lang": "th", "secs": 0.8}   or {"ok": false, "error": "..."}

Setup:  python -m pip install --target %USERPROFILE%/.houdini_brother/whisper faster-whisper ^
            nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
"""
import glob, json, os, site, sys, time

MODEL = os.environ.get("BROTHER_WHISPER_MODEL", "large-v3-turbo")
# installed with `pip install --target` here, NOT `--user`: a shell running inside the Claude
# desktop app (an MSIX package) has a virtualised %APPDATA%, so a --user install from it lands
# somewhere Houdini can never see. ~/.houdini_brother is outside AppData, so everyone sees it.
LIBS = os.path.join(os.path.expanduser("~"), ".houdini_brother", "whisper")


def _cuda_dlls():
    # the pip nvidia wheels put their DLLs in site-packages/nvidia/*/bin, which Windows won't find
    roots = [LIBS, site.getusersitepackages()] + list(site.getsitepackages())
    for r in roots:
        for d in glob.glob(os.path.join(r, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(d)
            except (OSError, AttributeError):
                pass
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _say(obj):
    # ASCII-escaped on purpose: a QProcess child's stdout is the Windows code page (cp1252), which
    # can't encode Thai - the first Thai transcript died with 'charmap' codec errors
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def main():
    # started from Houdini, the user site-packages (where pip --user put faster-whisper) can be
    # switched off by the inherited environment - put it back explicitly
    if os.path.isdir(LIBS):
        sys.path.insert(0, LIBS)
    us = site.getusersitepackages()
    if os.path.isdir(us) and us not in sys.path:
        sys.path.append(us)
    _cuda_dlls()
    from faster_whisper import WhisperModel
    model, device = None, None
    for dev, ct in (("cuda", "float16"), ("cpu", "int8")):
        try:
            model = WhisperModel(MODEL, device=dev, compute_type=ct)
            device = dev
            break
        except Exception as e:                      # no GPU / no CUDA libs: fall back
            last = e
    if model is None:
        _say({"ready": False, "error": str(last)}); return
    _say({"ready": True, "device": device, "model": MODEL})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            t = time.time()
            segs, info = model.transcribe(req["wav"], beam_size=5, vad_filter=True,
                                          initial_prompt=req.get("prompt") or None)
            text = "".join(s.text for s in segs).strip()
            _say({"ok": True, "text": text, "lang": info.language, "secs": round(time.time() - t, 2)})
        except Exception as e:
            _say({"ok": False, "error": str(e)})


if __name__ == "__main__":
    main()
