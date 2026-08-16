from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

VERSION = "0.16.0"
CHECKPOINTS = {0: "B0", 50: "B1", 100: "B2", 200: "B3"}


def _meta(core, vault):
    return core.wordmap_dirs(vault)["meta"]


def _eval_dir(core, vault):
    p = _meta(core, vault) / "Eval"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _exp_dir(core, vault):
    p = _meta(core, vault) / "experiments"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _manifest(core, vault, split):
    filename = "90_dev_manifest.json" if split == "dev" else "91_test_manifest.json"
    path = _eval_dir(core, vault) / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{split.upper()} manifest를 찾을 수 없습니다. Corpus v1을 먼저 설치하세요.") from exc
    if not isinstance(data.get("items"), list):
        raise ValueError("평가 manifest 형식이 잘못되었습니다.")
    return data


def _answer_text(result):
    generated = result.get("generated_sentences") or []
    if generated:
        text = str((generated[0] or {}).get("text") or "").strip()
        if text:
            return text
    situation = result.get("상황답변") or {}
    evidence = str(situation.get("근거문장") or "").strip()
    if evidence:
        return evidence
    values = situation.get("값") or []
    return " ".join(map(str, values)).strip()


def judge(item, result):
    answer = _answer_text(result)
    if not answer:
        return "무응답", answer
    low = answer.lower()
    required = [str(x).lower() for x in (item.get("required") or []) if str(x).strip()]
    forbidden = [str(x).lower() for x in (item.get("forbidden") or []) if str(x).strip()]
    hits = [x for x in required if x in low]
    bad = [x for x in forbidden if x in low]
    category = item.get("category")
    if category == "polysemy":
        correct = bool(hits)
    else:
        correct = bool(required) and len(hits) == len(required)
    if correct and not bad:
        return "정답", answer
    if hits and not bad:
        return "부분정답", answer
    question_terms = set(str(item.get("question", "")).replace("?", "").split())
    answer_terms = set(answer.replace(".", "").split())
    overlap = len(question_terms & answer_terms)
    if bad or (len(answer_terms) >= 3 and overlap == 0 and not hits):
        return "주제이탈", answer
    return "오답", answer


def _learning_path(core, vault):
    return _meta(core, vault) / "learning.json"


def _preserve_learning(core, vault):
    path = _learning_path(core, vault)
    return path.read_bytes() if path.exists() else None


def _restore_learning(core, vault, raw):
    path = _learning_path(core, vault)
    if raw is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    else:
        path.write_bytes(raw)
    try:
        import credit_learning
        credit_learning._ACTIVE["vault"] = str(vault)
        credit_learning._ACTIVE["data"] = credit_learning._load(core, vault)
    except Exception:
        pass


def _metrics(items, details):
    total = len(details)
    verdicts = Counter(row["verdict"] for row in details)
    correct = verdicts["정답"]
    by_cat = defaultdict(lambda: [0, 0])
    target = [0, 0]
    non_target = [0, 0]
    context = [0, 0]
    poly = [0, 0]
    wrong_answers = []
    item_map = {item.get("id"): item for item in items}
    for row in details:
        item = item_map.get(row["id"], {})
        cat = item.get("category", "unknown")
        by_cat[cat][1] += 1
        if row["verdict"] == "정답":
            by_cat[cat][0] += 1
        bucket = target if item.get("target") else non_target
        bucket[1] += 1
        bucket[0] += int(row["verdict"] == "정답")
        if item.get("context_required"):
            context[1] += 1
            context[0] += int(row["verdict"] == "정답")
        if cat == "polysemy":
            poly[1] += 1
            poly[0] += int(row["verdict"] == "정답")
        if row["verdict"] not in {"정답", "부분정답"} and row.get("answer"):
            wrong_answers.append(row["answer"])
    repeated = Counter(wrong_answers)
    repeated_wrong = sum(count - 1 for count in repeated.values() if count > 1)
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "partial": verdicts["부분정답"],
        "wrong": verdicts["오답"],
        "topic_drift": verdicts["주제이탈"],
        "no_answer": verdicts["무응답"],
        "topic_drift_rate": round(verdicts["주제이탈"] / total, 4) if total else 0.0,
        "same_wrong_repeat_rate": round(repeated_wrong / max(1, len(wrong_answers)), 4),
        "context_accuracy": round(context[0] / context[1], 4) if context[1] else None,
        "polysemy_accuracy": round(poly[0] / poly[1], 4) if poly[1] else None,
        "target_accuracy": round(target[0] / target[1], 4) if target[1] else None,
        "non_target_accuracy": round(non_target[0] / non_target[1], 4) if non_target[1] else None,
        "categories": {cat: {"correct": v[0], "total": v[1], "accuracy": round(v[0] / v[1], 4) if v[1] else 0.0} for cat, v in sorted(by_cat.items())},
    }


def _checkpoint_label(core, vault):
    updates = int((core.learning_status(vault) if hasattr(core, "learning_status") else {}).get("updates", 0))
    return CHECKPOINTS.get(updates, f"U{updates}"), updates


def _baseline_details(core, vault, split):
    path = _exp_dir(core, vault) / f"B0_{split}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("details", [])
    except Exception:
        return []


def _compare_baseline(core, vault, split, items, details):
    baseline = {row.get("id"): row.get("verdict") for row in _baseline_details(core, vault, split)}
    item_map = {item.get("id"): item for item in items}
    if not baseline:
        return {"regression_count": 0, "transfer_gain": 0}
    regression = 0
    transfer = 0
    for row in details:
        old = baseline.get(row["id"])
        new = row.get("verdict")
        if old == "정답" and new != "정답":
            regression += 1
        if old != "정답" and new == "정답" and not item_map.get(row["id"], {}).get("target"):
            transfer += 1
    return {"regression_count": regression, "transfer_gain": transfer}


def snapshot_learning(core, vault, label=None):
    if label is None:
        label, updates = _checkpoint_label(core, vault)
    else:
        updates = int(core.learning_status(vault).get("updates", 0)) if hasattr(core, "learning_status") else 0
    src = _learning_path(core, vault)
    dst = _exp_dir(core, vault) / f"{label}_learning.json"
    if src.exists():
        shutil.copy2(src, dst)
    else:
        dst.write_text(json.dumps({"version": VERSION, "updates": updates}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"label": label, "updates": updates, "path": str(dst)}


def run_benchmark(core, vault, split="dev", label=None):
    if split not in {"dev", "test"}:
        raise ValueError("split은 dev 또는 test여야 합니다.")
    manifest = _manifest(core, vault, split)
    items = manifest.get("items", [])
    saved_learning = _preserve_learning(core, vault)
    details = []
    try:
        for item in items:
            if hasattr(core, "dialogue_reset"):
                core.dialogue_reset(vault)
                core.dialogue_start(vault, f"bench-{item.get('id')}")
                for context in item.get("context") or []:
                    core.dialogue_prime(vault, context)
            try:
                result = core.ask(vault, item.get("question", ""), limit=8, depth=2)
                verdict, answer = judge(item, result)
            except Exception as exc:
                verdict, answer = "무응답", ""
                result = {"benchmark_error": str(exc)}
            details.append({
                "id": item.get("id"), "category": item.get("category"), "target": bool(item.get("target")),
                "verdict": verdict, "answer": answer, "question": item.get("question"),
                "required": item.get("required") or [], "forbidden": item.get("forbidden") or [],
            })
    finally:
        _restore_learning(core, vault, saved_learning)
        if hasattr(core, "dialogue_reset"):
            core.dialogue_reset(vault)
    metrics = _metrics(items, details)
    compare = _compare_baseline(core, vault, split, items, details)
    metrics.update(compare)
    if label is None:
        label, updates = _checkpoint_label(core, vault)
    else:
        updates = int(core.learning_status(vault).get("updates", 0)) if hasattr(core, "learning_status") else 0
    result = {
        "version": VERSION, "split": split, "label": label, "feedback_updates": updates,
        "ran_at": datetime.now().isoformat(timespec="seconds"), "metrics": metrics, "details": details,
    }
    (_exp_dir(core, vault) / f"{label}_{split}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run_pair(core, vault, label=None):
    if label is None:
        label, _updates = _checkpoint_label(core, vault)
    return {"label": label, "dev": run_benchmark(core, vault, "dev", label), "test": run_benchmark(core, vault, "test", label)}


def start_experiment(core, vault):
    if hasattr(core, "learning_reset"):
        core.learning_reset(vault)
    snapshot_learning(core, vault, "B0")
    return run_pair(core, vault, "B0")


def feedback_to(core, vault, target_updates):
    target_updates = int(target_updates)
    if target_updates not in {50, 100, 200}:
        raise ValueError("Feedback 목표는 50, 100, 200 중 하나여야 합니다.")
    manifest = _manifest(core, vault, "dev")
    targets = [item for item in manifest.get("items", []) if item.get("target")]
    if not targets:
        raise ValueError("Dev manifest에 target 문항이 없습니다.")
    status = core.learning_status(vault)
    updates = int(status.get("updates", 0))
    if updates > target_updates:
        raise ValueError("현재 Feedback 수가 목표보다 큽니다. B0에서 다시 시작하세요.")
    attempts = 0
    index = 0
    max_attempts = max(200, (target_updates - updates) * 8)
    while updates < target_updates and attempts < max_attempts:
        item = targets[index % len(targets)]
        index += 1
        attempts += 1
        if hasattr(core, "dialogue_reset"):
            core.dialogue_reset(vault)
            core.dialogue_start(vault, f"feedback-{updates+1}")
            for context in item.get("context") or []:
                core.dialogue_prime(vault, context)
        result = core.ask(vault, item.get("question", ""), limit=8, depth=2)
        trace_id = result.get("learning_trace_id")
        if not trace_id:
            continue
        verdict, _answer = judge(item, result)
        reward = 1 if verdict == "정답" else -1
        core.learning_feedback(vault, trace_id, reward)
        updates = int(core.learning_status(vault).get("updates", 0))
    if updates < target_updates:
        raise RuntimeError(f"Feedback trace가 부족해 {target_updates}회에 도달하지 못했습니다: {updates}")
    label = CHECKPOINTS[target_updates]
    snapshot_learning(core, vault, label)
    pair = run_pair(core, vault, label)
    return {"version": VERSION, "label": label, "updates": updates, "attempts": attempts, "benchmark": pair}


def status(core, vault):
    learning = core.learning_status(vault) if hasattr(core, "learning_status") else {"updates": 0}
    exp = _exp_dir(core, vault)
    files = sorted(path.name for path in exp.glob("B*_*json"))
    return {"version": VERSION, "learning_updates": int(learning.get("updates", 0)), "files": files, "checkpoints": CHECKPOINTS}


def apply(core):
    old_feedback = core.learning_feedback if hasattr(core, "learning_feedback") else None
    if old_feedback:
        def feedback(vault, trace_id, reward):
            result = old_feedback(vault, trace_id, reward)
            updates = int(result.get("total_updates", 0))
            if updates in CHECKPOINTS and updates != 0:
                snapshot_learning(core, vault, CHECKPOINTS[updates])
            return result
        core.learning_feedback = feedback
    core.benchmark_run = lambda vault, split="dev", label=None: run_benchmark(core, vault, split, label)
    core.benchmark_run_pair = lambda vault, label=None: run_pair(core, vault, label)
    core.experiment_start = lambda vault: start_experiment(core, vault)
    core.experiment_feedback_to = lambda vault, target: feedback_to(core, vault, target)
    core.experiment_status = lambda vault: status(core, vault)
    core.experiment_snapshot = lambda vault, label=None: snapshot_learning(core, vault, label)
    core.experiment_harness_version = VERSION
    return core
