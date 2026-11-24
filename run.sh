#!/usr/bin/env bash
# GraphInsight AI - start the dashboard on Linux / macOS     (Developer: Hamid Yarali)
# Usage: ./run.sh [--check]      (--check only verifies the environment)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
CHECK=0; [ "${1:-}" = "--check" ] && CHECK=1

die() { echo; echo "[ERROR] $*" >&2; exit 1; }
trap 'echo; echo "[ERROR] Stopped unexpectedly (line $LINENO). See the message above and data/logs/graphinsight.log" >&2' ERR

echo "============================================================"
echo "  GraphInsight AI                     (Developer: Hamid Yarali)"
echo "============================================================"

find_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' >/dev/null 2>&1; then
      echo "$c"; return 0
    fi
  done
  return 1
}
PY="$(find_python)" || die "Python 3.8 or newer was not found (Ubuntu: sudo apt install python3 python3-venv | macOS: brew install python@3.12)."
echo "[OK] $($PY --version)"

# permissions of the data folder and of the scripts
mkdir -p data/uploads data/projects data/outputs data/logs
[ -w data ] || die "The folder '$SCRIPT_DIR/data' is not writable (chmod -R u+w data)."
[ -x run.sh ] || chmod +x run.sh install.sh 2>/dev/null || true

if [ ! -x ".venv/bin/python" ]; then
  [ "$CHECK" = 1 ] && { echo "[check] virtual environment missing - it is created on the first normal start"; exit 0; }
  echo "[..] Creating the virtual environment (first run only) ..."
  "$PY" -m venv .venv || die "Could not create the virtual environment. On Debian/Ubuntu: sudo apt install python3-venv"
fi
VPY="$SCRIPT_DIR/.venv/bin/python"

if command -v sha256sum >/dev/null 2>&1; then HASH="$(sha256sum requirements.txt | cut -d' ' -f1)"; else HASH="$(shasum -a 256 requirements.txt | cut -d' ' -f1)"; fi
OLD=""; [ -f .venv/.requirements.sha256 ] && OLD="$(cat .venv/.requirements.sha256)"
if [ "$HASH" = "$OLD" ]; then
  echo "[OK] Dependencies are up to date."
elif [ "$CHECK" = 1 ]; then
  echo "[check] dependencies are not installed yet - run ./install.sh"; exit 0
else
  echo "[..] Installing dependencies (first run: a few minutes, needs internet) ..."
  "$VPY" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "$VPY" -m pip install -r requirements.txt || die "Installing the dependencies failed. Check the internet connection / proxy, or use Python 3.10 / 3.11 / 3.12."
  echo "$HASH" > .venv/.requirements.sha256
fi

command -v tesseract >/dev/null 2>&1 || echo "[WARNING] Tesseract OCR not installed: axis numbers must be typed manually (Ubuntu: sudo apt install tesseract-ocr | macOS: brew install tesseract)."

[ "$CHECK" = 1 ] && { echo "[check] environment OK"; exit 0; }
echo
echo "[OK] Starting GraphInsight AI at  http://127.0.0.1:8501     (Ctrl+C to stop)"
echo
exec "$VPY" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
