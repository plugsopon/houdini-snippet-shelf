"""FX AI - start brother_link whenever Houdini opens, so there is nothing to "connect".

Install: copy to $HOUDINI_USER_PREF_DIR/python3.11libs/pythonrc.py (Houdini runs every
pythonrc.py on its path at startup, alongside its own - unlike 123.py, this replaces nothing).
Silent (no Houdini Console pop-up). Localhost only, token-protected - see brother_link.py.
"""
try:
    import hou
    if hou.isUIAvailable():
        import hdefereval, sys

        def _fx_ai_link():
            p = r"P:\Project\Houdini Snippet Shelf\mcp\houdini"
            if p not in sys.path:
                sys.path.insert(0, p)
            try:
                import brother_link
                brother_link.start(quiet=True)
            except Exception as e:                 # never get in the way of Houdini starting
                print("FX AI: link not started (%s)" % e)

        hdefereval.executeDeferred(_fx_ai_link)
except Exception:
    pass
