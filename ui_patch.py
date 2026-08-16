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

    let qinfo=d['질문분석']||{};
    let qtags=qinfo['태그']||[];
    let questionHtml='';
    if(qtags.length){
      questionHtml='<div class="result"><div class="token">질문 분석</div>'
        +'<div class="meta" style="margin-top:7px">의도: '
        +qtags.map(esc).join(', ')+'</div>'
        +'<div class="meta" style="margin-top:5px">핵심 표제어: '
        +(qinfo['핵심표제어']||[]).map(esc).join(', ')+'</div>'
        +'</div>';
    }

    let active=(d['문맥활성화']||[]);
    let activeHtml='';
    if(active.length){
      activeHtml='<div class="result"><div class="token">현재 문맥 활성화</div>'
        +active.slice(0,10).map((x,i)=>{
          let why=(x['근거']||[]).slice(0,2).map(esc).join(' · ');
          return '<div style="margin-top:8px"><b>'+(i+1)+'. '+esc(x['표제어']||'')+'</b>'
            +'<div class="meta">활성도 '+Number(x['활성도']||0).toFixed(3)
            +(why?' · '+why:'')+'</div></div>';
        }).join('')
        +'</div>';
    }

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

    let generated=(d.generated_sentences||[]);
    let generatedHtml='';
    if(generated.length){
      generatedHtml='<div class="result"><div class="token">생성 문장 후보</div>'
        +generated.map((x,i)=>{
          let mode=x.mode==='semantic'?'의미관계 기반':'말뭉치 순서 기반';
          let path=(x.path||[]).map(esc).join(' → ');
          let pattern=x.grammar_pattern||'';
          let patternCount=Number(x.grammar_pattern_count||0);
          let activeSupport=Number(x.activation_support||0);
          return '<div style="margin-top:13px"><b>'+(i+1)+'. '+esc(x.text)+'</b>'
            +'<div class="meta" style="margin-top:4px">'+mode
            +(path?' · 경로 '+path:'')+'</div>'
            +(pattern?'<div class="meta" style="margin-top:3px">문법 패턴: '
              +esc(pattern)+(patternCount?' · 관찰 '+patternCount+'회':'')+'</div>':'')
            +(activeSupport?'<div class="meta" style="margin-top:3px">문맥 지지도: '
              +activeSupport.toFixed(3)+'</div>':'')
            +'</div>';
        }).join('')
        +'</div>';
    }

    let next=(d.next_word_candidates||[]);
    let nextHtml='';
    if(next.length){
      nextHtml='<div class="result"><div class="token">다음 단어 후보 · '
        +esc(d.next_word_source||'')+'</div>'
        +next.map((x,i)=>{
          let activeScore=Number(x.activation||0);
          return '<div style="margin-top:9px"><b>'+(i+1)+'. '
            +esc(x.token)+'</b><div class="meta">출현 '+Number(x.count||0)
            +'회 · 기본 '+(Number(x.probability||0)*100).toFixed(1)+'%'
            +(activeScore?' · 문맥활성 '+activeScore.toFixed(3):'')+'</div></div>';
        }).join('')
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
      +questionHtml
      +activeHtml
      +analysisHtml
      +generatedHtml
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
