from __future__ import annotations

from collections import Counter

import grammar
import language

VERSION = "0.7.0"

POS_KO = {
    "noun": "명사",
    "verb": "동사",
    "adjective": "형용사",
    "adverb": "부사",
    "proper": "고유명사",
    "unknown": "미분류",
}

QUESTION_INTENTS = (
    ("어떻게", "방법"),
    ("무엇", "정의"),
    ("뭐", "정의"),
    ("어디", "장소"),
    ("왜", "원인"),
    ("언제", "시간"),
    ("누구", "대상"),
    ("무슨", "종류"),
    ("어떤", "속성"),
    ("어느", "선택"),
    ("얼마", "수량"),
    ("몇", "수량"),
)

TERMINAL_ENDINGS = (
    "다", "요", "니다", "습니다", "한다", "된다", "했다", "됐다",
    "이다", "입니다", "였다", "이었다", "한다", "된다", "준다",
)
ADNOMINAL_ENDINGS = ("는", "은", "ㄴ", "을", "ㄹ", "던", "한", "적인")


def _ensure(graph):
    data = graph.setdefault("문법", {})
    data.setdefault("버전", VERSION)
    data.setdefault("문장수", 0)
    data.setdefault("패턴통계", {})
    data.setdefault("패턴예문", {})
    data.setdefault("표제어역할", {})
    data.setdefault("문장분석", [])
    return data


def _particle_from_surface(surface, lemma):
    if not surface or not lemma:
        return None
    if surface.startswith(lemma):
        suffix = surface[len(lemma):]
        if suffix in grammar.PARTICLES:
            return suffix
    return None


def _terminal(surface):
    return bool(surface) and surface.endswith(TERMINAL_ENDINGS)


def _adnominal(surface, pos):
    if pos not in {"verb", "adjective"} or not surface or _terminal(surface):
        return False
    return surface.endswith(ADNOMINAL_ENDINGS)


def _preliminary_role(surface, lemma, pos, particle):
    if pos == "adverb":
        return "부사어", None, None

    if pos in {"verb", "adjective"}:
        if _terminal(surface):
            return "서술어", None, "종결어미"
        if _adnominal(surface, pos):
            return "관형어", None, "관형형"
        return "서술어", None, "비종결"

    if particle in {"은", "는"}:
        return "주어", "주제", None
    if particle in {"이", "가"}:
        return "주어", "행위주체", None
    if particle in {"을", "를"}:
        return "목적어", "대상", None
    if particle == "의":
        return "관형어", "소유/수식", None
    if particle in {"에", "에서"}:
        return "부사어", "장소", None
    if particle in {"에게", "한테"}:
        return "부사어", "대상", None
    if particle in {"으로", "로"}:
        return "부사어", "방향/수단", None
    if particle in {"과", "와", "하고"}:
        return "접속어", "병렬", None
    if particle in {"부터", "까지"}:
        return "부사어", "범위", None

    return "체언" if pos in {"noun", "proper", "unknown"} else "미분류", None, None


def _entry_token(surface, entry):
    lemma = str(entry.get("lemma", surface))
    pos = str(entry.get("pos", "unknown"))
    pos_ko = POS_KO.get(pos, grammar.POS_KO.get(pos, "미분류"))
    particle = _particle_from_surface(surface, lemma)
    role, semantic, form = _preliminary_role(surface, lemma, pos, particle)
    token = {
        "표면형": surface,
        "표제어": lemma,
        "품사": pos_ko,
        "품사코드": pos,
        "문장역할": role,
    }
    if semantic:
        token["의미역할"] = semantic
    if particle:
        token["조사"] = particle
    if form:
        token["문법형태"] = form
    return token


def _unknown_token(surface):
    return {
        "표면형": surface,
        "표제어": surface,
        "품사": "미분류",
        "품사코드": "unknown",
        "문장역할": "미분류",
    }


def _refine_roles(tokens):
    # Bare nouns before another noun act as noun modifiers in many Korean noun
    # phrases: '고무 물성', '재고 관리', '우주 탐사'.
    for i, token in enumerate(tokens[:-1]):
        if token.get("문장역할") != "체언":
            continue
        if token.get("품사코드") not in {"noun", "proper", "unknown"}:
            continue
        nxt = tokens[i + 1]
        if nxt.get("품사코드") in {"noun", "proper", "unknown"} and nxt.get("문장역할") in {
            "체언", "주어", "목적어", "부사어"
        }:
            token["문장역할"] = "관형어"
            token["의미역할"] = "명사수식"

    # If there is no explicit subject, a sentence-initial bare noun followed by
    # a predicate is a useful conservative subject candidate.
    has_subject = any(t.get("문장역할") == "주어" for t in tokens)
    if not has_subject and tokens:
        first = tokens[0]
        if first.get("문장역할") == "체언" and any(
            t.get("문장역할") == "서술어" for t in tokens[1:]
        ):
            first["문장역할"] = "주어"
            first["의미역할"] = "주제"

    for token in tokens:
        tags = [f"품사/{token.get('품사', '미분류')}"]
        role = token.get("문장역할")
        if role and role != "미분류":
            tags.append(f"문장역할/{role}")
        semantic = token.get("의미역할")
        if semantic:
            tags.append(f"의미역할/{semantic}")
        particle = token.get("조사")
        if particle:
            tags.append(f"문법형태/조사/{particle}")
        form = token.get("문법형태")
        if form:
            tags.append(f"문법형태/{form}")
        token["태그"] = tags

    return tokens


def analyze_sentence(sentence, resolver=None):
    resolver = resolver or language.resolve_surface
    tokens = []

    for surface in grammar.raw_words(sentence):
        entries = resolver(surface) or []
        if not entries:
            tokens.append(_unknown_token(surface))
            continue

        if len(entries) == 1:
            tokens.append(_entry_token(surface, entries[0]))
            continue

        # Fused compound components have no trustworthy internal particle
        # boundary. Keep each component as a bare lexeme.
        for entry in entries:
            lemma = str(entry.get("lemma", ""))
            tokens.append(_entry_token(lemma, entry))

    _refine_roles(tokens)
    pattern = pattern_from_tokens(tokens)
    return {
        "문장": sentence.strip(),
        "패턴": pattern,
        "토큰": tokens,
    }


def _pattern_roles(tokens):
    roles = [
        token.get("문장역할")
        for token in tokens
        if token.get("문장역할") not in {None, "", "미분류"}
    ]
    # Repeated modifiers/adverbials are grouped into one structural slot. The
    # full token list is still retained in 문장분석.
    compact = []
    for role in roles:
        if not compact or compact[-1] != role:
            compact.append(role)
    return compact


def pattern_from_tokens(tokens):
    roles = _pattern_roles(tokens)
    return " → ".join(roles) if roles else "미분류"


def pattern_from_aligned(graph, path, surfaces):
    tokens = []
    for lemma, surface in zip(path, surfaces):
        pos = str(graph.get("nodes", {}).get(lemma, {}).get("pos", "unknown"))
        entry = {"lemma": lemma, "pos": pos}
        tokens.append(_entry_token(surface, entry))
    _refine_roles(tokens)
    return pattern_from_tokens(tokens)


def pattern_count(graph, pattern):
    return int(
        graph.get("문법", {})
        .get("패턴통계", {})
        .get(pattern, 0)
    )


def accumulate_syntax(graph, analysis):
    data = _ensure(graph)
    pattern = analysis.get("패턴", "미분류")
    data["문장수"] = int(data.get("문장수", 0)) + 1
    data["버전"] = VERSION

    stats = data["패턴통계"]
    stats[pattern] = int(stats.get(pattern, 0)) + 1

    examples = data["패턴예문"].setdefault(pattern, [])
    sentence = analysis.get("문장", "")
    if sentence and sentence not in examples and len(examples) < 5:
        examples.append(sentence)

    roles = data["표제어역할"]
    for token in analysis.get("토큰", []):
        lemma = token.get("표제어")
        role = token.get("문장역할")
        if not lemma or not role or role == "미분류":
            continue
        row = roles.setdefault(lemma, {})
        row[role] = int(row.get(role, 0)) + 1

    # Preserve sentence-level tags for inspection and future pattern learning.
    data["문장분석"].append(analysis)


def make_analyze(core, original_analyze):
    def analyze_into_graph(graph, text, window=4):
        stats = original_analyze(graph, text, window=window)
        for sentence in core.split_sentences(text):
            analysis = analyze_sentence(sentence)
            if analysis.get("토큰"):
                accumulate_syntax(graph, analysis)
        return stats
    return analyze_into_graph


def question_intent(surface):
    low = surface.strip("._-/").lower()
    for prefix, intent in QUESTION_INTENTS:
        if low.startswith(prefix):
            return intent
    return None


def analyze_question(question):
    intent_rows = []
    content_surfaces = []
    for surface in grammar.raw_words(question):
        intent = question_intent(surface)
        if intent:
            intent_rows.append({
                "표면형": surface,
                "의도": intent,
                "태그": f"질문의도/{intent}",
            })
        else:
            content_surfaces.append(surface)

    return {
        "원문": question,
        "내용표현": " ".join(content_surfaces).strip(),
        "의도": [row["의도"] for row in intent_rows],
        "태그": [row["태그"] for row in intent_rows],
        "의문표현": intent_rows,
    }


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        q = analyze_question(question)
        content = q.get("내용표현") or question
        result = original_ask(vault, content, limit=limit, depth=depth)
        q["핵심표제어"] = list(result.get("query_tokens", []))
        result["질문분석"] = q
        result["grammar_tag_version"] = VERSION
        return result
    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out
        graph = core.load_graph(vault)
        data = graph.get("문법", {})
        out["grammar_tag_version"] = data.get("버전", VERSION)
        out["grammar_sentences"] = int(data.get("문장수", 0))
        out["grammar_patterns"] = len(data.get("패턴통계", {}))
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
