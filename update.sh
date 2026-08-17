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
  core.py cleaning.py corpus_filter.py grammar.py lexicon.py language.py corpus_manager.py corpus_roles.py \
  corpus_v1.py corpus_v1_quality.py default_corpus.py eval_manifest.py eval_manifest_patch.py corpus_integrity.py \
  relations.py relation_guard.py hybrid.py sequence.py generation.py generation_tokens.py \
  syntax_tags.py syntax_bridge.py event_graph.py temporal_event.py activation.py context_map.py \
  wordmap_gpt2.py event_guidance.py dialogue_session.py dialogue_corpus.py visualizer.py lexicon_notes.py node_health.py \
  credit_learning.py experiment_harness.py \
  ui_patch.py corpus_web.py visual_ui.py node_health_web.py learning_web.py experiment_web.py workspace_ui.py benchmark.py \
  selftest.py selftest_gpt2.py selftest_v010.py selftest_v012.py selftest_v013.py selftest_v014.py selftest_v015.py selftest_v016.py selftest_v017.py selftest_v0171.py selftest_visualizer.py \
  launch.py wordmap_mobile.py \
  && python selftest.py \
  && python selftest_gpt2.py \
  && python selftest_v010.py \
  && python selftest_v012.py \
  && python selftest_v013.py \
  && python selftest_v014.py \
  && python selftest_v015.py \
  && python selftest_v016.py \
  && python selftest_v017.py \
  && python selftest_v0171.py \
  && python selftest_visualizer.py \
  && python -c "import launch; assert 'wuWorkspace' in launch.wordmap_mobile.HTML; print('[WordMap] v0.17.1 runtime wiring: OK')"; then
  NEW_VERSION="$(cat VERSION 2>/dev/null || echo unknown)"
  echo "[WordMap] 업데이트 완료: $OLD_VERSION -> $NEW_VERSION"
  echo "[WordMap] v0.17.1 Bundled Default Corpus가 적용되었습니다."
  echo "[WordMap] 사용자가 제공한 patched Corpus v1 1,500문장이 앱 코드에 기본 말뭉치로 포함됩니다."
  echo "[WordMap] '저장된 말뭉치로 전체 재생성' 전에 기본 Corpus와 DEV/TEST 평가 파일을 자동 동기화합니다."
  echo "[WordMap] 사용자가 수정한 기본 파일과 파일별 ON/OFF 상태는 자동 동기화가 덮어쓰지 않습니다."
  echo "[WordMap] 기본 파일을 직접 삭제하면 자동 복원을 억제하며, 명시적 기본 Corpus 복원에서만 다시 설치됩니다."
  echo "[WordMap] 업로드된 blank-line 대화 묶음과 answers형 DEV/TEST manifest를 정식으로 지원합니다."
  echo "[WordMap] 기존 v0.17 Utility Workspace UI와 학습/실험 데이터는 유지합니다."
  echo "[WordMap] 서버가 실행 중이었다면 Ctrl+C 후 bash start.sh 로 다시 실행하세요."
else
  echo "[WordMap] 새 버전 검사 실패. 이전 버전으로 되돌립니다."
  git reset --hard "$OLD_COMMIT"
  exit 1
fi
