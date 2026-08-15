from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

VERSION = "0.3.2"
MAX_NEIGHBORS = 14
MIN_EDGE_SCORE = 0.08
MIN_EDGE_CO = 0.25
HUB_PENALTY = 0.55

EXTRA_STOPWORDS = set(
    """
    그래서 따라서 그러므로 또는 혹은 여기 저기 가장 함께 다시 계속 우선 사실 실제
    현재 처음 정도 여러 모든 각각 관련 매우 정말 너무 자주 그냥 바로 이미 아직 이후
    이전 높다 낮다 많다 적다 같다
    """.split()
)

GENERIC_HUBS = set(
    """
    단어 연결 사용 데이터 정보 문서 질문 그래프 분석 결과 과정 방법 관계 개념 기능
    시스템 내용 자료 형태 의미 표현 구조 문제 작업
    """.split()
)

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
    하였습니다 하였다 하였고 하였으며 하였으면
    했습니다 했다 했고 했으며 했으면 해서
    합니다 하는 한다 하면 하며 하고 하여
    되었습니다 되었다 되었고 되었으며 되었으면
    됩니다 되는 된다 되면 되며 되고 되어 됐다
    시킵니다 시키는 시킨다 시키면 시키며 시키고 시켜
    입니다 이었다 였다 이다
    """.split(),
    key=len,
    reverse=True,
)

TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9_+\-./]{0,}")


def strip_suffixes(token):
    current = token

    # One particle pass only. Combined particles are listed explicitly.
    # This avoids corrupting nouns such as "사이의" -> "사".
    for suffix in PARTICLES:
        if current.endswith(suffix):
            base = current[:-len(suffix)]
            if base and re.search(r"[가-힣A-Za-z0-9]", base):
                current = base
                break

    # Collapse common 하다/되다 forms:
    # 사용하면/사용했다/사용한다 -> 사용
    for suffix in ENDINGS:
        if current.endswith(suffix):
            base = current[:-len(suffix)]
            if len(base) >= 2 and re.search(r"[가-힣]", base):
                current = base
                break

    return current


def make_tokenize(core):
    stopwords = set(core.STOPWORDS) | EXTRA_STOPWORDS

    def tokenize(text):
        out = []
        for raw in TOKEN_RE.findall(text.lower()):
            token = strip_suffixes(raw.strip("._-/"))
            if not token or token in stopwords:
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

    # A single weak/far co-occurrence gets discounted.
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

            co = float(co_value)
            if co < MIN_EDGE_CO:
                continue

            score = edge_score(a, b, co, nodes)
            if score < MIN_EDGE_SCORE:
                continue

            candidates.append((score, co, a, b))

        # Global strongest-first pruning with a hard degree cap.
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        degree = Counter()
        edges = defaultdict(dict)

        for score, co, a, b in candidates:
            if degree[a] >= MAX_NEIGHBORS or degree[b] >= MAX_NEIGHBORS:
                continue

            meta = {
                "co": round(co, 4),
                "score": round(score, 6),
            }
            edges[a][b] = meta
            edges[b][a] = meta
            degree[a] += 1
            degree[b] += 1

        graph["edges"] = dict(edges)
        graph["cleaning"] = {
            "version": VERSION,
            "max_neighbors": MAX_NEIGHBORS,
            "min_edge_score": MIN_EDGE_SCORE,
            "min_edge_co": MIN_EDGE_CO,
            "hub_penalty": HUB_PENALTY,
            "active_edges": sum(len(v) for v in edges.values()) // 2,
        }
        return graph

    return rebuild_edges


def apply(core):
    """Patch the existing core module without touching Corpus data."""
    core.STOPWORDS.update(EXTRA_STOPWORDS)
    core.tokenize = make_tokenize(core)
    core.strip_particle = strip_suffixes
    core.rebuild_edges = make_rebuild_edges(core)
    return core
