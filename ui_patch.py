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

    let analysis=(d.surface_analysis||[]);
    let analysisHtml='';
    let compounds=analysis.filter(x=>x.compound);
    if(compounds.length){
      analysisHtml='<div class="result"><div class="token">입력 분해</div>'
        +compounds.map(x=>'<div class="meta" style="margin-top:7px">'
          +esc(x.surface)+' → '+x.lemmas.map(esc).join(' + ')
          +'</div>').join('')
        +'</div>';
    }

    let next=(d.next_word_candidates||[]);
    let nextHtml='';
    if(next.length){
      nextHtml='<div class="result"><div class="token">다음 단어 후보 · '
        +esc(d.next_word_source||'')+'</div>'
        +next.map((x,i)=>'<div style="margin-top:9px"><b>'+(i+1)+'. '
          +esc(x.token)+'</b><div class="meta">출현 '+Number(x.count||0)
          +'회 · '+(Number(x.probability||0)*100).toFixed(1)+'%</div></div>').join('')
        +'</div>';
    }

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
      +analysisHtml
      +nextHtml
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
