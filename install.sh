#!/usr/bin/env bash
# GraphInsight AI - installation for Linux / macOS     (Developer: Hamid Yarali)
# Usage: ./install.sh [--force] [--check]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
FORCE=0; CHECK=0
for a in "$@"; do case "$a" in --force) FORCE=1;; --check) CHECK=1;; esac; done

die() { echo; echo "[ERROR] $*" >&2; exit 1; }
trap 'echo; echo "[ERROR] The installation stopped unexpectedly (line $LINENO). See the message above." >&2' ERR

echo "============================================================"
echo "  GraphInsight AI - installation      (Developer: Hamid Yarali)"
echo "============================================================"

find_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' >/dev/null 2>&1; then
      echo "$c"; return 0
    fi
  done
  return 1
}
PY="$(find_python)" || die "Python 3.8 or newer was not found. Install it (Ubuntu: sudo apt install python3 python3-venv python3-pip | macOS: brew install python@3.12)."
echo "[OK] $($PY --version) ($PY)"

mkdir -p data/uploads data/projects data/outputs data/logs
[ -w data ] || die "The folder '$SCRIPT_DIR/data' is not writable. Fix the permissions (chmod -R u+w data)."

if [ ! -x ".venv/bin/python" ]; then
  [ "$CHECK" = 1 ] && { echo "[check] virtual environment missing (it will be created on install)"; exit 0; }
  echo "[..] Creating the virtual environment ..."
  "$PY" -m venv .venv || die "Could not create the virtual environment. On Debian/Ubuntu run: sudo apt install python3-venv"
fi
VPY="$SCRIPT_DIR/.venv/bin/python"

if command -v sha256sum >/dev/null 2>&1; then HASH="$(sha256sum requirements.txt | cut -d' ' -f1)"; else HASH="$(shasum -a 256 requirements.txt | cut -d' ' -f1)"; fi
OLD=""; [ -f .venv/.requirements.sha256 ] && OLD="$(cat .venv/.requirements.sha256)"
[ "$FORCE" = 1 ] && OLD=""
if [ "$HASH" = "$OLD" ]; then
  echo "[OK] Dependencies are already installed (requirements.txt unchanged)."
elif [ "$CHECK" = 1 ]; then
  echo "[check] dependencies need to be installed"; exit 0
else
  echo "[..] Installing dependencies (a few minutes the first time) ..."
  "$VPY" -m pip install --upgrade pip >/dev/null 2>&1 || true
  "$VPY" -m pip install -r requirements.txt || die "Installing the dependencies failed (no internet / proxy / unsupported Python version?). Read the pip message above."
  echo "$HASH" > .venv/.requirements.sha256
fi

if command -v tesseract >/dev/null 2>&1; then
  echo "[OK] Tesseract OCR found ($(tesseract --version 2>&1 | head -n1))"
else
  echo "[WARNING] Tesseract OCR is not installed: axis numbers must then be typed manually."
  echo "          Ubuntu: sudo apt install tesseract-ocr   |   macOS: brew install tesseract"
fi
chmod +x run.sh install.sh 2>/dev/null || true
echo
echo "Installation finished. Start with:  ./run.sh   (http://127.0.0.1:8501)"
