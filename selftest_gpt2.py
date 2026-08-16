#!/usr/bin/env python3

import generation
import wordmap_gpt2


def main():
    graph = {
        "nodes": {
            "가황": {"pos": "noun"},
            "반응": {"pos": "noun"},
            "가격": {"pos": "noun"},
            "촉진하다": {"pos": "verb"},
        },
        "edges": {
            "가황": {
                "반응": {"score": 0.95},
                "가격": {"score": 0.04},
            },
            "반응": {"가황": {"score": 0.95}},
            "가격": {"가황": {"score": 0.04}},
        },
        "relations": {},
        "문법": {
            "패턴통계": {
                "주어 → 목적어 → 서술어": 12,
            }
        },
    }

    generation.accumulate_generation(
        graph,
        [("가황", "가황은"), ("반응", "반응을"), ("촉진하다", "촉진한다")],
    )
    generation.accumulate_generation(
        graph,
        [("가황", "가황은"), ("가격", "가격을"), ("촉진하다", "촉진한다")],
    )

    rows = wordmap_gpt2.generate_autoregressive_sentences(
        graph,
        ["가황"],
        limit=3,
    )
    assert rows, rows
    assert rows[0]["mode"] == "wordmap_gpt2", rows[0]
    assert rows[0]["text"] == "가황은 반응을 촉진한다.", rows
    assert rows[0]["path"] == ["가황", "반응", "촉진하다"], rows[0]
    assert len(rows[0]["generation_trace"]) == 2, rows[0]
    first_step = rows[0]["generation_trace"][0]
    assert first_step["선택"] == "반응", first_step
    assert first_step["후보상위"][0]["표제어"] == "반응", first_step
    assert first_step["후보상위"][0]["문맥활성"] > first_step["후보상위"][1]["문맥활성"], first_step

    conflict_graph = {
        "nodes": {
            "생태계": {"pos": "noun"},
            "경쟁": {"pos": "noun"},
            "기능": {"pos": "noun"},
        },
        "문법": {"패턴통계": {"주어": 3}},
    }
    fit, _pattern, reason = wordmap_gpt2.grammar_fit(
        conflict_graph,
        ["생태계", "경쟁", "기능"],
        ["생태계는", "경쟁이", "기능이"],
    )
    assert fit == 0.0 and reason == "주격 조사 중복", (fit, reason)

    trace = rows[0]["generation_trace"]
    assert trace[0]["이전문맥"] == ["가황"], trace
    assert trace[1]["이전문맥"] == ["가황", "반응"], trace
    assert trace[0]["후보상위"] != trace[1]["후보상위"], trace

    print("WordMap v0.10.0 autoregressive compatibility self-test: OK")


if __name__ == "__main__":
    main()
