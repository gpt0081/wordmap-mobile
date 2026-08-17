from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

VERSION = "0.16.1"
START_RE = re.compile(r"^\s*@@dialogue\s+([^\s]+)\s+START\s*$", re.I)
END_RE = re.compile(r"^\s*@@dialogue\s+([^\s]+)\s+END\s*$", re.I)
SPEAKER_RE = re.compile(r"^\s*(사용자|답변|user|assistant)\s*[:：]\s*(.*)$", re.I)
ANAPHORA = {"거기", "거기서", "그곳", "그것", "그걸", "그", "걔", "그다음", "다음", "뭘", "뭐"}
MAX_CONTEXT = 14


def _body(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n", text, flags=re.S)
        if m:
            text = text[m.end():]
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _merge(current, incoming):
    out = list(current)
    for token in incoming:
        if token in out:
            out.remove(token)
        out.append(token)
    return out[-MAX_CONTEXT:]


def _turn(core, speaker, utterance, context, reference_contexts):
    tokens = core.tokenize(utterance)
    cues = [
        token for token in tokens
        if token in ANAPHORA or any(x in token for x in ("거기", "그것", "그곳", "그걸", "걔", "다음"))
    ]
    before = list(context)
    if cues and before:
        for cue in cues:
            for prior in before[-8:]:
                reference_contexts[(cue, prior)] += 1
    after = _merge(context, tokens)
    return {
        "speaker": speaker,
        "utterance": utterance[:240],
        "context_before": before[-8:],
        "context_after": after[-8:],
        "cues": cues,
    }, after


def _explicit_sessions(core, path, body, reference_contexts):
    sessions = []
    active = None
    context = []
    turns = []
    for raw in body.splitlines():
        start = START_RE.match(raw)
        if start:
            active = start.group(1)
            context = []
            turns = []
            continue
        end = END_RE.match(raw)
        if end:
            if active:
                sessions.append({"id": active, "source": path.name, "turns": turns, "format": "explicit"})
            active = None
            context = []
            turns = []
            continue
        if not active:
            continue
        m = SPEAKER_RE.match(raw)
        if not m:
            continue
        speaker, utterance = m.group(1), m.group(2).strip()
        if not utterance:
            continue
        turn, context = _turn(core, speaker, utterance, context, reference_contexts)
        turns.append(turn)
    return sessions


def _implicit_sessions(core, path, body, reference_contexts):
    """Parse the patched Corpus v1 dialogue format.

    A blank line closes a session. Within each block lines alternate
    user/assistant. The boundary is structural metadata and never becomes a
    WordMap token.
    """
    sessions = []
    blocks = re.split(r"\n\s*\n+", body.strip()) if body.strip() else []
    for block_index, block in enumerate(blocks, start=1):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        context = []
        turns = []
        for index, raw in enumerate(lines):
            m = SPEAKER_RE.match(raw)
            if m:
                speaker, utterance = m.group(1), m.group(2).strip()
            else:
                speaker = "사용자" if index % 2 == 0 else "답변"
                utterance = raw
            turn, context = _turn(core, speaker, utterance, context, reference_contexts)
            turns.append(turn)
        sessions.append({
            "id": f"{path.stem}-{block_index:03d}",
            "source": path.name,
            "turns": turns,
            "format": "blank-line",
        })
    return sessions


def build(core, vault, graph=None):
    graph = graph or core.load_graph(vault)
    corpus = core.wordmap_dirs(vault)["corpus"]
    sessions = []
    reference_contexts = Counter()

    for path in sorted(corpus.glob("*.md")):
        if path.name not in {"05_dialogue_basic.md", "06_dialogue_context.md"}:
            continue
        if hasattr(core, "corpus_role") and core.corpus_role(path) != "train":
            continue
        body = _body(path)
        if START_RE.search(body):
            sessions.extend(_explicit_sessions(core, path, body, reference_contexts))
        else:
            sessions.extend(_implicit_sessions(core, path, body, reference_contexts))

    total_turns = sum(len(session.get("turns", [])) for session in sessions)
    refs = {}
    for (cue, token), count in reference_contexts.most_common(200):
        refs.setdefault(cue, []).append({"token": token, "count": count})
    graph["대화세션지도"] = {
        "버전": VERSION,
        "세션수": len(sessions),
        "턴수": total_turns,
        "세션": sessions[:160],
        "참조문맥": refs,
        "정책": {
            "세션시작_초기화": True,
            "세션내부_유지": True,
            "세션종료_초기화": True,
            "메타데이터_학습제외": True,
            "빈줄_세션경계": True,
        },
    }
    core.save_graph(vault, graph)
    return graph["대화세션지도"]


def apply(core):
    old_rebuild = core.rebuild_wordmap
    old_status = core.status

    def rebuild(vault, window=4):
        result = old_rebuild(vault, window=window)
        session_map = build(core, vault)
        result["dialogue_sessions"] = int(session_map.get("세션수", 0))
        result["dialogue_turns"] = int(session_map.get("턴수", 0))
        result["dialogue_corpus_version"] = VERSION
        return result

    def status():
        out = old_status()
        vault = out.get("vault")
        if vault:
            graph = core.load_graph(Path(vault))
            data = graph.get("대화세션지도", {}) or {}
            out["dialogue_corpus_version"] = VERSION
            out["dialogue_corpus_sessions"] = int(data.get("세션수", 0))
            out["dialogue_corpus_turns"] = int(data.get("턴수", 0))
        return out

    core.rebuild_wordmap = rebuild
    core.status = status
    core.dialogue_corpus_rebuild = lambda vault: build(core, vault)
    return core
