from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

VERSION = "0.16.0"
SIMILARITY_THRESHOLD = 0.86
MAX_EXAMPLES = 60
TIME_WORDS = ("아침", "오전", "점심", "오후", "저녁", "밤", "어제", "오늘", "현재", "지금", "처음", "이후", "다음")
TRANSIENT_OBJECTS = {"사과", "책", "열쇠", "공", "우산", "컵", "공책", "가방", "연필", "신발"}
TRANSIENT_PATTERN = "|".join(re.escape(x) for x in sorted(TRANSIENT_OBJECTS, key=len, reverse=True))
LOCATION_STATE_RE = re.compile(
    rf"(?:{TRANSIENT_PATTERN})(?:은|는|이|가)\s+"
    r".{0,35}?"
    r"(?:위|아래|안|밖|옆|앞|뒤)?에\s+"
    r"(?:있다|있었다|놓여\s*있다|보관되어\s*있다)"
)
POLYSEMY_GROUPS = {
    "배": ["과일", "선박", "신체", "복부", "항구", "바다"],
    "눈": ["시각", "사물", "눈송이", "겨울", "쌓"],
    "말": ["언어", "문장", "동물", "목장", "풀"],
    "사과": ["과일", "나무", "사과행위", "미안", "잘못"],
    "차": ["자동차", "도로", "음료", "컵", "찻잎"],
}


def normalize(text):
    text = str(text or "").lower().strip()
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return text


def token_set(text):
    return set(re.findall(r"[가-힣A-Za-z0-9]+", str(text or "").lower()))


def similarity(a, b):
    aa, bb = token_set(a), token_set(b)
    if len(aa) < 3 or len(bb) < 3:
        return 0.0
    inter = len(aa & bb)
    union = len(aa | bb)
    return inter / union if union else 0.0


def _role(path):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(?mi)^role\s*:\s*([a-z]+)", text)
        return m.group(1).lower() if m else "train"
    except Exception:
        return "train"


def _front_body(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if text.startswith("---"):
        m = re.match(r"^---\s*\n.*?\n---\s*\n", text, flags=re.S)
        if m:
            text = text[m.end():]
    return text


def _split_train(core, path):
    body = _front_body(path)
    if hasattr(core, "clean_training_body"):
        body = core.clean_training_body(body)
    return core.split_sentences(body)


def _manifest(core, vault, split):
    path = core.wordmap_dirs(vault)["meta"] / "Eval" / f"{'90_dev' if split == 'dev' else '91_test'}_manifest.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"items": []}


def _sets(core, vault):
    corpus = core.wordmap_dirs(vault)["corpus"]
    train = []
    for path in sorted(corpus.glob("*")):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"} and _role(path) == "train":
            train.extend((path.name, s) for s in _split_train(core, path) if s.strip())
    dev = [(item.get("id", "dev"), item.get("question", "")) for item in _manifest(core, vault, "dev").get("items", [])]
    test = [(item.get("id", "test"), item.get("question", "")) for item in _manifest(core, vault, "test").get("items", [])]
    return train, dev, test


def _exact_cross(a, b):
    right = {}
    for source, text in b:
        right.setdefault(normalize(text), []).append((source, text))
    found = []
    for source, text in a:
        key = normalize(text)
        if key and key in right:
            for rsource, rtext in right[key]:
                found.append({"left": source, "right": rsource, "left_text": text, "right_text": rtext})
                if len(found) >= MAX_EXAMPLES:
                    return found
    return found


def _similar_cross(a, b, threshold=SIMILARITY_THRESHOLD):
    found = []
    bsets = [(src, text, token_set(text)) for src, text in b]
    for asrc, atext in a:
        aset = token_set(atext)
        if len(aset) < 3:
            continue
        for bsrc, btext, bset in bsets:
            if len(bset) < 3:
                continue
            overlap = len(aset & bset)
            if overlap < 3:
                continue
            score = overlap / len(aset | bset)
            if score >= threshold and normalize(atext) != normalize(btext):
                found.append({"left": asrc, "right": bsrc, "score": round(score, 3), "left_text": atext, "right_text": btext})
                if len(found) >= MAX_EXAMPLES:
                    return found
    return found


def _repeat_warnings(train):
    counts = Counter(normalize(text) for _src, text in train if normalize(text))
    examples = []
    for key, count in counts.most_common():
        if count < 3:
            break
        example = next(text for _src, text in train if normalize(text) == key)
        examples.append({"count": count, "text": example})
        if len(examples) >= MAX_EXAMPLES:
            break
    return examples


def _temporal_warnings(train):
    found = []
    for source, text in train:
        if not LOCATION_STATE_RE.search(text):
            continue
        has_context = any(word in text for word in TIME_WORDS) or any(
            x in text for x in ("평소", "보관", "정리된 상태", "기본 보관", "보관 위치")
        )
        if not has_context:
            found.append({"source": source, "text": text})
            if len(found) >= MAX_EXAMPLES:
                break
    return found


def _polysemy_bridge_warnings(train):
    found = []
    for source, text in train:
        for word, markers in POLYSEMY_GROUPS.items():
            if word not in text:
                continue
            hits = [m for m in markers if m in text]
            if len(hits) >= 3 and ("다른 뜻" in text or ("의미" in text and "와" in text)):
                found.append({"source": source, "word": word, "markers": hits, "text": text})
                break
        if len(found) >= MAX_EXAMPLES:
            break
    return found


def _manifest_warnings(manifest):
    found = []
    for item in manifest.get("items", []):
        required = item.get("required") or []
        if not required:
            found.append({"id": item.get("id"), "issue": "required 정답 없음"})
        if len(set(required)) != len(required):
            found.append({"id": item.get("id"), "issue": "required 정답 중복"})
        if set(required) & set(item.get("forbidden") or []):
            found.append({"id": item.get("id"), "issue": "required/forbidden 충돌"})
    return found[:MAX_EXAMPLES]


def run(core, vault):
    train, dev, test = _sets(core, vault)
    train_dev_exact = _exact_cross(train, dev)
    train_test_exact = _exact_cross(train, test)
    dev_test_exact = _exact_cross(dev, test)
    train_dev_sim = _similar_cross(train, dev)
    train_test_sim = _similar_cross(train, test)
    dev_test_sim = _similar_cross(dev, test)
    repeats = _repeat_warnings(train)
    temporal = _temporal_warnings(train)
    poly = _polysemy_bridge_warnings(train)
    dev_manifest = _manifest(core, vault, "dev")
    test_manifest = _manifest(core, vault, "test")
    manifest_warnings = _manifest_warnings(dev_manifest) + _manifest_warnings(test_manifest)
    hard_fail = bool(train_dev_exact or train_test_exact or dev_test_exact or temporal or manifest_warnings)
    return {
        "version": VERSION,
        "ok": not hard_fail,
        "counts": {"train": len(train), "dev": len(dev), "test": len(test)},
        "exact": {
            "train_dev": len(train_dev_exact), "train_test": len(train_test_exact), "dev_test": len(dev_test_exact),
            "examples": {"train_dev": train_dev_exact, "train_test": train_test_exact, "dev_test": dev_test_exact},
        },
        "similar": {
            "threshold": SIMILARITY_THRESHOLD,
            "train_dev": len(train_dev_sim), "train_test": len(train_test_sim), "dev_test": len(dev_test_sim),
            "examples": {"train_dev": train_dev_sim, "train_test": train_test_sim, "dev_test": dev_test_sim},
        },
        "train_repeat_3plus": {"count": len(repeats), "examples": repeats},
        "temporal_without_context": {"count": len(temporal), "examples": temporal},
        "polysemy_direct_bridge": {"count": len(poly), "examples": poly},
        "manifest_warnings": {"count": len(manifest_warnings), "examples": manifest_warnings},
        "policy": "Exact split 누출·시간상태 무문맥·manifest 충돌은 실패, 유사문장·반복·다의어 브리지는 경고",
    }


def apply(core):
    core.corpus_integrity = lambda vault: run(core, vault)
    core.corpus_integrity_version = VERSION
    return core
