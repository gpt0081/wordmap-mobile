from __future__ import annotations

VERSION = "0.16.0"


def _adnominal(v):
    table = {
        "먹는다": "먹는", "마신다": "마시는", "읽는다": "읽는", "펼친다": "펼치는",
        "산다": "사는", "찾는다": "찾는", "사용한다": "사용하는", "던진다": "던지는",
        "편다": "펴는", "설명한다": "설명하는", "빌린다": "빌리는", "놓는다": "놓는",
        "정리한다": "정리하는", "제출한다": "제출하는", "만든다": "만드는", "씻는다": "씻는",
        "옮긴다": "옮기는", "한다": "하는", "만난다": "만나는", "받는다": "받는",
    }
    return table.get(v, v.rstrip("다") + "는")


def apply(corpus_v1):
    def gen_question_answer():
        rows = []
        for a, p, o, v in corpus_v1.EVENTS[:25]:
            objp = corpus_v1._obj(o)
            action = _adnominal(v)
            rows += [
                f"{a}가 {o}{objp} {action} 곳은 어디인가?",
                f"{a}가 {o}{objp} {action} 곳은 {p}이다.",
                f"{p}에서 {a}가 {action} 대상은 무엇인가?",
                f"{p}에서 {a}가 {action} 대상은 {o}이다.",
            ]
        stable = [
            ("상자", "책상 위"), ("컵", "찬장 안"), ("책", "책장 안"), ("공책", "서랍 안"),
            ("연필", "필통 안"), ("우산", "우산꽂이 안"), ("공", "운동장 창고 안"),
            ("열쇠", "열쇠걸이"), ("가방", "옷걸이 옆"), ("신발", "신발장 안"),
            ("학생", "교실"), ("선생님", "교실"), ("도서관 책", "도서관"), ("마트 사과", "마트"),
            ("마실 물", "부엌"), ("부엌 컵", "부엌"), ("운동용 공", "운동장"), ("수업용 연필", "교실"),
            ("비 오는 날 우산", "현관"), ("현관 열쇠", "현관"), ("들판 토끼", "들판"), ("숲 다람쥐", "숲"),
            ("숲 사슴", "숲"), ("강 물고기", "강"), ("연못 오리", "연못"),
        ]
        for thing, place in stable:
            rows += [
                f"{thing}과 연결된 기본 장소는 어디인가?",
                f"{thing}과 연결된 기본 장소는 {place}이다.",
                f"{place}의 사례에서 확인할 대상은 무엇인가? {thing}을 기준으로 답하라.",
                f"{place}의 이 사례에서 확인할 대상은 {thing}이다.",
            ]
        return corpus_v1._take(rows, 200, "question answer")

    def gen_negative_contrast():
        rows = []
        negatives = [
            ("토끼", "고기", "먹지 않는다"), ("다람쥐", "물고기", "먹지 않는다"),
            ("사슴", "고기", "먹지 않는다"), ("책", "음식", "아니다"), ("컵", "동물", "아니다"),
            ("숲", "동물", "아니다"), ("사과", "동물", "아니다"), ("우산", "음식", "아니다"),
            ("연필", "음료", "아니다"), ("공", "식물", "아니다"),
        ]
        qualifiers = ["일반적인 관계에서", "기본 분류에서", "학습된 기본 상황에서", "평소 조건에서"]
        for q in qualifiers:
            for a, b, pred in negatives:
                if pred.startswith("먹"):
                    rows.append(f"{q} {a}{corpus_v1._topic(a)} {b}{corpus_v1._obj(b)} {pred}.")
                else:
                    rows.append(f"{q} {a}{corpus_v1._topic(a)} {b}{corpus_v1._subj(b)} {pred}.")
        contrasts = [
            ("토끼", "풀", "여우", "고기"), ("다람쥐", "씨앗", "사슴", "나뭇잎"),
            ("민수", "물", "지수", "우유"), ("학생", "공책", "선생님", "자료"),
            ("새", "열매", "곰", "물"),
        ]
        contexts = ["보통", "주로", "이 사례에서는", "관찰된 상황에서는", "기본 상황에서는", "낮에는", "평소에는", "일반적으로"]
        for q in contexts:
            for a, x, b, y in contrasts:
                rows.append(f"{q} {a}{corpus_v1._topic(a)} {x}{corpus_v1._obj(x)} 이용하지만 {b}{corpus_v1._topic(b)} {y}{corpus_v1._obj(y)} 이용한다.")
        return corpus_v1._take(rows, 80, "negative contrast")

    corpus_v1.gen_question_answer = gen_question_answer
    corpus_v1.gen_negative_contrast = gen_negative_contrast
    corpus_v1.quality_patch_version = VERSION
    return corpus_v1
