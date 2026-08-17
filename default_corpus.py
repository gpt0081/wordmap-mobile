from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

VERSION = "0.16.1"
BUNDLE_VERSION = "Corpus-v1-patched-2026-08-17"
STATE_FILE = "default_corpus.json"
BUNDLE_DIR = Path(__file__).resolve().parent / "bundled_corpus" / "v1"
TRAIN_NAMES = [
    "01_core_facts.md",
    "02_event_patterns.md",
    "03_paraphrases.md",
    "04_question_answer.md",
    "05_dialogue_basic.md",
    "06_dialogue_context.md",
    "07_negative_contrast.md",
    "08_cause_condition.md",
    "09_polysemy_context.md",
    "10_temporal_state.md",
    "11_cross_topic.md",
]
EVAL_NAMES = [
    "90_dev_questions.md",
    "91_test_questions.md",
    "90_dev_manifest.json",
    "91_test_manifest.json",
]
EXPECTED_TRAIN = {
    "01_core_facts.md": 200,
    "02_event_patterns.md": 280,
    "03_paraphrases.md": 180,
    "04_question_answer.md": 200,
    "05_dialogue_basic.md": 160,
    "06_dialogue_context.md": 120,
    "07_negative_contrast.md": 80,
    "08_cause_condition.md": 70,
    "09_polysemy_context.md": 70,
    "10_temporal_state.md": 50,
    "11_cross_topic.md": 90,
}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _sha_path(path):
    try:
        return _sha_bytes(Path(path).read_bytes())
    except FileNotFoundError:
        return None


def _state_path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / STATE_FILE


def _default_state():
    return {
        "version": VERSION,
        "bundle_version": BUNDLE_VERSION,
        "enabled": True,
        "files": {},
        "eval": {},
        "updated": None,
    }


def _load(core, vault):
    path = _state_path(core, vault)
    exists = path.exists()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = _default_state()
    base = _default_state()
    for key, value in base.items():
        data.setdefault(key, value)
    if not isinstance(data.get("files"), dict):
        data["files"] = {}
    if not isinstance(data.get("eval"), dict):
        data["eval"] = {}
    data["version"] = VERSION
    data["bundle_version"] = BUNDLE_VERSION
    data["_state_existed"] = exists
    return data


def _save(core, vault, data):
    clean = {k: v for k, v in data.items() if not str(k).startswith("_")}
    clean["version"] = VERSION
    clean["bundle_version"] = BUNDLE_VERSION
    clean["updated"] = _now()
    _state_path(core, vault).write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return clean


def _bundle_source(name):
    path = (BUNDLE_DIR / name).resolve()
    if path.parent != BUNDLE_DIR.resolve() or not path.is_file():
        raise RuntimeError(f"기본 Corpus 번들 파일이 없습니다: {name}")
    return path


def _question_count(path):
    return len([line for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()])


def validate_bundle(core):
    missing = [name for name in TRAIN_NAMES + EVAL_NAMES if not (BUNDLE_DIR / name).is_file()]
    if missing:
        raise RuntimeError("기본 Corpus 번들 누락: " + ", ".join(missing))
    counts = {}
    total = 0
    for name in TRAIN_NAMES:
        text = (BUNDLE_DIR / name).read_text(encoding="utf-8")
        count = len(core.split_sentences(text))
        counts[name] = count
        total += count
        if count != EXPECTED_TRAIN[name]:
            raise RuntimeError(f"기본 Corpus 문장 수 오류 {name}: {count} != {EXPECTED_TRAIN[name]}")
    if total != 1500:
        raise RuntimeError(f"기본 Corpus 총 문장 수 오류: {total} != 1500")
    dev = _question_count(BUNDLE_DIR / "90_dev_questions.md")
    test = _question_count(BUNDLE_DIR / "91_test_questions.md")
    if dev != 60 or test != 110:
        raise RuntimeError(f"기본 평가 질문 수 오류: DEV {dev}, TEST {test}")
    for name, expected in (("90_dev_manifest.json", 60), ("91_test_manifest.json", 110)):
        raw = json.loads((BUNDLE_DIR / name).read_text(encoding="utf-8"))
        if int(raw.get("question_count", -1)) != expected or len(raw.get("answers") or []) != expected:
            raise RuntimeError(f"기본 평가 manifest 오류: {name}")
        if raw.get("training") is not False:
            raise RuntimeError(f"평가 manifest training=false 필요: {name}")
    return {"version": VERSION, "bundle_version": BUNDLE_VERSION, "train": total, "dev": dev, "test": test, "counts": counts}


def _backup_conflict(core, vault, target, name):
    root = core.wordmap_dirs(vault)["meta"] / "backups" / "default_corpus_migration"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = root / f"{stamp}_{name}"
    shutil.copy2(target, backup)
    return str(backup)


def _looks_generated_v016(path):
    try:
        head = Path(path).read_text(encoding="utf-8", errors="replace")[:700]
    except Exception:
        return False
    return "type: corpus-v1" in head and "role: train" in head


def _sync_one(core, vault, source, target, row, force=False, allow_migrate=False):
    src_hash = _sha_path(source)
    current_hash = _sha_path(target)
    old_installed = row.get("installed_hash")
    result = {"name": target.name, "action": "unchanged", "source_hash": src_hash}

    if row.get("suppressed") and not force:
        result["action"] = "suppressed"
        return result

    if current_hash is None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        row.update(installed_hash=src_hash, user_modified=False, suppressed=False, synced=_now())
        result["action"] = "installed"
        return result

    if current_hash == src_hash:
        row.update(installed_hash=src_hash, user_modified=False, suppressed=False, synced=_now())
        return result

    if force or (old_installed and current_hash == old_installed):
        backup = _backup_conflict(core, vault, target, target.name) if force else None
        shutil.copy2(source, target)
        row.update(installed_hash=src_hash, user_modified=False, suppressed=False, synced=_now())
        result.update(action="restored" if force else "updated", backup=backup)
        return result

    # One-time migration from the v0.16 generated Corpus v1 to the user-supplied
    # patched bundle. The old file is backed up before replacement.
    if allow_migrate and not old_installed and _looks_generated_v016(target):
        backup = _backup_conflict(core, vault, target, target.name)
        shutil.copy2(source, target)
        row.update(installed_hash=src_hash, user_modified=False, suppressed=False, synced=_now(), migrated_from="v0.16-generated")
        result.update(action="migrated", backup=backup)
        return result

    row.update(user_modified=True, observed_hash=current_hash, source_hash=src_hash, synced=_now())
    result["action"] = "user_modified_preserved"
    return result


def sync(core, vault, force=False):
    validation = validate_bundle(core)
    state = _load(core, vault)
    if not state.get("enabled", True) and not force:
        state.pop("_state_existed", None)
        _save(core, vault, state)
        return {"version": VERSION, "enabled": False, "skipped": True, "validation": validation}

    first_sync = not bool(state.get("_state_existed"))
    dirs = core.wordmap_dirs(vault)
    eval_dir = dirs["meta"] / "Eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for name in TRAIN_NAMES:
        row = state["files"].setdefault(name, {})
        results.append(_sync_one(
            core, vault, _bundle_source(name), dirs["corpus"] / name, row,
            force=force, allow_migrate=first_sync,
        ))

    for name in EVAL_NAMES:
        row = state["eval"].setdefault(name, {})
        results.append(_sync_one(
            core, vault, _bundle_source(name), eval_dir / name, row,
            force=force, allow_migrate=False,
        ))

    state["enabled"] = True
    state.pop("_state_existed", None)
    _save(core, vault, state)
    actions = {}
    for item in results:
        actions[item["action"]] = actions.get(item["action"], 0) + 1
    return {
        "version": VERSION,
        "bundle_version": BUNDLE_VERSION,
        "enabled": True,
        "validation": validation,
        "actions": actions,
        "files": results,
    }


def status(core, vault):
    validation = validate_bundle(core)
    state = _load(core, vault)
    dirs = core.wordmap_dirs(vault)
    eval_dir = dirs["meta"] / "Eval"
    rows = []
    for name in TRAIN_NAMES:
        src_hash = _sha_path(BUNDLE_DIR / name)
        target = dirs["corpus"] / name
        target_hash = _sha_path(target)
        meta = state.get("files", {}).get(name, {}) or {}
        rows.append({
            "name": name,
            "kind": "train",
            "exists": target.exists(),
            "matches_bundle": bool(target_hash and target_hash == src_hash),
            "suppressed": bool(meta.get("suppressed")),
            "user_modified": bool(meta.get("user_modified")) or bool(target_hash and target_hash != src_hash),
        })
    for name in EVAL_NAMES:
        src_hash = _sha_path(BUNDLE_DIR / name)
        target = eval_dir / name
        target_hash = _sha_path(target)
        meta = state.get("eval", {}).get(name, {}) or {}
        rows.append({
            "name": name,
            "kind": "eval",
            "exists": target.exists(),
            "matches_bundle": bool(target_hash and target_hash == src_hash),
            "suppressed": bool(meta.get("suppressed")),
            "user_modified": bool(meta.get("user_modified")) or bool(target_hash and target_hash != src_hash),
        })
    return {
        "version": VERSION,
        "bundle_version": BUNDLE_VERSION,
        "enabled": bool(state.get("enabled", True)),
        "validation": validation,
        "managed": len(rows),
        "installed": sum(1 for row in rows if row["exists"]),
        "matching": sum(1 for row in rows if row["matches_bundle"]),
        "user_modified": sum(1 for row in rows if row["user_modified"]),
        "suppressed": sum(1 for row in rows if row["suppressed"]),
        "files": rows,
        "updated": state.get("updated"),
    }


def set_provisioning(core, vault, enabled):
    state = _load(core, vault)
    state["enabled"] = bool(enabled)
    state.pop("_state_existed", None)
    _save(core, vault, state)
    return {"version": VERSION, "enabled": bool(enabled), "note": "자동 공급 설정만 변경하며 각 파일의 Corpus ON/OFF 상태는 바꾸지 않습니다."}


def mark_suppressed(core, vault, name):
    if name not in TRAIN_NAMES:
        return
    state = _load(core, vault)
    row = state["files"].setdefault(name, {})
    row["suppressed"] = True
    row["user_modified"] = False
    state.pop("_state_existed", None)
    _save(core, vault, state)


def mark_modified(core, vault, name):
    if name not in TRAIN_NAMES:
        return
    state = _load(core, vault)
    row = state["files"].setdefault(name, {})
    row["user_modified"] = True
    row["suppressed"] = False
    state.pop("_state_existed", None)
    _save(core, vault, state)


def install_replace(core, vault, rebuild=True):
    dirs = core.wordmap_dirs(vault)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = dirs["meta"] / "backups" / f"corpus_before_bundled_v1_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for path in dirs["corpus"].glob("*"):
        if path.is_file():
            shutil.copy2(path, backup / path.name)
            if path.suffix.lower() in {".md", ".txt"}:
                path.unlink()
    eval_dir = dirs["meta"] / "Eval"
    if eval_dir.exists():
        eval_backup = backup / "Eval"
        eval_backup.mkdir(parents=True, exist_ok=True)
        for path in eval_dir.glob("*"):
            if path.is_file():
                shutil.copy2(path, eval_backup / path.name)

    try:
        import corpus_manager
        corpus_manager._save_registry(core, vault, corpus_manager._default_registry())
    except Exception:
        pass
    _save(core, vault, _default_state())
    synced = sync(core, vault, force=True)
    if hasattr(core, "learning_reset"):
        core.learning_reset(vault)
    result = {"installed": True, "backup": str(backup), "sync": synced, "rebuild_required": not rebuild}
    if rebuild:
        result["rebuild"] = core.rebuild_wordmap(vault)
    return result


def apply(core):
    old_rebuild = core.rebuild_wordmap
    old_status = core.status
    old_delete = getattr(core, "corpus_delete", None)
    old_delete_all = getattr(core, "corpus_delete_all", None)
    old_update = getattr(core, "corpus_update", None)

    def rebuild(vault, window=4):
        synced = sync(core, vault, force=False)
        result = old_rebuild(vault, window=window)
        result["default_corpus_version"] = VERSION
        result["default_corpus_bundle"] = BUNDLE_VERSION
        result["default_corpus_sync"] = synced.get("actions", {})
        return result

    def status_wrapped():
        out = old_status()
        vault = out.get("vault")
        if vault:
            info = status(core, Path(vault))
            out["default_corpus_version"] = VERSION
            out["default_corpus_bundle"] = BUNDLE_VERSION
            out["default_corpus_enabled"] = info["enabled"]
            out["default_corpus_matching"] = info["matching"]
        return out

    core.rebuild_wordmap = rebuild
    core.status = status_wrapped

    if old_delete:
        def delete(vault, name):
            result = old_delete(vault, name)
            mark_suppressed(core, vault, str(name))
            return result
        core.corpus_delete = delete

    if old_update:
        def update(vault, name, content):
            result = old_update(vault, name, content)
            mark_modified(core, vault, str(name))
            return result
        core.corpus_update = update

    if old_delete_all:
        def delete_all(vault):
            result = old_delete_all(vault)
            state = _default_state()
            state["enabled"] = False
            _save(core, vault, state)
            result["default_corpus_provisioning_disabled"] = True
            return result
        core.corpus_delete_all = delete_all

    core.default_corpus_sync = lambda vault, force=False: sync(core, vault, force=force)
    core.default_corpus_status = lambda vault: status(core, vault)
    core.default_corpus_set_enabled = lambda vault, enabled: set_provisioning(core, vault, enabled)
    core.default_corpus_restore = lambda vault: sync(core, vault, force=True)
    # From v0.16.1 the Corpus v1 install/replace action installs the bundled,
    # user-supplied patched corpus instead of regenerating a synthetic copy.
    core.corpus_v1_install = lambda vault, rebuild=True: install_replace(core, vault, rebuild=rebuild)
    core.default_corpus_version = VERSION
    return core
