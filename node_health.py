from __future__ import annotations

import math
import re
from collections import defaultdict

VERSION = "0.14.0"
PAIR_SEP = "\x1f"
MAX_BRIDGES_PER_NODE = 8

STATUS_HEALTHY = "정상"
STATUS_WEAK = "약한 고립"
STATUS_VISUAL = "시각적 고립"
STATUS_ORPHAN = "진짜 고립"


def _relations(graph):
    rows = graph.get("relations", {})
    if isinstance(rows, dict):
        return list(rows.values())
    if isinstance(rows, list):
        return rows
    return []


def _bigrams(graph):
    generation = graph.get("generation", {}) or {}
    if generation.get("bigrams"):
        return generation.get("bigrams", {}) or {}
    return (graph.get("sequence", {}) or {}).get("bigrams", {}) or {}


def _events(graph):
    rows = (graph.get("상황지도", {}) or {}).get("사건", {}) or {}
    if isinstance(rows, dict):
        return list(rows.values())
    if isinstance(rows, list):
        return rows
    return []


def _tag_safe(value):
    return str(value or "미분류").strip().replace(" ", "-").replace("/", "-") or "미분류"


def _all_tokens(graph):
    """Return nodes that can actually appear as WordMap/semantic graph nodes.

    Grammar-only generation tokens are intentionally not promoted into health
    rows merely because they occur in sequence statistics.
    """
    tokens = set((graph.get("nodes", {}) or {}).keys())
    for source, neighbors in (graph.get("edges", {}) or {}).items():
        if source:
            tokens.add(source)
        tokens.update(x for x in (neighbors or {}) if x)
    for rel in _relations(graph):
        if rel.get("source"):
            tokens.add(rel["source"])
        if rel.get("target"):
            tokens.add(rel["target"])
    return tokens


def _tags_by_token(graph, tokens):
    grammar_roles = (graph.get("문법", {}) or {}).get("표제어역할", {}) or {}
    nodes = graph.get("nodes", {}) or {}
    out = {}
    for token in tokens:
        meta = nodes.get(token, {}) or {}
        pos = meta.get("pos_ko") or meta.get("pos") or "미분류"
        tags = {f"품사/{_tag_safe(pos)}"}
        for role, count in (grammar_roles.get(token, {}) or {}).items():
            if int(count or 0) > 0:
                tags.add(f"문장역할/{_tag_safe(role)}")
        out[token] = tags
    return out


def _protected_token(token, meta):
    low = str(token).lower()
    pos = str((meta or {}).get("pos", ""))
    if pos == "proper":
        return True
    if re.search(r"[0-9]", str(token)):
        return True
    if re.search(r"[A-Za-z]", str(token)) and str(token).upper() == str(token):
        return True
    return low in {
        "mbts", "sbr", "nbr", "hnbr", "epdm", "br", "cr", "ir", "erp",
        "llm", "rag", "ocr", "api", "gpu", "cpu", "ai", "ml", "json",
        "csv", "pvi", "zno", "doa", "totm", "tespt",
    }


def _indices(graph, tokens):
    association = defaultdict(set)
    semantic = defaultdict(set)
    sequence = defaultdict(set)
    event_links = defaultdict(set)
    raw_pairs = defaultdict(set)
    token_set = set(tokens)

    for source, neighbors in (graph.get("edges", {}) or {}).items():
        if source not in token_set:
            continue
        for target in (neighbors or {}):
            if target not in token_set or source == target:
                continue
            association[source].add(target)
            association[target].add(source)

    for rel in _relations(graph):
        source, target = rel.get("source"), rel.get("target")
        if source not in token_set or target not in token_set or source == target:
            continue
        semantic[source].add(target)
        semantic[target].add(source)

    for source, targets in _bigrams(graph).items():
        if source not in token_set:
            continue
        for target, count in (targets or {}).items():
            if target not in token_set or source == target or int(count or 0) <= 0:
                continue
            sequence[source].add(target)
            sequence[target].add(source)

    for i, event in enumerate(_events(graph)):
        event_id = str(event.get("id") or f"event:{i}")
        participants = set()
        predicate = event.get("서술어")
        if predicate in token_set:
            participants.add(predicate)
        for values in (event.get("역할", {}) or {}).values():
            participants.update(x for x in (values or []) if x in token_set)
        for token in participants:
            event_links[token].add(event_id)

    for key, value in (graph.get("pairs", {}) or {}).items():
        try:
            source, target = str(key).split(PAIR_SEP, 1)
        except ValueError:
            continue
        if source not in token_set or target not in token_set or source == target:
            continue
        if float(value or 0) <= 0:
            continue
        raw_pairs[source].add(target)
        raw_pairs[target].add(source)

    visible = defaultdict(set)
    for token in tokens:
        visible[token] = set(association[token]) | set(semantic[token])

    return association, semantic, sequence, event_links, raw_pairs, visible


def _isolated_tags(token, tags_by_token, visible):
    neighbors = visible.get(token, set())
    if not neighbors:
        return []
    isolated = []
    for tag in sorted(tags_by_token.get(token, set())):
        if not any(tag in tags_by_token.get(neighbor, set()) for neighbor in neighbors):
            isolated.append(tag)
    return isolated


def _bridge_paths(token, isolated_tags, tags_by_token, visible):
    if not isolated_tags:
        return []
    direct = visible.get(token, set())
    found, seen = [], set()
    for tag in isolated_tags:
        for middle in sorted(direct):
            for target in sorted(visible.get(middle, set())):
                if target == token or target in direct:
                    continue
                if tag not in tags_by_token.get(target, set()):
                    continue
                key = (tag, middle, target)
                if key in seen:
                    continue
                seen.add(key)
                found.append({
                    "태그": tag,
                    "경로": [token, middle, target],
                    "설명": "태그 필터에서 중간 노드가 숨겨질 수 있는 실제 2홉 경로",
                })
                if len(found) >= MAX_BRIDGES_PER_NODE:
                    return found
    return found


def analyze_graph(graph):
    tokens = sorted(_all_tokens(graph))
    tags_by_token = _tags_by_token(graph, tokens)
    association, semantic, sequence, event_links, raw_pairs, visible = _indices(graph, tokens)
    nodes = graph.get("nodes", {}) or {}

    rows = {}
    summary = {
        STATUS_HEALTHY: 0,
        STATUS_WEAK: 0,
        STATUS_VISUAL: 0,
        STATUS_ORPHAN: 0,
        "태그필터고립": 0,
        "보호노드": 0,
        "전체": len(tokens),
    }

    for token in tokens:
        assoc_n = len(association[token])
        semantic_n = len(semantic[token])
        sequence_n = len(sequence[token])
        event_n = len(event_links[token])
        visible_n = len(visible[token])
        internal_n = sequence_n + event_n
        structural_n = visible_n + internal_n
        raw_pair_n = len(raw_pairs[token])

        if structural_n == 0:
            status = STATUS_ORPHAN
        elif visible_n == 0 and internal_n > 0:
            status = STATUS_VISUAL
        elif visible_n <= 1 and structural_n <= 2:
            status = STATUS_WEAK
        else:
            status = STATUS_HEALTHY

        weighted = assoc_n + (1.45 * semantic_n) + (0.55 * sequence_n) + (1.10 * event_n)
        health_score = 1.0 - math.exp(-weighted / 4.0) if weighted > 0 else 0.0
        isolated_tags = _isolated_tags(token, tags_by_token, visible)
        bridges = _bridge_paths(token, isolated_tags, tags_by_token, visible)
        protected = _protected_token(token, nodes.get(token, {}))

        row = {
            "표제어": token,
            "상태": status,
            "건강도": round(health_score, 4),
            "빈도": int((nodes.get(token, {}) or {}).get("frequency", 0)),
            "연상연결": assoc_n,
            "의미연결": semantic_n,
            "순서연결": sequence_n,
            "사건연결": event_n,
            "표시연결": visible_n,
            "내부연결": internal_n,
            "구조연결": structural_n,
            "원시공기연결": raw_pair_n,
            "잘린약한연결": max(0, raw_pair_n - assoc_n),
            "태그": sorted(tags_by_token.get(token, set())),
            "태그필터고립": bool(isolated_tags),
            "고립태그": isolated_tags,
            "태그브리지": bridges,
            "보호노드": protected,
            "자동삭제허용": False,
        }
        rows[token] = row
        summary[status] += 1
        summary["태그필터고립"] += int(bool(isolated_tags))
        summary["보호노드"] += int(protected)

        meta = nodes.get(token)
        if isinstance(meta, dict):
            meta["health_status"] = status
            meta["health_score"] = round(health_score, 4)
            meta["tag_filter_isolated"] = bool(isolated_tags)
            meta["isolated_tags"] = isolated_tags[:8]

    graph["노드건강도"] = {
        "버전": VERSION,
        "요약": summary,
        "노드": rows,
        "정책": {
            "자동삭제": False,
            "태그브리지_가짜링크생성": False,
            "설명": "태그 필터 고립은 실제 구조 고립과 분리하며, 전문용어/희귀어를 자동 삭제하지 않습니다.",
        },
    }
    return graph["노드건강도"]


def ensure_health(core, vault, persist=True):
    graph = core.load_graph(vault)
    health = graph.get("노드건강도", {}) or {}
    if health.get("버전") != VERSION:
        health = analyze_graph(graph)
        if persist:
            core.save_graph(vault, graph)
    return graph, health


def health_summary(core, vault, status=None, tag_isolated=False, limit=100):
    _graph, health = ensure_health(core, vault, persist=True)
    rows = list((health.get("노드", {}) or {}).values())
    if status:
        rows = [row for row in rows if row.get("상태") == status]
    if tag_isolated:
        rows = [row for row in rows if row.get("태그필터고립")]
    severity = {STATUS_ORPHAN: 0, STATUS_VISUAL: 1, STATUS_WEAK: 2, STATUS_HEALTHY: 3}
    rows.sort(key=lambda row: (
        severity.get(row.get("상태"), 9),
        float(row.get("건강도", 0)),
        -int(row.get("빈도", 0)),
        str(row.get("표제어", "")),
    ))
    return {
        "version": VERSION,
        "summary": health.get("요약", {}),
        "filters": {"status": status, "tag_isolated": bool(tag_isolated)},
        "rows": rows[:max(1, min(int(limit), 500))],
        "matched": len(rows),
        "policy": health.get("정책", {}),
    }


def health_item(core, vault, token):
    _graph, health = ensure_health(core, vault, persist=True)
    row = (health.get("노드", {}) or {}).get(str(token or ""))
    if not row:
        raise ValueError("노드 건강도 정보를 찾을 수 없습니다.")
    return {"version": VERSION, "node": row}


def _append_note_health(core, vault, health):
    words_dir = core.wordmap_dirs(vault)["words"]
    for token, row in (health.get("노드", {}) or {}).items():
        note = words_dir / f"{core.safe(token)}.md"
        if not note.exists():
            continue
        state_tag = f"#연결상태/{_tag_safe(row.get('상태', '미분류'))}"
        tags = [state_tag]
        if row.get("태그필터고립"):
            tags.append("#연결상태/태그필터고립")
        if row.get("보호노드"):
            tags.append("#연결상태/보호노드")
        isolated = ", ".join(row.get("고립태그", [])[:8]) or "없음"
        bridges = row.get("태그브리지", []) or []
        bridge_text = "; ".join(
            " → ".join(item.get("경로", [])) + f" [{item.get('태그', '')}]"
            for item in bridges[:5]
        ) or "없음"
        block = (
            "\n## 노드 건강도\n"
            f"- 상태: **{row.get('상태')}** · 건강도={float(row.get('건강도', 0)):.3f}\n"
            f"- 연결: 연상 {row.get('연상연결', 0)} · 의미 {row.get('의미연결', 0)} · 순서 {row.get('순서연결', 0)} · 사건 {row.get('사건연결', 0)}\n"
            f"- 원시 공기 연결 {row.get('원시공기연결', 0)} · 정리 과정에서 잘린 약한 연결 {row.get('잘린약한연결', 0)}\n"
            f"- 태그 필터 고립: {'예' if row.get('태그필터고립') else '아니오'} · 고립 태그: {isolated}\n"
            f"- 실제 2홉 태그 브리지 후보: {bridge_text}\n"
            f"- 보호 노드: {'예' if row.get('보호노드') else '아니오'} · 자동 삭제: 하지 않음\n"
            f"- 진단 태그: {' '.join(tags)}\n"
            "\n> 태그 브리지는 진단 정보일 뿐이며 가짜 WordMap 링크로 추가하지 않습니다.\n"
        )
        text = note.read_text(encoding="utf-8")
        note.write_text(text.rstrip() + "\n" + block, encoding="utf-8")


def make_save_notes(core, original_save_notes):
    def save_notes(vault, graph, top=30):
        health = analyze_graph(graph)
        core.save_graph(vault, graph)
        result = original_save_notes(vault, graph, top=top)
        _append_note_health(core, vault, health)
        return result
    return save_notes


def refresh_health(core, vault):
    graph = core.load_graph(vault)
    health = analyze_graph(graph)
    core.save_graph(vault, graph)
    core.save_notes(vault, graph)
    return {
        "version": VERSION,
        "recalculated": True,
        "summary": health.get("요약", {}),
        "full_corpus_rebuild_required": False,
    }


def _decorate_visual(graph, visual):
    if not isinstance(visual, dict):
        return visual
    health = (graph.get("노드건강도", {}) or {}).get("노드", {}) or {}
    for node in visual.get("nodes", []) or []:
        row = health.get(node.get("id"), {}) or {}
        node["health_status"] = row.get("상태")
        node["health_score"] = row.get("건강도", 0)
        node["tag_isolated"] = bool(row.get("태그필터고립"))
        node["isolated_tags"] = list(row.get("고립태그", [])[:8])
    visual.setdefault("stats", {})["node_health"] = (
        graph.get("노드건강도", {}) or {}
    ).get("요약", {})
    return visual


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        result = original_ask(vault, question, limit=limit, depth=depth)
        graph, _health = ensure_health(core, vault, persist=True)
        if result.get("visual_graph"):
            _decorate_visual(graph, result["visual_graph"])
        result["node_health_version"] = VERSION
        return result
    return ask


def make_graph_snapshot(core, original_graph_snapshot):
    def graph_snapshot(vault, **kwargs):
        visual = original_graph_snapshot(vault, **kwargs)
        graph, _health = ensure_health(core, vault, persist=True)
        return _decorate_visual(graph, visual)
    return graph_snapshot


def make_rebuild(core, original_rebuild):
    def rebuild(vault, window=4):
        result = original_rebuild(vault, window=window)
        _graph, health = ensure_health(core, vault, persist=True)
        result["node_health_version"] = VERSION
        result["node_health"] = health.get("요약", {})
        return result
    return rebuild


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        out["node_health_version"] = VERSION
        if not vault:
            return out
        _graph, health = ensure_health(core, vault, persist=True)
        out["node_health"] = health.get("요약", {})
        return out
    return status


def apply(core):
    original_save_notes = core.save_notes
    original_rebuild = core.rebuild_wordmap
    original_ask = core.ask
    original_status = core.status
    original_graph_snapshot = getattr(core, "graph_snapshot", None)

    core.save_notes = make_save_notes(core, original_save_notes)
    core.rebuild_wordmap = make_rebuild(core, original_rebuild)
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    if original_graph_snapshot:
        core.graph_snapshot = make_graph_snapshot(core, original_graph_snapshot)

    core.node_health_list = lambda vault, status=None, tag_isolated=False, limit=100: health_summary(
        core, vault, status=status, tag_isolated=tag_isolated, limit=limit
    )
    core.node_health_get = lambda vault, token: health_item(core, vault, token)
    core.node_health_recalculate = lambda vault: refresh_health(core, vault)
    core.node_health_version = VERSION
    return core
