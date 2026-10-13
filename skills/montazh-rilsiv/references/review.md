# Reel Review page

A private page on the person's claude.ai account where they approve the edit before anything renders: cuts, graphics, captions, sound and colour, then a draft preview with timestamped notes. It needs Claude Code with Artifacts (the `Artifact` and `ArtifactData` tools) and the `db` + `assets` capabilities. If those aren't available, review in chat instead (rough-cut lines, then a card list) and skip this file.

## One time per reel

1. After transcribing and cleaning audio, run `python3 scripts/tighten.py <reel> --detect` so the "um"s are found (it writes `fillers.json`; without it the page shows no grey "um"s and none get cut). If it installs local Whisper first, that's normal. If it prints `FILLERS NOT DETECTED` (exit code 3), tell them the "um"s won't be cut automatically and that they can tap them out on the page. Then write `proposal.json` in the reel folder (format in the header of `scripts/review_sync.py`): the kept lines, accent words, and every graphic anchored to a spoken word with its `place` box and sound.
2. `python3 scripts/review_sync.py export <reel> proposal.json <out>` → `<out>/reel.json` (also saved as `<reel>/review_reel.json`).
3. Make the assets (keep them light, `nice -n 15`):
   - a 540x960 source proxy of `raw.mov` with the **cleaned** `voice.wav` as its audio (h264, ~900 kbps). The raw phone audio is ~20 dB quieter, so a proxy with it makes the voice sound broken
   - per graphic: `thumb_<id>.jpg` (180x320 frame at its anchor word) and `img_<id>.jpg` (its screenshot/image, 480 wide)
   - `audio_original.mp4` / `audio_cleaned.mp4` (same 10 s), `colour_before.jpg` / `colour_after.jpg` (same frame, grade applied), `sfx_<name>.mp4` for each sound
   - the brand's caption fonts (.otf/.ttf/.woff2) **only if the person owns them and the page stays private**
   Asset uploads accept mp4 (audio too), jpg/png, fonts; not m4a or wav.
4. First time only: publish `review/reel-review.html` with `files: {"core.js": "review/core.js"}`, `capabilities: {"db": {"rules": [{"path": "reel", "write": "admin"}, {"path": "builds", "write": "admin"}]}, "assets": {}}` (only editors can change the reel data and the preview; anyone you share it with at Contributor level can still record review decisions), `icon: "video"`. Later reels reuse the same page URL.
5. Upload the assets to the page (`asset: true`, up to 25 per call), then write `reel/current` = `reel.json` plus `srcUrl`, per-graphic `thumbUrl`/`imgUrl`, `assets` {audioOriginal, audioCleaned, colourBefore, colourAfter, sfx{name:url}}, `fonts` {body, accent}. Delete `review/current` and `builds/latest` from the previous reel (ask first if they hold notes).
6. Send the link. Tell them: tap words to cut, use the «Накладення» tab to add their own photo/video at the current rough-cut moment and drag it into place (size: small right/left, big on top, full screen; effect: soft, slide, polaroid, glass, zoom; up to 20 MB), tap ⏸ / grey "um"s to keep them, Play rough cut to watch the live cut, then Build preview.

## Two rounds: their overlays first, then Claude's graphics

Their own photos/videos come before Claude's cards and motion, so the graphics plan goes around them instead of under them.
1. **Round 1 (cuts + overlays).** Export with only the hook card on the board (`"cards"` in proposal.json = the hook alone), send the link and tell them: cut on «Нарізка», then on «Накладення» put their own photos/videos where they want them (size, effect, drag the box on the player), then write «графіка». If they have nothing to add, they write «графіка» straight away.
2. **On «графіка».** `ArtifactData get review/current`, then `python3 scripts/review_sync.py overlays <reel> <review.json>`: it lists every overlay they placed (cut and source time, the word it hangs on, its box). Plan the cards and own motion around those: no card or motion in the same moment AND the same area as one of their overlays, nothing at all during a full-screen one, and nothing that repeats what their picture already shows. Write proposal.json with the hook + the new cards, re-run `export` (word indices don't change, so their cuts, captions and overlays stay valid), upload the new thumbs, and `ArtifactData update reel/current` with the new `board` (keep `srcUrl`, `assets`, `fonts`, `theme`). Any `CONFLICT` line from `overlays` must be fixed before they see the page.
3. **Round 2.** Tell them the graphics are on «Графіка», listed in time order with «твоє» / «від Claude», then «збери чернетку».

## When they say "build preview"

1. `ArtifactData get review/current` (save to a file). Missing is fine: it means "use the proposal".
2. `python3 scripts/review_sync.py import <reel> <review.json>` → `edl.json` + `edit.json`. Act on every `CHANGE REQUESTED`, `NOTE` and `REVISION` line it prints before rendering; for every `OVERLAY ... DOWNLOAD asset <id>` line, fetch their upload with `Artifact` `action: "read"`, `url` = the page, `path` = that asset id, `out_dir` = `<reel>/overlays` (it lands as `<id>.<ext>`; the card already points there); `BRAND CHANGE REQUESTED` only touches brand.json after they confirm.
3. `python3 scripts/snap_joins.py <reel>`, `REEL_PREVIEW=1 python3 scripts/cut.py <reel>`, then `python3 scripts/precheck.py <reel>` and fix everything it lists (JOIN, MISSING, CHECK) before `REEL_PREVIEW=1 bash scripts/render.sh <reel>` (1080p, 2 workers, low priority). Every extra render is ~6 min of their wait.
4. Grab frames at every graphic and the longest caption words; fix anything out of frame before sending.
5. 540p proxy of `final.mp4` → upload → `ArtifactData set builds/latest` {url, hash (from edit.json), at, cutDur}. The page compares that hash with the live decisions and marks the preview outdated when they change.

## Final

After they approve the draft: if the brand resolution is 1080x1920 the approved draft's `final.mp4` is the final, so go straight to QA and deliver (no second render). Only a 4K brand renders again with `bash scripts/render.sh <reel> --final` (it re-cuts the 1080p preview master first). CapCut follows SKILL.md step 8 (`"capcut": "ask"` = ask after delivering).
