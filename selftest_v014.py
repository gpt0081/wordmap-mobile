#!/usr/bin/env python3

import node_health


def build_graph():
    sep = "\x1f"
    return {
        "nodes": {
            "중심": {"frequency": 8, "pos": "noun", "pos_ko": "명사"},
            "이웃하나": {"frequency": 5, "pos": "noun", "pos_ko": "명사"},
            "이웃둘": {"frequency": 4, "pos": "noun", "pos_ko": "명사"},
            "약한노드": {"frequency": 2, "pos": "noun", "pos_ko": "명사"},
            "내부노드": {"frequency": 3, "pos": "noun", "pos_ko": "명사"},
            "순서상대": {"frequency": 3, "pos": "noun", "pos_ko": "명사"},
            "태그노드": {"frequency": 3, "pos": "adjective", "pos_ko": "형용사"},
            "고립노드": {"frequency": 1, "pos": "noun", "pos_ko": "명사"},
            "TESPT": {"frequency": 1, "pos": "proper", "pos_ko": "고유명사/코드"},
        },
        "edges": {
            "중심": {
                "이웃하나": {"score": 0.4, "co": 2.0},
                "이웃둘": {"score": 0.3, "co": 2.0},
                "태그노드": {"score": 0.2, "co": 1.0},
            },
            "이웃하나": {
                "중심": {"score": 0.4, "co": 2.0},
                "약한노드": {"score": 0.2, "co": 1.0},
                "태그노드": {"score": 0.2, "co": 1.0},
            },
            "이웃둘": {"중심": {"score": 0.3, "co": 2.0}},
            "약한노드": {"이웃하나": {"score": 0.2, "co": 1.0}},
            "태그노드": {
                "이웃하나": {"score": 0.2, "co": 1.0},
                "중심": {"score": 0.2, "co": 1.0},
            },
        },
        "pairs": {
            sep.join(sorted(("중심", "이웃하나"))): 2.0,
            sep.join(sorted(("중심", "이웃둘"))): 2.0,
            sep.join(sorted(("중심", "태그노드"))): 1.0,
            sep.join(sorted(("이웃하나", "약한노드"))): 1.0,
            sep.join(sorted(("이웃하나", "태그노드"))): 1.0,
            sep.join(sorted(("고립노드", "이웃둘"))): 0.1,
        },
        "sequence": {
            "bigrams": {
                "내부노드": {"순서상대": 3},
            },
        },
        "relations": {},
        "상황지도": {"사건": {}},
        "문법": {
            "표제어역할": {
                "중심": {"주어": 2},
                "이웃하나": {"목적어": 2},
                "태그노드": {"서술어": 2},
            }
        },
    }


def main():
    graph = build_graph()
    health = node_health.analyze_graph(graph)
    rows = health["노드"]

    assert rows["중심"]["상태"] == node_health.STATUS_HEALTHY
    assert rows["약한노드"]["상태"] == node_health.STATUS_WEAK
    assert rows["내부노드"]["상태"] == node_health.STATUS_VISUAL
    assert rows["고립노드"]["상태"] == node_health.STATUS_ORPHAN
    assert rows["TESPT"]["상태"] == node_health.STATUS_ORPHAN
    assert rows["TESPT"]["보호노드"] is True
    assert rows["TESPT"]["자동삭제허용"] is False

    assert rows["태그노드"]["태그필터고립"] is True
    assert "품사/형용사" in rows["태그노드"]["고립태그"]
    assert rows["고립노드"]["잘린약한연결"] >= 1

    summary = health["요약"]
    assert summary[node_health.STATUS_ORPHAN] >= 2
    assert summary["태그필터고립"] >= 1
    assert health["정책"]["자동삭제"] is False
    assert health["정책"]["태그브리지_가짜링크생성"] is False

    print("WordMap v0.14.0 node health/orphan analyzer self-test: OK")


if __name__ == "__main__":
    main()
