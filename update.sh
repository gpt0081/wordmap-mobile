#!/data/data/com.termux/files/usr/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "[WordMap] git 설치 중..."
  pkg update -y
  pkg install -y git
fi

if [ ! -d ".git" ]; then
  echo "[WordMap] 이 폴더는 GitHub에서 clone한 저장소가 아닙니다."
  echo "[WordMap] ~/wordmap-mobile 로 git clone한 뒤 사용하세요."
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "[WordMap] 로컬 코드 변경사항이 있어 자동 업데이트를 중단합니다."
  git status --short
  exit 1
fi

OLD_COMMIT="$(git rev-parse HEAD)"
OLD_VERSION="$(cat VERSION 2>/dev/null || echo unknown)"

echo "[WordMap] GitHub 최신 버전 확인 중..."
git fetch origin

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse '@{u}')"

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "[WordMap] 이미 최신 버전입니다: $OLD_VERSION"
  exit 0
fi

echo "[WordMap] 업데이트 적용 중..."
git pull --ff-only

if python -m py_compile \
  core.py cleaning.py corpus_filter.py grammar.py lexicon.py language.py corpus_manager.py \
  relations.py relation_guard.py hybrid.py sequence.py generation.py generation_tokens.py \
  syntax_tags.py syntax_bridge.py event_graph.py activation.py wordmap_gpt2.py event_guidance.py \
  visualizer.py lexicon_notes.py node_health.py ui_patch.py corpus_web.py visual_ui.py node_health_web.py benchmark.py \
  selftest.py selftest_gpt2.py selftest_v010.py selftest_v012.py selftest_v013.py selftest_v014.py selftest_visualizer.py \
  launch.py wordmap_mobile.py \
  && python selftest.py \
  && python selftest_gpt2.py \
  && python selftest_v010.py \
  && python selftest_v012.py \
  && python selftest_v013.py \
  && python selftest_v014.py \
  && python selftest_visualizer.py; then
  NEW_VERSION="$(cat VERSION 2>/dev/null || echo unknown)"
  echo "[WordMap] 업데이트 완료: $OLD_VERSION -> $NEW_VERSION"
  echo "[WordMap] v0.14 Node Health / Orphan Analyzer가 추가되었습니다."
  echo "[WordMap] 진짜 고립, 약한 고립, 시각적 고립, 태그 필터 고립을 분리해 진단합니다."
  echo "[WordMap] 전문용어/희귀어와 고립 노드는 자동 삭제하지 않습니다."
  echo "[WordMap] 업그레이드 직후 전체 Corpus 재생성은 필요 없습니다. 웹의 '건강도 다시 계산'만 실행할 수 있습니다."
  echo "[WordMap] 말뭉치를 끄거나 수정/삭제했다면 기존처럼 활성 말뭉치로 전체 재생성을 실행하세요."
  echo "[WordMap] 서버가 실행 중이었다면 Ctrl+C 후 bash start.sh 로 다시 실행하세요."
else
  echo "[WordMap] 새 버전 검사 실패. 이전 버전으로 되돌립니다."
  git reset --hard "$OLD_COMMIT"
  exit 1
fi
