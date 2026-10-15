# Reel Review page

A private page on the person's claude.ai account where they approve the edit before anything renders: cuts, graphics, captions, sound and colour, then a draft preview with timestamped notes. It needs Claude Code with Artifacts (the `Artifact` and `ArtifactData` tools) and the `db` + `assets` capabilities. If those aren't available, review in chat instead (rough-cut lines, then a card list) and skip this file.

## One time per reel

1. After transcribing and cleaning audio, run `python3 scripts/tighten.py <reel> --detect` so the "um"s are found (it writes `fillers.json`; without it the page shows no grey "um"s and none get cut). It reads the "um"s from the Scribe transcript, so run it after `transcribe.py`. If it prints `FILLERS NOT DETECTED` (exit code 3), transcript.json is missing: transcribe first. Then write `proposal.json` in the reel folder (format in the header of `scripts/review_sync.py`): the kept lines, accent words, and every graphic anchored to a spoken word with its `place` box and sound.
2. `python3 scripts/review_sync.py export <reel> proposal.json <out>` → `<out>/reel.json` (also saved as `<reel>/review_reel.json`).
3. Make the assets (keep them light, `nice -n 15`):
   - a 540x960 source proxy of `raw.mov` with the **cleaned** `voice.wav` as its audio (h264, ~900 kbps). The raw phone audio is ~20 dB quieter, so a proxy with it makes the voice sound broken
   - per graphic: `thumb_<id>.jpg` (180x320 frame at its anchor word) and `img_<id>.jpg` (its screenshot/image, 480 wide)
   - `audio_original.mp4` / `audio_cleaned.mp4` (same 10 s), `colour_before.jpg` / `colour_after.jpg` (same frame, grade applied), `sfx_<name>.mp4` for each sound
   - the brand's caption fonts (.otf/.ttf/.woff2) **only if the person owns them and the page stays private**
   Asset uploads accept mp4 (audio too), jpg/png, fonts; not m4a or wav.
   The page takes its look from `reel.json` `theme` (brand.json colours; an optional brand.json `"page"` block overrides any token, e.g. their website's background, accent, grid and glows, and `label` for the line above the title).
4. First time only: publish `review/reel-review.html` with `files: {"core.js": "review/core.js"}`, `capabilities: {"db": {"rules": [{"path": "reel", "write": "admin"}, {"path": "builds", "write": "admin"}]}, "assets": {}}` (only editors can change the reel data and the preview; anyone you share it with at Contributor level can still record review decisions), `icon: "video"`. Later reels reuse the same page URL.
   **«Мої файли» (db `library/files`):** their reusable photos, stickers and logos live on the page across reels. On first publish, and whenever `~/reels/assets/elements` gets new files, upload those PNGs (`asset: true`, up to 25 per call) and write `library/files` = `{items: [{id, url, name, kind: "image"}], updatedAt}`. Read it first and merge: keep every item they saved from the page (the «Зберегти в мої файли» tick), add only new names, never drop theirs.
5. Upload the assets to the page (`asset: true`, up to 25 per call), then write `reel/current` = `reel.json` plus `srcUrl`, per-graphic `thumbUrl`/`imgUrl`, `assets` {audioOriginal, audioCleaned, colourBefore, colourAfter, sfx{name:url}}, `fonts` {body, accent}. Delete `review/current` and `builds/latest` from the previous reel (ask first if they hold notes).
6. Send the link. Tell them: type the hook and CTA in the fields on «Графіка» (or approve yours), tap words to cut, use the «Накладення» tab to add their own photo/video at the current rough-cut moment and drag it into place and pull its corner to any size, sticker-small up to full screen (or tick «На весь екран»); effect: soft, slide, polaroid, glass, zoom; up to 20 MB; or pick one from «Мої файли», or add text; tick «За мною» to put it behind them), tap ⏸ / grey "um"s to keep them, Play rough cut to watch the live cut, then Build preview.

## The big button and the steps (no chat words needed)

The page shows steps (1 her edit → 2 Claude's proposals → 3 draft → 4 final) and one big button at the bottom. Each press saves a request in her review doc and sends Claude a «Send to Claude» comment on the artifact, which wakes this session while the artifact's watch says "auto-replies armed" (`ArtifactComments action: "watch"` lists it). The comment text starts with ▶ and names the step; treat it exactly like the chat word:
- `graphicsRequest` / «графіка» → round 2 below. When the proposals are on the board, write `reel/current` with `claudeRound` = previous + 1: the page reloads it in place, jumps to «Графіка» and shows a banner (no refresh needed).
- `buildRequest` / «збери чернетку» → "When they say build preview".
- `fixRequest` (revisions marked `sent`) / «виправ нотатки» → act on those revisions, re-render, new `builds/latest` with `fixedFor` = `fixRequest.at` (the decisions hash may not change, so this is how the page knows the notes were answered).
- `finalRequest` / «фінал» → QA, deliver, covers only if brand.json `covers` isn't false; then `builds/latest` gets `final: true` (step 4).
Reply in the comment thread in one line («Взяв, роблю пропозиції, ~10 хв») and resolve it when done. If no session is listening the page tells her to type the word in chat instead.

## «Стиль» tab (their style, in rounds)

The page also holds the style lab: db `style/round` (written by Claude: the round's sections and variants with their mp4/poster urls) and `style/votes` (her verdicts, notes and references: reel links and uploaded files). It works with or without a reel loaded. db `style/list` (from `~/reels/styles/list.json`) feeds the «Стиль монтажу» buttons on «Графіка»: her pick is `style` in the review doc (part of the decisions hash) and `review_sync.py import` turns it into `<reel>/style.txt`. The «Готово → Claude» button there sends a «Send to Claude» comment naming the round. Everything else (making rounds, reading verdicts, writing styles) is in `references/style-lab.md`.

## Face, captions and «За мною»

- Before `export`, run `python3 scripts/face_box.py <reel>`: macOS Vision finds the face on 12 frames and writes `<reel>/face.json`; `export` puts it into reel.json as `face`. Without it nothing is moved.
- `core.js` `layout()` moves every graphic that would cover the face or the captions: below the chin, or above the head, inside the frame Instagram leaves clear; when nothing fits, the captions step aside while that card shows (`quiet` in edit.json). The page marks these «відсунуто від обличчя»; `review_sync import` writes the new `y` / `box`.
- Captions: on «Субтитри» she picks «Над головою / Під підборіддям / Внизу» or drags a caption on the player; it is saved as `capY` in her review doc and goes into edit.json as `caption_y`.
- «За мною» on any graphic on «Графіка» sets `board.<id>.behind`; the card renders behind the person (cut-out on those seconds only). Behind the body it would not show, so `layout()` lifts it into the background above the head (big words/hook tuck ~35% behind the hair, lists and cards ~8%; too tall → shrunk with `zoom`), and `capsAround()` drops the captions that would overlap it under the chin for those seconds (per-caption `y` in edit.json).

## Colour and sounds on «Звук і колір»

- **Colour**: iPhone-style sliders (exposure, highlights, shadows, contrast, brightness, saturation, vibrance, warmth, clarity, sharpness, each -100..100). The page previews them with WebGL using `core.js` `gradeParams`; `review_sync.py import` writes `<reel>/grade.cube` and the ffmpeg chain into `edl.json` `grade`, and `cut.py` applies it. Untouched = no grade.
- **Sounds**: each sound on a graphic can be switched off or replaced from the library (`sfxSwap` in the review doc). The library lives in db `library/sfx` = `{items: [{name, label, cat, url}]}` and on disk in `sfx/` of this skill (copied into `~/reels/assets/sfx`; `build_reel.py` takes sounds from both, the person's own folder wins). First setup: upload every `sfx/*.wav` as an audio-only mp4 (`asset: true`) and write `library/sfx` with those urls, labels and categories from `sfx/library.json`.
- Their own sounds: a recording with sound, silence, sound… → `python3 scripts/slice_sfx.py <video> [names.txt]` cuts it into separate sounds in `~/reels/assets/sfx`.

## Effects they ask for («Ефекти» tab)

On «Ефекти» they pick a moment of the rough cut, describe an effect (a HyperFrames catalog name such as `count-up`, or their own words) and can attach photos/videos for it. The «Відкрити бібліотеку ефектів» button opens the catalog: the public one at hyperframes.heygen.com/catalog, or their own gallery page: set `libraryUrl` in the db doc `library/files` (works for every reel) or brand.json `"page"` `"library"`. `review_sync.py import` and `overlays` print each as `EFFECT REQUESTED @ cut …s for …s, from word "…": <text> | files: <name> -> DOWNLOAD asset <id> into <reel>/effects`.
- Download each file with `Artifact` `action: "read"`, `path` = the asset id, `out_dir` = `<reel>/effects`.
- A catalog name: `cd engine/hf && npx hyperframes add <name>` if it isn't installed yet, add it to `references/motions.md`, then a `motion` card at that moment with their files as `images`/vars. Their own words: build it as a `custom` motion (see SKILL.md «Own motion design on phrases»).
- It goes on «Графіка» as their item (like an overlay), so plan your cards around it. If a description is unclear, ask one short question before building.

## Two rounds: their overlays first, then Claude's graphics

Their own photos/videos come before Claude's cards and motion, so the graphics plan goes around them instead of under them.
1. **Round 1 (cuts + overlays).** Export with only the hook card on the board (`"cards"` in proposal.json = the hook alone), send the link and tell them: cut on «Нарізка», then on «Накладення» put their own photos/videos where they want them (size, effect, drag the box on the player), then write «графіка». If they have nothing to add, they write «графіка» straight away.
2. **On «графіка».** `ArtifactData get review/current`, then `python3 scripts/review_sync.py overlays <reel> <review.json>`: it lists every overlay they placed (cut and source time, the word it hangs on, its box). Plan the cards and own motion around those: no card or motion in the same moment AND the same area as one of their overlays, nothing at all during a full-screen one, and nothing that repeats what their picture already shows. Write proposal.json with the hook + the new cards, re-run `export` (word indices don't change, so their cuts, captions and overlays stay valid), upload the new thumbs, and `ArtifactData update reel/current` with the new `board` (keep `srcUrl`, `assets`, `fonts`, `theme`). Any `CONFLICT` line from `overlays` must be fixed before they see the page.
3. **Round 2.** Tell them the graphics are on «Графіка», listed in time order with «твоє» / «від Claude», then «збери чернетку».

## Several reels at once (3-5 clips in one go)

The same page holds a batch: a «Рілс» picker appears at the top when `reel/index` lists more than one reel. Each reel keeps its own decisions and preview.
- **Docs per reel:** `reel/<id>`, `review/<id>`, `builds/<id>`, with `<id>` = the reel folder name (e.g. `2026-10-14-hooks`). `reel/index` = `{items: [{id, title, status}]}` in the order she will review them; `status` is a short Ukrainian word the picker shows («готується», «перевіряєш», «рендериться», «чернетка готова», «фінал»). One reel on its own keeps using `reel/current` / `review/current` / `builds/latest` and no index; when a batch starts, delete `reel/index` items from the previous batch first (ask if their review docs hold notes).
- **Prepare in order, first one fast.** Make a folder per clip. Do reel 1 end to end (transcribe, clean, `tighten --detect`, proposal with the hook only, export, assets, `reel/<id>`, add it to `reel/index`) and send the link at once. Then prepare 2..n one by one while she reviews (`nice`, never two transcriptions at the same time); after each, add it to `reel/index` (the page tells her «наступний рілс готовий») and say it in one line.
- **Her steps per reel stay the same:** cuts + overlays → «графіка» → your cards → «збери чернетку». She names the reel («графіка 2», «збери чернетку 3»); if she doesn't, check `review/<id>` of every reel in the index for a new `buildRequest` or new overlays.
- **Render queue.** On «збери чернетку» for a reel: import, snap_joins, `REEL_PREVIEW=1 cut.py`, precheck and fixes as usual, then `python3 scripts/render_queue.py add <reel> --preview` instead of render.sh, set its status to «рендериться», and start `python3 scripts/render_queue.py run` in the background (a second `run` exits by itself, so it is safe to start it every time). Renders run one at a time in the order added; re-adding a reel that still waits replaces its job. Never call render.sh directly during a batch: two renders at once slow both down and can freeze the Mac.
- **Each finished render:** watch `~/reels/.queue/done.log` (Monitor on new lines). On `DONE <reel>`: frame check, 540p proxy, upload, `builds/<id>`, status «чернетка готова», `PushNotification` with the reel's name. On `FAIL`: read the end of the render output, fix, re-add. `render_queue.py status` shows what is rendering and what waits.
- Final, covers, deliver and CapCut go reel by reel exactly as for a single reel; set status «фінал» when delivered.

## When they say "build preview"

1. `ArtifactData get review/current` (save to a file). Missing is fine: it means "use the proposal".
2. `python3 scripts/review_sync.py import <reel> <review.json>` → `edl.json` + `edit.json`. Act on every `CHANGE REQUESTED`, `NOTE` and `REVISION` line it prints before rendering; `HOOK` / `CTA` lines are their approved text: use it word for word (it already went into the title / CTA card), don't ask again; for every `OVERLAY ... DOWNLOAD asset <id>` line, fetch their upload with `Artifact` `action: "read"`, `url` = the page, `path` = that asset id, `out_dir` = `<reel>/overlays` (it lands as `<id>.<ext>`; the card already points there); `BRAND CHANGE REQUESTED` only touches brand.json after they confirm.
3. `python3 scripts/snap_joins.py <reel>`, `REEL_PREVIEW=1 python3 scripts/cut.py <reel>`, then `python3 scripts/precheck.py <reel>` and fix everything it lists (JOIN, MISSING, CHECK) before the draft: `REEL_DRAFT=1 REEL_PREVIEW=1 bash scripts/render.sh <reel>` → `draft.mp4` (540p, fast). The full-quality final renders only after «Це фінал».
4. Grab frames at every graphic and the longest caption words; fix anything out of frame before sending.
5. `draft.mp4` (already 540p) → upload → `ArtifactData set builds/latest` {url, hash (from edit.json), at, cutDur}. The page compares that hash with the live decisions and marks the preview outdated when they change. Then `PushNotification` (tool search first) with the reel name: the preview is ready to watch.

## Final

After they approve the draft: if the brand resolution is 1080x1920 the approved draft's `final.mp4` is the final, so go straight to QA and deliver (no second render). Only a 4K brand renders again with `bash scripts/render.sh <reel> --final` (it re-cuts the 1080p preview master first). Then `python3 scripts/cover.py <reel>` → three covers with the approved hook; show `covers.jpg` and let them pick. CapCut follows SKILL.md step 8 (`"capcut": "ask"` = ask after delivering).
