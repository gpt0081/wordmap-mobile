from __future__ import annotations

import re
from collections import Counter, defaultdict

VERSION = "0.5.0"

WORD_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9_+\-./]{0,}")

PARTICLES = sorted(
    """
    으로부터 에게서 한테서 까지는 에서는 으로는 로부터 에게는 한테는
    에서의 에게도 한테도 으로의 로의 에는 에도
    이라는 이라고 이라면 이면 에서 에게 한테 으로 까지 부터 처럼
    보다 마다 조차 마저 밖에 라도 이나 든지 하고
    와 과 은 는 이 가 을 를 의 에 도 만 로 나 든
    """.split(),
    key=len,
    reverse=True,
)

COMMON_FORMS = {
    "만들어진다": ("만들다", "verb", 0.98),
    "만들어진": ("만들다", "verb", 0.96),
    "만들어졌다": ("만들다", "verb", 0.98),
    "만든다": ("만들다", "verb", 0.98),
    "만들면": ("만들다", "verb", 0.96),
    "만들고": ("만들다", "verb", 0.96),
    "찾는다": ("찾다", "verb", 0.98),
    "찾으면": ("찾다", "verb", 0.96),
    "찾았다": ("찾다", "verb", 0.98),
    "읽는다": ("읽다", "verb", 0.98),
    "읽으면": ("읽다", "verb", 0.96),
    "읽었다": ("읽다", "verb", 0.98),
    "높인다": ("높이다", "verb", 0.98),
    "높이면": ("높이다", "verb", 0.96),
    "낮춘다": ("낮추다", "verb", 0.98),
    "낮추면": ("낮추다", "verb", 0.96),
    "많다": ("많다", "adjective", 0.99),
    "많은": ("많다", "adjective", 0.95),
    "많으면": ("많다", "adjective", 0.96),
    "많아서": ("많다", "adjective", 0.96),
    "많이": ("많이", "adverb", 0.99),
}

VERB_RULES = [
    (re.compile(r"^(?P<stem>.+)하였습니다$"), "하다"),
    (re.compile(r"^(?P<stem>.+)했습니다$"), "하다"),
    (re.compile(r"^(?P<stem>.+)하였다$"), "하다"),
    (re.compile(r"^(?P<stem>.+)했다$"), "하다"),
    (re.compile(r"^(?P<stem>.+)합니다$"), "하다"),
    (re.compile(r"^(?P<stem>.+)한다$"), "하다"),
    (re.compile(r"^(?P<stem>.+)하면$"), "하다"),
    (re.compile(r"^(?P<stem>.+)하고$"), "하다"),
    (re.compile(r"^(?P<stem>.+)하여$"), "하다"),
    (re.compile(r"^(?P<stem>.+)되었습니다$"), "되다"),
    (re.compile(r"^(?P<stem>.+)됐다$"), "되다"),
    (re.compile(r"^(?P<stem>.+)되었다$"), "되다"),
    (re.compile(r"^(?P<stem>.+)됩니다$"), "되다"),
    (re.compile(r"^(?P<stem>.+)된다$"), "되다"),
    (re.compile(r"^(?P<stem>.+)되면$"), "되다"),
    (re.compile(r"^(?P<stem>.+)되고$"), "되다"),
]

POS_KO = {
    "noun": "명사",
    "verb": "동사",
    "adjective": "형용사",
    "adverb": "부사",
    "proper": "고유명사/코드",
    "unknown": "미분류",
}


def raw_words(text):
    return [
        x.strip("._-/").lower()
        for x in WORD_RE.findall(text)
        if x.strip("._-/")
    ]


def particle_candidate(surface):
    for particle in PARTICLES:
        if surface.endswith(particle):
            base = surface[:-len(particle)]
            if base and re.search(r"[가-힣A-Za-z0-9]", base):
                return base, particle
    return None


def looks_like_code(surface):
    return bool(
        re.fullmatch(r"[a-z]+[a-z0-9+\-]*", surface, re.I)
        or re.fullmatch(r"\d{3,5}[a-z]*", surface, re.I)
        or re.fullmatch(r"[a-z0-9+\-]*\d[a-z0-9+\-]*", surface, re.I)
    )


def collect_evidence(texts):
    surface_counts = Counter()
    particle_bases = defaultdict(Counter)

    for text in texts:
        for surface in raw_words(text):
            surface_counts[surface] += 1
            candidate = particle_candidate(surface)
            if candidate:
                base, particle = candidate
                particle_bases[base][particle] += 1

    return {
        "surface_counts": surface_counts,
        "particle_bases": particle_bases,
    }


def one_char_noun_supported(base, evidence):
    if len(base) != 1 or not re.fullmatch(r"[가-힣]", base):
        return False

    standalone = int(evidence["surface_counts"].get(base, 0))
    particles = evidence["particle_bases"].get(base, Counter())

    # No protected-word hardcoding. The corpus itself must support the noun.
    return standalone >= 1 or len(particles) >= 2 or sum(particles.values()) >= 3


def analyze_surface(surface, evidence):
    """Conservative dictionary-style analysis of one surface form."""
    surface = surface.strip("._-/").lower()
    if not surface:
        return []

    if surface in COMMON_FORMS:
        lemma, pos, confidence = COMMON_FORMS[surface]
        return [{
            "lemma": lemma,
            "pos": pos,
            "confidence": confidence,
            "reason": "common_form",
            "derived_from": "많다" if surface == "많이" else None,
        }]

    for pattern, lemma_tail in VERB_RULES:
        match = pattern.match(surface)
        if match and match.group("stem"):
            return [{
                "lemma": match.group("stem") + lemma_tail,
                "pos": "verb",
                "confidence": 0.94,
                "reason": "regular_verb",
            }]

    if looks_like_code(surface):
        return [{
            "lemma": surface,
            "pos": "proper",
            "confidence": 0.98,
            "reason": "code_or_latin",
        }]

    candidate = particle_candidate(surface)
    if candidate:
        base, suffix = candidate

        # Critical safety rule: 많이 -> 많 is not accepted merely because
        # the last syllable can also be a particle. A one-syllable base needs
        # independent corpus evidence as a noun.
        if len(base) >= 2 or one_char_noun_supported(base, evidence):
            return [{
                "lemma": base,
                "pos": "noun",
                "confidence": 0.92 if len(base) >= 2 else 0.88,
                "reason": "noun_plus_particle",
                "particle": suffix,
            }]

    if re.fullmatch(r"[가-힣]+", surface):
        if len(surface) == 1:
            if one_char_noun_supported(surface, evidence):
                return [{
                    "lemma": surface,
                    "pos": "noun",
                    "confidence": 0.86,
                    "reason": "one_char_corpus_supported",
                }]
            return []

        # Preserve uncertain Korean forms whole rather than shaving off a
        # guessed suffix. Future evidence can upgrade their analysis.
        return [{
            "lemma": surface,
            "pos": "unknown",
            "confidence": 0.55,
            "reason": "surface_preserved",
        }]

    if len(surface) >= 2:
        return [{
            "lemma": surface,
            "pos": "unknown",
            "confidence": 0.50,
            "reason": "surface_preserved",
        }]

    return []
