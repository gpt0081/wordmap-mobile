#!/usr/bin/env python3

import re

import grammar
import lexicon
import relations


def main():
    # Regression sentences mirror the real WordMap corpus patterns that exposed
    # v0.5.0 failures. The test itself remains Vault-independent so update.sh
    # can run safely on any installation.
    corpus = [
        "많이 사용한다. 사용하면 편리하다. 할 수 있다. 보는 방법도 있다. "
        "황은 대표적인 가황제다. 돈과 대출과 금리가 함께 등장한다. "
        "MBTS는 가황촉진제의 한 종류이다.",
        "사용하는 방법과 조절하는 방법을 비교한다. "
        "많아지면 처리하기 어렵다. "
        "가격은 중요하다. 가격이 오르면 가격 변화를 확인한다. "
        "고무는 재료다. 고무가 필요하다. "
        "데이터는 기업의 의사결정에 사용된다. "
        "고무 배합에서 가황은 중요한 과정이다.",
    ]

    data = lexicon.build(corpus)
    lemmas = {
        entry["lemma"]
        for entry in data["entries"].values()
    }

    assert "많" not in lemmas, (
        "많이에서 가짜 한 글자 명사 '많'이 생성됨"
    )
    assert lexicon.resolve(data, "수") is None, (
        "독립 문법 조각 '수'가 명사로 승격됨"
    )

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
        assert (
            item
            and item["lemma"] == lemma
            and item["pos"] == pos
        ), (surface, item)

    # Bare and particle-marked forms must collapse to one dictionary lexeme.
    price_entries = [
        entry
        for entry in data["entries"].values()
        if entry["lemma"] == "가격"
    ]
    rubber_entries = [
        entry
        for entry in data["entries"].values()
        if entry["lemma"] == "고무"
    ]
    assert (
        len(price_entries) == 1
        and price_entries[0]["pos"] == "noun"
    ), price_entries
    assert (
        len(rubber_entries) == 1
        and rubber_entries[0]["pos"] == "noun"
    ), rubber_entries

    class Core:
        @staticmethod
        def tokenize(text):
            out = []
            for surface in grammar.raw_words(text):
                entry = lexicon.resolve(data, surface)
                if entry and entry.get("lemma"):
                    out.append(entry["lemma"])
            return out

        @staticmethod
        def split_sentences(text):
            return [
                x.strip()
                for x in re.split(
                    r"(?<=[.!?。！？])\s+|\n+",
                    text,
                )
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

    assert (
        "데이터",
        "used_for",
        "의사결정",
    ) in triples, triples
    assert (
        "가황",
        "is_a",
        "과정",
    ) in triples, triples
    assert (
        "황",
        "is_a",
        "가황제",
    ) in triples, triples

    # v0.5.0 incorrectly selected 기업 and 중요한 as semantic targets.
    assert not any(
        target in {"기업", "중요하다", "중요한"}
        for _source, _relation, target in triples
    ), triples

    print("WordMap language/relations self-test: OK")


if __name__ == "__main__":
    main()
