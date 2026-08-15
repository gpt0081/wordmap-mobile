#!/data/data/com.termux/files/usr/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== WordMap Doctor ==="
echo "경로: $SCRIPT_DIR"
echo "버전: $(cat VERSION 2>/dev/null || echo unknown)"
echo "Python: $(python --version 2>&1 || echo '미설치')"
echo "Git: $(git --version 2>&1 || echo '미설치')"
echo "공유저장소: $([ -d "$HOME/storage/shared" ] && echo 연결됨 || echo 미연결)"
echo

if command -v python >/dev/null 2>&1; then
  echo "--- Vault 탐색 결과 ---"
  python wordmap_mobile.py --scan-only || true
fi
