from __future__ import annotations

import hashlib
import re
from collections import defaultdict

import grammar
import language
import syntax_tags

VERSION = "0.12.0"
MAX_EVENTS = 12000
MAX_EXAMPLES = 4

QUESTION_PREFIXES = ("무엇", "뭐", "어디", "왜", "어떻게", "언제", "누구", "누가", "무슨", "어떤", "어느", "얼마", "몇")


def _ensure(graph):
    data = graph.setdefault("상황지도", {})
    data.setdefault("버전", VERSION)
    data.setdefault("사건수", 0)
    data.setdefault("사건", {})
    data.setdefault("서술어프레임", {})
    data.setdefault("역할값", {})
    return data


def _query_resolver(surface):
    rows = language.resolve_surface_for_grammar(surface)
    if rows:
        return rows

    low = surface.strip("._-/").lower()
    # Frequent Korean question endings. This is intentionally conservative and
    # grammar-only; it does not create new graph nodes.
    for ending in ("는가", "는지"):
        if low.endswith(ending) and len(low) > len(ending):
            stem = low[:-len(ending)]
            return [{
                "lemma": stem + "다",
                "pos": "verb",
                "confidence": 0.88,
                "reason": "event_question_ending",
            }]
    for ending in ("은가", "ㄴ가"):
        if low.endswith(ending) and len(low) > len(ending):
            stem = low[:-len(ending)]
            return [{
                "lemma": stem + "다",
                "pos": "adjective",
                "confidence": 0.82,
                "reason": "event_question_ending",
            }]
    return grammar.syntax_fallback(low)


def _requested_role(question):
    words = grammar.raw_words(question)
    for surface in words:
        low = surface.lower()
        particle = grammar.particle_candidate(low)
        base = particle[0] if particle else low
        suffix = particle[1] if particle else ""

        if base.startswith("어디") or low.startswith("어디"):
            return "장소"
        if base.startswith("왜") or low.startswith("왜"):
            return "원인"
        if base.startswith("어떻게") or low.startswith("어떻게"):
            return "방법"
        if base.startswith("언제") or low.startswith("언제"):
            return "시간"
        if base.startswith("누가"):
            return "행위자"
        if base.startswith("누구"):
            return "대상" if suffix in {"을", "를", "에게", "한테"} else "행위자"
        if base.startswith("무엇") or base.startswith("뭐") or low.startswith("무엇") or low.startswith("뭐"):
            if suffix in {"을", "를"}:
                return "대상"
            if suffix in {"에", "에서"}:
                return "장소"
            if re.search(r"무엇(?:인가|이다|입니까)|뭐(?:야|냐)", low):
                return "정의"
            # In an event question, a bare '무엇' most often asks for the
            # missing event participant. Definition questions are handled by
            # the semantic-relation layer when no predicate can be recovered.
            return "대상"
    return None


def _question_content(question):
    kept = []
    for surface in grammar.raw_words(question):
        low = surface.lower()
        if any(low.startswith(prefix) for prefix in QUESTION_PREFIXES):
            continue
        kept.append(surface)
    return " ".join(kept).strip()


def _role_for_token(tokens, index, predicate_pos):
    token = tokens[index]
    role = token.get("문장역할")
    semantic = token.get("의미역할", "")

    if role == "주어":
        return "행위자" if predicate_pos == "verb" else "주제"
    if role == "목적어":
        return "대상"
    if role == "보어":
        return "보어"
    if role == "부사어":
        if "장소" in semantic:
            return "장소"
        if "방향" in semantic or "수단" in semantic:
            return "수단"
        if semantic == "대상":
            return "수혜자"
        if semantic == "범위":
            return "범위"
        return "부가정보"

    # Korean coordination often gives the case particle only to the final
    # conjunct: '씨앗과 열매를'. Give the preceding connector the same event
    # role as the next explicit participant.
    if role == "접속어":
        for j in range(index + 1, min(len(tokens), index + 3)):
            nxt = tokens[j]
            nxt_role = nxt.get("문장역할")
            if nxt_role == "목적어":
                return "대상"
            if nxt_role == "주어":
                return "행위자" if predicate_pos == "verb" else "주제"
            if nxt_role == "부사어" and "장소" in nxt.get("의미역할", ""):
                return "장소"
    return None


def extract_event(sentence, resolver=None):
    analysis = syntax_tags.analyze_sentence(sentence, resolver=resolver)
    tokens = analysis.get("토큰", [])
    predicate_index = None
    for i, token in enumerate(tokens):
        if token.get("문장역할") == "서술어":
            predicate_index = i
    if predicate_index is None:
        return None

    predicate_token = tokens[predicate_index]
    predicate = predicate_token.get("표제어")
    if not predicate:
        return None
    predicate_pos = predicate_token.get("품사코드", "unknown")

    roles = defaultdict(list)
    for i, token in enumerate(tokens):
        if i == predicate_index:
            continue
        event_role = _role_for_token(tokens, i, predicate_pos)
        lemma = token.get("표제어")
        if not event_role or not lemma or lemma == predicate:
            continue
        if lemma not in roles[event_role]:
            roles[event_role].append(lemma)

    if not roles:
        return None

    confidence_values = [
        float(token.get("분석신뢰", 0))
        for token in tokens
        if token.get("분석신뢰") is not None
    ]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    frame_roles = sorted(roles)
    frame = " + ".join(frame_roles)
    event_type = "행동" if predicate_pos == "verb" else ("상태" if predicate_pos == "adjective" else "정의/서술")

    return {
        "문장": sentence.strip(),
        "사건종류": event_type,
        "서술어": predicate,
        "서술어품사": predicate_pos,
        "역할": dict(roles),
        "프레임": frame,
        "분석신뢰": round(confidence, 3),
        "문법패턴": analysis.get("정규패턴", analysis.get("패턴", "미분류")),
    }


def _event_signature(event):
    parts = [event.get("서술어", "")]
    for role in sorted(event.get("역할", {})):
        values = ",".join(sorted(event["역할"].get(role, [])))
        parts.append(f"{role}={values}")
    return "|".join(parts)


def accumulate_event(graph, event):
    if not event or not event.get("서술어"):
        return
    data = _ensure(graph)
    data["버전"] = VERSION
    data["사건수"] = int(data.get("사건수", 0)) + 1

    signature = _event_signature(event)
    event_id = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:16]
    events = data["사건"]
    if event_id not in events and len(events) >= MAX_EVENTS:
        return

    row = events.setdefault(event_id, {
        "id": event_id,
        "서술어": event.get("서술어"),
        "서술어품사": event.get("서술어품사"),
        "사건종류": event.get("사건종류"),
        "역할": event.get("역할", {}),
        "프레임": event.get("프레임", ""),
        "문법패턴": event.get("문법패턴", ""),
        "근거수": 0,
        "근거문장": [],
        "평균신뢰": 0.0,
    })
    old_count = int(row.get("근거수", 0))
    new_count = old_count + 1
    old_mean = float(row.get("평균신뢰", 0))
    row["근거수"] = new_count
    row["평균신뢰"] = round((old_mean * old_count + float(event.get("분석신뢰", 0))) / new_count, 3)
    sentence = event.get("문장")
    if sentence and sentence not in row["근거문장"] and len(row["근거문장"]) < MAX_EXAMPLES:
        row["근거문장"].append(sentence)

    predicate = event["서술어"]
    frame = event.get("프레임", "미분류") or "미분류"
    predicate_frames = data["서술어프레임"].setdefault(predicate, {})
    predicate_frames[frame] = int(predicate_frames.get(frame, 0)) + 1

    values_root = data["역할값"].setdefault(predicate, {})
    for role, values in event.get("역할", {}).items():
        bucket = values_root.setdefault(role, {})
        for value in values:
            bucket[value] = int(bucket.get(value, 0)) + 1


def _known_role_values(event):
    return {
        role: set(values)
        for role, values in (event or {}).get("역할", {}).items()
        if values
    }


def find_events(graph, query_event, requested_role=None, limit=8):
    if not query_event or not query_event.get("서술어"):
        return []
    predicate = query_event.get("서술어")
    known = _known_role_values(query_event)
    events = (graph.get("상황지도", {}) or {}).get("사건", {}) or {}
    rows = []

    for event in events.values():
        if event.get("서술어") != predicate:
            continue
        roles = event.get("역할", {}) or {}
        if requested_role and requested_role not in roles:
            continue

        score = 4.0
        matched = 0
        rejected = False
        for role, expected in known.items():
            observed = set(roles.get(role, []))
            # Do not use the requested slot itself as a hard query condition.
            if role == requested_role:
                continue
            if observed:
                overlap = expected & observed
                if overlap:
                    score += 2.5 * len(overlap)
                    matched += len(overlap)
                else:
                    rejected = True
                    break
        if rejected:
            continue

        score += min(1.5, 0.25 * int(event.get("근거수", 1)))
        score += 0.5 * float(event.get("평균신뢰", 0))
        rows.append({
            "id": event.get("id"),
            "점수": round(score, 3),
            "일치수": matched,
            "서술어": predicate,
            "역할": roles,
            "요청역할": requested_role,
            "답후보": list(roles.get(requested_role, [])) if requested_role else [],
            "근거수": int(event.get("근거수", 1)),
            "근거문장": list(event.get("근거문장", [])),
            "프레임": event.get("프레임"),
        })

    rows.sort(key=lambda x: (-float(x["점수"]), -int(x["근거수"]), str(x.get("id", ""))))
    return rows[:max(1, int(limit))]


def analyze_input(question):
    requested = _requested_role(question)
    content = _question_content(question) if requested else question
    event = extract_event(content, resolver=_query_resolver) if content.strip() else None

    if event:
        roles = event.get("역할", {})
        ordered_roles = ("행위자", "주제", "장소", "대상", "수혜자", "수단", "보어", "부가정보")
        core_nodes = []
        for role in ordered_roles:
            for token in roles.get(role, []):
                if token not in core_nodes:
                    core_nodes.append(token)
        predicate = event.get("서술어")
        if predicate and predicate not in core_nodes:
            core_nodes.append(predicate)
        start = (roles.get("행위자") or roles.get("주제") or core_nodes[:1])
    else:
        core_nodes = []
        start = []

    return {
        "입력유형": "질문" if requested else ("서술문" if event else "키워드/미분류"),
        "요청역할": requested,
        "사건": event,
        "핵심노드": core_nodes,
        "생성시작": start[0] if start else None,
    }


def make_analyze(core, original_analyze):
    def analyze_into_graph(graph, text, window=4):
        stats = original_analyze(graph, text, window=window)
        for sentence in core.split_sentences(text):
            event = extract_event(sentence)
            if event:
                accumulate_event(graph, event)
        return stats
    return analyze_into_graph


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        situation = analyze_input(question)
        result["상황문맥"] = situation
        result["event_graph_version"] = VERSION

        event = situation.get("사건")
        requested = situation.get("요청역할")
        hits = find_events(graph, event, requested_role=requested, limit=8) if event else []
        result["상황검색"] = hits

        if requested and hits:
            best = hits[0]
            evidence = best.get("근거문장") or []
            if evidence:
                event_candidate = {
                    "text": evidence[0],
                    "mode": "event",
                    "basis": "상황/사건 지도 직접 조회",
                    "score": 100.0 + float(best.get("점수", 0)),
                    "path": list(situation.get("핵심노드") or []),
                    "event_role": requested,
                    "event_values": list(best.get("답후보") or []),
                    "evidence_count": int(best.get("근거수", 1)),
                }
                existing = result.get("generated_sentences", []) or []
                result["generated_sentences"] = [event_candidate] + existing
                result["상황답변"] = {
                    "역할": requested,
                    "값": list(best.get("답후보") or []),
                    "근거문장": evidence[0],
                    "근거수": int(best.get("근거수", 1)),
                }
        return result
    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out
        data = core.load_graph(vault).get("상황지도", {}) or {}
        out["event_graph_version"] = data.get("버전", VERSION)
        out["event_evidence"] = int(data.get("사건수", 0))
        out["unique_events"] = len(data.get("사건", {}) or {})
        out["predicate_frames"] = sum(len(x) for x in (data.get("서술어프레임", {}) or {}).values())
        return out
    return status


def apply(core):
    original_analyze = core.analyze_into_graph
    original_ask = core.ask
    original_status = core.status
    core.analyze_into_graph = make_analyze(core, original_analyze)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    core.extract_event = extract_event
    core.find_events = find_events
    return core
