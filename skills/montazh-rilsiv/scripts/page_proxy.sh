#!/usr/bin/env bash
# 540x960 video for the review page: source clip (or any video) + an audio file, sized to stay under the 20 MB upload limit.
# On a Mac the media engine decodes and encodes (a 3 min 4K clip in ~1 min, not ~4 with libx264).
# Usage: page_proxy.sh <video> <audio or -> <out.mp4>      ("-" keeps the video's own sound)
set -euo pipefail
V="$1"; A="$2"; OUT="$3"
DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")"
# 18.5 MB budget: audio 96 kbps, the rest video, never above 1.2 Mbps
VB="$(python3 -c "d=float('$DUR');print(max(250,min(1200,int(18.5*8*1024/d-96-20))))")"
HW=(); ENC=(-c:v libx264 -preset veryfast -b:v "${VB}k" -maxrate "$((VB*13/10))k" -bufsize "$((VB*2))k")
if [ "$(uname)" = Darwin ]; then HW=(-hwaccel videotoolbox); ENC=(-c:v h264_videotoolbox -b:v "${VB}k" -maxrate "$((VB*13/10))k" -bufsize "$((VB*2))k" -allow_sw 1); fi
if [ "$A" = "-" ]; then MAP=(-map 0:v:0 -map "0:a:0?"); IN2=(); else MAP=(-map 0:v:0 -map 1:a:0); IN2=(-i "$A"); fi
nice -n 10 ffmpeg -v error -y "${HW[@]}" -i "$V" ${IN2[@]+"${IN2[@]}"} "${MAP[@]}" -vf "scale=540:960:force_original_aspect_ratio=increase,crop=540:960" \
  "${ENC[@]}" -g 30 -pix_fmt yuv420p -c:a aac -b:a 96k -movflags +faststart "$OUT"
echo "$OUT $(( $(stat -f %z "$OUT" 2>/dev/null || stat -c %s "$OUT") / 1048576 )) MB, video ${VB} kbps"
