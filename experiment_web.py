from __future__ import annotations

from urllib.parse import urlparse

VERSION = "0.16.0"


def apply(wordmap_mobile, core):
    Handler = wordmap_mobile.Handler
    old_get = Handler.do_GET
    old_post = Handler.do_POST

    def do_GET(self):
        path = urlparse(self.path).path
        managed = {"/api/corpus-v1/summary", "/api/integrity", "/api/experiment/status", "/api/dialogue/status"}
        if path not in managed:
            return old_get(self)
        try:
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            if path == "/api/corpus-v1/summary":
                return self.send_json(core.corpus_v1_summary(vault))
            if path == "/api/integrity":
                return self.send_json(core.corpus_integrity(vault))
            if path == "/api/dialogue/status":
                return self.send_json(core.dialogue_status(vault))
            return self.send_json(core.experiment_status(vault))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path
        managed = {
            "/api/corpus-v1/install", "/api/benchmark/run", "/api/experiment/start",
            "/api/experiment/feedback", "/api/dialogue/start", "/api/dialogue/reset",
        }
        if path not in managed:
            return old_post(self)
        try:
            data = self.read_body()
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            if path == "/api/corpus-v1/install":
                return self.send_json(core.corpus_v1_install(vault, rebuild=bool(data.get("rebuild", True))))
            if path == "/api/benchmark/run":
                return self.send_json(core.benchmark_run(vault, data.get("split", "dev")))
            if path == "/api/experiment/start":
                return self.send_json(core.experiment_start(vault))
            if path == "/api/experiment/feedback":
                return self.send_json(core.experiment_feedback_to(vault, int(data.get("target", 50))))
            if path == "/api/dialogue/start":
                return self.send_json(core.dialogue_start(vault, data.get("session_id", "web")))
            return self.send_json(core.dialogue_reset(vault))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    Handler.do_GET = do_GET
    Handler.do_POST = do_POST

    section = r'''
<section class="card" id="experimentCard">
<h2>Corpus v1 · 실험 Harness</h2>
<div class="meta">Train 1,500문장과 Dev 60/Test 110을 분리해 Corpus 무결성, Benchmark, Credit Backprop B0~B3를 반복 측정합니다. DEV/TEST는 코드에서 학습이 차단됩니다.</div>

<div class="exp-grid" style="margin-top:12px">
  <div class="exp-box">
    <b>1. Corpus v1</b>
    <div id="expCorpusSummary" class="meta" style="margin-top:6px">상태 확인 중...</div>
    <button style="margin-top:8px" onclick="expInstallCorpus()">Corpus v1 설치 / 교체</button>
    <button class="secondary" style="margin-top:6px" onclick="expIntegrity()">무결성 · 누출 검사</button>
  </div>
  <div class="exp-box">
    <b>2. Benchmark</b>
    <div class="meta" style="margin-top:6px">평가 질문은 생성과 판정에만 사용되며 Corpus 학습에는 들어가지 않습니다.</div>
    <div class="row" style="margin-top:8px">
      <button class="secondary" onclick="expBenchmark('dev')">Dev 60 실행</button>
      <button class="secondary" onclick="expBenchmark('test')">Test 110 실행</button>
    </div>
  </div>
  <div class="exp-box">
    <b>3. Credit Backprop 실험</b>
    <div id="expLearnState" class="meta" style="margin-top:6px">상태 확인 중...</div>
    <button style="margin-top:8px" onclick="expStartB0()">B0 초기화 + Benchmark</button>
    <div class="row exp-checkpoints" style="margin-top:6px">
      <button class="secondary" onclick="expFeedback(50)">B1 · Feedback 50</button>
      <button class="secondary" onclick="expFeedback(100)">B2 · Feedback 100</button>
      <button class="secondary" onclick="expFeedback(200)">B3 · Feedback 200</button>
    </div>
  </div>
  <div class="exp-box">
    <b>4. Dialogue Session</b>
    <div id="expDialogue" class="meta" style="margin-top:6px">상태 확인 중...</div>
    <div class="row" style="margin-top:8px">
      <button class="secondary" onclick="expDialogueStart()">새 대화 시작</button>
      <button class="secondary" onclick="expDialogueReset()">문맥 초기화</button>
    </div>
  </div>
</div>
<div id="expMetricCards" class="exp-metrics"></div>
<pre id="expOut">대기 중</pre>
</section>
<style>
.exp-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.exp-box{padding:11px;border:1px solid #343944;border-radius:11px;background:#11151b}.exp-checkpoints{grid-template-columns:repeat(3,1fr)}.exp-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px}.exp-metric{padding:8px;border:1px solid #343944;border-radius:9px;background:#151922}.exp-metric b{display:block;font-size:18px}.exp-role{display:inline-block;margin-right:5px;padding:2px 6px;border-radius:999px;font-size:9px;font-weight:800}.exp-role.train{background:#294333}.exp-role.dev{background:#3c3554}.exp-role.test{background:#553338}.exp-lock{opacity:.55}@media(max-width:700px){.exp-grid{grid-template-columns:1fr}.exp-checkpoints{grid-template-columns:1fr}.exp-metrics{grid-template-columns:1fr 1fr}}
</style>
'''

    script = r'''
<script>
function e16esc(s){return typeof esc==='function'?esc(s):String(s)}
function e16pct(v){return v===null||v===undefined?'—':(Number(v)*100).toFixed(1)+'%'}
function expSetOut(v){let o=document.getElementById('expOut');if(o)o.textContent=typeof v==='string'?v:JSON.stringify(v,null,2)}

async function expLoad(){
  try{
    let c=await api('/api/corpus-v1/summary');
    let docs=c.documents||[],train=docs.filter(x=>x.role==='train'),dev=docs.filter(x=>x.role==='dev'),test=docs.filter(x=>x.role==='test');
    document.getElementById('expCorpusSummary').textContent='TRAIN '+train.length+'파일 · DEV '+dev.length+' · TEST '+test.length+' · 목표 1,500 / 60 / 110';
    let s=await api('/api/experiment/status');
    document.getElementById('expLearnState').textContent='현재 Feedback '+Number(s.learning_updates||0)+'회 · 저장 체크포인트 '+(s.files||[]).length+'개';
    let d=await api('/api/dialogue/status');
    document.getElementById('expDialogue').textContent=(d.active?'세션 활성':'세션 비활성')+' · '+Number(d.turn_count||0)+'턴 · 문맥 '+(d.context_tokens||[]).slice(-6).join(', ');
    setTimeout(expDecorateCorpus,40);
  }catch(e){expSetOut('상태 오류: '+e.message)}
}

async function expDecorateCorpus(){
  try{
    let d=await api('/api/corpus'),rows=[...document.querySelectorAll('#corpusList .corpus-row')];
    rows.forEach(row=>{
      let meta=row.querySelector('.meta'),nameEl=row.querySelector('.corpus-name'),toggle=row.querySelector('input');if(!meta||!nameEl)return;
      let doc=(d.documents||[]).find(x=>meta.textContent.includes(x.name));if(!doc)return;
      let old=nameEl.querySelector('.exp-role');if(old)old.remove();
      let badge=document.createElement('span');badge.className='exp-role '+(doc.role||'train');badge.textContent=(doc.role_label||'TRAIN');nameEl.prepend(badge);
      if(doc.training_locked){if(toggle){toggle.checked=false;toggle.disabled=true}row.classList.add('exp-lock');meta.textContent=doc.name+' · '+doc.sentences+'문항 · 평가 전용 · 학습 금지';}
    });
  }catch(e){}
}

async function expInstallCorpus(){
  if(!confirm('기존 Corpus를 백업한 뒤 Corpus v1로 교체합니다.\n현재 생성 WordMap과 학습가중치도 새 Corpus 기준으로 재구성됩니다.\n계속할까요?'))return;
  let typed=prompt('확인을 위해 CORPUSV1 을 입력하세요.');if(typed!=='CORPUSV1'){expSetOut('설치 취소');return;}
  expSetOut('기존 Corpus 백업 → Corpus v1 생성 → 전체 재생성 중...');
  try{let d=await api('/api/corpus-v1/install','POST',{rebuild:true});expSetOut(d);if(typeof corpusLoadList==='function')await corpusLoadList();await expLoad();if(window.wmLoadGraph)setTimeout(wmLoadGraph,200);}catch(e){expSetOut('설치 오류: '+e.message)}
}

async function expIntegrity(){
  expSetOut('Train/Dev/Test 무결성 및 누출 검사 중...');
  try{let d=await api('/api/integrity');expSetOut(d);let c=d.counts||{};document.getElementById('expMetricCards').innerHTML='<div class="exp-metric"><span>상태</span><b>'+(d.ok?'PASS':'FAIL')+'</b></div><div class="exp-metric"><span>Train</span><b>'+Number(c.train||0)+'</b></div><div class="exp-metric"><span>Dev</span><b>'+Number(c.dev||0)+'</b></div><div class="exp-metric"><span>Test</span><b>'+Number(c.test||0)+'</b></div>';}catch(e){expSetOut('검사 오류: '+e.message)}
}

function expShowMetrics(d){
  let m=d.metrics||{},cards=document.getElementById('expMetricCards');
  cards.innerHTML='<div class="exp-metric"><span>전체 정확도</span><b>'+e16pct(m.accuracy)+'</b></div>'
    +'<div class="exp-metric"><span>문맥 정확도</span><b>'+e16pct(m.context_accuracy)+'</b></div>'
    +'<div class="exp-metric"><span>다의어 정확도</span><b>'+e16pct(m.polysemy_accuracy)+'</b></div>'
    +'<div class="exp-metric"><span>주제 이탈률</span><b>'+e16pct(m.topic_drift_rate)+'</b></div>'
    +'<div class="exp-metric"><span>Target</span><b>'+e16pct(m.target_accuracy)+'</b></div>'
    +'<div class="exp-metric"><span>Non-target</span><b>'+e16pct(m.non_target_accuracy)+'</b></div>'
    +'<div class="exp-metric"><span>Regression</span><b>'+Number(m.regression_count||0)+'</b></div>'
    +'<div class="exp-metric"><span>Transfer Gain</span><b>'+Number(m.transfer_gain||0)+'</b></div>';
}

async function expBenchmark(split){
  expSetOut((split==='dev'?'Dev 60':'Test 110')+' 자동 Benchmark 실행 중... 휴대폰 성능에 따라 시간이 걸릴 수 있습니다.');
  try{let d=await api('/api/benchmark/run','POST',{split});expShowMetrics(d);expSetOut({label:d.label,split:d.split,feedback_updates:d.feedback_updates,metrics:d.metrics,errors:(d.details||[]).filter(x=>x.verdict!=='정답').slice(0,20)});await expLoad();}catch(e){expSetOut('Benchmark 오류: '+e.message)}
}

async function expStartB0(){
  if(!confirm('학습 가중치를 0으로 초기화하고 B0 Dev+Test Benchmark를 실행할까요? Corpus는 수정하지 않습니다.'))return;
  expSetOut('B0 초기화 및 Dev/Test Benchmark 실행 중...');
  try{let d=await api('/api/experiment/start','POST',{});expShowMetrics(d.test);expSetOut({label:d.label,dev:d.dev.metrics,test:d.test.metrics});await expLoad();}catch(e){expSetOut('B0 오류: '+e.message)}
}

async function expFeedback(target){
  if(!confirm('Dev target 문항만 교사 신호로 사용해 Feedback '+target+'회까지 학습하고 Dev/Test를 다시 평가합니다.\nTest 정답은 피드백에 사용하지 않습니다. 계속할까요?'))return;
  expSetOut('Feedback '+target+'회 목표 학습 및 재평가 중...');
  try{let d=await api('/api/experiment/feedback','POST',{target});let t=d.benchmark?.test; if(t)expShowMetrics(t);expSetOut({label:d.label,updates:d.updates,attempts:d.attempts,dev:d.benchmark?.dev?.metrics,test:t?.metrics});await expLoad();}catch(e){expSetOut('Feedback 실험 오류: '+e.message)}
}

async function expDialogueStart(){try{let d=await api('/api/dialogue/start','POST',{session_id:'web'});expSetOut(d);await expLoad();}catch(e){expSetOut('대화 시작 오류: '+e.message)}}
async function expDialogueReset(){try{let d=await api('/api/dialogue/reset','POST',{});expSetOut(d);await expLoad();}catch(e){expSetOut('대화 초기화 오류: '+e.message)}}

setTimeout(()=>{
  const old=window.corpusLoadList;
  if(old)window.corpusLoadList=async function(){let x=await old.apply(this,arguments);setTimeout(expDecorateCorpus,40);return x};
  expLoad();
},180);
</script>
'''

    if "</main>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</main>", section + "\n</main>", 1)
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</body>", script + "\n</body>", 1)
    return wordmap_mobile
