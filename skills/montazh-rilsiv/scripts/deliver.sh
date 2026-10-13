#!/usr/bin/env bash
# Make the upload copy: same resolution, high-bitrate H.264, fast-start, saved to the brand's delivery folder.
# Usage: deliver.sh <final.mp4> "<clear name>"
set -euo pipefail
SRC="$1"; NAME="${2:-$(basename "${SRC%.*}")}"
BRAND="${REELS_HOME:-$HOME/reels}/brand.json"
DIR="$(python3 -c "import json,os;print(os.path.expanduser(json.load(open('$BRAND')).get('deliver_dir','~/Movies/Reels')))")"
mkdir -p "$DIR"; OUT="$DIR/$NAME.mp4"

H="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$SRC")"
if [ "$H" -ge 3000 ]; then MAX=45M; else MAX=30M; fi   # bitrate ceiling for a re-encode, 4K vs 1080p

# Every re-encode loses detail, so the render's own H.264 is copied as is when it is already upload-ready
# (8-bit 4:2:0 H.264 at or under 40 Mbit/s); otherwise one careful software encode, never the hardware encoder.
CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,pix_fmt -of csv=p=0 "$SRC")"
BR="$(ffprobe -v error -show_entries format=bit_rate -of csv=p=0 "$SRC")"
if [ "$CODEC" = "h264,yuv420p" ] && [ "${BR:-0}" -le 40000000 ]; then
  VENC=(-c:v copy); echo "video copied without re-encoding ($((BR / 1000000)) Mbit/s)" >&2
else
  VENC=(-c:v libx264 -preset slow -crf 14 -maxrate "$MAX" -bufsize "$MAX" -profile:v high -pix_fmt yuv420p)
fi
ffmpeg -hide_banner -loglevel error -y -i "$SRC" "${VENC[@]}" -tag:v avc1 \
  -c:a aac -b:a 256k -movflags +faststart "$OUT"
echo "$OUT"
