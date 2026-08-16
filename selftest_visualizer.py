#!/usr/bin/env python3

import visualizer


class Core:
    @staticmethod
    def load_graph(_vault):
        return {
            "nodes": {
                "생태계": {"frequency": 20, "pos": "noun", "pos_ko": "명사"},
                "경쟁": {"frequency": 8, "pos": "noun", "pos_ko": "명사"},
                "협력": {"frequency": 7, "pos": "noun", "pos_ko": "명사"},
                "기생": {"frequency": 6, "pos": "noun", "pos_ko": "명사"},
                "존재하다": {"frequency": 5, "pos": "verb", "pos_ko": "동사"},
            },
            "edges": {
                "생태계": {
                    "경쟁": {"score": 0.8, "co": 3.0},
                    "협력": {"score": 0.7, "co": 2.0},
                    "기생": {"score": 0.5, "co": 1.0},
                },
                "경쟁": {"생태계": {"score": 0.8, "co": 3.0}},
                "협력": {"생태계": {"score": 0.7, "co": 2.0}},
                "기생": {"생태계": {"score": 0.5, "co": 1.0}},
            },
            "relations": {
                "r1": {
                    "source": "생태계",
                    "relation": "related_to",
                    "label": "관련",
                    "target": "협력",
                    "confidence": 0.91,
                }
            },
            "generation": {
                "bigrams": {
                    "생태계": {"경쟁": 3, "기생": 1},
                    "경쟁": {"협력": 2},
                    "협력": {"존재하다": 2},
                }
            },
            "문법": {
                "정규패턴통계": {
                    "주어 → 수식어 → 서술어": 4,
                    "주어 → 서술어": 8,
                }
            },
        }


def main():
    active = [
        {"표제어": "생태계", "활성도": 1.0},
        {"표제어": "경쟁", "활성도": 0.8},
        {"표제어": "협력", "활성도": 0.7},
    ]
    snap = visualizer.graph_snapshot(
        Core,
        "dummy",
        focus=["생태계", "경쟁"],
        active=active,
        generation_path=["생태계", "경쟁", "협력", "존재하다"],
        candidate_tokens=["기생"],
        limit=50,
    )

    ids = {node["id"] for node in snap["nodes"]}
    assert {"생태계", "경쟁", "협력", "기생", "존재하다"} <= ids, ids
    candidate = next(node for node in snap["nodes"] if node["id"] == "기생")
    assert candidate["candidate"] is True, candidate

    layers = {edge["layer"] for edge in snap["edges"]}
    assert "연상" in layers, layers
    assert "의미" in layers, layers
    assert "순서" in layers, layers
    assert "생성" in layers, layers

    assert snap["stats"]["total_nodes"] == 5, snap["stats"]
    assert snap["grammar_patterns"][0]["pattern"] == "주어 → 서술어", snap["grammar_patterns"]

    result = {
        "seed_tokens": ["생태계", "경쟁"],
        "문맥활성화": active,
        "자동회귀생성과정": [
            {
                "단계": 1,
                "이전문맥": ["생태계"],
                "활성상위": active,
                "선택": "경쟁",
                "선택표면형": "경쟁과",
                "선택확률": 0.62,
                "선택문법적합": 0.91,
                "선택후보출처": ["문맥 활성", "연상 이웃"],
                "후보상위": [
                    {"표제어": "경쟁", "표면형": "경쟁과", "선택확률": 0.62},
                    {"표제어": "협력", "표면형": "협력이", "선택확률": 0.21},
                    {"표제어": "기생", "표면형": "기생이", "선택확률": 0.11},
                ],
            }
        ],
        "generated_sentences": [
            {
                "mode": "wordmap_gpt2",
                "text": "생태계에서는 경쟁과 협력이 존재한다.",
                "path": ["생태계", "경쟁", "협력", "존재하다"],
                "grammar_pattern": "주어 → 수식어 → 서술어",
                "context_activation": active,
            }
        ],
    }

    stages = visualizer.build_visual_trace(result)
    names = [stage["name"] for stage in stages]
    assert names[0] == "장기기억 지도", names
    assert "입력 개념" in names, names
    assert "문맥 활성화" in names, names
    generation_stage = next(stage for stage in stages if stage.get("kind") == "생성")
    assert "기생" in generation_stage.get("candidate_ids", []), generation_stage
    assert stages[-1]["kind"] == "완성", stages[-1]

    print("WordMap v0.11.1 focused visual debugger self-test: OK")


if __name__ == "__main__":
    main()
