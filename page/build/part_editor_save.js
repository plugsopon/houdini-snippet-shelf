  // ---------------- editor ----------------
  function blankFile(){ return {id:uid("f"),title:"",lang:"python",context:"Python Shell",tested:"",filename:"",description:"",notes:"",code:"",visual:""}; }
  function openEditor(kind){
    var t = tech(state.tid), d;
    if (kind==="new") d = {kind:kind, tech:{id:uid("t"),name:"",category:"",type:"Sop",author:"Plug",versions:[]}, ver:{v:"v001",date:today(),notes:"",previewImage:"",previewVisual:"",files:[blankFile()]}};
    else if (kind==="newver"){ var base=clone(verOf(t)); base.v=nextV(t); base.date=today(); base.files.forEach(function(f){ f.id=uid("f"); }); d={kind:kind, tech:clone(t), ver:base}; }
    else d = {kind:kind, tech:clone(t), ver:clone(verOf(t))};
    state.draft = d; state.mode = "edit"; state.confirm = false; renderEditor();
  }
  function fileCard(f, i){
    var p = "f"+i+"-";
    return '<div class="card" data-idx="'+i+'"><div class="fhead"><h3>File '+(i+1)+'</h3><button class="btn small danger" type="button" data-rmfile="'+i+'">Remove file</button></div>'+
      '<div class="row">'+
        '<label for="'+p+'title">Title<input id="'+p+'title" data-k="title" value="'+esc(f.title)+'"></label>'+
        '<label for="'+p+'lang">Language<select id="'+p+'lang" data-k="lang"><option value="python"'+(f.lang==="python"?" selected":"")+'>Python</option><option value="vex"'+(f.lang==="vex"?" selected":"")+'>VEX</option></select></label>'+
        '<label for="'+p+'context">Where to paste<input id="'+p+'context" data-k="context" placeholder="Python Shell / Attribute Wrangle · Points" value="'+esc(f.context)+'"></label>'+
        '<label for="'+p+'tested">Tested on<input id="'+p+'tested" data-k="tested" placeholder="Houdini 21.0.671" value="'+esc(f.tested)+'"></label>'+
        '<label for="'+p+'filename">File name<input id="'+p+'filename" data-k="filename" placeholder="my_tool.py" value="'+esc(f.filename)+'"></label>'+
      '</div>'+
      '<label for="'+p+'description">What it does<textarea id="'+p+'description" data-k="description" rows="2">'+esc(f.description)+'</textarea></label>'+
      '<label for="'+p+'notes">Notes / gotchas<textarea id="'+p+'notes" data-k="notes" rows="2">'+esc(f.notes)+'</textarea></label>'+
      '<label for="'+p+'code">Code<textarea id="'+p+'code" data-k="code" class="code" spellcheck="false">'+esc(f.code)+'</textarea></label></div>';
  }
  function renderEditor(){
    var d = state.draft, t = d.tech, v = d.ver;
    var title = d.kind==="new" ? "New technique" : d.kind==="newver" ? "New version "+v.v+" of “"+t.name+"”" : "Edit “"+t.name+"” "+v.v;
    var cats = Array.from(new Set(DB.techniques.map(function(x){return x.category;}).filter(Boolean))).sort();
    $("main").innerHTML =
      '<form class="editor" id="edForm" novalidate>'+
        '<div class="dhead"><h2>'+esc(title)+'</h2></div>'+
        '<div class="card"><h3>Technique</h3><div class="row">'+
          '<label for="t-name">Name<input id="t-name" required value="'+esc(t.name)+'"></label>'+
          '<label for="t-cat">Category<input id="t-cat" list="t-cats" placeholder="Particles / Pyro / RBD…" value="'+esc(t.category)+'"><datalist id="t-cats">'+cats.map(function(c){return '<option value="'+esc(c)+'">';}).join("")+'</datalist></label>'+
          '<label for="t-type">Type<select id="t-type">'+TYPES.map(function(x){return '<option'+(x===t.type?" selected":"")+'>'+x+'</option>';}).join("")+'</select></label>'+
          '<label for="t-author">Author<input id="t-author" value="'+esc(t.author)+'"></label>'+
        '</div></div>'+
        '<div class="card"><h3>Version '+esc(v.v)+'</h3>'+
          '<label for="v-notes">Notes (อะไรเปลี่ยนใน version นี้ · วิธีใช้)<textarea id="v-notes" rows="4">'+esc(v.notes)+'</textarea></label>'+
          '<div class="drop" id="drop">'+
            (v.previewImage ? '<img src="/_blob/'+esc(v.previewImage)+'" alt="Preview">' : '<span>Preview: '+(v.previewVisual||"auto diagram / none")+'</span>')+
            (assetsApi ? '<label for="v-img" class="btn small" style="flex-direction:row">Choose image<input id="v-img" type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden></label><span>หรือกด Ctrl+V เพื่อ paste ภาพหน้าจอ</span>' : '<span>(ต้องเป็นเจ้าของหน้านี้ถึงจะอัปโหลดภาพได้)</span>')+
            (v.previewImage ? '<button class="btn small" type="button" id="rmImg">Remove image</button>' : '')+
          '</div>'+
        '</div>'+
        '<div id="files">'+v.files.map(fileCard).join("")+'</div>'+
        '<div><button class="btn" type="button" id="addFile">+ Add file</button></div>'+
        '<div class="formbar"><span class="status" id="edStatus">Save เผยแพร่หน้านี้เป็นเวอร์ชันใหม่</span>'+
          '<span class="actions"><button class="btn" type="button" id="cancelBtn">Cancel</button><button class="btn primary" type="submit" id="saveBtn">Save</button></span></div>'+
      '</form>';
    $("files").querySelectorAll("textarea.code").forEach(function(ta){
      ta.addEventListener("keydown", function(e){ if (e.key==="Tab" && !e.shiftKey){ e.preventDefault(); var a=ta.selectionStart,b=ta.selectionEnd; ta.value=ta.value.slice(0,a)+"    "+ta.value.slice(b); ta.selectionStart=ta.selectionEnd=a+4; } });
    });
    var imgInput = $("v-img");
    if (imgInput) imgInput.addEventListener("change", function(){ if (imgInput.files[0]) uploadPreview(imgInput.files[0]); });
    $("edForm").addEventListener("submit", function(e){ e.preventDefault(); commitDraft(); });
  }
  function readForm(){
    var d = state.draft;
    d.tech.name = $("t-name").value.trim(); d.tech.category = $("t-cat").value.trim();
    d.tech.type = $("t-type").value; d.tech.author = $("t-author").value.trim();
    d.ver.notes = $("v-notes").value.trim();
    $("files").querySelectorAll(".card").forEach(function(card){
      var f = d.ver.files[+card.dataset.idx];
      card.querySelectorAll("[data-k]").forEach(function(el){ f[el.dataset.k] = el.value; });
    });
  }
  function uploadPreview(file){
    if (!assetsApi) return;
    readForm();
    var st = $("edStatus"); st.className="status"; st.textContent="Uploading image…";
    assetsApi.upload(file).then(function(r){
      state.draft.ver.previewImage = r.id; renderEditor(); $("edStatus").textContent="Image attached — press Save to keep it.";
    }, function(err){
      var c = err && err.code;
      st.className="status err";
      st.textContent = c==="too_large" ? "Image is over 20 MB — use a smaller screenshot." : c==="unsupported_type" ? "Use a PNG, JPEG, WebP or GIF image." : "Upload failed ("+(c||"error")+").";
    });
  }
  function commitDraft(){
    readForm();
    var d = state.draft, st = $("edStatus");
    if (!d.tech.name){ st.className="status err"; st.textContent="Give the technique a name."; $("t-name").focus(); return; }
    d.ver.files = d.ver.files.map(function(f){ f.code = String(f.code||"").replace(/\s+$/,"") + "\n"; return f; });
    var next = clone(DB);
    var existing = next.techniques.find(function(x){return x.id===d.tech.id;});
    if (!existing){ d.tech.versions = [d.ver]; next.techniques.push(d.tech); }
    else {
      existing.name=d.tech.name; existing.category=d.tech.category; existing.type=d.tech.type; existing.author=d.tech.author;
      var i = existing.versions.findIndex(function(x){return x.v===d.ver.v;});
      if (i>=0) existing.versions[i]=d.ver; else existing.versions.push(d.ver);
    }
    save(next, d.tech.id, st, $("saveBtn"));
  }

  // ---------------- save (republish the whole page from data) ----------------
  function buildDoc(next){
    var json = JSON.stringify(next).replace(/</g,"\\u003c");
    var start = PRISTINE.indexOf('<script id="lib-data" type="application/json">');
    var open = PRISTINE.indexOf(">", start) + 1;
    var close = PRISTINE.indexOf("<\/script>", open);
    return PRISTINE.slice(0, open) + json + PRISTINE.slice(close);
  }
  function save(next, tid, statusEl, btn){
    if (!artifactApi) return;
    if (btn) btn.disabled = true;
    if (statusEl){ statusEl.className="status"; statusEl.textContent="Saving…"; }
    try { history.replaceState(null,"", tid ? "#"+tid : location.pathname); } catch(e){}
    artifactApi.publish(buildDoc(next)).then(function(){
      if (statusEl) statusEl.textContent = "Saved.";
    }, function(err){
      if (btn) btn.disabled = false;
      var code = err && err.code;
      var msg = code==="conflict" ? "A newer version was saved elsewhere — the page is reloading to it; redo this edit."
        : (code==="not_writer"||code==="not_granted") ? "You can view this shelf but not edit it."
        : "Could not save ("+(code||"error")+"). Try again.";
      if (statusEl){ statusEl.className="status err"; statusEl.textContent=msg; }
    });
  }

