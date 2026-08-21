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
  wordmap_gpt2.py event_guidance.py dialogue_session.py priming.py associative_cascade.py dialogue_corpus.py \
  visualizer.py cognition_visual_patch.py lexicon_notes.py node_health.py credit_learning.py cognition_learning_bridge.py experiment_harness.py \
  ui_patch.py corpus_web.py visual_ui.py node_health_web.py learning_web.py experiment_web.py workspace_ui.py chat_ui_patch.py cognition_ui_patch.py benchmark.py \
  selftest.py selftest_gpt2.py selftest_v010.py selftest_v012.py selftest_v013.py selftest_v014.py selftest_v015.py selftest_v016.py selftest_v017.py selftest_v0171.py selftest_v0172.py selftest_v018.py selftest_visualizer.py \
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
  && python selftest_v0172.py \
  && python selftest_v018.py \
  && python selftest_visualizer.py \
  && python -c "import launch, credit_learning; assert 'wuWorkspace' in launch.wordmap_mobile.HTML; assert 'wuDeleteHistoryBtn' in launch.wordmap_mobile.HTML; assert 'wuCognitionPanel' in launch.wordmap_mobile.HTML; assert launch.core.priming_version == '0.18.0'; assert launch.core.associative_cascade_version == '0.18.0'; assert credit_learning._origin_key('점화') == '점화'; assert credit_learning._origin_key('연상 폭포') == '연상 폭포'; print('[WordMap] v0.18 runtime wiring: OK')"; then
  NEW_VERSION="$(cat VERSION 2>/dev/null || echo unknown)"
  echo "[WordMap] 업데이트 완료: $OLD_VERSION -> $NEW_VERSION"
  echo "[WordMap] v0.18 Priming + Associative Cascade가 적용되었습니다."
  echo "[WordMap] 이전 대화의 핵심 개념은 점화 메모리로 남고 턴마다 자동 감쇠합니다."
  echo "[WordMap] 현재 입력과 점화에서 최대 3파동의 연상 폭포가 퍼지며 사고경로를 기록합니다."
  echo "[WordMap] 연결이 지나치게 많은 허브 노드는 자동 감점되고 ContextMap과 충돌하는 연상은 억제됩니다."
  echo "[WordMap] 점화/연상은 후보 선택에 영향을 주지만 원본 Corpus와 지식 그래프 사실은 수정하지 않습니다."
  echo "[WordMap] Credit Backprop은 점화와 연상 폭포의 유용성을 서로 다른 출처 가중치로 학습합니다."
  echo "[WordMap] 대화 화면과 시각화 단계에서 점화 메모리·연상 경로·억제를 확인할 수 있습니다."
  echo "[WordMap] 기존 기본 Corpus, 대화 UI, Credit Backprop, Benchmark 데이터는 유지합니다."
  echo "[WordMap] 서버가 실행 중이었다면 Ctrl+C 후 bash start.sh 로 다시 실행하세요."
else
  echo "[WordMap] 새 버전 검사 실패. 이전 버전으로 되돌립니다."
  git reset --hard "$OLD_COMMIT"
  exit 1
fi
