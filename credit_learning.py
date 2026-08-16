from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import context_map

VERSION = "0.15.0"
LEARNING_FILE = "learning.json"
SEP = "\x1f"
DEFAULT_LR = 0.08
TRACE_DECAY = 0.86
MAX_PENDING = 12
MAX_HISTORY = 60
MAX_WEIGHT = 1.50

_ACTIVE = {"vault": None, "data": None}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / LEARNING_FILE


def _default():
    return {
        "version": VERSION,
        "learning_rate": DEFAULT_LR,
        "updates": 0,
        "positive": 0,
        "negative": 0,
        "transitions": {},
        "context_targets": {},
        "origins": {},
        "pending": {},
        "used_traces": [],
        "history": [],
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
    base = _default()
    for key, value in base.items():
        data.setdefault(key, value)
    data["version"] = VERSION
    return data


def _save(core, vault, data):
    data["version"] = VERSION
    data["updated"] = _now()
    _path(core, vault).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def _clamp(value):
    return max(-MAX_WEIGHT, min(MAX_WEIGHT, float(value)))


def _origin_key(origin):
    text = str(origin or "")
    if text.startswith("의미관계/"):
        return "의미관계"
    if text.startswith("말뭉치"):
        return "말뭉치 순서"
    if text.startswith("문맥"):
        return "문맥 활성"
    if text.startswith("연상"):
        return "연상 이웃"
    return text or "기타"


def _context_key(context_tokens, target):
    return context_map.context_signature(context_tokens, limit=6) + SEP + str(target)


def _transition_key(source, target):
    return str(source or "") + SEP + str(target or "")


def _active_data():
    return _ACTIVE.get("data") or _default()


def learned_adjustment(context_seeds, path, candidate):
    data = _active_data()
    target = candidate.get("token")
    context_tokens = list(context_seeds or []) + list(path or [])[-4:]
    transition = 0.0
    if path:
        transition = float((data.get("transitions", {}) or {}).get(_transition_key(path[-1], target), 0.0))
    context = float((data.get("context_targets", {}) or {}).get(_context_key(context_tokens, target), 0.0))
    origins = [_origin_key(x) for x in (candidate.get("origins") or [])]
    origin_values = [float((data.get("origins", {}) or {}).get(x, 0.0)) for x in origins]
    origin = sum(origin_values) / len(origin_values) if origin_values else 0.0
    total = transition + context + (0.45 * origin)
    return {
        "total": round(total, 6),
        "transition": round(transition, 6),
        "context": round(context, 6),
        "origin": round(origin, 6),
    }


def patch_wordmap(wordmap_gpt2):
    if getattr(wordmap_gpt2, "_credit_learning_patched", False):
        return
    original_score = wordmap_gpt2._score_candidates
    original_trace = wordmap_gpt2._trace_candidates

    def score_candidates(graph, context_seeds, path, surfaces):
        rows, state = original_score(graph, context_seeds, path, surfaces)
        for row in rows:
            learned = learned_adjustment(context_seeds, path, row)
            row["learning_adjustment"] = learned["total"]
            row["learning_components"] = learned
            row["raw_score"] = float(row.get("raw_score", 0)) + float(learned["total"])
        rows.sort(key=lambda x: (-float(x.get("raw_score", 0)), -float(x.get("probability", 0)), str(x.get("token", ""))))
        wordmap_gpt2._softmax(rows)
        return rows, state

    def trace_candidates(rows, limit=5):
        out = original_trace(rows, limit=limit)
        for item, row in zip(out, rows[:limit]):
            item["학습보정"] = round(float(row.get("learning_adjustment", 0)), 4)
            item["학습근거"] = dict(row.get("learning_components", {}))
        return out

    wordmap_gpt2._score_candidates = score_candidates
    wordmap_gpt2._trace_candidates = trace_candidates
    wordmap_gpt2._credit_learning_patched = True


def _trace_id(question, steps):
    payload = question + "|" + "|".join(str(step.get("선택", "")) for step in steps) + "|" + _now()
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def _record_pending(core, vault, result, question):
    data = _load(core, vault)
    steps = result.get("자동회귀생성과정") or []
    if not steps:
        _ACTIVE["data"] = data
        return None
    trace_id = _trace_id(question, steps)
    seeds = list(result.get("seed_tokens") or result.get("query_tokens") or [])
    generated = result.get("generated_sentences") or []
    top_text = generated[0].get("text") if generated else None
    compact_steps = []
    for step in steps:
        compact_steps.append({
            "단계": int(step.get("단계", len(compact_steps) + 1)),
            "이전문맥": list(step.get("이전문맥") or []),
            "선택": step.get("선택"),
            "선택확률": float(step.get("선택확률", 0)),
            "선택후보출처": list(step.get("선택후보출처") or []),
        })
    data.setdefault("pending", {})[trace_id] = {
        "id": trace_id,
        "created": _now(),
        "question": question,
        "seeds": seeds,
        "answer": top_text,
        "steps": compact_steps,
    }
    pending = data.get("pending", {})
    while len(pending) > MAX_PENDING:
        oldest = next(iter(pending))
        pending.pop(oldest, None)
    _save(core, vault, data)
    _ACTIVE["data"] = data
    return trace_id


def feedback(core, vault, trace_id, reward):
    reward = 1 if float(reward) > 0 else -1
    data = _load(core, vault)
    used = set(data.get("used_traces", []) or [])
    if trace_id in used:
        raise ValueError("이미 학습에 사용된 답변입니다.")
    trace = (data.get("pending", {}) or {}).get(str(trace_id or ""))
    if not trace:
        raise ValueError("학습할 답변 trace를 찾을 수 없습니다.")

    lr = float(data.get("learning_rate", DEFAULT_LR))
    steps = trace.get("steps", []) or []
    n = len(steps)
    changes = []

    for i, step in enumerate(steps):
        target = step.get("선택")
        prefix = list(step.get("이전문맥") or [])
        if not target:
            continue
        distance = max(0, n - 1 - i)
        confidence = 0.60 + (0.40 * max(0.0, min(1.0, float(step.get("선택확률", 0)))))
        credit = reward * lr * (TRACE_DECAY ** distance) * confidence

        if prefix:
            key = _transition_key(prefix[-1], target)
            old = float(data["transitions"].get(key, 0.0))
            data["transitions"][key] = round(_clamp(old + credit), 6)

        context_tokens = list(trace.get("seeds") or []) + prefix[-4:]
        ckey = _context_key(context_tokens, target)
        old = float(data["context_targets"].get(ckey, 0.0))
        data["context_targets"][ckey] = round(_clamp(old + credit), 6)

        origins = {_origin_key(x) for x in (step.get("선택후보출처") or [])}
        for origin in origins:
            old = float(data["origins"].get(origin, 0.0))
            data["origins"][origin] = round(_clamp(old + (credit * 0.30)), 6)

        changes.append({"단계": step.get("단계"), "선택": target, "credit": round(credit, 6)})

    data["updates"] = int(data.get("updates", 0)) + 1
    data["positive" if reward > 0 else "negative"] = int(data.get("positive" if reward > 0 else "negative", 0)) + 1
    data.setdefault("used_traces", []).append(trace_id)
    data["used_traces"] = data["used_traces"][-200:]
    data.get("pending", {}).pop(trace_id, None)
    data.setdefault("history", []).append({
        "time": _now(),
        "trace_id": trace_id,
        "reward": reward,
        "question": trace.get("question"),
        "answer": trace.get("answer"),
        "changes": changes,
    })
    data["history"] = data["history"][-MAX_HISTORY:]
    _save(core, vault, data)
    _ACTIVE["vault"] = str(vault)
    _ACTIVE["data"] = data
    return {
        "version": VERSION,
        "trace_id": trace_id,
        "reward": reward,
        "updated_steps": len(changes),
        "total_updates": data["updates"],
        "changes": changes,
    }


def learning_status(core, vault):
    data = _load(core, vault)
    return {
        "version": VERSION,
        "learning_rate": float(data.get("learning_rate", DEFAULT_LR)),
        "updates": int(data.get("updates", 0)),
        "positive": int(data.get("positive", 0)),
        "negative": int(data.get("negative", 0)),
        "learned_transitions": len(data.get("transitions", {}) or {}),
        "learned_context_targets": len(data.get("context_targets", {}) or {}),
        "learned_origins": len(data.get("origins", {}) or {}),
        "pending": len(data.get("pending", {}) or {}),
        "updated": data.get("updated"),
    }


def reset_learning(core, vault):
    data = _default()
    _save(core, vault, data)
    _ACTIVE["vault"] = str(vault)
    _ACTIVE["data"] = data
    return {"version": VERSION, "reset": True}


def make_ask(core, original_ask):
    def ask(vault, question, limit=20, depth=2):
        data = _load(core, vault)
        _ACTIVE["vault"] = str(vault)
        _ACTIVE["data"] = data
        result = original_ask(vault, question, limit=limit, depth=depth)
        trace_id = _record_pending(core, vault, result, question)
        result["learning_trace_id"] = trace_id
        result["credit_learning_version"] = VERSION
        result["학습상태"] = learning_status(core, vault)
        return result
    return ask


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if vault:
            learn = learning_status(core, Path(vault))
            out["credit_learning_version"] = VERSION
            out["learning_updates"] = learn["updates"]
            out["learned_transitions"] = learn["learned_transitions"]
        return out
    return status


def apply(core, wordmap_gpt2):
    patch_wordmap(wordmap_gpt2)
    original_ask = core.ask
    original_status = core.status
    core.ask = make_ask(core, original_ask)
    core.status = make_status(core, original_status)
    core.learning_feedback = lambda vault, trace_id, reward: feedback(core, vault, trace_id, reward)
    core.learning_status = lambda vault: learning_status(core, vault)
    core.learning_reset = lambda vault: reset_learning(core, vault)
    core.credit_learning_version = VERSION
    return core
