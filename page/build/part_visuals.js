  // ---------------- diagrams (inline SVG, colours from theme tokens) ----------------
  function fig(body, caption){
    return '<figure class="visual"><div class="scroll">'+body+'</div>'+(caption?'<figcaption>'+caption+'</figcaption>':'')+'</figure>';
  }
  function network(nodes, wires, vw, vh){
    var W=170,H=40, byId={};
    nodes.forEach(function(n){ byId[n.id]=n; });
    function inPort(n,i){ var k=n.ins||1; return [n.x+W*(i+1)/(k+1), n.y]; }
    function outPort(n){ return [n.x+W/2, n.y+H]; }
    var g = wires.map(function(w){
      var a=outPort(byId[w[0]]), b=inPort(byId[w[1]], w[2]||0), dy=Math.max(30,(b[1]-a[1])*0.5);
      return '<path class="wire" d="M'+a[0]+' '+a[1]+' C'+a[0]+' '+(a[1]+dy)+' '+b[0]+' '+(b[1]-dy)+' '+b[0]+' '+b[1]+'"/>';
    }).join("");
    g += nodes.map(function(n){
      var ports='', k=n.ins||0;
      for (var i=0;i<k;i++){ var p=inPort(n,i); ports+='<circle class="port" cx="'+p[0]+'" cy="'+p[1]+'" r="3.5"/>'; }
      var o=outPort(n);
      return '<g class="node '+(n.cls||"")+'"><rect x="'+n.x+'" y="'+n.y+'" width="'+W+'" height="'+H+'" rx="5"/>'+
        '<rect class="flag" x="'+n.x+'" y="'+n.y+'" width="5" height="'+H+'" rx="2"/>'+
        '<text x="'+(n.x+14)+'" y="'+(n.y+17)+'" font-size="12.5" font-weight="500">'+esc(n.name)+'</text>'+
        '<text class="sub" x="'+(n.x+14)+'" y="'+(n.y+31)+'">'+esc(n.sub||"")+'</text>'+
        ports+'<circle class="port" cx="'+o[0]+'" cy="'+o[1]+'" r="3.5"/></g>';
    }).join("");
    return '<svg viewBox="0 0 '+vw+' '+vh+'" role="img" aria-label="Node network">'+g+'</svg>';
  }
  var VISUALS = {
    "rig-graph": function(){
      var nodes=[
        {id:"sim",  x:20,  y:14,  name:"SIM_NODE", sub:"live particles · every frame", cls:"io"},
        {id:"emit", x:300, y:14,  name:"EMITTER_NODE", sub:"optional · same space", cls:"io"},
        {id:"geo",  x:590, y:14,  name:"DEFORM_NODE", sub:"geometry in rest pose", cls:"io"},
        {id:"rest", x:20,  y:104, name:"follow_rest", sub:"timeshift → REST_FRAME", ins:1},
        {id:"info", x:300, y:104, name:"follow_sim_info", sub:"detail v@emitpos", ins:2},
        {id:"mark", x:110, y:194, name:"follow_mark_born", sub:"i@born · i@srcpt", ins:2},
        {id:"only", x:390, y:274, name:"follow_born_only", sub:"live points only", ins:1},
        {id:"fol",  x:110, y:354, name:"follow_live", sub:"closest live position", ins:3, cls:"key"},
        {id:"out",  x:110, y:434, name:"OUT_follow_live", sub:"deformed lattice", ins:1},
        {id:"pd",   x:470, y:434, name:"follow_pointdeform", sub:"geo · rest · deformed", ins:3},
        {id:"outd", x:470, y:514, name:"OUT_follow_deform", sub:"display", ins:1, cls:"key"}
      ];
      var wires=[["sim","rest",0],["sim","info",0],["emit","info",1],["rest","mark",0],["sim","mark",1],
        ["mark","only",0],["mark","fol",0],["info","fol",1],["only","fol",2],["fol","out",0],
        ["geo","pd",0],["rest","pd",1],["out","pd",2],["pd","outd",0]];
      return fig(network(nodes,wires,780,570),
        'สิ่งที่สคริปต์สร้าง: node สีฟ้าคือของที่พี่ชี้ path ใน CONFIG ส่วน node สีส้มคือตัวที่ทำงานหลักและตัวที่ต้องดูผล · inputs อยู่ขอบบน output อยู่ขอบล่าง แบบ Houdini');
    },
    "follow-concept": function(){
      var born=[[80,236],[120,214],[152,244],[100,184],[172,204],[140,164],[192,176],[210,144],[160,128],[265,148],[186,118],[232,190]];
      var unborn=[[232,104],[205,88],[255,78],[222,58],[270,112],[195,66]];
      var U=[240,106], h=42, emitNow=[600,262];
      function now(p){ return [400+p[0]*0.62+40, p[1]*0.42+150]; }
      function taken(p){
        var sx=0,sy=0,sw=0;
        born.forEach(function(b){ var d=Math.hypot(p[0]-b[0],p[1]-b[1])/h, w=Math.exp(-d*d); var n=now(b); sx+=n[0]*w; sy+=n[1]*w; sw+=w; });
        var wa=0.05; sx+=emitNow[0]*wa; sy+=emitNow[1]*wa; sw+=wa;
        return [sx/sw, sy/sw];
      }
      var near=born.filter(function(b){ return Math.hypot(U[0]-b[0],U[1]-b[1]) < h*1.6; });
      var s='<rect class="frame" x="10" y="26" width="370" height="252" rx="6"/><rect class="frame" x="410" y="26" width="370" height="252" rx="6"/>';
      s+='<text class="lbl" x="22" y="18">REST · frame 240 (timeshift)</text><text class="lbl" x="422" y="18">NOW · frame 40 (live sim)</text>';
      s+='<circle class="radius" cx="'+U[0]+'" cy="'+U[1]+'" r="'+(h*1.6)+'"/>';
      born.forEach(function(b){ s+='<circle class="'+(near.indexOf(b)>=0?"hot":"born")+'" cx="'+b[0]+'" cy="'+b[1]+'" r="5"/>'; });
      unborn.forEach(function(p){ s+='<circle class="unborn" cx="'+p[0]+'" cy="'+p[1]+'" r="5"/>'; });
      s+='<circle class="target" cx="'+U[0]+'" cy="'+U[1]+'" r="7"/>';
      s+='<text class="sub" x="'+(U[0]+12)+'" y="'+(U[1]-40)+'">Closest Radius</text><text class="sub" x="'+(U[0]+14)+'" y="'+(U[1]+4)+'">ยังไม่เกิด</text>';
      s+='<rect class="emit" x="'+(emitNow[0]-40)+'" y="'+(emitNow[1]-4)+'" width="80" height="8" rx="2"/><text class="sub" x="'+(emitNow[0]+46)+'" y="'+(emitNow[1]+4)+'">emitter</text>';
      born.forEach(function(b){ var n=now(b); s+='<circle class="'+(near.indexOf(b)>=0?"hot":"born")+'" cx="'+n[0].toFixed(1)+'" cy="'+n[1].toFixed(1)+'" r="5"/>'; });
      var T=taken(U);
      near.forEach(function(b){ var n=now(b); s+='<line class="pull" x1="'+n[0].toFixed(1)+'" y1="'+n[1].toFixed(1)+'" x2="'+T[0].toFixed(1)+'" y2="'+T[1].toFixed(1)+'"/>'; });
      unborn.forEach(function(p){ if(p===U) return; var t=taken(p); s+='<circle class="unborn" cx="'+t[0].toFixed(1)+'" cy="'+t[1].toFixed(1)+'" r="5"/>'; });
      s+='<circle class="target" cx="'+T[0].toFixed(1)+'" cy="'+T[1].toFixed(1)+'" r="7"/>';
      s+='<text class="sub" x="'+(T[0]+12).toFixed(1)+'" y="'+(T[1]-10).toFixed(1)+'">weighted avg ของเพื่อน</text>';
      s+='<circle class="born" cx="22" cy="300" r="5"/><text class="sub" x="32" y="304">เกิดแล้ว</text>'+
         '<circle class="hot" cx="102" cy="300" r="5"/><text class="sub" x="112" y="304">เพื่อนที่อยู่ในรัศมี</text>'+
         '<circle class="unborn" cx="232" cy="300" r="5"/><text class="sub" x="242" y="304">ยังไม่เกิด</text>'+
         '<circle class="target" cx="318" cy="300" r="6"/><text class="sub" x="330" y="304">พอยต์ที่กำลังดู</text>';
      return fig('<svg viewBox="0 0 790 316" role="img" aria-label="Unborn point borrows the current positions of its rest-layout neighbours">'+s+'</svg>',
        'ซ้าย: หาเพื่อนที่เกิดแล้วซึ่งอยู่ใกล้ในท่า rest (ภายในรัศมี) · ขวา: เอาตำแหน่งตอนนี้ของเพื่อนกลุ่มนั้นมาเฉลี่ยแบบ Gaussian (ตัวที่ใกล้กว่ามีน้ำหนักมากกว่า) บวก emitter เป็นตัวถ่วงเล็กน้อย · ภาพนี้คำนวณจากสูตรเดียวกับใน VEX');
    },
    "born-mask": function(opts){
      var ids=[0,1,2,3,4,5,6,7,8,9], live=[0,1,2,3,4,5];
      function row(label, cells, hl){ return '<tr'+(hl?' class="hl"':'')+'><th>'+label+'</th>'+cells.join("")+'</tr>'; }
      var r = row("rest id (frame 240)", ids.map(function(i){return '<td>'+i+'</td>';}));
      r += row("อยู่ในซิมตอนนี้?", ids.map(function(i){return live.indexOf(i)>=0?'<td class="y">✓</td>':'<td class="n">—</td>';}));
      r += row("i@born", ids.map(function(i){return '<td class="'+(live.indexOf(i)>=0?"y":"n")+'">'+(live.indexOf(i)>=0?1:0)+'</td>';}), !opts);
      r += row("i@srcpt", ids.map(function(i){var k=live.indexOf(i); return '<td class="'+(k>=0?"":"n")+'">'+(k>=0?k:-1)+'</td>';}));
      if (opts) r += row("born_only", ids.map(function(i){return live.indexOf(i)>=0?'<td class="y">keep</td>':'<td class="gone">'+i+'</td>';}), true);
      return fig('<table class="mask">'+r+'</table>', opts
        ? 'born_only ลบพอยต์ที่ i@born = 0 ทิ้ง เหลือแค่พาร์ติเคิลที่มีชีวิตเป็น point cloud ให้ pcfind ค้น ตัวอย่างนี้คือเฟรมที่ id 0–5 เกิดแล้ว'
        : 'ตัวอย่างเฟรมที่ id 0–5 เกิดแล้ว: idtopoint() หา id ในซิมตอนนี้ ถ้าเจอจะได้ index (i@srcpt) ถ้าไม่เจอได้ −1 จึงเป็น i@born = 0');
    },
    "patch-swap": function(){
      var s='<text class="lbl" x="20" y="18">BEFORE</text><text class="lbl" x="420" y="18">AFTER</text>';
      var nb=[{id:"a",x:20,y:30,name:"follow_mark_born",sub:"i@born · i@srcpt",ins:2},{id:"b",x:20,y:120,name:"follow_born_only",sub:"Blast · group @born==0",ins:1},{id:"c",x:20,y:210,name:"follow_live",sub:"input 2",ins:3}];
      var na=[{id:"a",x:420,y:30,name:"follow_mark_born",sub:"i@born · i@srcpt",ins:2},{id:"b",x:420,y:120,name:"follow_born_only",sub:"Wrangle · removepoint",ins:1,cls:"key"},{id:"c",x:420,y:210,name:"follow_live",sub:"input 2 (rewired)",ins:3}];
      var w=[["a","b",0],["b","c",2]];
      var strip=function(x){ return x.replace(/^<svg[^>]*>|<\/svg>$/g,""); };
      s+=strip(network(nb,w,380,260))+strip(network(na,w,380,260))+'<path class="pull" d="M230 140 L400 140"/><text class="sub" x="262" y="132">patch_born.py</text>';
      return fig('<svg viewBox="0 0 620 262" role="img" aria-label="Blast replaced by a wrangle">'+s+'</svg>',
        'patch หา node ชื่อ follow_born_only เปลี่ยนเป็น wrangle ที่ชื่อเดิม ตำแหน่งเดิม แล้วต่อสาย output กลับเข้า input เดิมให้ · ผลลัพธ์เหมือนเวอร์ชัน Blast ทุกพอยต์');
    }
  };
  VISUALS["born-only"] = function(){ return VISUALS["born-mask"](true); };

