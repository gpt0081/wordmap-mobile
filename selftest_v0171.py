#!/usr/bin/env python3

import tempfile
from pathlib import Path

import launch  # noqa: F401 - validates full runtime patch order
import core
import eval_manifest


def main():
    with tempfile.TemporaryDirectory() as td:
        vault = Path(td) / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        core.wordmap_dirs(vault)

        sync = core.default_corpus_sync(vault)
        assert sync["validation"]["train"] == 1500
        assert sync["validation"]["dev"] == 60
        assert sync["validation"]["test"] == 110

        info = core.default_corpus_status(vault)
        assert info["managed"] == 15, info
        assert info["installed"] == 15, info
        assert info["matching"] == 15, info

        docs = {row["name"]: row for row in core.corpus_list(vault)["documents"]}
        expected = {
            "01_core_facts.md": 200,
            "02_event_patterns.md": 280,
            "03_paraphrases.md": 180,
            "04_question_answer.md": 200,
            "05_dialogue_basic.md": 160,
            "06_dialogue_context.md": 120,
            "07_negative_contrast.md": 80,
            "08_cause_condition.md": 70,
            "09_polysemy_context.md": 70,
            "10_temporal_state.md": 50,
            "11_cross_topic.md": 90,
        }
        assert set(docs) == set(expected), sorted(docs)
        assert sum(docs[name]["sentences"] for name in expected) == 1500
        for name, count in expected.items():
            assert docs[name]["sentences"] == count, (name, docs[name]["sentences"], count)

        dev = eval_manifest.load(core, vault, "dev")
        test = eval_manifest.load(core, vault, "test")
        assert len(dev["items"]) == 60
        assert len(test["items"]) == 110
        assert test.get("frozen") is True
        assert not any(item.get("target") for item in test["items"])

        # Blank-line dialogue blocks are sessions even without metadata labels.
        session_map = core.dialogue_corpus_rebuild(vault)
        assert session_map["세션수"] == 100, session_map["세션수"]
        assert session_map["턴수"] == 280, session_map["턴수"]
        assert session_map["정책"]["빈줄_세션경계"] is True

        # User edits survive routine rebuild sync.
        original = core.corpus_get(vault, "01_core_facts.md")["content"]
        edited = original.rstrip() + "\n사용자가 추가한 보존 문장이다.\n"
        core.corpus_update(vault, "01_core_facts.md", edited)
        core.default_corpus_sync(vault)
        assert "사용자가 추가한 보존 문장이다." in core.corpus_get(vault, "01_core_facts.md")["content"]

        # Explicit restore returns the managed file to the bundled original.
        core.default_corpus_restore(vault)
        restored = core.corpus_get(vault, "01_core_facts.md")["content"]
        assert "사용자가 추가한 보존 문장이다." not in restored
        assert len(core.split_sentences(restored)) == 200

        # Deleting one bundled document suppresses auto-resurrection until restore.
        core.corpus_delete(vault, "11_cross_topic.md")
        core.default_corpus_sync(vault)
        assert not (core.wordmap_dirs(vault)["corpus"] / "11_cross_topic.md").exists()
        core.default_corpus_restore(vault)
        assert (core.wordmap_dirs(vault)["corpus"] / "11_cross_topic.md").exists()

        print("WordMap v0.17.1 bundled default Corpus self-test: OK")


if __name__ == "__main__":
    main()
