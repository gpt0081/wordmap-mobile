#!/usr/bin/env python3

import grammar
import lexicon


def main():
    corpus = [
        "많이 사용한다. 사용하면 편리하다. "
        "황은 가황에 사용된다. 황을 넣는다. 황과 촉진제를 배합한다. "
        "MBTS는 가황촉진제의 한 종류이다."
    ]

    data = lexicon.build(corpus)
    lemmas = {entry["lemma"] for entry in data["entries"].values()}

    assert "많" not in lemmas, "많이에서 가짜 한 글자 명사 '많'이 생성됨"

    many = lexicon.resolve(data, "많이")
    assert many and many["lemma"] == "많이" and many["pos"] == "adverb"

    sulfur = lexicon.resolve(data, "황은")
    assert sulfur and sulfur["lemma"] == "황" and sulfur["pos"] == "noun"

    use = lexicon.resolve(data, "사용한다")
    assert use and use["lemma"] == "사용하다" and use["pos"] == "verb"

    mbts = lexicon.resolve(data, "mbts는")
    assert mbts and mbts["lemma"] == "mbts"

    print("WordMap language self-test: OK")


if __name__ == "__main__":
    main()
