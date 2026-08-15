from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import grammar

VERSION = "0.5.1"


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

    # If the corpus proves a lemma as a real POS, absorb an unknown bare form
    # of the exact same spelling. This removes duplicate lexemes such as
    # noun:고무 + unknown:고무 and noun:가격 + unknown:가격.
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
    # as well (분석/분석하다, 사용/사용하다). Promote only roots that actually
    # occurred in the corpus, rather than maintaining a domain word list.
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

    # Rewrite the index after merges and also index the lemma itself. The bare
    # dictionary form can then resolve even if only an inflected form occurred.
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

    # Resolve a dictionary lemma even if this exact bare surface did not occur.
    best = _rank([
        entry
        for entry in entries.values()
        if entry.get("lemma") == surface
    ])
    if best:
        return best

    # Resolve an unseen case-marked form from a noun lemma already proven by
    # the corpus. This improves both user queries and semantic head extraction.
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
