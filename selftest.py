#!/usr/bin/env python3

import re

import activation
import generation
import grammar
import lexicon
import relations
import sequence
import syntax_tags


def main():
    corpus = [
        "많이 사용한다. 사용하면 편리하다. 할 수 있다. 보는 방법도 있다. "
        "황은 대표적인 가황제다. 황만 따로 본다. 돈과 대출과 금리가 함께 등장한다. "
        "돈과 가격을 비교한다. MBTS는 가황촉진제의 한 종류이다.",
        "사용하는 방법과 조절하는 방법을 비교한다. 많이 모을 수 있다. "
        "많아지면 처리하기 어렵다. 가격은 중요하다. 가격이 오르면 가격 변화를 확인한다. "
        "고무는 재료다. 고무가 필요하다. 고무 배합을 연구한다. "
        "가황은 중요한 과정이다. 가황은 고무 물성을 조절한다. "
        "자동차는 제품이다. 차는 이동수단이다. "
        "데이터는 기업의 의사결정에 사용된다. 고무 배합에서 가황은 중요한 과정이다.",
        "서로 연결된다. 서로의 관계를 본다. 모든 데이터를 본다. 주로 사용한다. "
        "주는 값을 확인한다. 가을에는 온도가 낮다. 가을의 변화와 온도의 변화를 본다. "
        "강도가 높다. 강도는 재료의 특성이다. 비가 온다. 비가 내린다. 힘을 쓰고 힘이 든다.",
    ]

    data = lexicon.build(corpus)
    lemmas = {entry["lemma"] for entry in data["entries"].values()}

    assert "많" not in lemmas, "많이에서 가짜 한 글자 명사 '많'이 생성됨"
    assert lexicon.resolve(data, "수") is None, "독립 문법 조각 '수'가 명사로 승격됨"

    for bad in ["서", "모", "가", "온", "강", "주"]:
        assert bad not in lemmas, f"긴 단어/활용형에서 가짜 한 글자 명사 생성: {bad}"

    checks = [
        ("많이", "많이", "adverb"),
        ("황은", "황", "noun"),
        ("돈과", "돈", "noun"),
        ("사용하는", "사용하다", "verb"),
        ("조절하는", "조절하다", "verb"),
        ("많아지면", "많아지다", "verb"),
        ("보는", "보다", "verb"),
        ("주로", "주로", "adverb"),
    ]
    for surface, lemma, pos in checks:
        item = lexicon.resolve(data, surface)
        assert item and item["lemma"] == lemma and item["pos"] == pos, (surface, item)

    for whole in ["가을", "온도", "강도"]:
        item = lexicon.resolve(data, whole)
        assert item and item["lemma"] == whole, (whole, item)

    price_entries = [e for e in data["entries"].values() if e["lemma"] == "가격"]
    rubber_entries = [e for e in data["entries"].values() if e["lemma"] == "고무"]
    assert len(price_entries) == 1 and price_entries[0]["pos"] == "noun", price_entries
    assert len(rubber_entries) == 1 and rubber_entries[0]["pos"] == "noun", rubber_entries

    compound = lexicon.resolve_many(data, "고무가황")
    assert [x["lemma"] for x in compound] == ["고무", "가황"], compound
    automobile = lexicon.resolve_many(data, "자동차")
    assert len(automobile) == 1 and automobile[0]["lemma"] == "자동차", automobile

    def resolver(surface):
        return lexicon.resolve_many(data, surface)

    tagged = syntax_tags.analyze_sentence(
        "가황은 고무 물성을 조절한다.",
        resolver=resolver,
    )
    assert tagged["패턴"] == "주어 → 관형어 → 목적어 → 서술어", tagged
    roles = [token["문장역할"] for token in tagged["토큰"]]
    assert roles == ["주어", "관형어", "목적어", "서술어"], tagged
    assert "품사/명사" in tagged["토큰"][0]["태그"], tagged
    assert "문장역할/주어" in tagged["토큰"][0]["태그"], tagged
    assert "문법형태/조사/은" in tagged["토큰"][0]["태그"], tagged

    syntax_graph = {}
    syntax_tags.accumulate_syntax(syntax_graph, tagged)
    assert syntax_graph["문법"]["패턴통계"][tagged["패턴"]] == 1, syntax_graph
    assert syntax_graph["문법"]["표제어역할"]["가황"]["주어"] == 1, syntax_graph

    question = syntax_tags.analyze_question("가황 어디")
    assert question["내용표현"] == "가황", question
    assert question["태그"] == ["질문의도/장소"], question
    question2 = syntax_tags.analyze_question("우주 무엇")
    assert question2["내용표현"] == "우주", question2
    assert question2["태그"] == ["질문의도/정의"], question2

    class Core:
        @staticmethod
        def tokenize(text):
            out = []
            for surface in grammar.raw_words(text):
                for entry in lexicon.resolve_many(data, surface):
                    if entry and entry.get("lemma"):
                        out.append(entry["lemma"])
            return out

        @staticmethod
        def split_sentences(text):
            return [x.strip() for x in re.split(r"(?<=[.!?。！？])\s+|\n+", text) if x.strip()]

    relation_text = (
        "데이터는 기업의 의사결정에 사용된다. "
        "고무 배합에서 가황은 중요한 과정이다. "
        "황은 대표적인 가황제다."
    )
    found = relations.extract_relations(Core, relation_text)
    triples = {(x["source"], x["relation"], x["target"]) for x in found}
    assert ("데이터", "used_for", "의사결정") in triples, triples
    assert ("가황", "is_a", "과정") in triples, triples
    assert ("황", "is_a", "가황제") in triples, triples
    assert not any(target in {"기업", "중요하다", "중요한"} for _s, _r, target in triples), triples

    graph = {}
    sequence.accumulate_sequence(graph, ["고무", "배합"])
    sequence.accumulate_sequence(graph, ["고무", "배합"])
    sequence.accumulate_sequence(graph, ["고무", "가황"])
    ranked = sequence.rank_next_words(graph, "고무", limit=5)
    assert ranked[0]["token"] == "배합" and ranked[0]["count"] == 2, ranked
    assert ranked[1]["token"] == "가황" and ranked[1]["count"] == 1, ranked

    sentence_graph = {
        "nodes": {
            "고무": {"pos": "noun"},
            "가황": {"pos": "noun"},
            "사용하다": {"pos": "verb"},
        },
        "문법": {
            "패턴통계": {"주어 → 부사어 → 서술어": 3}
        },
    }
    for _ in range(3):
        generation.accumulate_generation(
            sentence_graph,
            [("고무", "고무는"), ("가황", "가황에"), ("사용하다", "사용된다")],
        )
    generated = generation.generate_sequence_sentences(sentence_graph, "고무", limit=3)
    assert generated and generated[0]["text"] == "고무는 가황에 사용된다.", generated
    assert generated[0]["grammar_pattern"] == "주어 → 부사어 → 서술어", generated
    assert generated[0]["grammar_pattern_count"] == 3, generated

    incomplete = {"nodes": {"가황": {"pos": "noun"}, "중요하다": {"pos": "adjective"}}}
    generation.accumulate_generation(incomplete, [("가황", "가황은"), ("중요하다", "중요한")])
    assert generation.generate_sequence_sentences(incomplete, "가황") == [], incomplete

    collide = {
        "nodes": {
            "git": {"pos": "proper"}, "status": {"pos": "noun"},
            "상태": {"pos": "noun"}, "확인하다": {"pos": "verb"},
        }
    }
    generation.accumulate_generation(
        collide,
        [("git", "git"), ("status", "status를"), ("상태", "상태를"), ("확인하다", "확인한다")],
    )
    collision_rows = generation.generate_sequence_sentences(collide, "git", limit=5)
    assert not any("status를 상태를" in row["text"] for row in collision_rows), collision_rows

    earth = {
        "nodes": {"지구": {"pos": "noun"}, "태양": {"pos": "noun"}, "공전하다": {"pos": "verb"}}
    }
    generation.accumulate_generation(earth, [("지구", "지구의"), ("태양", "태양을"), ("공전하다", "공전한다")])
    generation.accumulate_generation(earth, [("지구", "지구는"), ("공전하다", "공전한다")])
    earth_rows = generation.generate_sequence_sentences(earth, "지구", limit=3)
    assert earth_rows and earth_rows[0]["text"].startswith("지구는 "), earth_rows

    semantic_graph = {
        "relations": {
            "x": {
                "source": "황", "relation": "used_for", "label": "사용처",
                "target": "가황", "confidence": 0.92,
                "evidence": ["황은 가황에 사용된다."],
            }
        }
    }
    semantic = generation.generate_semantic_sentences(semantic_graph, ["황"], limit=3)
    assert semantic and semantic[0]["text"] == "황은 가황에 사용된다.", semantic
    assert semantic[0]["grammar_pattern"] == "주어 → 부사어 → 서술어", semantic

    # GPT-2-inspired dynamic context activation. Equal sequence frequency must
    # be broken by support from the whole current context, not the last word alone.
    active_graph = {
        "edges": {
            "가황": {
                "촉진하다": {"score": 0.90},
                "가격": {"score": 0.05},
            },
            "반응": {},
        },
        "relations": {
            "r1": {
                "source": "가황", "relation": "affects", "label": "영향",
                "target": "반응", "confidence": 0.95,
            }
        },
        "generation": {
            "bigrams": {
                "가황": {"반응": 3},
                "반응": {"촉진하다": 1, "가격": 1},
            }
        },
    }
    state = activation.build_context_state(
        active_graph,
        seeds=["가황"],
        path=["가황", "반응"],
        steps=2,
    )
    assert activation.candidate_activation(state, "촉진하다") > activation.candidate_activation(state, "가격"), state
    reranked = activation.rerank_next_candidates(
        [
            {"token": "가격", "count": 1, "probability": 0.5},
            {"token": "촉진하다", "count": 1, "probability": 0.5},
        ],
        state,
    )
    assert reranked[0]["token"] == "촉진하다", reranked
    assert reranked[0]["activation"] > reranked[1]["activation"], reranked

    support, trace, _top = activation.path_activation_support(
        active_graph,
        "가황",
        ["가황", "반응", "촉진하다"],
    )
    assert support > 0 and len(trace) == 2, (support, trace)

    activation.patch_generation()
    activated_generated = generation.generate_sequence_sentences(sentence_graph, "고무", limit=3)
    assert activated_generated, activated_generated
    assert "activation_support" in activated_generated[0], activated_generated
    assert "동적 문맥 활성화" in activated_generated[0]["basis"], activated_generated

    print("WordMap v0.8.0 Korean grammar + dynamic context activation self-test: OK")


if __name__ == "__main__":
    main()
