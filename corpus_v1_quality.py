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
                f"{place}의 사례에서 {thing}의 관련 대상을 확인하면 무엇인가?",
                f"{place}의 이 사례에서 확인할 관련 대상은 {thing}이다.",
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

    def eval_manifest(split, count):
        tones = ["이 장면을 기준으로", "앞의 조건을 기준으로", "주어진 상황에서", "현재 설명만 보면", "관찰된 정보를 따르면", "이 사례의 범위에서", "앞선 사실에 따르면"]
        categories = ["fact", "event_role", "paraphrase", "context", "polysemy", "negative", "cause", "temporal"]
        negative_rules = [
            ("토끼", "고기"), ("다람쥐", "물고기"), ("사슴", "고기"), ("책", "음식"),
            ("컵", "동물"), ("숲", "동물"), ("사과", "동물"), ("우산", "음식"),
            ("연필", "음료"), ("공", "식물"),
        ]
        causes = [
            ("비가 올 때", "민수", "우산"), ("배가 고플 때", "민수", "밥"), ("목이 마를 때", "지수", "물"),
            ("얼음이 따뜻해질 때", "얼음", "녹는다"), ("책이 필요할 때", "학생", "도서관"),
            ("연필을 잃어버렸을 때", "학생", "새 연필"), ("수업이 시작될 때", "학생", "교실"),
            ("해가 질 때", "주변", "어두워진다"), ("문이 잠겼을 때", "사람", "열쇠"), ("물이 매우 차가워질 때", "물", "얼음"),
        ]
        poly = [
            ("배", "과일", "먹기 위해 껍질을 깎는 배", ["과일"]),
            ("배", "선박", "항구와 바다를 오가는 배", ["선박", "바다"]),
            ("배", "신체", "밥을 많이 먹고 아픈 배", ["신체", "복부"]),
            ("눈", "시각기관", "사물을 바라볼 때 쓰는 눈", ["시각", "사물"]),
            ("눈", "눈송이", "겨울 하늘에서 내려 쌓이는 눈", ["겨울", "쌓"]),
            ("말", "언어", "생각을 문장으로 전하는 말", ["언어", "문장"]),
            ("말", "동물", "목장에서 풀을 먹는 말", ["동물", "풀"]),
            ("사과", "과일", "나무에서 열려 먹는 사과", ["과일", "나무"]),
            ("사과", "사과행위", "잘못을 인정하며 미안함을 전하는 사과", ["미안", "잘못"]),
            ("차", "자동차", "도로를 달리고 주차하는 차", ["자동차", "도로"]),
            ("차", "음료", "컵에 따라 따뜻하게 마시는 차", ["음료", "마신"]),
        ]
        temporal = [
            ("민수", "사과", "식탁", "냉장고"), ("지수", "책", "책상", "가방"),
            ("수진", "열쇠", "현관", "주머니"), ("현우", "공", "운동장", "창고"),
            ("영희", "우산", "현관", "우산꽂이"), ("민수", "컵", "식탁", "찬장"),
            ("지수", "공책", "책상", "서랍"), ("수진", "가방", "방", "현관 옆"),
            ("현우", "연필", "책상", "필통"), ("영희", "신발", "현관", "신발장"),
        ]
        offset = 0 if split == "dev" else 1000
        items = []
        for local in range(count):
            serial = offset + local
            category = categories[serial % len(categories)]
            tone = tones[(serial // 280) % len(tones)]
            a, p, o, v = corpus_v1.EVENTS[serial % len(corpus_v1.EVENTS)]
            action = _adnominal(v)
            item = {"id": f"{split.upper()}-{local+1:03d}", "category": category, "context": [], "forbidden": [], "target": (local % 3 == 0)}
            if category == "fact":
                item.update(question=f"{tone}, {a}가 {o}{corpus_v1._obj(o)} {action} 장소를 답해 줘.", required=[p])
            elif category == "event_role":
                item.update(question=f"{tone}, {p}에서 {a}가 {action} 대상은 무엇인가?", required=[o])
            elif category == "paraphrase":
                item.update(question=f"{tone}, {a}와 {p}의 활동 관계에서 핵심 대상 하나를 말해 줘.", required=[o])
            elif category == "context":
                item.update(context=[f"{a}{corpus_v1._topic(a)} {p}에 있다.", f"{a}{corpus_v1._topic(a)} 그곳에서 {o}{corpus_v1._obj(o)} {v}."], question=f"{tone}, 거기서 다루는 대상은 뭐야?", required=[o], context_required=True)
            elif category == "polysemy":
                word, sense, ctx, required = poly[serial % len(poly)]
                item.update(context=[ctx + "."], question=f"{tone}, 이 문맥의 '{word}'가 가리키는 뜻은 무엇인가?", required=required, sense=sense, context_required=True)
            elif category == "negative":
                x, y = negative_rules[serial % len(negative_rules)]
                item.update(question=f"{tone}, {x}와 {y}의 관계에서 부정되어야 하는 대상은 무엇인가?", required=[y])
            elif category == "cause":
                cond, who, answer = causes[serial % len(causes)]
                item.update(question=f"{tone}, {cond} {who}와 연결되는 결과나 대상은 무엇인가?", required=[answer])
            else:
                owner, obj, first, later = temporal[serial % len(temporal)]
                item.update(context=[f"아침에 {owner}의 {obj}{corpus_v1._topic(obj)} {first}에 있었다.", f"현재 {owner}의 {obj}{corpus_v1._topic(obj)} {later}에 있다."], question=f"{tone}, 현재 {owner}의 {obj}{corpus_v1._topic(obj)} 어디에 있나?", required=[later], context_required=True)
            items.append(item)
        return {"version": VERSION, "split": split, "count": count, "items": items}

    corpus_v1.gen_question_answer = gen_question_answer
    corpus_v1.gen_negative_contrast = gen_negative_contrast
    corpus_v1.eval_manifest = eval_manifest
    corpus_v1.quality_patch_version = VERSION
    return corpus_v1
