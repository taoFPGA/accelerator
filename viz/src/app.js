/* app.js -- scene construction, animation, UI. Reads globals from data.js + content.js. */
(function(){
"use strict";
var RM = window.matchMedia && matchMedia("(prefers-reduced-motion:reduce)").matches;
var errEl = document.getElementById("err"), bootEl = document.getElementById("boot");
function fail(m){ errEl.style.display="block"; errEl.innerHTML=m; bootEl.style.display="none"; }
if(!window.THREE){ return fail("WebGL / three.js failed to load."); }

/* ======================================================================
   DATA  — distilled from architecture_data.json + architecture_data_accel.json
   (dump_arch.tcl over scripts/soc_build/post_route.dcp = the routed
    checkpoint behind exports/design.bit, Vivado 2025.2)
   ====================================================================== */

/* ======================================================================
   RENDERER / SCENE
   ====================================================================== */
var canvas = document.getElementById("view");
var renderer;
try{
  renderer = new THREE.WebGLRenderer({canvas:canvas, antialias:true, powerPreference:"high-performance"});
}catch(e){ return fail("Could not create a WebGL context."); }
var DPR = Math.min(devicePixelRatio||1, 1.8);
renderer.setPixelRatio(DPR);
renderer.outputEncoding = THREE.sRGBEncoding;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.02;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

var scene = new THREE.Scene();
scene.background = gradientTex("#0b0d11","#05060a");
scene.fog = new THREE.Fog(0x08090d, 34, 90);

var camera = new THREE.PerspectiveCamera(38, 2, 0.1, 500);
camera.position.set(0, 17, 20);

/* image-based lighting from a procedural room */
var HAS_ROOM = !!THREE.RoomEnvironment;
try{
  if(HAS_ROOM){
    var pmrem = new THREE.PMREMGenerator(renderer);
    var envRT = pmrem.fromScene(new THREE.RoomEnvironment(), 0.04);
    scene.environment = envRT.texture;
    pmrem.dispose();
  }
}catch(e){ HAS_ROOM = false; }

scene.add(new THREE.HemisphereLight(0x9fb4d6, 0x0a0c10, HAS_ROOM?0.22:0.7));
var key = new THREE.DirectionalLight(0xfff3e2, HAS_ROOM?1.7:2.6);
key.position.set(-11, 18, 9);
key.castShadow = true;
key.shadow.mapSize.set(2048,2048);
key.shadow.camera.near = 6; key.shadow.camera.far = 60;
key.shadow.camera.left=-22; key.shadow.camera.right=22; key.shadow.camera.top=22; key.shadow.camera.bottom=-22;
key.shadow.bias = -0.0004; key.shadow.radius = 4;
scene.add(key);
var fill = new THREE.DirectionalLight(0x7fa0d8, HAS_ROOM?0.35:0.7);
fill.position.set(12, 7, -12); scene.add(fill);

/* studio floor with soft contact shadow */
var floor = new THREE.Mesh(
  new THREE.PlaneGeometry(240,240),
  new THREE.MeshStandardMaterial({color:0x0c0e13, roughness:0.92, metalness:0.0})
);
floor.rotation.x = -Math.PI/2; floor.position.y = -3.4; floor.receiveShadow = true;
scene.add(floor);

/* ======================================================================
   MATERIALS (procedural PBR — CSP blocks external textures)
   ====================================================================== */
function gradientTex(a,b){
  var c=document.createElement("canvas"); c.width=4; c.height=256;
  var g=c.getContext("2d").createLinearGradient(0,0,0,256);
  g.addColorStop(0,a); g.addColorStop(1,b);
  var x=c.getContext("2d"); x.fillStyle=g; x.fillRect(0,0,4,256);
  var t=new THREE.CanvasTexture(c); t.needsUpdate=true; return t;
}
function noiseCanvas(size, base, spread){
  var c=document.createElement("canvas"); c.width=c.height=size;
  var x=c.getContext("2d"), im=x.createImageData(size,size), d=im.data;
  for(var i=0;i<d.length;i+=4){
    var n = base + (Math.random()-0.5)*spread;
    d[i]=d[i+1]=d[i+2]=Math.max(0,Math.min(255,n*255)); d[i+3]=255;
  }
  x.putImageData(im,0,0);
  return c;
}
function pcbMaterial(){
  var rc=noiseCanvas(256,0.62,0.18);
  var xr=rc.getContext("2d");
  // faint routed copper traces
  xr.strokeStyle="rgba(150,110,60,0.5)"; xr.lineWidth=2;
  for(var k=0;k<70;k++){
    var x0=Math.random()*256, y0=Math.random()*256, len=20+Math.random()*90;
    xr.beginPath(); xr.moveTo(x0,y0);
    if(Math.random()<0.5) xr.lineTo(x0+len,y0); else xr.lineTo(x0,y0+len);
    xr.stroke();
  }
  var rough=new THREE.CanvasTexture(rc); rough.wrapS=rough.wrapT=THREE.RepeatWrapping; rough.repeat.set(3,2);
  return new THREE.MeshStandardMaterial({color:0x0c3b2e, roughnessMap:rough, roughness:0.78, metalness:0.12, envMapIntensity:0.5});
}
function ceramicMaterial(){
  var r=new THREE.CanvasTexture(noiseCanvas(128,0.7,0.08));
  return new THREE.MeshStandardMaterial({color:0x9a9aa0, roughnessMap:r, roughness:0.82, metalness:0.05, envMapIntensity:0.7});
}
function brushedLid(){
  var c=document.createElement("canvas"); c.width=c.height=256; var x=c.getContext("2d");
  x.fillStyle="#7d8288"; x.fillRect(0,0,256,256);
  for(var i=0;i<2600;i++){ x.strokeStyle="rgba(255,255,255,"+(Math.random()*0.05)+")"; x.beginPath();
    var y=Math.random()*256; x.moveTo(0,y); x.lineTo(256,y+ (Math.random()-0.5)*3); x.stroke(); }
  var rmap=new THREE.CanvasTexture(c); rmap.wrapS=rmap.wrapT=THREE.RepeatWrapping;
  return new THREE.MeshStandardMaterial({color:0xb9bfc6, metalness:1.0, roughness:0.34, roughnessMap:rmap, envMapIntensity:1.0});
}
var GOLD = new THREE.MeshStandardMaterial({color:0xd9b45a, metalness:1.0, roughness:0.32, envMapIntensity:1.0});
function siliconMaterial(){
  return new THREE.MeshStandardMaterial({color:0x0a1a24, metalness:0.62, roughness:0.28, envMapIntensity:1.1});
}
/* fresnel sheen shell for the die (fake iridescence) */
function fresnelShell(geo, tint){
  var m = new THREE.ShaderMaterial({
    transparent:true, blending:THREE.AdditiveBlending, depthWrite:false, side:THREE.FrontSide,
    uniforms:{ uTint:{value:new THREE.Color(tint)}, uPow:{value:2.4}, uAmp:{value:0.55} },
    vertexShader:"varying vec3 vN; varying vec3 vV; void main(){ vec4 wp=modelMatrix*vec4(position,1.0); vN=normalize(mat3(modelMatrix)*normal); vV=normalize(cameraPosition-wp.xyz); gl_Position=projectionMatrix*viewMatrix*wp; }",
    fragmentShader:"uniform vec3 uTint; uniform float uPow; uniform float uAmp; varying vec3 vN; varying vec3 vV; void main(){ float f=pow(1.0-max(dot(vN,vV),0.0),uPow); vec3 sh=mix(uTint, vec3(0.4,0.75,1.0), f); gl_FragColor=vec4(sh*f*uAmp, f*uAmp); }"
  });
  return new THREE.Mesh(geo, m);
}
var KCOL = { stream:0xf0a755, ctrl:0x5f9be0, compute:0x33c7a6, hard:0xc56ba0, signal:0xeaf6ff, gold:0xd8b45c };
function kcol(k){ return KCOL[k]||KCOL.ctrl; }

/* ======================================================================
   GROUPS
   ====================================================================== */
var gBoard = new THREE.Group();     // package + PCB
var gFloor = new THREE.Group();     // silicon floorplan (Layer A)
var gLogic = new THREE.Group();     // logical pipeline (Layer B)
var gArray = new THREE.Group();     // systolic detail (lives in gLogic space near PE node)
scene.add(gBoard); scene.add(gFloor); scene.add(gLogic);

/* map SLICE-space (x:0..114, y:0..150) -> die plane (X:-DW/2..+, Z:-DZ/2..+).
   xc7z020 has a 2 x 3 clock-region grid (X0-1, Y0-2), 50 CLB rows per region. */
var DW = 10.2, DZ = 13.4;
function sx(x){ return (x/114 - 0.5)*DW; }
function sz(y){ return (0.5 - y/150)*DZ; }   // SLICE y up -> world -Z away
/* world centre of a clock region "X<c>Y<r>", matching the tile overlay below */
function regionCentre(rk){
  var cx = rk.charAt(1) === "1" ? DW/4 : -DW/4;
  var yr = rk.charAt(3);
  var cz = yr === "0" ? DZ/3 : yr === "2" ? -DZ/3 : 0;
  return [cx, cz];
}
var pickables = [];

/* ---------- BOARD & PACKAGE ---------- */
(function board(){
  var pcb = new THREE.Mesh(new THREE.BoxGeometry(17,0.34,12.6), pcbMaterial());
  pcb.position.y = -0.9; pcb.receiveShadow = true; pcb.castShadow = true;
  gBoard.add(pcb);
  // silkscreen hairline border
  var bd = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(16.2,0.36,11.8)),
    new THREE.LineBasicMaterial({color:0x2a5c4c}));
  bd.position.y=-0.9; gBoard.add(bd);

  // ceramic package body
  var pkg = new THREE.Mesh(new THREE.BoxGeometry(7.4,0.5,7.4), ceramicMaterial());
  pkg.position.y = -0.45; pkg.castShadow = true; pkg.receiveShadow = true;
  pkg.userData = {pick:"pkg"}; gBoard.add(pkg); pickables.push(pkg);
  // metal lid
  var lid = new THREE.Mesh(new THREE.BoxGeometry(5.9,0.36,5.9), brushedLid());
  lid.position.y = -0.06; lid.castShadow = true;
  lid.userData = {pick:"pkg"}; gBoard.add(lid); pickables.push(lid);
  var lidbev = new THREE.Mesh(new THREE.BoxGeometry(6.5,0.16,6.5),
    new THREE.MeshStandardMaterial({color:0x6c7176, metalness:1, roughness:0.5}));
  lidbev.position.y = -0.24; gBoard.add(lidbev);
  // laser-etch label on lid
  var lc=document.createElement("canvas"); lc.width=512; lc.height=256; var lx=lc.getContext("2d");
  lx.fillStyle="rgba(0,0,0,0)"; lx.fillRect(0,0,512,256);
  lx.fillStyle="rgba(20,22,24,0.9)"; lx.font="600 40px 'IBM Plex Mono',monospace"; lx.textAlign="center";
  lx.fillText("XC7Z020", 256, 120); lx.font="400 26px 'IBM Plex Mono',monospace";
  lx.fillText("CLG400-1", 256, 158);
  var lt=new THREE.CanvasTexture(lc);
  var lbl=new THREE.Mesh(new THREE.PlaneGeometry(3.6,1.8), new THREE.MeshBasicMaterial({map:lt,transparent:true,opacity:0.5}));
  lbl.rotation.x=-Math.PI/2; lbl.position.set(0,0.13,0); gBoard.add(lbl);

  // gold BGA contacts
  var ball = new THREE.SphereGeometry(0.055,10,8);
  var balls = new THREE.InstancedMesh(ball, GOLD, 24*24);
  var d=new THREE.Object3D(), bi=0;
  for(var i=0;i<24;i++)for(var j=0;j<24;j++){
    d.position.set((i-11.5)*0.3, -0.72, (j-11.5)*0.3); d.updateMatrix();
    balls.setMatrixAt(bi++, d.matrix);
  }
  balls.castShadow=false; gBoard.add(balls);

  // thin gold traces fanning off the package
  var tg = new THREE.MeshStandardMaterial({color:0xc9a24a, metalness:1, roughness:0.4});
  for(var t=0;t<40;t++){
    var w=0.03+Math.random()*0.03, len=1.2+Math.random()*3.4;
    var tr=new THREE.Mesh(new THREE.BoxGeometry(len,0.02,w), tg);
    var side=t%4, off=(Math.random()-0.5)*6;
    if(side===0){ tr.position.set(3.7+len/2,-0.73, off); }
    else if(side===1){ tr.position.set(-3.7-len/2,-0.73, off); }
    else if(side===2){ tr.rotation.y=Math.PI/2; tr.position.set(off,-0.73,3.7+len/2); }
    else { tr.rotation.y=Math.PI/2; tr.position.set(off,-0.73,-3.7-len/2); }
    gBoard.add(tr);
  }
})();

/* ---------- SILICON FLOORPLAN (Layer A) ---------- */
var floorBlocks = {};
var floorBbox = {};   // faint outline of each block's true (scattered) cell bbox
(function floorplan(){
  var die = new THREE.Mesh(new THREE.BoxGeometry(DW+0.5, 0.32, DZ+0.5), siliconMaterial());
  die.position.y = 0; die.castShadow = true; die.receiveShadow = true;
  gFloor.add(die);
  gFloor.add(fresnelShell(new THREE.BoxGeometry(DW+0.58,0.4,DZ+0.58), 0x123a4a));

  // clock-region tiles: 2 cols x 3 rows, gold hairline borders + labels
  for(var cx=0;cx<2;cx++)for(var cy=0;cy<3;cy++){
    var w=DW/2, h=DZ/3;
    var tile = new THREE.Mesh(new THREE.PlaneGeometry(w-0.12,h-0.12),
      new THREE.MeshBasicMaterial({color:0x0e2630, transparent:true, opacity:0.35}));
    tile.rotation.x=-Math.PI/2;
    tile.position.set((cx-0.5)*w, 0.17, (1-cy)*h);
    gFloor.add(tile);
    var eg=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(w-0.12,h-0.12)),
      new THREE.LineBasicMaterial({color:0x7a6a3a, transparent:true, opacity:0.55}));
    eg.rotation.x=-Math.PI/2; eg.position.copy(tile.position); gFloor.add(eg);
    gFloor.add(textSprite("X"+cx+"Y"+cy, 0.5, "#c8b06a",
      (cx-0.5)*w - w/2 + 0.35, 0.2, (1-cy)*h - h/2 + 0.3, true));
  }

  // This design has no floorplan constraints -- the placer scatters every
  // module across the die. So position each block at its clock-region-weighted
  // cell centroid (where its logic actually clusters), size it by cell count
  // (how much logic), and keep the true scattered bbox as a faint outline
  // that lights up on selection.
  Object.keys(N).forEach(function(id){
    var b=N[id];
    var wx=0, wz=0, tot=0;
    for(var rk in b.cr){ var c=b.cr[rk]||0; var rc=regionCentre(rk); wx+=rc[0]*c; wz+=rc[1]*c; tot+=c; }
    var cxw = tot>0 ? wx/tot : sx((b.bbox[0]+b.bbox[2])/2);
    var czw = tot>0 ? wz/tot : sz((b.bbox[1]+b.bbox[3])/2);

    var cells = b.lut + b.ff*0.6 + b.dsp*40 + b.bram*110;
    var fp  = Math.max(0.7, Math.min(3.0, Math.sqrt(cells)/24));
    var bw  = b.big ? DW-0.6 : fp;
    var bd  = b.big ? DZ-0.6 : fp;
    var hgt = b.big ? 0.5 : Math.max(0.3, Math.min(3.2, Math.sqrt(cells)/20));

    var mat = new THREE.MeshStandardMaterial({
      color:kcol(b.kind), roughness:0.42, metalness:0.25,
      transparent:b.big, opacity:b.big?0.13:1,
      emissive:kcol(b.kind), emissiveIntensity:b.big?0.03:0.12
    });
    var box = new THREE.Mesh(new THREE.BoxGeometry(bw, hgt, bd), mat);
    box.position.set(cxw, 0.16 + hgt/2, czw);
    box.castShadow=!b.big; box.receiveShadow=true;
    box.userData={pick:"soc", id:id};
    box.add(new THREE.LineSegments(new THREE.EdgesGeometry(box.geometry),
      new THREE.LineBasicMaterial({color:kcol(b.kind), transparent:true, opacity:b.big?0.4:0.3})));
    gFloor.add(box); floorBlocks[id]=box;
    if(!b.big) pickables.push(box);

    // true cell bbox, drawn flat on the die, hidden until selected
    var obw = Math.max(0.3,(b.bbox[2]-b.bbox[0])/114*DW);
    var obd = Math.max(0.3,(b.bbox[3]-b.bbox[1])/150*DZ);
    var out = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(obw,obd)),
      new THREE.LineBasicMaterial({color:kcol(b.kind), transparent:true, opacity:0}));
    out.rotation.x = -Math.PI/2;
    out.position.set(sx((b.bbox[0]+b.bbox[2])/2), 0.2, sz((b.bbox[1]+b.bbox[3])/2));
    out.userData.noPick = true;
    gFloor.add(out); floorBbox[id]=out;

    if(fp>1.0 || b.big){
      gFloor.add(textSprite(b.big ? "transformer_block_axi · 16×16"
                                  : b.name.replace(/^design_1_i\//,"").replace(/_0$/,""),
        b.big?0.62:0.42, "#dfe6f0", cxw, 0.2 + (b.big?0.7:hgt+0.35), czw, true));
    }
  });
  gFloor.add(textSprite("unconstrained placement — box = clock-region centroid + logic size · click for the true cell bbox",
    0.34, "#8a93a6", 0, 0.05, DZ/2 + 1.0, true));
})();

/* ---------- LOGICAL PIPELINE (Layer B) ---------- */
var logicNodes = {};
/* lane = [column 0..8, track]  track: 0=control rail · 1=PS · 2=main data path · 3=second feed */
function lanePos(l){
  var x = (l[0]-4)*2.35;
  var z = ({0:-3.0, 1:0.9, 2:0.0, 3:2.6})[l[1]];
  if(z===undefined) z = 0;
  return new THREE.Vector3(x, 0.55, z);
}
(function logic(){
  var grid = new THREE.GridHelper(38, 38, 0x1a2230, 0x141a26);
  grid.position.y = -0.02; gLogic.add(grid);

  Object.keys(N).forEach(function(id){
    var b=N[id];
    var s = b.big ? [2.4,1.5,2.4] : b.kind==="hard" ? [1.7,1.9,2.2] : [1.5,1.0,1.5];
    var m = new THREE.MeshStandardMaterial({color:0x11151d, roughness:0.5, metalness:0.3,
      emissive:kcol(b.kind), emissiveIntensity:0.16});
    var mesh = new THREE.Mesh(new THREE.BoxGeometry(s[0],s[1],s[2]), m);
    var lp = lanePos(b.lane); mesh.position.copy(lp);
    mesh.castShadow=true; mesh.receiveShadow=true;
    mesh.userData={pick:"soc", id:id};
    var eg = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),
      new THREE.LineBasicMaterial({color:kcol(b.kind), transparent:true, opacity:0.6}));
    mesh.add(eg);
    gLogic.add(mesh); logicNodes[id]=mesh; pickables.push(mesh);
    gLogic.add(textSprite(b.name.replace(/^design_1_i\//,"").replace(/_0$/,""), 0.42, "#dfe6f0",
      lp.x, lp.y + s[1]/2 + 0.4, lp.z, true));
  });
})();

/* ---------- post-MatMul pipeline: downsizer -> Softmax -> upsizer -> GELU
   (real, placed & routed in this bitstream) ---------- */
var gGhost = new THREE.Group(); gGhost.visible = false; gLogic.add(gGhost);
var ghostNodes = {}, ghostCurves = [];
(function pipe(){
  var startX = lanePos(N.mm.lane).x;   // continues east off the accelerator
  var pts = [ new THREE.Vector3(startX, 0.55, 0) ];
  GHOST.order.forEach(function(id, i){
    var g = GHOST[id];
    var x = startX + 3.4 + i*2.5;
    var s = [1.5, 0.95, 1.5];
    var col = kcol(g.kind);
    var mat = new THREE.MeshStandardMaterial({ color:0x11151d, roughness:0.5, metalness:0.3,
      emissive:col, emissiveIntensity:0.16 });
    var mesh = new THREE.Mesh(new THREE.BoxGeometry(s[0],s[1],s[2]), mat);
    mesh.position.set(x, 0.55, 0);
    mesh.castShadow = true;
    mesh.userData = {pick:"ghost", id:id};
    mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry),
      new THREE.LineBasicMaterial({color:col, transparent:true, opacity:0.6})));
    gGhost.add(mesh); ghostNodes[id]=mesh; pickables.push(mesh);
    gGhost.add(textSprite(g.name, 0.4, "#dfe6f0", x, 0.55 + s[1]/2 + 0.4, 0, true));
    pts.push(new THREE.Vector3(x, 0.55, 0));
  });
  gGhost.add(textSprite("MatMul → LayerNorm → Softmax → GELU  ·  one 100 MHz domain", 0.36, "#9aa4b2",
    startX + 3.4 + 1.5*2.5, 1.9, 0, true));
  for(var i=0;i<pts.length-1;i++){
    var a=pts[i], b=pts[i+1];
    var m=a.clone().add(b).multiplyScalar(0.5); m.y += 0.7;
    var c=new THREE.CatmullRomCurve3([a,m,b]);
    ghostCurves.push(c);
    var tube=new THREE.Mesh(new THREE.TubeGeometry(c,30,0.028,6,false),
      new THREE.MeshBasicMaterial({color:KCOL.stream, transparent:true, opacity:0.4}));
    gGhost.add(tube);
  }
})();
var ghostPk = new THREE.InstancedMesh(
  new THREE.IcosahedronGeometry(0.05,0),
  new THREE.MeshBasicMaterial({color:KCOL.signal, toneMapped:false, transparent:true, opacity:0.95}),
  ghostCurves.length*3);
ghostPk.frustumCulled=false; ghostPk.count=0; gGhost.add(ghostPk);
var ghostT = 0;

/* ---------- edges + illuminated pulses (shared between layers) ---------- */
var curvesFloor = [], curvesLogic = [], streamsRT = [];
function buildEdges(){
  EDGES.forEach(function(e){
    var A=N[e[0]], B=N[e[1]];
    // floor curve
    var a1=new THREE.Vector3(floorBlocks[e[0]].position.x, 0.3, floorBlocks[e[0]].position.z);
    var b1=new THREE.Vector3(floorBlocks[e[1]].position.x, 0.3, floorBlocks[e[1]].position.z);
    var m1=a1.clone().add(b1).multiplyScalar(0.5); m1.y += (e[2]==="stream"?2.0:1.1)+a1.distanceTo(b1)*0.06;
    var c1=new THREE.CatmullRomCurve3([a1,m1,b1]);
    // logic curve
    var a2=lanePos(A.lane).clone(), b2=lanePos(B.lane).clone();
    var m2=a2.clone().add(b2).multiplyScalar(0.5); m2.y += (e[2]==="stream"?1.6:0.9);
    var c2=new THREE.CatmullRomCurve3([a2,m2,b2]);

    var col = e[2]==="stream"?KCOL.stream:KCOL.ctrl;
    var rad = e[2]==="stream"? 0.03 + e[3]/128*0.05 : 0.016;
    var tubeF = new THREE.Mesh(new THREE.TubeGeometry(c1,50,rad,7,false),
      new THREE.MeshBasicMaterial({color:col, transparent:true, opacity:e[2]==="stream"?0.4:0.24}));
    var tubeL = new THREE.Mesh(new THREE.TubeGeometry(c2,50,rad,7,false),
      new THREE.MeshBasicMaterial({color:col, transparent:true, opacity:e[2]==="stream"?0.4:0.24}));
    tubeL.userData={edgeTube:true};
    gFloor.add(tubeF); gLogic.add(tubeL);
    curvesFloor.push({c:c1,e:e,tube:tubeF}); curvesLogic.push({c:c2,e:e,tube:tubeL});

    streamsRT.push({
      from:e[0], to:e[1], kind:e[2], bits:e[3],
      rate: e[2]==="stream" ? 0.11 + e[3]/128*0.16 : 0.24,
      spawn: e[2]==="stream" ? (0.5 + e[3]/40) : 1.1,
      acc: Math.random()*3, pk: [], col:col
    });
  });
}
buildEdges();

var PKMAX = 1400;
var pkGeo = new THREE.IcosahedronGeometry(0.055, 0);
var pkMat = new THREE.MeshBasicMaterial({transparent:true, toneMapped:false});
var pkMesh = new THREE.InstancedMesh(pkGeo, pkMat, PKMAX);
pkMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
pkMesh.count = 0; pkMesh.frustumCulled = false;
scene.add(pkMesh);
var _M=new THREE.Matrix4(), _Q=new THREE.Quaternion(), _S=new THREE.Vector3(), _P=new THREE.Vector3(), _C=new THREE.Color();
if(RM){ streamsRT.forEach(function(s){ s.pk=[0.2,0.5,0.8]; }); }

/* ======================================================================
   SYSTOLIC ARRAY DETAIL (built once, parented under the PE node)
   ====================================================================== */
var GN = ACC.cols, AW = 7.6, cell = AW/GN;
var peMesh, peBase=[], peIsDsp=[], arrCenter=new THREE.Vector3();
var flowW, flowA, flowS, wf = {cycle:0, frac:0};
(function systolic(){
  var host = logicNodes.mm;
  arrCenter.copy(host.position);
  gArray.position.copy(arrCenter);
  gLogic.add(gArray);

  // DSP distribution per line: real per-row DSP counts from the netlist,
  // spread evenly across the row (exact per-(i,j) placement isn't extracted).
  for(var r=0;r<ACC.rows;r++){
    var row=[], n=ACC.dspPerLine[r]|0;
    if(n<=0){ for(var c0=0;c0<GN;c0++) row.push(0); }
    else if(n>=GN){ for(var c1=0;c1<GN;c1++) row.push(1); }
    else {
      var stride=GN/n, nxt=0;
      for(var c=0;c<GN;c++){ if(c>=nxt){ row.push(1); nxt+=stride; } else row.push(0); }
    }
    peIsDsp.push(row);
  }
  var g = new THREE.BoxGeometry(cell*0.72, 1, cell*0.72);
  var m = new THREE.MeshStandardMaterial({roughness:0.42, metalness:0.35});
  peMesh = new THREE.InstancedMesh(g, m, GN*ACC.rows);
  peMesh.castShadow = true;
  var d=new THREE.Object3D(), idx=0;
  for(var r2=0;r2<ACC.rows;r2++)for(var c2=0;c2<GN;c2++){
    var dsp = peIsDsp[r2][c2];
    var x=(c2-(GN-1)/2)*cell, z=(r2-(ACC.rows-1)/2)*cell, h=dsp?0.6:0.16;
    d.position.set(x, h/2, z); d.scale.set(1,h,1); d.updateMatrix();
    peMesh.setMatrixAt(idx, d.matrix);
    var base = dsp ? new THREE.Color(KCOL.compute) : new THREE.Color(0x1c2732);
    peBase.push(base); peMesh.setColorAt(idx, base); idx++;
  }
  peMesh.instanceColor.needsUpdate = true;
  peMesh.userData = {pick:"pe"};
  gArray.add(peMesh); pickables.push(peMesh);
  gArray.add(new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(AW+cell,0.02,AW+cell)),
    new THREE.LineBasicMaterial({color:KCOL.compute, transparent:true, opacity:0.32})));

  // staging buffers
  function bram(count, per, zc, color, id){
    var grp=new THREE.Group(); grp.userData={pick:"pe", id:id};
    var rows=Math.ceil(count/per), sw=AW/per*0.84, sh=0.4, sd=0.44;
    var mm=new THREE.MeshStandardMaterial({color:color, roughness:0.4, metalness:0.2,
      emissive:color, emissiveIntensity:0.14});
    for(var i=0;i<count;i++){
      var cx=i%per, cz=Math.floor(i/per);
      var b=new THREE.Mesh(new THREE.BoxGeometry(sw,sh,sd), mm);
      b.position.set((cx-(per-1)/2)*(AW/per), sh/2, zc + cz*(sd+0.12)*(zc<0?-1:1));
      b.castShadow=true; grp.add(b);
    }
    return grp;
  }
  var inb = bram(29,15, -(AW/2)-1.0, new THREE.Color(KCOL.stream), "inbuf");
  var outb = bram(38,19, (AW/2)+1.0, new THREE.Color(KCOL.compute), "outbuf");
  gArray.add(inb); gArray.add(outb); pickables.push(inb, outb);
  gArray.add(textSprite("MM_in_buffer · 29×RAMB36", 0.5, "#f0c89a", 0, 1.1, -(AW/2)-2.1, true));
  gArray.add(textSprite("MM_out_buffer · 37.5 RAMB36", 0.5, "#9fe9d6", 0, 1.1, (AW/2)+2.4, true));
  gArray.add(textSprite("PE_array — weights ↓  activations →  Σ ↑   (idealized systolic schedule)", 0.44, "#aab4c2", 0, 2.4, 0, true));

  function flow(n, geo, color){
    var im=new THREE.InstancedMesh(geo, new THREE.MeshBasicMaterial({color:color, toneMapped:false}), n);
    im.count=0; im.instanceMatrix.setUsage(THREE.DynamicDrawUsage); im.frustumCulled=false;
    gArray.add(im); return {im:im, list:[], acc:0};
  }
  flowW = flow(GN*4, new THREE.BoxGeometry(cell*0.26,cell*0.26,cell*0.5), KCOL.stream);
  flowA = flow(ACC.rows*4, new THREE.BoxGeometry(cell*0.5,cell*0.26,cell*0.26), 0xbcd2ff);
  flowS = flow(GN*3, new THREE.OctahedronGeometry(cell*0.22,0), KCOL.signal);

  gArray.visible = false;
})();

/* ======================================================================
   TEXT SPRITE helper
   ====================================================================== */
function textSprite(text, worldH, color, x,y,z, billboard){
  var pad=10, f=32;
  var c=document.createElement("canvas"), t=c.getContext("2d");
  t.font="500 "+f+"px 'IBM Plex Mono', monospace";
  c.width = Math.ceil(t.measureText(text).width)+pad*2;
  c.height = f+pad*2;
  t=c.getContext("2d");
  t.font="500 "+f+"px 'IBM Plex Mono', monospace";
  t.fillStyle="rgba(8,10,14,0.66)"; rr(t,0,0,c.width,c.height,8); t.fill();
  t.fillStyle=color; t.textBaseline="middle"; t.fillText(text, pad, c.height/2+1);
  var tex=new THREE.CanvasTexture(c); tex.anisotropy=2;
  var sp=new THREE.Sprite(new THREE.SpriteMaterial({map:tex, transparent:true, depthWrite:false, depthTest:true}));
  sp.scale.set(c.width/c.height*worldH, worldH, 1);
  sp.position.set(x,y,z);
  sp.userData.noPick=true;
  return sp;
}
function rr(c,x,y,w,h,r){c.beginPath();c.moveTo(x+r,y);c.arcTo(x+w,y,x+w,y+h,r);c.arcTo(x+w,y+h,x,y+h,r);c.arcTo(x,y+h,x,y,r);c.arcTo(x,y,x+w,y,r);c.closePath();}

/* ======================================================================
   POST-PROCESSING (guarded)
   ====================================================================== */
var USE_POST = !!(THREE.EffectComposer && THREE.RenderPass && THREE.ShaderPass && THREE.UnrealBloomPass);
var composer, bloomPass, smaaPass;
if(USE_POST){
  try{
    composer = new THREE.EffectComposer(renderer);
    composer.addPass(new THREE.RenderPass(scene, camera));
    bloomPass = new THREE.UnrealBloomPass(new THREE.Vector2(innerWidth,innerHeight), 0.62, 0.7, 0.72);
    composer.addPass(bloomPass);
    if(THREE.SMAAPass){
      smaaPass = new THREE.SMAAPass(innerWidth*DPR, innerHeight*DPR);
      composer.addPass(smaaPass);
    }
    var last = composer.passes[composer.passes.length-1];
    last.renderToScreen = true;
  }catch(e){ USE_POST=false; }
}

/* ======================================================================
   CONTROLS
   ====================================================================== */
var controls, fallbackOrbit=null;
if(THREE.OrbitControls){
  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = 5; controls.maxDistance = 70;
  controls.maxPolarAngle = Math.PI*0.495;
  controls.target.set(0,0.4,0);
} else {
  var sp2={r:26,th:0.7,ph:0.95,t:new THREE.Vector3(0,0.4,0)};
  fallbackOrbit = sp2;
  function fbApply(){ camera.position.set(sp2.t.x+sp2.r*Math.sin(sp2.ph)*Math.sin(sp2.th),
    sp2.t.y+sp2.r*Math.cos(sp2.ph), sp2.t.z+sp2.r*Math.sin(sp2.ph)*Math.cos(sp2.th)); camera.lookAt(sp2.t); }
  var dr=null;
  canvas.addEventListener("pointerdown",function(e){dr={x:e.clientX,y:e.clientY};});
  canvas.addEventListener("pointermove",function(e){ if(!dr)return;
    sp2.th-=(e.clientX-dr.x)*0.006; sp2.ph=Math.max(0.15,Math.min(1.4,sp2.ph-(e.clientY-dr.y)*0.006));
    dr.x=e.clientX; dr.y=e.clientY; fbApply(); });
  window.addEventListener("pointerup",function(){dr=null;});
  canvas.addEventListener("wheel",function(e){ e.preventDefault();
    sp2.r=Math.max(5,Math.min(70,sp2.r*(1+Math.sign(e.deltaY)*0.09))); fbApply(); },{passive:false});
  fbApply();
}

/* camera tween */
var camTween=null;
function flyTo(pos, tgt, dur){
  var t0 = (controls?controls.target:fallbackOrbit.t).clone();
  camTween = { p0:camera.position.clone(), p1:new THREE.Vector3().fromArray(pos),
               t0:t0, t1:new THREE.Vector3().fromArray(tgt), k:0, dur:dur||1.3 };
}
function setCamTarget(v){ if(controls) controls.target.copy(v); else fallbackOrbit.t.copy(v); }

/* ======================================================================
   LAYERS + BOOKMARKS
   ====================================================================== */
var layer = "phys";   // phys | logic
var bookmark = "floor";
function setLayer(l, fly){
  layer = l;
  document.getElementById("layPhys").setAttribute("aria-pressed", l==="phys");
  document.getElementById("layLogic").setAttribute("aria-pressed", l==="logic");
  gFloor.visible = (l==="phys");
  gBoard.visible = (l==="phys" && bookmark==="board");
  gLogic.visible = (l==="logic");
  gGhost.visible = (l==="logic" && ghostVisible);
  applyIsolate();
  if(fly){
    if(l==="logic" && bookmark!=="core") flyTo([0.5,10,15.5],[0.5,0.3,-0.2],1.2);
    else if(l==="phys") flyTo(VIEWS[bookmark==="board"?"board":"floor"].pos, VIEWS[bookmark==="board"?"board":"floor"].tgt, 1.2);
  }
}
var VIEWS = {
  board: { pos:[0,13,20],   tgt:[0,-0.6,0], layer:"phys", showBoard:true },
  floor: { pos:[0.5,15.5,12], tgt:[0,0,0],  layer:"phys", showBoard:false },
  core:  { pos:[0,6.5,11],   tgt:[0,0.6,0], layer:"logic", core:true }
};
function goBookmark(name){
  bookmark = name;
  var v = VIEWS[name];
  document.querySelectorAll("#left .btn[data-view]").forEach(function(b){
    b.setAttribute("aria-pressed", b.dataset.view===name);
  });
  setLayer(v.layer);
  gBoard.visible = (v.layer==="phys" && !!v.showBoard);
  gArray.visible = !!v.core;
  if(v.core){ // hide the big MM node while its guts are shown
    logicNodes.mm.visible = false;
    flyTo([arrCenter.x, arrCenter.y+7, arrCenter.z+11],[arrCenter.x,arrCenter.y+0.4,arrCenter.z], 1.4);
  } else {
    logicNodes.mm.visible = true;
    flyTo(v.pos, v.tgt, 1.3);
  }
}

/* isolate critical data path */
var iso=false;
function applyIsolate(){
  var streamIds={cv0:1,cv1:1,cv2:1,mm:1,dma0:1,dma1:1,dma2:1};
  Object.keys(floorBlocks).forEach(function(id){
    var m=floorBlocks[id].material;
    m.opacity = iso ? (streamIds[id]? (N[id].big?0.18:1) : 0.06) : (N[id].big?0.13:1);
    m.transparent = m.opacity<1;
  });
  Object.keys(logicNodes).forEach(function(id){
    logicNodes[id].material.emissiveIntensity = iso ? (streamIds[id]?0.4:0.04) : 0.16;
  });
  curvesFloor.concat(curvesLogic).forEach(function(o){
    o.tube.material.opacity = iso ? (o.e[2]==="stream"?0.6:0.04) : (o.e[2]==="stream"?0.4:0.24);
  });
}

/* ======================================================================
   INSPECTOR
   ====================================================================== */
var IEls = {
  tag:byId("iTag"), name:byId("iName"), path:byId("iPath"), ref:byId("iRef"),
  clk:byId("iClk"), reg:byId("iReg"), lut:byId("iLut"), ff:byId("iFf"),
  dsp:byId("iDsp"), bram:byId("iBram"), crWrap:byId("iCrWrap"), crTot:byId("iCrTot"),
  cr:byId("iCr"), note:byId("iNote"), tim:byId("iTim")
};
function byId(x){ return document.getElementById(x); }
function setTim(label, rows){
  if(!label){ IEls.tim.hidden = true; return; }
  IEls.tim.hidden = false;
  IEls.tim.innerHTML = "<div class='l'>"+label+"</div>" + rows.map(function(r){
    return "<div class='r'><span>"+r[0]+"</span><b class='mono'>"+r[1]+"</b></div>";
  }).join("");
}
function kfmt(n){ if(typeof n!=="number") return n;
  return n>=1000 ? (n/1000).toFixed(n>=10000?0:1)+"k" : (n%1===0?n:n.toFixed(1)); }
function renderCR(cr){
  if(!cr){ IEls.crWrap.style.display="none"; return; }
  IEls.crWrap.style.display="";
  var max=0,tot=0; CRO.forEach(function(k){ var v=cr[k]||0; if(v>max)max=v; tot+=v; });
  IEls.crTot.textContent = kfmt(tot)+" cells";
  IEls.cr.innerHTML = CRO.map(function(k){
    return '<span title="'+k+': '+(cr[k]||0)+'" style="--f:'+(max?(cr[k]||0)/max:0).toFixed(3)+'"><em>'+k+'</em></span>';
  }).join("");
}
function inspectSoc(id){
  var b=N[id]; if(!b) return;
  IEls.tag.textContent = b.kind==="stream"?"stream node":b.kind==="compute"?"compute core":b.kind==="hard"?"hard block":"interconnect";
  IEls.name.textContent = b.name;
  IEls.path.textContent = b.path;
  IEls.ref.textContent = b.ref;
  IEls.clk.textContent = "clk_fpga_0 · 100 MHz";
  IEls.reg.textContent = b.kind==="hard" ? "n/a (hard)" : Math.round(b.reg*100)+"%";
  IEls.lut.textContent = kfmt(b.lut); IEls.ff.textContent = kfmt(b.ff);
  IEls.dsp.textContent = b.dsp; IEls.bram.textContent = kfmt(b.bram);
  renderCR(b.cr); IEls.note.textContent = b.note;
  setTim(null);
  highlight("soc", id);
}
function inspectAcc(id){
  var b = ACC[id]; if(!b) return;
  IEls.tag.textContent = "accelerator · "+(id==="array"?"compute":"buffer");
  IEls.name.textContent = b.name; IEls.path.textContent = b.path; IEls.ref.textContent = b.ref;
  IEls.clk.textContent = "clk_fpga_0 · 100 MHz";
  IEls.reg.textContent = Math.round(b.reg*100)+"%";
  IEls.lut.textContent = kfmt(b.lut); IEls.ff.textContent = kfmt(b.ff);
  IEls.dsp.textContent = b.dsp; IEls.bram.textContent = kfmt(b.bram);
  renderCR(b.cr); IEls.note.textContent = b.note;
  if(id==="array"){
    setTim("Systolic timing @ 100 MHz", [
      ["MAC latency", "3 cyc (A/B→M→P)"],
      ["Array traversal", "2·16 = 32 cyc"],
      ["First result", "≈ 35 cyc · 0.35 µs"],
      ["Steady state", "1 result col / cyc"],
      ["Peak compute", "205·2·100M = 41.0 GOP/s"]
    ]);
  } else setTim(null);
}
function inspectPE(r,c){
  var dsp = peIsDsp[r][c];
  IEls.tag.textContent = "PE_array["+r+"]["+c+"]";
  IEls.name.textContent = "processing element";
  IEls.path.textContent = ".../u_PE_array/array["+r+"].PE_line_u/array_line["+c+"].PE_u";
  IEls.ref.textContent = dsp ? "PE · DSP48E1 MAC" : "PE · LUT fallback";
  IEls.clk.textContent = "clk_fpga_0 · 100 MHz";
  IEls.reg.textContent = dsp ? "100% (M/P reg)" : "~50%";
  IEls.lut.textContent = dsp?"1":"70"; IEls.ff.textContent = dsp?"16":"37";
  IEls.dsp.textContent = dsp?"1":"0"; IEls.bram.textContent = "0";
  renderCR(null);
  IEls.note.textContent = dsp
    ? "One 25×18 multiply-add per cycle. Weight held in the B register; activation passes A_in→A_out to column "+(c+1)+"; partial sum flows P→row "+(r+1)+"."
    : "The last 4 of the 16 PE rows get no DSP48E1 (the device is one DSP column short) — these fall back to LUT-based MAC.";
  if(dsp){
    setTim("Cycle-level timing", [
      ["MAC latency", "3 cyc  (A/B → M → P reg)"],
      ["A_in → A_out", "1 cyc / column hop"],
      ["Reaches PE["+r+"]["+(c)+"]", "≈ "+(r+c)+" cyc after row 0 col 0"],
      ["Full array traverse", "32 + 3 ≈ 35 cyc"]
    ]);
  } else setTim(null);
}
function inspectGhost(id){
  var g = GHOST[id]; if(!g) return;
  IEls.tag.textContent = "accelerator · pipeline";
  IEls.name.textContent = g.name;
  IEls.path.textContent = "transformer_block_top / " + g.inst;
  IEls.ref.textContent = g.role;
  IEls.clk.textContent = "clk_fpga_0 · 100 MHz";
  IEls.reg.textContent = Math.round(g.reg*100)+"%";
  IEls.lut.textContent = kfmt(g.lut); IEls.ff.textContent = kfmt(g.ff);
  IEls.dsp.textContent = g.dsp; IEls.bram.textContent = kfmt(g.bram);
  renderCR(g.cr || null);
  IEls.note.textContent = g.note;
  setTim(null);
}
function inspectPkg(){
  IEls.tag.textContent = "package";
  IEls.name.textContent = "XC7Z020-CLG400"; IEls.path.textContent = "Zynq-7000 · 400-ball CSBGA";
  IEls.ref.textContent = "28 nm · speed grade -1";
  IEls.clk.textContent = "PS ref 33.333 MHz → PLL";
  IEls.reg.textContent = "—";
  IEls.lut.textContent = kfmt(DEV.lut); IEls.ff.textContent = kfmt(DEV.ff);
  IEls.dsp.textContent = DEV.dsp; IEls.bram.textContent = DEV.bram;
  renderCR(N.mm.cr);
  IEls.note.textContent = "Single-die SoC: dual Cortex-A9 PS + Artix-7 fabric (53 200 LUT, 106 400 FF, 220 DSP48E1, 140 BRAM36). This design uses 205 of the 220 DSPs — the 16×16 array is one DSP column short of full.";
  setTim(null);
}
function highlight(kind, id){
  Object.keys(floorBlocks).forEach(function(k){
    if(!N[k].big) floorBlocks[k].material.emissiveIntensity = (kind==="soc"&&k===id)?0.5:0.12;
    if(floorBbox[k]) floorBbox[k].material.opacity = (kind==="soc"&&k===id)?0.55:0;
  });
  Object.keys(logicNodes).forEach(function(k){
    logicNodes[k].material.emissiveIntensity = (kind==="soc"&&k===id)?0.5: (iso? (({cv0:1,cv1:1,cv2:1,mm:1,dma0:1,dma1:1,dma2:1})[k]?0.4:0.04) : 0.16);
  });
}

/* raycast */
var ray = new THREE.Raycaster(), mouse = new THREE.Vector2();
canvas.addEventListener("pointerdown", function(e){ downXY=[e.clientX,e.clientY]; });
var downXY=[0,0];
canvas.addEventListener("pointerup", function(e){
  if(Math.abs(e.clientX-downXY[0])+Math.abs(e.clientY-downXY[1]) > 6) return;
  var r=canvas.getBoundingClientRect();
  mouse.x=((e.clientX-r.left)/r.width)*2-1; mouse.y=-((e.clientY-r.top)/r.height)*2+1;
  ray.setFromCamera(mouse, camera);
  var hits = ray.intersectObjects(pickables, true);
  for(var i=0;i<hits.length;i++){
    var o=hits[i].object;
    if(o.userData.noPick) continue;
    var u=o.userData;
    if(u.pick==="pe" && o===peMesh && hits[i].instanceId!=null){
      var id=hits[i].instanceId; inspectPE(Math.floor(id/GN), id%GN); return;
    }
    // climb to a parent that carries pick data
    var p=o;
    while(p && !(p.userData && p.userData.pick)) p=p.parent;
    if(!p) continue;
    var pu=p.userData;
    if(pu.pick==="soc"){ inspectSoc(pu.id); return; }
    if(pu.pick==="pe"){ if(pu.id) inspectAcc(pu.id); else inspectAcc("array"); return; }
    if(pu.pick==="pkg"){ inspectPkg(); return; }
    if(pu.pick==="ghost"){ inspectGhost(pu.id); return; }
  }
});

/* ======================================================================
   GUIDED TOUR
   ====================================================================== */
var tourOn=false, stageIx=0;
var stepsEl=document.getElementById("steps");
STAGES.forEach(function(st,i){
  var d=document.createElement("div"); d.className="step"; d.setAttribute("role","button"); d.tabIndex=0;
  d.innerHTML="<div class='s'>"+st.s+"</div><div class='t'>"+st.t+"</div>";
  d.addEventListener("click",function(){ enterStage(i); });
  d.addEventListener("keydown",function(e){ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); enterStage(i); }});
  stepsEl.appendChild(d);
});
function enterStage(i){
  stageIx = (i+STAGES.length)%STAGES.length;
  tourOn = true;
  document.getElementById("tour").classList.add("open");
  var st = STAGES[stageIx];
  [].forEach.call(stepsEl.children,function(c,ci){ c.setAttribute("aria-current", ci===stageIx); });
  document.getElementById("explTxt").innerHTML = st.html;
  drawDia(st.dia);
  if(st.ghost){ ghostVisible = true; ghostSw.setAttribute("aria-pressed", "true"); }
  if(st.view==="core"){ goBookmark("core"); }
  else {
    bookmark = "__tour";
    document.querySelectorAll("#left .btn[data-view]").forEach(function(b){ b.setAttribute("aria-pressed", false); });
    logicNodes.mm.visible = true;
    gArray.visible = false;
    setLayer("logic");
  }
  gGhost.visible = ghostVisible && layer==="logic";
  if(st.cam){ flyTo(st.cam, st.tgt, 1.4); }
  // emphasis
  var em={}; st.emph.forEach(function(x){ em[x]=1; });
  Object.keys(logicNodes).forEach(function(k){
    logicNodes[k].material.emissiveIntensity = em[k]? 0.5 : 0.05;
  });
  curvesLogic.forEach(function(o){
    var lit = em[o.e[0]]&&em[o.e[1]];
    o.tube.material.opacity = lit ? (o.e[2]==="stream"?0.7:0.3) : 0.05;
  });
  if(stageIx===1||stageIx===2){ inspectAcc("array"); } else { inspectSoc("mm"); }
}
function drawDia(kind){
  var host=document.getElementById("explDia");
  if(kind==="pe"){
    host.innerHTML =
      "<svg viewBox='0 0 230 150'>"+
      "<defs><marker id='ah' markerWidth='7' markerHeight='7' refX='5' refY='3.5' orient='auto'><path d='M0 0 L7 3.5 L0 7 z' fill='#8fa0b6'/></marker></defs>"+
      "<rect x='70' y='45' width='90' height='60' rx='7' fill='#12202a' stroke='#33c7a6'/>"+
      "<text x='115' y='40' fill='#9fe9d6' font-size='10' font-family='IBM Plex Mono' text-anchor='middle'>PE(i,j)</text>"+
      "<circle cx='115' cy='75' r='15' fill='none' stroke='#f0a755' stroke-width='1.4'/>"+
      "<text x='115' y='79' fill='#f0c89a' font-size='11' font-family='IBM Plex Mono' text-anchor='middle'>×+</text>"+
      "<text x='115' y='100' fill='#7f8ea3' font-size='7.5' font-family='IBM Plex Mono' text-anchor='middle'>DSP48E1</text>"+
      "<line x1='20' y1='75' x2='69' y2='75' stroke='#8fa0b6' marker-end='url(#ah)'/>"+
      "<text x='20' y='69' fill='#aab4c2' font-size='9' font-family='IBM Plex Mono'>A_in</text>"+
      "<line x1='161' y1='75' x2='210' y2='75' stroke='#8fa0b6' marker-end='url(#ah)'/>"+
      "<text x='185' y='69' fill='#aab4c2' font-size='9' font-family='IBM Plex Mono'>A_out</text>"+
      "<line x1='115' y1='12' x2='115' y2='44' stroke='#8fa0b6' marker-end='url(#ah)'/>"+
      "<text x='120' y='20' fill='#aab4c2' font-size='9' font-family='IBM Plex Mono'>B (held)</text>"+
      "<line x1='115' y1='106' x2='115' y2='140' stroke='#8fa0b6' marker-end='url(#ah)'/>"+
      "<text x='120' y='128' fill='#aab4c2' font-size='9' font-family='IBM Plex Mono'>Σ P</text>"+
      "<rect x='60' y='60' width='6' height='30' fill='#5f9be0'/><rect x='164' y='60' width='6' height='30' fill='#5f9be0'/>"+
      "<text x='2' y='120' fill='#5b6470' font-size='7' font-family='IBM Plex Mono'>│ = pipeline reg</text>"+
      "</svg>";
  } else {
    var chain = kind==="ingest" ? ["DDR","SMC","DMA","AXIS 128b","in_buf ×29"]
              : kind==="drain"  ? ["array","out_buf 37.5","LayerNorm","Softmax","GELU","DMA"]
              : ["mm_out_data","axis_downsizer","Softmax_control","axis_upsizer_fifo","EightGelus"];
    var vh = 8 + chain.length*26;
    host.innerHTML = "<svg viewBox='0 0 230 "+vh+"'>"+chain.map(function(t,i){
      var y=6+i*26;
      return "<rect x='30' y='"+y+"' width='170' height='18' rx='5' fill='#12161d' stroke='#2b3646'/>"+
             "<text x='115' y='"+(y+13)+"' fill='#c7cfda' font-size='9.5' font-family='IBM Plex Mono' text-anchor='middle'>"+t+"</text>"+
             (i<chain.length-1?"<line x1='115' y1='"+(y+18)+"' x2='115' y2='"+(y+26)+"' stroke='#5f9be0' stroke-width='1.5'/>":"");
    }).join("")+"</svg>";
  }
}
document.getElementById("tourToggle").addEventListener("click", function(){
  document.getElementById("tour").classList.toggle("open");
});
document.getElementById("tPrev").addEventListener("click", function(){ enterStage(stageIx-1); });
document.getElementById("tNext").addEventListener("click", function(){ enterStage(stageIx+1); });

/* ======================================================================
   TRANSPORT
   ====================================================================== */
var playing = !RM, speed = 1, flowVisible = true, ghostVisible = true;
var tPlay=document.getElementById("tPlay");
function setPlaying(p){ playing=p; tPlay.textContent = p?"❚❚":"▶"; tPlay.setAttribute("aria-label", p?"Pause dataflow":"Play dataflow"); }
tPlay.addEventListener("click", function(){ setPlaying(!playing); });
document.getElementById("tStep").addEventListener("click", function(){
  setPlaying(false); wf.cycle++; advancePE(0.999); // discrete cycle step
  streamsRT.forEach(function(s){ s.pk.forEach(function(_,k){ s.pk[k]=Math.min(0.999,s.pk[k]+0.12); }); });
});
var tSpeed=document.getElementById("tSpeed"), tRate=document.getElementById("tRate");
tSpeed.addEventListener("input", function(){ speed=parseFloat(tSpeed.value); tRate.textContent=speed.toFixed(1)+"×"; if(speed>0&&!playing) setPlaying(true); });
if(RM){ setPlaying(false); tSpeed.value=0; tRate.textContent="0.0×"; }

/* left panel wiring */
document.querySelectorAll("#left .btn[data-view]").forEach(function(b){
  b.addEventListener("click", function(){ tourOn=false; document.getElementById("tour").classList.remove("open");
    [].forEach.call(stepsEl.children,function(c){ c.removeAttribute("aria-current"); });
    goBookmark(b.dataset.view); });
});
document.getElementById("layPhys").addEventListener("click", function(){ tourOn=false; document.getElementById("tour").classList.remove("open"); logicNodes.mm.visible=true; gArray.visible=false; setLayer("phys", true); });
document.getElementById("layLogic").addEventListener("click", function(){ tourOn=false; document.getElementById("tour").classList.remove("open"); logicNodes.mm.visible=true; gArray.visible=false; setLayer("logic", true); });
var isoSw=document.getElementById("isoSw");
function toggleIso(){ iso=!iso; isoSw.setAttribute("aria-pressed",iso); applyIsolate(); highlight("soc",null); }
isoSw.addEventListener("click", toggleIso);
isoSw.addEventListener("keydown", function(e){ if(e.key==="Enter"||e.key===" "){e.preventDefault();toggleIso();} });
var flowSw=document.getElementById("flowSw");
flowSw.addEventListener("click", function(){ flowVisible=!flowVisible; flowSw.setAttribute("aria-pressed",flowVisible);
  pkMesh.visible=flowVisible; });
var ghostSw=document.getElementById("ghostSw");
function setGhost(on){
  ghostVisible = on;
  ghostSw.setAttribute("aria-pressed", on);
  gGhost.visible = on && layer==="logic";
  if(on && layer!=="logic"){ setLayer("logic", true); gGhost.visible = true; }
}
ghostSw.addEventListener("click", function(){ setGhost(!ghostVisible); });
ghostSw.addEventListener("keydown", function(e){ if(e.key==="Enter"||e.key===" "){ e.preventDefault(); setGhost(!ghostVisible); } });

document.addEventListener("keydown", function(e){
  if(e.target.tagName==="INPUT") return;
  if(e.code==="Space"){ e.preventDefault(); setPlaying(!playing); }
  else if(e.key==="1"){ goBookmark("board"); }
  else if(e.key==="2"){ goBookmark("floor"); }
  else if(e.key==="3"){ goBookmark("core"); }
});

/* ======================================================================
   ANIMATION
   ====================================================================== */
function advanceSoc(dt){
  if(bookmark==="core"){ if(pkMesh.count){ pkMesh.count=0; pkMesh.instanceMatrix.needsUpdate=true; } return; }
  var curves = layer==="phys" ? curvesFloor : curvesLogic;
  var byKey = {};
  curves.forEach(function(o){ byKey[o.e[0]+">"+o.e[1]] = o.c; });
  var n=0;
  for(var i=0;i<streamsRT.length && n<PKMAX;i++){
    var s=streamsRT[i];
    var curve = byKey[s.from+">"+s.to];
    if(!curve) continue;
    if(playing && !RM){
      s.acc += dt*speed*s.spawn;
      while(s.acc>=1){ s.acc-=1; s.pk.push(0); }
      for(var j=s.pk.length-1;j>=0;j--){ s.pk[j]+=dt*speed*s.rate; if(s.pk[j]>=1) s.pk.splice(j,1); }
    }
    var headScale = s.kind==="stream" ? 1.0 + s.bits/128*0.6 : 0.7;
    for(var k=0;k<s.pk.length && n<PKMAX;k++){
      var t=s.pk[k]; if(t<0||t>1) continue;
      curve.getPointAt(Math.min(0.999,Math.max(0.001,t)), _P);
      // trail: a few shrinking followers
      for(var q=0;q<3 && n<PKMAX;q++){
        var tt = t - q*0.018*(s.kind==="stream"?1:1.6);
        if(tt<=0) break;
        curve.getPointAt(Math.min(0.999,tt), _P);
        _S.setScalar((q===0?headScale:headScale*(1-q*0.32)));
        _M.compose(_P,_Q,_S);
        pkMesh.setMatrixAt(n,_M);
        _C.setHex(q===0 ? KCOL.signal : s.col);
        pkMesh.setColorAt(n,_C);
        n++;
      }
    }
  }
  pkMesh.count=n;
  pkMesh.instanceMatrix.needsUpdate=true;
  if(pkMesh.instanceColor) pkMesh.instanceColor.needsUpdate=true;
}

function advancePE(dt){
  if(!gArray.visible) return;
  var half=AW/2;
  if(playing && !RM){ wf.frac += dt*speed*3.2; while(wf.frac>=1){ wf.frac-=1; wf.cycle++; } }
  var phase = wf.cycle + wf.frac;
  var band = phase % (ACC.rows+GN);

  // weights streaming down columns (visual feed from in_buffer)
  var W=flowW; if(playing&&!RM){ W.acc+=dt*speed*8; while(W.acc>=1){ W.acc-=1; W.list.push({c:(Math.random()*GN)|0,t:0}); } }
  for(var i=W.list.length-1;i>=0;i--){ if(playing&&!RM) W.list[i].t+=dt*speed*0.55; if(W.list[i].t>=1) W.list.splice(i,1); }
  var wc=0, d=new THREE.Object3D();
  W.list.forEach(function(w){ var x=(w.c-(GN-1)/2)*cell, z=half - w.t*AW;
    d.position.set(x,0.85,z); d.rotation.set(0,0,0); d.scale.set(1,1,1); d.updateMatrix(); W.im.setMatrixAt(wc++,d.matrix); });
  W.im.count=wc; W.im.instanceMatrix.needsUpdate=true;

  // activations across rows
  var A=flowA; if(playing&&!RM){ A.acc+=dt*speed*8; while(A.acc>=1){ A.acc-=1; A.list.push({r:(Math.random()*ACC.rows)|0,t:0}); } }
  for(var a=A.list.length-1;a>=0;a--){ if(playing&&!RM) A.list[a].t+=dt*speed*0.55; if(A.list[a].t>=1) A.list.splice(a,1); }
  var ac=0;
  A.list.forEach(function(v){ var z=(v.r-(ACC.rows-1)/2)*cell, x=-half + v.t*AW;
    d.position.set(x,0.66,z); d.scale.set(1,1,1); d.updateMatrix(); A.im.setMatrixAt(ac++,d.matrix); });
  A.im.count=ac; A.im.instanceMatrix.needsUpdate=true;

  // partial sums draining up into out_buffer
  var S=flowS; if(playing&&!RM){ S.acc+=dt*speed*5; while(S.acc>=1){ S.acc-=1; S.list.push({c:(Math.random()*GN)|0,t:0}); } }
  for(var s2=S.list.length-1;s2>=0;s2--){ if(playing&&!RM) S.list[s2].t+=dt*speed*0.6; if(S.list[s2].t>=1) S.list.splice(s2,1); }
  var sc=0;
  S.list.forEach(function(v){ var x=(v.c-(GN-1)/2)*cell, z=-half + v.t*(AW+2.4);
    d.position.set(x, 0.8 + v.t*0.5, z); d.scale.set(1,1,1); d.updateMatrix(); S.im.setMatrixAt(sc++,d.matrix); });
  S.im.count=sc; S.im.instanceMatrix.needsUpdate=true;

  // diagonal compute glow on DSP PEs
  for(var id=0; id<peBase.length; id++){
    var rr2=Math.floor(id/GN), cc2=id%GN;
    var base=peBase[id];
    if(peIsDsp[rr2][cc2]){
      var dist=Math.abs((rr2+cc2) - band);
      var g = dist<2.4 ? (1-dist/2.4) : 0;
      _C.copy(base).lerp(new THREE.Color(KCOL.signal), g*0.85);
      peMesh.setColorAt(id,_C);
    }
  }
  peMesh.instanceColor.needsUpdate=true;
}

/* ---- ghost (transformer extension) pulses ---- */
function updateGhost(dt){
  if(!gGhost.visible){ return; }
  if(playing && !RM) ghostT += dt*speed*0.35;
  var n=0, d=new THREE.Object3D();
  for(var i=0;i<ghostCurves.length;i++){
    for(var k=0;k<2;k++){
      var t=(ghostT*0.6 + i*0.25 + k*0.5) % 1;
      ghostCurves[i].getPointAt(Math.min(0.999,Math.max(0.001,t)), _P);
      d.position.copy(_P); d.updateMatrix();
      ghostPk.setMatrixAt(n++, d.matrix);
    }
  }
  ghostPk.count = n;
  ghostPk.instanceMatrix.needsUpdate = true;
}

/* ---- live telemetry model ---- */
var TEL = { gops:0, ddr:0, cyc:0, duty:0 };
var telEl = {
  cyc:document.getElementById("tCyc"), gops:document.getElementById("tGops"),
  gopsBar:document.getElementById("tGopsBar"), ddr:document.getElementById("tDdr"),
  ddrBar:document.getElementById("tDdrBar"), ddrCap:document.getElementById("tDdrCap")
};
var GOPS_PEAK = 41.0;          // 205 DSP48E1 x 2 ops x 100 MHz
var DDR_PEAK  = 3.6;           // 2 x 128-bit in + 1 x 32-bit out @ 100 MHz = 2*1.6 + 0.4 GB/s
var DDR_CEIL  = 4.3;           // 32-bit DDR3-1066 on the PS
function updateTelem(dt){
  var target = 0;
  if(playing){
    if(bookmark==="core"){
      var fill = Math.min(1, wf.cycle/35);           // fills over the first ~35 cycles
      target = 0.30 + 0.62*fill;                      // -> ~0.92 steady (192/205 DSP in the array)
    } else {
      target = 0.68;                                  // pipeline running; downsizer bridge caps sustained rate
    }
  }
  TEL.duty += (target - TEL.duty) * Math.min(1, dt*3);
  TEL.gops = GOPS_PEAK * TEL.duty;
  TEL.ddr  = flowVisible ? DDR_PEAK * (0.4 + 0.6*TEL.duty) : 0;
  if(playing && !RM && bookmark==="core") TEL.cyc = wf.cycle;

  if(telEl.gops){
    telEl.gops.textContent = TEL.gops.toFixed(1);
    telEl.gopsBar.style.width = (TEL.gops/GOPS_PEAK*100).toFixed(0)+"%";
    telEl.ddr.textContent = TEL.ddr.toFixed(1);
    telEl.ddrBar.style.width = Math.min(100, TEL.ddr/DDR_CEIL*100).toFixed(0)+"%";
    telEl.cyc.textContent = bookmark==="core" ? ("cycle "+TEL.cyc+(TEL.cyc>35?" · steady":"")) : "cycle —";
    telEl.ddrCap.innerHTML = TEL.ddr>0.1
      ? "<b>"+Math.round(TEL.ddr/DDR_CEIL*100)+"% of the 32-bit DDR3 ceiling</b> — 16-lane config stays memory-bound-free"
      : "<b>32-bit DDR3 ≈ 4.3 GB/s</b> — peak stream demand 3.6 GB/s fits under it";
  }
}

var clock = new THREE.Clock();
var started = false;
function loop(){
  requestAnimationFrame(loop);
  var dt = Math.min(clock.getDelta(), 0.05);

  if(camTween){
    camTween.k = Math.min(1, camTween.k + dt/camTween.dur);
    var e = camTween.k<0.5 ? 4*camTween.k*camTween.k*camTween.k
          : 1 - Math.pow(-2*camTween.k+2,3)/2;
    camera.position.lerpVectors(camTween.p0, camTween.p1, e);
    var tg = new THREE.Vector3().lerpVectors(camTween.t0, camTween.t1, e);
    setCamTarget(tg);
    if(camTween.k>=1) camTween=null;
  }
  if(controls) controls.update();

  if(flowVisible) advanceSoc(dt);
  advancePE(dt);
  updateGhost(dt);
  updateTelem(dt);

  if(USE_POST && composer) composer.render();
  else renderer.render(scene, camera);

  if(!started){ started=true; window.__taofpgaBooted=true; setTimeout(function(){ bootEl.style.opacity=0; setTimeout(function(){bootEl.style.display="none";},500); }, 120); }
}

/* ======================================================================
   RESIZE / BOOT
   ====================================================================== */
function resize(){
  var w=innerWidth, h=innerHeight;
  renderer.setSize(w,h,false);
  camera.aspect=w/h; camera.updateProjectionMatrix();
  if(composer){ composer.setSize(w,h); if(bloomPass) bloomPass.setSize(w,h); }
}
window.addEventListener("resize", resize);
resize();

try{
  setLayer("phys");
  goBookmark("floor");
  inspectSoc("mm");
  setPlaying(!RM);
  loop();
}catch(err){
  fail("Scene build failed.<br><span class='mono' style='font-size:11px'>"+(err && err.message || err)+"</span>");
  throw err;
}

setTimeout(function(){ var h=document.getElementById("hint"); if(h) h.style.opacity=0; }, 7000);
})();
