#!/usr/bin/env python3

import json
import tempfile
from pathlib import Path

import corpus_manager


class FakeCore:
    def __init__(self, root):
        self.root = Path(root)
        self.rebuild_calls = 0
        self.saved_graph = None

    def wordmap_dirs(self, vault):
        base = Path(vault) / "WordMap"
        meta = base / ".wordmap"
        corpus = meta / "Corpus"
        words = base / "Words"
        for path in (base, meta, corpus, words):
            path.mkdir(parents=True, exist_ok=True)
        return {"root": base, "meta": meta, "corpus": corpus, "words": words}

    @staticmethod
    def split_sentences(text):
        return [x.strip() for x in text.replace("?", ".").replace("!", ".").split(".") if x.strip()]

    @staticmethod
    def empty_graph():
        return {"version": 4, "nodes": {}, "pairs": {}, "edges": {}}

    def save_graph(self, vault, graph):
        self.saved_graph = graph
        path = self.wordmap_dirs(vault)["meta"] / "graph.json"
        path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def corpus_body(path):
        text = Path(path).read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end >= 0:
                rest = text.find("\n", end + 4)
                return text[rest + 1:] if rest >= 0 else ""
        return text

    def rebuild_wordmap(self, vault, window=4):
        self.rebuild_calls += 1
        docs = []
        for path in corpus_manager._corpus_files(self, vault):
            body = self.corpus_body(path)
            if body.strip():
                docs.append(path.name)
        return {"rebuilt": True, "documents": len(docs), "docs": docs}

    def status(self):
        return {"vault": str(self.root), "vaults": [str(self.root)]}


def main():
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "Vault"
        (vault / ".obsidian").mkdir(parents=True)
        core = FakeCore(vault)
        d = core.wordmap_dirs(vault)

        a = d["corpus"] / "a.md"
        b = d["corpus"] / "b.txt"
        a.write_text('---\ntype: corpus\nsource: "alpha"\n---\n\n다람쥐는 숲에서 씨앗을 먹는다.', encoding="utf-8")
        b.write_text('토끼는 들판에서 풀잎을 먹는다.', encoding="utf-8")
        (d["words"] / "old.md").write_text("old", encoding="utf-8")
        (d["meta"] / "lexicon.json").write_text("{}", encoding="utf-8")

        corpus_manager.apply(core)

        listing = core.corpus_list(vault)
        assert listing["total"] == 2, listing
        assert listing["enabled"] == 2, listing
        assert listing["dirty"] is False, listing

        item = core.corpus_get(vault, "a.md")
        assert item["source"] == "alpha", item
        assert "다람쥐" in item["content"], item

        core.corpus_set_enabled(vault, "b.txt", False)
        assert core.corpus_body(b) == "", "disabled corpus must not enter rebuild"
        assert core.corpus_body(a).strip().startswith("다람쥐"), "enabled corpus disappeared"
        listing = core.corpus_list(vault)
        assert listing["enabled"] == 1 and listing["disabled"] == 1 and listing["dirty"], listing

        result = core.rebuild_wordmap(vault)
        assert result["corpus_active_documents"] == 1, result
        assert result["corpus_disabled_documents"] == 1, result
        assert core.corpus_list(vault)["dirty"] is False

        core.corpus_update(vault, "a.md", "다람쥐는 숲에서 열매를 먹는다.\n다람쥐는 씨앗도 먹는다.")
        raw = a.read_text(encoding="utf-8")
        assert raw.startswith('---\ntype: corpus\nsource: "alpha"'), raw
        assert "열매" in core.corpus_get(vault, "a.md")["content"]
        assert core.corpus_list(vault)["dirty"] is True

        try:
            core.corpus_get(vault, "../outside.txt")
            raise AssertionError("path traversal was accepted")
        except ValueError:
            pass

        core.corpus_delete(vault, "b.txt")
        assert not b.exists()
        assert core.corpus_list(vault)["total"] == 1

        core.corpus_set_enabled(vault, "a.md", False)
        result = core.rebuild_wordmap(vault)
        assert result["documents"] == 0, result
        assert result["total_nodes"] == 0, result
        assert not (d["words"] / "old.md").exists(), "generated notes were not cleared"
        assert not (d["meta"] / "lexicon.json").exists(), "lexicon was not cleared"
        assert core.corpus_list(vault)["dirty"] is False

        core.corpus_set_enabled(vault, "a.md", True)
        deleted = core.corpus_delete_all(vault)
        assert deleted["deleted_count"] == 1, deleted
        assert core.corpus_list(vault)["total"] == 0
        assert core.corpus_list(vault)["dirty"] is False

    print("WordMap v0.13.0 corpus manager self-test: OK")


if __name__ == "__main__":
    main()
