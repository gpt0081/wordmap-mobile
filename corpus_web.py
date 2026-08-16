from __future__ import annotations

from urllib.parse import parse_qs, urlparse

VERSION = "0.13.0"


def apply(wordmap_mobile, core):
    Handler = wordmap_mobile.Handler
    original_get = Handler.do_GET
    original_post = Handler.do_POST

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path not in {"/api/corpus", "/api/corpus/item"}:
            return original_get(self)
        try:
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            if path == "/api/corpus":
                return self.send_json(core.corpus_list(vault))
            params = parse_qs(parsed.query)
            name = (params.get("name") or [""])[0]
            return self.send_json(core.corpus_get(vault, name))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        managed = {
            "/api/corpus/toggle",
            "/api/corpus/update",
            "/api/corpus/delete",
            "/api/corpus/delete-all",
        }
        if path not in managed:
            return original_post(self)
        try:
            data = self.read_body()
            vault = core.current_vault()
            if not vault:
                return self.send_json({"error": "Vault가 선택되지 않았습니다."}, 400)
            if path == "/api/corpus/toggle":
                return self.send_json(core.corpus_set_enabled(
                    vault,
                    data.get("name", ""),
                    bool(data.get("enabled", True)),
                ))
            if path == "/api/corpus/update":
                return self.send_json(core.corpus_update(
                    vault,
                    data.get("name", ""),
                    data.get("content", ""),
                ))
            if path == "/api/corpus/delete":
                return self.send_json(core.corpus_delete(
                    vault,
                    data.get("name", ""),
                ))
            if path == "/api/corpus/delete-all":
                return self.send_json(core.corpus_delete_all(vault))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    Handler.do_GET = do_GET
    Handler.do_POST = do_POST

    section = r'''
<section class="card" id="corpusManagerCard">
<h2>말뭉치 관리</h2>
<div class="meta">파일을 끄면 원문은 보존되지만 다음 전체 재생성부터 학습에서 제외됩니다.</div>
<div class="row" style="margin-top:10px">
  <button class="secondary" onclick="corpusLoadList()">목록 새로고침</button>
  <button onclick="corpusApplyRebuild()">활성 말뭉치로 전체 재생성</button>
</div>
<div id="corpusSummary" class="meta" style="margin-top:10px">불러오는 중...</div>
<div id="corpusDirty" class="warn" style="display:none;margin-top:6px">변경사항이 아직 WordMap에 반영되지 않았습니다. 전체 재생성을 실행하세요.</div>
<div id="corpusList" style="margin-top:10px"></div>

<details id="corpusDetails" style="margin-top:14px">
<summary style="cursor:pointer;font-weight:700">상세 설정</summary>
<div class="space"></div>
<div id="corpusSelected" class="meta">편집할 말뭉치를 선택하세요.</div>
<textarea id="corpusEditor" placeholder="말뭉치 원문" style="min-height:260px" disabled></textarea>
<div class="row">
  <button id="corpusSaveBtn" onclick="corpusSaveCurrent()" disabled>내용 저장</button>
  <button id="corpusDeleteBtn" class="secondary" onclick="corpusDeleteCurrent()" disabled>선택 파일 삭제</button>
</div>
<div class="card" style="margin-top:14px;border-color:#6b3131;background:#211516">
  <b>위험 구역</b>
  <div class="meta" style="margin:6px 0 10px">전체 삭제는 Corpus 원문과 현재 생성된 WordMap을 함께 비웁니다.</div>
  <button class="rebuild" onclick="corpusDeleteAll()">전체 말뭉치 삭제</button>
</div>
</details>
<pre id="corpusManagerOut">대기 중</pre>
</section>
<style>
.corpus-row{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:10px 0;border-top:1px solid #30343d}
.corpus-row:first-child{border-top:0}
.corpus-toggle{width:20px;height:20px}
.corpus-name{font-weight:700;word-break:break-all}
.corpus-off{opacity:.48}
.corpus-detail-btn{padding:8px 10px;font-size:12px}
@media(max-width:600px){.corpus-row{grid-template-columns:auto 1fr}.corpus-detail-btn{grid-column:2}}
</style>
'''

    script = r'''
<script>
const CORPUS_UI={selected:null};

function corpusFmtBytes(n){
  n=Number(n||0);if(n<1024)return n+' B';if(n<1024*1024)return (n/1024).toFixed(1)+' KB';return (n/1024/1024).toFixed(1)+' MB';
}

async function corpusLoadList(){
  let list=document.getElementById('corpusList');
  if(!list)return;
  list.textContent='말뭉치 목록 불러오는 중...';
  try{
    let d=await api('/api/corpus');
    document.getElementById('corpusSummary').textContent='전체 '+d.total+'개 · 사용 '+d.enabled+'개 · 제외 '+d.disabled+'개';
    document.getElementById('corpusDirty').style.display=d.dirty?'block':'none';
    list.innerHTML='';
    if(!d.documents.length){list.innerHTML='<div class="meta">저장된 말뭉치가 없습니다.</div>';return;}
    d.documents.forEach(doc=>{
      let row=document.createElement('div');row.className='corpus-row'+(doc.enabled?'':' corpus-off');
      let toggle=document.createElement('input');toggle.type='checkbox';toggle.className='corpus-toggle';toggle.checked=!!doc.enabled;
      toggle.addEventListener('change',()=>corpusToggle(doc.name,toggle.checked));
      let info=document.createElement('div');
      let name=document.createElement('div');name.className='corpus-name';name.textContent=doc.source||doc.name;
      let meta=document.createElement('div');meta.className='meta';meta.textContent=doc.name+' · '+doc.sentences+'문장 · '+corpusFmtBytes(doc.size_bytes);
      info.append(name,meta);
      let detail=document.createElement('button');detail.className='secondary corpus-detail-btn';detail.textContent='상세';detail.addEventListener('click',()=>corpusOpen(doc.name));
      row.append(toggle,info,detail);list.appendChild(row);
    });
  }catch(e){list.textContent='오류: '+e.message;}
}

async function corpusToggle(name,enabled){
  try{
    await api('/api/corpus/toggle','POST',{name,enabled});
    document.getElementById('corpusManagerOut').textContent=(enabled?'사용: ':'제외: ')+name+'\n전체 재생성 후 WordMap에 반영됩니다.';
    await corpusLoadList();if(typeof refresh==='function')refresh();
  }catch(e){document.getElementById('corpusManagerOut').textContent='오류: '+e.message;await corpusLoadList();}
}

async function corpusOpen(name){
  try{
    let d=await api('/api/corpus/item?name='+encodeURIComponent(name));
    CORPUS_UI.selected=name;
    document.getElementById('corpusSelected').textContent=(d.enabled?'사용 중 · ':'제외 중 · ')+(d.source||name)+' · '+d.sentences+'문장';
    let editor=document.getElementById('corpusEditor');editor.disabled=false;editor.value=d.content||'';
    document.getElementById('corpusSaveBtn').disabled=false;document.getElementById('corpusDeleteBtn').disabled=false;
    document.getElementById('corpusDetails').open=true;editor.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(e){document.getElementById('corpusManagerOut').textContent='오류: '+e.message;}
}

async function corpusSaveCurrent(){
  if(!CORPUS_UI.selected)return;
  if(!confirm('이 말뭉치 원문을 현재 편집 내용으로 저장할까요?'))return;
  try{
    let content=document.getElementById('corpusEditor').value;
    let d=await api('/api/corpus/update','POST',{name:CORPUS_UI.selected,content});
    document.getElementById('corpusManagerOut').textContent='저장 완료: '+d.name+'\n'+d.sentences+'문장 · 전체 재생성 필요';
    await corpusLoadList();if(typeof refresh==='function')refresh();
  }catch(e){document.getElementById('corpusManagerOut').textContent='오류: '+e.message;}
}

async function corpusDeleteCurrent(){
  if(!CORPUS_UI.selected)return;
  let name=CORPUS_UI.selected;
  if(!confirm('정말 삭제할까요?\n\n'+name+'\n\n이 작업은 원문 파일을 삭제합니다.'))return;
  try{
    let d=await api('/api/corpus/delete','POST',{name});
    document.getElementById('corpusManagerOut').textContent='삭제 완료: '+d.deleted+(d.rebuild_required?'\n전체 재생성 필요':'');
    CORPUS_UI.selected=null;document.getElementById('corpusEditor').value='';document.getElementById('corpusEditor').disabled=true;
    document.getElementById('corpusSaveBtn').disabled=true;document.getElementById('corpusDeleteBtn').disabled=true;document.getElementById('corpusSelected').textContent='편집할 말뭉치를 선택하세요.';
    await corpusLoadList();if(typeof refresh==='function')refresh();if(window.wmLoadGraph)setTimeout(wmLoadGraph,200);
  }catch(e){document.getElementById('corpusManagerOut').textContent='오류: '+e.message;}
}

async function corpusDeleteAll(){
  if(!confirm('모든 Corpus 원문을 삭제하고 현재 WordMap도 비웁니다.\n\n계속할까요?'))return;
  let typed=prompt('실수 방지를 위해 전체삭제 라고 입력하세요.');
  if(typed!=='전체삭제'){document.getElementById('corpusManagerOut').textContent='전체 삭제가 취소되었습니다.';return;}
  try{
    let d=await api('/api/corpus/delete-all','POST',{});
    document.getElementById('corpusManagerOut').textContent='전체 삭제 완료 · '+d.deleted_count+'개 파일 삭제 · WordMap 초기화';
    CORPUS_UI.selected=null;document.getElementById('corpusEditor').value='';document.getElementById('corpusEditor').disabled=true;
    document.getElementById('corpusSaveBtn').disabled=true;document.getElementById('corpusDeleteBtn').disabled=true;document.getElementById('corpusSelected').textContent='편집할 말뭉치를 선택하세요.';
    await corpusLoadList();if(typeof refresh==='function')refresh();if(window.wmLoadGraph)setTimeout(wmLoadGraph,200);
  }catch(e){document.getElementById('corpusManagerOut').textContent='오류: '+e.message;}
}

async function corpusApplyRebuild(){
  if(!confirm('현재 사용으로 켜진 말뭉치만 사용해 WordMap을 전체 재생성할까요?'))return;
  let out=document.getElementById('corpusManagerOut');out.textContent='활성 말뭉치로 전체 재생성 중...';
  try{
    let d=await api('/api/rebuild','POST',{});out.textContent=JSON.stringify(d,null,2);
    await corpusLoadList();if(typeof refresh==='function')refresh();if(window.wmLoadGraph)setTimeout(wmLoadGraph,250);
  }catch(e){out.textContent='재생성 오류: '+e.message;}
}

setTimeout(corpusLoadList,550);
const corpusOldRefresh=window.refresh;
if(corpusOldRefresh){window.refresh=async function(){let x=await corpusOldRefresh.apply(this,arguments);setTimeout(corpusLoadList,80);return x;};}
</script>
'''

    if "</main>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</main>", section + "\n</main>", 1,
        )
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</body>", script + "\n</body>", 1,
        )
    return wordmap_mobile
