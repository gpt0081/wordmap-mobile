from __future__ import annotations

VERSION = "0.11.0"


def apply(wordmap_mobile):
    visual_html = r'''
<section class="card" id="wmVisualCard">
<h2>3. WordMap Visual Debugger</h2>
<div class="meta">Vault의 graph.json을 자동으로 읽어 같은 좌표 위에 여러 지도 레이어를 겹쳐 표시합니다.</div>
<div class="wmv-toolbar">
  <button class="secondary" onclick="wmLoadGraph()">지도 다시 불러오기</button>
  <button class="secondary" onclick="wmPrevStage()">◀ 단계</button>
  <button class="secondary" id="wmPlay" onclick="wmTogglePlay()">▶ 재생</button>
  <button class="secondary" onclick="wmNextStage()">단계 ▶</button>
</div>
<div class="wmv-layers">
  <label><input type="checkbox" data-wm-layer="연상" checked> 연상</label>
  <label><input type="checkbox" data-wm-layer="의미" checked> 의미</label>
  <label><input type="checkbox" data-wm-layer="순서"> 순서</label>
  <label><input type="checkbox" data-wm-layer="생성" checked> 생성</label>
  <label><input type="checkbox" id="wmActiveLayer" checked> 활성화</label>
  <label><input type="checkbox" id="wmLabels" checked> 라벨</label>
</div>
<div id="wmGraphWrap"><canvas id="wmGraphCanvas"></canvas></div>
<input id="wmStage" type="range" min="0" max="0" value="0" step="1" oninput="wmSetStage(Number(this.value))">
<div id="wmStageInfo" class="wmv-stage">그래프 불러오는 중...</div>
<div id="wmGraphInfo" class="meta"></div>
</section>
<style>
#wmGraphWrap{height:440px;margin-top:12px;background:#0b0d11;border:1px solid #343944;border-radius:14px;overflow:hidden;position:relative}
#wmGraphCanvas{width:100%;height:100%;display:block;touch-action:none}
.wmv-toolbar{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:6px;margin-top:10px}
.wmv-toolbar button{padding:9px 6px;font-size:12px}
.wmv-layers{display:flex;flex-wrap:wrap;gap:9px 14px;margin-top:10px;font-size:12px;color:#c6cad2}
.wmv-layers label{display:flex;align-items:center;gap:4px}
.wmv-layers input{width:auto;margin:0}
#wmStage{margin-top:10px;padding:0}
.wmv-stage{margin-top:8px;padding:9px;border-radius:9px;background:#101319;font-size:12px;line-height:1.55;color:#d7dbe3}
@media(max-width:600px){#wmGraphWrap{height:390px}.wmv-toolbar{grid-template-columns:1fr 1fr}.wmv-toolbar button{font-size:11px}}
</style>
'''

    script = r'''
<script>
const WMV={graph:null,pos:{},stages:[],stage:0,timer:null,drag:null,zoom:1,panX:0,panY:0};

function wmHash(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function wmLayerOn(name){let x=document.querySelector('[data-wm-layer="'+name+'"]');return !x||x.checked}
function wmEsc(s){return typeof esc==='function'?esc(s):String(s)}

function wmResize(){
  let c=document.getElementById('wmGraphCanvas');if(!c)return;
  let r=c.getBoundingClientRect(),d=Math.min(2,window.devicePixelRatio||1);
  c.width=Math.max(10,Math.floor(r.width*d));c.height=Math.max(10,Math.floor(r.height*d));
  c._scale=d;wmRender();
}

function wmInitialLayout(graph){
  let nodes=graph.nodes||[],n=Math.max(1,nodes.length),pos={};
  nodes.forEach((node,i)=>{
    let h=wmHash(node.id),a=((h%100000)/100000)*Math.PI*2;
    let rank=i/n,r=.12+.39*Math.sqrt(rank);
    pos[node.id]={x:.5+Math.cos(a)*r,y:.5+Math.sin(a)*r,vx:0,vy:0};
  });
  let links=(graph.edges||[]).filter(e=>e.layer==='연상'||e.layer==='의미');
  for(let iter=0;iter<28;iter++){
    for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
      let a=pos[nodes[i].id],b=pos[nodes[j].id],dx=a.x-b.x,dy=a.y-b.y;
      let d2=dx*dx+dy*dy+.0008,f=.000015/d2;
      a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;
    }
    links.forEach(e=>{
      let a=pos[e.source],b=pos[e.target];if(!a||!b)return;
      let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.0001;
      let target=.10,force=(d-target)*.0035*Math.max(.15,Number(e.weight||.2));
      a.vx+=dx/d*force;a.vy+=dy/d*force;b.vx-=dx/d*force;b.vy-=dy/d*force;
    });
    nodes.forEach(node=>{
      let p=pos[node.id];p.vx+=(0.5-p.x)*.001;p.vy+=(0.5-p.y)*.001;
      p.vx*=.72;p.vy*=.72;p.x=Math.max(.04,Math.min(.96,p.x+p.vx));p.y=Math.max(.04,Math.min(.96,p.y+p.vy));
    });
  }
  WMV.pos=pos;
}

function wmStageData(){return WMV.stages[WMV.stage]||{activation:{},path:[]}}
function wmXY(p,w,h){return {x:(p.x-.5)*WMV.zoom*w+w*.5+WMV.panX,y:(p.y-.5)*WMV.zoom*h+h*.5+WMV.panY}}

function wmArrow(ctx,a,b,color,width,alpha,directed){
  ctx.save();ctx.globalAlpha=alpha;ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
  if(directed){let ang=Math.atan2(b.y-a.y,b.x-a.x),s=5+width;ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.lineTo(b.x-Math.cos(ang-.55)*s,b.y-Math.sin(ang-.55)*s);ctx.lineTo(b.x-Math.cos(ang+.55)*s,b.y-Math.sin(ang+.55)*s);ctx.closePath();ctx.fill()}
  ctx.restore();
}

function wmRender(){
  let c=document.getElementById('wmGraphCanvas');if(!c||!WMV.graph)return;
  let d=c._scale||1,ctx=c.getContext('2d'),w=c.width/d,h=c.height/d;ctx.setTransform(d,0,0,d,0,0);ctx.clearRect(0,0,w,h);
  let stage=wmStageData(),active=stage.activation||{},path=stage.path||[],pathPairs=new Set();
  for(let i=1;i<path.length;i++)pathPairs.add(path[i-1]+'\u001f'+path[i]);
  let edgeStyle={연상:['#58606d',.32],의미:['#d3a657',.64],순서:['#6e8fcf',.30],생성:['#67d59b',.95]};
  (WMV.graph.edges||[]).forEach(e=>{
    if(!wmLayerOn(e.layer))return;let pa=WMV.pos[e.source],pb=WMV.pos[e.target];if(!pa||!pb)return;
    let a=wmXY(pa,w,h),b=wmXY(pb,w,h),style=edgeStyle[e.layer]||['#555',.3];
    let isPath=pathPairs.has(e.source+'\u001f'+e.target);let width=isPath?3.1:Math.max(.45,Math.min(2,Number(e.weight||.2)*1.8));
    wmArrow(ctx,a,b,isPath?'#8af0b4':style[0],width,isPath?1:style[1],!!e.directed);
  });
  if(wmLayerOn('생성')){
    for(let i=1;i<path.length;i++){let pa=WMV.pos[path[i-1]],pb=WMV.pos[path[i]];if(pa&&pb)wmArrow(ctx,wmXY(pa,w,h),wmXY(pb,w,h),'#8af0b4',3.4,1,true)}
  }
  let showActive=document.getElementById('wmActiveLayer')?.checked!==false,showLabels=document.getElementById('wmLabels')?.checked!==false;
  let freqMax=Math.max(1,...(WMV.graph.nodes||[]).map(n=>Number(n.frequency||0)));
  (WMV.graph.nodes||[]).forEach(node=>{
    let p=WMV.pos[node.id];if(!p)return;let q=wmXY(p,w,h),a=showActive?Number(active[node.id]||node.activation||0):0;
    let inPath=path.includes(node.id),base=2.6+4*Math.sqrt(Number(node.frequency||0)/freqMax),r=base+a*10+(inPath?2.5:0);
    ctx.beginPath();ctx.arc(q.x,q.y,r,0,Math.PI*2);ctx.fillStyle=inPath?'#9af2bd':(a>.02?'#f2c875':'#8b95a5');ctx.globalAlpha=inPath?1:(a>.02?.45+.55*a:.58);ctx.fill();ctx.globalAlpha=1;
    if(showLabels&&(inPath||a>.12||r>4.4)){
      ctx.font=(inPath?'700 ':'')+'11px system-ui';ctx.fillStyle='#eef1f5';ctx.globalAlpha=inPath?1:.78;ctx.fillText(node.label,q.x+r+3,q.y+4);ctx.globalAlpha=1;
    }
  });
  wmUpdateStageInfo();
}

function wmUpdateStageInfo(){
  let el=document.getElementById('wmStageInfo');if(!el)return;let s=wmStageData(),parts=['<b>'+wmEsc(s.name||'장기기억 지도')+'</b>'];
  if(s.message)parts.push(wmEsc(s.message));
  if((s.path||[]).length)parts.push('경로: '+s.path.map(wmEsc).join(' → '));
  if(s.selected)parts.push('선택: <b>'+wmEsc(s.selected_surface||s.selected)+'</b> · 확률 '+(Number(s.selection_probability||0)*100).toFixed(1)+'% · 문법 '+Number(s.grammar_fit||0).toFixed(3));
  if((s.candidate_origins||[]).length)parts.push('선택 근거: '+s.candidate_origins.map(wmEsc).join(', '));
  if(s.grammar_pattern)parts.push('문법 패턴: '+wmEsc(s.grammar_pattern));
  if(s.text)parts.push('완성: <b>'+wmEsc(s.text)+'</b>');
  let cand=(s.candidates||[]).slice(0,3);if(cand.length)parts.push('후보: '+cand.map(x=>wmEsc(x['표면형']||x['표제어']||'')+' '+(Number(x['선택확률']||0)*100).toFixed(1)+'%').join(' · '));
  el.innerHTML=parts.join('<br>');
}

function wmSetGraph(graph,stages){
  if(!graph)return;WMV.graph=graph;WMV.stages=(stages&&stages.length)?stages:[{name:'장기기억 지도',kind:'기본',activation:{},path:[],message:'Vault의 장기 WordMap입니다.'}];WMV.stage=0;WMV.zoom=1;WMV.panX=0;WMV.panY=0;
  wmInitialLayout(graph);let slider=document.getElementById('wmStage');slider.max=Math.max(0,WMV.stages.length-1);slider.value=0;
  let st=graph.stats||{},layers=st.layers||{};document.getElementById('wmGraphInfo').textContent='전체 노드 '+Number(st.total_nodes||0).toLocaleString()+'개 중 '+Number(st.shown_nodes||0)+'개 표시 · 연상 '+Number(layers['연상']||0)+' · 의미 '+Number(layers['의미']||0)+' · 순서 '+Number(layers['순서']||0)+' · 생성 '+Number(layers['생성']||0);
  wmResize();
}

async function wmLoadGraph(){
  try{document.getElementById('wmStageInfo').textContent='Vault graph.json 불러오는 중...';let g=await api('/api/graph');wmSetGraph(g,null)}catch(e){document.getElementById('wmStageInfo').textContent='그래프 오류: '+e.message}
}
function wmUseAskResult(d){if(d&&d.visual_graph)wmSetGraph(d.visual_graph,d['시각화단계']||[])}
function wmSetStage(i){WMV.stage=Math.max(0,Math.min(WMV.stages.length-1,Number(i)||0));document.getElementById('wmStage').value=WMV.stage;wmRender()}
function wmPrevStage(){wmSetStage(WMV.stage-1)}
function wmNextStage(){wmSetStage(WMV.stage+1)}
function wmTogglePlay(){
  let b=document.getElementById('wmPlay');if(WMV.timer){clearInterval(WMV.timer);WMV.timer=null;b.textContent='▶ 재생';return}
  if(WMV.stage>=WMV.stages.length-1)wmSetStage(0);b.textContent='■ 정지';WMV.timer=setInterval(()=>{if(WMV.stage>=WMV.stages.length-1){clearInterval(WMV.timer);WMV.timer=null;b.textContent='▶ 재생';return}wmNextStage()},900);
}

document.querySelectorAll('[data-wm-layer],#wmActiveLayer,#wmLabels').forEach(x=>x.addEventListener('change',wmRender));
window.addEventListener('resize',wmResize);
let wmCanvas=document.getElementById('wmGraphCanvas');
wmCanvas.addEventListener('wheel',e=>{e.preventDefault();WMV.zoom=Math.max(.6,Math.min(2.6,WMV.zoom*(e.deltaY<0?1.12:.89)));wmRender()},{passive:false});
wmCanvas.addEventListener('pointerdown',e=>{WMV.drag={x:e.clientX,y:e.clientY,px:WMV.panX,py:WMV.panY};wmCanvas.setPointerCapture(e.pointerId)});
wmCanvas.addEventListener('pointermove',e=>{if(!WMV.drag)return;WMV.panX=WMV.drag.px+(e.clientX-WMV.drag.x);WMV.panY=WMV.drag.py+(e.clientY-WMV.drag.y);wmRender()});
wmCanvas.addEventListener('pointerup',()=>{WMV.drag=null});

const wmOriginalApi=window.api;
window.api=async function(p,m='GET',b=null){
  let d=await wmOriginalApi(p,m,b);
  if(p==='/api/ask')wmUseAskResult(d);
  if(p==='/api/select-vault'||p==='/api/rebuild'||p==='/api/ingest')setTimeout(wmLoadGraph,250);
  return d;
};
setTimeout(wmLoadGraph,450);
</script>
'''

    if "</main>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</main>",
            visual_html + "\n</main>",
            1,
        )
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</body>",
            script + "\n</body>",
            1,
        )
    return wordmap_mobile
