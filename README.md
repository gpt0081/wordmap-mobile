# Obsidian WordMap Mobile

Android + Termux에서 실행되는 로컬 WordMap 실험 서버입니다.

- Obsidian Device Storage Vault 자동 탐색
- 말뭉치 → 단어 노드/연결 생성
- Obsidian `[[wiki link]]` 노트 생성
- 질문 → 그래프 1~3홉 탐색
- 프로그램 코드는 GitHub에, 데이터는 Obsidian Vault에 분리 저장

## 데이터 안전 구조

프로그램:

```text
~/wordmap-mobile/
```

사용자 데이터:

```text
/storage/emulated/0/.../SecondBrain/WordMap/
```

`git pull` 또는 `update.sh`는 Obsidian의 Corpus/Words를 직접 삭제하지 않습니다.

## 폰 최초 설치

Termux:

```bash
pkg install -y git python
termux-setup-storage
cd ~
git clone https://github.com/gpt0081/wordmap-mobile.git
cd ~/wordmap-mobile
bash start.sh
```

브라우저:

```text
http://127.0.0.1:8765
```

## 이후 업데이트

서버가 실행 중이면 먼저 해당 Termux 세션에서 `Ctrl+C`.

```bash
cd ~/wordmap-mobile
bash update.sh
bash start.sh
```

## 상태 점검

```bash
cd ~/wordmap-mobile
bash doctor.sh
```

## 설계 원칙

- `Corpus`는 원본 데이터
- `Words`와 `graph.json`은 알고리즘으로 재생성 가능한 결과물
- 코드 업데이트와 Vault 데이터 업데이트는 분리
- 자동 업데이트 대신 사용자가 명시적으로 `update.sh` 실행
