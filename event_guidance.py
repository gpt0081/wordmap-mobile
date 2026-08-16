from __future__ import annotations

import activation
import generation
import wordmap_gpt2

VERSION = "0.12.0"


def _event_guided_generate(graph, seeds, preferred_start, limit=3, max_words=None):
    seeds = [x for x in (seeds or []) if x]
    if not seeds or not preferred_start:
        return []
    if max_words is None:
        max_words = wordmap_gpt2.MAX_WORDS

    start_surface = generation._initial_surface(graph, preferred_start)
    beams = [{
        "path": [preferred_start],
        "surfaces": [start_surface],
        "score": 0.0,
        "trace": [],
    }]
    completed = []

    for step_index in range(max(1, int(max_words)) - 1):
        next_beams = []
        for beam in beams:
            completed_row = wordmap_gpt2._complete_row(graph, seeds, beam)
            if completed_row:
                completed.append(completed_row)
                continue

            rows, state = wordmap_gpt2._score_candidates(
                graph,
                seeds,
                beam["path"],
                beam["surfaces"],
            )
            if not rows:
                continue

            top_candidates = wordmap_gpt2._trace_candidates(rows, limit=5)
            active_top = activation.top_rows(state, limit=5, exclude=[])
            for chosen in rows[:wordmap_gpt2.EXPAND_PER_BEAM]:
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
        beams = next_beams[:wordmap_gpt2.BEAM_WIDTH]

    for beam in beams:
        row = wordmap_gpt2._complete_row(graph, seeds, beam)
        if row:
            completed.append(row)

    unique = {}
    for row in completed:
        text = row.get("text", "")
        if not text:
            continue
        item = dict(row)
        item["basis"] = "상황/사건 문맥 + " + str(item.get("basis", "단어지도 GPT-2식"))
        item["situation_guided"] = True
        old = unique.get(text)
        if old is None or float(item.get("score", 0)) > float(old.get("score", 0)):
            unique[text] = item

    ranked = sorted(
        unique.values(),
        key=lambda x: (
            -float(x.get("score", 0)),
            -float(x.get("activation_support", 0)),
            len(x.get("path", [])),
            str(x.get("text", "")),
        )
    )
    return ranked[:max(1, int(limit))]


def _event_candidate(result):
    answer = result.get("상황답변") or {}
    sentence = answer.get("근거문장")
    if not sentence:
        return None
    situation = result.get("상황문맥") or {}
    return {
        "text": sentence,
        "mode": "event",
        "basis": "상황/사건 지도 직접 조회",
        "score": 120.0,
        "path": list(situation.get("핵심노드") or []),
        "event_role": answer.get("역할"),
        "event_values": list(answer.get("값") or []),
        "evidence_count": int(answer.get("근거수", 1)),
    }


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        situation = result.get("상황문맥") or {}
        seeds = list(situation.get("핵심노드") or [])
        preferred_start = situation.get("생성시작")
        result["event_guidance_version"] = VERSION

        if not seeds:
            return result

        graph = core.load_graph(vault)
        state = activation.build_context_state(graph, seeds=seeds, path=[], steps=2)
        result["문맥활성화"] = activation.top_rows(state, limit=12, exclude=[])
        result["context_seed_tokens"] = seeds
        if result.get("next_word_candidates"):
            result["next_word_candidates"] = activation.rerank_next_candidates(
                result["next_word_candidates"], state
            )

        dynamic = _event_guided_generate(
            graph,
            seeds,
            preferred_start,
            limit=3,
        ) if preferred_start else []

        old_generated = result.get("generated_sentences", []) or []
        semantic = [row for row in old_generated if row.get("mode") == "semantic"][:2]
        event_row = _event_candidate(result)

        combined = []
        if event_row:
            combined.append(event_row)
        combined.extend(dynamic)
        combined.extend(semantic)
        if combined:
            seen = set()
            result["generated_sentences"] = [
                row for row in combined
                if row.get("text") and not (row.get("text") in seen or seen.add(row.get("text")))
            ][:6]

        if dynamic:
            result["자동회귀생성과정"] = dynamic[0].get("generation_trace", [])
        result["생성모델"] = "상황지도 + 단어지도 GPT-2식 자동회귀 v0.12"
        return result
    return ask


def make_status(original_status):
    def status():
        out = original_status()
        out["event_guidance_version"] = VERSION
        out["context_model"] = "사건역할+동적활성화+자동회귀"
        return out
    return status


def apply(core):
    original_ask = core.ask
    original_status = core.status
    core.ask = make_ask(core, original_ask)
    core.status = make_status(original_status)
    return core
