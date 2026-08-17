from __future__ import annotations

import json
import re
from pathlib import Path

VERSION = "0.16.1"

CATEGORY_MAP = {
    "fact_recall": "fact",
    "event_role": "event_role",
    "paraphrase": "paraphrase",
    "unseen_paraphrase": "paraphrase",
    "context": "context",
    "context_reasoning": "context",
    "pronoun_ellipsis": "context",
    "polysemy": "polysemy",
    "polysemy_context": "polysemy",
    "negative_contrast": "negative",
    "cause_condition": "cause",
    "temporal_state": "temporal",
    "composition_generalization": "composition",
}


def _eval_dir(core, vault):
    path = core.wordmap_dirs(vault)["meta"] / "Eval"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(core, vault, split):
    if split not in {"dev", "test"}:
        raise ValueError("split은 dev 또는 test여야 합니다.")
    name = "90_dev_manifest.json" if split == "dev" else "91_test_manifest.json"
    return _eval_dir(core, vault) / name


def _category_for_line(categories, line_no):
    for raw_name, bounds in (categories or {}).items():
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            continue
        try:
            start, end = int(bounds[0]), int(bounds[1])
        except Exception:
            continue
        if start <= line_no <= end:
            key = re.sub(r"^[A-Z]_", "", str(raw_name))
            return CATEGORY_MAP.get(key, key)
    return "unknown"


def _question_lines(path):
    try:
        return [
            line.strip()
            for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        raise ValueError(f"평가 질문 파일을 읽을 수 없습니다: {path.name}") from exc


def _answer_required(answer):
    if isinstance(answer, list):
        return [str(x).strip() for x in answer if str(x).strip()]
    text = str(answer or "").strip()
    return [text] if text else []


def load(core, vault, split):
    path = _manifest_path(core, vault, split)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{split.upper()} manifest를 찾을 수 없습니다. 기본 Corpus를 먼저 동기화하세요.") from exc

    if isinstance(raw.get("items"), list):
        out = dict(raw)
        out.setdefault("version", VERSION)
        out.setdefault("split", split)
        return out

    answers = raw.get("answers")
    if not isinstance(answers, list):
        raise ValueError("평가 manifest에 items 또는 answers 배열이 필요합니다.")

    question_file = str(raw.get("question_file") or ("90_dev_questions.md" if split == "dev" else "91_test_questions.md"))
    questions = _question_lines(_eval_dir(core, vault) / question_file)
    expected = int(raw.get("question_count", len(answers)))
    if len(questions) != expected:
        raise ValueError(f"{split.upper()} 질문 수 불일치: 파일 {len(questions)} / manifest {expected}")
    if len(answers) != expected:
        raise ValueError(f"{split.upper()} 정답 수 불일치: {len(answers)} / manifest {expected}")

    items = []
    for index, answer in enumerate(answers, start=1):
        if not isinstance(answer, dict):
            raise ValueError(f"{split.upper()} answer #{index} 형식이 잘못되었습니다.")
        line_no = int(answer.get("line", index))
        if line_no < 1 or line_no > len(questions):
            raise ValueError(f"{split.upper()} answer #{index} line 범위 오류: {line_no}")
        category = _category_for_line(raw.get("categories"), line_no)
        required = _answer_required(answer.get("answer"))
        if not required:
            raise ValueError(f"{answer.get('id', index)} 정답이 비어 있습니다.")
        items.append({
            "id": str(answer.get("id") or f"{split.upper()}-{line_no:03d}"),
            "category": category,
            "question": questions[line_no - 1],
            "required": required,
            "forbidden": list(answer.get("forbidden") or []),
            "context": list(answer.get("context") or []),
            "context_required": category in {"context", "temporal"},
            # Only DEV may provide teacher feedback. TEST is always evaluation-only.
            "target": bool(split == "dev" and ((line_no - 1) % 3 == 0)),
            "source_line": line_no,
            "source_manifest_schema": "answers_v1",
        })

    return {
        **raw,
        "version": VERSION,
        "split": split,
        "count": len(items),
        "items": items,
    }


def summary(core, vault):
    dev = load(core, vault, "dev")
    test = load(core, vault, "test")
    return {
        "version": VERSION,
        "dev": len(dev.get("items", [])),
        "test": len(test.get("items", [])),
        "test_frozen": bool(test.get("frozen", False)),
    }
