from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime

VERSION = "0.4.1"
MAX_ASSOC_LINKS = 3
MIN_ASSOC_SCORE = 0.15


def _relations_list(graph):
    rels = graph.get("relations", {})
    if isinstance(rels, dict):
        return list(rels.values())
    if isinstance(rels, list):
        return rels
    return []


def _semantic_pairs(graph):
    pairs = set()
    for rel in _relations_list(graph):
        a = rel.get("source")
        b = rel.get("target")
        if a and b:
            pairs.add(frozenset((a, b)))
    return pairs


def _select_association_links(graph):
    """Pick a tiny set of strong non-semantic links.

    These links exist only to keep the Obsidian graph connected. Their arrow
    direction is NOT semantic. Each undirected pair is emitted only once so
    Obsidian does not draw overlapping arrows in both directions.
    """
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", {})
    semantic_pairs = _semantic_pairs(graph)
    seen_pairs = set()
    candidates = []

    for a, neighbors in edges.items():
        for b, meta in neighbors.items():
            pair = frozenset((a, b))
            if len(pair) != 2 or pair in seen_pairs or pair in semantic_pairs:
                continue
            seen_pairs.add(pair)

            score = float(meta.get("score", 0))
            if score < MIN_ASSOC_SCORE:
                continue
            co = float(meta.get("co", 0))
            candidates.append((score, co, a, b))

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)

    degree = Counter()
    selected = []

    for score, co, a, b in candidates:
        if degree[a] >= MAX_ASSOC_LINKS or degree[b] >= MAX_ASSOC_LINKS:
            continue

        # Deterministic one-way storage only. More frequent concept points to
        # the rarer one; ties are lexical. This direction is explicitly marked
        # as non-semantic in the note.
        fa = int(nodes.get(a, {}).get("frequency", 0))
        fb = int(nodes.get(b, {}).get("frequency", 0))
        if (fa, a) >= (fb, b):
            source, target = a, b
        else:
            source, target = b, a

        selected.append({
            "source": source,
            "target": target,
            "score": round(score, 6),
            "co": round(co, 4),
        })
        degree[a] += 1
        degree[b] += 1

    return selected


def _extend_relation_patterns(relations):
    additions = {
        "uses": "사용",
        "contains": "포함",
        "belongs_to": "소속",
        "related_to": "관련",
    }
    relations.RELATION_LABELS.update(additions)

    S = relations.SUBJ
    O = relations.OBJ

    extra = [
        (
            "contains",
            0.90,
            re.compile(
                rf"{S}(?:은|는|이|가)\s+{O}(?:을|를)\s+(?:포함한다|포함합니다|포함하고\s*있다|포함하고\s*있습니다)",
                re.I,
            ),
        ),
        (
            "uses",
            0.88,
            re.compile(
                rf"{S}(?:은|는|이|가)\s+{O}(?:을|를)\s+(?:사용한다|사용합니다|사용하고\s*있다|사용하고\s*있습니다)",
                re.I,
            ),
        ),
        (
            "belongs_to",
            0.90,
            re.compile(
                rf"{S}(?:은|는|이|가)\s+{O}(?:에|으로)\s+(?:속한다|속합니다|분류된다|분류됩니다)",
                re.I,
            ),
        ),
        (
            "related_to",
            0.82,
            re.compile(
                rf"{S}(?:은|는|이|가)\s+{O}(?:와|과)\s+(?:관련된다|관련됩니다|관련이\s*있다|관련이\s*있습니다)",
                re.I,
            ),
        ),
        (
            "causes",
            0.90,
            re.compile(
                rf"{S}(?:은|는|이|가)\s+{O}(?:의)?\s+원인(?:이다|입니다)",
                re.I,
            ),
        ),
        (
            "requires",
            0.90,
            re.compile(
                rf"{S}(?:은|는|이|가)\s+{O}(?:을|를)\s+필요로\s+(?:한다|합니다)",
                re.I,
            ),
        ),
        # Conservative noun-definition form. It deliberately accepts a short
        # object phrase only, avoiding broad sentence-level guesses.
        (
            "is_a",
            0.80,
            re.compile(
                rf"{S}(?:은|는)\s+(?P<o>[가-힣A-Za-z0-9+._/-]+(?:\s+[가-힣A-Za-z0-9+._/-]+)?)\s*(?:이다|입니다)\.?$",
                re.I,
            ),
        ),
    ]

    existing = {
        (kind, pattern.pattern)
        for kind, _confidence, pattern in relations.PATTERNS
    }
    for item in extra:
        key = (item[0], item[2].pattern)
        if key not in existing:
            relations.PATTERNS.append(item)
            existing.add(key)


def make_save_notes(core, relations):
    def save_notes(vault, graph, top=30):
        d = core.wordmap_dirs(vault)
        words_dir = d["words"]

        for old_note in words_dir.glob("*.md"):
            try:
                old_note.unlink()
            except FileNotFoundError:
                pass

        rels = _relations_list(graph)
        assoc_links = _select_association_links(graph)

        semantic_nodes = set()
        outgoing = defaultdict(list)
        incoming = defaultdict(list)
        for rel in rels:
            source = rel.get("source")
            target = rel.get("target")
            if not source or not target:
                continue
            semantic_nodes.add(source)
            semantic_nodes.add(target)
            outgoing[source].append(rel)
            incoming[target].append(rel)

        assist_out = defaultdict(list)
        assist_nodes = set()
        for link in assoc_links:
            assist_out[link["source"]].append(link)
            assist_nodes.add(link["source"])
            assist_nodes.add(link["target"])

        active_nodes = semantic_nodes | assist_nodes
        stamp = datetime.now().isoformat(timespec="seconds")

        for token in sorted(active_nodes):
            meta = graph.get("nodes", {}).get(token, {"frequency": 0})
            frequency = int(meta.get("frequency", 0))

            semantic_lines = []
            for rel in sorted(
                outgoing.get(token, []),
                key=lambda x: (
                    -float(x.get("confidence", 0)),
                    -int(x.get("count", 0)),
                    x.get("target", ""),
                ),
            ):
                target = rel["target"]
                label = rel.get("label", rel.get("relation", "관계"))
                confidence = float(rel.get("confidence", 0))
                count = int(rel.get("count", 1))
                semantic_lines.append(
                    f"- **{label}** → [[{core.safe(target)}|{target}]] "
                    f"· 신뢰={confidence:.2f} · 근거={count}"
                )
            if not semantic_lines:
                semantic_lines = ["- 추출된 방향 관계 없음"]

            incoming_lines = []
            for rel in sorted(
                incoming.get(token, []),
                key=lambda x: (-float(x.get("confidence", 0)), x.get("source", "")),
            )[:10]:
                incoming_lines.append(
                    f"- {rel.get('source')} —{rel.get('label', '관계')}→ {token}"
                )
            if not incoming_lines:
                incoming_lines = ["- 없음"]

            assist_lines = []
            for link in sorted(
                assist_out.get(token, []),
                key=lambda x: (-float(x.get("score", 0)), x.get("target", "")),
            ):
                assist_lines.append(
                    f"- ≈ [[{core.safe(link['target'])}|{link['target']}]] "
                    f"· strength={float(link['score']):.4f} · 방향 의미 없음"
                )
            if not assist_lines:
                assist_lines = ["- 없음"]

            assoc_ranked = sorted(
                graph.get("edges", {}).get(token, {}).items(),
                key=lambda x: x[1].get("score", 0),
                reverse=True,
            )[:min(int(top), 10)]
            assoc_text = [
                f"- {neighbor} · strength={float(edge.get('score', 0)):.4f} "
                f"· co={float(edge.get('co', 0)):.2f}"
                for neighbor, edge in assoc_ranked
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
                "## 의미 관계 · 화살표 의미 있음\n"
                + "\n".join(semantic_lines)
                + "\n\n## 들어오는 의미 관계\n"
                + "\n".join(incoming_lines)
                + "\n\n## 보조 연결 · 화살표 방향 의미 없음\n"
                + "\n".join(assist_lines)
                + "\n\n## 연관 단어 · 참고용\n"
                + "\n".join(assoc_text)
                + "\n"
            )

            (words_dir / f"{core.safe(token)}.md").write_text(body, encoding="utf-8")

    return save_notes


def make_status(core, original):
    def status():
        out = original()
        vault = out.get("vault")
        if not vault:
            return out
        graph = core.load_graph(vault)
        out["association_links"] = len(_select_association_links(graph))
        out["hybrid_version"] = VERSION
        return out
    return status


def apply(core, relations):
    _extend_relation_patterns(relations)
    original_status = core.status
    core.save_notes = make_save_notes(core, relations)
    core.status = make_status(core, original_status)
    return core
