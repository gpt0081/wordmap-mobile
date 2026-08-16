from __future__ import annotations

import math
from collections import Counter

VERSION = "0.15.0"
MAX_SENSES = 6
MAX_TERMS = 20
MAX_EXAMPLES = 3
MIN_CONTEXT_TERMS = 2
MERGE_THRESHOLD = 0.24
SEP = "\x1f"


def _ensure(graph):
    data = graph.setdefault("문맥지도", {})
    data.setdefault("버전", VERSION)
    data.setdefault("문장수", 0)
    data.setdefault("단어문맥", {})
    return data


def _unique(tokens):
    out = []
    for token in tokens or []:
        if token and token not in out:
            out.append(token)
    return out


def context_signature(tokens, limit=6):
    cleaned = sorted(set(x for x in (tokens or []) if x))[: max(1, int(limit))]
    return SEP.join(cleaned)


def _profile_terms(sense):
    terms = sense.get("용어", {}) or {}
    return set(terms)


def _similarity(context_terms, sense):
    current = set(context_terms or [])
    profile = _profile_terms(sense)
    if not current or not profile:
        return 0.0
    overlap = current & profile
    if not overlap:
        return 0.0
    weighted = 0.0
    total = 0.0
    term_counts = sense.get("용어", {}) or {}
    max_count = max([int(v) for v in term_counts.values()] or [1])
    for term in current:
        w = 0.4 + 0.6 * (int(term_counts.get(term, 0)) / max_count)
        total += 1.0
        if term in overlap:
            weighted += w
    cosine_like = len(overlap) / math.sqrt(max(1, len(current)) * max(1, len(profile)))
    local = weighted / max(1.0, total)
    return max(0.0, min(1.0, (0.58 * cosine_like) + (0.42 * local)))


def _trim_terms(terms):
    ranked = sorted(
        ((str(k), int(v)) for k, v in (terms or {}).items() if k and int(v) > 0),
        key=lambda x: (-x[1], x[0]),
    )[:MAX_TERMS]
    return {k: v for k, v in ranked}


def _new_sense(token, index, context_terms, sentence):
    return {
        "id": f"{token}#{index}",
        "관찰수": 1,
        "용어": {term: 1 for term in context_terms[:MAX_TERMS]},
        "예문": [sentence[:240]] if sentence else [],
    }


def _merge_sense(sense, context_terms, sentence):
    sense["관찰수"] = int(sense.get("관찰수", 0)) + 1
    terms = Counter({k: int(v) for k, v in (sense.get("용어", {}) or {}).items()})
    for term in context_terms:
        terms[term] += 1
    sense["용어"] = _trim_terms(terms)
    if sentence:
        examples = sense.setdefault("예문", [])
        if sentence not in examples and len(examples) < MAX_EXAMPLES:
            examples.append(sentence[:240])


def accumulate_sentence(graph, sentence, tokens):
    tokens = _unique(tokens)
    if len(tokens) < MIN_CONTEXT_TERMS + 1:
        return
    data = _ensure(graph)
    data["버전"] = VERSION
    data["문장수"] = int(data.get("문장수", 0)) + 1
    root = data["단어문맥"]

    for token in tokens:
        context_terms = [x for x in tokens if x != token][:MAX_TERMS]
        if len(context_terms) < MIN_CONTEXT_TERMS:
            continue
        row = root.setdefault(token, {"관찰수": 0, "문맥군": []})
        row["관찰수"] = int(row.get("관찰수", 0)) + 1
        senses = row.setdefault("문맥군", [])

        scored = sorted(
            ((_similarity(context_terms, sense), sense) for sense in senses),
            key=lambda x: -x[0],
        )
        best_score, best = scored[0] if scored else (0.0, None)
        if best is not None and (best_score >= MERGE_THRESHOLD or len(senses) >= MAX_SENSES):
            _merge_sense(best, context_terms, sentence)
        else:
            senses.append(_new_sense(token, len(senses) + 1, context_terms, sentence))


def best_context_match(graph, token, context_tokens):
    row = ((graph.get("문맥지도", {}) or {}).get("단어문맥", {}) or {}).get(token)
    if not row:
        return {
            "표제어": token,
            "문맥군": None,
            "적합도": 0.5,
            "관찰수": 0,
            "프로필없음": True,
            "대표용어": [],
        }
    context_tokens = [x for x in _unique(context_tokens) if x != token]
    senses = row.get("문맥군", []) or []
    if not context_tokens or not senses:
        return {
            "표제어": token,
            "문맥군": senses[0].get("id") if senses else None,
            "적합도": 0.5,
            "관찰수": int(row.get("관찰수", 0)),
            "프로필없음": False,
            "대표용어": [],
        }
    ranked = sorted(
        ((_similarity(context_tokens, sense), sense) for sense in senses),
        key=lambda x: (-x[0], -int(x[1].get("관찰수", 0)), x[1].get("id", "")),
    )
    fit, sense = ranked[0]
    terms = sorted(
        (sense.get("용어", {}) or {}).items(),
        key=lambda x: (-int(x[1]), x[0]),
    )[:8]
    return {
        "표제어": token,
        "문맥군": sense.get("id"),
        "적합도": round(float(fit), 4),
        "관찰수": int(row.get("관찰수", 0)),
        "문맥군관찰수": int(sense.get("관찰수", 0)),
        "프로필없음": False,
        "대표용어": [term for term, _count in terms],
        "문맥군수": len(senses),
    }


def context_gate(graph, token, context_tokens):
    match = best_context_match(graph, token, context_tokens)
    if match.get("프로필없음"):
        return 1.0, match
    fit = float(match.get("적합도", 0.5))
    # A context profile changes usage, never the underlying fact edge.
    # Floor 0.72 prevents a sparse ContextMap from deleting a valid candidate.
    gate = 0.72 + (0.56 * fit)
    return max(0.72, min(1.28, gate)), match


def map_summary(graph):
    data = graph.get("문맥지도", {}) or {}
    rows = data.get("단어문맥", {}) or {}
    senses = sum(len((row or {}).get("문맥군", []) or []) for row in rows.values())
    ambiguous = sum(1 for row in rows.values() if len((row or {}).get("문맥군", []) or []) >= 2)
    return {
        "version": data.get("버전", VERSION),
        "sentences": int(data.get("문장수", 0)),
        "profiled_tokens": len(rows),
        "context_clusters": senses,
        "multi_context_tokens": ambiguous,
    }


def context_item(graph, token):
    row = ((graph.get("문맥지도", {}) or {}).get("단어문맥", {}) or {}).get(str(token or ""))
    if not row:
        raise ValueError("해당 표제어의 문맥지도를 찾을 수 없습니다.")
    senses = []
    for sense in row.get("문맥군", []) or []:
        item = dict(sense)
        item["대표용어"] = [
            term for term, _count in sorted(
                (sense.get("용어", {}) or {}).items(),
                key=lambda x: (-int(x[1]), x[0]),
            )[:12]
        ]
        senses.append(item)
    return {"version": VERSION, "표제어": token, "관찰수": int(row.get("관찰수", 0)), "문맥군": senses}


def patch_activation(activation):
    if getattr(activation, "_context_map_patched", False):
        return
    original_build = activation.build_context_state
    original_candidate = activation.candidate_activation
    original_top = activation.top_rows

    def build_context_state(graph, seeds=None, path=None, steps=2):
        state = original_build(graph, seeds=seeds, path=path, steps=steps)
        state["_context_graph"] = graph
        state["_context_tokens"] = _unique(list(seeds or []) + list(path or [])[-6:])
        return state

    def candidate_activation(state, token):
        base = float(original_candidate(state, token))
        graph = (state or {}).get("_context_graph")
        if not graph or not token:
            return base
        gate, _match = context_gate(graph, token, (state or {}).get("_context_tokens", []))
        return max(0.0, min(1.0, base * gate))

    def top_rows(state, limit=12, exclude=None):
        expanded = original_top(state, limit=max(36, int(limit) * 3), exclude=exclude)
        for row in expanded:
            token = row.get("표제어")
            row["활성도"] = round(candidate_activation(state, token), 4)
            graph = (state or {}).get("_context_graph")
            if graph and token:
                _gate, match = context_gate(graph, token, (state or {}).get("_context_tokens", []))
                row["문맥군"] = match.get("문맥군")
                row["문맥적합"] = match.get("적합도")
        expanded.sort(key=lambda x: (-float(x.get("활성도", 0)), x.get("표제어", "")))
        return expanded[:max(1, int(limit))]

    activation.build_context_state = build_context_state
    activation.candidate_activation = candidate_activation
    activation.top_rows = top_rows
    activation._context_map_patched = True


def make_analyze(core, original_analyze):
    def analyze_into_graph(graph, text, window=4):
        stats = original_analyze(graph, text, window=window)
        for sentence in core.split_sentences(text):
            tokens = core.tokenize(sentence)
            accumulate_sentence(graph, sentence, tokens)
        return stats
    return analyze_into_graph


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        seeds = result.get("seed_tokens") or result.get("query_tokens") or []
        matches = []
        for token in seeds[:8]:
            context = [x for x in seeds if x != token]
            matches.append(best_context_match(graph, token, context))
        result["문맥지도매칭"] = matches
        result["context_map_version"] = VERSION
        return result
    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if vault:
            summary = map_summary(core.load_graph(vault))
            out["context_map_version"] = VERSION
            out["context_clusters"] = summary["context_clusters"]
            out["multi_context_tokens"] = summary["multi_context_tokens"]
        return out
    return status


def apply(core, activation):
    patch_activation(activation)
    original_analyze = core.analyze_into_graph
    original_ask = core.ask
    original_status = core.status
    core.analyze_into_graph = make_analyze(core, original_analyze)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    core.context_map_summary = lambda vault: map_summary(core.load_graph(vault))
    core.context_map_get = lambda vault, token: context_item(core.load_graph(vault), token)
    core.context_map_version = VERSION
    return core
