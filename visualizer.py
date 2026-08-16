from __future__ import annotations

import math
from collections import defaultdict

VERSION = "0.11.0"
DEFAULT_LIMIT = 160
MAX_ASSOC_EDGES = 360
MAX_SEQUENCE_EDGES = 260


def _relations(graph):
    rels = graph.get("relations", {})
    if isinstance(rels, dict):
        return list(rels.values())
    if isinstance(rels, list):
        return rels
    return []


def _generation_bigrams(graph):
    data = graph.get("generation", {}) or {}
    if data.get("bigrams"):
        return data.get("bigrams", {}) or {}
    return graph.get("sequence", {}).get("bigrams", {}) or {}


def _node_score(meta):
    freq = max(0, int((meta or {}).get("frequency", 0)))
    return math.log1p(freq)


def _select_nodes(graph, focus=None, active=None, generation_path=None, limit=DEFAULT_LIMIT):
    nodes = graph.get("nodes", {}) or {}
    focus = [x for x in (focus or []) if x]
    generation_path = [x for x in (generation_path or []) if x]
    active = active or []

    scores = defaultdict(float)
    for token, meta in nodes.items():
        scores[token] += 0.10 * _node_score(meta)

    for token in focus:
        scores[token] += 100.0
    for token in generation_path:
        scores[token] += 90.0
    for row in active:
        token = row.get("표제어")
        if token:
            scores[token] += 60.0 * float(row.get("활성도", 0))

    anchors = list(dict.fromkeys(focus + generation_path + [
        row.get("표제어") for row in active[:18] if row.get("표제어")
    ]))

    for source in anchors:
        for target, meta in sorted(
            (graph.get("edges", {}).get(source, {}) or {}).items(),
            key=lambda x: -float((x[1] or {}).get("score", 0)),
        )[:16]:
            scores[target] += 18.0 * float((meta or {}).get("score", 0))

    for rel in _relations(graph):
        source = rel.get("source")
        target = rel.get("target")
        confidence = float(rel.get("confidence", 0))
        if source in anchors and target:
            scores[target] += 22.0 * confidence
        if target in anchors and source:
            scores[source] += 8.0 * confidence

    bigrams = _generation_bigrams(graph)
    for source in anchors:
        row = bigrams.get(source, {}) or {}
        total = sum(max(0, int(v)) for v in row.values())
        if total <= 0:
            continue
        for target, count in sorted(row.items(), key=lambda x: -int(x[1]))[:12]:
            scores[target] += 14.0 * (int(count) / total)

    ranked = sorted(
        scores.items(),
        key=lambda x: (-float(x[1]), -int(nodes.get(x[0], {}).get("frequency", 0)), x[0]),
    )
    selected = [token for token, _score in ranked[:max(20, int(limit))]]

    for token in focus + generation_path:
        if token and token not in selected:
            selected.append(token)
    return selected[:max(20, int(limit))]


def graph_snapshot(core, vault, focus=None, active=None, generation_path=None, limit=DEFAULT_LIMIT):
    graph = core.load_graph(vault)
    selected = _select_nodes(
        graph,
        focus=focus,
        active=active,
        generation_path=generation_path,
        limit=limit,
    )
    selected_set = set(selected)
    active_map = {
        row.get("표제어"): float(row.get("활성도", 0))
        for row in (active or [])
        if row.get("표제어")
    }
    focus_set = set(focus or [])
    generation_set = set(generation_path or [])

    nodes = []
    for token in selected:
        meta = graph.get("nodes", {}).get(token, {}) or {}
        nodes.append({
            "id": token,
            "label": token,
            "frequency": int(meta.get("frequency", 0)),
            "pos": meta.get("pos_ko") or meta.get("pos") or "미분류",
            "activation": round(float(active_map.get(token, 0)), 4),
            "focus": token in focus_set,
            "generated": token in generation_set,
        })

    edges = []
    seen_assoc = set()
    assoc_candidates = []
    for source in selected:
        for target, meta in (graph.get("edges", {}).get(source, {}) or {}).items():
            if target not in selected_set or source == target:
                continue
            pair = tuple(sorted((source, target)))
            if pair in seen_assoc:
                continue
            seen_assoc.add(pair)
            assoc_candidates.append((
                float((meta or {}).get("score", 0)),
                float((meta or {}).get("co", 0)),
                source,
                target,
            ))
    assoc_candidates.sort(reverse=True)
    for score, co, source, target in assoc_candidates[:MAX_ASSOC_EDGES]:
        edges.append({
            "source": source,
            "target": target,
            "layer": "연상",
            "weight": round(score, 4),
            "co": round(co, 3),
            "directed": False,
        })

    for rel in _relations(graph):
        source = rel.get("source")
        target = rel.get("target")
        if source not in selected_set or target not in selected_set:
            continue
        edges.append({
            "source": source,
            "target": target,
            "layer": "의미",
            "weight": round(float(rel.get("confidence", 0)), 4),
            "label": rel.get("label", rel.get("relation", "관계")),
            "directed": True,
        })

    sequence_candidates = []
    bigrams = _generation_bigrams(graph)
    for source in selected:
        row = bigrams.get(source, {}) or {}
        total = sum(max(0, int(v)) for v in row.values())
        if total <= 0:
            continue
        for target, count in row.items():
            if target not in selected_set:
                continue
            probability = int(count) / total
            sequence_candidates.append((probability, int(count), source, target))
    sequence_candidates.sort(reverse=True)
    for probability, count, source, target in sequence_candidates[:MAX_SEQUENCE_EDGES]:
        edges.append({
            "source": source,
            "target": target,
            "layer": "순서",
            "weight": round(probability, 4),
            "count": count,
            "directed": True,
        })

    path = [x for x in (generation_path or []) if x in selected_set]
    for source, target in zip(path, path[1:]):
        edges.append({
            "source": source,
            "target": target,
            "layer": "생성",
            "weight": 1.0,
            "directed": True,
        })

    grammar_data = graph.get("문법", {}) or {}
    pattern_stats = grammar_data.get("정규패턴통계", {}) or grammar_data.get("패턴통계", {}) or {}
    top_patterns = sorted(
        pattern_stats.items(),
        key=lambda x: (-int(x[1]), x[0]),
    )[:10]

    layer_counts = defaultdict(int)
    for edge in edges:
        layer_counts[edge["layer"]] += 1

    return {
        "version": VERSION,
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(graph.get("nodes", {})),
            "shown_nodes": len(nodes),
            "shown_edges": len(edges),
            "layers": dict(layer_counts),
        },
        "grammar_patterns": [
            {"pattern": pattern, "count": int(count)}
            for pattern, count in top_patterns
        ],
    }


def build_visual_trace(result):
    seeds = list(result.get("seed_tokens") or result.get("query_tokens") or [])
    stages = [{
        "name": "장기기억 지도",
        "kind": "기본",
        "activation": {},
        "path": [],
        "message": "Vault의 장기 WordMap을 표시합니다.",
    }]

    if seeds:
        stages.append({
            "name": "입력 개념",
            "kind": "입력",
            "activation": {token: 1.0 for token in seeds},
            "path": list(seeds),
            "message": "질문에서 찾은 핵심 노드를 강조합니다.",
        })

    active = result.get("문맥활성화") or []
    if active:
        stages.append({
            "name": "문맥 활성화",
            "kind": "활성화",
            "activation": {
                row.get("표제어"): float(row.get("활성도", 0))
                for row in active
                if row.get("표제어")
            },
            "path": list(seeds),
            "message": "연상·의미·순서 지도가 현재 문맥에서 활성화한 노드입니다.",
        })

    trace = result.get("자동회귀생성과정") or []
    for step in trace:
        path = list(step.get("이전문맥") or [])
        chosen = step.get("선택")
        if chosen:
            path.append(chosen)
        activation_rows = step.get("활성상위") or []
        stages.append({
            "name": f"생성 {int(step.get('단계', len(stages)))}단계",
            "kind": "생성",
            "activation": {
                row.get("표제어"): float(row.get("활성도", 0))
                for row in activation_rows
                if row.get("표제어")
            },
            "path": path,
            "selected": chosen,
            "selected_surface": step.get("선택표면형"),
            "selection_probability": float(step.get("선택확률", 0)),
            "grammar_fit": float(step.get("선택문법적합", 0)),
            "candidate_origins": list(step.get("선택후보출처") or []),
            "candidates": list(step.get("후보상위") or [])[:5],
            "message": "현재 문맥을 다시 계산한 뒤 다음 단어를 선택한 단계입니다.",
        })

    generated = result.get("generated_sentences") or []
    top = generated[0] if generated else None
    if top:
        stages.append({
            "name": "완성 문장",
            "kind": "완성",
            "activation": {
                row.get("표제어"): float(row.get("활성도", 0))
                for row in (top.get("context_activation") or [])
                if row.get("표제어")
            },
            "path": list(top.get("path") or []),
            "grammar_pattern": top.get("grammar_pattern"),
            "text": top.get("text"),
            "message": "선택된 생성 경로와 최종 문법 패턴입니다.",
        })

    return stages


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        active = result.get("문맥활성화") or []
        generated = result.get("generated_sentences") or []
        path = []
        if generated:
            preferred = next(
                (row for row in generated if row.get("mode") == "wordmap_gpt2"),
                generated[0],
            )
            path = list(preferred.get("path") or [])

        result["visual_graph"] = graph_snapshot(
            core,
            vault,
            focus=result.get("seed_tokens") or result.get("query_tokens") or [],
            active=active,
            generation_path=path,
            limit=DEFAULT_LIMIT,
        )
        result["시각화단계"] = build_visual_trace(result)
        result["visualizer_version"] = VERSION
        return result
    return ask


def make_status(original_status):
    def status():
        out = original_status()
        out["visualizer_version"] = VERSION
        return out
    return status


def apply(core):
    original_ask = core.ask
    original_status = core.status
    core.ask = make_ask(core, original_ask)
    core.status = make_status(original_status)
    core.graph_snapshot = lambda vault, **kwargs: graph_snapshot(core, vault, **kwargs)
    return core
