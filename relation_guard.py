from __future__ import annotations

import re

VERSION = "0.10.0"

LINGUISTIC_TERMS = r"명사|동사|형용사|부사|관형사|조사|어미|품사|표제어|낱말|단어|문법|문장"
META_RE = re.compile(
    rf"(?:라는|이라고|이라는|라면|표현|뜻|의미|문법|품사).*?(?:{LINGUISTIC_TERMS})|"
    rf"(?:{LINGUISTIC_TERMS}).*?(?:라고|라는|이라고|포함한다|부른다|뜻한다|표현한다)",
    re.I,
)


def is_metalinguistic(sentence: str) -> bool:
    text = re.sub(r"\s+", " ", sentence).strip()
    if not text:
        return False
    return bool(META_RE.search(text))


def apply(relations_module):
    original = relations_module.extract_relations
    if getattr(relations_module, "_v010_relation_guard", False):
        return relations_module

    def extract_relations(core, text):
        found = []
        for sentence in core.split_sentences(text):
            if is_metalinguistic(sentence):
                continue
            found.extend(original(core, sentence))
        return found

    relations_module.extract_relations = extract_relations
    relations_module._v010_relation_guard = True
    relations_module.RELATION_GUARD_VERSION = VERSION
    return relations_module
