from __future__ import annotations

from datetime import datetime
from pathlib import Path

import grammar
import lexicon as lexicon_mod

VERSION = "0.10.0"

_ACTIVE = {
    "version": VERSION,
    "entries": {},
    "surface_index": {},
    "stats": {},
}
_TOKEN_STOPWORDS = set()
_QUERY_LEMMAS = []


def _lexicon_path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / "lexicon.json"


def _rebuild_query_index():
    global _QUERY_LEMMAS
    rows = []
    for entry in _ACTIVE.get("entries", {}).values():
        lemma = str(entry.get("lemma", ""))
        pos = entry.get("pos")
        confidence = float(entry.get("confidence", 0))
        if not lemma or pos not in {"noun", "proper"}:
            continue
        if len(lemma) == 1 and confidence < 0.86:
            continue
        if len(lemma) >= 2 and confidence < 0.72:
            continue
        rows.append(entry)
    rows.sort(key=lambda x: (-len(str(x.get("lemma", ""))), -float(x.get("confidence", 0))))
    _QUERY_LEMMAS = rows


def _set(data):
    global _ACTIVE
    _ACTIVE = data or {
        "version": VERSION,
        "entries": {},
        "surface_index": {},
        "stats": {},
    }
    _rebuild_query_index()


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


def _accepted(entry, surface):
    """Graph-token acceptance: hub-like grammar words may be filtered here."""
    if not entry or not entry.get("lemma"):
        return False
    lemma = entry["lemma"]
    if surface in _TOKEN_STOPWORDS or lemma in _TOKEN_STOPWORDS:
        return False
    if len(lemma) == 1 and entry.get("pos") not in {"noun", "proper"}:
        return False
    return True


def resolve_surface(surface):
    """Resolve a surface for WordMap graph construction/search."""
    return [
        entry
        for entry in lexicon_mod.resolve_many(_ACTIVE, surface)
        if _accepted(entry, surface)
    ]


def resolve_surface_for_grammar(surface):
    """Resolve a surface for syntax without applying graph STOPWORDS.

    Grammar needs words such as 있다/된다/한다/수 even when they are poor graph
    nodes. Grammar-only fallback entries never force those words into WordMap.
    """
    surface = surface.strip("._-/").lower()
    candidates = list(lexicon_mod.resolve_many(_ACTIVE, surface) or [])
    fallback = grammar.syntax_fallback(surface)

    # A grammar-specific predicate/coplanar analysis is more trustworthy than
    # a preserved unknown/noun analysis of the exact inflected surface.
    if fallback:
        fb = fallback[0]
        if (
            not candidates
            or surface in grammar.COMMON_FORMS
            or surface.endswith("는다")
            or surface.endswith(("이다", "입니다", "였다", "이었다"))
            or all(x.get("pos") == "unknown" for x in candidates)
        ):
            candidates = fallback + candidates

    unique = {}
    for entry in candidates:
        if not entry or not entry.get("lemma"):
            continue
        key = (entry.get("pos"), entry.get("lemma"))
        old = unique.get(key)
        if old is None or float(entry.get("confidence", 0)) > float(old.get("confidence", 0)):
            unique[key] = entry

    rows = list(unique.values())
    rows.sort(
        key=lambda x: (
            float(x.get("confidence", 0)),
            x.get("pos") != "unknown",
        ),
        reverse=True,
    )
    return rows[:4]


def _query_fallback_entries(surface):
    """Recover known pieces from an otherwise OOV query surface.

    This is query-only and deliberately does not mutate the Lexicon. It allows
    '숲속 생태계' to retain the known concept '숲' even if '숲속' itself has not
    appeared in Corpus yet.
    """
    surface = surface.strip("._-/").lower()
    if not surface:
        return []

    hits = []
    occupied = set()
    for entry in _QUERY_LEMMAS:
        lemma = str(entry.get("lemma", ""))
        if not lemma or lemma == surface or lemma not in surface:
            continue
        start = surface.find(lemma)
        span = set(range(start, start + len(lemma)))
        if span & occupied:
            continue
        # One-character hints are accepted only at a word boundary.
        if len(lemma) == 1 and not (surface.startswith(lemma) or surface.endswith(lemma)):
            continue
        hits.append(entry)
        occupied |= span
        if len(hits) >= 3:
            break

    hits.sort(key=lambda x: surface.find(str(x.get("lemma", ""))))
    return hits


def resolve_query_surface(surface):
    rows = resolve_surface(surface)
    if rows:
        return rows, False
    return _query_fallback_entries(surface), True


def tokenize(text):
    out = []
    for surface in grammar.raw_words(text):
        for entry in resolve_surface(surface):
            out.append(entry["lemma"])
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
        "token_layers": {
            "graph": "불용어 제거 + 표제어",
            "grammar": "불용어 보존 + 표제어/문법형 복구",
        },
    }
    core.save_graph(vault, graph)
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
            "token_layers": "graph+grammar 분리",
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

        analyses = []
        normalized = []
        for surface in grammar.raw_words(question):
            entries, fallback = resolve_query_surface(surface)
            if not entries:
                continue
            lemmas = []
            for entry in entries:
                lemma = entry.get("lemma")
                if lemma and lemma not in lemmas:
                    lemmas.append(lemma)
                    normalized.append(lemma)
            analyses.append({
                "surface": surface,
                "lemmas": lemmas,
                "compound": len(lemmas) > 1,
                "query_fallback": bool(fallback),
            })

        rewritten = " ".join(normalized).strip() or question
        result = original_ask(
            vault,
            rewritten,
            limit=limit,
            depth=depth,
        )
        result["question"] = question
        result["normalized_question"] = rewritten
        result["surface_analysis"] = analyses

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
            "language_version": VERSION,
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
