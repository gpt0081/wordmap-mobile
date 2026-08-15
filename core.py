from __future__ import annotations
import hashlib, json, math, os, re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

APP_DIR = Path.home()/'.wordmap_mobile'
CONFIG_PATH = APP_DIR/'config.json'
APP_DIR.mkdir(parents=True, exist_ok=True)

STOPWORDS = set('그리고 그러나 하지만 또한 대한 위한 통해 때문 경우 이것 저것 그것 더 및 같은 있는 없는 합니다 됩니다 입니다 있다 없다 한다 했다 되다 된다 하는 수 것 저 그 이 를 을 은 는 가 와 과 의 에 도 로 한 할 함'.split())
PARTICLES = sorted('으로부터 에게서 한테서 에서는 으로는 로부터 에게는 한테는 이라는 이라고 이라면 이면 에서 에게 한테 으로 까지 부터 처럼 보다 마다 조차 마저 밖에 라도 이나 든지 하고 입니다 이었다 였다 이다 하는 한다 했다 되는 된다 됐다 와 과 은 는 이 가 을 를 의 에 도 만 로 나 든'.split(), key=len, reverse=True)
TOKEN_RE = re.compile(r'[가-힣A-Za-z0-9][가-힣A-Za-z0-9_+\-./]{0,}')
PAIR_SEP='\x1f'
SKIP={'Android','.Trash','.thumbnails','.cache','.git','node_modules','DCIM','Movies','Music','Pictures','Podcasts','Ringtones','Alarms'}

def load_config():
    try: return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
    except Exception: return {}

def save_config(cfg): CONFIG_PATH.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')

def roots():
    raw=[Path.home()/'storage'/'shared',Path('/storage/emulated/0'),Path('/sdcard')]
    out=[]; seen=set()
    for p in raw:
        try:
            if p.exists() and str(p.resolve()) not in seen:
                seen.add(str(p.resolve())); out.append(p)
        except Exception: pass
    return out

def is_vault(p):
    try: return Path(p).is_dir() and (Path(p)/'.obsidian').is_dir()
    except Exception: return False

def find_vaults(max_depth=7):
    found=set()
    for root in roots():
        for p in [root,root/'Documents',root/'Documents'/'Obsidian',root/'Obsidian',root/'Notes',root/'Download']:
            try:
                if is_vault(p): found.add(str(p.resolve()))
                if p.is_dir():
                    for c in p.iterdir():
                        if is_vault(c): found.add(str(c.resolve()))
            except Exception: pass
    for root in roots():
        try:
            rd=len(root.resolve().parts)
            for cur,dirs,_ in os.walk(root,topdown=True):
                cp=Path(cur)
                if len(cp.parts)-rd>max_depth: dirs[:]=[]; continue
                if '.obsidian' in dirs:
                    found.add(str(cp.resolve())); dirs.remove('.obsidian')
                dirs[:]=[d for d in dirs if d not in SKIP and not d.startswith('.')]
        except Exception: pass
    return sorted(found)

def current_vault():
    cfg=load_config(); saved=cfg.get('vault_path')
    if saved and is_vault(saved): return Path(saved)
    vs=find_vaults()
    if len(vs)==1:
        cfg['vault_path']=vs[0]; save_config(cfg); return Path(vs[0])
    return None

def set_vault(path):
    p=Path(path).expanduser()
    if not is_vault(p): raise ValueError('선택한 폴더에 .obsidian 폴더가 없습니다.')
    cfg=load_config(); cfg['vault_path']=str(p.resolve()); save_config(cfg); dirs(p)
    return str(p.resolve())

def dirs(vault):
    root=Path(vault)/'WordMap'; d={'root':root,'words':root/'Words','corpus':root/'Corpus','meta':root/'.wordmap'}
    for p in d.values(): p.mkdir(parents=True,exist_ok=True)
    return d

def strip_particle(token):
    for s in PARTICLES:
        if token.endswith(s):
            b=token[:-len(s)]
            if b and re.search(r'[가-힣A-Za-z0-9]',b): return b
    return token

def tokenize(text):
    out=[]
    for raw in TOKEN_RE.findall(text.lower()):
        t=strip_particle(raw.strip('._-/'))
        if not t or t in STOPWORDS: continue
        if len(t)<2 and not re.fullmatch(r'[가-힣]',t): continue
        out.append(t)
    return out

def split_sentences(text): return [x.strip() for x in re.split(r'(?<=[.!?。！？])\s+|\n+',text.replace('\r','')) if x.strip()]
def pairkey(a,b): return PAIR_SEP.join(sorted((a,b)))
def safe(t):
    n=re.sub(r'[\\/:*?"<>|]','_',t).strip(' .')
    return (n or hashlib.sha1(t.encode()).hexdigest()[:12])[:100]

def load_graph(vault):
    p=dirs(vault)['meta']/'graph.json'
    try: return json.loads(p.read_text(encoding='utf-8'))
    except Exception: return {'version':3,'nodes':{},'pairs':{},'edges':{}}

def rebuild_edges(g):
    e=defaultdict(dict); nodes=g.get('nodes',{})
    for k,co in g.get('pairs',{}).items():
        try: a,b=k.split(PAIR_SEP,1)
        except ValueError: continue
        fa=max(1,float(nodes.get(a,{}).get('frequency',1))); fb=max(1,float(nodes.get(b,{}).get('frequency',1)))
        score=round(float(co)/math.sqrt(fa*fb),6)
        e[a][b]={'co':round(float(co),4),'score':score}; e[b][a]={'co':round(float(co),4),'score':score}
    g['edges']=dict(e); return g

def save_notes(vault,g,top=30):
    wd=dirs(vault)['words']; stamp=datetime.now().isoformat(timespec='seconds')
    for token,meta in g.get('nodes',{}).items():
        ranked=sorted(g.get('edges',{}).get(token,{}).items(),key=lambda x:x[1].get('score',0),reverse=True)[:top]
        links='\n'.join(f"- [[{safe(n)}|{n}]] · strength={m['score']:.4f} · co={m['co']:.2f}" for n,m in ranked) or '- 연결 단어 없음'
        body=f'''---\ntype: word-node\ntoken: "{token.replace(chr(34),chr(39))}"\nfrequency: {int(meta.get('frequency',0))}\nupdated: "{stamp}"\n---\n\n# {token}\n\n빈도: **{int(meta.get('frequency',0))}**\n\n## 연결 단어\n{links}\n'''
        (wd/f'{safe(token)}.md').write_text(body,encoding='utf-8')

def ingest(vault,text,source='mobile',window=4):
    if not text.strip(): raise ValueError('말뭉치가 비어 있습니다.')
    g=load_graph(vault); nodes=g.setdefault('nodes',{}); pairs=g.setdefault('pairs',{})
    freq=Counter(); pc=Counter(); ss=split_sentences(text)
    for s in ss:
        ts=tokenize(s); freq.update(ts)
        for i,a in enumerate(ts):
            for j in range(i+1,min(i+1+window,len(ts))):
                b=ts[j]
                if a!=b: pc[pairkey(a,b)]+=1/(j-i)
    for t,c in freq.items(): nodes[t]={'frequency':int(nodes.get(t,{}).get('frequency',0))+int(c)}
    for k,c in pc.items(): pairs[k]=round(float(pairs.get(k,0))+float(c),4)
    g['updated']=datetime.now().isoformat(timespec='seconds'); rebuild_edges(g)
    d=dirs(vault); (d['meta']/'graph.json').write_text(json.dumps(g,ensure_ascii=False,indent=2),encoding='utf-8')
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f'); src=safe(source or 'mobile')
    cp=d['corpus']/f'{stamp}_{src}.md'; cp.write_text(f'---\ntype: corpus\nsource: "{source}"\n---\n\n{text}',encoding='utf-8')
    save_notes(vault,g)
    return {'sentences':len(ss),'tokens_in_document':sum(freq.values()),'unique_tokens_in_document':len(freq),'total_nodes':len(nodes),'total_pairs':len(pairs),'vault':str(vault),'corpus_note':str(cp)}

def ask(vault,question,limit=20,depth=2):
    g=load_graph(vault); nodes=g.get('nodes',{}); edges=g.get('edges',{}); qt=tokenize(question)
    seeds=[]
    for t in qt:
        if t in nodes and t not in seeds: seeds.append(t)
    if not seeds:
        for q in qt:
            for n in [n for n in nodes if q in n or n in q][:5]:
                if n not in seeds: seeds.append(n)
    scores=defaultdict(float); reasons=defaultdict(list); frontier={}
    for s in seeds: scores[s]+=5; reasons[s].append(f'질문 직접 일치: {s}'); frontier[s]=1
    for hop in range(1,max(1,min(int(depth),4))+1):
        nxt=defaultdict(float)
        for source,strength in frontier.items():
            for target,m in sorted(edges.get(source,{}).items(),key=lambda x:x[1].get('score',0),reverse=True)[:40]:
                c=strength*float(m.get('score',0))*(0.62**hop)
                if c>0: scores[target]+=c; nxt[target]+=c; reasons[target].append(f'{hop}홉: {source} → {target}')
        frontier=dict(sorted(nxt.items(),key=lambda x:x[1],reverse=True)[:30])
    ranked=sorted(scores.items(),key=lambda x:x[1],reverse=True)[:max(1,min(int(limit),100))]
    return {'question':question,'query_tokens':qt,'seed_tokens':seeds,'results':[{'token':t,'score':round(s,6),'frequency':int(nodes.get(t,{}).get('frequency',0)),'reasons':reasons[t][:4]} for t,s in ranked],'warning':None if seeds else '질문과 직접 연결되는 시작 단어를 찾지 못했습니다.'}

def status():
    v=current_vault(); vs=find_vaults(); out={'vault':str(v) if v else None,'vaults':vs}
    if v:
        g=load_graph(v); out.update(nodes=len(g.get('nodes',{})),pairs=len(g.get('pairs',{})),updated=g.get('updated'))
    return out
