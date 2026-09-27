import sys, re, json
S = sys.argv[1]
live_t = open(sys.argv[2], encoding="utf8").read()
live = json.loads(re.search(r'<script id="lib-data" type="application/json">(.*?)</script>', live_t, re.S).group(1))
t = open(S + "/shelf5_template.html", encoding="utf8").read()
t = t.replace("/*__VISUALS__*/", open(S + "/part_visuals.js", encoding="utf8").read())
t = t.replace("/*__EDITOR__*/", open(S + "/part_editor_save.js", encoding="utf8").read())
m = re.search(r'(<script id="app-js">)(.*?)(</script>)', t, re.S)
t = t[:m.start(2)] + m.group(2).replace(" · ", ", ") + t[m.end(2):]
BS = chr(92)
payload = json.dumps(live, ensure_ascii=False).replace("<", BS + "u003c")
assert "</script" not in payload
t = t.replace("/*__DATA__*/", payload)
open(S + "/houdini-snippet-shelf.html", "w", encoding="utf8").write(t)
print("built with", len(live["techniques"]), "techniques", len(t))
