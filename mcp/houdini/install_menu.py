"""Put Brother's "AI" menu on Houdini's main menu bar.

Copies MainMenuCommon.xml (next to this file) into the user's Houdini pref folder
($HOUDINI_USER_PREF_DIR, e.g. Documents/houdini21.0), where Houdini merges it with its own menus.
Houdini reads menu files at START-UP: restart Houdini once after installing.

Refuses to overwrite a different MainMenuCommon.xml that is already there (that would delete
someone's own menu additions) - merge by hand in that case.

    hython install_menu.py        or, in Houdini's Python Shell:  exec(open(r"...install_menu.py").read())
"""
import filecmp, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else \
    r"P:\Project\Houdini Snippet Shelf\mcp\houdini"


def install():
    import hou
    src = os.path.join(HERE, "MainMenuCommon.xml")
    dst = os.path.join(hou.homeHoudiniDirectory(), "MainMenuCommon.xml")
    if os.path.exists(dst) and not filecmp.cmp(src, dst, shallow=False):
        raise RuntimeError("%s already exists and differs - merge Brother's <subMenu id=\"brother_ai_menu\"> "
                           "into it by hand instead of overwriting it." % dst)
    shutil.copyfile(src, dst)
    print("Installed %s - restart Houdini to see the AI menu." % dst)
    return dst


if __name__ == "__main__" or "hou" in dir():
    install()
