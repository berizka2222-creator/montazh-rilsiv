#!/usr/bin/env bash
# One-time: the Remotion motion library in the person's brand (~/motion + the motion-brand skill). Re-run safely any time.
#  - copies the template (../motion) to ~/motion if there is no project there yet (never overwrites one that exists)
#  - installs its packages (npm ci, ~1 GB, a few minutes the first time)
#  - installs the motion-brand skill to ~/.claude/skills/motion-brand if it isn't there
#  - takes colours, fonts and own elements from <REELS_HOME>/brand.json (scripts/sync-brand.py)
#  - renders one transparent test element and checks it
# MOTION_HOME overrides ~/motion (the reel skill's motions.py reads the same variable).
set -euo pipefail
SK="$(cd "$(dirname "$0")/.." && pwd)"
M="${MOTION_HOME:-$HOME/motion}"
if [ ! -f "$M/package.json" ]; then
  mkdir -p "$M"; cp -R "$SK/motion/." "$M/"; rm -rf "$M/skill"
  echo "motion project copied to $M"
fi
if [ ! -d "$HOME/.claude/skills/motion-brand" ]; then
  mkdir -p "$HOME/.claude/skills/motion-brand"; cp -R "$SK/motion/skill/." "$HOME/.claude/skills/motion-brand/"
  echo "motion-brand skill installed"
fi
cd "$M"
[ -d node_modules/@remotion/cli ] || npm ci --no-audit --no-fund --loglevel=error
python3 scripts/sync-brand.py
T="$(mktemp -d)/test.webm"
scripts/render-overlay.sh Counter '{"value":87,"suffix":"%","label":"тест","duration":1.5,"place":"top"}' "$T" >/dev/null
CODEC="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$T")"
[ "$CODEC" = "vp9" ] || { echo "motion test render failed (codec: ${CODEC:-none})" >&2; exit 1; }
rm -rf "$(dirname "$T")"
echo "motion ready: $M (test render ok)"
