#!/usr/bin/env python3

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from core import (
    ask,
    current_vault,
    ingest,
    rebuild_wordmap,
    set_vault,
    status,
)

HTML = r'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WordMap Mobile</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#101216;color:#eee;font-family:system-ui,sans-serif}
main{max-width:900px;margin:auto;padding:18px 14px 60px}
.card{background:#191c22;border:1px solid #30343d;border-radius:16px;padding:15px;margin:12px 0}
textarea,input,select{width:100%;background:#0e1014;color:#eee;border:1px solid #444;border-radius:10px;padding:11px;font-size:16px}
textarea{min-height:170px}
button{border:0;border-radius:10px;padding:12px;font-weight:700;background:#eceff4;color:#111}
button.secondary{background:#303641;color:#eee}
button.rebuild{background:#5a3b12;color:#fff}
.row{display:flex;gap:8px;flex-wrap:wrap}
.row>*{flex:1}
.meta{font-size:12px;color:#aaa}
.result{padding:10px 0;border-top:1px solid #333}
.token{font-size:18px;font-weight:700}
pre{white-space:pre-wrap;word-break:break-word;background:#0d0f12;padding:10px;border-radius:10px}
.ok{color:#8cdda8}
.warn{color:#ffd27a}
.space{height:8px}
</style>
</head>
<body>
<main>
<h1>Obsidian WordMap Mobile</h1>

<section class="card">
<h2>Vault</h2>
<div id="st">탐색 중...</div>
<select id="vs"></select>
<div class="row">
<button onclick="choose()">이 Vault 사용</button>
<button class="secondary" onclick="refresh()">다시 찾기</button>
</div>
<div class="space"></div>
<input id="manual" placeholder="/storage/emulated/0/Documents/MyVault">
<button class="secondary" onclick="manual()">직접 경로 사용</button>
</section>

<section class="card">
<h2>1. 말뭉치 → WordMap</h2>
<input type="file" id="file" accept=".txt,.md">
<input id="source" value="mobile" placeholder="출처">
<textarea id="corpus" placeholder="말뭉치를 붙여넣으세요."></textarea>
<button onclick="ingestText()">단어지도 생성 / 누적</button>
<div class="space"></div>
<button class="rebuild" onclick="rebuildMap()">저장된 말뭉치로 전체 재생성</button>
<div class="meta" style="margin-top:7px">
Corpus 원문은 보존하고 Words와 graph.json만 다시 만듭니다.
</div>
<pre id="ingestOut">대기 중</pre>
</section>

<section class="card">
<h2>2. 질문 → 연결 단어</h2>
<textarea id="q" placeholder="질문을 입력하세요."></textarea>
<div class="row">
<select id="depth">
<option>1</option>
<option selected>2</option>
<option>3</option>
</select>
<button onclick="askQ()">Vault 탐색</button>
</div>
<div id="results"></div>
</section>

<script>
const $=x=>document.getElementById(x);

async function api(p,m='GET',b=null){
  let o={method:m,headers:{}};
  if(b!==null){
    o.headers['Content-Type']='application/json';
    o.body=JSON.stringify(b);
  }
  let r=await fetch(p,o),d=await r.json();
  if(!r.ok) throw Error(d.error||r.status);
  return d;
}

async function refresh(){
  let s=await api('/api/status'),v=$('vs');
  v.innerHTML='';
  (s.vaults||[]).forEach(x=>{
    let o=document.createElement('option');
    o.value=o.textContent=x;
    if(x===s.vault)o.selected=true;
    v.appendChild(o);
  });
  $('manual').value=s.vault||'';
  $('st').innerHTML=s.vault
    ? '<span class="ok">사용 중</span><br>'+esc(s.vault)
      +'<br>말뭉치 '+(s.corpus_documents||0)+'개 · 노드 '+(s.nodes||0)+' · 연결 '+(s.pairs||0)
    : '<span class="warn">Vault를 선택하세요.</span>';
}

async function choose(){
  if($('vs').value){
    await api('/api/select-vault','POST',{path:$('vs').value});
    refresh();
  }
}

async function manual(){
  await api('/api/select-vault','POST',{path:$('manual').value});
  refresh();
}

$('file').addEventListener('change',async e=>{
  let f=e.target.files[0];
  if(f){
    $('source').value=f.name;
    $('corpus').value=await f.text();
  }
});

async function ingestText(){
  try{
    $('ingestOut').textContent='생성 중...';
    let d=await api('/api/ingest','POST',{
      text:$('corpus').value,
      source_name:$('source').value
    });
    $('ingestOut').textContent=JSON.stringify(d,null,2);
    refresh();
  }catch(e){
    $('ingestOut').textContent='오류: '+e.message;
  }
}

async function rebuildMap(){
  if(!confirm(
    '저장된 Corpus 전체를 다시 분석합니다.\n\n'
    +'Corpus 원문은 삭제하지 않습니다.\n'
    +'기존 Words와 graph.json은 새 결과로 교체됩니다.\n\n'
    +'계속할까요?'
  )) return;

  try{
    $('ingestOut').textContent='저장된 말뭉치 전체를 다시 분석 중...';
    let d=await api('/api/rebuild','POST',{});
    $('ingestOut').textContent=JSON.stringify(d,null,2);
    await refresh();
    alert('WordMap 전체 재생성이 완료되었습니다.');
  }catch(e){
    $('ingestOut').textContent='재생성 오류: '+e.message;
  }
}

async function askQ(){
  let box=$('results');
  box.textContent='탐색 중...';
  try{
    let d=await api('/api/ask','POST',{
      question:$('q').value,
      depth:Number($('depth').value),
      limit:20
    });
    box.innerHTML=
      '<div class="meta">질문 토큰: '+d.query_tokens.map(esc).join(', ')
      +'<br>시작 노드: '+d.seed_tokens.map(esc).join(', ')+'</div>'
      +(d.warning?'<div class="warn">'+esc(d.warning)+'</div>':'')
      +d.results.map((x,i)=>
        '<div class="result"><div class="token">'+(i+1)+'. '+esc(x.token)
        +'</div><div class="meta">score '+x.score+' · 빈도 '+x.frequency
        +'</div></div>'
      ).join('');
  }catch(e){
    box.textContent='오류: '+e.message;
  }
}

function esc(s){
  return String(s).replace(/[&<>"']/g,m=>({
    '&':'&amp;',
    '<':'&lt;',
    '>':'&gt;',
    '"':'&quot;',
    "'":'&#039;'
  }[m]));
}

refresh();
</script>
</main>
</body>
</html>'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(
            "[%s] %s\n" % (self.log_date_time_string(), fmt % args)
        )

    def send_json(self, obj, code=200):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def read_body(self):
        size = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(size) if size else b"{}"
        return json.loads(raw.decode())

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/":
            raw = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/status":
            self.send_json(status())
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        try:
            data = self.read_body()

            if path == "/api/select-vault":
                return self.send_json(
                    {"vault": set_vault(data.get("path", ""))}
                )

            vault = current_vault()
            if not vault:
                return self.send_json(
                    {"error": "Vault가 선택되지 않았습니다."},
                    400,
                )

            if path == "/api/ingest":
                return self.send_json(
                    ingest(
                        vault,
                        data.get("text", ""),
                        data.get("source_name", "mobile"),
                    )
                )

            if path == "/api/rebuild":
                return self.send_json(rebuild_wordmap(vault))

            if path == "/api/ask":
                return self.send_json(
                    ask(
                        vault,
                        data.get("question", ""),
                        data.get("limit", 20),
                        data.get("depth", 2),
                    )
                )

            self.send_json({"error": "not found"}, 404)

        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 500)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--scan-only", action="store_true")
    args = parser.parse_args()

    if args.scan_only:
        print(json.dumps(status(), ensure_ascii=False, indent=2))
        return

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"WordMap Mobile: http://127.0.0.1:{args.port}")
    print("종료: Ctrl+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
