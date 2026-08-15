from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

APP_DIR = Path.home() / ".wordmap_mobile"
CONFIG_PATH = APP_DIR / "config.json"
APP_DIR.mkdir(parents=True, exist_ok=True)

STOPWORDS = set(
    "그리고 그러나 하지만 또한 대한 위한 통해 때문 경우 이것 저것 그것 더 및 같은 "
    "있는 없는 합니다 됩니다 입니다 있다 없다 한다 했다 되다 된다 하는 수 것 저 그 "
    "이 를 을 은 는 가 와 과 의 에 도 로 한 할 함".split()
)

PARTICLES = sorted(
    "으로부터 에게서 한테서 에서는 으로는 로부터 에게는 한테는 이라는 이라고 이라면 "
    "이면 에서 에게 한테 으로 까지 부터 처럼 보다 마다 조차 마저 밖에 라도 이나 든지 "
    "하고 입니다 이었다 였다 이다 하는 한다 했다 되는 된다 됐다 와 과 은 는 이 가 을 "
    "를 의 에 도 만 로 나 든".split(),
    key=len,
    reverse=True,
)

TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9_+\-./]{0,}")
PAIR_SEP = "\x1f"
SKIP = {
    "Android", ".Trash", ".thumbnails", ".cache", ".git", "node_modules",
    "DCIM", "Movies", "Music", "Pictures", "Podcasts", "Ringtones", "Alarms",
}


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg):
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def roots():
    raw = [
        Path.home() / "storage" / "shared",
        Path("/storage/emulated/0"),
        Path("/sdcard"),
    ]
    out, seen = [], set()
    for p in raw:
        try:
            resolved = str(p.resolve())
            if p.exists() and resolved not in seen:
                seen.add(resolved)
                out.append(p)
        except Exception:
            pass
    return out


def is_vault(path):
    try:
        p = Path(path)
        return p.is_dir() and (p / ".obsidian").is_dir()
    except Exception:
        return False


def find_vaults(max_depth=7):
    found = set()

    for root in roots():
        quick = [
            root,
            root / "Documents",
            root / "Documents" / "Obsidian",
            root / "Obsidian",
            root / "Notes",
            root / "Download",
        ]
        for p in quick:
            try:
                if is_vault(p):
                    found.add(str(p.resolve()))
                if p.is_dir():
                    for child in p.iterdir():
                        if is_vault(child):
                            found.add(str(child.resolve()))
            except Exception:
                pass

    for root in roots():
        try:
            root_depth = len(root.resolve().parts)
            for cur, dirs_list, _ in os.walk(root, topdown=True):
                cp = Path(cur)
                if len(cp.parts) - root_depth > max_depth:
                    dirs_list[:] = []
                    continue

                if ".obsidian" in dirs_list:
                    found.add(str(cp.resolve()))
                    dirs_list.remove(".obsidian")

                dirs_list[:] = [
                    d for d in dirs_list
                    if d not in SKIP and not d.startswith(".")
                ]
        except Exception:
            pass

    return sorted(found)


def current_vault():
    cfg = load_config()
    saved = cfg.get("vault_path")

    if saved and is_vault(saved):
        return Path(saved)

    vaults = find_vaults()
    if len(vaults) == 1:
        cfg["vault_path"] = vaults[0]
        save_config(cfg)
        return Path(vaults[0])

    return None


def set_vault(path):
    p = Path(path).expanduser()
    if not is_vault(p):
        raise ValueError("선택한 폴더에 .obsidian 폴더가 없습니다.")

    cfg = load_config()
    cfg["vault_path"] = str(p.resolve())
    save_config(cfg)
    wordmap_dirs(p)
    return str(p.resolve())


def wordmap_dirs(vault):
    root = Path(vault) / "WordMap"
    result = {
        "root": root,
        "words": root / "Words",
        "corpus": root / "Corpus",
        "meta": root / ".wordmap",
    }
    for p in result.values():
        p.mkdir(parents=True, exist_ok=True)
    return result


# Backward-compatible name used by older code.
dirs = wordmap_dirs


def strip_particle(token):
    for suffix in PARTICLES:
        if token.endswith(suffix):
            base = token[:-len(suffix)]
            if base and re.search(r"[가-힣A-Za-z0-9]", base):
                return base
    return token


def tokenize(text):
    out = []
    for raw in TOKEN_RE.findall(text.lower()):
        token = strip_particle(raw.strip("._-/"))
        if not token or token in STOPWORDS:
            continue
        if len(token) < 2 and not re.fullmatch(r"[가-힣]", token):
            continue
        out.append(token)
    return out


def split_sentences(text):
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [
        x.strip()
        for x in re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)
        if x.strip()
    ]


def pairkey(a, b):
    return PAIR_SEP.join(sorted((a, b)))


def safe(token):
    name = re.sub(r'[\\/:*?"<>|]', "_", token).strip(" .")
    return (name or hashlib.sha1(token.encode()).hexdigest()[:12])[:100]


def empty_graph():
    return {"version": 4, "nodes": {}, "pairs": {}, "edges": {}}


def graph_file(vault):
    return wordmap_dirs(vault)["meta"] / "graph.json"


def load_graph(vault):
    p = graph_file(vault)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return empty_graph()


def save_graph(vault, graph):
    graph_file(vault).write_text(
        json.dumps(graph, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rebuild_edges(graph):
    edges = defaultdict(dict)
    nodes = graph.get("nodes", {})

    for key, co in graph.get("pairs", {}).items():
        try:
            a, b = key.split(PAIR_SEP, 1)
        except ValueError:
            continue

        fa = max(1.0, float(nodes.get(a, {}).get("frequency", 1)))
        fb = max(1.0, float(nodes.get(b, {}).get("frequency", 1)))
        score = round(float(co) / math.sqrt(fa * fb), 6)
        co = round(float(co), 4)

        edges[a][b] = {"co": co, "score": score}
        edges[b][a] = {"co": co, "score": score}

    graph["edges"] = dict(edges)
    return graph


def analyze_into_graph(graph, text, window=4):
    nodes = graph.setdefault("nodes", {})
    pairs = graph.setdefault("pairs", {})

    freq = Counter()
    pair_counts = Counter()
    sentences = split_sentences(text)

    for sentence in sentences:
        tokens = tokenize(sentence)
        freq.update(tokens)

        for i, a in enumerate(tokens):
            for j in range(i + 1, min(i + 1 + window, len(tokens))):
                b = tokens[j]
                if a != b:
                    pair_counts[pairkey(a, b)] += 1 / (j - i)

    for token, count in freq.items():
        old = int(nodes.get(token, {}).get("frequency", 0))
        nodes[token] = {"frequency": old + int(count)}

    for key, count in pair_counts.items():
        pairs[key] = round(float(pairs.get(key, 0)) + float(count), 4)

    return {
        "sentences": len(sentences),
        "tokens": int(sum(freq.values())),
        "unique_tokens": len(freq),
    }


def save_notes(vault, graph, top=30):
    words_dir = wordmap_dirs(vault)["words"]
    stamp = datetime.now().isoformat(timespec="seconds")

    for token, meta in graph.get("nodes", {}).items():
        ranked = sorted(
            graph.get("edges", {}).get(token, {}).items(),
            key=lambda x: x[1].get("score", 0),
            reverse=True,
        )[:top]

        links = "\n".join(
            f"- [[{safe(neighbor)}|{neighbor}]] · "
            f"strength={edge['score']:.4f} · co={edge['co']:.2f}"
            for neighbor, edge in ranked
        ) or "- 연결 단어 없음"

        body = (
            "---\n"
            "type: word-node\n"
            f'token: "{token.replace(chr(34), chr(39))}"\n'
            f"frequency: {int(meta.get('frequency', 0))}\n"
            f'updated: "{stamp}"\n'
            "---\n\n"
            f"# {token}\n\n"
            f"빈도: **{int(meta.get('frequency', 0))}**\n\n"
            "## 연결 단어\n"
            f"{links}\n"
        )

        (words_dir / f"{safe(token)}.md").write_text(body, encoding="utf-8")


def corpus_body(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n", text, flags=re.S)
        if match:
            return text[match.end():]
    return text


def ingest(vault, text, source="mobile", window=4):
    if not text.strip():
        raise ValueError("말뭉치가 비어 있습니다.")

    graph = load_graph(vault)
    stats = analyze_into_graph(graph, text, window=window)
    graph["updated"] = datetime.now().isoformat(timespec="seconds")
    rebuild_edges(graph)

    d = wordmap_dirs(vault)
    save_graph(vault, graph)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    source_name = source or "mobile"
    corpus_path = d["corpus"] / f"{stamp}_{safe(source_name)}.md"
    safe_source = source_name.replace('"', "'")
    corpus_path.write_text(
        f'---\ntype: corpus\nsource: "{safe_source}"\n---\n\n{text}',
        encoding="utf-8",
    )

    save_notes(vault, graph)

    return {
        "sentences": stats["sentences"],
        "tokens_in_document": stats["tokens"],
        "unique_tokens_in_document": stats["unique_tokens"],
        "total_nodes": len(graph.get("nodes", {})),
        "total_pairs": len(graph.get("pairs", {})),
        "vault": str(vault),
        "corpus_note": str(corpus_path),
    }


def rebuild_wordmap(vault, window=4):
    """Rebuild Words and graph.json from saved Corpus documents.

    Corpus is treated as source-of-truth and is never deleted here.
    """
    d = wordmap_dirs(vault)
    corpus_files = sorted(
        [*d["corpus"].glob("*.md"), *d["corpus"].glob("*.txt")]
    )

    if not corpus_files:
        raise ValueError("저장된 Corpus 말뭉치가 없습니다.")

    graph = empty_graph()
    totals = {
        "documents": 0,
        "sentences": 0,
        "tokens": 0,
    }

    for path in corpus_files:
        text = corpus_body(path)
        if not text.strip():
            continue

        stats = analyze_into_graph(graph, text, window=window)
        totals["documents"] += 1
        totals["sentences"] += stats["sentences"]
        totals["tokens"] += stats["tokens"]

    if totals["documents"] == 0:
        raise ValueError("내용이 있는 Corpus 말뭉치가 없습니다.")

    graph["updated"] = datetime.now().isoformat(timespec="seconds")
    rebuild_edges(graph)

    # Only generated outputs are removed. Corpus remains untouched.
    for old_note in d["words"].glob("*.md"):
        try:
            old_note.unlink()
        except FileNotFoundError:
            pass

    save_graph(vault, graph)
    save_notes(vault, graph)

    return {
        "rebuilt": True,
        "corpus_preserved": True,
        "documents": totals["documents"],
        "sentences": totals["sentences"],
        "tokens": totals["tokens"],
        "total_nodes": len(graph.get("nodes", {})),
        "total_pairs": len(graph.get("pairs", {})),
        "vault": str(vault),
    }


def ask(vault, question, limit=20, depth=2):
    graph = load_graph(vault)
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", {})
    query_tokens = tokenize(question)

    seeds = []
    for token in query_tokens:
        if token in nodes and token not in seeds:
            seeds.append(token)

    if not seeds:
        for query in query_tokens:
            for node in [n for n in nodes if query in n or n in query][:5]:
                if node not in seeds:
                    seeds.append(node)

    scores = defaultdict(float)
    reasons = defaultdict(list)
    frontier = {}

    for seed in seeds:
        scores[seed] += 5
        reasons[seed].append(f"질문 직접 일치: {seed}")
        frontier[seed] = 1

    for hop in range(1, max(1, min(int(depth), 4)) + 1):
        next_frontier = defaultdict(float)
        for source, strength in frontier.items():
            ranked = sorted(
                edges.get(source, {}).items(),
                key=lambda x: x[1].get("score", 0),
                reverse=True,
            )[:40]

            for target, meta in ranked:
                contribution = (
                    strength
                    * float(meta.get("score", 0))
                    * (0.62 ** hop)
                )
                if contribution > 0:
                    scores[target] += contribution
                    next_frontier[target] += contribution
                    reasons[target].append(f"{hop}홉: {source} → {target}")

        frontier = dict(
            sorted(
                next_frontier.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:30]
        )

    ranked = sorted(
        scores.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:max(1, min(int(limit), 100))]

    return {
        "question": question,
        "query_tokens": query_tokens,
        "seed_tokens": seeds,
        "results": [
            {
                "token": token,
                "score": round(score, 6),
                "frequency": int(nodes.get(token, {}).get("frequency", 0)),
                "reasons": reasons[token][:4],
            }
            for token, score in ranked
        ],
        "warning": None if seeds else "질문과 직접 연결되는 시작 단어를 찾지 못했습니다.",
    }


def status():
    vault = current_vault()
    vaults = find_vaults()
    out = {
        "vault": str(vault) if vault else None,
        "vaults": vaults,
    }

    if vault:
        graph = load_graph(vault)
        d = wordmap_dirs(vault)
        corpus_count = len(list(d["corpus"].glob("*.md"))) + len(
            list(d["corpus"].glob("*.txt"))
        )
        out.update(
            nodes=len(graph.get("nodes", {})),
            pairs=len(graph.get("pairs", {})),
            corpus_documents=corpus_count,
            updated=graph.get("updated"),
        )

    return out
