from __future__ import annotations

import math
import re
from collections import Counter

import grammar
import language

VERSION = "0.6.1"
SEP = "\x1f"
MAX_WORDS = 8
BEAM_WIDTH = 6


def _ensure(graph):
    data = graph.setdefault("generation", {})
    data.setdefault("version", VERSION)
    data.setdefault("bigrams", {})
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


def _surface_segments(sentence):
    """Return contiguous resolved [(lemma, surface)] segments.

    Unresolved/filtered words create a boundary. This prevents the generator
    from inventing adjacency across omitted words, e.g. 'status를 ... 상태를'.
    """
    segments = []
    current = []
    for surface in grammar.raw_words(sentence):
        entries = language.resolve_surface(surface)
        if not entries:
            if current:
                segments.append(current)
                current = []
            continue

        if len(entries) == 1:
            current.append((entries[0]["lemma"], surface))
        else:
            for entry in entries:
                current.append((entry["lemma"], entry["lemma"]))

    if current:
        segments.append(current)
    return segments


def accumulate_generation(graph, items):
    if not items:
        return

    data = _ensure(graph)
    bigrams = data["bigrams"]
    trigrams = data["trigrams"]
    starts = data["start_surfaces"]
    forms = data["forms"]
    pair_surfaces = data["pair_surfaces"]
    trigram_surfaces = data["trigram_surfaces"]
    end_counts = data["end_counts"]

    first_lemma, first_surface = items[0]
    _inc_nested(starts, first_lemma, first_surface)

    for lemma, surface in items:
        _inc_nested(forms, lemma, surface)

    for i in range(len(items) - 1):
        a, _surface_a = items[i]
        b, surface_b = items[i + 1]
        _inc_nested(bigrams, a, b)
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
            for items in _surface_segments(sentence):
                if items:
                    accumulate_generation(graph, items)
        return stats
    return analyze_into_graph


def _has_batchim(word):
    if not word:
        return False
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return ((code - 0xAC00) % 28) != 0
    return True


def _topic(word):
    return word + ("은" if _has_batchim(word) else "는")


def _object(word):
    return word + ("을" if _has_batchim(word) else "를")


def _with(word):
    return word + ("과" if _has_batchim(word) else "와")


def _instrumental(word):
    return word + ("으로" if _has_batchim(word) else "로")


def _node_pos(graph, lemma):
    return str(graph.get("nodes", {}).get(lemma, {}).get("pos", "unknown"))


def _surface_role(surface, lemma):
    if not surface:
        return "none"
    if surface == lemma:
        return "bare"
    if _looks_terminal(surface):
        return "predicate"
    if surface.startswith(lemma):
        suffix = surface[len(lemma):]
        if suffix in {"은", "는"}:
            return "topic"
        if suffix in {"이", "가"}:
            return "subject"
        if suffix in {"을", "를"}:
            return "object"
        if suffix in {"의"}:
            return "genitive"
        if suffix in {"에", "에서", "에게", "한테", "으로", "로"}:
            return "location"
        if suffix in {"과", "와", "하고"}:
            return "connective"
    return "other"


def _best_surface(counter_map, fallback, scorer=None):
    if not counter_map:
        return fallback
    rows = []
    for surface, count in counter_map.items():
        score = float(count)
        if scorer:
            score += float(scorer(surface))
        rows.append((score, int(count), -len(surface), surface))
    rows.sort(reverse=True)
    return rows[0][3]


def _initial_surface(graph, lemma):
    data = graph.get("generation", {})
    starts = data.get("start_surfaces", {}).get(lemma, {})
    forms = data.get("forms", {}).get(lemma, {})
    candidates = Counter()
    for surface, count in forms.items():
        candidates[surface] += max(1, int(count))
    for surface, count in starts.items():
        candidates[surface] += max(1, int(count)) * 3

    if not candidates:
        return lemma

    pos = _node_pos(graph, lemma)

    def bonus(surface):
        role = _surface_role(surface, lemma)
        table = {
            "topic": 8.0,
            "subject": 7.0,
            "bare": 4.0,
            "predicate": 2.5,
            "connective": -1.0,
            "location": -2.0,
            "object": -4.0,
            "genitive": -5.0,
        }
        return table.get(role, 0.0)

    chosen = _best_surface(candidates, lemma, bonus)
    role = _surface_role(chosen, lemma)
    if pos in {"noun", "proper"} and role in {"object", "genitive", "location", "connective"}:
        if re.fullmatch(r"[가-힣]+", lemma):
            return _topic(lemma)
        return lemma
    return chosen


def _surface_candidates(counter_map):
    return sorted(
        ((surface, int(count)) for surface, count in (counter_map or {}).items()),
        key=lambda x: (-x[1], len(x[0]), x[0]),
    )


def _surface_conflict(prev_surface, prev_lemma, surface, lemma):
    prev_role = _surface_role(prev_surface, prev_lemma)
    role = _surface_role(surface, lemma)
    return prev_role == "object" and role == "object"


def _target_surface(graph, path, surfaces, target):
    data = graph.get("generation", {})
    sources = []
    if len(path) >= 2:
        key3 = SEP.join((path[-2], path[-1], target))
        counter = data.get("trigram_surfaces", {}).get(key3, {})
        if counter:
            sources.append(counter)
    if path:
        key2 = SEP.join((path[-1], target))
        counter = data.get("pair_surfaces", {}).get(key2, {})
        if counter:
            sources.append(counter)
    forms = data.get("forms", {}).get(target, {})
    if forms:
        sources.append(forms)

    prev_surface = surfaces[-1] if surfaces else ""
    prev_lemma = path[-1] if path else ""
    had_contextual = bool(sources)

    for counter in sources:
        rows = _surface_candidates(counter)
        pos = _node_pos(graph, target)
        if pos in {"verb", "adjective"}:
            rows.sort(key=lambda x: (not _looks_terminal(x[0]), -x[1], len(x[0]), x[0]))
        for surface, _count in rows:
            if _surface_conflict(prev_surface, prev_lemma, surface, target):
                continue
            return surface

    if had_contextual:
        return None
    return target


def _next_counts(graph, path):
    data = graph.get("generation", {})
    if len(path) >= 2:
        context = SEP.join((path[-2], path[-1]))
        tri = data.get("trigrams", {}).get(context, {})
        if tri:
            return tri, "trigram"
        return {}, "none"
    if not path:
        return {}, "none"
    return data.get("bigrams", {}).get(path[-1], {}), "bigram"


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


def _seed_affinity(graph, seed, target):
    if not seed or not target or seed == target:
        return 0.0
    score = 0.0
    edge = graph.get("edges", {}).get(seed, {}).get(target)
    if edge:
        score = max(score, min(0.35, float(edge.get("score", 0)) * 0.35))
    relations = graph.get("relations", {})
    rels = relations.values() if isinstance(relations, dict) else relations
    for rel in rels or []:
        if {seed, target} == {rel.get("source"), rel.get("target")}:
            score = max(score, 0.30 * float(rel.get("confidence", 0)))
    return score


def _looks_terminal(surface):
    return bool(surface) and surface.endswith(
        ("다", "요", "니다", "습니다", "한다", "된다", "였다", "이다", "했다", "됐다")
    )


def _is_terminal(graph, lemma, surface):
    if not _looks_terminal(surface):
        return False
    if surface.endswith(("이다", "입니다", "였다", "이었다")):
        return True
    return _node_pos(graph, lemma) in {"verb", "adjective", "unknown"}


def _sentence_valid(graph, path, surfaces):
    if len(path) < 2 or len(path) != len(surfaces):
        return False
    if not _is_terminal(graph, path[-1], surfaces[-1]):
        return False
    first_role = _surface_role(surfaces[0], path[0])
    if first_role in {"object", "genitive", "location", "connective"}:
        return False
    for i in range(1, len(path)):
        if _surface_conflict(surfaces[i - 1], path[i - 1], surfaces[i], path[i]):
            return False
    return True


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

            if len(path) >= 2 and _sentence_valid(graph, path, surfaces):
                completed.append((path, surfaces, score + 0.20, evidence))
                continue

            counts, model = _next_counts(graph, path)
            total = sum(int(v) for v in counts.values())
            if not counts or total <= 0:
                continue

            ranked = sorted(
                ((token, int(count)) for token, count in counts.items()),
                key=lambda x: (-x[1], x[0]),
            )[:12]

            for target, count in ranked:
                if path.count(target) >= 1:
                    continue
                target_surface = _target_surface(graph, path, surfaces, target)
                if not target_surface:
                    continue
                probability = count / total
                new_score = (
                    score
                    + math.log(max(probability, 1e-9))
                    + _relation_bonus(graph, current, target)
                    + _seed_affinity(graph, seed, target)
                    + (0.18 if model == "trigram" else 0.0)
                )
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
        if _sentence_valid(graph, state[0], state[1]):
            completed.append(state)

    unique = {}
    for path, surfaces, score, evidence in completed:
        if not _sentence_valid(graph, path, surfaces):
            continue
        text = _finish_text(surfaces)
        if not text or text in unique:
            continue
        unique[text] = {
            "text": text,
            "mode": "sequence",
            "basis": "Corpus의 끊기지 않은 단어 순서",
            "score": round(float(score), 4),
            "path": path,
            "evidence": evidence,
        }

    ranked = sorted(
        unique.values(),
        key=lambda x: (-float(x["score"]), len(x["path"]), x["text"]),
    )
    return ranked[:max(1, int(limit))]


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
        "property": f"{s} {target}의 특성을 가진다.",
        "component": f"{s} {_instrumental(target)} 구성된다.",
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
        sequence_rows.extend(generate_sequence_sentences(graph, seed, limit=3))

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
        result["generated_sentences"] = generate_sentences(graph, seeds, limit=5)
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
        out["generation_bigram_sources"] = len(data.get("bigrams", {}))
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
