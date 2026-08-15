#!/usr/bin/env python3

import re

import generation
import grammar
import lexicon
import relations
import sequence


def main():
    corpus = [
        "많이 사용한다. 사용하면 편리하다. 할 수 있다. 보는 방법도 있다. "
        "황은 대표적인 가황제다. 돈과 대출과 금리가 함께 등장한다. "
        "MBTS는 가황촉진제의 한 종류이다.",
        "사용하는 방법과 조절하는 방법을 비교한다. "
        "많아지면 처리하기 어렵다. "
        "가격은 중요하다. 가격이 오르면 가격 변화를 확인한다. "
        "고무는 재료다. 고무가 필요하다. 고무 배합을 연구한다. "
        "가황은 중요한 과정이다. "
        "자동차는 제품이다. 차는 이동수단이다. "
        "데이터는 기업의 의사결정에 사용된다. "
        "고무 배합에서 가황은 중요한 과정이다.",
    ]

    data = lexicon.build(corpus)
    lemmas = {
        entry["lemma"]
        for entry in data["entries"].values()
    }

    assert "많" not in lemmas, "많이에서 가짜 한 글자 명사 '많'이 생성됨"
    assert lexicon.resolve(data, "수") is None, "독립 문법 조각 '수'가 명사로 승격됨"

    checks = [
        ("많이", "많이", "adverb"),
        ("황은", "황", "noun"),
        ("돈과", "돈", "noun"),
        ("사용하는", "사용하다", "verb"),
        ("조절하는", "조절하다", "verb"),
        ("많아지면", "많아지다", "verb"),
        ("보는", "보다", "verb"),
    ]
    for surface, lemma, pos in checks:
        item = lexicon.resolve(data, surface)
        assert item and item["lemma"] == lemma and item["pos"] == pos, (surface, item)

    price_entries = [
        entry for entry in data["entries"].values()
        if entry["lemma"] == "가격"
    ]
    rubber_entries = [
        entry for entry in data["entries"].values()
        if entry["lemma"] == "고무"
    ]
    assert len(price_entries) == 1 and price_entries[0]["pos"] == "noun", price_entries
    assert len(rubber_entries) == 1 and rubber_entries[0]["pos"] == "noun", rubber_entries

    compound = lexicon.resolve_many(data, "고무가황")
    assert [x["lemma"] for x in compound] == ["고무", "가황"], compound

    automobile = lexicon.resolve_many(data, "자동차")
    assert len(automobile) == 1 and automobile[0]["lemma"] == "자동차", automobile

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
            return [
                x.strip()
                for x in re.split(r"(?<=[.!?。！？])\s+|\n+", text)
                if x.strip()
            ]

    relation_text = (
        "데이터는 기업의 의사결정에 사용된다. "
        "고무 배합에서 가황은 중요한 과정이다. "
        "황은 대표적인 가황제다."
    )
    found = relations.extract_relations(Core, relation_text)
    triples = {
        (item["source"], item["relation"], item["target"])
        for item in found
    }

    assert ("데이터", "used_for", "의사결정") in triples, triples
    assert ("가황", "is_a", "과정") in triples, triples
    assert ("황", "is_a", "가황제") in triples, triples
    assert not any(
        target in {"기업", "중요하다", "중요한"}
        for _source, _relation, target in triples
    ), triples

    # Ordered next-word statistics.
    graph = {}
    sequence.accumulate_sequence(graph, ["고무", "배합"])
    sequence.accumulate_sequence(graph, ["고무", "배합"])
    sequence.accumulate_sequence(graph, ["고무", "가황"])
    ranked = sequence.rank_next_words(graph, "고무", limit=5)
    assert ranked[0]["token"] == "배합" and ranked[0]["count"] == 2, ranked
    assert ranked[1]["token"] == "가황" and ranked[1]["count"] == 1, ranked
    assert ranked[0]["probability"] > ranked[1]["probability"], ranked

    # Corpus-grounded surface realization. The generator must recover the
    # observed Korean forms rather than output bare lemmas such as
    # '고무 가황 사용하다'.
    sentence_graph = {}
    for _ in range(3):
        sequence.accumulate_sequence(
            sentence_graph,
            ["고무", "가황", "사용하다"],
        )
        generation.accumulate_generation(
            sentence_graph,
            [
                ("고무", "고무는"),
                ("가황", "가황에"),
                ("사용하다", "사용된다"),
            ],
        )

    generated = generation.generate_sequence_sentences(
        sentence_graph,
        "고무",
        limit=3,
    )
    assert generated, generated
    assert generated[0]["text"] == "고무는 가황에 사용된다.", generated

    semantic_graph = {
        "relations": {
            "x": {
                "source": "황",
                "relation": "used_for",
                "label": "사용처",
                "target": "가황",
                "confidence": 0.92,
                "evidence": ["황은 가황에 사용된다."],
            }
        }
    }
    semantic = generation.generate_semantic_sentences(
        semantic_graph,
        ["황"],
        limit=3,
    )
    assert semantic and semantic[0]["text"] == "황은 가황에 사용된다.", semantic

    print("WordMap v0.6.0 language/relations/sequence/generation self-test: OK")


if __name__ == "__main__":
    main()
