#!/usr/bin/env python3

import re
import tempfile
from pathlib import Path

import corpus_integrity
import corpus_roles
import corpus_v1
import corpus_v1_quality
import temporal_event


class StubCore:
    def wordmap_dirs(self, vault):
        root = Path(vault) / "WordMap"
        meta = root / ".wordmap"
        corpus = meta / "Corpus"
        words = root / "Words"
        for p in (root, meta, corpus, words):
            p.mkdir(parents=True, exist_ok=True)
        return {"root": root, "meta": meta, "corpus": corpus, "words": words}

    def split_sentences(self, text):
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        return [x.strip() for x in re.split(r"(?<=[.!?。！？])\s+|\n+", normalized) if x.strip()]

    clean_training_body = staticmethod(corpus_roles.clean_training_body)


def main():
    corpus_v1_quality.apply(corpus_v1)
    generated = corpus_v1.validate_generated()
    assert generated["train_sentences"] == 1500
    assert generated["dev"] == 60
    assert generated["test"] == 110

    basic = corpus_v1.gen_dialogue_basic()
    context = corpus_v1.gen_dialogue_context()
    assert sum(1 for x in basic if x and not x.startswith("@@")) == 160
    assert sum(1 for x in context if x and not x.startswith("@@")) == 120
    cleaned = corpus_roles.clean_training_body("@@dialogue D1 START\n사용자: 민수는 어디 있어?\n답변: 민수는 부엌에 있다.\n@@dialogue D1 END")
    assert "@@dialogue" not in cleaned and "사용자:" not in cleaned and "답변:" not in cleaned
    assert "민수는 어디 있어?" in cleaned

    assert temporal_event._times("아침에 민수의 사과는 식탁 위에 있다.") == ["아침"]
    assert temporal_event._owners("현재 민수의 사과는 냉장고 안에 있다.") == ["민수"]

    with tempfile.TemporaryDirectory() as tmp:
        core = StubCore()
        vault = Path(tmp)
        installed = corpus_v1.install(core, vault, rebuild=False)
        assert installed["train_sentences"] == 1500
        corpus = core.wordmap_dirs(vault)["corpus"]
        assert corpus_roles.role_from_path(corpus / "01_core_facts.md") == "train"
        assert corpus_roles.role_from_path(corpus / "90_dev_questions.md") == "dev"
        assert corpus_roles.role_from_path(corpus / "91_test_questions.md") == "test"

        report = corpus_integrity.run(core, vault)
        assert report["counts"] == {"train": 1500, "dev": 60, "test": 110}, report["counts"]
        assert report["exact"]["train_dev"] == 0
        assert report["exact"]["train_test"] == 0
        assert report["exact"]["dev_test"] == 0
        assert report["temporal_without_context"]["count"] == 0, report["temporal_without_context"]
        assert report["manifest_warnings"]["count"] == 0

    print("WordMap v0.16.0 Corpus v1 experiment harness self-test: OK")


if __name__ == "__main__":
    main()
