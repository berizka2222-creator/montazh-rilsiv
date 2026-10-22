#!/bin/bash
# Finished video (brand background): H.264 MP4 for Instagram / ads.
# usage: scripts/render.sh <CompositionId> <props.json> <out.mp4>     (MotionReel for a whole motion reel)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/sync-brand.py >/dev/null   # their brand.json -> colours, fonts, elements
id="$1"; props="$2"; out="$3"
mkdir -p "$(dirname "$out")"
npx remotion render "$id" "$out" --props="$props" --codec=h264 --crf=16 --image-format=jpeg --jpeg-quality=95 --log=error
echo "video: $out"
