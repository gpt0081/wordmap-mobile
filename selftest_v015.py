#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path

import context_map
import credit_learning


def test_context_map():
    graph = {}
    ecology = [
        ("생태계에서는 협력과 공생이 함께 나타난다.", ["생태계", "협력", "공생", "종"]),
        ("생태계의 협력은 공생과 자원 공유에서 나타난다.", ["생태계", "협력", "공생", "자원"]),
        ("협력은 생태계에서 경쟁과 함께 존재할 수 있다.", ["협력", "생태계", "경쟁", "공생"]),
    ]
    international = [
        ("국제 협력은 국가와 국제기구 사이에서 이루어진다.", ["국제", "협력", "국가", "국제기구"]),
        ("국가들은 외교와 국제기구를 통해 협력한다.", ["국가", "협력", "외교", "국제기구"]),
        ("국제사회의 협력에는 국가와 외교가 중요하다.", ["국제", "협력", "국가", "외교"]),
    ]
    for sentence, tokens in ecology + international:
        context_map.accumulate_sentence(graph, sentence, tokens)

    row = graph["문맥지도"]["단어문맥"]["협력"]
    assert len(row["문맥군"]) >= 2, row

    eco = context_map.best_context_match(graph, "협력", ["생태계", "공생", "경쟁"])
    intl = context_map.best_context_match(graph, "협력", ["국제", "국가", "외교"])
    assert eco["문맥군"] != intl["문맥군"], (eco, intl)
    assert eco["적합도"] > 0.20
    assert intl["적합도"] > 0.20

    summary = context_map.map_summary(graph)
    assert summary["context_clusters"] >= 2
    assert summary["multi_context_tokens"] >= 1


def test_credit_learning():
    class Core:
        @staticmethod
        def wordmap_dirs(vault):
            meta = Path(vault) / ".wordmap"
            meta.mkdir(parents=True, exist_ok=True)
            return {"meta": meta}

    core = Core()
    with tempfile.TemporaryDirectory() as temp:
        vault = Path(temp)
        data = credit_learning._default()
        trace_id = "trace-test"
        data["pending"][trace_id] = {
            "id": trace_id,
            "question": "생태계 협력",
            "answer": "생태계의 협력은 공생과 관련된다.",
            "seeds": ["생태계", "협력"],
            "steps": [
                {"단계": 1, "이전문맥": ["생태계"], "선택": "협력", "선택확률": 0.7, "선택후보출처": ["문맥 활성"]},
                {"단계": 2, "이전문맥": ["생태계", "협력"], "선택": "공생", "선택확률": 0.6, "선택후보출처": ["의미관계/관계", "문맥 활성"]},
            ],
        }
        credit_learning._save(core, vault, data)
        out = credit_learning.feedback(core, vault, trace_id, 1)
        assert out["reward"] == 1
        assert out["updated_steps"] == 2

        learned = json.loads((vault / ".wordmap" / "learning.json").read_text(encoding="utf-8"))
        assert learned["updates"] == 1
        assert learned["positive"] == 1
        assert learned["transitions"]
        assert learned["context_targets"]
        assert learned["origins"]
        assert all(float(v) > 0 for v in learned["transitions"].values())

        credit_learning._ACTIVE["data"] = learned
        adj = credit_learning.learned_adjustment(
            ["생태계", "협력"],
            ["생태계", "협력"],
            {"token": "공생", "origins": ["문맥 활성", "의미관계/관계"]},
        )
        assert adj["total"] > 0, adj

        try:
            credit_learning.feedback(core, vault, trace_id, 1)
            raise AssertionError("duplicate feedback was accepted")
        except ValueError:
            pass


def main():
    test_context_map()
    test_credit_learning()
    print("WordMap v0.15.0 ContextMap + credit backprop self-test: OK")


if __name__ == "__main__":
    main()
