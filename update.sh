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
  echo "git status:"
  git status --short
  echo
  echo "코드 변경사항을 보존한 뒤 다시 실행하세요."
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

if python -m py_compile core.py cleaning.py relations.py ui_patch.py launch.py wordmap_mobile.py; then
  NEW_VERSION="$(cat VERSION 2>/dev/null || echo unknown)"
  echo "[WordMap] 업데이트 완료: $OLD_VERSION -> $NEW_VERSION"
  echo "[WordMap] 서버가 실행 중이었다면 Ctrl+C로 종료 후 bash start.sh 로 다시 실행하세요."
else
  echo "[WordMap] 새 코드 문법 검사 실패. 이전 버전으로 되돌립니다."
  git reset --hard "$OLD_COMMIT"
  exit 1
fi
