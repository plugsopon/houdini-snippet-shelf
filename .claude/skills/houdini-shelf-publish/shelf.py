#!/usr/bin/env python3
"""Houdini Snippet Shelf data tool.

The shelf page keeps every technique in <script id="lib-data" type="application/json">.
This tool reads / changes that JSON without touching the rest of the page.

  python shelf.py list    PAGE.html
  python shelf.py diff    A.html B.html                 exit 1 if the data differs
  python shelf.py add     LIVE.html SPEC.json OUT.html  add a version (or a new technique)
  python shelf.py export  PAGE.html REPO_ROOT           write techniques/<name>/ (latest versions)

`add` always starts from LIVE.html (the artifact as it is published right now),
so edits made on the page itself are never lost. Every input is unwrapped from the
artifact service's page shell first. SPEC.json format: see SKILL.md.
"""
import datetime, json, os, re, shutil, sys

DATA_RX = re.compile(r'(<script id="lib-data" type="application/json">)(.*?)(</script>)', re.S)
FILE_KEYS = ("id", "title", "lang", "context", "tested", "filename", "description", "notes", "code", "visual")


SHELL_HEAD = "<!doctype html><html><head><meta charset=utf8>"


def read(path):
    return unwrap(open(path, encoding="utf8").read())


def unwrap(html):
    """An Artifact `read` returns the page inside the service's own shell
    (<!doctype html>...<style>...</style></head><body> ... </body></html>).
    The published source never has it - the service adds it on publish - so strip it,
    or every publish would nest one more shell."""
    if not html.startswith(SHELL_HEAD):
        return html
    body = html.index("<body>") + len("<body>")
    end = html.rstrip().rfind("</body></html>")
    if end < body:
        sys.exit("found the artifact shell's head but not its </body></html> - not stripping blindly")
    return html[body:end].strip("\r\n") + "\n"


def load(html):
    m = DATA_RX.search(html)
    if not m:
        sys.exit("no lib-data block found - is this the shelf page?")
    return json.loads(m.group(2))


def inject(html, data):
    # "<" must be escaped or a "</script>" inside a snippet would end the block early
    payload = json.dumps(data, ensure_ascii=False).replace("<", chr(92) + "u003c")
    assert "</script" not in payload
    out = DATA_RX.sub(lambda m: m.group(1) + payload + m.group(3), html, count=1)
    assert load(out) == data, "round-trip failed"
    return out


def folder_name(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name.replace("→", "to")).strip("_")


def cmd_list(page):
    for t in load(read(page))["techniques"]:
        v = t["versions"][-1]
        print("%-26s %-40s %-22s %s  files: %s" % (
            t["id"], t["name"], t["category"], ",".join(x["v"] for x in t["versions"]),
            ", ".join(f.get("filename", f["id"]) for f in v["files"])))


def cmd_diff(a, b):
    da, db = load(read(a)), load(read(b))
    if da == db:
        print("same data")
        return 0
    ta = {t["id"]: t for t in da["techniques"]}
    tb = {t["id"]: t for t in db["techniques"]}
    for k in sorted(set(ta) | set(tb)):
        if k not in ta:
            print("only in B:", k)
        elif k not in tb:
            print("only in A:", k)
        elif ta[k] != tb[k]:
            va = [v["v"] for v in ta[k]["versions"]]
            vb = [v["v"] for v in tb[k]["versions"]]
            print("differs:", k, "| A", va, "| B", vb)
    return 1


def next_v(versions):
    nums = [int(re.sub(r"\D", "", v["v"]) or 0) for v in versions]
    return "v%03d" % ((max(nums) if nums else 0) + 1)


def build_file(spec, base_dir):
    f = {k: spec.get(k, "") for k in FILE_KEYS if k != "code"}
    if "code_file" in spec:
        p = spec["code_file"] if os.path.isabs(spec["code_file"]) else os.path.join(base_dir, spec["code_file"])
        f["code"] = open(p, encoding="utf8").read()     # code files are never unwrapped
        f["filename"] = f["filename"] or os.path.basename(p)
    else:
        f["code"] = spec["code"]
    if not f["id"]:
        sys.exit("every file needs an id")
    return f


def cmd_add(live, spec_path, out):
    html = read(live)
    data = load(html)
    spec = json.load(open(spec_path, encoding="utf8"))
    base_dir = os.path.dirname(os.path.abspath(spec_path))
    tech = spec["technique"]
    found = [t for t in data["techniques"] if t["id"] == tech["id"]]
    if found:
        t = found[0]
        for k in ("name", "category", "type", "author"):     # allow renames, never blank them
            if tech.get(k):
                t[k] = tech[k]
    else:
        for k in ("name", "category", "type"):
            if not tech.get(k):
                sys.exit("new technique %r needs %s" % (tech["id"], k))
        t = {"id": tech["id"], "name": tech["name"], "category": tech["category"],
             "type": tech["type"], "author": tech.get("author", "Plug"), "versions": []}
        after = tech.get("insert_after")
        idx = next((i + 1 for i, x in enumerate(data["techniques"]) if x["id"] == after), len(data["techniques"]))
        data["techniques"].insert(idx, t)

    vs = spec["version"]
    v = vs.get("v") or "auto"
    if v == "auto":
        v = next_v(t["versions"])
    if any(x["v"] == v for x in t["versions"]):
        sys.exit("%s already has %s - pick another v or use auto" % (t["id"], v))

    prev = t["versions"][-1] if t["versions"] else None
    files = [dict(f) for f in prev["files"]] if (prev and vs.get("keep_previous_files", True)) else []
    for i, fs in enumerate(vs.get("files", [])):
        nf = build_file(fs, base_dir)
        j = next((k for k, f in enumerate(files) if f["id"] == nf["id"]), None)
        if j is not None:
            files[j] = nf                                    # replace by id, keep its position
        else:
            files.insert(fs.get("position", len(files)), nf)
    for rid in vs.get("remove_files", []):
        files = [f for f in files if f["id"] != rid]

    notes = vs.get("notes", "")
    if vs.get("append_previous_notes") and prev:
        notes = notes + "\n\n" + prev["notes"]
    t["versions"].append({
        "v": v, "date": vs.get("date") or datetime.date.today().isoformat(), "notes": notes,
        "previewImage": vs.get("previewImage", prev.get("previewImage", "") if prev else ""),
        "previewVisual": vs.get("previewVisual", prev.get("previewVisual", "") if prev else ""),
        "files": files})
    open(out, "w", encoding="utf8", newline="\n").write(inject(html, data))
    print("%s %s -> %s  (%d files: %s)" % (t["id"], v, out, len(files), ", ".join(f.get("filename") or f["id"] for f in files)))


def cmd_export(page, root):
    data = load(read(page))
    tdir = os.path.join(root, "techniques")
    os.makedirs(tdir, exist_ok=True)
    wanted = set()
    for t in data["techniques"]:
        v = t["versions"][-1]
        name = folder_name(t["name"])
        wanted.add(name)
        d = os.path.join(tdir, name)
        if os.path.isdir(d):
            shutil.rmtree(d)                                 # a file dropped from the latest version must disappear
        os.makedirs(d)
        lines = ["# " + t["name"], "",
                 "Category: %s · Type: %s · Latest: %s (%s)" % (t["category"], t["type"], v["v"], v["date"]),
                 "All versions: " + ", ".join(x["v"] for x in t["versions"]) + " (older versions live in the shelf page)",
                 "", "## Notes", "", v["notes"], "", "## Files", ""]
        for f in v["files"]:
            fn = f.get("filename") or (f["id"] + (".vfl" if f["lang"] == "vex" else ".py"))
            with open(os.path.join(d, fn), "w", encoding="utf8", newline="\n") as fh:
                fh.write(f["code"])
            lines += ["### %s — %s" % (fn, f["title"]), "", "- Where: " + f.get("context", ""),
                      "- Tested: " + f.get("tested", ""), "", f.get("description", ""), ""]
            if f.get("notes"):
                lines += [f["notes"], ""]
        with open(os.path.join(d, "README.md"), "w", encoding="utf8", newline="\n") as fh:
            fh.write("\n".join(lines))
    stale = sorted(set(os.listdir(tdir)) - wanted)
    print("exported %d techniques to %s" % (len(wanted), tdir))
    if stale:
        print("NOT in the page any more (left alone, delete by hand if intended):", ", ".join(stale))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("list", "diff", "add", "export"):
        sys.exit(__doc__)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf8")
    sys.exit({"list": lambda: cmd_list(*a[1:]), "diff": lambda: cmd_diff(*a[1:]),
              "add": lambda: cmd_add(*a[1:]), "export": lambda: cmd_export(*a[1:])}[a[0]]() or 0)
