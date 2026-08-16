from __future__ import annotations

import re
from pathlib import Path

VERSION = "0.16.0"
TRAIN = "train"
DEV = "dev"
TEST = "test"
EVAL = {DEV, TEST}
META_RE = re.compile(r"^\s*@@(?:dialogue|turn|session)\b.*$", re.I)
SPEAKER_RE = re.compile(r"^\s*(?:사용자|답변|user|assistant)\s*[:：]\s*", re.I)


def _parts(text):
    if not str(text).startswith("---"):
        return "", str(text)
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", str(text), flags=re.S)
    return (m.group(1), str(text)[m.end():]) if m else ("", str(text))


def role_from_text(text):
    fm, _ = _parts(text)
    m = re.search(r"(?mi)^role\s*:\s*[\"']?([a-z]+)", fm)
    role = m.group(1).lower() if m else TRAIN
    return role if role in {TRAIN, DEV, TEST} else TRAIN


def role_from_path(path):
    try:
        return role_from_text(Path(path).read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return TRAIN


def clean_training_body(text):
    out = []
    for raw in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if META_RE.match(raw):
            continue
        line = SPEAKER_RE.sub("", raw).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def apply(core):
    old_body = core.corpus_body
    old_list = core.corpus_list
    old_get = core.corpus_get
    old_set = core.corpus_set_enabled
    old_status = core.status

    def corpus_body(path):
        if role_from_path(path) != TRAIN:
            return ""
        return clean_training_body(old_body(path))

    def corpus_list(vault):
        result = old_list(vault)
        for row in result.get("documents", []):
            path = core.wordmap_dirs(vault)["corpus"] / row.get("name", "")
            role = role_from_path(path)
            row["role"] = role
            row["role_label"] = role.upper()
            row["training_locked"] = role in EVAL
            if role in EVAL:
                row["enabled"] = False
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
                _fm, body = _parts(raw)
                body = clean_training_body(body) if role == TRAIN else body
                row["sentences"] = len(core.split_sentences(body))
            except Exception:
                pass
        result["role_guard_version"] = VERSION
        return result

    def corpus_get(vault, name):
        result = old_get(vault, name)
        role = role_from_path(core.wordmap_dirs(vault)["corpus"] / str(name))
        result.update(role=role, role_label=role.upper(), training_locked=role in EVAL)
        if role in EVAL:
            result["enabled"] = False
        return result

    def set_enabled(vault, name, enabled):
        role = role_from_path(core.wordmap_dirs(vault)["corpus"] / str(name))
        if role in EVAL:
            if enabled:
                raise ValueError(f"{role.upper()} 평가 파일은 학습에 사용할 수 없습니다.")
            return {"name": name, "enabled": False, "role": role, "training_locked": True, "rebuild_required": False}
        return old_set(vault, name, enabled)

    def status():
        out = old_status()
        out["corpus_role_guard_version"] = VERSION
        return out

    core.corpus_body = corpus_body
    core.corpus_list = corpus_list
    core.corpus_get = corpus_get
    core.corpus_set_enabled = set_enabled
    core.status = status
    core.corpus_role = role_from_path
    core.clean_training_body = clean_training_body
    return core
