from __future__ import annotations

import math
from collections import Counter

import grammar
import language

VERSION = "0.6.0"
SEP = "\x1f"
MAX_WORDS = 9
BEAM_WIDTH = 6


def _ensure(graph):
    data = graph.setdefault("generation", {})
    data.setdefault("version", VERSION)
    data.setdefault("trigrams", {})
    data.setdefault("start_surfaces", {})
    data.setdefault("forms", {})
    data.setdefault("pair_surfaces", {})
    data.setdefault("trigram_surfaces", {})
    data.setdefault("end_counts", {})
    data.setdefault("sentences", 0)
    return data


def _inc_nested(bucket, key, subkey, amount=1):
    row = bucket.setdefault(key, {})
    row[subkey] = int(row.get(subkey, 0)) + int(amount)


def _surface_items(sentence):
    """Return [(lemma, observed_surface)] aligned to one corpus sentence."""
    items = []
    for surface in grammar.raw_words(sentence):
        entries = language.resolve_surface(surface)
        if not entries:
            continue
        if len(entries) == 1:
            items.append((entries[0]["lemma"], surface))
            continue

        # A fused compound such as 고무가황 has no internal surface boundary.
        # Keep its proven component lemmas, using the lemmas themselves as the
        # recoverable surface rather than inventing a spacing/particle pattern.
        for entry in entries:
            items.append((entry["lemma"], entry["lemma"]))
    return items


def accumulate_generation(graph, items):
    if not items:
        return

    data = _ensure(graph)
    starts = data["start_surfaces"]
    forms = data["forms"]
    pair_surfaces = data["pair_surfaces"]
    trigram_surfaces = data["trigram_surfaces"]
    trigrams = data["trigrams"]
    end_counts = data["end_counts"]

    first_lemma, first_surface = items[0]
    _inc_nested(starts, first_lemma, first_surface)

    for lemma, surface in items:
        _inc_nested(forms, lemma, surface)

    for i in range(len(items) - 1):
        a, _surface_a = items[i]
        b, surface_b = items[i + 1]
        _inc_nested(pair_surfaces, SEP.join((a, b)), surface_b)

    for i in range(len(items) - 2):
        a, _surface_a = items[i]
        b, _surface_b = items[i + 1]
        c, surface_c = items[i + 2]
        context = SEP.join((a, b))
        _inc_nested(trigrams, context, c)
        _inc_nested(trigram_surfaces, SEP.join((a, b, c)), surface_c)

    last_lemma = items[-1][0]
    end_counts[last_lemma] = int(end_counts.get(last_lemma, 0)) + 1
    data["sentences"] = int(data.get("sentences", 0)) + 1
    data["version"] = VERSION


def make_analyze(core, original_analyze):
    def analyze_into_graph(graph, text, window=4):
        stats = original_analyze(graph, text, window=window)
        for sentence in core.split_sentences(text):
            items = _surface_items(sentence)
            if items:
                accumulate_generation(graph, items)
        return stats
    return analyze_into_graph


def _best_surface(counter_map, fallback):
    if not counter_map:
        return fallback
    return sorted(
        ((surface, int(count)) for surface, count in counter_map.items()),
        key=lambda x: (-x[1], len(x[0]), x[0]),
    )[0][0]


def _initial_surface(graph, lemma):
    data = graph.get("generation", {})
    starts = data.get("start_surfaces", {}).get(lemma, {})
    if starts:
        return _best_surface(starts, lemma)

    forms = data.get("forms", {}).get(lemma, {})
    if not forms:
        return lemma

    def rank(item):
        surface, count = item
        bonus = 0.0
        if surface == lemma:
            bonus += 1.5
        if surface.endswith(("은", "는", "이", "가")):
            bonus += 1.0
        if surface.endswith(("을", "를", "과", "와", "의", "에")):
            bonus -= 0.4
        return (float(count) + bonus, -len(surface), surface)

    return max(forms.items(), key=rank)[0]


def _target_surface(graph, path, target):
    data = graph.get("generation", {})
    if len(path) >= 2:
        key3 = SEP.join((path[-2], path[-1], target))
        counter = data.get("trigram_surfaces", {}).get(key3, {})
        if counter:
            return _best_surface(counter, target)

    if path:
        key2 = SEP.join((path[-1], target))
        counter = data.get("pair_surfaces", {}).get(key2, {})
        if counter:
            return _best_surface(counter, target)

    return _best_surface(
        data.get("forms", {}).get(target, {}),
        target,
    )


def _next_counts(graph, path):
    data = graph.get("generation", {})
    if len(path) >= 2:
        context = SEP.join((path[-2], path[-1]))
        tri = data.get("trigrams", {}).get(context, {})
        if tri:
            return tri, "trigram"

    if not path:
        return {}, "none"
    bi = (
        graph.get("sequence", {})
        .get("bigrams", {})
        .get(path[-1], {})
    )
    return bi, "bigram"


def _relation_bonus(graph, source, target):
    bonus = 0.0
    relations = graph.get("relations", {})
    rels = relations.values() if isinstance(relations, dict) else relations
    for rel in rels or []:
        if rel.get("source") == source and rel.get("target") == target:
            bonus = max(bonus, 0.45 * float(rel.get("confidence", 0)))
        elif rel.get("source") == target and rel.get("target") == source:
            bonus = max(bonus, 0.10 * float(rel.get("confidence", 0)))

    edge = graph.get("edges", {}).get(source, {}).get(target)
    if edge:
        bonus += min(0.18, max(0.0, float(edge.get("score", 0))) * 0.20)
    return bonus


def _looks_terminal(surface):
    return bool(surface) and surface.endswith(
        ("다", "요", "니다", "습니다", "한다", "된다", "였다", "이다")
    )


def _end_ratio(graph, lemma):
    data = graph.get("generation", {})
    ends = int(data.get("end_counts", {}).get(lemma, 0))
    outgoing = sum(
        int(v)
        for v in (
            graph.get("sequence", {})
            .get("bigrams", {})
            .get(lemma, {})
        ).values()
    )
    total = ends + outgoing
    return (ends / total) if total else 0.0


def _finish_text(surfaces):
    text = " ".join(x for x in surfaces if x).strip()
    if not text:
        return ""
    if text[-1] not in ".!?。！？":
        text += "."
    return text


def generate_sequence_sentences(graph, seed, limit=3, max_words=MAX_WORDS):
    if not seed:
        return []

    initial_surface = _initial_surface(graph, seed)
    beams = [([seed], [initial_surface], 0.0, [])]
    completed = []

    for _step in range(max(1, int(max_words)) - 1):
        next_beams = []
        for path, surfaces, score, evidence in beams:
            current = path[-1]

            if len(path) >= 3 and (
                _looks_terminal(surfaces[-1])
                or _end_ratio(graph, current) >= 0.45
            ):
                completed.append((path, surfaces, score + 0.15, evidence))
                continue

            counts, model = _next_counts(graph, path)
            total = sum(int(v) for v in counts.values())
            if not counts or total <= 0:
                if len(path) >= 2:
                    completed.append((path, surfaces, score, evidence))
                continue

            ranked = sorted(
                ((token, int(count)) for token, count in counts.items()),
                key=lambda x: (-x[1], x[0]),
            )[:12]

            for target, count in ranked:
                if path.count(target) >= 1:
                    continue
                probability = count / total
                target_surface = _target_surface(graph, path, target)
                pair_bonus = _relation_bonus(graph, current, target)
                new_score = score + math.log(max(probability, 1e-9)) + pair_bonus
                new_evidence = evidence + [{
                    "from": current,
                    "to": target,
                    "model": model,
                    "count": count,
                    "probability": round(probability, 4),
                }]
                next_beams.append((
                    path + [target],
                    surfaces + [target_surface],
                    new_score,
                    new_evidence,
                ))

        if not next_beams:
            break
        next_beams.sort(key=lambda x: x[2], reverse=True)
        beams = next_beams[:BEAM_WIDTH]

    for state in beams:
        if len(state[0]) >= 2:
            completed.append(state)

    unique = {}
    for path, surfaces, score, evidence in completed:
        text = _finish_text(surfaces)
        if not text or text in unique:
            continue
        unique[text] = {
            "text": text,
            "mode": "sequence",
            "basis": "Corpus에서 관찰된 단어 순서",
            "score": round(float(score), 4),
            "path": path,
            "evidence": evidence,
        }

    ranked = sorted(
        unique.values(),
        key=lambda x: (-float(x["score"]), len(x["path"]), x["text"]),
    )
    return ranked[:max(1, int(limit))]


def _has_batchim(word):
    if not word:
        return False
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return ((code - 0xAC00) % 28) != 0
    return False


def _topic(word):
    return word + ("은" if _has_batchim(word) else "는")


def _object(word):
    return word + ("을" if _has_batchim(word) else "를")


def _with(word):
    return word + ("과" if _has_batchim(word) else "와")


def _relation_sentence(rel):
    source = str(rel.get("source", "")).strip()
    target = str(rel.get("target", "")).strip()
    relation = rel.get("relation")
    if not source or not target:
        return None

    s = _topic(source)
    templates = {
        "is_a": f"{s} {target}이다.",
        "used_for": f"{s} {target}에 사용된다.",
        "promotes": f"{s} {_object(target)} 촉진한다.",
        "increases": f"{s} {_object(target)} 증가시킨다.",
        "decreases": f"{s} {_object(target)} 감소시킨다.",
        "affects": f"{s} {target}에 영향을 준다.",
        "property": f"{s} {target} 특성을 가진다.",
        "component": f"{s} {target}로 구성된다.",
        "causes": f"{s} {_object(target)} 유발한다.",
        "requires": f"{s} {_object(target)} 필요로 한다.",
        "uses": f"{s} {_object(target)} 사용한다.",
        "contains": f"{s} {_object(target)} 포함한다.",
        "belongs_to": f"{s} {target}에 속한다.",
        "related_to": f"{s} {_with(target)} 관련된다.",
    }
    return templates.get(relation)


def generate_semantic_sentences(graph, seeds, limit=4):
    seed_set = set(seeds or [])
    relations = graph.get("relations", {})
    rels = relations.values() if isinstance(relations, dict) else relations
    out = []
    seen = set()

    for rel in rels or []:
        if seed_set and rel.get("source") not in seed_set:
            continue
        text = _relation_sentence(rel)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append({
            "text": text,
            "mode": "semantic",
            "basis": "WordMap 의미 관계",
            "score": round(float(rel.get("confidence", 0)), 4),
            "path": [rel.get("source"), rel.get("target")],
            "relation": rel.get("label", rel.get("relation")),
            "evidence": rel.get("evidence", [])[:2],
        })

    out.sort(key=lambda x: (-float(x["score"]), x["text"]))
    return out[:max(1, int(limit))]


def generate_sentences(graph, seeds, limit=5):
    seeds = [x for x in (seeds or []) if x]
    if not seeds:
        return []

    semantic = generate_semantic_sentences(graph, seeds, limit=limit)
    sequence_rows = []
    for seed in seeds[:2]:
        sequence_rows.extend(
            generate_sequence_sentences(graph, seed, limit=3)
        )

    # Semantic sentences are explicit claims backed by typed edges, so show
    # them first. Sequence sentences follow as corpus-grounded continuations.
    combined = semantic + sequence_rows
    seen = set()
    out = []
    for row in combined:
        if row["text"] in seen:
            continue
        seen.add(row["text"])
        out.append(row)
        if len(out) >= max(1, int(limit)):
            break
    return out


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        seeds = result.get("seed_tokens") or result.get("query_tokens") or []
        result["generated_sentences"] = generate_sentences(
            graph,
            seeds,
            limit=5,
        )
        result["generation_version"] = VERSION
        return result
    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out
        graph = core.load_graph(vault)
        data = graph.get("generation", {})
        out["generation_version"] = data.get("version", VERSION)
        out["generation_sentences"] = int(data.get("sentences", 0))
        out["generation_trigram_contexts"] = len(data.get("trigrams", {}))
        return out
    return status


def apply(core):
    original_analyze = core.analyze_into_graph
    original_ask = core.ask
    original_status = core.status

    core.analyze_into_graph = make_analyze(core, original_analyze)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    return core
