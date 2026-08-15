from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "0.3.4"

MAX_NEIGHBORS = 10
MIN_EDGE_SCORE = 0.11
MIN_EDGE_CO = 0.30
HUB_PENALTY = 0.38

MIN_NODE_FREQUENCY = 2
RARE_KEEP_SCORE = 0.18
RARE_KEEP_HIGH_SCORE = 0.32
RARE_REQUIRED_STRONG_NEIGHBORS = 2

EXTRA_STOPWORDS = set(
    """
    그래서 따라서 그러므로 또는 혹은 여기 저기 가장 함께 다시 계속 우선 사실 실제
    현재 처음 정도 여러 모든 각각 관련 매우 정말 너무 자주 그냥 바로 이미 아직 이후
    이전 높다 낮다 많다 적다 같다 경우 부분 통해 위한 대한 때문 조금 약간 어느 어떤
    하나 하나씩 오랫동안
    """.split()
)

GENERIC_HUBS = set(
    """
    단어 연결 사용 데이터 정보 문서 질문 그래프 분석 결과 과정 방법 관계 개념 기능
    시스템 내용 자료 형태 의미 표현 구조 문제 작업 상태 처리 입력 출력 생성 저장 검색
    선택 변화 비교 확인 적용 관리
    """.split()
)

DOMAIN_ALLOWLIST = {
    "mbts", "sbr", "nbr", "hnbr", "epdm", "br", "cr", "ir",
    "erp", "llm", "rag", "ocr", "api", "gpu", "cpu", "ai", "ml",
    "json", "csv", "pvi", "zno", "doa", "totm", "tespt",
}

PARTICLES = sorted(
    """
    으로부터 에게서 한테서 까지는 에서는 으로는 로부터 에게는 한테는
    에서의 에게도 한테도 으로의 로의 에는 에도
    이라는 이라고 이라면 이면 에서 에게 한테 으로 까지 부터 처럼
    보다 마다 조차 마저 밖에 라도 이나 든지 하고
    와 과 은 는 이 가 을 를 의 에 도 만 로 나 든
    """.split(),
    key=len,
    reverse=True,
)

ENDINGS = sorted(
    """
    하였습니다 하였다 하였고 하였으며 하였으면 하였던
    했습니다 했다 했고 했으며 했으면 했던 해서
    합니다 하는 한다 하면 하며 하고 하여 하려고 하면서
    되었습니다 되었다 되었고 되었으며 되었으면 되었던
    됩니다 되는 된다 되면 되며 되고 되어 되어서 됐다
    시킵니다 시키는 시킨다 시키면 시키며 시키고 시켜
    이었습니다 이었다 였습니다 였다 입니다 이다
    """.split(),
    key=len,
    reverse=True,
)

SPECIAL_CANONICAL = {
    "만들어진다": "만들다",
    "만들어진": "만들다",
    "만들어졌다": "만들다",
    "만든다": "만들다",
    "만들면": "만들다",
    "만들고": "만들다",
    "찾는다": "찾다",
    "찾으면": "찾다",
    "찾았다": "찾다",
    "읽는다": "읽다",
    "읽으면": "읽다",
    "읽었다": "읽다",
    "높인다": "높이다",
    "높이면": "높이다",
    "낮춘다": "낮추다",
    "낮추면": "낮추다",
}

TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9_+\-./]{0,}")
FILE_EXT_RE = re.compile(
    r"\.(?:md|txt|json|jsonl|csv|tsv|py|js|ts|html?|pdf|png|jpe?g|webp|zip)$",
    re.I,
)
DATEISH_RE = re.compile(r"(?:19|20)\d{2}[-_.]?\d{1,2}[-_.]?\d{1,2}")
LONG_DIGITS_RE = re.compile(r"\d{6,}")


def is_noise_token(token: str) -> bool:
    low = token.lower()
    if low.startswith(("http", "www.")):
        return True
    if "/" in token or "\\" in token:
        return True
    if FILE_EXT_RE.search(token):
        return True
    if DATEISH_RE.fullmatch(token):
        return True
    if LONG_DIGITS_RE.fullmatch(token):
        return True
    if len(token) > 36:
        return True
    if token.count("_") >= 2 and re.search(r"\d", token):
        return True
    return False


def is_domain_token(token: str) -> bool:
    low = token.lower()
    if low in DOMAIN_ALLOWLIST:
        return True
    if re.fullmatch(r"[a-z]+[a-z0-9+\-]*\d+[a-z0-9+\-]*", low):
        return True
    if re.fullmatch(r"\d{3,5}[a-z]*", low):
        return True
    return False


def strip_suffixes(token: str) -> str:
    current = token
    for suffix in PARTICLES:
        if current.endswith(suffix):
            base = current[:-len(suffix)]
            if base and re.search(r"[가-힣A-Za-z0-9]", base):
                current = base
                break

    if current in SPECIAL_CANONICAL:
        return SPECIAL_CANONICAL[current]

    for suffix in ENDINGS:
        if current.endswith(suffix):
            base = current[:-len(suffix)]
            if len(base) >= 2 and re.search(r"[가-힣]", base):
                current = base
                break

    return SPECIAL_CANONICAL.get(current, current)


def make_tokenize(core):
    stopwords = set(core.STOPWORDS) | EXTRA_STOPWORDS

    def tokenize(text):
        out = []
        for raw in TOKEN_RE.findall(text):
            token = raw.strip("._-/")
            if not token:
                continue
            token = token.lower()
            if is_noise_token(token):
                continue
            token = strip_suffixes(token)
            if not token or token in stopwords or is_noise_token(token):
                continue
            if len(token) < 2 and not re.fullmatch(r"[가-힣]", token):
                continue
            out.append(token)
        return out

    return tokenize


def edge_score(a, b, co, nodes):
    fa = max(1.0, float(nodes.get(a, {}).get("frequency", 1)))
    fb = max(1.0, float(nodes.get(b, {}).get("frequency", 1)))
    score = float(co) / math.sqrt(fa * fb)
    score *= min(1.0, float(co))
    if a in GENERIC_HUBS:
        score *= HUB_PENALTY
    if b in GENERIC_HUBS:
        score *= HUB_PENALTY
    return score


def make_rebuild_edges(core):
    def rebuild_edges(graph):
        nodes = graph.get("nodes", {})
        candidates = []

        for key, co_value in graph.get("pairs", {}).items():
            try:
                a, b = key.split(core.PAIR_SEP, 1)
            except ValueError:
                continue
            if is_noise_token(a) or is_noise_token(b):
                continue

            co = float(co_value)
            if co < MIN_EDGE_CO:
                continue

            score = edge_score(a, b, co, nodes)
            if score < MIN_EDGE_SCORE:
                continue

            candidates.append((score, co, a, b))

        strong_neighbor_count = Counter()
        best_rare_score = defaultdict(float)

        for score, _co, a, b in candidates:
            fa = int(nodes.get(a, {}).get("frequency", 0))
            fb = int(nodes.get(b, {}).get("frequency", 0))

            if fa < MIN_NODE_FREQUENCY and fb >= MIN_NODE_FREQUENCY and score >= RARE_KEEP_SCORE:
                strong_neighbor_count[a] += 1
                best_rare_score[a] = max(best_rare_score[a], score)

            if fb < MIN_NODE_FREQUENCY and fa >= MIN_NODE_FREQUENCY and score >= RARE_KEEP_SCORE:
                strong_neighbor_count[b] += 1
                best_rare_score[b] = max(best_rare_score[b], score)

        def eligible(token):
            freq = int(nodes.get(token, {}).get("frequency", 0))
            if freq >= MIN_NODE_FREQUENCY:
                return True
            if is_domain_token(token):
                return True
            if strong_neighbor_count[token] >= RARE_REQUIRED_STRONG_NEIGHBORS:
                return True
            if best_rare_score[token] >= RARE_KEEP_HIGH_SCORE:
                return True
            return False

        candidates = [
            item for item in candidates
            if eligible(item[2]) and eligible(item[3])
        ]
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

        degree = Counter()
        edges = defaultdict(dict)

        for score, co, a, b in candidates:
            if degree[a] >= MAX_NEIGHBORS or degree[b] >= MAX_NEIGHBORS:
                continue

            meta = {"co": round(co, 4), "score": round(score, 6)}
            edges[a][b] = meta
            edges[b][a] = meta
            degree[a] += 1
            degree[b] += 1

        active_nodes = {token for token, neighbors in edges.items() if neighbors}
        rare_kept = sum(
            1 for token in active_nodes
            if int(nodes.get(token, {}).get("frequency", 0)) < MIN_NODE_FREQUENCY
        )

        graph["edges"] = dict(edges)
        graph["cleaning"] = {
            "version": VERSION,
            "max_neighbors": MAX_NEIGHBORS,
            "min_edge_score": MIN_EDGE_SCORE,
            "min_edge_co": MIN_EDGE_CO,
            "hub_penalty": HUB_PENALTY,
            "min_node_frequency": MIN_NODE_FREQUENCY,
            "rare_keep_score": RARE_KEEP_SCORE,
            "rare_keep_high_score": RARE_KEEP_HIGH_SCORE,
            "active_edges": sum(len(v) for v in edges.values()) // 2,
            "active_nodes": len(active_nodes),
            "raw_nodes": len(nodes),
            "rare_nodes_kept": rare_kept,
        }
        return graph

    return rebuild_edges


def make_wordmap_dirs(core):
    def wordmap_dirs(vault):
        root = Path(vault) / "WordMap"
        meta = root / ".wordmap"
        words = root / "Words"
        hidden_corpus = meta / "Corpus"
        legacy_corpus = root / "Corpus"

        for p in (root, meta, words, hidden_corpus):
            p.mkdir(parents=True, exist_ok=True)

        if legacy_corpus.is_dir():
            for source in list(legacy_corpus.iterdir()):
                if not source.is_file() or source.suffix.lower() not in {".md", ".txt"}:
                    continue

                target = hidden_corpus / source.name
                if target.exists():
                    stem, suffix = source.stem, source.suffix
                    i = 1
                    while target.exists():
                        target = hidden_corpus / f"{stem}_legacy{i}{suffix}"
                        i += 1
                source.replace(target)

            try:
                legacy_corpus.rmdir()
            except OSError:
                pass

        return {
            "root": root,
            "words": words,
            "corpus": hidden_corpus,
            "meta": meta,
        }

    return wordmap_dirs


def make_save_notes(core, original_save_notes):
    def save_notes(vault, graph, top=30):
        d = core.wordmap_dirs(vault)
        words_dir = d["words"]

        for old_note in words_dir.glob("*.md"):
            try:
                old_note.unlink()
            except FileNotFoundError:
                pass

        active = {
            token
            for token, neighbors in graph.get("edges", {}).items()
            if neighbors
        }

        visible_graph = dict(graph)
        visible_graph["nodes"] = {
            token: meta
            for token, meta in graph.get("nodes", {}).items()
            if token in active
        }
        visible_graph["edges"] = {
            token: {
                neighbor: meta
                for neighbor, meta in neighbors.items()
                if neighbor in active
            }
            for token, neighbors in graph.get("edges", {}).items()
            if token in active
        }

        return original_save_notes(
            vault,
            visible_graph,
            top=min(int(top), MAX_NEIGHBORS),
        )

    return save_notes


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out

        graph = core.load_graph(Path(vault))
        cleaning = graph.get("cleaning", {})
        out["raw_nodes"] = len(graph.get("nodes", {}))
        out["nodes"] = int(cleaning.get("active_nodes", out.get("nodes", 0)))
        out["pairs"] = int(cleaning.get("active_edges", out.get("pairs", 0)))
        out["rare_nodes_kept"] = int(cleaning.get("rare_nodes_kept", 0))
        return out

    return status


def apply(core):
    original_save_notes = core.save_notes
    original_status = core.status

    core.STOPWORDS.update(EXTRA_STOPWORDS)
    core.wordmap_dirs = make_wordmap_dirs(core)
    core.dirs = core.wordmap_dirs
    core.tokenize = make_tokenize(core)
    core.strip_particle = strip_suffixes
    core.rebuild_edges = make_rebuild_edges(core)
    core.save_notes = make_save_notes(core, original_save_notes)
    core.status = make_status(core, original_status)

    return core
