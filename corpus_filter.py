from __future__ import annotations

import re

VERSION = "0.10.0"

# These are document scaffolding labels observed in textbook-style corpora.
# They are removed only when a line is effectively just a label/heading.
META_LABELS = {
    "본문", "예시", "예제", "연습문제", "문제", "해설", "정답",
    "쉬움", "보통", "도전", "난이도", "학습목표", "핵심정리",
}

MARKDOWN_EDGE_RE = re.compile(r"^[\s#>*_`\-+\[\](){}0-9.:]+|[\s#>*_`\-+\[\](){}.:]+$")
DIFFICULTY_RE = re.compile(
    r"^\s*(?:난이도\s*[:：]?\s*)?(쉬움|보통|도전)\s*$",
    re.I,
)
LABEL_WITH_COLON_RE = re.compile(
    r"^\s*(본문|예시|예제|연습문제|문제|해설|정답|학습목표|핵심정리)\s*[:：]?\s*$",
    re.I,
)


def _plain_label(line: str) -> str:
    text = line.strip()
    text = re.sub(r"^#{1,6}\s*", "", text)
    text = re.sub(r"^[-*+>]\s*", "", text)
    text = re.sub(r"^\d+[.)]\s*", "", text)
    text = text.strip(" *_`[](){}:：.-")
    return text.strip()


def is_scaffolding_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    if DIFFICULTY_RE.fullmatch(text) or LABEL_WITH_COLON_RE.fullmatch(text):
        return True
    return _plain_label(text) in META_LABELS


def clean_text(text: str) -> str:
    """Return an analysis view of Corpus without mutating the source file."""
    out = []
    previous_blank = False
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if is_scaffolding_line(line):
            continue
        if not line.strip():
            if not previous_blank:
                out.append("")
            previous_blank = True
            continue
        previous_blank = False
        out.append(line)
    return "\n".join(out).strip()


def make_corpus_body(original):
    def corpus_body(path):
        return clean_text(original(path))
    return corpus_body


def make_status(original_status):
    def status():
        out = original_status()
        out["corpus_filter_version"] = VERSION
        return out
    return status


def apply(core):
    core.corpus_body = make_corpus_body(core.corpus_body)
    core.status = make_status(core.status)
    return core
