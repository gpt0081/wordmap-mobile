from __future__ import annotations

import re

VERSION = "0.16.0"
TIME_PATTERNS = [
    (r"\b아침(?:에|에는)?\b", "아침"), (r"\b오전(?:에|에는)?\b", "오전"),
    (r"\b점심(?:에|에는| 뒤에는| 뒤에)?\b", "점심"), (r"\b오후(?:에|에는)?\b", "오후"),
    (r"\b저녁(?:에|에는)?\b", "저녁"), (r"\b밤(?:에|에는)?\b", "밤"),
    (r"\b어제(?:는|에)?\b", "어제"), (r"\b오늘(?:은|에)?\b", "오늘"),
    (r"\b현재(?:는| 상태에서)?\b", "현재"), (r"\b지금(?:은)?\b", "현재"),
    (r"\b처음(?:에는| 상태에서)?\b", "처음"), (r"\b다음 날(?:에는|에)?\b", "다음날"),
]
OWNER_RE = re.compile(r"([가-힣A-Za-z0-9]{1,20})의\s+([가-힣A-Za-z0-9]{1,30})(?:은|는|이|가|을|를)")


def _times(sentence):
    out = []
    for pattern, label in TIME_PATTERNS:
        if re.search(pattern, sentence):
            if label not in out:
                out.append(label)
    return out


def _owners(sentence):
    out = []
    for owner, _thing in OWNER_RE.findall(sentence):
        if owner not in out:
            out.append(owner)
    return out


def apply(event_graph):
    if getattr(event_graph, "_temporal_v016", False):
        return event_graph
    old_extract = event_graph.extract_event
    old_analyze_input = event_graph.analyze_input

    def extract_event(sentence, resolver=None):
        event = old_extract(sentence, resolver=resolver)
        if not event:
            return event
        roles = event.setdefault("역할", {})
        times = _times(sentence)
        owners = _owners(sentence)
        if times:
            roles["시간"] = times
        if owners:
            roles["소유자"] = owners
        if times or owners:
            event["프레임"] = " + ".join(sorted(roles))
            event["시간문맥명시"] = bool(times)
            event["소유자문맥명시"] = bool(owners)
        return event

    def analyze_input(question):
        result = old_analyze_input(question)
        event = result.get("사건")
        if event:
            core_nodes = list(result.get("핵심노드") or [])
            for role in ("시간", "소유자"):
                for token in (event.get("역할", {}) or {}).get(role, []):
                    if token not in core_nodes:
                        core_nodes.append(token)
            result["핵심노드"] = core_nodes
        return result

    event_graph.extract_event = extract_event
    event_graph.analyze_input = analyze_input
    event_graph.temporal_event_version = VERSION
    event_graph._temporal_v016 = True
    return event_graph
