from __future__ import annotations

VERSION = "0.17.2"


def apply(wordmap_mobile):
    style = r'''
<style id="wuChatPatch0172">
#wuChatCard,#wuChatCard .row,#wuChatCard .row>*,#wuChatHero,#wuAnswerText,#wuAnswerMeta,#results,#results>*,#wuRecent{min-width:0;max-width:100%;box-sizing:border-box}
#wuAnswerText,#wuAnswerMeta,#results,#results p,#results div,#results span,#results td,#results th,#results li,#results pre,#wuDebugDetails pre{overflow-wrap:anywhere;word-break:break-word}
#results pre,#wuDebugDetails pre{white-space:pre-wrap;overflow-x:hidden}
#q{white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word}
#wuRecent{display:flex;flex-wrap:wrap;align-items:flex-start;overflow:visible;gap:6px}
#wuRecent .meta{width:100%;white-space:normal!important}
.wu-recent-chip{white-space:normal!important;max-width:100%;height:auto;min-height:34px;text-align:left;line-height:1.4;overflow-wrap:anywhere;word-break:break-word}
#wuDeleteHistoryBtn{background:#2b2023;border:1px solid #5a343b;color:#f0c6cc}
</style>
'''
    script = r'''
<script id="wuChatPatchScript0172">
(function(){
async function wuDeleteHistory0172(){
  if(!confirm('대화내역과 현재 대화 문맥을 모두 삭제할까요?'))return;
  try{if(window.WU&&WU.recentKey)localStorage.removeItem(WU.recentKey)}catch(e){}
  try{if(typeof api==='function')await api('/api/dialogue/start','POST',{session_id:'web-'+Date.now()})}catch(e){}
  let q=document.getElementById('q');if(q)q.value='';
  let r=document.getElementById('results');if(r)r.innerHTML='';
  let h=document.getElementById('wuChatHero');if(h)h.classList.remove('visible');
  let a=document.getElementById('wuAnswerText');if(a)a.textContent='';
  let m=document.getElementById('wuAnswerMeta');if(m)m.textContent='';
  let d=document.getElementById('wuDebugDetails');if(d)d.open=false;
  let recent=document.getElementById('wuRecent');if(recent)recent.innerHTML='';
  if(typeof wuRenderRecent==='function')wuRenderRecent();
  if(typeof wuSwitch==='function')wuSwitch('chat',false);
}
window.wuDeleteChatHistory=wuDeleteHistory0172;
function install(){
  let tools=document.getElementById('wuAskTools');
  if(!tools||document.getElementById('wuDeleteHistoryBtn'))return false;
  let b=document.createElement('button');b.type='button';b.id='wuDeleteHistoryBtn';b.className='wu-small-btn';b.textContent='대화내역 삭제';b.onclick=wuDeleteHistory0172;tools.appendChild(b);return true;
}
function boot(){if(install())return;let n=0,t=setInterval(()=>{n++;if(install()||n>40)clearInterval(t)},100)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,0));else setTimeout(boot,0);
})();
</script>
'''
    if "</head>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</head>", style + "\n</head>", 1)
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</body>", script + "\n</body>", 1)
    return wordmap_mobile
