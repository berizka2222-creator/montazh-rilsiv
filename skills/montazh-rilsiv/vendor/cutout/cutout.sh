#!/usr/bin/env bash
# Cut the person out of a clip -> transparent WebM (VP9 + alpha), for «за мною».
#   cutout.sh in.mp4 out.webm
# Mac: Apple Vision person segmentation (Neural Engine, ~0.1-0.3 s a frame; keeps hair, mic, hands far better than u2net).
# The binary is built once from cutout_vision.swift. Exit 3 = not available here (build_reel then uses HyperFrames' cut-out).
set -e
D="$(cd "$(dirname "$0")" && pwd)"; IN="$1"; OUT="$2"
BIN="$D/cutout_vision"
if [ ! -x "$BIN" ] || [ "$D/cutout_vision.swift" -nt "$BIN" ]; then
  command -v swiftc >/dev/null 2>&1 || exit 3
  swiftc -O "$D/cutout_vision.swift" -o "$BIN" 2>/dev/null || exit 3
fi
M="$(mktemp -d)"; trap 'rm -rf "$M"' EXIT
"$BIN" "$IN" "$M"
FPS="$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 "$IN")"
SZ="$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=s=x:p=0 "$IN")"
# a touch of blur on the mask edge so hair blends; the mask's own soft values are kept
ffmpeg -nostdin -v error -y -i "$IN" -framerate "$FPS" -i "$M/%05d.png" \
  -filter_complex "[1:v]format=gray,scale=${SZ/x/:}:flags=bicubic,gblur=sigma=0.8[m];[0:v][m]alphamerge,format=yuva420p" \
  -an -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 22 -row-mt 1 -deadline good -cpu-used 4 -auto-alt-ref 0 "$OUT"
