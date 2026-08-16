from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

VERSION = "0.13.0"
REGISTRY_FILE = "corpus_registry.json"
ALLOWED_SUFFIXES = {".md", ".txt"}


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _registry_path(core, vault):
    return core.wordmap_dirs(vault)["meta"] / REGISTRY_FILE


def _default_registry():
    return {
        "version": VERSION,
        "dirty": False,
        "updated": None,
        "files": {},
    }


def _load_registry(core, vault):
    path = _registry_path(core, vault)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = _default_registry()
    data.setdefault("version", VERSION)
    data.setdefault("dirty", False)
    data.setdefault("updated", None)
    data.setdefault("files", {})
    if not isinstance(data["files"], dict):
        data["files"] = {}
    return data


def _save_registry(core, vault, data):
    data["version"] = VERSION
    data["updated"] = _now()
    _registry_path(core, vault).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return data


def _corpus_files(core, vault):
    corpus = core.wordmap_dirs(vault)["corpus"]
    return sorted(
        [
            path
            for path in corpus.iterdir()
            if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES
        ],
        key=lambda p: p.name,
    )


def _safe_document_path(core, vault, name):
    name = str(name or "")
    if not name or Path(name).name != name:
        raise ValueError("잘못된 말뭉치 파일 이름입니다.")
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(".md 또는 .txt 말뭉치만 관리할 수 있습니다.")
    corpus = core.wordmap_dirs(vault)["corpus"].resolve()
    path = (corpus / name).resolve()
    if path.parent != corpus:
        raise ValueError("Corpus 폴더 밖의 파일은 수정할 수 없습니다.")
    return path


def _split_frontmatter(text):
    if text.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n", text, flags=re.S)
        if match:
            return text[:match.end()], text[match.end():]
    return "", text


def _raw_document(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    frontmatter, body = _split_frontmatter(text)
    return frontmatter, body


def _source_from_frontmatter(frontmatter, fallback):
    match = re.search(r"(?mi)^source\s*:\s*[\"']?([^\n\"']+)", frontmatter or "")
    return match.group(1).strip() if match else fallback


def _enabled_from_registry(registry, name):
    row = (registry.get("files", {}) or {}).get(name, {}) or {}
    return bool(row.get("enabled", True))


def document_enabled(core, vault, name):
    return _enabled_from_registry(_load_registry(core, vault), str(name))


def list_documents(core, vault):
    registry = _load_registry(core, vault)
    rows = []
    active = 0
    for path in _corpus_files(core, vault):
        frontmatter, body = _raw_document(path)
        enabled = _enabled_from_registry(registry, path.name)
        active += int(enabled)
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
            size = int(path.stat().st_size)
        except OSError:
            modified = None
            size = 0
        rows.append({
            "name": path.name,
            "source": _source_from_frontmatter(frontmatter, path.stem),
            "enabled": enabled,
            "size_bytes": size,
            "characters": len(body),
            "sentences": len(core.split_sentences(body)),
            "modified": modified,
        })
    return {
        "version": VERSION,
        "documents": rows,
        "total": len(rows),
        "enabled": active,
        "disabled": len(rows) - active,
        "dirty": bool(registry.get("dirty", False)),
        "registry_updated": registry.get("updated"),
    }


def get_document(core, vault, name):
    path = _safe_document_path(core, vault, name)
    if not path.is_file():
        raise ValueError("말뭉치 파일을 찾을 수 없습니다.")
    frontmatter, body = _raw_document(path)
    registry = _load_registry(core, vault)
    return {
        "name": path.name,
        "source": _source_from_frontmatter(frontmatter, path.stem),
        "enabled": _enabled_from_registry(registry, path.name),
        "content": body,
        "characters": len(body),
        "sentences": len(core.split_sentences(body)),
    }


def _mark_dirty(core, vault, registry=None):
    registry = registry or _load_registry(core, vault)
    registry["dirty"] = True
    return _save_registry(core, vault, registry)


def _mark_clean(core, vault):
    registry = _load_registry(core, vault)
    registry["dirty"] = False
    return _save_registry(core, vault, registry)


def set_enabled(core, vault, name, enabled):
    path = _safe_document_path(core, vault, name)
    if not path.is_file():
        raise ValueError("말뭉치 파일을 찾을 수 없습니다.")
    registry = _load_registry(core, vault)
    row = registry["files"].setdefault(path.name, {})
    row["enabled"] = bool(enabled)
    row["changed"] = _now()
    _mark_dirty(core, vault, registry)
    return {
        "name": path.name,
        "enabled": bool(enabled),
        "rebuild_required": True,
    }


def update_document(core, vault, name, content):
    path = _safe_document_path(core, vault, name)
    if not path.is_file():
        raise ValueError("말뭉치 파일을 찾을 수 없습니다.")
    if not isinstance(content, str):
        raise ValueError("말뭉치 내용은 문자열이어야 합니다.")
    frontmatter, _old_body = _raw_document(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(frontmatter + content, encoding="utf-8")
    temp.replace(path)
    _mark_dirty(core, vault)
    return {
        "name": path.name,
        "characters": len(content),
        "sentences": len(core.split_sentences(content)),
        "rebuild_required": True,
    }


def delete_document(core, vault, name):
    path = _safe_document_path(core, vault, name)
    if not path.is_file():
        raise ValueError("말뭉치 파일을 찾을 수 없습니다.")
    path.unlink()
    registry = _load_registry(core, vault)
    registry.get("files", {}).pop(path.name, None)
    _mark_dirty(core, vault, registry)
    remaining = len(_corpus_files(core, vault))
    if remaining == 0:
        _clear_generated(core, vault)
        _mark_clean(core, vault)
    return {
        "deleted": path.name,
        "remaining": remaining,
        "rebuild_required": remaining > 0,
    }


def _clear_generated(core, vault):
    d = core.wordmap_dirs(vault)
    for old_note in d["words"].glob("*.md"):
        try:
            old_note.unlink()
        except FileNotFoundError:
            pass
    graph = core.empty_graph()
    graph["updated"] = _now()
    core.save_graph(vault, graph)
    lexicon_path = d["meta"] / "lexicon.json"
    try:
        lexicon_path.unlink()
    except FileNotFoundError:
        pass
    try:
        import language
        language._set({
            "version": getattr(language, "VERSION", "unknown"),
            "entries": {},
            "surface_index": {},
            "stats": {},
        })
    except Exception:
        pass


def delete_all(core, vault):
    files = _corpus_files(core, vault)
    deleted = []
    for path in files:
        try:
            path.unlink()
            deleted.append(path.name)
        except FileNotFoundError:
            pass
    _clear_generated(core, vault)
    registry = _default_registry()
    _save_registry(core, vault, registry)
    return {
        "deleted_count": len(deleted),
        "deleted": deleted,
        "rebuild_required": False,
        "wordmap_cleared": True,
    }


def _registry_for_corpus_path(path):
    path = Path(path)
    try:
        registry_path = path.parent.parent / REGISTRY_FILE
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def make_corpus_body(original_corpus_body):
    def corpus_body(path):
        registry = _registry_for_corpus_path(path)
        if not _enabled_from_registry(registry, Path(path).name):
            return ""
        return original_corpus_body(path)
    return corpus_body


def make_rebuild(core, original_rebuild):
    def rebuild(vault, window=4):
        docs = _corpus_files(core, vault)
        registry = _load_registry(core, vault)
        active = [path for path in docs if _enabled_from_registry(registry, path.name)]
        if not active:
            _clear_generated(core, vault)
            _mark_clean(core, vault)
            return {
                "rebuilt": True,
                "corpus_preserved": True,
                "documents": 0,
                "corpus_total_documents": len(docs),
                "corpus_disabled_documents": len(docs),
                "sentences": 0,
                "tokens": 0,
                "total_nodes": 0,
                "total_pairs": 0,
                "vault": str(vault),
                "warning": "활성화된 말뭉치가 없어 WordMap을 비웠습니다.",
            }
        result = original_rebuild(vault, window=window)
        _mark_clean(core, vault)
        result["corpus_total_documents"] = len(docs)
        result["corpus_active_documents"] = len(active)
        result["corpus_disabled_documents"] = len(docs) - len(active)
        result["corpus_manager_version"] = VERSION
        return result
    return rebuild


def make_status(core, original_status):
    def status():
        out = original_status()
        vault = out.get("vault")
        if not vault:
            return out
        summary = list_documents(core, Path(vault))
        out["corpus_documents"] = summary["total"]
        out["corpus_enabled"] = summary["enabled"]
        out["corpus_disabled"] = summary["disabled"]
        out["corpus_dirty"] = summary["dirty"]
        out["corpus_manager_version"] = VERSION
        return out
    return status


def apply(core):
    original_corpus_body = core.corpus_body
    original_rebuild = core.rebuild_wordmap
    original_status = core.status

    core.corpus_body = make_corpus_body(original_corpus_body)
    core.rebuild_wordmap = make_rebuild(core, original_rebuild)
    core.status = make_status(core, original_status)

    core.corpus_list = lambda vault: list_documents(core, vault)
    core.corpus_get = lambda vault, name: get_document(core, vault, name)
    core.corpus_set_enabled = lambda vault, name, enabled: set_enabled(core, vault, name, enabled)
    core.corpus_update = lambda vault, name, content: update_document(core, vault, name, content)
    core.corpus_delete = lambda vault, name: delete_document(core, vault, name)
    core.corpus_delete_all = lambda vault: delete_all(core, vault)
    core.corpus_manager_version = VERSION
    return core
