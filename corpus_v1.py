from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

VERSION = "0.16.0"
TRAIN_SPECS = {
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
DEV_COUNT = 60
TEST_COUNT = 110

ANIMALS = [
    ("다람쥐", "숲", "씨앗"), ("토끼", "들판", "풀"), ("사슴", "숲", "나뭇잎"),
    ("새", "숲", "열매"), ("곰", "숲", "열매"), ("여우", "들판", "작은 동물"),
]
PEOPLE = ["민수", "지수", "수진", "현우", "영희"]
PLACES = ["부엌", "거실", "방", "마트", "도서관", "교실", "운동장", "공원"]
OBJECTS = ["사과", "책", "공책", "컵", "가방", "열쇠", "연필", "공", "우산", "상자"]
EVENTS = [
    ("다람쥐", "숲", "씨앗", "먹는다"), ("토끼", "들판", "풀", "먹는다"),
    ("사슴", "숲", "나뭇잎", "먹는다"), ("새", "숲", "열매", "먹는다"),
    ("곰", "강가", "물", "마신다"), ("민수", "부엌", "물", "마신다"),
    ("지수", "방", "책", "읽는다"), ("수진", "도서관", "책", "읽는다"),
    ("현우", "교실", "공책", "펼친다"), ("영희", "마트", "사과", "산다"),
    ("민수", "방", "가방", "찾는다"), ("지수", "거실", "열쇠", "찾는다"),
    ("수진", "교실", "연필", "사용한다"), ("현우", "운동장", "공", "던진다"),
    ("영희", "공원", "우산", "편다"), ("선생님", "교실", "문제", "설명한다"),
    ("학생", "도서관", "책", "빌린다"), ("민수", "마트", "우유", "산다"),
    ("지수", "부엌", "빵", "먹는다"), ("수진", "거실", "컵", "놓는다"),
    ("현우", "방", "책", "정리한다"), ("영희", "교실", "숙제", "제출한다"),
    ("토끼", "강가", "물", "마신다"), ("사슴", "강가", "물", "마신다"),
    ("다람쥐", "숲", "열매", "찾는다"), ("새", "나무", "둥지", "만든다"),
    ("민수", "도서관", "공책", "읽는다"), ("지수", "마트", "우유", "산다"),
    ("수진", "부엌", "사과", "씻는다"), ("현우", "거실", "컵", "옮긴다"),
    ("영희", "방", "가방", "정리한다"), ("선생님", "도서관", "자료", "찾는다"),
    ("학생", "교실", "질문", "한다"), ("민수", "공원", "친구", "만난다"),
    ("지수", "운동장", "공", "받는다"),
]


def _has_final(word):
    if not word:
        return False
    ch = word[-1]
    if not ("가" <= ch <= "힣"):
        return False
    return (ord(ch) - 0xAC00) % 28 != 0


def _p(word, consonant, vowel):
    return consonant if _has_final(word) else vowel


def _topic(word): return _p(word, "은", "는")
def _subj(word): return _p(word, "이", "가")
def _obj(word): return _p(word, "을", "를")


def _dedupe(rows):
    out, seen = [], set()
    for row in rows:
        row = re.sub(r"\s+", " ", str(row)).strip()
        if row and row not in seen:
            seen.add(row)
            out.append(row)
    return out


def _take(rows, count, label):
    rows = _dedupe(rows)
    if len(rows) < count:
        raise ValueError(f"{label} 생성량 부족: {len(rows)} < {count}")
    return rows[:count]


def gen_core_facts():
    rows = []
    definitions = [
        ("숲", "여러 나무와 생물이 함께 사는 환경"), ("들판", "풀이 넓게 자라는 열린 공간"),
        ("강", "물이 한 방향으로 흐르는 자연 지형"), ("나무", "줄기와 가지를 가진 식물"),
        ("씨앗", "새 식물이 자랄 수 있는 구조"), ("열매", "식물이 만드는 먹을 수 있는 부분"),
        ("책", "글과 정보를 담은 물건"), ("도서관", "책을 읽고 빌릴 수 있는 장소"),
        ("교실", "학생이 수업을 듣는 장소"), ("마트", "생활 물건과 음식을 사는 장소"),
        ("컵", "물을 담아 마시는 용기"), ("가방", "물건을 넣어 옮기는 도구"),
        ("열쇠", "문을 열거나 잠그는 도구"), ("우산", "비를 피할 때 사용하는 도구"),
        ("상자", "물건을 넣어 보관하는 용기"), ("공책", "글을 적는 종이 묶음"),
        ("연필", "글씨를 쓰는 도구"), ("공", "던지거나 차며 노는 둥근 물건"),
        ("얼음", "물이 차가워져 굳은 상태"), ("물", "사람과 동물이 마실 수 있는 액체"),
    ]
    for s, d in definitions:
        rows += [f"{s}{_topic(s)} {d}이다.", f"{d}{_p(d,'인','인')} 것은 {s}이다.", f"{s}의 기본 특징은 {d}이라는 점이다."]
    for a, place, food in ANIMALS:
        rows += [
            f"{a}{_topic(a)} 주로 {place}에서 산다.",
            f"{a}{_topic(a)} {food}{_obj(food)} 먹는다.",
            f"{place}에는 {a}{_subj(a)} 살 수 있다.",
            f"{food}{_topic(food)} {a}{_subj(a)} 먹는 먹이 가운데 하나이다.",
            f"{a}에게 {place}{_topic(place)} 중요한 생활 공간이다.",
        ]
    for i, person in enumerate(PEOPLE):
        home = ["집", "집", "집", "집", "집"][i]
        rows += [
            f"{person}{_topic(person)} {home}에서 생활한다.",
            f"{person}{_topic(person)} 물을 마실 수 있다.",
            f"{person}{_topic(person)} 책을 읽을 수 있다.",
            f"{person}{_topic(person)} 마트에서 물건을 살 수 있다.",
            f"{person}{_topic(person)} 도서관에서 책을 빌릴 수 있다.",
        ]
    stable = [
        ("상자", "책상 위"), ("컵", "찬장 안"), ("책", "책장 안"), ("공책", "서랍 안"),
        ("연필", "필통 안"), ("우산", "우산꽂이 안"), ("공", "운동장 창고 안"),
        ("열쇠", "열쇠걸이"), ("가방", "옷걸이 옆"), ("신발", "신발장 안"),
    ]
    for obj, loc in stable:
        rows += [
            f"보관할 때 {obj}{_topic(obj)} {loc}에 둔다.",
            f"평소 보관 위치에서 {obj}{_topic(obj)} {loc}에 있다.",
            f"{loc}{_topic(loc)} {obj}의 기본 보관 장소이다.",
            f"정리된 상태에서는 {obj}{_subj(obj)} {loc}에 놓여 있다.",
        ]
    school = [
        ("학생", "교실", "수업"), ("선생님", "교실", "설명"), ("학생", "도서관", "독서"),
        ("친구", "운동장", "놀이"), ("학생", "책상", "공부"), ("선생님", "칠판", "수업"),
        ("학생", "공책", "필기"), ("학생", "연필", "쓰기"), ("친구", "도서관", "대화"),
        ("학생", "학교", "학습"),
    ]
    for who, where, what in school:
        rows += [
            f"{who}{_topic(who)} {where}에서 {what}{_obj(what)} 한다.",
            f"{where}{_topic(where)} {who}{_subj(who)} {what}{_obj(what)} 할 수 있는 곳이다.",
            f"{what}{_topic(what)} {where}에서 이루어질 수 있다.",
            f"{who}에게 {where}{_topic(where)} {what}과 관련된 장소이다.",
        ]
    rows += [
        "비가 오면 땅은 젖을 수 있다.", "햇빛은 낮에 주변을 밝게 한다.",
        "사람은 눈으로 주변을 볼 수 있다.", "사람은 말을 사용해 생각을 전달할 수 있다.",
        "차는 도로를 이동하는 자동차를 뜻할 수 있다.", "차는 마시는 음료를 뜻할 수도 있다.",
        "배는 먹는 과일을 뜻할 수 있다.", "배는 바다를 이동하는 선박을 뜻할 수 있다.",
        "배는 사람의 신체 부위를 뜻할 수도 있다.", "사과는 과일의 이름으로 쓰일 수 있다.",
    ]
    return _take(rows, 200, "core facts")


def gen_event_patterns():
    rows = []
    for a, p, o, v in EVENTS:
        rows += [
            f"{a}{_topic(a)} {p}에서 {o}{_obj(o)} {v}.",
            f"{p}에서 {a}{_subj(a)} {o}{_obj(o)} {v}.",
            f"{a}{_subj(a)} {o}{_obj(o)} {p}에서 {v}.",
            f"{a}{_topic(a)} 보통 {p}에서 {o}{_obj(o)} {v}.",
            f"{a}{_subj(a)} {p}에서 천천히 {o}{_obj(o)} {v}.",
            f"{p}에 있는 {a}{_topic(a)} {o}{_obj(o)} {v}.",
            f"{a}{_topic(a)} {p}에서 필요한 {o}{_obj(o)} {v}.",
            f"{a}{_subj(a)} 주로 {p}에서 {o}{_obj(o)} {v}.",
        ]
    return _take(rows, 280, "event patterns")


def gen_paraphrases():
    rows = []
    eat = EVENTS[:15]
    for a, p, o, _v in eat:
        rows += [
            f"{a}{_topic(a)} {o}{_obj(o)} 먹거나 이용한다.",
            f"{o}{_topic(o)} {a}에게 필요한 대상 가운데 하나이다.",
            f"{a}{_subj(a)} {p}에 있을 때 {o}{_obj(o)} 이용하는 모습을 볼 수 있다.",
            f"{p}에서 {o}{_obj(o)} 이용하는 주체는 {a}이다.",
            f"{a}와 {o}의 관계는 {p}에서 자주 관찰된다.",
            f"{a}{_topic(a)} {p}에서 활동하며 {o}{_obj(o)} 이용한다.",
        ]
    live = [
        ("다람쥐", "숲"), ("토끼", "들판"), ("사슴", "숲"), ("새", "숲"), ("곰", "숲"),
        ("민수", "집"), ("지수", "집"), ("학생", "학교"), ("선생님", "학교"), ("물고기", "강"),
        ("개구리", "연못"), ("고양이", "집"), ("강아지", "집"), ("오리", "연못"), ("벌", "꽃밭"),
    ]
    for a, p in live:
        rows += [
            f"{a}{_topic(a)} {p}{_obj(p)} 생활 공간으로 이용한다.",
            f"{p}{_topic(p)} {a}{_subj(a)} 머물 수 있는 장소이다.",
            f"{a}{_subj(a)} 생활하는 곳으로 {p}{_subj(p)} 알려져 있다.",
            f"{a}의 생활 장소를 말하면 {p}{_obj(p)} 들 수 있다.",
            f"{p}에서는 {a}{_subj(a)} 생활하는 모습을 볼 수 있다.",
            f"{a}에게 익숙한 생활 환경 가운데 하나는 {p}이다.",
        ]
    return _take(rows, 180, "paraphrases")


def gen_question_answer():
    rows = []
    facts = EVENTS[:25]
    for a, p, o, v in facts:
        rows += [
            f"{a}{_topic(a)} 어디에서 활동하는가?",
            f"{a}{_topic(a)} 이 사례에서는 {p}에서 활동한다.",
            f"{a}{_subj(a)} {p}에서 이용하거나 다루는 대상은 무엇인가?",
            f"{a}{_subj(a)} {p}에서 이용하거나 다루는 대상은 {o}이다.",
        ]
    stable = [
        ("상자", "책상 위"), ("컵", "찬장 안"), ("책", "책장 안"), ("공책", "서랍 안"),
        ("연필", "필통 안"), ("우산", "우산꽂이 안"), ("공", "운동장 창고 안"),
        ("열쇠", "열쇠걸이"), ("가방", "옷걸이 옆"), ("신발", "신발장 안"),
        ("학생", "교실"), ("선생님", "교실"), ("책", "도서관"), ("사과", "마트"),
        ("물", "부엌"), ("컵", "부엌"), ("공", "운동장"), ("연필", "교실"),
        ("우산", "현관"), ("열쇠", "현관"), ("토끼", "들판"), ("다람쥐", "숲"),
        ("사슴", "숲"), ("물고기", "강"), ("오리", "연못"),
    ]
    for thing, place in stable:
        rows += [
            f"{thing}과 가장 관련된 장소는 어디인가?",
            f"{thing}과 관련된 장소는 {place}이다.",
            f"{place}와 관련된 대상 가운데 하나는 무엇인가?",
            f"{place}와 관련된 대상 가운데 하나는 {thing}이다.",
        ]
    return _take(rows, 200, "question answer")


def gen_dialogue_basic():
    rows = []
    scenarios = (EVENTS * 2)[:40]
    for i, (a, p, o, v) in enumerate(scenarios, 1):
        rows.append(f"@@dialogue BASIC-{i:03d} START")
        rows.append(f"사용자: {a}{_topic(a)} 어디에 있어?")
        rows.append(f"답변: {a}{_topic(a)} {p}에 있다.")
        rows.append(f"사용자: {a}{_topic(a)} 거기서 무엇을 해?")
        rows.append(f"답변: {a}{_topic(a)} {p}에서 {o}{_obj(o)} {v}.")
        rows.append(f"@@dialogue BASIC-{i:03d} END")
    return rows


def gen_dialogue_context():
    rows = []
    pairs = list(zip((EVENTS * 2)[:20], (EVENTS[10:] + EVENTS[:10])[:20]))
    for i, (first, second) in enumerate(pairs, 1):
        a, p, o, v = first
        _a2, p2, o2, v2 = second
        rows.append(f"@@dialogue CONTEXT-{i:03d} START")
        rows.append(f"사용자: {a}{_topic(a)} 지금 어디에 있어?")
        rows.append(f"답변: {a}{_topic(a)} {p}에 있다.")
        rows.append("사용자: 거기서 뭘 해?")
        rows.append(f"답변: {a}{_topic(a)} {o}{_obj(o)} {v}.")
        rows.append("사용자: 그 다음에는 무엇을 해?")
        rows.append(f"답변: {a}{_topic(a)} 다음에 {p2}에서 {o2}{_obj(o2)} {v2}.")
        rows.append(f"@@dialogue CONTEXT-{i:03d} END")
    return rows


def gen_negative_contrast():
    rows = []
    negatives = [
        ("토끼", "고기", "먹지 않는다"), ("다람쥐", "물고기", "먹지 않는다"),
        ("사슴", "고기", "먹지 않는다"), ("책", "음식", "아니다"), ("컵", "동물", "아니다"),
        ("숲", "동물", "아니다"), ("사과", "동물", "아니다"), ("우산", "음식", "아니다"),
        ("연필", "음료", "아니다"), ("공", "식물", "아니다"),
    ]
    for i in range(40):
        a, b, pred = negatives[i % len(negatives)]
        if pred.startswith("먹"):
            rows.append(f"{a}{_topic(a)} {b}{_obj(b)} {pred}.")
        else:
            rows.append(f"{a}{_topic(a)} {b}{_subj(b)} {pred}.")
        rows[-1] = rows[-1][:-1] + (" 일반적인 분류에서도 그렇다." if i >= 10 else ".")
    contrasts = [
        ("토끼", "풀", "여우", "고기"), ("다람쥐", "씨앗", "사슴", "나뭇잎"),
        ("민수", "물", "지수", "우유"), ("학생", "공책", "선생님", "자료"),
        ("새", "열매", "곰", "물"),
    ]
    for i in range(40):
        a, x, b, y = contrasts[i % len(contrasts)]
        adverb = ["보통", "주로", "이 사례에서는", "관찰된 상황에서는", "기본 상황에서는"][i % 5]
        rows.append(f"{adverb} {a}{_topic(a)} {x}{_obj(x)} 이용하지만 {b}{_topic(b)} {y}{_obj(y)} 이용한다.")
    return _take(rows, 80, "negative contrast")


def gen_cause_condition():
    bases = [
        ("비가 오면", "민수는 우산을 편다"), ("배가 고프면", "민수는 밥을 먹는다"),
        ("목이 마르면", "지수는 물을 마신다"), ("얼음이 따뜻해지면", "얼음은 녹는다"),
        ("물이 충분히 차가워지면", "물은 얼 수 있다"), ("책이 필요하면", "학생은 도서관에 간다"),
        ("연필을 잃어버리면", "학생은 새 연필을 찾는다"), ("수업이 시작되면", "학생은 교실에 앉는다"),
        ("해가 지면", "주변은 어두워진다"), ("문이 잠겨 있으면", "열쇠가 필요하다"),
    ]
    prefixes = ["", "일반적으로 ", "이 상황에서는 ", "조건이 충족되면 ", "보통 ", "대체로 ", "기본 상황에서 "]
    rows = []
    for pre in prefixes:
        for cond, result in bases:
            rows.append(f"{pre}{cond} {result}.")
    return _take(rows, 70, "cause condition")


def gen_polysemy():
    senses = [
        ("배", "과일", ["먹는다", "껍질을 깎는다", "과일 바구니에 둔다", "달콤한 맛이 난다"]),
        ("배", "선박", ["항구를 떠난다", "바다를 이동한다", "부두에 정박한다", "사람과 짐을 싣는다"]),
        ("배", "신체", ["밥을 먹으면 부를 수 있다", "아프면 손으로 누르기도 한다", "몸의 가운데 부분에 있다", "복부를 뜻한다"]),
        ("눈", "시각기관", ["사물을 본다", "얼굴에 있다", "빛을 받아들인다", "아프면 쉬어야 한다"]),
        ("눈", "눈송이", ["겨울 하늘에서 내린다", "땅에 쌓인다", "추운 날 녹지 않고 남기도 한다", "하얀 결정으로 보인다"]),
        ("말", "언어", ["생각을 전달한다", "문장으로 표현된다", "사람 사이의 대화에 쓰인다", "뜻을 담을 수 있다"]),
        ("말", "동물", ["네 발로 걷는다", "풀을 먹는다", "사람을 태울 수 있다", "목장에서 살 수 있다"]),
        ("사과", "과일", ["나무에서 열린다", "먹을 수 있다", "껍질을 씻어 먹는다", "과일 바구니에 담는다"]),
        ("사과", "사과행위", ["잘못을 인정할 때 한다", "상대에게 미안함을 전한다", "말이나 행동으로 표현한다", "관계를 회복하는 데 도움이 된다"]),
        ("차", "자동차", ["도로를 달린다", "사람을 태우고 이동한다", "주차장에 세운다", "바퀴가 있다"]),
        ("차", "음료", ["컵에 따라 마신다", "따뜻하게 마실 수 있다", "찻잎으로 만들 수 있다", "향을 느끼며 마신다"]),
    ]
    rows = []
    i = 0
    while len(rows) < 70:
        word, sense, facts = senses[i % len(senses)]
        fact = facts[(i // len(senses)) % len(facts)]
        intros = [f"{sense} 의미의 {word}", f"이 문맥에서 {word}{_topic(word)} {sense}{_obj(sense)} 뜻하며", f"{sense}를 가리키는 {word}{_topic(word)}"]
        intro = intros[(i // (len(senses) * len(facts))) % len(intros)]
        rows.append(f"{intro} {fact}.")
        i += 1
    return _take(rows, 70, "polysemy")


def gen_temporal_state():
    items = [
        ("민수", "사과", "식탁 위", "냉장고 안"), ("지수", "책", "책상 위", "가방 안"),
        ("수진", "열쇠", "현관 선반", "주머니 안"), ("현우", "공", "운동장", "창고 안"),
        ("영희", "우산", "현관", "우산꽂이 안"), ("민수", "컵", "식탁 위", "찬장 안"),
        ("지수", "공책", "책상 위", "서랍 안"), ("수진", "가방", "방 안", "현관 옆"),
        ("현우", "연필", "책상 위", "필통 안"), ("영희", "신발", "현관", "신발장 안"),
    ]
    rows = []
    for owner, obj, first, later in items:
        rows += [
            f"아침에 {owner}의 {obj}{_topic(obj)} {first}에 있다.",
            f"점심 뒤에는 {owner}의 {obj}{_topic(obj)} {later}에 있다.",
            f"처음 상태에서 {owner}의 {obj}{_topic(obj)} {first}에 있었다.",
            f"현재 상태에서 {owner}의 {obj}{_topic(obj)} {later}에 있다.",
            f"저녁에는 {owner}의 {obj}{_topic(obj)} {later}에 보관되어 있다.",
        ]
    return _take(rows, 50, "temporal state")


def gen_cross_topic():
    triples = [
        ("민수", "숲", "다람쥐"), ("지수", "학교", "숲"), ("선생님", "교실", "생태계"),
        ("학생", "도서관", "동물"), ("민수", "공원", "새"), ("지수", "마트", "사과"),
        ("수진", "부엌", "과일"), ("현우", "학교", "우산"), ("영희", "도서관", "선박"),
        ("민수", "교실", "얼음"), ("지수", "공원", "나무"), ("선생님", "도서관", "강"),
        ("학생", "운동장", "비"), ("수진", "마트", "컵"), ("현우", "부엌", "물"),
        ("영희", "숲", "열매"), ("민수", "도서관", "말"), ("지수", "학교", "자동차"),
        ("수진", "공원", "토끼"), ("현우", "교실", "사과"), ("영희", "마트", "책"),
        ("학생", "숲", "씨앗"), ("선생님", "공원", "곤충"), ("민수", "학교", "눈"),
        ("지수", "도서관", "차"), ("수진", "교실", "배"), ("현우", "마트", "우유"),
        ("영희", "공원", "강아지"), ("학생", "부엌", "물"), ("선생님", "숲", "사슴"),
    ]
    rows = []
    for a, p, o in triples:
        rows += [
            f"{a}{_topic(a)} {p}에서 {o}에 대해 관찰하거나 배웠다.",
            f"{p}에서 본 {o}에 관한 내용을 {a}{_subj(a)} 다른 장소에서도 이야기했다.",
            f"{a}{_topic(a)} {o}에 관한 경험을 {p}의 상황과 연결해 설명했다.",
        ]
    return _take(rows, 90, "cross topic")


def train_documents():
    docs = {
        "01_core_facts.md": gen_core_facts(),
        "02_event_patterns.md": gen_event_patterns(),
        "03_paraphrases.md": gen_paraphrases(),
        "04_question_answer.md": gen_question_answer(),
        "05_dialogue_basic.md": gen_dialogue_basic(),
        "06_dialogue_context.md": gen_dialogue_context(),
        "07_negative_contrast.md": gen_negative_contrast(),
        "08_cause_condition.md": gen_cause_condition(),
        "09_polysemy_context.md": gen_polysemy(),
        "10_temporal_state.md": gen_temporal_state(),
        "11_cross_topic.md": gen_cross_topic(),
    }
    # Dialogue control lines do not count as learning sentences.
    for name in ("05_dialogue_basic.md", "06_dialogue_context.md"):
        count = sum(1 for line in docs[name] if line and not line.startswith("@@"))
        if count != TRAIN_SPECS[name]:
            raise AssertionError(f"{name}: {count}")
    for name, expected in TRAIN_SPECS.items():
        if name not in {"05_dialogue_basic.md", "06_dialogue_context.md"} and len(docs[name]) != expected:
            raise AssertionError(f"{name}: {len(docs[name])}")
    return docs


def _eval_item(i, split):
    category_cycle = ["fact", "event_role", "paraphrase", "context", "polysemy", "negative", "cause", "temporal"]
    category = category_cycle[i % len(category_cycle)]
    a, p, o, v = EVENTS[i % len(EVENTS)]
    item = {"id": f"{split.upper()}-{i+1:03d}", "category": category, "context": [], "forbidden": [], "target": (i % 3 == 0)}
    if category == "fact":
        item.update(question=f"{a}와 가장 관련된 활동 장소를 한 곳 말해 줘.", required=[p])
    elif category == "event_role":
        item.update(question=f"{p}에서 {a}{_subj(a)} 다루는 대상은 무엇이라고 볼 수 있나?", required=[o])
    elif category == "paraphrase":
        item.update(question=f"{a}의 {p} 생활에서 등장하는 대상을 답해 줘.", required=[o])
    elif category == "context":
        item.update(context=[f"{a}{_topic(a)} {p}에 있다.", f"{a}{_topic(a)} {p}에서 {o}{_obj(o)} {v}."], question="거기서 다루는 대상은 뭐야?", required=[o], context_required=True)
    elif category == "polysemy":
        poly = [
            ("배", "과일", "먹을 수 있는 배에 대해 말하고 있다.", ["과일"]),
            ("배", "선박", "항구를 떠나는 배에 대해 말하고 있다.", ["선박", "바다"]),
            ("눈", "시각기관", "사람이 사물을 보는 눈에 대해 말하고 있다.", ["시각", "본다", "사물"]),
            ("눈", "눈송이", "겨울 하늘에서 내리는 눈에 대해 말하고 있다.", ["겨울", "내린다", "쌓"]),
            ("말", "동물", "목장에서 풀을 먹는 말에 대해 말하고 있다.", ["동물", "풀"]),
            ("사과", "사과행위", "잘못을 인정하는 사과에 대해 말하고 있다.", ["미안", "잘못", "인정"]),
            ("차", "음료", "컵에 따라 마시는 차에 대해 말하고 있다.", ["음료", "마신"]),
        ][i % 7]
        word, sense, ctx, required = poly
        item.update(context=[ctx], question=f"이 문맥의 '{word}'는 어떤 의미인가?", required=required, sense=sense, context_required=True)
    elif category == "negative":
        item.update(question="토끼가 일반적으로 먹지 않는 것으로 학습된 것은 무엇인가?", required=["고기"], forbidden=["풀"])
    elif category == "cause":
        item.update(question="비가 오는 조건에서 민수가 사용하는 물건은 무엇인가?", required=["우산"])
    else:
        owner, obj, first, later = [
            ("민수", "사과", "식탁", "냉장고"), ("지수", "책", "책상", "가방"),
            ("수진", "열쇠", "현관", "주머니"), ("현우", "공", "운동장", "창고"),
        ][i % 4]
        item.update(context=[f"아침에 {owner}의 {obj}{_topic(obj)} {first}에 있었다.", f"현재 {owner}의 {obj}{_topic(obj)} {later}에 있다."], question=f"현재 {owner}의 {obj}{_topic(obj)} 어디에 있나?", required=[later], context_required=True)
    return item


def eval_manifest(split, count):
    return {"version": VERSION, "split": split, "count": count, "items": [_eval_item(i + (0 if split == "dev" else 1000), split) for i in range(count)]}


def _doc_text(name, role, lines, expected):
    body = "\n".join(lines).strip() + "\n"
    return (
        "---\n"
        "type: corpus-v1\n"
        f"role: {role}\n"
        f"source: \"{name}\"\n"
        f"expected_sentences: {expected}\n"
        f"corpus_version: \"{VERSION}\"\n"
        "---\n\n" + body
    )


def _eval_markdown(manifest):
    return [item["question"] for item in manifest["items"]]


def validate_generated():
    docs = train_documents()
    learned = 0
    for name, rows in docs.items():
        learned += sum(1 for line in rows if line and not line.startswith("@@"))
    if learned != 1500:
        raise AssertionError(f"train total={learned}")
    dev = eval_manifest("dev", DEV_COUNT)
    test = eval_manifest("test", TEST_COUNT)
    if len(dev["items"]) != DEV_COUNT or len(test["items"]) != TEST_COUNT:
        raise AssertionError("eval count")
    train_plain = {line.strip() for rows in docs.values() for line in rows if line and not line.startswith("@@")}
    eval_plain = {item["question"].strip() for item in dev["items"] + test["items"]}
    if train_plain & eval_plain:
        raise AssertionError("exact train/eval leak")
    if "상자는 책상 아래에 있다." in train_plain:
        raise AssertionError("box location conflict")
    return {"train_sentences": learned, "dev": DEV_COUNT, "test": TEST_COUNT, "files": len(docs)}


def install(core, vault, rebuild=True):
    validate_generated()
    d = core.wordmap_dirs(vault)
    corpus = d["corpus"]
    backups = d["meta"] / "backups"
    eval_dir = d["meta"] / "Eval"
    backups.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backups / f"corpus_before_v1_{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for path in corpus.iterdir():
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            shutil.copy2(path, backup / path.name)
            path.unlink()

    docs = train_documents()
    for name, rows in docs.items():
        (corpus / name).write_text(_doc_text(name, "train", rows, TRAIN_SPECS[name]), encoding="utf-8")

    dev = eval_manifest("dev", DEV_COUNT)
    test = eval_manifest("test", TEST_COUNT)
    (corpus / "90_dev_questions.md").write_text(_doc_text("90_dev_questions.md", "dev", _eval_markdown(dev), DEV_COUNT), encoding="utf-8")
    (corpus / "91_test_questions.md").write_text(_doc_text("91_test_questions.md", "test", _eval_markdown(test), TEST_COUNT), encoding="utf-8")
    (eval_dir / "90_dev_manifest.json").write_text(json.dumps(dev, ensure_ascii=False, indent=2), encoding="utf-8")
    (eval_dir / "91_test_manifest.json").write_text(json.dumps(test, ensure_ascii=False, indent=2), encoding="utf-8")

    # Registry: only 01~11 can ever be active. Evaluation files are hard-off.
    registry_path = d["meta"] / "corpus_registry.json"
    registry = {"version": VERSION, "dirty": True, "updated": datetime.now().isoformat(timespec="seconds"), "files": {}}
    for name in TRAIN_SPECS:
        registry["files"][name] = {"enabled": True, "role": "train"}
    registry["files"]["90_dev_questions.md"] = {"enabled": False, "role": "dev"}
    registry["files"]["91_test_questions.md"] = {"enabled": False, "role": "test"}
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    if hasattr(core, "learning_reset"):
        core.learning_reset(vault)
    result = {"version": VERSION, "installed": True, "backup": str(backup), **validate_generated()}
    if rebuild:
        result["rebuild"] = core.rebuild_wordmap(vault)
    return result


def summary(core, vault):
    d = core.wordmap_dirs(vault)
    eval_dir = d["meta"] / "Eval"
    docs = core.corpus_list(vault)
    return {
        "version": VERSION,
        "expected_train_sentences": 1500,
        "expected_dev": DEV_COUNT,
        "expected_test": TEST_COUNT,
        "documents": docs.get("documents", []),
        "dev_manifest": (eval_dir / "90_dev_manifest.json").exists(),
        "test_manifest": (eval_dir / "91_test_manifest.json").exists(),
    }


def apply(core):
    core.corpus_v1_install = lambda vault, rebuild=True: install(core, vault, rebuild=rebuild)
    core.corpus_v1_summary = lambda vault: summary(core, vault)
    core.corpus_v1_validate_generated = validate_generated
    core.corpus_v1_version = VERSION
    return core
