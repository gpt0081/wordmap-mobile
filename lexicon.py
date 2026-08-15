from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import grammar

VERSION = "0.5.0"


def lexeme_id(pos, lemma):
    return f"{pos}:{lemma}"


def build(texts):
    texts = list(texts)
    evidence = grammar.collect_evidence(texts)
    entries = {}
    surface_index = defaultdict(list)

    for text in texts:
        for surface in grammar.raw_words(text):
            for item in grammar.analyze_surface(surface, evidence):
                lid = lexeme_id(item["pos"], item["lemma"])
                entry = entries.setdefault(lid, {
                    "id": lid,
                    "lemma": item["lemma"],
                    "pos": item["pos"],
                    "pos_ko": grammar.POS_KO.get(item["pos"], item["pos"]),
                    "confidence": 0.0,
                    "forms_seen": Counter(),
                    "particles_seen": Counter(),
                    "reasons": Counter(),
                })

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
        "surface_index": {k: v for k, v in sorted(surface_index.items())},
        "stats": {
            "lexemes": len(clean_entries),
            "surfaces": len(surface_index),
            "one_char_nouns": sum(
                1
                for entry in clean_entries.values()
                if entry["pos"] == "noun" and len(entry["lemma"]) == 1
            ),
        },
    }


def resolve(data, surface):
    surface = surface.strip("._-/").lower()
    ids = data.get("surface_index", {}).get(surface, [])
    entries = data.get("entries", {})
    candidates = [entries[x] for x in ids if x in entries]

    if not candidates:
        return None

    candidates.sort(
        key=lambda entry: (
            float(entry.get("confidence", 0)),
            sum(int(v) for v in entry.get("forms_seen", {}).values()),
        ),
        reverse=True,
    )
    return candidates[0]


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
