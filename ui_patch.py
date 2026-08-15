from __future__ import annotations


def apply(wordmap_mobile):
    extra = r'''
<script>
window.askQ = async function(){
  let box=document.getElementById('results');
  box.textContent='탐색 중...';
  try{
    let d=await api('/api/ask','POST',{
      question:document.getElementById('q').value,
      depth:Number(document.getElementById('depth').value),
      limit:20
    });

    let semantic=(d.semantic_paths||[]);
    let semanticHtml='';
    if(semantic.length){
      semanticHtml='<div class="result"><div class="token">의미 관계 경로</div>'
        +semantic.map(x=>'<div class="meta" style="margin-top:7px">'
          +esc(x.text)+' · 신뢰 '+Number(x.confidence||0).toFixed(2)
          +'</div>').join('')
        +'</div>';
    }

    box.innerHTML=
      '<div class="meta">질문 토큰: '+d.query_tokens.map(esc).join(', ')
      +'<br>시작 노드: '+d.seed_tokens.map(esc).join(', ')+'</div>'
      +(d.warning?'<div class="warn">'+esc(d.warning)+'</div>':'')
      +semanticHtml
      +d.results.map((x,i)=>
        '<div class="result"><div class="token">'+(i+1)+'. '+esc(x.token)
        +'</div><div class="meta">score '+x.score+' · 빈도 '+x.frequency
        +'</div></div>'
      ).join('');
  }catch(e){
    box.textContent='오류: '+e.message;
  }
};
</script>
'''
    if "</body>" in wordmap_mobile.HTML:
        wordmap_mobile.HTML = wordmap_mobile.HTML.replace(
            "</body>",
            extra + "\n</body>",
            1,
        )
    return wordmap_mobile
