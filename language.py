from __future__ import annotations

from datetime import datetime
from pathlib import Path

import grammar
import lexicon as lexicon_mod

VERSION = "0.5.1"

_ACTIVE = {
    "version": VERSION,
    "entries": {},
    "surface_index": {},
    "stats": {},
}
_TOKEN_STOPWORDS = set()


def _lexicon_path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / "lexicon.json"


def _set(data):
    global _ACTIVE
    _ACTIVE = data or {
        "version": VERSION,
        "entries": {},
        "surface_index": {},
        "stats": {},
    }


def _load(core, vault):
    data = lexicon_mod.load(_lexicon_path(core, vault))
    _set(data)
    return data


def _texts(core, vault):
    d = core.wordmap_dirs(vault)
    files = sorted([
        *d["corpus"].glob("*.md"),
        *d["corpus"].glob("*.txt"),
    ])
    return [(path, core.corpus_body(path)) for path in files]


def tokenize(text):
    out = []
    for surface in grammar.raw_words(text):
        entry = lexicon_mod.resolve(_ACTIVE, surface)
        if not entry or not entry.get("lemma"):
            continue

        lemma = entry["lemma"]

        # v0.5.0 accidentally bypassed the cleaner's stopword set after
        # replacing core.tokenize. Restore the exact same language filter here.
        if surface in _TOKEN_STOPWORDS or lemma in _TOKEN_STOPWORDS:
            continue

        # Unsupported one-syllable grammatical fragments must not become graph
        # nodes. Corpus-supported nouns such as 황/돈 still survive.
        if len(lemma) == 1 and entry.get("pos") not in {"noun", "proper"}:
            continue

        out.append(lemma)

    return out


def _annotate_graph(core, vault, data):
    graph = core.load_graph(vault)
    lemma_map = lexicon_mod.by_lemma(data)

    for token, meta in graph.get("nodes", {}).items():
        candidates = sorted(
            lemma_map.get(token, []),
            key=lambda x: float(x.get("confidence", 0)),
            reverse=True,
        )
        if not candidates:
            continue

        best = candidates[0]
        meta["pos"] = best.get("pos", "unknown")
        meta["pos_ko"] = best.get("pos_ko", "미분류")
        meta["lexicon_confidence"] = best.get("confidence", 0)
        meta["forms_seen"] = best.get("forms_seen", {})

    graph["language"] = {
        "version": VERSION,
        "lexicon_stats": data.get("stats", {}),
    }
    core.save_graph(vault, graph)

    # Re-write generated notes after POS/form metadata is attached.
    core.save_notes(vault, graph)
    return graph


def make_rebuild(core, original_rebuild):
    def rebuild(vault, window=4):
        texts = [
            text
            for _path, text in _texts(core, vault)
            if text.strip()
        ]
        if not texts:
            raise ValueError("내용이 있는 Corpus 말뭉치가 없습니다.")

        data = lexicon_mod.build(texts)
        _set(data)
        lexicon_mod.save(_lexicon_path(core, vault), data)

        result = original_rebuild(vault, window=window)
        graph = _annotate_graph(core, vault, data)
        stats = data.get("stats", {})

        result.update({
            "lexicon_version": VERSION,
            "lexemes": int(stats.get("lexemes", 0)),
            "surface_forms": int(stats.get("surfaces", 0)),
            "one_char_nouns": int(stats.get("one_char_nouns", 0)),
            "unknown_lexemes": int(stats.get("unknown_lexemes", 0)),
            "active_nodes": len(graph.get("edges", {})),
        })
        return result

    return rebuild


def make_ingest(core):
    def ingest(vault, text, source="mobile", window=4):
        if not text.strip():
            raise ValueError("말뭉치가 비어 있습니다.")

        d = core.wordmap_dirs(vault)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        source_name = source or "mobile"
        corpus_path = d["corpus"] / f"{stamp}_{core.safe(source_name)}.md"
        safe_source = source_name.replace('"', "'")
        corpus_path.write_text(
            f'---\ntype: corpus\nsource: "{safe_source}"\n---\n\n{text}',
            encoding="utf-8",
        )

        # New corpus can change grammatical evidence, so rebuild the lexicon
        # and graph transactionally from preserved source documents.
        result = core.rebuild_wordmap(vault, window=window)
        result.update({
            "source": source_name,
            "corpus_note": str(corpus_path),
            "ingest_mode": "save_then_full_rebuild",
        })
        return result

    return ingest


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        _load(core, vault)
        result = original_ask(
            vault,
            question,
            limit=limit,
            depth=depth,
        )

        # Do not turn a rejected fragment into fuzzy graph search.
        if not result.get("query_tokens"):
            result["seed_tokens"] = []
            result["results"] = []
            result["warning"] = (
                "유효한 표제어를 찾지 못했습니다. "
                "문법적으로 불완전한 조각은 검색하지 않습니다."
            )
        return result

    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out

        data = _load(core, Path(vault))
        stats = data.get("stats", {})
        out.update({
            "lexicon_version": data.get("version"),
            "lexemes": int(stats.get("lexemes", 0)),
            "surface_forms": int(stats.get("surfaces", 0)),
            "one_char_nouns": int(stats.get("one_char_nouns", 0)),
            "unknown_lexemes": int(stats.get("unknown_lexemes", 0)),
        })
        return out

    return status


def apply(core):
    global _TOKEN_STOPWORDS

    original_rebuild = core.rebuild_wordmap
    original_ask = core.ask
    original_status = core.status

    # cleaning.apply(core) runs before this module, so this captures both the
    # original core stopwords and cleaning.py's extra stopwords.
    _TOKEN_STOPWORDS = set(getattr(core, "STOPWORDS", set()))

    core.tokenize = tokenize
    core.rebuild_wordmap = make_rebuild(core, original_rebuild)
    core.ingest = make_ingest(core)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)

    vault = core.current_vault()
    if vault:
        _load(core, vault)

    return core
