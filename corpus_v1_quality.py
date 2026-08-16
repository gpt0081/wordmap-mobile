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
    def gen_paraphrases():
        rows = []
        for a, p, o, v in corpus_v1.EVENTS[:15]:
            action = _adnominal(v)
            rows += [
                f"{a}가 {p}에서 하는 행동 가운데 하나는 {o}{corpus_v1._obj(o)} {action} 것이다.",
                f"{p}에서 {a}가 {action} 대상은 {o}이다.",
                f"{o}{corpus_v1._topic(o)} {p}에서 {a}가 {action} 대상이다.",
                f"{a}와 {o}{corpus_v1._topic(o)} {p}의 {action} 상황에서 함께 등장한다.",
                f"{p}의 이 사례에는 {a}가 {o}{corpus_v1._obj(o)} {action} 행동이 포함된다.",
                f"{a}의 {p} 활동을 설명할 때 {o}{corpus_v1._obj(o)} {action} 장면을 들 수 있다.",
            ]
        live = [
            ("다람쥐", "숲"), ("토끼", "들판"), ("사슴", "숲"), ("새", "숲"), ("곰", "숲"),
            ("민수", "집"), ("지수", "집"), ("학생", "학교"), ("선생님", "학교"), ("물고기", "강"),
            ("개구리", "연못"), ("고양이", "집"), ("강아지", "집"), ("오리", "연못"), ("벌", "꽃밭"),
        ]
        for a, p in live:
            rows += [
                f"{a}{corpus_v1._topic(a)} {p}{corpus_v1._obj(p)} 생활 공간으로 이용한다.",
                f"{p}{corpus_v1._topic(p)} {a}{corpus_v1._subj(a)} 머물 수 있는 장소이다.",
                f"{a}{corpus_v1._subj(a)} 생활하는 곳으로 {p}{corpus_v1._subj(p)} 알려져 있다.",
                f"{a}의 생활 장소를 말하면 {p}{corpus_v1._obj(p)} 들 수 있다.",
                f"{p}에서는 {a}{corpus_v1._subj(a)} 생활하는 모습을 볼 수 있다.",
                f"{a}에게 익숙한 생활 환경 가운데 하나는 {p}이다.",
            ]
        return corpus_v1._take(rows, 180, "paraphrases")

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

    def gen_polysemy():
        senses = [
            ["민수는 잘 익은 배를 씻어 먹는다.", "지수는 배의 껍질을 깎아 접시에 놓는다.", "과일 바구니에 배가 여러 개 담겨 있다.", "수진은 달콤한 배를 한 조각 먹었다.", "마트 과일 코너에서 배를 샀다.", "현우는 배를 잘라 친구와 나누어 먹었다.", "냉장고의 배를 꺼내 간식으로 먹었다."],
            ["큰 배가 항구를 천천히 떠난다.", "배는 바다를 건너 다른 항구로 이동한다.", "사람들이 부두에서 배에 짐을 싣는다.", "배가 파도를 지나 바다 위를 나아간다.", "항구에 도착한 배가 부두에 정박한다.", "선장은 배를 몰고 섬으로 향한다.", "바다 위의 배에는 사람과 화물이 타고 있다."],
            ["민수는 밥을 많이 먹어 배가 불렀다.", "지수는 배가 아파 손으로 배를 눌렀다.", "의사는 아픈 배의 상태를 확인했다.", "수진은 배가 고파서 식사를 기다렸다.", "현우는 웃다가 배가 아플 정도로 힘들었다.", "사람의 배는 몸 가운데 부분에 있다.", "운동 뒤 민수는 배에 힘을 주었다."],
            ["민수는 눈으로 멀리 있는 나무를 본다.", "지수는 눈이 피곤해서 잠시 감았다.", "사람은 눈으로 빛과 사물을 본다.", "수진의 눈에 작은 먼지가 들어갔다.", "현우는 눈을 뜨고 책을 읽었다.", "밝은 빛을 보면 눈이 부실 수 있다.", "의사는 아픈 눈을 살펴보았다."],
            ["겨울 아침에 하얀 눈이 내린다.", "산길에 눈이 두껍게 쌓였다.", "아이들은 쌓인 눈으로 작은 눈사람을 만들었다.", "추운 밤에 내린 눈이 길가에 남아 있다.", "햇빛이 강해지자 쌓인 눈이 조금씩 녹았다.", "창밖으로 눈이 천천히 내려왔다.", "겨울 숲의 나뭇가지 위에 눈이 쌓였다."],
            ["민수는 말로 자신의 생각을 친구에게 전했다.", "지수의 말에는 부탁하는 뜻이 담겨 있었다.", "선생님의 말을 학생들이 조용히 들었다.", "사람은 말을 사용해 질문하고 대답한다.", "수진은 고마운 마음을 말로 표현했다.", "현우는 짧은 말로 상황을 설명했다.", "대화에서는 상대의 말을 잘 듣는 것이 중요하다."],
            ["말이 목장에서 천천히 풀을 먹는다.", "갈색 말이 들판을 빠르게 달린다.", "사람이 말의 등에 올라타 이동한다.", "목장에는 여러 마리의 말이 살고 있다.", "말은 네 발로 걸으며 풀을 먹는다.", "농장 주인이 말에게 물을 주었다.", "말이 울타리 안에서 쉬고 있다."],
            ["민수는 빨간 사과를 씻어 먹었다.", "사과가 나무 가지에 여러 개 열렸다.", "지수는 사과를 잘라 접시에 담았다.", "마트에서 신선한 사과를 한 봉지 샀다.", "사과 껍질을 깨끗이 씻은 뒤 먹었다.", "수진은 과일 바구니에 사과를 넣었다.", "현우는 달콤한 사과를 간식으로 먹었다."],
            ["민수는 실수를 인정하고 지수에게 사과했다.", "지수는 민수의 진심 어린 사과를 받아들였다.", "잘못한 사람은 상대에게 사과할 수 있다.", "수진은 늦은 일에 대해 친구에게 사과했다.", "현우의 사과에는 미안한 마음이 담겨 있었다.", "사과를 받은 친구는 다시 대화를 시작했다.", "민수는 자신의 잘못을 설명한 뒤 정중히 사과했다."],
            ["민수의 차가 도로를 따라 이동한다.", "지수는 차를 주차장에 세웠다.", "차에는 사람이 타고 이동할 수 있다.", "현우는 차의 문을 열고 좌석에 앉았다.", "도로 위의 차가 신호등 앞에서 멈췄다.", "수진은 차를 타고 학교로 갔다.", "주차된 차에는 네 개의 바퀴가 보였다."],
            ["민수는 따뜻한 차를 컵에 따라 마셨다.", "지수는 향이 좋은 차를 천천히 마신다.", "뜨거운 물에 찻잎을 넣어 차를 만들었다.", "수진은 식사 뒤 따뜻한 차 한 잔을 마셨다.", "컵 속의 차에서 은은한 향이 난다.", "현우는 차가 식기를 기다렸다가 마셨다.", "친구들은 테이블에 앉아 차를 마시며 이야기했다."],
        ]
        rows = []
        for round_index in range(7):
            for sense in senses:
                if len(rows) >= 70:
                    break
                rows.append(sense[round_index])
            if len(rows) >= 70:
                break
        return corpus_v1._take(rows, 70, "polysemy")

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

    corpus_v1.gen_paraphrases = gen_paraphrases
    corpus_v1.gen_question_answer = gen_question_answer
    corpus_v1.gen_negative_contrast = gen_negative_contrast
    corpus_v1.gen_polysemy = gen_polysemy
    corpus_v1.eval_manifest = eval_manifest
    corpus_v1.quality_patch_version = VERSION
    return corpus_v1
