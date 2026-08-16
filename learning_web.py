from __future__ import annotations

from urllib.parse import parse_qs, urlparse

VERSION = "0.15.0"


def apply(wordmap_mobile, core):
    Handler = wordmap_mobile.Handler
    original_get = Handler.do_GET
    original_post = Handler.do_POST

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        managed = {"/api/context-map/summary", "/api/context-map/item", "/api/learning/status"}
        if path not in managed:
            return original_get(self)
        try:
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            if path == "/api/context-map/summary":
                return self.send_json(core.context_map_summary(vault))
            if path == "/api/context-map/item":
                params = parse_qs(parsed.query)
                token = (params.get("token") or [""])[0]
                return self.send_json(core.context_map_get(vault, token))
            return self.send_json(core.learning_status(vault))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path not in {"/api/learning/feedback", "/api/learning/reset"}:
            return original_post(self)
        try:
            data = self.read_body()
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            if path == "/api/learning/reset":
                return self.send_json(core.learning_reset(vault))
            return self.send_json(core.learning_feedback(
                vault,
                data.get("trace_id", ""),
                data.get("reward", 0),
            ))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    Handler.do_GET = do_GET
    Handler.do_POST = do_POST

    section = r'''
<section class="card" id="learningCard">
<h2>문맥지도 · 역전파 학습</h2>
<div class="meta">문맥지도는 Corpus에서 장기 문맥군을 만들고, 역전파는 지식 자체가 아니라 문맥별 사용가중치와 억제가중치를 수정합니다.</div>

<div class="learn-grid" style="margin-top:12px">
  <div class="learn-box">
    <b>문맥지도</b>
    <div id="ctxSummary" class="meta" style="margin-top:6px">불러오는 중...</div>
    <div class="row" style="margin-top:8px">
      <input id="ctxToken" placeholder="표제어 예: 협력" style="margin:0">
      <button class="secondary" onclick="ctxLookup()">문맥군 보기</button>
    </div>
    <div id="ctxResult" class="meta" style="margin-top:8px"></div>
  </div>

  <div class="learn-box">
    <b>Credit Backprop</b>
    <div id="learnSummary" class="meta" style="margin-top:6px">불러오는 중...</div>
    <div id="learnLast" class="meta" style="margin-top:8px">먼저 질문을 실행하세요.</div>
    <div class="row learn-feedback" style="margin-top:8px">
      <button id="learnGood" onclick="learnFeedback(1)" disabled>좋음 +1</button>
      <button id="learnBad" class="secondary" onclick="learnFeedback(-1)" disabled>나쁨 -1</button>
    </div>
    <button class="secondary" style="margin-top:8px" onclick="learnReset()">학습 가중치 초기화</button>
  </div>
</div>
<div id="learnContextMatch" class="meta" style="margin-top:10px"></div>
<pre id="learnOut">대기 중</pre>
</section>
<style>
.learn-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.learn-box{padding:11px;border:1px solid #343944;border-radius:11px;background:#11151b}.learn-feedback{grid-template-columns:1fr 1fr}.ctx-sense{padding:8px;margin-top:7px;border-radius:8px;background:#171c24}.ctx-terms{color:#9fc5e8}.ctx-example{margin-top:4px;color:#aeb6c2;font-size:11px;line-height:1.45}@media(max-width:700px){.learn-grid{grid-template-columns:1fr}}
</style>
'''

    script = r'''
<script>
const LEARN15={trace:null,used:false};
function l15esc(s){return typeof esc==='function'?esc(s):String(s)}

async function learnLoadStatus(){
  try{
    let c=await api('/api/context-map/summary');
    let cs=document.getElementById('ctxSummary');if(cs)cs.textContent='분석 문장 '+Number(c.sentences||0)+' · 문맥 프로필 단어 '+Number(c.profiled_tokens||0)+' · 문맥군 '+Number(c.context_clusters||0)+' · 복수 문맥 단어 '+Number(c.multi_context_tokens||0);
    let l=await api('/api/learning/status');
    let ls=document.getElementById('learnSummary');if(ls)ls.textContent='학습 '+Number(l.updates||0)+'회 · 좋음 '+Number(l.positive||0)+' · 나쁨 '+Number(l.negative||0)+' · 학습 전이 '+Number(l.learned_transitions||0)+' · 문맥→후보 '+Number(l.learned_context_targets||0);
  }catch(e){let o=document.getElementById('learnOut');if(o)o.textContent='상태 오류: '+e.message;}
}

async function ctxLookup(){
  let token=(document.getElementById('ctxToken').value||'').trim(),out=document.getElementById('ctxResult');
  if(!token){out.textContent='표제어를 입력하세요.';return;}
  out.textContent='문맥군 검색 중...';
  try{
    let d=await api('/api/context-map/item?token='+encodeURIComponent(token));
    let html='<b>'+l15esc(d['표제어'])+'</b> · 관찰 '+Number(d['관찰수']||0)+'회 · 문맥군 '+Number((d['문맥군']||[]).length)+'개';
    (d['문맥군']||[]).forEach(s=>{
      html+='<div class="ctx-sense"><b>'+l15esc(s.id||'문맥군')+'</b> · '+Number(s['관찰수']||0)+'회'
        +'<div class="ctx-terms">'+(s['대표용어']||[]).map(l15esc).join(' · ')+'</div>'
        +'<div class="ctx-example">'+(s['예문']||[]).slice(0,2).map(l15esc).join('<br>')+'</div></div>';
    });
    out.innerHTML=html;
  }catch(e){out.textContent='오류: '+e.message;}
}

function learnUseAsk(d){
  if(!d)return;
  LEARN15.trace=d.learning_trace_id||null;LEARN15.used=false;
  let good=document.getElementById('learnGood'),bad=document.getElementById('learnBad');if(good)good.disabled=!LEARN15.trace;if(bad)bad.disabled=!LEARN15.trace;
  let last=document.getElementById('learnLast');if(last)last.textContent=LEARN15.trace?'현재 답변 trace '+LEARN15.trace+' · 평가 대기':'이번 답변에는 자동회귀 학습 trace가 없습니다.';
  let matches=d['문맥지도매칭']||[],box=document.getElementById('learnContextMatch');
  if(box){box.innerHTML=matches.length?'<b>현재 입력 문맥 해석</b><br>'+matches.map(x=>l15esc(x['표제어'])+' → '+l15esc(x['문맥군']||'프로필 없음')+' · 적합 '+Number(x['적합도']||0).toFixed(3)+' · '+(x['대표용어']||[]).map(l15esc).join(', ')).join('<br>'):'';}
  learnLoadStatus();
}

async function learnFeedback(reward){
  if(!LEARN15.trace||LEARN15.used)return;
  let out=document.getElementById('learnOut');out.textContent='생성 경로에 보상을 역전파하는 중...';
  try{
    let d=await api('/api/learning/feedback','POST',{trace_id:LEARN15.trace,reward});
    LEARN15.used=true;document.getElementById('learnGood').disabled=true;document.getElementById('learnBad').disabled=true;
    document.getElementById('learnLast').textContent=(reward>0?'좋음':'나쁨')+' 피드백 학습 완료 · '+Number(d.updated_steps||0)+'단계에 credit 전달';
    out.textContent=JSON.stringify(d,null,2);await learnLoadStatus();
  }catch(e){out.textContent='학습 오류: '+e.message;}
}

async function learnReset(){
  if(!confirm('학습된 사용가중치와 억제가중치를 초기화할까요?\nCorpus와 WordMap 지식은 삭제하지 않습니다.'))return;
  try{let d=await api('/api/learning/reset','POST',{});document.getElementById('learnOut').textContent=JSON.stringify(d,null,2);LEARN15.trace=null;LEARN15.used=false;document.getElementById('learnGood').disabled=true;document.getElementById('learnBad').disabled=true;await learnLoadStatus();}catch(e){document.getElementById('learnOut').textContent='초기화 오류: '+e.message;}
}

setTimeout(()=>{
  const old=window.api;
  if(!old)return;
  window.api=async function(p,m='GET',b=null){let d=await old(p,m,b);if(p==='/api/ask')learnUseAsk(d);if(p==='/api/rebuild'||p==='/api/select-vault')setTimeout(learnLoadStatus,150);return d};
  learnLoadStatus();
},120);
</script>
'''

    if "</main>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</main>", section + "\n</main>", 1)
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</body>", script + "\n</body>", 1)
    return wordmap_mobile
