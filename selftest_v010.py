#!/usr/bin/env python3

import activation
import corpus_filter
import generation
import generation_tokens
import grammar
import language
import lexicon
import relation_guard
import syntax_tags
import wordmap_gpt2


def main():
    # 1) Textbook/document scaffolding is removed only from the analysis view.
    raw = """
# 본문
고무는 탄성이 있는 재료다.
## 연습문제
난이도: 쉬움
정답
본문은 문서의 중심 내용이라는 뜻으로도 쓸 수 있다.
"""
    cleaned = corpus_filter.clean_text(raw)
    assert "# 본문" not in cleaned, cleaned
    assert "연습문제" not in cleaned, cleaned
    assert "난이도: 쉬움" not in cleaned, cleaned
    assert "\n정답\n" not in "\n" + cleaned + "\n", cleaned
    assert "본문은 문서의 중심 내용" in cleaned, cleaned

    # 2) Build a small lexicon containing the exact failure families seen in
    # the larger Vault: stopword predicates, -는다, copula, one-char noun.
    corpus = [
        "숲은 생태계다. 숲이 있다. "
        "다람쥐는 숲에서 씨앗과 열매를 먹는다. "
        "생태계에서는 죽음도 물질 순환의 일부가 된다. "
        "숲은 다양한 생물이 함께 살아가는 공간이다. "
        "할 수 있다. 고무는 재료다. 가황은 고무 물성을 조절한다."
    ]
    data = lexicon.build(corpus)
    language._TOKEN_STOPWORDS = {"있다", "된다", "되다", "한다", "하다", "수", "것"}
    language._set(data)

    evidence = grammar.collect_evidence(corpus)
    eating = grammar.analyze_surface("먹는다", evidence)
    assert eating and eating[0]["lemma"] == "먹다" and eating[0]["pos"] == "verb", eating
    assert grammar.analyze_surface("된다", evidence)[0]["lemma"] == "되다"
    assert grammar.analyze_surface("한다", evidence)[0]["lemma"] == "하다"

    # Graph resolver may discard a hub-like grammar word, grammar resolver must not.
    assert language.resolve_surface("있다") == [], language.resolve_surface("있다")
    grammar_exists = language.resolve_surface_for_grammar("있다")
    assert grammar_exists and grammar_exists[0]["lemma"] == "있다", grammar_exists
    grammar_dep = language.resolve_surface_for_grammar("수")
    assert grammar_dep and grammar_dep[0]["lemma"] == "수", grammar_dep

    # 3) Syntax should recover predicates and copular endings.
    tagged = syntax_tags.analyze_sentence("다람쥐는 숲에서 씨앗과 열매를 먹는다.")
    assert tagged["토큰"][-1]["표제어"] == "먹다", tagged
    assert tagged["토큰"][-1]["문장역할"] == "서술어", tagged

    copula = syntax_tags.analyze_sentence("숲은 공간이다.")
    assert copula["토큰"][-1]["표제어"] == "공간", copula
    assert copula["토큰"][-1]["문장역할"] == "서술어", copula
    assert copula["토큰"][-1]["문법형태"] == "종결어미", copula

    dependent = syntax_tags.analyze_sentence("할 수 있다.")
    lemmas = [x["표제어"] for x in dependent["토큰"]]
    assert "수" in lemmas and "있다" in lemmas, dependent

    # 4) Raw and normalized patterns are both preserved. Generation-facing
    # patterns collapse fragile surface distinctions.
    structured = syntax_tags.analyze_sentence("가황은 고무 물성을 조절한다.")
    assert structured["패턴"] == "주어 → 관형어 → 목적어 → 서술어", structured
    assert structured["정규패턴"] == "주어 → 수식어 → 목적어 → 서술어", structured
    syntax_graph = {}
    syntax_tags.accumulate_syntax(syntax_graph, structured)
    assert syntax_graph["문법"]["정규패턴통계"][structured["정규패턴"]] == 1

    # 5) OOV query surfaces retain known concepts instead of disappearing.
    recovered, used_fallback = language.resolve_query_surface("숲속")
    assert used_fallback, recovered
    assert any(x.get("lemma") == "숲" for x in recovered), recovered

    # 6) Generation sequence keeps grammar words even if graph tokenization removes them.
    segs = generation_tokens.surface_segments("할 수 있다.")
    assert segs, segs
    seq_lemmas = [lemma for lemma, _surface in segs[0]]
    assert seq_lemmas == ["하다", "수", "있다"], seq_lemmas

    # 7) Metalinguistic statements are not world-knowledge relation evidence.
    assert relation_guard.is_metalinguistic("고무라는 명사를 포함한다.")
    assert not relation_guard.is_metalinguistic("고무는 탄성을 가진 재료이다.")

    # 8) Candidate space is no longer n-gram-only. '협력' never follows
    # '생태계' in the bigram row below, but strong context/relation support
    # must still make it a candidate.
    candidate_graph = {
        "nodes": {
            "생태계": {"pos": "noun"},
            "경쟁": {"pos": "noun"},
            "협력": {"pos": "noun"},
        },
        "edges": {
            "생태계": {
                "협력": {"score": 0.90, "co": 3.0},
            }
        },
        "relations": {
            "r": {
                "source": "생태계", "relation": "related_to", "label": "관련",
                "target": "협력", "confidence": 0.95,
            }
        },
        "generation": {
            "bigrams": {"생태계": {"경쟁": 4}},
            "trigrams": {},
            "forms": {
                "생태계": {"생태계는": 2},
                "경쟁": {"경쟁이": 2},
                "협력": {"협력이": 2},
            },
            "start_surfaces": {"생태계": {"생태계는": 2}},
            "pair_surfaces": {},
            "trigram_surfaces": {},
        },
    }
    state = activation.build_context_state(
        candidate_graph,
        seeds=["생태계"],
        path=["생태계"],
        steps=2,
    )
    pool = wordmap_gpt2._candidate_pool(candidate_graph, ["생태계"], state)
    by_token = {row["token"]: row for row in pool}
    assert "경쟁" in by_token, pool
    assert "협력" in by_token, pool
    assert "말뭉치 순서" not in by_token["협력"].get("origins", []), by_token["협력"]
    assert any(x.startswith("의미관계/") or x == "문맥 활성" or x == "연상 이웃" for x in by_token["협력"]["origins"]), by_token["협력"]

    print("WordMap v0.10.0 language-representation self-test: OK")


if __name__ == "__main__":
    main()
