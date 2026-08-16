from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

VERSION = "0.16.0"
STATE_FILE = "dialogue_state.json"
MAX_CONTEXT = 14
MAX_TURNS = 12
CONTEXT_HINT_RE = re.compile(r"거기|그곳|그걸|그것|그 사람|그 다음|그는|그녀|걔|뭘|뭐 해|어디 있어|그중|그때")


def _path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / STATE_FILE


def _default():
    return {"version": VERSION, "session_id": "web", "active": False, "context_tokens": [], "turns": [], "updated": None}


def _load(core, vault):
    path = _path(core, vault)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = _default()
    for k, v in _default().items():
        data.setdefault(k, v)
    data["version"] = VERSION
    return data


def _save(core, vault, data):
    data["version"] = VERSION
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    _path(core, vault).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def start(core, vault, session_id="web"):
    data = _default()
    data["active"] = True
    data["session_id"] = str(session_id or "web")
    _save(core, vault, data)
    return status(core, vault)


def reset(core, vault):
    data = _default()
    _save(core, vault, data)
    return status(core, vault)


def status(core, vault):
    data = _load(core, vault)
    return {
        "version": VERSION,
        "session_id": data.get("session_id"),
        "active": bool(data.get("active")),
        "context_tokens": list(data.get("context_tokens") or []),
        "turn_count": len(data.get("turns") or []),
        "updated": data.get("updated"),
    }


def _merge_tokens(current, incoming):
    out = list(current or [])
    for token in incoming or []:
        if not token:
            continue
        if token in out:
            out.remove(token)
        out.append(token)
    return out[-MAX_CONTEXT:]


def prime(core, vault, text):
    data = _load(core, vault)
    if not data.get("active"):
        data["active"] = True
    tokens = core.tokenize(str(text or ""))
    data["context_tokens"] = _merge_tokens(data.get("context_tokens"), tokens)
    data.setdefault("turns", []).append({"type": "prime", "text": str(text or "")[:240]})
    data["turns"] = data["turns"][-MAX_TURNS:]
    _save(core, vault, data)
    return status(core, vault)


def _should_use_context(core, question, data):
    if not data.get("active") or not data.get("context_tokens"):
        return False
    if CONTEXT_HINT_RE.search(str(question or "")):
        return True
    tokens = core.tokenize(str(question or ""))
    return len(tokens) <= 2


def _result_tokens(result):
    out = []
    situation = result.get("상황문맥") or {}
    out.extend(situation.get("핵심노드") or [])
    out.extend(result.get("seed_tokens") or [])
    generated = result.get("generated_sentences") or []
    if generated:
        out.extend((generated[0] or {}).get("path") or [])
    seen = []
    for token in out:
        if token and token not in seen:
            seen.append(token)
    return seen


def apply(core):
    old_ask = core.ask
    old_status = core.status

    def ask(vault, question, limit=20, depth=2):
        data = _load(core, vault)
        use_context = _should_use_context(core, question, data)
        context = list(data.get("context_tokens") or [])
        effective = str(question or "")
        if use_context:
            prefix = " ".join(context[-8:])
            effective = (prefix + " " + effective).strip()
        result = old_ask(vault, effective, limit=limit, depth=depth)
        result["원질문"] = question
        result["세션보강질문"] = effective if use_context else None
        result["question"] = question
        learned = _result_tokens(result)
        if not data.get("active"):
            data["active"] = True
        data["context_tokens"] = _merge_tokens(context, core.tokenize(str(question or "")) + learned)
        data.setdefault("turns", []).append({
            "type": "ask", "question": str(question or "")[:240], "used_context": use_context,
            "context_before": context[-8:], "context_after": data["context_tokens"][-8:],
        })
        data["turns"] = data["turns"][-MAX_TURNS:]
        _save(core, vault, data)
        result["대화세션"] = {
            "version": VERSION,
            "active": True,
            "session_id": data.get("session_id"),
            "문맥사용": use_context,
            "이전문맥": context[-8:],
            "현재문맥": data["context_tokens"][-8:],
        }
        return result

    def system_status():
        out = old_status()
        vault = out.get("vault")
        if vault:
            s = status(core, Path(vault))
            out["dialogue_session_version"] = VERSION
            out["dialogue_session_active"] = s["active"]
            out["dialogue_turns"] = s["turn_count"]
        return out

    core.ask = ask
    core.status = system_status
    core.dialogue_start = lambda vault, session_id="web": start(core, vault, session_id)
    core.dialogue_reset = lambda vault: reset(core, vault)
    core.dialogue_prime = lambda vault, text: prime(core, vault, text)
    core.dialogue_status = lambda vault: status(core, vault)
    core.dialogue_session_version = VERSION
    return core
