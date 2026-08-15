from __future__ import annotations

import re
from collections import Counter, defaultdict

VERSION = "0.5.1"

WORD_RE = re.compile(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9_+\-./]{0,}")

PARTICLES = sorted(
    """
    으로부터 에게서 한테서 까지는 에서는 으로는 로부터 에게는 한테는
    에서의 에게도 한테도 으로의 로의 에는 에도
    이라는 이라고 이라면 라는 라고 라면 이면 에서 에게 한테 으로 까지 부터 처럼
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
    "만들어질": ("만들다", "verb", 0.94),
    "만든다": ("만들다", "verb", 0.98),
    "만들면": ("만들다", "verb", 0.96),
    "만들고": ("만들다", "verb", 0.96),
    "찾는다": ("찾다", "verb", 0.98),
    "찾으면": ("찾다", "verb", 0.96),
    "찾았다": ("찾다", "verb", 0.98),
    "찾을": ("찾다", "verb", 0.94),
    "읽는다": ("읽다", "verb", 0.98),
    "읽으면": ("읽다", "verb", 0.96),
    "읽었다": ("읽다", "verb", 0.98),
    "읽을": ("읽다", "verb", 0.94),
    "높인다": ("높이다", "verb", 0.98),
    "높이면": ("높이다", "verb", 0.96),
    "낮춘다": ("낮추다", "verb", 0.98),
    "낮추면": ("낮추다", "verb", 0.96),
    "가진다": ("가지다", "verb", 0.96),
    "준다": ("주다", "verb", 0.96),
    "받을": ("받다", "verb", 0.94),
    "보면": ("보다", "verb", 0.94),
    "보는": ("보다", "verb", 0.94),
    "볼": ("보다", "verb", 0.94),
    "될": ("되다", "verb", 0.96),
    "할": ("하다", "verb", 0.96),
    "않는": ("않다", "verb", 0.96),
    "떠올릴": ("떠올리다", "verb", 0.94),
    "있다": ("있다", "adjective", 0.99),
    "있는": ("있다", "adjective", 0.97),
    "없다": ("없다", "adjective", 0.99),
    "없는": ("없다", "adjective", 0.97),
    "없으면": ("없다", "adjective", 0.96),
    "많다": ("많다", "adjective", 0.99),
    "많은": ("많다", "adjective", 0.97),
    "많으면": ("많다", "adjective", 0.96),
    "많아서": ("많다", "adjective", 0.96),
    "많이": ("많이", "adverb", 0.99),
    "같다": ("같다", "adjective", 0.99),
    "같은": ("같다", "adjective", 0.97),
    "높다": ("높다", "adjective", 0.99),
    "높은": ("높다", "adjective", 0.97),
    "낮다": ("낮다", "adjective", 0.99),
    "낮은": ("낮다", "adjective", 0.97),
    "좋다": ("좋다", "adjective", 0.99),
    "좋은": ("좋다", "adjective", 0.97),
    "강한": ("강하다", "adjective", 0.95),
    "약한": ("약하다", "adjective", 0.95),
    "크게": ("크다", "adverb", 0.90),
    "빠르게": ("빠르다", "adverb", 0.90),
    "강하게": ("강하다", "adverb", 0.90),
    "새로운": ("새롭다", "adjective", 0.95),
    "다른": ("다르다", "adjective", 0.95),
    "읽으며": ("읽다", "verb", 0.94),
    "들어오면": ("들어오다", "verb", 0.94),
    "모이면": ("모이다", "verb", 0.94),
    "이어질": ("이어지다", "verb", 0.94),
    "가질": ("가지다", "verb", 0.94),
    "높일": ("높이다", "verb", 0.94),
    "아닐": ("아니다", "adjective", 0.94),
}

HADA_RULES = [
    re.compile(r"^(?P<stem>.+)하였습니다$"),
    re.compile(r"^(?P<stem>.+)했습니다$"),
    re.compile(r"^(?P<stem>.+)하였다$"),
    re.compile(r"^(?P<stem>.+)했다$"),
    re.compile(r"^(?P<stem>.+)합니다$"),
    re.compile(r"^(?P<stem>.+)한다$"),
    re.compile(r"^(?P<stem>.+)하는$"),
    re.compile(r"^(?P<stem>.+)하면$"),
    re.compile(r"^(?P<stem>.+)하며$"),
    re.compile(r"^(?P<stem>.+)하면서$"),
    re.compile(r"^(?P<stem>.+)하고$"),
    re.compile(r"^(?P<stem>.+)하여$"),
    re.compile(r"^(?P<stem>.+)해서$"),
    re.compile(r"^(?P<stem>.+)할$"),
    re.compile(r"^(?P<stem>.+)하도록$"),
    re.compile(r"^(?P<stem>.+)하기$"),
    re.compile(r"^(?P<stem>.+)하려고$"),
    re.compile(r"^(?P<stem>.+)해야$"),
    re.compile(r"^(?P<stem>.+)하지$"),
    re.compile(r"^(?P<stem>.+)하다고$"),
]

HADA_ADNOMINAL = re.compile(r"^(?P<stem>.+)한$")

DOEDA_RULES = [
    re.compile(r"^(?P<stem>.+)되었습니다$"),
    re.compile(r"^(?P<stem>.+)되었다$"),
    re.compile(r"^(?P<stem>.+)됐다$"),
    re.compile(r"^(?P<stem>.+)됩니다$"),
    re.compile(r"^(?P<stem>.+)된다$"),
    re.compile(r"^(?P<stem>.+)되는$"),
    re.compile(r"^(?P<stem>.+)된$"),
    re.compile(r"^(?P<stem>.+)되면$"),
    re.compile(r"^(?P<stem>.+)되고$"),
    re.compile(r"^(?P<stem>.+)될$"),
    re.compile(r"^(?P<stem>.+)되지$"),
]

BECOME_RULES = [
    re.compile(r"^(?P<stem>.+[아어워해])지면$"),
    re.compile(r"^(?P<stem>.+[아어워해])진다$"),
    re.compile(r"^(?P<stem>.+[아어워해])지는$"),
    re.compile(r"^(?P<stem>.+[아어워해])졌다$"),
]

COPULA_RULES = [
    re.compile(r"^(?P<base>.+?)입니다$"),
    re.compile(r"^(?P<base>.+?)이었다$"),
    re.compile(r"^(?P<base>.+?)였다$"),
    re.compile(r"^(?P<base>.+?)이다$"),
]

POS_KO = {
    "noun": "명사",
    "verb": "동사",
    "adjective": "형용사",
    "adverb": "부사",
    "proper": "고유명사/코드",
    "unknown": "미분류",
}

STRONG_ONE_CHAR_PARTICLES = {"은", "는", "을", "를", "와", "과", "의", "에", "도", "만"}


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
    explicit_copula_bases = Counter()

    for text in texts:
        for surface in raw_words(text):
            surface_counts[surface] += 1
            candidate = particle_candidate(surface)
            if candidate:
                base, particle = candidate
                particle_bases[base][particle] += 1
            for pattern in COPULA_RULES:
                match = pattern.match(surface)
                if match and match.group("base"):
                    explicit_copula_bases[match.group("base")] += 1
                    break

    return {
        "surface_counts": surface_counts,
        "particle_bases": particle_bases,
        "explicit_copula_bases": explicit_copula_bases,
    }


def one_char_noun_supported(base, evidence, particle=None):
    if len(base) != 1 or not re.fullmatch(r"[가-힣]", base):
        return False

    particles = evidence["particle_bases"].get(base, Counter())

    # Standalone occurrence alone is not enough. Otherwise grammar fragments
    # such as 수/데/할/될 become fake nouns.
    if len(particles) >= 2 or sum(particles.values()) >= 3:
        return True

    # One strong case/topic particle is useful evidence. This admits 황은 and
    # 돈과 without relying on a protected-word list. 많이 is resolved as an
    # adverb before particle analysis, so it never becomes 많 + 이.
    if particle in STRONG_ONE_CHAR_PARTICLES and int(particles.get(particle, 0)) >= 1:
        return True
    return False


def _predicate_item(lemma, pos="verb", confidence=0.94, reason="regular_predicate"):
    return [{
        "lemma": lemma,
        "pos": pos,
        "confidence": confidence,
        "reason": reason,
    }]


def analyze_surface(surface, evidence):
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

    # 명사 + 이다/입니다 is strong noun evidence.
    for pattern in COPULA_RULES:
        match = pattern.match(surface)
        if match and match.group("base"):
            return [{
                "lemma": match.group("base"),
                "pos": "noun",
                "confidence": 0.96,
                "reason": "noun_plus_copula",
            }]

    # Compound 하다 predicates, including 사용하는/사용할/분석하기.
    for pattern in HADA_RULES:
        match = pattern.match(surface)
        if match and match.group("stem"):
            return _predicate_item(
                match.group("stem") + "하다",
                "verb",
                0.95,
                "hada_conjugation",
            )

    # -한 is ambiguous, so only multi-syllable roots are inferred here.
    match = HADA_ADNOMINAL.match(surface)
    if match and len(match.group("stem")) >= 2:
        return _predicate_item(
            match.group("stem") + "하다",
            "adjective",
            0.90,
            "hada_adnominal",
        )

    for pattern in DOEDA_RULES:
        match = pattern.match(surface)
        if match and match.group("stem"):
            return _predicate_item(
                match.group("stem") + "되다",
                "verb",
                0.95,
                "doeda_conjugation",
            )

    for pattern in BECOME_RULES:
        match = pattern.match(surface)
        if match and match.group("stem"):
            return _predicate_item(
                match.group("stem") + "지다",
                "verb",
                0.92,
                "become_conjugation",
            )

    # Preserve a dictionary-form predicate as a lemma instead of an unknown
    # surface string. Verb/adjective distinction can be refined later.
    if re.fullmatch(r"[가-힣]{2,}다", surface):
        return _predicate_item(surface, "verb", 0.72, "dictionary_form")

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
        if len(base) >= 2 or one_char_noun_supported(base, evidence, suffix):
            return [{
                "lemma": base,
                "pos": "noun",
                "confidence": 0.92 if len(base) >= 2 else 0.89,
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

        # Unknown Korean forms are kept whole. Never shave a guessed suffix.
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
