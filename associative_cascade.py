from __future__ import annotations

import math
from collections import defaultdict

import context_map

VERSION = "0.18.0"
MAX_WAVES = 3
WAVE_DECAY = 0.60
PRIME_FRONTIER_WEIGHT = 0.72
PRIME_STATE_WEIGHT = 0.46
CASCADE_STATE_WEIGHT = 0.52
ASSOCIATION_WEIGHT = 0.52
RELATION_FORWARD_WEIGHT = 0.78
RELATION_REVERSE_WEIGHT = 0.16
SEQUENCE_WEIGHT = 0.30
HUB_FACTOR = 0.24
MAX_FRONTIER = 18
MAX_NEIGHBORS = 10
MAX_STREAMS = 8
MAX_ACTIVE_ROWS = 24
MIN_PROPAGATE = 0.020
CONTEXT_INHIBIT_THRESHOLD = 0.18
INHIBITION_STRENGTH = 0.62

_CACHE = {}
_REL_CACHE = {}


def _clip(value):
    return max(0.0, min(1.0, float(value)))


def _merge(old, amount):
    old = _clip(old)
    amount = _clip(amount)
    return 1.0 - ((1.0 - old) * (1.0 - amount))


def _unique(tokens):
    out = []
    for token in tokens or []:
        token = str(token or "").strip()
        if token and token not in out:
            out.append(token)
    return out


def _relation_index(graph):
    key = id(graph)
    if key in _REL_CACHE:
        return _REL_CACHE[key]
    forward = defaultdict(list)
    reverse = defaultdict(list)
    relations = graph.get("relations", {})
    rows = relations.values() if isinstance(relations, dict) else relations
    for rel in rows or []:
        source = rel.get("source")
        target = rel.get("target")
        if not source or not target:
            continue
        confidence = _clip(rel.get("confidence", 0))
        label = rel.get("label", rel.get("relation", "의미관계"))
        forward[source].append((target, confidence, label))
        reverse[target].append((source, confidence, label))
    if len(_REL_CACHE) > 4:
        _REL_CACHE.clear()
    _REL_CACHE[key] = (forward, reverse)
    return forward, reverse


def _sequence_row(graph, source):
    generation = graph.get("generation", {}).get("bigrams", {}) or {}
    if source in generation:
        return generation.get(source, {}) or {}
    return (graph.get("sequence", {}).get("bigrams", {}).get(source, {}) or {})


def _hub_penalty(graph, source, forward, reverse):
    degree = len(graph.get("edges", {}).get(source, {}) or {})
    degree += len(forward.get(source, []) or [])
    degree += len(reverse.get(source, []) or [])
    degree += len(_sequence_row(graph, source))
    return 1.0 / (1.0 + (HUB_FACTOR * math.log1p(max(0, degree))))


def _neighbors(graph, source, forward, reverse):
    rows = []

    assoc = sorted(
        (graph.get("edges", {}).get(source, {}) or {}).items(),
        key=lambda x: -float((x[1] or {}).get("score", 0)),
    )[:MAX_NEIGHBORS]
    for target, meta in assoc:
        strength = _clip((meta or {}).get("score", 0))
        if strength > 0:
            rows.append((target, ASSOCIATION_WEIGHT * strength, "연상", f"{source} ↔ {target}"))

    for target, confidence, label in forward.get(source, [])[:MAX_NEIGHBORS]:
        rows.append((target, RELATION_FORWARD_WEIGHT * confidence, "의미", f"{source} →({label})→ {target}"))

    for target, confidence, label in reverse.get(source, [])[:MAX_NEIGHBORS]:
        rows.append((target, RELATION_REVERSE_WEIGHT * confidence, "역의미", f"{target} →({label})→ {source}"))

    seq = _sequence_row(graph, source)
    total = sum(max(0, int(v)) for v in seq.values())
    if total > 0:
        for target, count in sorted(seq.items(), key=lambda x: (-int(x[1]), x[0]))[:MAX_NEIGHBORS]:
            probability = max(0, int(count)) / total
            if probability > 0:
                rows.append((target, SEQUENCE_WEIGHT * probability, "순서", f"{source} → {target}"))

    rows.sort(key=lambda x: (-float(x[1]), x[0], x[2]))
    return rows[:MAX_NEIGHBORS * 3]


def _cache_key(graph, seeds, path, prime_scores, waves):
    prime = tuple(sorted(
        ((str(k), round(float(v), 3)) for k, v in (prime_scores or {}).items() if float(v) >= MIN_PROPAGATE),
        key=lambda x: (-x[1], x[0]),
    )[:12])
    return (id(graph), tuple(seeds or []), tuple((path or [])[-6:]), prime, int(waves))


def _context_inhibition(graph, tokens, context_tokens):
    out = {}
    matches = {}
    for token in tokens:
        match = context_map.best_context_match(graph, token, context_tokens)
        matches[token] = match
        if match.get("프로필없음"):
            continue
        fit = float(match.get("적합도", 0.5))
        if fit >= CONTEXT_INHIBIT_THRESHOLD:
            continue
        out[token] = round(
            _clip((CONTEXT_INHIBIT_THRESHOLD - fit) / CONTEXT_INHIBIT_THRESHOLD),
            6,
        )
    return out, matches


def build_cascade(graph, seeds=None, path=None, prime_scores=None, waves=MAX_WAVES):
    seeds = _unique(seeds)
    path = _unique(path)
    prime_scores = {str(k): _clip(v) for k, v in (prime_scores or {}).items() if str(k) and _clip(v) >= MIN_PROPAGATE}
    waves = max(1, min(MAX_WAVES, int(waves)))
    key = _cache_key(graph, seeds, path, prime_scores, waves)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    forward, reverse = _relation_index(graph)
    frontier = {}
    for seed in _unique(seeds + path[-3:]):
        frontier[seed] = {"activation": 1.0, "path": [seed], "source": "입력"}
    for token, score in sorted(prime_scores.items(), key=lambda x: (-x[1], x[0]))[:12]:
        amount = _clip(score * PRIME_FRONTIER_WEIGHT)
        existing = frontier.get(token)
        if existing:
            existing["activation"] = _merge(existing["activation"], amount)
        else:
            frontier[token] = {"activation": amount, "path": [token], "source": "점화"}

    scores = {}
    best_paths = {}
    reasons = defaultdict(list)
    wave_rows = []

    for wave in range(1, waves + 1):
        if not frontier:
            break
        next_frontier = {}
        decay = WAVE_DECAY ** (wave - 1)
        sources = sorted(
            frontier.items(),
            key=lambda x: (-float((x[1] or {}).get("activation", 0)), x[0]),
        )[:MAX_FRONTIER]

        expanded = []
        for source, source_meta in sources:
            source_activation = _clip(source_meta.get("activation", 0))
            if source_activation < MIN_PROPAGATE:
                continue
            source_path = list(source_meta.get("path") or [source])
            hub = _hub_penalty(graph, source, forward, reverse)

            for target, edge_weight, origin, reason in _neighbors(graph, source, forward, reverse):
                if not target or target in source_path:
                    continue
                amount = source_activation * edge_weight * decay * hub
                if amount < MIN_PROPAGATE:
                    continue
                amount = _clip(amount)
                scores[target] = _merge(scores.get(target, 0.0), amount)
                candidate_path = source_path + [target]
                old = best_paths.get(target)
                if old is None or amount > float(old.get("contribution", 0)):
                    best_paths[target] = {
                        "path": candidate_path,
                        "wave": wave,
                        "origin": origin,
                        "contribution": round(amount, 6),
                    }
                reasons[target].append({
                    "wave": wave,
                    "origin": origin,
                    "reason": reason,
                    "contribution": round(amount, 6),
                    "hub_penalty": round(hub, 4),
                })
                row = next_frontier.setdefault(target, {
                    "activation": 0.0,
                    "path": candidate_path,
                    "source": origin,
                    "best": 0.0,
                })
                row["activation"] = _merge(row.get("activation", 0), amount)
                if amount > float(row.get("best", 0)):
                    row["best"] = amount
                    row["path"] = candidate_path
                    row["source"] = origin
                expanded.append((target, amount, candidate_path, origin))

        expanded.sort(key=lambda x: (-x[1], x[0]))
        wave_rows.append({
            "wave": wave,
            "top": [
                {"표제어": token, "활성도": round(amount, 4), "경로": p, "출처": origin}
                for token, amount, p, origin in expanded[:12]
            ],
        })
        frontier = next_frontier

    context_tokens = _unique(seeds + path[-6:] + [k for k, _v in sorted(prime_scores.items(), key=lambda x: -x[1])[:6]])
    inhibition, matches = _context_inhibition(graph, scores.keys(), context_tokens)

    thought_streams = []
    ranked = sorted(
        scores.items(),
        key=lambda x: (-(float(x[1]) * (1.0 - (INHIBITION_STRENGTH * float(inhibition.get(x[0], 0))))), x[0]),
    )
    seen_paths = set()
    for token, score in ranked:
        meta = best_paths.get(token) or {}
        stream_path = tuple(meta.get("path") or [token])
        if stream_path in seen_paths:
            continue
        seen_paths.add(stream_path)
        inhib = float(inhibition.get(token, 0))
        effective = _clip(float(score) * (1.0 - (INHIBITION_STRENGTH * inhib)))
        thought_streams.append({
            "id": f"T{len(thought_streams) + 1}",
            "끝점": token,
            "경로": list(stream_path),
            "파동": int(meta.get("wave", 0)),
            "출처": meta.get("origin"),
            "연상도": round(float(score), 4),
            "억제": round(inhib, 4),
            "유효활성": round(effective, 4),
            "문맥군": (matches.get(token) or {}).get("문맥군"),
            "문맥적합": (matches.get(token) or {}).get("적합도"),
        })
        if len(thought_streams) >= MAX_STREAMS:
            break

    result = {
        "version": VERSION,
        "seeds": seeds,
        "path": path,
        "prime_scores": prime_scores,
        "scores": scores,
        "paths": best_paths,
        "reasons": dict(reasons),
        "waves": wave_rows,
        "inhibition": inhibition,
        "context_matches": matches,
        "thought_streams": thought_streams,
    }
    if len(_CACHE) >= 128:
        _CACHE.clear()
    _CACHE[key] = result
    return result


def top_rows(cascade, limit=MAX_ACTIVE_ROWS):
    rows = []
    for token, score in (cascade.get("scores", {}) or {}).items():
        inhib = float((cascade.get("inhibition", {}) or {}).get(token, 0))
        meta = (cascade.get("paths", {}) or {}).get(token, {}) or {}
        rows.append({
            "표제어": token,
            "연상도": round(float(score), 4),
            "억제": round(inhib, 4),
            "유효활성": round(_clip(float(score) * (1.0 - (INHIBITION_STRENGTH * inhib))), 4),
            "파동": int(meta.get("wave", 0)),
            "경로": list(meta.get("path") or []),
            "출처": meta.get("origin"),
        })
    rows.sort(key=lambda x: (-float(x["유효활성"]), -float(x["연상도"]), x["표제어"]))
    return rows[:max(1, int(limit))]


def patch_activation(activation, priming):
    if getattr(activation, "_associative_cascade_patched", False):
        return
    original_build = activation.build_context_state
    original_candidate = activation.candidate_activation
    original_top = activation.top_rows

    def build_context_state(graph, seeds=None, path=None, steps=2):
        state = original_build(graph, seeds=seeds, path=path, steps=steps)
        active_prime = priming.active_snapshot()
        prime_scores = dict(active_prime.get("scores", {}) or {})
        cascade = build_cascade(graph, seeds=seeds, path=path, prime_scores=prime_scores, waves=MAX_WAVES)
        scores = state.setdefault("scores", {})
        reasons = state.setdefault("reasons", {})

        for token, score in prime_scores.items():
            amount = _clip(float(score) * PRIME_STATE_WEIGHT)
            if amount <= 0:
                continue
            scores[token] = _merge(scores.get(token, 0), amount)
            reasons.setdefault(token, []).append({"근거": "점화 메모리", "기여": round(amount, 4)})

        for token, score in (cascade.get("scores", {}) or {}).items():
            amount = _clip(float(score) * CASCADE_STATE_WEIGHT)
            if amount <= 0:
                continue
            scores[token] = _merge(scores.get(token, 0), amount)
            path_meta = (cascade.get("paths", {}) or {}).get(token, {}) or {}
            path_text = " → ".join(path_meta.get("path") or [])
            reasons.setdefault(token, []).append({
                "근거": f"연상 폭포 {path_text}" if path_text else "연상 폭포",
                "기여": round(amount, 4),
            })

        state["_priming_scores"] = prime_scores
        state["_priming_rows"] = list(active_prime.get("rows", []) or [])
        state["_associative_cascade"] = cascade
        state["_cascade_scores"] = dict(cascade.get("scores", {}) or {})
        state["_cascade_inhibition"] = dict(cascade.get("inhibition", {}) or {})
        state["_thought_streams"] = list(cascade.get("thought_streams", []) or [])
        return state

    def candidate_activation(state, token):
        base = float(original_candidate(state, token))
        inhibition = float((state or {}).get("_cascade_inhibition", {}).get(token, 0))
        return _clip(base * (1.0 - (INHIBITION_STRENGTH * inhibition)))

    def activation_top_rows(state, limit=12, exclude=None):
        expanded = original_top(state, limit=max(48, int(limit) * 4), exclude=exclude)
        prime_scores = (state or {}).get("_priming_scores", {}) or {}
        cascade_scores = (state or {}).get("_cascade_scores", {}) or {}
        inhibition = (state or {}).get("_cascade_inhibition", {}) or {}
        paths = (((state or {}).get("_associative_cascade", {}) or {}).get("paths", {}) or {})
        for row in expanded:
            token = row.get("표제어")
            row["활성도"] = round(candidate_activation(state, token), 4)
            row["점화활성"] = round(float(prime_scores.get(token, 0)), 4)
            row["연상활성"] = round(float(cascade_scores.get(token, 0)), 4)
            row["연상억제"] = round(float(inhibition.get(token, 0)), 4)
            meta = paths.get(token, {}) or {}
            row["연상파동"] = int(meta.get("wave", 0))
            row["연상경로"] = list(meta.get("path") or [])
        expanded.sort(key=lambda x: (-float(x.get("활성도", 0)), x.get("표제어", "")))
        return expanded[:max(1, int(limit))]

    activation.build_context_state = build_context_state
    activation.candidate_activation = candidate_activation
    activation.top_rows = activation_top_rows
    activation._associative_cascade_patched = True


def patch_wordmap(wordmap_gpt2):
    if getattr(wordmap_gpt2, "_associative_cascade_patched", False):
        return
    original_pool = wordmap_gpt2._candidate_pool
    original_trace = wordmap_gpt2._trace_candidates

    def candidate_pool(graph, path, state):
        rows = original_pool(graph, path, state)
        primes = (state or {}).get("_priming_scores", {}) or {}
        cascade = (state or {}).get("_cascade_scores", {}) or {}
        inhibition = (state or {}).get("_cascade_inhibition", {}) or {}
        paths = (((state or {}).get("_associative_cascade", {}) or {}).get("paths", {}) or {})
        for row in rows:
            token = row.get("token")
            p = float(primes.get(token, 0))
            c = float(cascade.get(token, 0))
            if p >= MIN_PROPAGATE and "점화" not in row.setdefault("origins", []):
                row["origins"].append("점화")
            if c >= MIN_PROPAGATE and "연상 폭포" not in row.setdefault("origins", []):
                row["origins"].append("연상 폭포")
            row["priming_activation"] = round(p, 6)
            row["cascade_activation"] = round(c, 6)
            row["cascade_inhibition"] = round(float(inhibition.get(token, 0)), 6)
            row["cascade_path"] = list((paths.get(token, {}) or {}).get("path") or [])
        return rows

    def trace_candidates(rows, limit=5):
        out = original_trace(rows, limit=limit)
        for item, row in zip(out, rows[:limit]):
            item["점화활성"] = round(float(row.get("priming_activation", 0)), 4)
            item["연상활성"] = round(float(row.get("cascade_activation", 0)), 4)
            item["연상억제"] = round(float(row.get("cascade_inhibition", 0)), 4)
            item["연상경로"] = list(row.get("cascade_path") or [])
        return out

    wordmap_gpt2._candidate_pool = candidate_pool
    wordmap_gpt2._trace_candidates = trace_candidates
    wordmap_gpt2._associative_cascade_patched = True


def make_ask(core, priming, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        seeds = result.get("seed_tokens") or result.get("query_tokens") or []
        before = ((result.get("점화상태") or {}).get("사용전") or [])
        prime_scores = {
            row.get("표제어"): float(row.get("점화도", 0))
            for row in before
            if row.get("표제어")
        }
        cascade = build_cascade(graph, seeds=seeds, path=seeds, prime_scores=prime_scores, waves=MAX_WAVES)
        result["연상폭포"] = list(cascade.get("thought_streams", []) or [])
        result["연상활성화"] = top_rows(cascade, limit=MAX_ACTIVE_ROWS)
        result["연상파동"] = list(cascade.get("waves", []) or [])
        inhibited = [
            {"표제어": token, "억제": round(float(value), 4)}
            for token, value in (cascade.get("inhibition", {}) or {}).items()
            if float(value) > 0
        ]
        inhibited.sort(key=lambda x: (-x["억제"], x["표제어"]))
        result["연상억제"] = inhibited[:16]
        result["associative_cascade_version"] = VERSION
        return result
    return ask


def apply(core, activation, wordmap_gpt2, priming):
    patch_activation(activation, priming)
    patch_wordmap(wordmap_gpt2)
    original_ask = core.ask
    original_status = core.status
    core.ask = make_ask(core, priming, original_ask)

    def status():
        out = original_status()
        out["associative_cascade_version"] = VERSION
        out["associative_waves"] = MAX_WAVES
        return out

    core.status = status
    core.associative_cascade = lambda vault, seeds=None, path=None, prime_scores=None, waves=MAX_WAVES: build_cascade(
        core.load_graph(vault), seeds=seeds, path=path, prime_scores=prime_scores, waves=waves
    )
    core.associative_cascade_version = VERSION
    return core
