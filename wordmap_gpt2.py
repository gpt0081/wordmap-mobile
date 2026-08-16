from __future__ import annotations

import math

import activation
import generation
import language
import syntax_tags

VERSION = "0.10.0"
BEAM_WIDTH = 10
EXPAND_PER_BEAM = 4
MAX_WORDS = 10
MAX_SEQUENCE_CANDIDATES = 18
MAX_CONTEXT_CANDIDATES = 24

ACTIVATION_WEIGHT = 1.35
GRAMMAR_WEIGHT = 0.80
RELATION_WEIGHT = 0.65
TRIGRAM_BONUS = 0.24
REPEAT_PENALTY = 1.20


def _generation_data(graph):
    return graph.get("generation", {}) or {}


def _bigram_row(graph, source):
    data = _generation_data(graph)
    if source in data.get("bigrams", {}):
        return data.get("bigrams", {}).get(source, {}) or {}
    return (
        graph.get("sequence", {})
        .get("bigrams", {})
        .get(source, {})
    ) or {}


def _trigram_row(graph, path):
    if len(path) < 2:
        return {}
    key = generation.SEP.join((path[-2], path[-1]))
    return _generation_data(graph).get("trigrams", {}).get(key, {}) or {}


def _sequence_candidates(graph, path):
    if not path:
        return []

    bi = _bigram_row(graph, path[-1])
    tri = _trigram_row(graph, path)
    bi_total = sum(max(0, int(v)) for v in bi.values())
    tri_total = sum(max(0, int(v)) for v in tri.values())

    tokens = set(bi) | set(tri)
    rows = []
    for token in tokens:
        bi_count = max(0, int(bi.get(token, 0)))
        tri_count = max(0, int(tri.get(token, 0)))
        bi_p = (bi_count / bi_total) if bi_total else 0.0
        tri_p = (tri_count / tri_total) if tri_total else 0.0

        if tri_total:
            if tri_count:
                probability = (0.78 * tri_p) + (0.22 * bi_p)
                model = "3단어 문맥"
            else:
                probability = 0.12 * bi_p
                model = "2단어 보조"
        else:
            probability = bi_p
            model = "2단어 문맥"

        if probability <= 0:
            continue
        rows.append({
            "token": token,
            "count": max(bi_count, tri_count),
            "probability": probability,
            "bigram_probability": bi_p,
            "trigram_probability": tri_p,
            "model": model,
            "origins": ["말뭉치 순서"],
        })

    rows.sort(
        key=lambda x: (
            -float(x["probability"]),
            -int(x["count"]),
            str(x["token"]),
        )
    )
    return rows[:MAX_SEQUENCE_CANDIDATES]


def _known_generation_token(graph, token):
    if not token:
        return False
    data = _generation_data(graph)
    return bool(
        token in graph.get("nodes", {})
        or token in data.get("forms", {})
        or token in data.get("bigrams", {})
    )


def _relation_targets(graph, sources):
    rels = graph.get("relations", {})
    rows = rels.values() if isinstance(rels, dict) else rels
    source_set = set(sources)
    out = []
    for rel in rows or []:
        if rel.get("source") not in source_set or not rel.get("target"):
            continue
        out.append((
            rel.get("target"),
            float(rel.get("confidence", 0)),
            rel.get("label", rel.get("relation", "의미관계")),
        ))
    return out


def _candidate_pool(graph, path, state):
    """Candidate union for the WordMap autoregressive model.

    Unlike v0.9 this is not trapped inside observed bigram/trigram successors.
    New candidates can enter from active context, semantic relations, or graph
    neighbors, but receive a conservative prior unless corpus order supports them.
    """
    merged = {}

    def add(token, probability, origin, **extra):
        if not token or token in path or not _known_generation_token(graph, token):
            return
        probability = max(1e-6, min(1.0, float(probability)))
        row = merged.setdefault(token, {
            "token": token,
            "count": 0,
            "probability": 0.0,
            "bigram_probability": 0.0,
            "trigram_probability": 0.0,
            "model": "문맥 확장",
            "origins": [],
        })
        row["probability"] = max(float(row.get("probability", 0)), probability)
        if origin not in row["origins"]:
            row["origins"].append(origin)
        for key, value in extra.items():
            if key in {"count"}:
                row[key] = max(int(row.get(key, 0)), int(value))
            elif key in {"bigram_probability", "trigram_probability"}:
                row[key] = max(float(row.get(key, 0)), float(value))
            elif key == "model" and value:
                row[key] = value

    for row in _sequence_candidates(graph, path):
        add(
            row["token"],
            row["probability"],
            "말뭉치 순서",
            count=row.get("count", 0),
            bigram_probability=row.get("bigram_probability", 0),
            trigram_probability=row.get("trigram_probability", 0),
            model=row.get("model"),
        )

    for row in activation.top_rows(state, limit=MAX_CONTEXT_CANDIDATES, exclude=path):
        token = row.get("표제어")
        active = float(row.get("활성도", 0))
        add(token, 0.025 + (0.095 * active), "문맥 활성")

    for target, confidence, label in _relation_targets(graph, path[-3:]):
        add(target, 0.04 + (0.08 * confidence), f"의미관계/{label}")

    for source in path[-2:]:
        neighbors = sorted(
            (graph.get("edges", {}).get(source, {}) or {}).items(),
            key=lambda x: -float((x[1] or {}).get("score", 0)),
        )[:12]
        for target, meta in neighbors:
            strength = max(0.0, min(1.0, float((meta or {}).get("score", 0))))
            add(target, 0.015 + (0.05 * strength), "연상 이웃")

    rows = list(merged.values())
    rows.sort(
        key=lambda x: (
            -float(x.get("probability", 0)),
            -int(x.get("count", 0)),
            str(x.get("token", "")),
        )
    )
    return rows[:MAX_CONTEXT_CANDIDATES]


def _aligned_tokens(graph, path, surfaces):
    tokens = []
    for lemma, surface in zip(path, surfaces):
        pos = str(graph.get("nodes", {}).get(lemma, {}).get("pos", "unknown"))
        confidence = 0.5
        if pos == "unknown":
            resolved = language.resolve_surface_for_grammar(surface)
            if resolved:
                pos = str(resolved[0].get("pos", "unknown"))
                confidence = float(resolved[0].get("confidence", 0.5))
        tokens.append(syntax_tags._entry_token(
            surface,
            {"lemma": lemma, "pos": pos, "confidence": confidence},
        ))
    syntax_tags._refine_roles(tokens)
    return tokens


def _has_connector_between(tokens, left_index, right_index):
    for token in tokens[left_index + 1:right_index]:
        if token.get("문장역할") == "접속어" or token.get("의미역할") == "병렬":
            return True
    return False


def _duplicate_case_conflict(tokens, particles):
    indices = [i for i, token in enumerate(tokens) if token.get("조사") in particles]
    if len(indices) <= 1:
        return False
    for left, right in zip(indices, indices[1:]):
        if not _has_connector_between(tokens, left, right):
            return True
    return False


def grammar_fit(graph, path, surfaces):
    if not path or len(path) != len(surfaces):
        return 0.0, "미분류", "경로와 표면형 길이 불일치"

    tokens = _aligned_tokens(graph, path, surfaces)
    if not tokens:
        return 0.0, "미분류", "문법 토큰 없음"

    for token in tokens[:-1]:
        if token.get("문법형태") == "종결어미":
            return 0.0, syntax_tags.pattern_from_tokens(tokens), "문장 중간 종결어미"

    if _duplicate_case_conflict(tokens, {"이", "가"}):
        return 0.0, syntax_tags.pattern_from_tokens(tokens), "주격 조사 중복"
    if _duplicate_case_conflict(tokens, {"을", "를"}):
        return 0.0, syntax_tags.pattern_from_tokens(tokens), "목적격 조사 중복"

    for i in range(1, len(path)):
        if generation._surface_conflict(
            surfaces[i - 1], path[i - 1], surfaces[i], path[i]
        ):
            return 0.0, syntax_tags.pattern_from_tokens(tokens), "인접 문법 역할 충돌"

    pattern = syntax_tags.pattern_from_tokens(tokens)
    grammar_data = graph.get("문법", {})
    patterns = grammar_data.get("정규패턴통계", {}) or grammar_data.get("패턴통계", {}) or {}
    terminal = generation._sentence_valid(graph, path, surfaces)

    if not patterns:
        return 0.72, pattern, "문법 패턴 데이터 없음"

    exact = int(patterns.get(pattern, 0))
    if terminal:
        if exact <= 0:
            return 0.0, pattern, "완성 정규패턴 미관찰"
        score = min(1.0, 0.82 + (0.04 * math.log1p(exact)))
        return score, pattern, f"정규 완성패턴 {exact}회 관찰"

    prefix_matches = [
        int(count)
        for observed, count in patterns.items()
        if observed == pattern or observed.startswith(pattern + " →")
    ]
    if prefix_matches:
        best = max(prefix_matches)
        score = min(0.98, 0.72 + (0.04 * math.log1p(best)))
        return score, pattern, f"정규 패턴 접두부 {best}회 이상 관찰"

    return 0.30, pattern, "부분 정규패턴 미관찰"


def _softmax(rows):
    if not rows:
        return rows
    top = max(float(row["raw_score"]) for row in rows)
    denom = sum(math.exp(float(row["raw_score"]) - top) for row in rows)
    for row in rows:
        row["selection_probability"] = (
            math.exp(float(row["raw_score"]) - top) / denom if denom else 0.0
        )
    return rows


def _score_candidates(graph, context_seeds, path, surfaces):
    state = activation.build_context_state(
        graph,
        seeds=context_seeds,
        path=path,
        steps=2,
    )
    rows = []

    for candidate in _candidate_pool(graph, path, state):
        target = candidate["token"]
        surface = generation._target_surface(graph, path, surfaces, target)
        if not surface:
            continue

        new_path = path + [target]
        new_surfaces = surfaces + [surface]
        grammar_score, pattern, grammar_reason = grammar_fit(
            graph,
            new_path,
            new_surfaces,
        )
        if grammar_score <= 0:
            continue

        active = activation.candidate_activation(state, target)
        relation = generation._relation_bonus(graph, path[-1], target)
        prior = max(1e-9, float(candidate["probability"]))
        repeat_penalty = REPEAT_PENALTY if target in path else 0.0

        raw = (
            math.log(prior)
            + (ACTIVATION_WEIGHT * active)
            + (GRAMMAR_WEIGHT * grammar_score)
            + (RELATION_WEIGHT * relation)
            + (TRIGRAM_BONUS if candidate.get("trigram_probability", 0) > 0 else 0.0)
            - repeat_penalty
        )

        rows.append({
            **candidate,
            "surface": surface,
            "activation": active,
            "grammar_score": grammar_score,
            "grammar_pattern": pattern,
            "grammar_reason": grammar_reason,
            "relation_bonus": relation,
            "raw_score": raw,
        })

    rows.sort(
        key=lambda x: (
            -float(x["raw_score"]),
            -float(x["probability"]),
            str(x["token"]),
        )
    )
    _softmax(rows)
    return rows, state


def _trace_candidates(rows, limit=5):
    out = []
    for row in rows[:limit]:
        out.append({
            "표제어": row["token"],
            "표면형": row["surface"],
            "선택확률": round(float(row.get("selection_probability", 0)), 4),
            "순서/사전확률": round(float(row.get("probability", 0)), 4),
            "문맥활성": round(float(row.get("activation", 0)), 4),
            "문법적합": round(float(row.get("grammar_score", 0)), 4),
            "의미보너스": round(float(row.get("relation_bonus", 0)), 4),
            "후보출처": list(row.get("origins", [])),
            "문법근거": row.get("grammar_reason", ""),
        })
    return out


def _initial_beams(graph, seeds):
    unique = []
    for token in list(reversed(seeds)) + list(seeds):
        if token and token not in unique:
            unique.append(token)
        if len(unique) >= 2:
            break

    beams = []
    for i, seed in enumerate(unique):
        surface = generation._initial_surface(graph, seed)
        beams.append({
            "path": [seed],
            "surfaces": [surface],
            "score": -0.10 * i,
            "trace": [],
        })
    return beams


def _context_support(graph, seeds, path):
    if len(path) < 2:
        return 0.0, [], []
    trace = []
    total = 0.0
    weight_total = 0.0
    final_state = None
    for i in range(1, len(path)):
        prefix = path[:i]
        target = path[i]
        state = activation.build_context_state(graph, seeds=seeds, path=prefix, steps=2)
        active = activation.candidate_activation(state, target)
        weight = 1.0 + (0.12 * i)
        total += active * weight
        weight_total += weight
        trace.append({"문맥": list(prefix), "후보": target, "활성도": round(active, 4)})
        final_state = state
    support = total / weight_total if weight_total else 0.0
    return round(support, 4), trace, activation.top_rows(final_state or {}, limit=6, exclude=[])


def _complete_row(graph, seeds, beam):
    path = beam["path"]
    surfaces = beam["surfaces"]
    if not generation._sentence_valid(graph, path, surfaces):
        return None

    pattern, pattern_count, grammar_bonus = generation._grammar_pattern_meta(
        graph,
        path,
        surfaces,
    )
    if grammar_bonus is None:
        return None

    support, activation_trace, active_top = _context_support(graph, seeds, path)
    chosen_activations = [
        float(step.get("선택문맥활성", 0))
        for step in beam["trace"]
        if step.get("선택문맥활성") is not None
    ]
    mean_activation = (
        sum(chosen_activations) / len(chosen_activations)
        if chosen_activations else 0.0
    )

    return {
        "text": generation._finish_text(surfaces),
        "mode": "wordmap_gpt2",
        "basis": "단어지도 GPT-2식 자동회귀 + 확장 후보공간 + 동적 문맥 + 정규 문법패턴",
        "score": round(float(beam["score"] + grammar_bonus), 4),
        "path": list(path),
        "grammar_pattern": pattern,
        "grammar_pattern_count": pattern_count,
        "activation_support": support,
        "mean_step_activation": round(mean_activation, 4),
        "generation_trace": list(beam["trace"]),
        "activation_trace": activation_trace,
        "context_activation": active_top,
        "context_seeds": list(seeds),
    }


def generate_autoregressive_sentences(graph, seeds, limit=3, max_words=MAX_WORDS):
    seeds = [token for token in (seeds or []) if token]
    if not seeds:
        return []

    beams = _initial_beams(graph, seeds)
    completed = []

    for step_index in range(max(1, int(max_words)) - 1):
        next_beams = []
        for beam in beams:
            completed_row = _complete_row(graph, seeds, beam)
            if completed_row:
                completed.append(completed_row)
                continue

            rows, state = _score_candidates(
                graph,
                seeds,
                beam["path"],
                beam["surfaces"],
            )
            if not rows:
                continue

            top_candidates = _trace_candidates(rows, limit=5)
            active_top = activation.top_rows(state, limit=5, exclude=[])

            for chosen in rows[:EXPAND_PER_BEAM]:
                step = {
                    "단계": step_index + 1,
                    "이전문맥": list(beam["path"]),
                    "활성상위": active_top,
                    "후보상위": top_candidates,
                    "선택": chosen["token"],
                    "선택표면형": chosen["surface"],
                    "선택확률": round(float(chosen.get("selection_probability", 0)), 4),
                    "선택문맥활성": round(float(chosen.get("activation", 0)), 4),
                    "선택문법적합": round(float(chosen.get("grammar_score", 0)), 4),
                    "선택후보출처": list(chosen.get("origins", [])),
                }
                next_beams.append({
                    "path": beam["path"] + [chosen["token"]],
                    "surfaces": beam["surfaces"] + [chosen["surface"]],
                    "score": beam["score"] + float(chosen["raw_score"]),
                    "trace": beam["trace"] + [step],
                })

        if not next_beams:
            break

        next_beams.sort(
            key=lambda x: (
                -float(x["score"]),
                len(x["path"]),
                " ".join(x["surfaces"]),
            )
        )
        beams = next_beams[:BEAM_WIDTH]

    for beam in beams:
        row = _complete_row(graph, seeds, beam)
        if row:
            completed.append(row)

    unique = {}
    for row in completed:
        text = row.get("text", "")
        if not text:
            continue
        old = unique.get(text)
        if old is None or float(row["score"]) > float(old["score"]):
            unique[text] = row

    ranked = sorted(
        unique.values(),
        key=lambda x: (
            -float(x.get("score", 0)),
            -float(x.get("activation_support", 0)),
            len(x.get("path", [])),
            x.get("text", ""),
        )
    )
    return ranked[:max(1, int(limit))]


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        seeds = result.get("seed_tokens") or result.get("query_tokens") or []
        dynamic = generate_autoregressive_sentences(graph, seeds, limit=3)

        if dynamic:
            semantic = [
                row for row in result.get("generated_sentences", [])
                if row.get("mode") == "semantic"
            ][:2]
            result["generated_sentences"] = dynamic + semantic
            result["자동회귀생성과정"] = dynamic[0].get("generation_trace", [])
        else:
            result["자동회귀생성과정"] = []

        result["wordmap_gpt2_version"] = VERSION
        result["생성모델"] = "단어지도 GPT-2식 자동회귀 v0.10"
        return result

    return ask


def make_status(original_status):
    def status():
        out = original_status()
        out["wordmap_gpt2_version"] = VERSION
        out["candidate_space"] = "n-gram+문맥활성+의미관계+연상이웃"
        return out
    return status


def apply(core):
    original_ask = core.ask
    original_status = core.status
    core.ask = make_ask(core, original_ask)
    core.status = make_status(original_status)
    return core
