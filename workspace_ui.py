from __future__ import annotations

VERSION = "0.17.0"


def apply(wordmap_mobile):
    style = r'''
<style id="wuStyles">
:root{
  --wu-bg:#0c0f14;
  --wu-panel:#151922;
  --wu-panel2:#10141b;
  --wu-line:#2a303a;
  --wu-text:#eef1f5;
  --wu-muted:#9aa4b2;
  --wu-accent:#9fd3ff;
  --wu-good:#91d7a8;
  --wu-warn:#ffd07a;
  --wu-danger:#ff9a9a;
}
html{scroll-behavior:smooth}
body{background:var(--wu-bg);color:var(--wu-text);padding-bottom:12px}
main{max-width:1180px;padding:14px 14px 90px}
main>h1{display:none}
.card{background:var(--wu-panel);border-color:var(--wu-line);border-radius:14px;margin:0 0 12px;padding:14px}
.card h2{margin:0 0 10px;font-size:18px;letter-spacing:-.02em}
.card h3{letter-spacing:-.02em}
textarea,input,select{border-color:#39414e;background:#0c1016;border-radius:10px;outline:none}
textarea:focus,input:focus,select:focus{border-color:#729fc6;box-shadow:0 0 0 2px rgba(114,159,198,.15)}
button{min-height:42px;border-radius:10px;cursor:pointer}
button:disabled{opacity:.45;cursor:not-allowed}
pre{max-height:360px;overflow:auto;border:1px solid #242a33}

#wuTopbar{position:sticky;top:0;z-index:80;background:rgba(12,15,20,.94);backdrop-filter:blur(14px);border-bottom:1px solid var(--wu-line)}
.wu-top-inner{max-width:1180px;margin:auto;padding:9px 14px;display:flex;align-items:center;gap:10px}
.wu-brand{display:flex;align-items:center;gap:9px;min-width:150px}
.wu-logo{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:#e9edf2;color:#111;font-weight:900;font-size:14px}
.wu-brand-title{font-weight:850;line-height:1.05;letter-spacing:-.03em}.wu-brand-sub{font-size:10px;color:var(--wu-muted);margin-top:3px}
.wu-status{display:flex;gap:6px;align-items:center;min-width:0;flex:1;overflow:auto;scrollbar-width:none}.wu-status::-webkit-scrollbar{display:none}
.wu-chip{white-space:nowrap;padding:5px 8px;border:1px solid var(--wu-line);border-radius:999px;background:#11161d;color:#c6ced8;font-size:10px}
.wu-chip strong{color:#f2f4f7}.wu-top-actions{display:flex;gap:6px}.wu-icon-btn{min-height:34px;height:34px;padding:0 10px;background:#202630;color:#dce2e9;border:1px solid #343c48;font-size:11px}

#wuDesktopNav{position:sticky;top:53px;z-index:70;display:grid;grid-template-columns:repeat(6,1fr);gap:5px;padding:7px;background:rgba(12,15,20,.94);backdrop-filter:blur(12px);border:1px solid var(--wu-line);border-radius:12px;margin-bottom:12px}
.wu-nav-btn{display:flex;justify-content:center;align-items:center;gap:7px;min-height:38px;padding:7px 8px;background:#171c24;color:#aeb8c5;border:1px solid transparent;font-size:12px}
.wu-nav-btn.active{background:#e8edf2;color:#111;border-color:#e8edf2}.wu-nav-icon{font-size:14px}
#wuBottomNav{display:none}
.wu-panel{display:none}.wu-panel.active{display:block}.wu-panel-grid{display:grid;gap:12px}
.wu-section-note{padding:9px 11px;margin-bottom:10px;border:1px solid var(--wu-line);border-radius:10px;background:var(--wu-panel2);font-size:11px;color:var(--wu-muted);line-height:1.5}

#wuChatHero{display:none;margin:10px 0 8px;padding:14px;border:1px solid #354557;border-radius:13px;background:linear-gradient(180deg,#17202a,#121820)}
#wuChatHero.visible{display:block}.wu-answer-label{font-size:10px;color:#9cb7cd;margin-bottom:7px}.wu-answer-text{font-size:19px;font-weight:750;line-height:1.55;letter-spacing:-.025em;word-break:keep-all}.wu-answer-meta{font-size:10px;color:var(--wu-muted);margin-top:8px}
#wuAskTools{display:flex;gap:7px;flex-wrap:wrap;margin:8px 0 2px}.wu-small-btn{min-height:34px;padding:6px 9px;font-size:11px;background:#252c36;color:#dce2e9}
#wuRecent{display:flex;gap:6px;overflow:auto;margin-top:8px;padding-bottom:2px;scrollbar-width:none}#wuRecent::-webkit-scrollbar{display:none}.wu-recent-chip{white-space:nowrap;border:1px solid #343c48;background:#11161d;color:#bdc6d1;border-radius:999px;padding:6px 9px;font-size:10px;cursor:pointer}
#wuDebugDetails{margin-top:9px;border-top:1px solid var(--wu-line);padding-top:9px}#wuDebugDetails>summary{cursor:pointer;color:#aeb8c5;font-size:11px;font-weight:750;user-select:none}#wuDebugDetails[open]>summary{margin-bottom:8px}
#wuDebugDetails #results{margin-top:0}

.wu-quick-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin:8px 0}.wu-quick-card{padding:10px;border:1px solid var(--wu-line);border-radius:10px;background:#11161d;cursor:pointer}.wu-quick-card b{display:block;font-size:12px}.wu-quick-card span{display:block;margin-top:3px;color:var(--wu-muted);font-size:10px;line-height:1.4}
.wu-hidden{display:none!important}

@media(min-width:900px){
  #wuPanel-corpus .wu-panel-grid{grid-template-columns:minmax(320px,.8fr) minmax(460px,1.2fr);align-items:start}
  #wuPanel-manage .wu-panel-grid{grid-template-columns:minmax(320px,.75fr) minmax(520px,1.25fr);align-items:start}
  #wuPanel-learn .wu-panel-grid{grid-template-columns:1fr}
}
@media(max-width:760px){
  body{padding-bottom:70px}main{padding:10px 10px 88px}.card{padding:12px;border-radius:12px}.card h2{font-size:17px}
  .wu-top-inner{padding:8px 10px}.wu-brand{min-width:auto}.wu-brand-title{font-size:14px}.wu-brand-sub{display:none}.wu-logo{width:32px;height:32px}.wu-status{gap:4px}.wu-chip{font-size:9px;padding:4px 7px}.wu-chip:nth-child(n+4){display:none}.wu-top-actions{display:none}
  #wuDesktopNav{display:none}
  #wuBottomNav{display:grid;position:fixed;z-index:100;bottom:0;left:0;right:0;grid-template-columns:repeat(6,1fr);gap:2px;padding:6px max(5px,env(safe-area-inset-right)) calc(6px + env(safe-area-inset-bottom)) max(5px,env(safe-area-inset-left));background:rgba(10,13,18,.97);backdrop-filter:blur(14px);border-top:1px solid var(--wu-line)}
  #wuBottomNav .wu-nav-btn{min-height:48px;padding:4px 1px;display:flex;flex-direction:column;gap:2px;border-radius:9px;background:transparent;font-size:9px}
  #wuBottomNav .wu-nav-btn.active{background:#242b35;color:#fff;border-color:#313a46}.wu-nav-icon{font-size:16px}
  .wu-answer-text{font-size:17px}.wu-quick-grid{grid-template-columns:1fr}.row>*{min-width:0}
  textarea{min-height:120px}
}
</style>
'''

    script = r'''
<script id="wuScript">
const WU={version:'0.17.0',tab:'chat',recentKey:'wordmap_recent_questions_v017',apiWrapped:false};
const WU_TABS=[
  ['chat','💬','대화'],['map','🗺️','지도'],['corpus','🗂️','말뭉치'],
  ['learn','🧠','학습'],['experiment','🧪','실험'],['manage','⚙️','관리']
];
function wuEsc(s){return typeof esc==='function'?esc(s):String(s)}
function wuSectionByHeading(text){return [...document.querySelectorAll('main > section.card')].find(s=>(s.querySelector('h2')?.textContent||'').includes(text))||null}
function wuMake(tag,cls,html){let x=document.createElement(tag);if(cls)x.className=cls;if(html!==undefined)x.innerHTML=html;return x}

function wuBuildNav(id){
  let nav=wuMake('nav','');nav.id=id;
  WU_TABS.forEach(([key,icon,label])=>{
    let b=wuMake('button','wu-nav-btn','<span class="wu-nav-icon">'+icon+'</span><span>'+label+'</span>');
    b.type='button';b.dataset.tab=key;b.onclick=()=>wuSwitch(key);nav.appendChild(b);
  });
  return nav;
}

function wuBuild(){
  if(document.getElementById('wuWorkspace'))return;
  let main=document.querySelector('main');if(!main)return;
  main.id='wuWorkspace';

  let top=wuMake('header','');top.id='wuTopbar';
  top.innerHTML='<div class="wu-top-inner"><div class="wu-brand"><div class="wu-logo">WM</div><div><div class="wu-brand-title">WordMap</div><div class="wu-brand-sub">Utility Workspace · v'+WU.version+'</div></div></div><div class="wu-status"><span class="wu-chip" id="wuVaultChip">Vault · 확인 중</span><span class="wu-chip" id="wuCorpusChip">Corpus · —</span><span class="wu-chip" id="wuNodeChip">노드 · —</span><span class="wu-chip" id="wuPairChip">연결 · —</span></div><div class="wu-top-actions"><button class="wu-icon-btn" onclick="wuNewDialogue()">새 대화</button><button class="wu-icon-btn" onclick="wuRefreshAll()">↻ 새로고침</button></div></div>';
  document.body.insertBefore(top,main);

  let desktopNav=wuBuildNav('wuDesktopNav');
  main.insertBefore(desktopNav,main.firstChild);
  document.body.appendChild(wuBuildNav('wuBottomNav'));

  let baseVault=wuSectionByHeading('Vault');
  let baseIngest=wuSectionByHeading('말뭉치 → WordMap');
  let baseAsk=wuSectionByHeading('질문 → 연결 단어');
  let visual=document.getElementById('wmVisualCard');
  let corpus=document.getElementById('corpusManagerCard');
  let health=document.getElementById('nodeHealthCard');
  let learning=document.getElementById('learningCard');
  let experiment=document.getElementById('experimentCard');

  if(baseVault){baseVault.id='wuVaultCard';let h=baseVault.querySelector('h2');if(h)h.textContent='Vault 연결'}
  if(baseIngest){baseIngest.id='wuIngestCard';let h=baseIngest.querySelector('h2');if(h)h.textContent='말뭉치 추가 / 재생성'}
  if(baseAsk){baseAsk.id='wuChatCard';let h=baseAsk.querySelector('h2');if(h)h.textContent='대화'}
  if(visual){let h=visual.querySelector('h2');if(h)h.textContent='사고 지도'}
  if(health){let h=health.querySelector('h2');if(h)h.textContent='노드 건강도'}
  if(learning){let h=learning.querySelector('h2');if(h)h.textContent='문맥지도 / Credit Backprop'}

  let panels={};
  WU_TABS.forEach(([key])=>{
    let p=wuMake('div','wu-panel');p.id='wuPanel-'+key;p.dataset.tab=key;
    let g=wuMake('div','wu-panel-grid');p.appendChild(g);panels[key]=g;main.appendChild(p);
  });
  if(baseAsk)panels.chat.appendChild(baseAsk);
  if(visual)panels.map.appendChild(visual);
  if(baseIngest)panels.corpus.appendChild(baseIngest);
  if(corpus)panels.corpus.appendChild(corpus);
  if(learning)panels.learn.appendChild(learning);
  if(experiment)panels.experiment.appendChild(experiment);
  if(baseVault)panels.manage.appendChild(baseVault);
  if(health)panels.manage.appendChild(health);

  wuEnhanceChat(baseAsk);
  wuAddPanelNotes(panels);
  wuBindShortcuts();
  wuWireApiSoon();
  wuWrapRefreshSoon();
  let saved='chat';try{saved=localStorage.getItem('wordmap_ui_tab')||'chat'}catch(e){}
  if(!WU_TABS.some(x=>x[0]===saved))saved='chat';wuSwitch(saved,false);
  setTimeout(wuRefreshStatus,120);setTimeout(wuRefreshStatus,700);
}

function wuAddPanelNotes(p){
  const notes={
    map:'생성 경로와 경쟁 후보를 먼저 보고, 필요할 때 의미 관계·단어 순서·전체 지도로 범위를 넓히세요.',
    corpus:'말뭉치 추가와 파일별 관리 기능을 한곳에 모았습니다. DEV/TEST 파일은 학습에서 잠깁니다.',
    learn:'문맥군을 확인하고 답변에 좋음/나쁨 피드백을 줘 사용가중치를 조정합니다.',
    experiment:'Corpus v1 무결성, Benchmark, B0~B3 Credit Backprop 실험을 실행합니다.',
    manage:'Vault 연결과 고립 노드 진단 등 운영·점검 기능을 모았습니다.'
  };
  Object.entries(notes).forEach(([key,text])=>{let n=wuMake('div','wu-section-note',text);p[key].insertBefore(n,p[key].firstChild)});
}

function wuEnhanceChat(card){
  if(!card)return;
  let q=document.getElementById('q'),results=document.getElementById('results');
  let send=[...card.querySelectorAll('button')].find(b=>(b.getAttribute('onclick')||'').includes('askQ'));
  if(send)send.textContent='질문 실행';
  if(q){q.placeholder='질문을 입력하세요. 예: 다람쥐는 무엇을 먹어?';q.setAttribute('enterkeyhint','send')}
  let hero=wuMake('div','');hero.id='wuChatHero';
  hero.innerHTML='<div class="wu-answer-label">대표 응답</div><div class="wu-answer-text" id="wuAnswerText"></div><div class="wu-answer-meta" id="wuAnswerMeta"></div>';
  if(results)results.parentNode.insertBefore(hero,results);

  let tools=wuMake('div','');tools.id='wuAskTools';tools.innerHTML='<button class="wu-small-btn" onclick="wuNewDialogue()">＋ 새 대화</button><button class="wu-small-btn" onclick="wuFocusQuestion()">⌨ 질문 입력</button>';
  if(results)results.parentNode.insertBefore(tools,results);
  let recent=wuMake('div','');recent.id='wuRecent';if(results)results.parentNode.insertBefore(recent,results);wuRenderRecent();

  if(results){
    let details=document.createElement('details');details.id='wuDebugDetails';
    let summary=document.createElement('summary');summary.textContent='내부 분석 보기 · 사건 / 문맥 / 후보확률 / 생성 trace';details.appendChild(summary);
    results.parentNode.insertBefore(details,results);details.appendChild(results);
  }
}

function wuSwitch(tab,scroll=true){
  WU.tab=tab;
  document.querySelectorAll('.wu-panel').forEach(p=>p.classList.toggle('active',p.dataset.tab===tab));
  document.querySelectorAll('.wu-nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));
  try{localStorage.setItem('wordmap_ui_tab',tab)}catch(e){}
  if(tab==='map')setTimeout(()=>{if(typeof wmResize==='function')wmResize();if(typeof wmRender==='function')wmRender()},80);
  if(tab==='corpus'&&typeof corpusLoadList==='function')setTimeout(corpusLoadList,30);
  if(tab==='learn'&&typeof learnLoadStatus==='function')setTimeout(learnLoadStatus,30);
  if(tab==='experiment'&&typeof expLoad==='function')setTimeout(expLoad,30);
  if(tab==='manage'){if(typeof refresh==='function')setTimeout(refresh,30);if(typeof nhLoad==='function')setTimeout(()=>nhLoad(''),100)}
  if(scroll)window.scrollTo({top:0,behavior:'smooth'});
}
window.wuSwitch=wuSwitch;

function wuAnswerFrom(d){
  let generated=d?.generated_sentences||[];
  if(generated.length&&generated[0]?.text)return generated[0].text;
  let answer=d?.['상황답변'];
  if(answer){let vals=answer['값']||[];if(vals.length)return (answer['역할']?answer['역할']+': ':'')+vals.join(', ')}
  let rows=d?.results||[];if(rows.length)return '관련 개념: '+rows.slice(0,5).map(x=>x.token).join(', ');
  return d?.warning||'생성된 응답이 없습니다.';
}
function wuHandleAsk(d){
  let hero=document.getElementById('wuChatHero'),text=document.getElementById('wuAnswerText'),meta=document.getElementById('wuAnswerMeta');if(!hero||!text)return;
  text.textContent=wuAnswerFrom(d);hero.classList.add('visible');
  let model=d?.['생성모델']||'WordMap';let ctx=d?.['문맥지도매칭']||[];let ctxTxt=ctx.length?' · 문맥 '+ctx.slice(0,2).map(x=>(x['표제어']||'')+' '+Number(x['적합도']||0).toFixed(2)).join(', '):'';
  meta.textContent=model+ctxTxt;
  let q=(document.getElementById('q')?.value||'').trim();if(q)wuRemember(q);
}

function wuWireApiSoon(){
  setTimeout(()=>{
    let old=window.api;if(typeof old!=='function'||old._wuWrapped)return;
    let wrapped=async function(p,m='GET',b=null){let d=await old(p,m,b);if(p==='/api/ask')setTimeout(()=>wuHandleAsk(d),0);return d};wrapped._wuWrapped=true;window.api=wrapped;WU.apiWrapped=true;
  },420);
}
function wuWrapRefreshSoon(){
  setTimeout(()=>{let old=window.refresh;if(typeof old!=='function'||old._wuWrapped)return;let f=async function(){let x=await old.apply(this,arguments);setTimeout(wuRefreshStatus,40);return x};f._wuWrapped=true;window.refresh=f},500);
}

async function wuRefreshStatus(){
  try{
    let d=typeof api==='function'?await api('/api/status'):(await fetch('/api/status')).json();
    let vault=d.vault?String(d.vault).split(/[\\/]/).filter(Boolean).pop():'미선택';
    let set=(id,label,val)=>{let e=document.getElementById(id);if(e)e.innerHTML=label+' · <strong>'+wuEsc(val)+'</strong>'};
    set('wuVaultChip','Vault',vault);set('wuCorpusChip','Corpus',Number(d.corpus_documents||0));set('wuNodeChip','노드',Number(d.nodes||0));set('wuPairChip','연결',Number(d.pairs||0));
  }catch(e){let v=document.getElementById('wuVaultChip');if(v)v.textContent='Vault · 연결 확인 필요'}
}
window.wuRefreshStatus=wuRefreshStatus;

async function wuRefreshAll(){
  try{if(typeof refresh==='function')await refresh();if(typeof expLoad==='function')await expLoad();if(WU.tab==='map'&&typeof wmLoadGraph==='function')await wmLoadGraph();await wuRefreshStatus()}catch(e){}
}
window.wuRefreshAll=wuRefreshAll;

async function wuNewDialogue(){
  try{
    if(typeof api==='function')await api('/api/dialogue/start','POST',{session_id:'web-'+Date.now()});
    let q=document.getElementById('q');if(q)q.value='';let r=document.getElementById('results');if(r)r.innerHTML='';let h=document.getElementById('wuChatHero');if(h)h.classList.remove('visible');let det=document.getElementById('wuDebugDetails');if(det)det.open=false;wuSwitch('chat');setTimeout(wuFocusQuestion,100);
  }catch(e){wuSwitch('chat');wuFocusQuestion()}
}
window.wuNewDialogue=wuNewDialogue;
function wuFocusQuestion(){wuSwitch('chat',false);let q=document.getElementById('q');if(q){q.focus();q.scrollIntoView({behavior:'smooth',block:'center'})}}
window.wuFocusQuestion=wuFocusQuestion;

function wuRecentList(){try{return JSON.parse(localStorage.getItem(WU.recentKey)||'[]')}catch(e){return []}}
function wuRemember(q){let a=wuRecentList().filter(x=>x!==q);a.unshift(q);a=a.slice(0,7);try{localStorage.setItem(WU.recentKey,JSON.stringify(a))}catch(e){}wuRenderRecent()}
function wuRenderRecent(){let box=document.getElementById('wuRecent');if(!box)return;let a=wuRecentList();box.innerHTML=a.length?'<span class="meta" style="white-space:nowrap;align-self:center">최근</span>':'';a.forEach(q=>{let b=wuMake('button','wu-recent-chip');b.type='button';b.textContent=q;b.onclick=()=>{let t=document.getElementById('q');if(t){t.value=q;t.focus()}};box.appendChild(b)})}

function wuBindShortcuts(){
  document.addEventListener('keydown',e=>{
    let tag=(e.target?.tagName||'').toLowerCase();
    if((e.ctrlKey||e.metaKey)&&e.key==='Enter'){if(typeof askQ==='function'){e.preventDefault();wuSwitch('chat',false);askQ()}return}
    if(e.altKey&&/^[1-6]$/.test(e.key)){e.preventDefault();wuSwitch(WU_TABS[Number(e.key)-1][0]);return}
    if(e.key==='/'&&!['input','textarea','select'].includes(tag)){e.preventDefault();wuFocusQuestion()}
  });
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',wuBuild);else setTimeout(wuBuild,0);
</script>
'''

    if "</head>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</head>", style + "\n</head>", 1)
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</body>", script + "\n</body>", 1)
    return wordmap_mobile
