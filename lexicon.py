from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import grammar

VERSION = "0.5.2"


def lexeme_id(pos, lemma):
    return f"{pos}:{lemma}"


def _new_entry(item):
    lid = lexeme_id(item["pos"], item["lemma"])
    return lid, {
        "id": lid,
        "lemma": item["lemma"],
        "pos": item["pos"],
        "pos_ko": grammar.POS_KO.get(item["pos"], item["pos"]),
        "confidence": 0.0,
        "forms_seen": Counter(),
        "particles_seen": Counter(),
        "reasons": Counter(),
    }


def _merge_entry(target, source):
    target["confidence"] = max(
        float(target.get("confidence", 0)),
        float(source.get("confidence", 0)),
    )
    target["forms_seen"].update(source.get("forms_seen", {}))
    target["particles_seen"].update(source.get("particles_seen", {}))
    target["reasons"].update(source.get("reasons", {}))


def build(texts):
    texts = list(texts)
    evidence = grammar.collect_evidence(texts)
    entries = {}
    surface_index = defaultdict(list)

    for text in texts:
        for surface in grammar.raw_words(text):
            for item in grammar.analyze_surface(surface, evidence):
                lid = lexeme_id(item["pos"], item["lemma"])
                if lid not in entries:
                    _lid, entries[lid] = _new_entry(item)

                entry = entries[lid]
                entry["confidence"] = max(
                    float(entry["confidence"]),
                    float(item.get("confidence", 0)),
                )
                entry["forms_seen"][surface] += 1
                if item.get("particle"):
                    entry["particles_seen"][item["particle"]] += 1
                entry["reasons"][item.get("reason", "unknown")] += 1

                if lid not in surface_index[surface]:
                    surface_index[surface].append(lid)

    # Absorb an unknown bare form into a corpus-proven POS with the same lemma.
    by_lemma = defaultdict(list)
    for lid, entry in entries.items():
        by_lemma[entry["lemma"]].append(lid)

    redirects = {}
    for lemma, lids in by_lemma.items():
        known = [lid for lid in lids if entries[lid]["pos"] != "unknown"]
        unknown = [lid for lid in lids if entries[lid]["pos"] == "unknown"]
        if not known or not unknown:
            continue

        known.sort(
            key=lambda lid: (
                float(entries[lid]["confidence"]),
                sum(entries[lid]["forms_seen"].values()),
            ),
            reverse=True,
        )
        winner = known[0]

        for loser in unknown:
            _merge_entry(entries[winner], entries[loser])
            redirects[loser] = winner
            del entries[loser]

    # A standalone root observed together with root+하다 is often a valid noun
    # as well (분석/분석하다, 사용/사용하다).
    for lid in list(entries):
        entry = entries.get(lid)
        if not entry or entry["pos"] != "unknown":
            continue

        lemma = entry["lemma"]
        predicate_ids = [
            lexeme_id("verb", lemma + "하다"),
            lexeme_id("adjective", lemma + "하다"),
        ]
        if not any(pid in entries for pid in predicate_ids):
            continue

        noun_id = lexeme_id("noun", lemma)
        if noun_id not in entries:
            entries[noun_id] = {
                "id": noun_id,
                "lemma": lemma,
                "pos": "noun",
                "pos_ko": grammar.POS_KO["noun"],
                "confidence": 0.76,
                "forms_seen": Counter(),
                "particles_seen": Counter(),
                "reasons": Counter(),
            }

        _merge_entry(entries[noun_id], entry)
        entries[noun_id]["reasons"]["standalone_hada_root"] += sum(
            entry["forms_seen"].values()
        )
        redirects[lid] = noun_id
        del entries[lid]

    clean_index = defaultdict(list)
    for surface, lids in surface_index.items():
        for lid in lids:
            final = redirects.get(lid, lid)
            if final in entries and final not in clean_index[surface]:
                clean_index[surface].append(final)

    for lid, entry in entries.items():
        lemma = entry["lemma"]
        if lid not in clean_index[lemma]:
            clean_index[lemma].append(lid)

    clean_entries = {}
    for lid, entry in sorted(entries.items()):
        clean_entries[lid] = {
            "id": lid,
            "lemma": entry["lemma"],
            "pos": entry["pos"],
            "pos_ko": entry["pos_ko"],
            "confidence": round(float(entry["confidence"]), 3),
            "forms_seen": dict(entry["forms_seen"].most_common()),
            "particles_seen": dict(entry["particles_seen"].most_common()),
            "reasons": dict(entry["reasons"].most_common()),
        }

    return {
        "version": VERSION,
        "entries": clean_entries,
        "surface_index": {k: v for k, v in sorted(clean_index.items())},
        "stats": {
            "lexemes": len(clean_entries),
            "surfaces": len(clean_index),
            "one_char_nouns": sum(
                1
                for entry in clean_entries.values()
                if entry["pos"] == "noun" and len(entry["lemma"]) == 1
            ),
            "unknown_lexemes": sum(
                1
                for entry in clean_entries.values()
                if entry["pos"] == "unknown"
            ),
        },
    }


def _rank(candidates):
    candidates.sort(
        key=lambda entry: (
            float(entry.get("confidence", 0)),
            sum(int(v) for v in entry.get("forms_seen", {}).values()),
            entry.get("pos") != "unknown",
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None


def resolve(data, surface):
    surface = surface.strip("._-/").lower()
    entries = data.get("entries", {})

    ids = data.get("surface_index", {}).get(surface, [])
    best = _rank([entries[x] for x in ids if x in entries])
    if best:
        return best

    best = _rank([
        entry
        for entry in entries.values()
        if entry.get("lemma") == surface
    ])
    if best:
        return best

    candidate = grammar.particle_candidate(surface)
    if candidate:
        base, _particle = candidate
        best = _rank([
            entry
            for entry in entries.values()
            if entry.get("lemma") == base and entry.get("pos") == "noun"
        ])
        if best:
            return best

    return None


def _compound_lemma_index(data):
    """Return safe components for query-time compound splitting.

    Only corpus-proven nouns/proper nouns with at least two characters are used.
    This deliberately refuses fragile one-syllable cuts such as 자동차 -> 자동+차.
    """
    out = {}
    for entry in data.get("entries", {}).values():
        lemma = str(entry.get("lemma", ""))
        if entry.get("pos") not in {"noun", "proper"}:
            continue
        if len(lemma) < 2:
            continue
        confidence = float(entry.get("confidence", 0))
        if confidence < 0.72:
            continue
        old = out.get(lemma)
        if old is None or confidence > float(old.get("confidence", 0)):
            out[lemma] = entry
    return out


def split_compound(data, surface, max_parts=4):
    """Split an unknown fused noun using known dictionary lemmas.

    Whole-word known lexemes always win. Unknown whole-word entries do not block
    a strong noun+noun analysis such as 고무가황 -> 고무 + 가황.
    """
    surface = surface.strip("._-/").lower()
    if len(surface) < 4:
        return []

    whole = resolve(data, surface)
    if whole and whole.get("pos") != "unknown":
        return [whole]

    lemma_index = _compound_lemma_index(data)
    n = len(surface)
    memo = {}

    def solve(i, parts_left):
        key = (i, parts_left)
        if key in memo:
            return memo[key]
        if i == n:
            return (0.0, [])
        if parts_left <= 0:
            return None

        best = None
        for j in range(i + 2, n + 1):
            piece = surface[i:j]
            entry = lemma_index.get(piece)
            if not entry:
                continue
            tail = solve(j, parts_left - 1)
            if tail is None:
                continue

            confidence = float(entry.get("confidence", 0))
            frequency = sum(
                int(v) for v in entry.get("forms_seen", {}).values()
            )
            piece_score = confidence * 2.0 + min(frequency, 8) * 0.05
            score = piece_score + tail[0]
            path = [entry] + tail[1]

            if best is None or score > best[0]:
                best = (score, path)

        memo[key] = best
        return best

    result = solve(0, max_parts)
    if not result:
        return []

    path = result[1]
    if len(path) < 2:
        return []
    if "".join(item["lemma"] for item in path) != surface:
        return []
    if min(float(item.get("confidence", 0)) for item in path) < 0.72:
        return []
    return path


def resolve_many(data, surface):
    """Resolve one surface into one lexeme or a safe compound sequence."""
    surface = surface.strip("._-/").lower()
    direct = resolve(data, surface)
    if direct and direct.get("pos") != "unknown":
        return [direct]

    compound = split_compound(data, surface)
    if compound:
        return compound

    return [direct] if direct else []


def by_lemma(data):
    out = defaultdict(list)
    for entry in data.get("entries", {}).values():
        out[entry.get("lemma")].append(entry)
    return dict(out)


def save(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": VERSION,
            "entries": {},
            "surface_index": {},
            "stats": {},
        }
