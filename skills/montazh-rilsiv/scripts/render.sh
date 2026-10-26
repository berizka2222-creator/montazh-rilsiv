#!/usr/bin/env bash
# Build the reel from edit.json and render it. Logs how long each part took to <reel>/timings.log.
# Usage: render.sh <reel-folder> [--capcut] [--final]
# Low priority throughout. REEL_DRAFT=1: 540p draft.mp4, 2 Chrome workers (3 above 8 GB). Otherwise final.mp4 at 1080p (--final: the brand
# resolution, e.g. 4K), 1 worker on an 8 GB Mac.
set -euo pipefail
REEL="$(cd "$1" && pwd)"; shift
FINAL=0; ARGS=(); for a in "$@"; do [ "$a" = "--final" ] && FINAL=1 || ARGS+=("$a"); done
MEM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 17179869184) / 1073741824 ))
WORKERS="${REEL_WORKERS:-$([ "$MEM_GB" -le 8 ] && echo 1 || echo 2)}"   # each worker is a Chrome; on 8 GB two run out of memory, time out and redo frames
S="$(cd "$(dirname "$0")" && pwd)"
BRAND="${REELS_HOME:-$HOME/reels}/brand.json"
RES="$(python3 -c "import json;r=json.load(open('$BRAND')).get('resolution',[1080,1920]);print('portrait-4k' if r[0]>=2160 else 'portrait')")"
[ "$FINAL" = 1 ] || RES=portrait                 # previews at 1080p: a quarter of the pixels of 4K
stamp() { echo "$(date +%s) $1" >> "$REEL/timings.log"; }
# low priority, but never past 19: the renderer sets its own setup worker to 19, and a shell that already runs jobs niced
# (zsh puts background jobs at +5) plus nice 15 = 20 makes that a priority raise macOS refuses (uv_os_setpriority EACCES)
# Git Bash's ps has no -o: never let that stop the script (set -e + pipefail)
CUR_NICE="$( (ps -o nice= -p $$ 2>/dev/null || true) | tr -d ' ')"; case "$CUR_NICE" in ''|*[!0-9-]*) CUR_NICE=0;; esac; NI=$(( 19 - ${CUR_NICE:-0} )); [ "$NI" -gt 15 ] && NI=15; [ "$NI" -lt 0 ] && NI=0

# a preview cut leaves a 1080p master.mp4; re-cut it at the brand resolution so the final isn't an upscale
if [ "$FINAL" = 1 ] || [ -z "${REEL_DRAFT:-}" ]; then   # the real render needs a full-quality master: a draft cut (540p) is re-cut first
  WANT="$(python3 -c "import json;print(json.load(open('$BRAND')).get('resolution',[1080,1920])[1])")"
  [ "$FINAL" = 1 ] || WANT=1920
  HAVE="$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$REEL/master.mp4")"
  if [ "$HAVE" -lt "$WANT" ]; then echo "master.mp4 is ${HAVE}p, re-cutting at ${WANT}p for the final"; env -u REEL_PREVIEW -u REEL_DRAFT python3 "$S/cut.py" "$REEL"; python3 "$S/precheck.py" "$REEL" | tail -3; fi
fi

[ -s "$S/../engine/gsap.min.js" ] || bash "$S/setup_engine.sh"
# graphics checked on stills first (fx_check.py): a render is never how we find a wrong effect
[ -n "${REEL_NO_CHECK:-}" ] || python3 "$S/fx_check.py" "$REEL" --verify || exit 3
stamp "fx:start"; python3 "$S/fx_pass.py" "$REEL"; stamp "fx:end"   # Vibha's effects («fx» cards) into the cut first; nothing to do without them
stamp "build:start"; python3 "$S/build_reel.py" "$REEL" ${ARGS[@]+"${ARGS[@]}"}; stamp "build:end"
stamp "render:start"
if [ -n "${REEL_DRAFT:-}" ]; then   # fast review draft at 540x960 (build_reel.py shrinks the stage); -> draft.mp4, final.mp4 untouched
  # 540p frames are small, so HyperFrames' automatic low-memory profile (1 worker) is switched off. 3 workers were faster on a
  # 30 s draft, but on a 90 s reel with many motions (8 GB) they timed out and redid 408 frames in one worker: 6m48 instead
  # of ~2 min (2026-10-24). 2 workers on 8 GB, 3 on bigger Macs. Fast capture can't help: glass cards use backdrop-filter.
  nice -n "$NI" npx -y hyperframes@0.8.145 render "$REEL/proj" --workers "${REEL_DRAFT_WORKERS:-$([ "$MEM_GB" -le 8 ] && echo 2 || echo 3)}" --no-low-memory-mode --gpu -o "$REEL/draft.mp4" --quality draft --quiet
  stamp "render:end"; echo "draft: $REEL/draft.mp4"; exit 0
fi
if ! nice -n "$NI" npx -y hyperframes@0.8.145 render "$REEL/proj" --workers "$WORKERS" -o "$REEL/final.mp4" --resolution "$RES" --quality delivery --crf "${REEL_CRF:-14}" --quiet; then   # CRF 14: graphics and skin stay clean through Instagram's own re-encode
  # 2026-10-26: on an 8 GB Mac the one-worker (low-memory, sequential) capture stalled at the same frames 8 times in a row;
  # two parallel workers got through (frames they miss are retried on one worker). Same path the drafts take.
  echo "final render failed: retrying with 2 parallel workers"
  nice -n "$NI" npx -y hyperframes@0.8.145 render "$REEL/proj" --workers 2 --no-low-memory-mode -o "$REEL/final.mp4" --resolution "$RES" --quality delivery --crf "${REEL_CRF:-14}" --quiet
fi
stamp "render:end"
# Final mix. Optional music bed (brand.json "music": path) sits ~18 dB under the voice and ducks further while she talks.
# Then bring the whole mix to -14 LUFS (video copied, not re-encoded).
MUSIC="$(python3 -c "import json,os;m=json.load(open('$BRAND')).get('music');print(os.path.expanduser(m) if m else '')")"
if [ -n "$MUSIC" ] && [ -f "$MUSIC" ]; then
  ffmpeg -v error -y -i "$REEL/final.mp4" -stream_loop -1 -i "$MUSIC" -filter_complex \
    "[1:a]volume=-18dB,afade=t=in:d=0.5[m];[0:a]asplit[v][key];[m][key]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[md];[v][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=7[a]" \
    -map 0:v -map "[a]" -c:v copy -ar 48000 -c:a aac -b:a 256k "$REEL/final_ln.mp4"
else
  ffmpeg -v error -y -i "$REEL/final.mp4" -c:v copy -af "loudnorm=I=-14:TP=-1.5:LRA=7" -ar 48000 -c:a aac -b:a 256k "$REEL/final_ln.mp4"
fi
mv "$REEL/final_ln.mp4" "$REEL/final.mp4"
python3 "$S/timings.py" "$REEL"
# a Mac notification when the render is done (the person may be away from the screen)
command -v osascript >/dev/null && osascript -e "display notification \"$(basename "$REEL")\" with title \"Рілс відрендерено\" sound name \"Glass\"" >/dev/null 2>&1 || true
