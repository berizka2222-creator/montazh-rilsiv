#!/bin/bash
# Builds the website embed: dist-embed/motion-assets/ (motion-embed.js + fonts + chrome). Copy that folder into the site.
# usage: scripts/build-embed.sh [site-folder]   (with a site folder it also copies motion-assets/ there)
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/sync-brand.py >/dev/null   # their brand.json -> colours, fonts, elements
out=dist-embed/motion-assets
rm -rf dist-embed && mkdir -p "$out"
node_modules/.bin/esbuild src/player/embed.tsx --bundle --minify --format=iife --target=es2020 \
  --define:process.env.NODE_ENV='"production"' --outfile="$out/motion-embed.js" --log-level=warning
cp -r public/fonts "$out/"; [ -d public/chrome ] && cp -r public/chrome "$out/"
cp scripts/embed-demo.html dist-embed/index.html
du -sh "$out" "$out/motion-embed.js"
if [ -n "${1:-}" ]; then rm -rf "$1/motion-assets"; cp -r "$out" "$1/"; echo "copied to $1/motion-assets"; fi
