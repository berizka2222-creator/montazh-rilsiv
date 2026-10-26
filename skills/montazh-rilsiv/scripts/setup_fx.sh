#!/usr/bin/env bash
# One-time: Python for Vibha's 42 video effects (vendor/vibha-fx): numpy, OpenCV, Pillow, MediaPipe in their own .venv.
# MediaPipe needs Python 3.10-3.12, so the skill's usual Python is not used. Safe to re-run: prints READY when set.
set -e
D="$(cd "$(dirname "$0")/../vendor/vibha-fx" && pwd)"; cd "$D"
VPY=".venv/bin/python"; [ -x "$VPY" ] || VPY=".venv/Scripts/python.exe"
if [ -x "$VPY" ] && "$VPY" -c "import mediapipe, cv2, PIL, numpy, fontTools" 2>/dev/null; then echo READY; exit 0; fi
PY=""
for v in python3.12 python3.11 python3.10 py; do
  if command -v "$v" >/dev/null 2>&1; then
    if [ "$v" = py ]; then for m in 3.12 3.11 3.10; do py -$m -c "1" 2>/dev/null && { PY="py -$m"; break; }; done
    elif "$v" -c 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)' 2>/dev/null; then PY="$v"; fi
  fi
  [ -n "$PY" ] && break
done
if [ -n "$PY" ]; then $PY -m venv .venv
elif command -v uv >/dev/null 2>&1; then uv venv -q -p 3.12 .venv; UV=1
else echo "NEED_PYTHON312: install Python 3.12 (Mac: brew install python@3.12, Windows: winget install Python.Python.3.12), then run this again"; exit 1; fi
VPY=".venv/bin/python"; [ -x "$VPY" ] || VPY=".venv/Scripts/python.exe"
if [ -n "${UV:-}" ]; then uv pip install -q -p "$VPY" -r requirements.txt   # a uv venv has no pip of its own
else "$VPY" -m pip install -q --upgrade pip; "$VPY" -m pip install -q -r requirements.txt; fi
"$VPY" -c "import mediapipe, cv2, PIL, numpy, fontTools; print('READY')"
