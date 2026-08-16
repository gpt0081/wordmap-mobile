from __future__ import annotations

from urllib.parse import parse_qs, urlparse

VERSION = "0.14.0"


def apply(wordmap_mobile, core):
    Handler = wordmap_mobile.Handler
    original_get = Handler.do_GET
    original_post = Handler.do_POST

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path not in {"/api/node-health", "/api/node-health/item"}:
            return original_get(self)
        try:
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            params = parse_qs(parsed.query)
            if path == "/api/node-health/item":
                token = (params.get("token") or [""])[0]
                return self.send_json(core.node_health_get(vault, token))
            status = (params.get("status") or [None])[0]
            tag_isolated = (params.get("tag_isolated") or ["0"])[0] in {"1", "true", "yes"}
            try:
                limit = int((params.get("limit") or ["100"])[0])
            except ValueError:
                limit = 100
            return self.send_json(core.node_health_list(
                vault,
                status=status or None,
                tag_isolated=tag_isolated,
                limit=limit,
            ))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/node-health/recalculate":
            return original_post(self)
        try:
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            return self.send_json(core.node_health_recalculate(vault))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    Handler.do_GET = do_GET
    Handler.do_POST = do_POST

    section = r'''
<section class="card" id="nodeHealthCard">
<h2>상세 설정 · 노드 건강도</h2>
<div class="meta">고립처럼 보이는 노드를 실제 구조 고립과 태그 필터 고립으로 분리합니다. 진단 결과만 만들며 연결이나 노드를 자동 삭제하지 않습니다.</div>
<div class="row nh-actions" style="margin-top:10px">
  <button class="secondary" onclick="nhLoad('')">전체</button>
  <button class="secondary" onclick="nhLoad('진짜 고립')">진짜 고립</button>
  <button class="secondary" onclick="nhLoad('시각적 고립')">시각적 고립</button>
  <button class="secondary" onclick="nhLoad('약한 고립')">약한 고립</button>
  <button class="secondary" onclick="nhLoad('',true)">태그 필터 고립</button>
</div>
<div class="row" style="margin-top:8px">
  <button onclick="nhRecalculate()">건강도 다시 계산</button>
</div>
<div id="nhSummary" class="meta" style="margin-top:10px">불러오는 중...</div>
<div id="nhExplanation" class="warn" style="display:none;margin-top:8px"></div>
<div id="nhList" style="margin-top:10px"></div>
<details id="nhDetails" style="margin-top:12px">
  <summary style="cursor:pointer;font-weight:700">선택 노드 상세</summary>
  <div id="nhNodeDetail" class="meta" style="margin-top:10px">노드를 선택하세요.</div>
</details>
<pre id="nhOut">대기 중</pre>
</section>
<style>
.nh-actions{grid-template-columns:repeat(5,1fr)}
.nh-row{display:grid;grid-template-columns:1fr auto;gap:8px;padding:10px 0;border-top:1px solid #30343d;align-items:center}
.nh-row:first-child{border-top:0}
.nh-token{font-weight:800;word-break:break-all}
.nh-badges{display:flex;gap:5px;flex-wrap:wrap;margin-top:5px}
.nh-badge{padding:2px 6px;border-radius:999px;background:#292f39;font-size:10px;color:#cbd1da}
.nh-badge.orphan{background:#51262b}.nh-badge.visual{background:#45351f}.nh-badge.weak{background:#303747}.nh-badge.tag{background:#253c4c}.nh-badge.protected{background:#2d4332}
.nh-detail-btn{padding:7px 9px;font-size:11px}
.nh-path{padding:7px 8px;margin-top:5px;border-radius:8px;background:#151922;word-break:break-all}
@media(max-width:700px){.nh-actions{grid-template-columns:1fr 1fr}.nh-actions button:last-child{grid-column:1/3}.nh-row{grid-template-columns:1fr auto}}
</style>
'''

    script = r'''
<script>
const NH={status:'',tag:false};
function nhEsc(s){return typeof esc==='function'?esc(s):String(s)}
function nhBadgeClass(status){return status==='진짜 고립'?'orphan':status==='시각적 고립'?'visual':status==='약한 고립'?'weak':''}

async function nhLoad(status='',tag=false){
  NH.status=status||'';NH.tag=!!tag;
  let list=document.getElementById('nhList');if(!list)return;
  list.textContent='노드 건강도 계산 중...';
  try{
    let qs='?limit=160';if(NH.status)qs+='&status='+encodeURIComponent(NH.status);if(NH.tag)qs+='&tag_isolated=1';
    let d=await api('/api/node-health'+qs),s=d.summary||{};
    document.getElementById('nhSummary').textContent='전체 '+Number(s['전체']||0)+' · 정상 '+Number(s['정상']||0)+' · 약한 고립 '+Number(s['약한 고립']||0)+' · 시각적 고립 '+Number(s['시각적 고립']||0)+' · 진짜 고립 '+Number(s['진짜 고립']||0)+' · 태그 필터 고립 '+Number(s['태그필터고립']||0)+' · 보호노드 '+Number(s['보호노드']||0)+' · 현재 표시 '+Number(d.matched||0);
    let explain=document.getElementById('nhExplanation');
    explain.style.display=(NH.status||NH.tag)?'block':'none';
    if(NH.tag)explain.textContent='태그 필터 고립은 실제 연결이 없는 뜻이 아닙니다. 같은 태그의 직접 이웃이 없어 Obsidian 태그 필터에서 떨어져 보일 수 있습니다.';
    else if(NH.status==='시각적 고립')explain.textContent='연상·의미 링크는 없지만 순서지도나 사건지도 안에서는 연결된 노드입니다.';
    else if(NH.status==='진짜 고립')explain.textContent='현재 분석한 연상·의미·순서·사건 지도 모두에서 연결을 찾지 못했습니다. 자동 삭제하지 않습니다.';
    else if(NH.status==='약한 고립')explain.textContent='연결은 있으나 직접 표시 연결이 1개 이하이거나 전체 구조 연결이 매우 적은 노드입니다.';
    list.innerHTML='';
    if(!(d.rows||[]).length){list.innerHTML='<div class="meta">해당 조건의 노드가 없습니다.</div>';return;}
    (d.rows||[]).forEach(row=>{
      let item=document.createElement('div');item.className='nh-row';
      let info=document.createElement('div');
      let title=document.createElement('div');title.className='nh-token';title.textContent=row['표제어'];
      let meta=document.createElement('div');meta.className='meta';meta.textContent='건강도 '+Number(row['건강도']||0).toFixed(3)+' · 빈도 '+Number(row['빈도']||0)+' · 연상 '+Number(row['연상연결']||0)+' · 의미 '+Number(row['의미연결']||0)+' · 순서 '+Number(row['순서연결']||0)+' · 사건 '+Number(row['사건연결']||0);
      let badges=document.createElement('div');badges.className='nh-badges';
      let b=document.createElement('span');b.className='nh-badge '+nhBadgeClass(row['상태']);b.textContent=row['상태'];badges.appendChild(b);
      if(row['태그필터고립']){let x=document.createElement('span');x.className='nh-badge tag';x.textContent='태그필터고립';badges.appendChild(x)}
      if(row['보호노드']){let x=document.createElement('span');x.className='nh-badge protected';x.textContent='보호';badges.appendChild(x)}
      info.append(title,meta,badges);
      let detail=document.createElement('button');detail.className='secondary nh-detail-btn';detail.textContent='진단';detail.addEventListener('click',()=>nhOpen(row['표제어']));
      item.append(info,detail);list.appendChild(item);
    });
  }catch(e){list.textContent='오류: '+e.message;}
}

async function nhOpen(token){
  try{
    let d=await api('/api/node-health/item?token='+encodeURIComponent(token)),r=d.node||{};
    let bridges=(r['태그브리지']||[]).map(x=>'<div class="nh-path">'+nhEsc((x['경로']||[]).join(' → '))+'<br><span class="meta">'+nhEsc(x['태그']||'')+' · 실제 2홉 경로, 가짜 링크 생성 안 함</span></div>').join('');
    let tags=(r['태그']||[]).map(nhEsc).join(', ')||'없음';
    let isolated=(r['고립태그']||[]).map(nhEsc).join(', ')||'없음';
    document.getElementById('nhNodeDetail').innerHTML='<b>'+nhEsc(r['표제어']||token)+'</b> · '+nhEsc(r['상태']||'')+'<br><br>'
      +'건강도 '+Number(r['건강도']||0).toFixed(3)+' · 빈도 '+Number(r['빈도']||0)+'<br>'
      +'연상 '+Number(r['연상연결']||0)+' · 의미 '+Number(r['의미연결']||0)+' · 순서 '+Number(r['순서연결']||0)+' · 사건 '+Number(r['사건연결']||0)+'<br>'
      +'원시 공기 연결 '+Number(r['원시공기연결']||0)+' · 정리 과정에서 잘린 약한 연결 '+Number(r['잘린약한연결']||0)+'<br>'
      +'태그: '+tags+'<br>고립 태그: '+isolated+'<br>'
      +'보호 노드: '+(r['보호노드']?'예':'아니오')+' · 자동 삭제: 안 함'
      +(bridges?'<br><br><b>태그 브리지 후보</b>'+bridges:'');
    document.getElementById('nhDetails').open=true;document.getElementById('nhDetails').scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(e){document.getElementById('nhOut').textContent='오류: '+e.message;}
}

async function nhRecalculate(){
  let out=document.getElementById('nhOut');out.textContent='현재 graph.json에서 노드 건강도 다시 계산 중...';
  try{
    let d=await api('/api/node-health/recalculate','POST',{});out.textContent=JSON.stringify(d,null,2);await nhLoad(NH.status,NH.tag);if(window.wmLoadGraph)setTimeout(wmLoadGraph,150);
  }catch(e){out.textContent='오류: '+e.message;}
}

setTimeout(()=>nhLoad('',false),850);

setTimeout(()=>{
  const old=window.wmShowNode;
  if(!old)return;
  window.wmShowNode=function(id){
    old(id);
    let node=window.wmNodeById?window.wmNodeById(id):null,el=document.getElementById('wmNodeInfo');
    if(!node||!el)return;
    if(node.health_status){
      let extra='<br><span class="meta">연결상태 '+nhEsc(node.health_status)+' · 건강도 '+Number(node.health_score||0).toFixed(3);
      if(node.tag_isolated)extra+=' · 태그필터고립';
      if((node.isolated_tags||[]).length)extra+='<br>고립 태그: '+(node.isolated_tags||[]).map(nhEsc).join(', ');
      extra+='</span>';el.innerHTML+=extra;
    }
  };
},100);
</script>
'''

    if "</main>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</main>", section + "\n</main>", 1)
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace("</body>", script + "\n</body>", 1)
    return wordmap_mobile
