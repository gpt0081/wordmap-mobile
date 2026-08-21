from __future__ import annotations

VERSION = "0.18.0"


def apply(wordmap_mobile):
    style = r'''
<style id="wuCognitionStyles018">
#wuCognitionPanel{display:none;margin:8px 0;padding:10px 11px;border:1px solid #303b48;border-radius:11px;background:#10161d;color:#dbe4ed}
#wuCognitionPanel.visible{display:block}
.wu-cog-title{font-size:10px;font-weight:800;color:#9fb6ca;margin-bottom:7px}
.wu-cog-line{font-size:11px;line-height:1.55;overflow-wrap:anywhere;word-break:break-word;margin:3px 0}
.wu-cog-label{color:#8998a8;margin-right:5px}
.wu-cog-path{color:#dfe9f2}
.wu-cog-muted{color:#7f8b98}
</style>
'''
    script = r'''
<script id="wuCognitionScript018">
(function(){
function escText(x){return String(x==null?'':x)}
function ensurePanel(){
  let p=document.getElementById('wuCognitionPanel');if(p)return p;
  let hero=document.getElementById('wuChatHero');if(!hero)return null;
  p=document.createElement('div');p.id='wuCognitionPanel';
  hero.parentNode.insertBefore(p,hero.nextSibling);return p;
}
function renderCog(d){
  let p=ensurePanel();if(!p)return;
  let primes=((d||{})['점화상태']||{})['사용전']||[];
  let streams=(d||{})['연상폭포']||[];
  let inhibited=(d||{})['연상억제']||[];
  if(!primes.length&&!streams.length&&!inhibited.length){p.classList.remove('visible');p.textContent='';return}
  p.textContent='';
  let title=document.createElement('div');title.className='wu-cog-title';title.textContent='점화 · 연상 사고상태';p.appendChild(title);
  if(primes.length){
    let line=document.createElement('div');line.className='wu-cog-line';
    let label=document.createElement('span');label.className='wu-cog-label';label.textContent='점화';line.appendChild(label);
    line.appendChild(document.createTextNode(primes.slice(0,6).map(x=>escText(x['표제어'])+' '+Number(x['점화도']||0).toFixed(2)).join('  ')));p.appendChild(line);
  }
  if(streams.length){
    let line=document.createElement('div');line.className='wu-cog-line';
    let label=document.createElement('span');label.className='wu-cog-label';label.textContent='연상';line.appendChild(label);
    let span=document.createElement('span');span.className='wu-cog-path';span.textContent=(streams[0]['경로']||[]).join(' → ')+'  '+Number(streams[0]['유효활성']||0).toFixed(2);line.appendChild(span);p.appendChild(line);
  }
  if(inhibited.length){
    let line=document.createElement('div');line.className='wu-cog-line wu-cog-muted';
    let label=document.createElement('span');label.className='wu-cog-label';label.textContent='억제';line.appendChild(label);
    line.appendChild(document.createTextNode(inhibited.slice(0,5).map(x=>escText(x['표제어'])+' '+Number(x['억제']||0).toFixed(2)).join('  ')));p.appendChild(line);
  }
  p.classList.add('visible');
}
function install(){
  let sub=document.querySelector('.wu-brand-sub');if(sub)sub.textContent='Utility Workspace · v0.18.0';
  ensurePanel();
  let old=window.wuHandleAsk;
  if(typeof old==='function'&&!old._cog018){
    let wrapped=function(d){let out=old.apply(this,arguments);try{renderCog(d)}catch(e){}return out};wrapped._cog018=true;window.wuHandleAsk=wrapped;
    return true;
  }
  return false;
}
function boot(){if(install())return;let n=0,t=setInterval(()=>{n++;if(install()||n>50)clearInterval(t)},100)}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(boot,0));else setTimeout(boot,0);
})();
</script>
'''
    if "</head>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</head>", style + "\n</head>", 1)
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</body>", script + "\n</body>", 1)
    return wordmap_mobile
