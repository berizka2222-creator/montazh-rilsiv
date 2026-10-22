#!/bin/bash
# Save an API key without it ever showing in the chat: a hidden-input dialog on the Mac writes it straight into
# ~/.config/reels/.env (chmod 600) and prints only its length.
#   set_key.sh PIXABAY_API_KEY | PEXELS_API_KEY | GIPHY_API_KEY | ELEVENLABS_API_KEY
set -euo pipefail
NAME="${1:?key name, e.g. PEXELS_API_KEY}"
case "$NAME" in
  PEXELS_API_KEY) HINT="Встав ключ Pexels (pexels.com/api → Your API Key)";;
  PIXABAY_API_KEY) HINT="Встав ключ Pixabay (pixabay.com/api/docs → після входу ключ у рядку key)";;
  GIPHY_API_KEY)  HINT="Встав ключ GIPHY (developers.giphy.com → Create an App → API Key)";;
  ELEVENLABS_API_KEY) HINT="Встав API-ключ ElevenLabs (починається з sk_)";;
  *) HINT="Встав ключ $NAME";;
esac
K="$(osascript -e "text returned of (display dialog \"$HINT\" default answer \"\" with hidden answer buttons {\"Скасувати\",\"OK\"} default button \"OK\" giving up after 600)")" || { echo "cancelled"; exit 1; }
K="$(printf '%s' "$K" | tr -d '[:space:]')"
[ -n "$K" ] || { echo "empty key"; exit 1; }
ENV="$HOME/.config/reels/.env"; mkdir -p "$(dirname "$ENV")"; touch "$ENV"
grep -v "^$NAME=" "$ENV" > "$ENV.tmp" || true
printf '%s=%s\n' "$NAME" "$K" >> "$ENV.tmp"; mv "$ENV.tmp" "$ENV"; chmod 600 "$ENV"
echo "$NAME saved (${#K} characters)"
