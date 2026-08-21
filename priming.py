from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

VERSION = "0.18.0"
STATE_FILE = "priming_state.json"
TURN_DECAY = 0.72
QUESTION_GAIN = 0.62
ANSWER_GAIN = 0.38
SITUATION_GAIN = 0.48
PRIME_GAIN = 0.70
MIN_SCORE = 0.035
MAX_PRIMES = 48
MAX_VISIBLE = 16

_ACTIVE = ContextVar("wordmap_priming_active", default=None)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / STATE_FILE


def _default(session_id="web"):
    return {
        "version": VERSION,
        "session_id": str(session_id or "web"),
        "turn": 0,
        "activations": {},
        "updated": None,
    }


def _load(core, vault):
    path = _path(core, vault)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = _default()
    data.setdefault("session_id", "web")
    data.setdefault("turn", 0)
    data.setdefault("activations", {})
    data["version"] = VERSION
    return data


def _save(core, vault, data):
    data["version"] = VERSION
    data["updated"] = _now()
    _path(core, vault).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def _clip(value):
    return max(0.0, min(1.0, float(value)))


def _merge(old, amount):
    old = _clip(old)
    amount = _clip(amount)
    return 1.0 - ((1.0 - old) * (1.0 - amount))


def _unique(tokens):
    out = []
    for token in tokens or []:
        token = str(token or "").strip()
        if token and token not in out:
            out.append(token)
    return out


def _decay(data):
    rows = data.get("activations", {}) or {}
    kept = {}
    for token, row in rows.items():
        score = float((row or {}).get("score", 0)) * TURN_DECAY
        if score < MIN_SCORE:
            continue
        item = dict(row or {})
        item["score"] = round(_clip(score), 6)
        kept[token] = item
    data["activations"] = kept
    data["turn"] = int(data.get("turn", 0)) + 1
    return data


def _stimulate(data, tokens, amount, source):
    amount = _clip(amount)
    rows = data.setdefault("activations", {})
    turn = int(data.get("turn", 0))
    for index, token in enumerate(_unique(tokens)):
        local = amount * max(0.68, 1.0 - (0.035 * index))
        row = rows.setdefault(token, {
            "score": 0.0,
            "count": 0,
            "sources": {},
            "last_turn": turn,
        })
        row["score"] = round(_merge(row.get("score", 0), local), 6)
        row["count"] = int(row.get("count", 0)) + 1
        row["last_turn"] = turn
        sources = row.setdefault("sources", {})
        sources[source] = int(sources.get(source, 0)) + 1

    ranked = sorted(
        rows.items(),
        key=lambda x: (-float((x[1] or {}).get("score", 0)), -int((x[1] or {}).get("count", 0)), x[0]),
    )[:MAX_PRIMES]
    data["activations"] = {token: row for token, row in ranked}
    return data


def _scores(data):
    return {
        token: _clip((row or {}).get("score", 0))
        for token, row in (data.get("activations", {}) or {}).items()
        if _clip((row or {}).get("score", 0)) >= MIN_SCORE
    }


def top_rows(data, limit=MAX_VISIBLE):
    rows = []
    for token, row in (data.get("activations", {}) or {}).items():
        rows.append({
            "표제어": token,
            "점화도": round(_clip((row or {}).get("score", 0)), 4),
            "반복": int((row or {}).get("count", 0)),
            "근거": sorted(
                ((row or {}).get("sources", {}) or {}).items(),
                key=lambda x: (-int(x[1]), x[0]),
            )[:4],
        })
    rows.sort(key=lambda x: (-float(x["점화도"]), -int(x["반복"]), x["표제어"]))
    return rows[:max(1, int(limit))]


def active_snapshot():
    data = _ACTIVE.get() or {}
    return {
        "vault": data.get("vault"),
        "session_id": data.get("session_id"),
        "turn": int(data.get("turn", 0)),
        "scores": dict(data.get("scores", {}) or {}),
        "rows": list(data.get("rows", []) or []),
    }


def reset(core, vault, session_id="web"):
    data = _default(session_id=session_id)
    _save(core, vault, data)
    return status(core, vault)


def prime_text(core, vault, text, amount=PRIME_GAIN, source="명시적 점화"):
    data = _load(core, vault)
    tokens = core.tokenize(str(text or ""))
    _stimulate(data, tokens, amount, source)
    _save(core, vault, data)
    return status(core, vault)


def status(core, vault):
    data = _load(core, vault)
    return {
        "version": VERSION,
        "session_id": data.get("session_id"),
        "turn": int(data.get("turn", 0)),
        "active_count": len(data.get("activations", {}) or {}),
        "top": top_rows(data, limit=MAX_VISIBLE),
        "updated": data.get("updated"),
    }


def _result_tokens(core, result):
    situation = result.get("상황문맥") or {}
    situation_tokens = list(situation.get("핵심노드") or [])

    answer_tokens = []
    generated = result.get("generated_sentences") or []
    if generated:
        preferred = next(
            (row for row in generated if row.get("mode") == "wordmap_gpt2"),
            generated[0],
        )
        answer_tokens.extend(preferred.get("path") or [])
        if not answer_tokens and preferred.get("text"):
            answer_tokens.extend(core.tokenize(str(preferred.get("text"))))

    event_answer = result.get("상황답변") or {}
    answer_tokens.extend(event_answer.get("값") or [])
    return _unique(situation_tokens), _unique(answer_tokens)


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        data = _load(core, vault)
        _decay(data)
        before_rows = top_rows(data, limit=MAX_VISIBLE)
        active = {
            "vault": str(vault),
            "session_id": data.get("session_id"),
            "turn": int(data.get("turn", 0)),
            "scores": _scores(data),
            "rows": before_rows,
        }
        token = _ACTIVE.set(active)
        try:
            result = original_ask(vault, question, limit=limit, depth=depth)
        finally:
            _ACTIVE.reset(token)

        question_tokens = core.tokenize(str(question or ""))
        situation_tokens, answer_tokens = _result_tokens(core, result)
        _stimulate(data, question_tokens, QUESTION_GAIN, "이전 질문")
        _stimulate(data, situation_tokens, SITUATION_GAIN, "상황 핵심")
        _stimulate(data, answer_tokens, ANSWER_GAIN, "이전 답변")
        _save(core, vault, data)

        result["점화상태"] = {
            "version": VERSION,
            "session_id": data.get("session_id"),
            "turn": int(data.get("turn", 0)),
            "사용전": before_rows,
            "갱신후": top_rows(data, limit=MAX_VISIBLE),
            "감쇠율": TURN_DECAY,
        }
        result["priming_version"] = VERSION
        return result
    return ask


def apply(core):
    original_ask = core.ask
    original_status = core.status
    original_start = getattr(core, "dialogue_start", None)
    original_reset = getattr(core, "dialogue_reset", None)
    original_prime = getattr(core, "dialogue_prime", None)

    core.ask = make_ask(core, original_ask)

    if original_start:
        def dialogue_start(vault, session_id="web"):
            out = original_start(vault, session_id)
            reset(core, vault, session_id=session_id)
            return out
        core.dialogue_start = dialogue_start

    if original_reset:
        def dialogue_reset(vault):
            out = original_reset(vault)
            reset(core, vault, session_id="web")
            return out
        core.dialogue_reset = dialogue_reset

    if original_prime:
        def dialogue_prime(vault, text):
            out = original_prime(vault, text)
            prime_text(core, vault, text, amount=PRIME_GAIN, source="대화 사전문맥")
            return out
        core.dialogue_prime = dialogue_prime

    def system_status():
        out = original_status()
        vault = out.get("vault")
        if vault:
            s = status(core, Path(vault))
            out["priming_version"] = VERSION
            out["priming_active"] = s["active_count"]
            out["priming_turn"] = s["turn"]
        return out

    core.status = system_status
    core.priming_status = lambda vault: status(core, vault)
    core.priming_reset = lambda vault: reset(core, vault)
    core.priming_prime = lambda vault, text, amount=PRIME_GAIN: prime_text(core, vault, text, amount=amount)
    core.priming_version = VERSION
    return core
