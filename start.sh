#!/data/data/com.termux/files/usr/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "$HOME/storage/shared" ]; then
  echo "[WordMap] Android 저장소 연결이 필요합니다."
  termux-setup-storage || true
  echo "[WordMap] 권한을 허용한 뒤 다시 start.sh를 실행하세요."
  exit 1
fi

if ! command -v python >/dev/null 2>&1; then
  echo "[WordMap] Python이 없어 설치합니다."
  pkg update -y
  pkg install -y python
fi

PORT="${WORDMAP_PORT:-8765}"
URL="http://127.0.0.1:${PORT}"

echo
echo "=============================================="
echo " Obsidian WordMap Mobile"
echo " Version: $(cat VERSION 2>/dev/null || echo unknown)"
echo " URL: $URL"
echo " 종료: Ctrl+C"
echo "=============================================="
echo

(
  sleep 1
  if command -v termux-open-url >/dev/null 2>&1; then
    termux-open-url "$URL" >/dev/null 2>&1 || true
  fi
) &

exec python wordmap_mobile.py --host 127.0.0.1 --port "$PORT"
