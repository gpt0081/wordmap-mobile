from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

VERSION = "0.4.0"

RELATION_LABELS = {
    "is_a": "종류",
    "used_for": "사용처",
    "promotes": "촉진",
    "increases": "증가",
    "decreases": "감소",
    "affects": "영향",
    "property": "특성",
    "component": "구성",
    "causes": "원인",
    "requires": "필요",
}

# High-precision Korean surface patterns only. The goal is to make arrows
# meaningful, not to pretend we have a full parser.
SUBJ = r"(?P<s>[가-힣A-Za-z0-9+._/-]{1,40})"
OBJ = r"(?P<o>[가-힣A-Za-z0-9+._/-]+(?:\s+[가-힣A-Za-z0-9+._/-]+){0,3})"

PATTERNS = [
    (
        "is_a",
        0.95,
        re.compile(
            rf"{SUBJ}(?:은|는)\s+(?P<o>[가-힣A-Za-z0-9+._/-]+)(?:의)?\s*(?:한\s+)?종류(?:이다|입니다|다)",
            re.I,
        ),
    ),
    (
        "used_for",
        0.92,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:에|에서)\s+(?:사용된다|사용됩니다|쓰인다|쓰입니다)",
            re.I,
        ),
    ),
    (
        "used_for",
        0.88,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:로|으로)\s+(?:사용된다|사용됩니다|쓰인다|쓰입니다)",
            re.I,
        ),
    ),
    (
        "promotes",
        0.93,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:을|를)\s+(?:촉진|가속)(?:한다|합니다|시킨다|시킵니다)",
            re.I,
        ),
    ),
    (
        "increases",
        0.90,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:을|를)\s+(?:증가시키|높이)(?:는|며|고|면|다|ㅂ니다|습니다|인다)",
            re.I,
        ),
    ),
    (
        "decreases",
        0.90,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:을|를)\s+(?:감소시키|낮추)(?:는|며|고|면|다|ㅂ니다|습니다|인다)",
            re.I,
        ),
    ),
    (
        "affects",
        0.90,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:에|에게)\s+영향(?:을)?\s+(?:준다|줍니다|미친다|미칩니다)",
            re.I,
        ),
    ),
    (
        "property",
        0.84,
        re.compile(
            rf"{SUBJ}(?:은|는)\s+{OBJ}(?:이|가)\s+(?:우수하다|우수합니다|높다|높습니다|낮다|낮습니다|좋다|좋습니다)",
            re.I,
        ),
    ),
    (
        "component",
        0.88,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:로|으로)\s+구성(?:된다|됩니다|되어\s*있다|되어\s*있습니다)",
            re.I,
        ),
    ),
    (
        "causes",
        0.90,
        re.compile(
            rf"{SUBJ}(?:은|는|이|가)\s+{OBJ}(?:을|를)\s+(?:유발한다|유발합니다|발생시킨다|발생시킵니다)",
            re.I,
        ),
    ),
    (
        "requires",
        0.86,
        re.compile(
            rf"{SUBJ}(?:은|는|에|에는)\s+{OBJ}(?:이|가)\s+필요(?:하다|합니다)",
            re.I,
        ),
    ),
]

RELATION_WORDS = {
    "종류", "사용", "사용되다", "쓰이다", "촉진", "가속", "증가", "감소",
    "영향", "구성", "유발", "발생", "필요", "우수", "높다", "낮다", "좋다",
}


def _clean_phrase(phrase: str) -> str:
    return phrase.strip(" \t\r\n,;:()[]{}\"'`")


def _pick_token(core, phrase: str):
    tokens = [
        t for t in core.tokenize(_clean_phrase(phrase))
        if t not in RELATION_WORDS
    ]
    if not tokens:
        return None
    return tokens[-1]


def extract_relations(core, text: str):
    found = []
    seen = set()

    for sentence in core.split_sentences(text):
        compact = re.sub(r"\s+", " ", sentence).strip()
        if not compact:
            continue

        for relation, confidence, pattern in PATTERNS:
            for match in pattern.finditer(compact):
                source = _pick_token(core, match.group("s"))
                target = _pick_token(core, match.group("o"))

                if not source or not target or source == target:
                    continue

                key = (source, relation, target, compact)
                if key in seen:
                    continue
                seen.add(key)

                found.append({
                    "source": source,
                    "relation": relation,
                    "label": RELATION_LABELS[relation],
                    "target": target,
                    "confidence": confidence,
                    "evidence": compact[:240],
                })

    return found


def _relation_key(source: str, relation: str, target: str) -> str:
    return "\x1e".join((source, relation, target))


def accumulate_relations(graph, relations):
    bucket = graph.setdefault("relations", {})

    for item in relations:
        key = _relation_key(item["source"], item["relation"], item["target"])
        old = bucket.get(key)

        if old is None:
            bucket[key] = {
                "source": item["source"],
                "relation": item["relation"],
                "label": item["label"],
                "target": item["target"],
                "count": 1,
                "confidence": round(float(item["confidence"]), 3),
                "evidence": [item["evidence"]],
            }
            continue

        old["count"] = int(old.get("count", 0)) + 1
        old["confidence"] = round(
            max(float(old.get("confidence", 0)), float(item["confidence"])),
            3,
        )
        evidence = old.setdefault("evidence", [])
        if item["evidence"] not in evidence and len(evidence) < 3:
            evidence.append(item["evidence"])


def make_analyze_into_graph(core, original):
    def analyze_into_graph(graph, text, window=4):
        stats = original(graph, text, window=window)
        accumulate_relations(graph, extract_relations(core, text))
        return stats
    return analyze_into_graph


def _relations_list(graph):
    rels = graph.get("relations", {})
    if isinstance(rels, dict):
        return list(rels.values())
    if isinstance(rels, list):
        return rels
    return []


def make_save_notes(core):
    def save_notes(vault, graph, top=30):
        d = core.wordmap_dirs(vault)
        words_dir = d["words"]

        for old_note in words_dir.glob("*.md"):
            try:
                old_note.unlink()
            except FileNotFoundError:
                pass

        assoc_edges = graph.get("edges", {})
        relations = _relations_list(graph)
        semantic_nodes = set()
        outgoing = defaultdict(list)
        incoming = defaultdict(list)

        for rel in relations:
            source = rel.get("source")
            target = rel.get("target")
            if not source or not target:
                continue
            semantic_nodes.add(source)
            semantic_nodes.add(target)
            outgoing[source].append(rel)
            incoming[target].append(rel)

        association_nodes = {
            token for token, neighbors in assoc_edges.items() if neighbors
        }
        active_nodes = association_nodes | semantic_nodes
        stamp = datetime.now().isoformat(timespec="seconds")

        for token in sorted(active_nodes):
            meta = graph.get("nodes", {}).get(token, {"frequency": 0})
            frequency = int(meta.get("frequency", 0))

            rel_lines = []
            for rel in sorted(
                outgoing.get(token, []),
                key=lambda x: (-float(x.get("confidence", 0)), -int(x.get("count", 0)), x.get("target", "")),
            ):
                target = rel["target"]
                label = rel.get("label", rel.get("relation", "관계"))
                confidence = float(rel.get("confidence", 0))
                count = int(rel.get("count", 1))
                rel_lines.append(
                    f"- **{label}** → [[{core.safe(target)}|{target}]] "
                    f"· 신뢰={confidence:.2f} · 근거={count}"
                )
            if not rel_lines:
                rel_lines = ["- 추출된 방향 관계 없음"]

            incoming_lines = []
            for rel in sorted(
                incoming.get(token, []),
                key=lambda x: (-float(x.get("confidence", 0)), x.get("source", "")),
            )[:10]:
                # No wiki link: a backlink would create a fake reverse arrow.
                incoming_lines.append(
                    f"- {rel.get('source')} —{rel.get('label', '관계')}→ {token}"
                )
            if not incoming_lines:
                incoming_lines = ["- 없음"]

            ranked = sorted(
                assoc_edges.get(token, {}).items(),
                key=lambda x: x[1].get("score", 0),
                reverse=True,
            )[:min(int(top), 10)]
            assoc_lines = [
                f"- {neighbor} · strength={float(edge.get('score', 0)):.4f} "
                f"· co={float(edge.get('co', 0)):.2f}"
                for neighbor, edge in ranked
            ] or ["- 연관 단어 없음"]

            body = (
                "---\n"
                "type: word-node\n"
                f'token: "{token.replace(chr(34), chr(39))}"\n'
                f"frequency: {frequency}\n"
                f'updated: "{stamp}"\n'
                "---\n\n"
                f"# {token}\n\n"
                f"빈도: **{frequency}**\n\n"
                "## 의미 관계\n" + "\n".join(rel_lines)
                + "\n\n## 들어오는 관계\n" + "\n".join(incoming_lines)
                + "\n\n## 연관 단어 · 방향 없음\n" + "\n".join(assoc_lines)
                + "\n"
            )

            (words_dir / f"{core.safe(token)}.md").write_text(body, encoding="utf-8")

    return save_notes


def _semantic_paths(graph, seeds, max_paths=16):
    rels = _relations_list(graph)
    outgoing = defaultdict(list)

    for rel in rels:
        if rel.get("source") and rel.get("target"):
            outgoing[rel["source"]].append(rel)

    paths = []
    seen = set()

    for seed in seeds:
        for first in outgoing.get(seed, []):
            key = (seed, first.get("relation"), first.get("target"))
            if key not in seen:
                seen.add(key)
                paths.append({
                    "depth": 1,
                    "text": f"{seed} →({first.get('label', '관계')})→ {first.get('target')}",
                    "confidence": float(first.get("confidence", 0)),
                })

            middle = first.get("target")
            for second in outgoing.get(middle, []):
                key2 = (seed, first.get("relation"), middle, second.get("relation"), second.get("target"))
                if key2 in seen:
                    continue
                seen.add(key2)
                paths.append({
                    "depth": 2,
                    "text": (
                        f"{seed} →({first.get('label', '관계')})→ {middle} "
                        f"→({second.get('label', '관계')})→ {second.get('target')}"
                    ),
                    "confidence": min(
                        float(first.get("confidence", 0)),
                        float(second.get("confidence", 0)),
                    ),
                })

    paths.sort(key=lambda x: (-x["confidence"], x["depth"], x["text"]))
    return paths[:max_paths]


def make_ask(core, original):
    def ask(vault, question, limit=20, depth=2):
        result = original(vault, question, limit=limit, depth=depth)
        graph = core.load_graph(vault)
        result["semantic_paths"] = _semantic_paths(graph, result.get("seed_tokens", []))
        return result
    return ask


def make_status(core, original):
    def status():
        out = original()
        vault = out.get("vault")
        if not vault:
            return out
        graph = core.load_graph(vault)
        rels = _relations_list(graph)
        out["semantic_relations"] = len(rels)
        out["semantic_nodes"] = len({
            x for rel in rels for x in (rel.get("source"), rel.get("target")) if x
        })
        return out
    return status


def apply(core):
    original_analyze = core.analyze_into_graph
    original_ask = core.ask
    original_status = core.status

    core.analyze_into_graph = make_analyze_into_graph(core, original_analyze)
    core.save_notes = make_save_notes(core)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    return core
