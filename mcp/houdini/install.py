"""Install FX AI into Houdini - from wherever this repo was cloned. Run once, then restart Houdini.

    hython mcp/houdini/install.py            or in Houdini's Python Shell:
    exec(open(r"<repo>/mcp/houdini/install.py").read())

What it does, all inside your Houdini pref folder ($HOUDINI_USER_PREF_DIR, e.g. Documents/houdini21.0):
  packages/fx_ai.json         sets FXAI_HOME = this repo, and FXAI_PYTHON = a Python that has the
                              `mcp` package (for the houdini-live server). Nothing else in the
                              package: your HOUDINI_PATH is not touched.
  MainMenuCommon.xml          the FX AI menu (refuses to replace a different one - merge by hand)
  python_panels/fx_ai.pypanel the FX AI pane tab (New Pane Tab Type > FX AI)
  toolbar/fx_ai.shelf         the FX AI shelf
  python3.11libs/pythonrc.py  starts brother_link when Houdini opens (refuses to replace a different one)

None of the copied files holds a path: they find the repo through $FXAI_HOME. Move the repo?
Run this again. Re-running is safe; it says what it changed.
"""
import filecmp, json, os, shutil, subprocess, sys

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:                       # exec(open(...).read()) in the Python Shell has no __file__
    HERE = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else os.getcwd()
REPO = os.path.dirname(os.path.dirname(HERE))

# file in this folder -> where it goes under the pref folder; "own" = may replace a different copy
# only if that copy is one of ours (it mentions FX AI / brother_)
FILES = (("MainMenuCommon.xml", "MainMenuCommon.xml", "brother_ai_menu"),
         ("fx_ai.pypanel", os.path.join("python_panels", "fx_ai.pypanel"), "fx_ai_chat"),
         ("fx_ai.shelf", os.path.join("toolbar", "fx_ai.shelf"), "fxai_chat"),
         ("pythonrc.py", os.path.join("python3.11libs", "pythonrc.py"), "brother_link"))


def find_mcp_python():
    """A Python that can `import mcp` - the houdini-live server runs on it, not on Houdini's."""
    tries = []
    if os.environ.get("FXAI_PYTHON"):
        tries.append([os.environ["FXAI_PYTHON"]])
    tries += [["py", "-3.13"], ["py", "-3.12"], ["py", "-3"], ["python3"], ["python"]]
    # Houdini's own Python settings must not leak in: with PYTHONHOME/PYTHONPATH pointing at
    # Houdini's 3.11, another Python finds the wrong stdlib and packages (the MCP server runs
    # without them too - brother_chat strips them)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP")}
    for cmd in tries:
        try:
            # the real server module, from a neutral folder: run from the repo root, a bare
            # `import mcp` finds this repo's own mcp/ folder and wrongly succeeds
            out = subprocess.run(cmd + ["-c", "import mcp.server.fastmcp, sys; print(sys.executable)"],
                                 capture_output=True, text=True, timeout=20, env=env,
                                 cwd=os.path.expanduser("~"))
        except (OSError, subprocess.SubprocessError):
            continue
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip().splitlines()[-1]
    return None


def install(pref=None):
    import hou
    pref = pref or hou.homeHoudiniDirectory()
    done = []
    py = find_mcp_python()
    env = [{"FXAI_HOME": REPO.replace("\\", "/")}]
    if py:
        env.append({"FXAI_PYTHON": py.replace("\\", "/")})
    pkg = os.path.join(pref, "packages", "fx_ai.json")
    os.makedirs(os.path.dirname(pkg), exist_ok=True)
    with open(pkg, "w", encoding="utf8") as fh:
        json.dump({"env": env}, fh, indent=2)
    done.append(pkg)
    for name, rel, mark in FILES:
        src, dst = os.path.join(HERE, name), os.path.join(pref, rel)
        if os.path.exists(dst) and not filecmp.cmp(src, dst, shallow=False):
            with open(dst, encoding="utf8", errors="replace") as fh:
                ours = mark in fh.read()
            if not ours:
                print("SKIPPED %s - it already exists and is not FX AI's; merge it by hand." % dst)
                continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        done.append(dst)
    print("FX AI installed (FXAI_HOME = %s):" % REPO)
    for d in done:
        print("  " + d)
    if not py:
        print("No Python with the `mcp` package found: `pip install mcp`, then run this again "
              "(the chat works without it, but Claude can't see Houdini).")
    print("Restart Houdini.")
    return done


if __name__ == "__main__" or "hou" in dir():
    install()
