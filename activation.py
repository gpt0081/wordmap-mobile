from __future__ import annotations

from collections import defaultdict

VERSION = "0.8.0"

CONTEXT_DECAY = 0.82
ASSOCIATION_WEIGHT = 0.42
RELATION_FORWARD_WEIGHT = 0.78
RELATION_REVERSE_WEIGHT = 0.24
SEQUENCE_WEIGHT = 0.34
SECOND_HOP_DECAY = 0.55
MAX_FRONTIER = 24
MAX_NEIGHBORS = 14


def _clip(value):
    return max(0.0, min(1.0, float(value)))


def _merge(old, amount):
    """Bounded noisy-OR accumulation in the 0..1 interval."""
    old = _clip(old)
    amount = _clip(amount)
    return 1.0 - ((1.0 - old) * (1.0 - amount))


def _relation_index(graph):
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
    return forward, reverse


def _sequence_row(graph, source):
    generation = graph.get("generation", {}).get("bigrams", {})
    if source in generation:
        return generation.get(source, {}) or {}
    return (
        graph.get("sequence", {})
        .get("bigrams", {})
        .get(source, {})
    ) or {}


def _add(scores, reasons, token, amount, reason):
    if not token or amount <= 0:
        return
    amount = _clip(amount)
    scores[token] = _merge(scores.get(token, 0.0), amount)
    reasons[token].append({
        "근거": reason,
        "기여": round(amount, 4),
    })


def _base_state(seeds, path):
    scores = {}
    reasons = defaultdict(list)

    for i, seed in enumerate(seeds or []):
        if not seed:
            continue
        weight = max(0.72, 1.0 - (0.08 * i))
        if weight > scores.get(seed, 0.0):
            scores[seed] = weight
        reasons[seed].append({"근거": "질문 핵심개념", "기여": round(weight, 4)})

    context = [x for x in (path or []) if x]
    for distance, token in enumerate(reversed(context)):
        weight = CONTEXT_DECAY ** distance
        if weight > scores.get(token, 0.0):
            scores[token] = weight
        reasons[token].append({
            "근거": f"현재 문맥 위치 -{distance}",
            "기여": round(weight, 4),
        })

    return scores, reasons


def build_context_state(graph, seeds=None, path=None, steps=2):
    """Build an explainable, GPT-2-inspired dynamic activation state.

    This is intentionally not neural attention. It combines the current
    context with explicit WordMap association edges, semantic relations, and
    observed next-word statistics. Every score remains inspectable.
    """
    seeds = [x for x in (seeds or []) if x]
    path = [x for x in (path or []) if x]
    scores, reasons = _base_state(seeds, path)
    forward, reverse = _relation_index(graph)

    frontier = dict(scores)
    for step in range(max(0, int(steps))):
        if not frontier:
            break
        step_decay = 1.0 if step == 0 else SECOND_HOP_DECAY ** step
        next_frontier = {}

        sources = sorted(
            frontier.items(),
            key=lambda x: (-float(x[1]), x[0]),
        )[:MAX_FRONTIER]

        for source, source_activation in sources:
            if source_activation < 0.04:
                continue

            # Undirected association edges.
            assoc = graph.get("edges", {}).get(source, {}) or {}
            assoc_rows = sorted(
                assoc.items(),
                key=lambda x: -float((x[1] or {}).get("score", 0)),
            )[:MAX_NEIGHBORS]
            for target, meta in assoc_rows:
                edge_score = _clip((meta or {}).get("score", 0))
                amount = source_activation * ASSOCIATION_WEIGHT * edge_score * step_decay
                if amount <= 0:
                    continue
                _add(scores, reasons, target, amount, f"연상 {source} ↔ {target}")
                next_frontier[target] = _merge(next_frontier.get(target, 0.0), amount)

            # Directed semantic relations carry more weight forward than back.
            for target, confidence, label in forward.get(source, [])[:MAX_NEIGHBORS]:
                amount = source_activation * RELATION_FORWARD_WEIGHT * confidence * step_decay
                _add(scores, reasons, target, amount, f"의미 {source} →({label})→ {target}")
                next_frontier[target] = _merge(next_frontier.get(target, 0.0), amount)

            for target, confidence, label in reverse.get(source, [])[:MAX_NEIGHBORS]:
                amount = source_activation * RELATION_REVERSE_WEIGHT * confidence * step_decay
                _add(scores, reasons, target, amount, f"역방향 의미 {target} →({label})→ {source}")
                next_frontier[target] = _merge(next_frontier.get(target, 0.0), amount)

            # Ordered corpus evidence acts like a small next-token prior.
            seq = _sequence_row(graph, source)
            total = sum(max(0, int(v)) for v in seq.values())
            if total > 0:
                seq_rows = sorted(
                    ((target, int(count)) for target, count in seq.items()),
                    key=lambda x: (-x[1], x[0]),
                )[:MAX_NEIGHBORS]
                for target, count in seq_rows:
                    probability = count / total
                    amount = source_activation * SEQUENCE_WEIGHT * probability * step_decay
                    _add(scores, reasons, target, amount, f"순서 {source} → {target}")
                    next_frontier[target] = _merge(next_frontier.get(target, 0.0), amount)

        frontier = next_frontier

    return {
        "version": VERSION,
        "scores": scores,
        "reasons": dict(reasons),
        "seeds": seeds,
        "path": path,
    }


def candidate_activation(state, token):
    return _clip((state or {}).get("scores", {}).get(token, 0.0))


def top_rows(state, limit=12, exclude=None):
    exclude = set(exclude or [])
    scores = (state or {}).get("scores", {})
    reasons = (state or {}).get("reasons", {})
    rows = []
    for token, score in scores.items():
        if token in exclude:
            continue
        why = sorted(
            reasons.get(token, []),
            key=lambda x: -float(x.get("기여", 0)),
        )[:3]
        rows.append({
            "표제어": token,
            "활성도": round(float(score), 4),
            "근거": [x.get("근거", "") for x in why if x.get("근거")],
        })
    rows.sort(key=lambda x: (-float(x["활성도"]), x["표제어"]))
    return rows[:max(1, int(limit))]


def rerank_next_candidates(rows, state):
    out = []
    for row in rows or []:
        item = dict(row)
        token = item.get("token")
        probability = float(item.get("probability", 0))
        active = candidate_activation(state, token)
        item["activation"] = round(active, 4)
        item["context_score"] = round(probability * (1.0 + (0.90 * active)), 6)
        out.append(item)
    out.sort(
        key=lambda x: (
            -float(x.get("context_score", 0)),
            -int(x.get("count", 0)),
            str(x.get("token", "")),
        )
    )
    return out


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        seeds = result.get("seed_tokens") or result.get("query_tokens") or []
        state = build_context_state(graph, seeds=seeds, path=seeds, steps=2)
        result["문맥활성화"] = top_rows(state, limit=12, exclude=[])
        result["activation_version"] = VERSION
        if result.get("next_word_candidates"):
            result["next_word_candidates"] = rerank_next_candidates(
                result["next_word_candidates"],
                state,
            )
        return result
    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        out["activation_version"] = VERSION
        return out
    return status


def apply(core):
    original_ask = core.ask
    original_status = core.status
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    return core
