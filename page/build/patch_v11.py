"""shelf5: Dremzo-style dropdowns (ChromeDropdown look) + bento technique tiles."""
p = "shelf5_template.html"
t = open(p, encoding="utf8").read()

def rep(a, b):
    global t
    assert t.count(a) == 1, ("not unique", a[:80], t.count(a))
    t = t.replace(a, b)

# ---------- CSS: pane-kind trigger + menu + field trigger ----------
start = t.index(".kind{appearance:none")
end = t.index(".phead .sp{")
t = t[:start] + """.kind{display:inline-flex;align-items:center;gap:6px;background:transparent;border:0;color:var(--ink-2);font:600 10.5px var(--f-ui);letter-spacing:.14em;text-transform:uppercase;padding:4px 7px 4px 6px;border-radius:7px}
.kind:hover,.kind[aria-expanded="true"]{background:rgba(255,255,255,.06);color:var(--ink)}
.chev{width:12px;height:12px;flex:none;color:var(--ink-3);transition:transform .2s}
[aria-expanded="true"]>.chev{transform:rotate(180deg)}
.pselect{display:flex;align-items:center;justify-content:space-between;gap:8px;min-width:120px;height:30px;justify-self:start;border:1px solid rgba(63,63,70,.6);background:rgba(24,24,27,.8);color:#f4f4f5;border-radius:8px;padding:0 10px;font:12.5px var(--f-ui);transition:border-color .15s,box-shadow .15s}
.pselect:hover{border-color:#52525b}
.pselect[aria-expanded="true"]{border-color:rgba(243,34,133,.7);box-shadow:0 0 0 2px rgba(243,34,133,.2)}
.dd-back{position:fixed;inset:0;z-index:60}
.dd-menu{position:fixed;z-index:61;background:#18181b;border-radius:16px;box-shadow:0 0 0 1px #27272a,0 20px 25px -5px rgba(0,0,0,.5),0 8px 10px -6px rgba(0,0,0,.5);padding:4px;overflow-y:auto;display:flex;flex-direction:column;gap:1px}
.dd-row{display:flex;align-items:center;gap:8px;width:100%;border:0;background:transparent;color:#e4e4e7;text-align:left;font:12.5px var(--f-ui);padding:7px 10px;border-radius:10px;cursor:pointer}
.dd-row:hover,.dd-row.hot{background:#27272a}
.dd-row[aria-selected="true"]{background:var(--pink);color:#fff}
.dd-row span{flex:1;min-width:0}
.dd-row svg{width:14px;height:14px;flex:none}
@media (prefers-reduced-motion:reduce){.chev{transition:none}}
""" + t[end:]

# ---------- CSS: bento tiles (at most half the old card size) ----------
start = t.index(".tcards{display:grid")
end = t.index("/* network view */")
t = t[:start] + """.tcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,124px));grid-auto-rows:92px;grid-auto-flow:dense;gap:10px;padding:12px;justify-content:start}
.tcard{position:relative;display:block;width:100%;height:100%;border-radius:14px;overflow:hidden;border:0;padding:0;background:#0C0F12;box-shadow:0 0 0 1px var(--line-2);text-align:left;transition:box-shadow .12s}
.tcard.w{grid-column:span 2}.tcard.h{grid-row:span 2}
.tcard:hover{box-shadow:0 0 0 2px #3C4652}
.tcard[aria-current="true"]{box-shadow:0 0 0 2px var(--pink)}
.tcard img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.tcard .ph{position:absolute;inset:0;display:grid;place-items:center;padding-bottom:22px;font:700 17px var(--f-ui);color:rgba(255,255,255,.88);letter-spacing:.05em;
  background-image:radial-gradient(rgba(255,255,255,.08) 1px,transparent 1.2px),linear-gradient(150deg,var(--tc) -50%,#0C0F12 75%);background-size:12px 12px,100% 100%}
.tcard.w.h .ph{font-size:24px}
.tcard .cap{position:absolute;left:0;right:0;bottom:0;padding:18px 9px 8px;background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.88) 55%);display:flex;flex-direction:column;gap:2px}
.tcard .cap b{font:600 11.5px/1.25 var(--f-ui);color:#fff;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tcard .cap span{font:10.5px/1.3 var(--f-ui);color:#AEB8C2;display:flex;gap:5px;align-items:center;white-space:nowrap;overflow:hidden}
.tcard .cap i{width:6px;height:6px;border-radius:50%;background:var(--tc);flex:none}
""" + t[end:]

# ---------- HTML: triggers ----------
rep("""'<select class="kind" data-kind="'+n.id+'" id="kind-'+n.id+'" aria-label="Pane type">'+KINDS.map(function(k){ return '<option value="'+k.kind+'"'+(k.kind===n.kind?' selected':'')+'>'+k.label+'</option>'; }).join("")+'</select>'+""",
    """'<button class="kind" type="button" data-kindmenu="'+n.id+'" aria-haspopup="listbox" aria-expanded="false" title="Change pane type">'+kindLabel(n.kind)+CHEV+'</button>'+""")
rep("""'<label for="pver-'+esc(t.id)+'">Version</label><select id="pver-'+esc(t.id)+'" data-pver="'+esc(t.id)+'">'+t.versions.map(function(x){ return '<option'+(x.v===v.v?' selected':'')+'>'+esc(x.v)+'</option>'; }).join("")+'</select>'+""",
    """'<label>Version</label><button class="pselect" type="button" data-vermenu="'+esc(t.id)+'" aria-haspopup="listbox" aria-expanded="false" aria-label="Version"><span>'+esc(v.v)+'</span>'+CHEV+'</button>'+""")

# bento spans: a repeating rhythm so the wall reads as a bento, not a list
rep("""      return '<div class="tcards">'+list.map(function(t){""",
    """      var SPAN = ["w h", "", "h", "", "w", "", "", "h"];
      return '<div class="tcards">'+list.map(function(t, i){""")
rep("""'<button class="tcard" type="button" data-pick="'+esc(t.id)+'" aria-current="'+(t.id===state.tid)+'" style="--tc:'+tc+'"><span class="art">'+art+'</span>'+""",
    """'<button class="tcard '+SPAN[i % SPAN.length]+'" type="button" data-pick="'+esc(t.id)+'" aria-current="'+(t.id===state.tid)+'" style="--tc:'+tc+'" title="'+esc(t.name)+'">'+art+""")

# ---------- JS: the menu ----------
rep("""  function paneHtml(n){""", """  var CHEV = '<svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CHECK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  function kindLabel(k){ return esc((KINDS.find(function(x){ return x.kind===k; })||{}).label || k); }

  // One popover menu, styled after Dremzo's ChromeDropdown: portalled to <body>,
  // left edge and min width locked to the trigger, pink selected row with a tick.
  var menu = null;
  function closeMenu(){
    if (!menu) return;
    menu.back.remove(); menu.el.remove();
    menu.anchor.setAttribute("aria-expanded", "false");
    var a = menu.anchor; menu = null;
    if (document.body.contains(a)) a.focus();
  }
  function openMenu(anchor, options, value, onPick){
    closeMenu();
    var back = document.createElement("div"); back.className = "dd-back";
    var el = document.createElement("div"); el.className = "dd-menu"; el.setAttribute("role", "listbox");
    el.innerHTML = options.map(function(o, i){
      var sel = o.value === value;
      return '<button type="button" class="dd-row'+(sel?' hot':'')+'" role="option" data-i="'+i+'" aria-selected="'+sel+'"><span>'+esc(o.label)+'</span>'+(sel?CHECK:'')+'</button>';
    }).join("");
    document.body.appendChild(back); document.body.appendChild(el);
    var r = anchor.getBoundingClientRect(), w = Math.max(r.width, 168);
    el.style.minWidth = w + "px";
    var left = Math.min(r.left, innerWidth - el.offsetWidth - 8);
    var below = innerHeight - r.bottom - 12, above = r.top - 12;
    var maxH = Math.min(320, Math.max(below, above));
    el.style.maxHeight = maxH + "px"; el.style.left = Math.max(8, left) + "px";
    if (below >= Math.min(el.offsetHeight, 200) || below >= above) el.style.top = (r.bottom + 6) + "px";
    else el.style.top = Math.max(8, r.top - 6 - Math.min(el.offsetHeight, maxH)) + "px";
    anchor.setAttribute("aria-expanded", "true");
    menu = {el:el, back:back, anchor:anchor};
    back.addEventListener("pointerdown", function(e){ e.preventDefault(); closeMenu(); });
    el.addEventListener("click", function(e){
      var row = e.target.closest(".dd-row"); if (!row) return;
      var o = options[+row.getAttribute("data-i")]; closeMenu(); onPick(o.value);
    });
    var rows = el.querySelectorAll(".dd-row"), cur = Math.max(0, options.findIndex(function(o){ return o.value===value; }));
    rows[cur].focus();
    el.addEventListener("keydown", function(e){
      if (e.key === "ArrowDown" || e.key === "ArrowUp"){
        e.preventDefault(); cur = (cur + (e.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length; rows[cur].focus();
      } else if (e.key === "Escape" || e.key === "Tab"){ e.preventDefault(); closeMenu(); }
    });
  }
  window.addEventListener("resize", closeMenu);
  document.addEventListener("scroll", function(e){ if (menu && !menu.el.contains(e.target)) closeMenu(); }, true);

  function paneHtml(n){""")

rep("""    var d = b.dataset;
    if (d.split){""", """    var d = b.dataset;
    if (d.kindmenu){
      var node = findNode(tree, d.kindmenu);
      if (menu && menu.anchor === b) { closeMenu(); return; }
      openMenu(b, KINDS.map(function(k){ return {value:k.kind, label:k.label}; }), node.kind, function(k){
        opKind(d.kindmenu, k); saveLayout(); renderDesk();
        var nb = document.querySelector('[data-kindmenu="'+d.kindmenu+'"]'); if (nb) nb.focus();
      });
      return;
    }
    if (d.vermenu){
      var tt0 = tech(d.vermenu); if (!tt0) return;
      if (menu && menu.anchor === b) { closeMenu(); return; }
      openMenu(b, tt0.versions.map(function(x){ return {value:x.v, label:x.v+(x.date?"   "+x.date:"")}; }), verOf(tt0).v, function(v){
        state.ver[d.vermenu]=v; state.confirm=false; state.fid=null; renderBodies();
      });
      return;
    }
    if (d.split){""")
rep("""    if (s.dataset && s.dataset.kind){ opKind(s.dataset.kind, s.value); saveLayout(); renderDesk(); return; }
    if (s.dataset && s.dataset.pver){ state.ver[s.dataset.pver]=s.value; state.confirm=false; state.fid=null; renderBodies(); }
""", "")

open(p, "w", encoding="utf8").write(t)
print("patched")
