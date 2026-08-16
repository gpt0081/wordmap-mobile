#!/usr/bin/env python3

import json

import event_graph
import language
import lexicon

VERSION = "0.12.0"

CORPUS = [
    "다람쥐는 숲에서 씨앗과 열매를 먹는다.",
    "토끼는 들판에서 풀잎을 먹는다.",
    "사슴은 숲에서 나뭇잎을 먹는다.",
    "철수는 도서관에서 책자를 읽는다.",
    "학생은 교실에서 문제집을 읽는다.",
    "고양이는 방에서 사료를 먹는다.",
]

EXTRACTION_CASES = [
    {
        "sentence": "다람쥐는 숲에서 씨앗과 열매를 먹는다.",
        "predicate": "먹다",
        "roles": {"행위자": {"다람쥐"}, "장소": {"숲"}, "대상": {"씨앗", "열매"}},
    },
    {
        "sentence": "토끼는 들판에서 풀잎을 먹는다.",
        "predicate": "먹다",
        "roles": {"행위자": {"토끼"}, "장소": {"들판"}, "대상": {"풀잎"}},
    },
    {
        "sentence": "사슴은 숲에서 나뭇잎을 먹는다.",
        "predicate": "먹다",
        "roles": {"행위자": {"사슴"}, "장소": {"숲"}, "대상": {"나뭇잎"}},
    },
    {
        "sentence": "철수는 도서관에서 책자를 읽는다.",
        "predicate": "읽다",
        "roles": {"행위자": {"철수"}, "장소": {"도서관"}, "대상": {"책자"}},
    },
]

QA_CASES = [
    ("다람쥐는 무엇을 먹는가?", "대상", {"씨앗", "열매"}),
    ("토끼는 무엇을 먹는가?", "대상", {"풀잎"}),
    ("철수는 어디에서 책자를 읽는가?", "장소", {"도서관"}),
]


def _prepare_language():
    data = lexicon.build(CORPUS)
    language._set(data)


def _role_sets(event):
    return {role: set(values) for role, values in (event or {}).get("역할", {}).items()}


def run():
    _prepare_language()
    extraction_details = []
    extraction_passed = 0

    for case in EXTRACTION_CASES:
        event = event_graph.extract_event(case["sentence"])
        roles = _role_sets(event)
        ok = bool(event) and event.get("서술어") == case["predicate"]
        if ok:
            for role, expected in case["roles"].items():
                if not expected <= roles.get(role, set()):
                    ok = False
                    break
        extraction_passed += int(ok)
        extraction_details.append({
            "sentence": case["sentence"],
            "passed": ok,
            "predicate": (event or {}).get("서술어"),
            "roles": (event or {}).get("역할", {}),
        })

    graph = {}
    for sentence in CORPUS:
        event = event_graph.extract_event(sentence)
        if event:
            event_graph.accumulate_event(graph, event)

    qa_details = []
    qa_passed = 0
    for question, role, expected in QA_CASES:
        situation = event_graph.analyze_input(question)
        hits = event_graph.find_events(
            graph,
            situation.get("사건"),
            requested_role=situation.get("요청역할"),
            limit=5,
        )
        found = set(hits[0].get("답후보", [])) if hits else set()
        ok = situation.get("요청역할") == role and expected <= found
        qa_passed += int(ok)
        qa_details.append({
            "question": question,
            "requested_role": situation.get("요청역할"),
            "expected": sorted(expected),
            "found": sorted(found),
            "passed": ok,
        })

    total = len(EXTRACTION_CASES) + len(QA_CASES)
    passed = extraction_passed + qa_passed
    result = {
        "version": VERSION,
        "score": round(passed / total, 4) if total else 0.0,
        "passed": passed,
        "total": total,
        "event_extraction": {
            "passed": extraction_passed,
            "total": len(EXTRACTION_CASES),
            "details": extraction_details,
        },
        "event_qa": {
            "passed": qa_passed,
            "total": len(QA_CASES),
            "details": qa_details,
        },
        "learned": {
            "event_evidence": int(graph.get("상황지도", {}).get("사건수", 0)),
            "unique_events": len(graph.get("상황지도", {}).get("사건", {})),
            "predicate_frames": graph.get("상황지도", {}).get("서술어프레임", {}),
        },
    }
    return result


def main():
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["passed"] != result["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
