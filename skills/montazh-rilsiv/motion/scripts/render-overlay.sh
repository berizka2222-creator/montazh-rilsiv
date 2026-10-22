#!/bin/bash
# Transparent element for a reel (reel-editor overlay card): VP9 WebM with alpha, 1080x1920, bg forced to "none".
# usage: scripts/render-overlay.sh <ElementId> '<props json>' <out.webm>
#   e.g. scripts/render-overlay.sh Counter '{"value":87,"suffix":"%","label":"окупність","duration":3}' ~/reels/<reel>/overlays/roi.webm
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/sync-brand.py >/dev/null   # their brand.json -> colours, fonts, elements
id="$1"; props="${2:-{\}}"; out="$3"
mkdir -p "$(dirname "$out")"
merged=$(node -e 'const p=JSON.parse(process.argv[1]);p.bg="none";console.log(JSON.stringify(p))' "$props")
npx remotion render "$id" "$out" --props="$merged" --codec=vp9 --image-format=png --pixel-format=yuva420p --log=error
echo "overlay: $out"
