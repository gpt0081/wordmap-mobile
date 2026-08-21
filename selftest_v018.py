#!/usr/bin/env python3

import copy
import tempfile
from pathlib import Path

import launch  # noqa: F401 - validates full patch order
import activation
import associative_cascade
import core
import credit_learning
import priming


def synthetic_graph():
    nodes = {
        token: {"frequency": 5, "pos": "noun"}
        for token in [
            "생태계", "협력", "공생", "국제기구", "국가", "외교",
            "다람쥐", "겨울", "저장", "씨앗", "숲",
        ]
    }
    return {
        "version": 4,
        "nodes": nodes,
        "pairs": {},
        "edges": {
            "협력": {
                "공생": {"score": 0.86, "co": 6},
                "국제기구": {"score": 0.86, "co": 6},
            },
            "겨울": {"저장": {"score": 0.92, "co": 8}},
            "저장": {"씨앗": {"score": 0.88, "co": 7}},
        },
        "relations": {},
        "generation": {"bigrams": {}},
        "문맥지도": {
            "버전": "0.15.0",
            "문장수": 10,
            "단어문맥": {
                "공생": {
                    "관찰수": 5,
                    "문맥군": [{
                        "id": "공생#1",
                        "관찰수": 5,
                        "용어": {"생태계": 5, "협력": 4, "종": 3},
                        "예문": [],
                    }],
                },
                "국제기구": {
                    "관찰수": 5,
                    "문맥군": [{
                        "id": "국제기구#1",
                        "관찰수": 5,
                        "용어": {"국가": 5, "외교": 5, "조약": 3},
                        "예문": [],
                    }],
                },
            },
        },
    }


def main():
    graph = synthetic_graph()
    original = copy.deepcopy(graph)

    # Equal-strength associations must diverge when ContextMap says only one
    # belongs to the current semantic neighborhood.
    cascade = associative_cascade.build_cascade(
        graph,
        seeds=["생태계", "협력"],
        path=["생태계", "협력"],
        prime_scores={},
    )
    assert cascade["scores"].get("공생", 0) > 0
    assert cascade["scores"].get("국제기구", 0) > 0
    assert cascade["inhibition"].get("국제기구", 0) > cascade["inhibition"].get("공생", 0)
    assert cascade["thought_streams"][0]["끝점"] == "공생", cascade["thought_streams"]
    assert graph == original, "associative cascade must not mutate knowledge graph"

    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        core.wordmap_dirs(vault)
        core.save_graph(vault, graph)

        # Explicit priming is persistent across the session and feeds the next
        # activation calculation without becoming a knowledge fact.
        core.priming_prime(vault, "겨울 숲")
        status = core.priming_status(vault)
        before = {row["표제어"]: row["점화도"] for row in status["top"]}
        assert before.get("겨울", 0) > 0
        assert before.get("숲", 0) > 0

        data = priming._load(core, vault)
        ctx = priming._ACTIVE.set({
            "vault": str(vault),
            "session_id": data.get("session_id"),
            "turn": data.get("turn", 0),
            "scores": priming._scores(data),
            "rows": priming.top_rows(data),
        })
        try:
            state = activation.build_context_state(
                graph,
                seeds=["다람쥐"],
                path=["다람쥐"],
                steps=1,
            )
        finally:
            priming._ACTIVE.reset(ctx)

        assert state.get("_priming_scores", {}).get("겨울", 0) > 0
        assert state.get("_cascade_scores", {}).get("저장", 0) > 0
        assert state.get("_cascade_scores", {}).get("씨앗", 0) > 0
        paths = (state.get("_associative_cascade", {}) or {}).get("paths", {})
        assert int((paths.get("씨앗") or {}).get("wave", 0)) >= 2, paths.get("씨앗")
        assert (paths.get("씨앗") or {}).get("path") == ["겨울", "저장", "씨앗"]

        # Starting a new conversation clears both dialogue context and primes.
        core.dialogue_start(vault, "fresh-session")
        assert core.priming_status(vault)["active_count"] == 0

    # Credit Backprop keeps cognition origins separately so good/bad feedback
    # can learn whether priming or cascade paths were useful.
    assert credit_learning._origin_key("점화") == "점화"
    assert credit_learning._origin_key("연상 폭포") == "연상 폭포"
    assert credit_learning._origin_key("연상 이웃") == "연상 이웃"

    assert core.priming_version == "0.18.0"
    assert core.associative_cascade_version == "0.18.0"
    assert getattr(activation, "_associative_cascade_patched", False) is True
    print("WordMap v0.18.0 priming + associative cascade self-test: OK")


if __name__ == "__main__":
    main()
