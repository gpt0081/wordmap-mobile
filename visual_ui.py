from __future__ import annotations

VERSION = "0.11.1"


def apply(wordmap_mobile):
    visual_html = r'''
<section class="card" id="wmVisualCard">
<h2>3. WordMap 사고 지도</h2>
<div class="meta">기본 화면은 전체 지도가 아니라 현재 생성 경로와 경쟁 후보만 보여줍니다. 필요할 때 주변 지도와 전체 지도를 펼칠 수 있습니다.</div>

<div class="wmv-modes">
  <button class="wmv-mode active" data-wm-mode="thought" onclick="wmSetMode('thought')">현재 사고</button>
  <button class="wmv-mode" data-wm-mode="meaning" onclick="wmSetMode('meaning')">의미 관계</button>
  <button class="wmv-mode" data-wm-mode="order" onclick="wmSetMode('order')">단어 순서</button>
  <button class="wmv-mode" data-wm-mode="full" onclick="wmSetMode('full')">전체 지도</button>
</div>

<div class="wmv-toolbar">
  <button class="secondary" onclick="wmLoadGraph()">지도 다시 불러오기</button>
  <button class="secondary" onclick="wmPrevStage()">◀ 단계</button>
  <button class="secondary" id="wmPlay" onclick="wmTogglePlay()">▶ 재생</button>
  <button class="secondary" onclick="wmNextStage()">단계 ▶</button>
</div>

<div class="wmv-toolbar compact">
  <button class="secondary" id="wmScope" onclick="wmCycleScope()">주변 1홉</button>
  <button class="secondary" onclick="wmResetView()">화면 맞춤</button>
</div>

<div class="wmv-legend">
  <span><i class="wmv-dot path"></i>생성 경로</span>
  <span><i class="wmv-dot candidate"></i>경쟁 후보</span>
  <span><i class="wmv-dot active"></i>활성 개념</span>
  <span><i class="wmv-dot quiet"></i>주변 노드</span>
</div>

<div id="wmGraphWrap"><canvas id="wmGraphCanvas"></canvas></div>
<input id="wmStage" type="range" min="0" max="0" value="0" step="1" oninput="wmSetStage(Number(this.value))">
<div id="wmStageInfo" class="wmv-stage">그래프 불러오는 중...</div>
<div id="wmNodeInfo" class="wmv-nodeinfo"></div>
<div id="wmGraphInfo" class="meta"></div>
</section>
<style>
#wmGraphWrap{height:420px;margin-top:10px;background:#0b0d11;border:1px solid #343944;border-radius:14px;overflow:hidden;position:relative}
#wmGraphCanvas{width:100%;height:100%;display:block;touch-action:none}
.wmv-modes{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:12px}
.wmv-mode{padding:9px 4px;font-size:12px;background:#272c35;color:#cdd2da;border:1px solid #343b46}
.wmv-mode.active{background:#e8ebf0;color:#111;border-color:#e8ebf0}
.wmv-toolbar{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:6px;margin-top:8px}
.wmv-toolbar.compact{grid-template-columns:1fr 1fr;margin-top:6px}
.wmv-toolbar button{padding:9px 6px;font-size:12px}
.wmv-legend{display:flex;gap:8px 13px;flex-wrap:wrap;margin-top:9px;color:#aeb5c0;font-size:11px}
.wmv-legend span{display:flex;align-items:center;gap:5px}
.wmv-dot{width:9px;height:9px;border-radius:50%;display:inline-block;background:#7d8795}
.wmv-dot.path{background:#8ff0b6}.wmv-dot.candidate{background:#f1c56e}.wmv-dot.active{background:#70b9ef}.wmv-dot.quiet{background:#5c6470}
#wmStage{margin-top:10px;padding:0}
.wmv-stage{margin-top:8px;padding:11px;border-radius:10px;background:#101319;font-size:12px;line-height:1.6;color:#d7dbe3}
.wmv-stage .wmv-title{font-size:15px;font-weight:800;margin-bottom:4px}
.wmv-stage .wmv-choice{margin-top:7px;padding:7px 8px;border-radius:8px;background:#171c24}
.wmv-stage .wmv-cands{display:grid;gap:4px;margin-top:7px}
.wmv-stage .wmv-cand{display:flex;justify-content:space-between;gap:8px;color:#bfc6d0}
.wmv-nodeinfo{display:none;margin-top:7px;padding:8px;border-radius:9px;background:#151922;color:#cfd5de;font-size:12px}
@media(max-width:600px){#wmGraphWrap{height:370px}.wmv-modes{grid-template-columns:1fr 1fr}.wmv-toolbar{grid-template-columns:1fr 1fr}.wmv-toolbar button,.wmv-mode{font-size:11px}}
</style>
'''

    script = r'''
<script>
const WMV={graph:null,pos:{},stages:[],stage:0,timer:null,drag:null,zoom:1,panX:0,panY:0,mode:'thought',scope:1,visible:new Set(),screenPos:{},moved:false};

function wmHash(s){let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function wmEsc(s){return typeof esc==='function'?esc(s):String(s)}
function wmStageData(){return WMV.stages[WMV.stage]||{activation:{},path:[],candidates:[],candidate_ids:[]}}
function wmNodeById(id){return (WMV.graph?.nodes||[]).find(n=>n.id===id)}
function wmCandidateIds(stage){let out=[];(stage.candidate_ids||[]).forEach(x=>{if(x&&!out.includes(x))out.push(x)});(stage.candidates||[]).slice(0,5).forEach(x=>{let t=x['표제어'];if(t&&!out.includes(t))out.push(t)});return out}
function wmCandidateMap(stage){let m={};(stage.candidates||[]).slice(0,5).forEach(x=>{let t=x['표제어'];if(t)m[t]=x});return m}
function wmActiveIds(stage,limit=8){return Object.entries(stage.activation||{}).sort((a,b)=>Number(b[1])-Number(a[1])).slice(0,limit).map(x=>x[0])}
function wmRecentPath(stage){let p=(stage.path||[]).filter(Boolean);return p.length>5?p.slice(-5):p}

function wmResize(){
  let c=document.getElementById('wmGraphCanvas');if(!c)return;
  let r=c.getBoundingClientRect(),d=Math.min(2,window.devicePixelRatio||1);
  c.width=Math.max(10,Math.floor(r.width*d));c.height=Math.max(10,Math.floor(r.height*d));c._scale=d;
  if(WMV.mode!=='thought')wmAutoFocus();wmRender();
}

function wmInitialLayout(graph){
  let nodes=graph.nodes||[],n=Math.max(1,nodes.length),pos={};
  nodes.forEach((node,i)=>{let h=wmHash(node.id),a=((h%100000)/100000)*Math.PI*2,rank=i/n,r=.12+.39*Math.sqrt(rank);pos[node.id]={x:.5+Math.cos(a)*r,y:.5+Math.sin(a)*r,vx:0,vy:0}});
  let links=(graph.edges||[]).filter(e=>e.layer==='연상'||e.layer==='의미'||e.layer==='생성');
  for(let iter=0;iter<30;iter++){
    for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
      let a=pos[nodes[i].id],b=pos[nodes[j].id],dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy+.001,f=.000013/d2;
      a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;
    }
    links.forEach(e=>{let a=pos[e.source],b=pos[e.target];if(!a||!b)return;let dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.0001,target=e.layer==='생성'?.08:.11,force=(d-target)*.0032*Math.max(.18,Number(e.weight||.2));a.vx+=dx/d*force;a.vy+=dy/d*force;b.vx-=dx/d*force;b.vy-=dy/d*force});
    nodes.forEach(node=>{let p=pos[node.id];p.vx+=(0.5-p.x)*.001;p.vy+=(0.5-p.y)*.001;p.vx*=.72;p.vy*=.72;p.x=Math.max(.04,Math.min(.96,p.x+p.vx));p.y=Math.max(.04,Math.min(.96,p.y+p.vy))});
  }
  WMV.pos=pos;
}

function wmThoughtCore(stage){
  let ids=[];wmRecentPath(stage).forEach(x=>{if(x&&!ids.includes(x))ids.push(x)});wmCandidateIds(stage).forEach(x=>{if(x&&!ids.includes(x))ids.push(x)});wmActiveIds(stage,7).forEach(x=>{if(x&&!ids.includes(x))ids.push(x)});if(stage.selected&&!ids.includes(stage.selected))ids.push(stage.selected);return ids;
}

function wmVisibleIds(){
  if(!WMV.graph)return [];
  let stage=wmStageData();
  if(WMV.mode==='full')return (WMV.graph.nodes||[]).map(n=>n.id);
  let base=wmThoughtCore(stage),set=new Set(base),layer=WMV.mode==='meaning'?'의미':WMV.mode==='order'?'순서':null;
  if(WMV.scope===0)return [...set];
  let candidates=[];
  (WMV.graph.edges||[]).forEach(e=>{
    if(layer&&e.layer!==layer&&e.layer!=='생성')return;
    if(WMV.mode==='thought'&&e.layer==='순서'&&WMV.scope<2)return;
    let one=set.has(e.source),two=set.has(e.target);if(!one&&!two)return;
    let other=one?e.target:e.source;if(set.has(other))return;
    let lp=e.layer==='의미'?3:e.layer==='생성'?4:e.layer==='연상'?2:1;
    candidates.push({id:other,score:lp+Number(e.weight||0)});
  });
  candidates.sort((a,b)=>b.score-a.score);
  let cap=WMV.mode==='thought'?(WMV.scope===1?30:48):(WMV.scope===1?42:65);
  for(let x of candidates){if(set.size>=cap)break;set.add(x.id)}
  return [...set];
}

function wmThoughtPositions(ids,w,h){
  let stage=wmStageData(),pos={},path=wmRecentPath(stage),cand=wmCandidateIds(stage).filter(x=>!path.includes(x)).slice(0,4),active=wmActiveIds(stage,7).filter(x=>!path.includes(x)&&!cand.includes(x));
  if(path.length){let x0=.10,x1=.67;path.forEach((id,i)=>{let t=path.length===1?1:i/(path.length-1);pos[id]={x:x0+(x1-x0)*t,y:.53}})}
  else{let core=ids.slice(0,1);if(core[0])pos[core[0]]={x:.45,y:.53}}
  cand.forEach((id,i)=>{let ys=[.20,.38,.68,.84];pos[id]={x:.86,y:ys[i]||(.2+i*.16)}});
  active.forEach((id,i)=>{let ang=(-Math.PI*.85)+(i/Math.max(1,active.length-1))*Math.PI*1.7;pos[id]={x:.43+Math.cos(ang)*.27,y:.52+Math.sin(ang)*.31}});
  let leftovers=ids.filter(id=>!pos[id]);leftovers.forEach((id,i)=>{let hsh=wmHash(id),ang=((hsh%10000)/10000)*Math.PI*2,r=.40+.035*(i%3);pos[id]={x:.48+Math.cos(ang)*r,y:.52+Math.sin(ang)*r*.78}});
  return pos;
}

function wmGlobalXY(p,w,h){return {x:(p.x-.5)*WMV.zoom*w+w*.5+WMV.panX,y:(p.y-.5)*WMV.zoom*h+h*.5+WMV.panY}}
function wmArrow(ctx,a,b,color,width,alpha,directed,dash){
  ctx.save();ctx.globalAlpha=alpha;ctx.strokeStyle=color;ctx.lineWidth=width;if(dash)ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();ctx.setLineDash([]);
  if(directed){let ang=Math.atan2(b.y-a.y,b.x-a.x),s=5+width;ctx.fillStyle=color;ctx.beginPath();ctx.moveTo(b.x,b.y);ctx.lineTo(b.x-Math.cos(ang-.55)*s,b.y-Math.sin(ang-.55)*s);ctx.lineTo(b.x-Math.cos(ang+.55)*s,b.y-Math.sin(ang+.55)*s);ctx.closePath();ctx.fill()}ctx.restore();
}

function wmEdgeAllowed(e,visible,core){
  if(!visible.has(e.source)||!visible.has(e.target))return false;
  if(e.layer==='생성')return true;
  if(WMV.mode==='meaning')return e.layer==='의미';
  if(WMV.mode==='order')return e.layer==='순서';
  if(WMV.mode==='full')return e.layer!=='생성';
  if(WMV.mode==='thought'){
    if(e.layer==='의미')return core.has(e.source)||core.has(e.target);
    if(e.layer==='연상')return WMV.scope>0&&(core.has(e.source)||core.has(e.target));
    if(e.layer==='순서')return WMV.scope>1&&(core.has(e.source)||core.has(e.target));
  }
  return false;
}

function wmRender(){
  let c=document.getElementById('wmGraphCanvas');if(!c||!WMV.graph)return;
  let d=c._scale||1,ctx=c.getContext('2d'),w=c.width/d,h=c.height/d;ctx.setTransform(d,0,0,d,0,0);ctx.clearRect(0,0,w,h);
  let stage=wmStageData(),ids=wmVisibleIds(),visible=new Set(ids),core=new Set(wmThoughtCore(stage)),path=wmRecentPath(stage),pathPairs=new Set(),candMap=wmCandidateMap(stage),active=stage.activation||{};
  WMV.visible=visible;for(let i=1;i<path.length;i++)pathPairs.add(path[i-1]+'\u001f'+path[i]);
  let local=WMV.mode==='thought'?wmThoughtPositions(ids,w,h):null,screen={};
  ids.forEach(id=>{let p=local?.[id]||WMV.pos[id];if(!p)return;screen[id]=WMV.mode==='thought'?{x:p.x*w,y:p.y*h}:wmGlobalXY(p,w,h)});WMV.screenPos=screen;

  let edgeStyle={연상:['#56606d',.20],의미:['#d4a654',.58],순서:['#6688c7',.30],생성:['#74e5a4',1]};
  (WMV.graph.edges||[]).forEach(e=>{if(!wmEdgeAllowed(e,visible,core))return;let a=screen[e.source],b=screen[e.target];if(!a||!b)return;let st=edgeStyle[e.layer]||['#555',.2],isPath=pathPairs.has(e.source+'\u001f'+e.target),width=isPath?3.5:Math.max(.45,Math.min(1.8,Number(e.weight||.2)*1.5));wmArrow(ctx,a,b,isPath?'#8ff0b6':st[0],width,isPath?1:st[1],!!e.directed)});

  if(path.length>1){for(let i=1;i<path.length;i++){let a=screen[path[i-1]],b=screen[path[i]];if(a&&b)wmArrow(ctx,a,b,'#8ff0b6',3.7,1,true)}}

  if(WMV.mode==='thought'&&path.length){let source=path.length>1?path[path.length-2]:path[path.length-1],a=screen[source];if(a){wmCandidateIds(stage).slice(0,4).forEach(id=>{if(id===stage.selected||path.includes(id))return;let b=screen[id];if(b)wmArrow(ctx,a,b,'#e9bd67',1.4,.58,true,[4,4])})}}

  let freqMax=Math.max(1,...(WMV.graph.nodes||[]).map(n=>Number(n.frequency||0))),topFreq=[...(WMV.graph.nodes||[])].sort((a,b)=>Number(b.frequency||0)-Number(a.frequency||0)).slice(0,12).map(n=>n.id),activeTop=new Set(wmActiveIds(stage,8));
  ids.forEach(id=>{
    let node=wmNodeById(id),q=screen[id];if(!node||!q)return;let a=Number(active[id]||node.activation||0),inPath=path.includes(id),selected=id===stage.selected,candidate=!!candMap[id]&&!selected;
    let base=WMV.mode==='full'?2.4+3.2*Math.sqrt(Number(node.frequency||0)/freqMax):3.2;
    let r=base+(activeTop.has(id)?Math.min(6,a*7):0)+(inPath?2.5:0)+(selected?2.5:0)+(candidate?1.4:0);
    ctx.beginPath();ctx.arc(q.x,q.y,r,0,Math.PI*2);ctx.fillStyle=selected?'#9af2bd':inPath?'#7edfa5':candidate?'#f1c56e':activeTop.has(id)?'#70b9ef':'#66707d';ctx.globalAlpha=selected||inPath?1:candidate?.92:activeTop.has(id)?.78:.30;ctx.fill();ctx.globalAlpha=1;
    if(candidate){ctx.beginPath();ctx.arc(q.x,q.y,r+3,0,Math.PI*2);ctx.strokeStyle='#f1c56e';ctx.globalAlpha=.42;ctx.lineWidth=1;ctx.stroke();ctx.globalAlpha=1}
    let showLabel=inPath||candidate||activeTop.has(id)||(WMV.mode==='full'&&topFreq.includes(id))||(WMV.mode!=='thought'&&core.has(id));
    if(showLabel){let label=node.label;if(candidate){let p=Number(candMap[id]?.['선택확률']||0);if(p>0)label+=' '+(p*100).toFixed(0)+'%'}ctx.font=(inPath||selected?'700 ':'')+(selected?'13':'11')+'px system-ui';ctx.fillStyle='#f2f4f7';ctx.globalAlpha=inPath||candidate?1:.80;ctx.fillText(label,q.x+r+4,q.y+4);ctx.globalAlpha=1}
  });
  wmUpdateStageInfo();
}

function wmUpdateStageInfo(){
  let el=document.getElementById('wmStageInfo');if(!el)return;let s=wmStageData(),parts=['<div class="wmv-title">'+wmEsc(s.name||'장기기억 지도')+' <span class="meta">'+(WMV.stage+1)+'/'+Math.max(1,WMV.stages.length)+'</span></div>'];
  if(s.message)parts.push('<div>'+wmEsc(s.message)+'</div>');
  if((s.path||[]).length)parts.push('<div class="meta" style="margin-top:4px">전체 경로: '+s.path.map(wmEsc).join(' → ')+'</div>');
  if(s.selected)parts.push('<div class="wmv-choice">현재 선택 <b>'+wmEsc(s.selected_surface||s.selected)+'</b><br><span class="meta">선택확률 '+(Number(s.selection_probability||0)*100).toFixed(1)+'% · 문법 적합 '+Number(s.grammar_fit||0).toFixed(3)+(s.candidate_origins?.length?' · '+s.candidate_origins.map(wmEsc).join(' / '):'')+'</span></div>');
  let cand=(s.candidates||[]).slice(0,4);if(cand.length){parts.push('<div class="wmv-cands">'+cand.map((x,i)=>'<div class="wmv-cand"><span>'+(i+1)+'. '+wmEsc(x['표면형']||x['표제어']||'')+'</span><b>'+(Number(x['선택확률']||0)*100).toFixed(1)+'%</b></div>').join('')+'</div>')}
  if(s.grammar_pattern)parts.push('<div class="meta" style="margin-top:5px">문법 패턴: '+wmEsc(s.grammar_pattern)+'</div>');
  if(s.text)parts.push('<div class="wmv-choice">완성 문장<br><b>'+wmEsc(s.text)+'</b></div>');
  el.innerHTML=parts.join('');
}

function wmSetGraph(graph,stages){
  if(!graph)return;WMV.graph=graph;WMV.stages=(stages&&stages.length)?stages:[{name:'장기기억 지도',kind:'기본',activation:{},path:[],candidate_ids:[],message:'Vault의 장기 WordMap입니다.'}];WMV.stage=stages&&stages.length?Math.min(2,WMV.stages.length-1):0;WMV.zoom=1;WMV.panX=0;WMV.panY=0;WMV.scope=1;
  wmInitialLayout(graph);let slider=document.getElementById('wmStage');slider.max=Math.max(0,WMV.stages.length-1);slider.value=WMV.stage;
  let st=graph.stats||{},layers=st.layers||{};document.getElementById('wmGraphInfo').textContent='불러온 서브그래프 '+Number(st.shown_nodes||0)+'개 · 전체 WordMap '+Number(st.total_nodes||0).toLocaleString()+'개 · 의미 '+Number(layers['의미']||0)+' · 순서 '+Number(layers['순서']||0)+' · 연상 '+Number(layers['연상']||0);
  wmUpdateScopeLabel();setTimeout(()=>{wmResetView();wmResize()},30);
}

async function wmLoadGraph(){try{document.getElementById('wmStageInfo').textContent='Vault graph.json 불러오는 중...';let g=await api('/api/graph');wmSetGraph(g,null)}catch(e){document.getElementById('wmStageInfo').textContent='그래프 오류: '+e.message}}
function wmUseAskResult(d){if(d&&d.visual_graph)wmSetGraph(d.visual_graph,d['시각화단계']||[])}

function wmSetMode(mode){WMV.mode=mode;document.querySelectorAll('[data-wm-mode]').forEach(b=>b.classList.toggle('active',b.dataset.wmMode===mode));if(mode==='full')WMV.scope=2;else if(WMV.scope>1)WMV.scope=1;wmUpdateScopeLabel();wmResetView()}
function wmCycleScope(){WMV.scope=(WMV.scope+1)%3;wmUpdateScopeLabel();wmResetView()}
function wmUpdateScopeLabel(){let b=document.getElementById('wmScope');if(b)b.textContent=['핵심만','주변 1홉','주변 넓게'][WMV.scope]}
function wmSetStage(i){WMV.stage=Math.max(0,Math.min(WMV.stages.length-1,Number(i)||0));document.getElementById('wmStage').value=WMV.stage;document.getElementById('wmNodeInfo').style.display='none';wmResetView()}
function wmPrevStage(){wmSetStage(WMV.stage-1)}
function wmNextStage(){wmSetStage(WMV.stage+1)}
function wmTogglePlay(){let b=document.getElementById('wmPlay');if(WMV.timer){clearInterval(WMV.timer);WMV.timer=null;b.textContent='▶ 재생';return}if(WMV.stage>=WMV.stages.length-1)wmSetStage(0);b.textContent='■ 정지';WMV.timer=setInterval(()=>{if(WMV.stage>=WMV.stages.length-1){clearInterval(WMV.timer);WMV.timer=null;b.textContent='▶ 재생';return}wmNextStage()},950)}

function wmAutoFocus(){
  if(WMV.mode==='thought'){WMV.zoom=1;WMV.panX=0;WMV.panY=0;return}
  let c=document.getElementById('wmGraphCanvas');if(!c||!WMV.graph)return;let ids=wmVisibleIds().filter(id=>WMV.pos[id]);if(!ids.length)return;let xs=ids.map(id=>WMV.pos[id].x),ys=ids.map(id=>WMV.pos[id].y),minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys),span=Math.max(.13,maxX-minX,maxY-minY),cx=(minX+maxX)/2,cy=(minY+maxY)/2,r=c.getBoundingClientRect();WMV.zoom=Math.max(.72,Math.min(3.2,.72/span));WMV.panX=-(cx-.5)*WMV.zoom*r.width;WMV.panY=-(cy-.5)*WMV.zoom*r.height;
}
function wmResetView(){WMV.zoom=1;WMV.panX=0;WMV.panY=0;wmAutoFocus();wmRender()}

function wmPickNode(clientX,clientY){let c=document.getElementById('wmGraphCanvas'),r=c.getBoundingClientRect(),x=clientX-r.left,y=clientY-r.top,best=null,dist=1e9;Object.entries(WMV.screenPos||{}).forEach(([id,p])=>{let d=(p.x-x)**2+(p.y-y)**2;if(d<dist){dist=d;best=id}});return dist<900?best:null}
function wmShowNode(id){let node=wmNodeById(id),el=document.getElementById('wmNodeInfo');if(!node||!el)return;let s=wmStageData(),a=Number((s.activation||{})[id]||node.activation||0),cand=wmCandidateMap(s)[id];el.style.display='block';el.innerHTML='<b>'+wmEsc(node.label)+'</b> · '+wmEsc(node.pos||'미분류')+'<br><span class="meta">빈도 '+Number(node.frequency||0)+(a?' · 현재 활성 '+a.toFixed(3):'')+(cand?' · 후보확률 '+(Number(cand['선택확률']||0)*100).toFixed(1)+'%':'')+'</span>'}

window.addEventListener('resize',wmResize);
let wmCanvas=document.getElementById('wmGraphCanvas');
wmCanvas.addEventListener('wheel',e=>{if(WMV.mode==='thought')return;e.preventDefault();WMV.zoom=Math.max(.55,Math.min(4,WMV.zoom*(e.deltaY<0?1.12:.89)));wmRender()},{passive:false});
wmCanvas.addEventListener('pointerdown',e=>{WMV.drag={x:e.clientX,y:e.clientY,px:WMV.panX,py:WMV.panY};WMV.moved=false;wmCanvas.setPointerCapture(e.pointerId)});
wmCanvas.addEventListener('pointermove',e=>{if(!WMV.drag||WMV.mode==='thought')return;let dx=e.clientX-WMV.drag.x,dy=e.clientY-WMV.drag.y;if(Math.abs(dx)+Math.abs(dy)>5)WMV.moved=true;WMV.panX=WMV.drag.px+dx;WMV.panY=WMV.drag.py+dy;wmRender()});
wmCanvas.addEventListener('pointerup',e=>{if(!WMV.moved){let id=wmPickNode(e.clientX,e.clientY);if(id)wmShowNode(id)}WMV.drag=null});

const wmOriginalApi=window.api;
window.api=async function(p,m='GET',b=null){let d=await wmOriginalApi(p,m,b);if(p==='/api/ask')wmUseAskResult(d);if(p==='/api/select-vault'||p==='/api/rebuild'||p==='/api/ingest')setTimeout(wmLoadGraph,250);return d};
setTimeout(wmLoadGraph,450);
</script>
'''

    if "</main>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</main>", visual_html + "\n</main>", 1,
        )
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</body>", script + "\n</body>", 1,
        )
    return wordmap_mobile
