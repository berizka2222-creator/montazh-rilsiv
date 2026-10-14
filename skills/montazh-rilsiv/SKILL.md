---
name: montazh-rilsiv
description: Скіл від @inna_berezova (Інна Березова). Монтаж рілсів з говорячою головою у власному стилі людини (українська мова) - нарізка, прибирання «ем» і пауз, субтитри, хук-заголовок, графіка, власний моушн на фразах, сторінка перевірки перед рендером. ТРИГЕРИ - «змонтуй рілс», «зроби з цього рілс», «монтаж рілса», «обріж відео», «додай субтитри», «виріж паузи й ем», «налаштуй мій бренд для рілсів», а також будь-яке сире відео-говоряча голова, яке людина дає для монтажу. Based on getgitgirl's claude-reel-editor (MIT).
---

# Reel editor

*Монтаж рілсів від [@inna_berezova](https://instagram.com/inna_berezova) (Інна Березова).*

Turns a raw talking-head clip into a finished, on-brand vertical reel. Every brand choice (colours, fonts, caption style, sounds, CTA) comes from the person's **brand file**, never from defaults baked into this skill. You do the editing; they only make the calls that are theirs.

## Before anything else: is there a brand file?

The workspace is `~/reels/` unless `REELS_HOME` is set.

- **No `~/reels/brand.md`** → run the setup interview: read `references/setup-uk.md` first (design system + reference reels are required before the first edit), then `references/setup-interview.md`. Do not edit a clip without a brand file, even if they say "just use whatever". The interview takes 5 minutes and it is the whole point of this skill.
- **Brand file exists** → read `brand.md` and `brand.json` in full, then continue.

## First run on a new computer (do it yourself, never send the person to a terminal)
The person works in the Claude desktop app, Code tab. Never ask them to open the Terminal. In this order, skipping what is already there:
1. `python3` missing → run `xcode-select --install`: macOS opens a normal install window; tell them to click «Встановити» and wait, then continue.
2. `node` missing → if Homebrew exists, `brew install node`; otherwise download the latest LTS macOS installer (.pkg) from nodejs.org into ~/Downloads and `open` it: the person clicks through the installer window and types their Mac password there. Then re-check `node -v` (use the full path `/usr/local/bin/node` if PATH is stale).
3. `ffmpeg` missing → if Homebrew exists, `brew install ffmpeg`; otherwise download static macOS builds of `ffmpeg` and `ffprobe` into `~/.local/bin`, `chmod +x`, clear quarantine (`xattr -d com.apple.quarantine`), and add `export PATH="$HOME/.local/bin:$PATH"` to `~/.zprofile`.
4. `npx skills add heygen-com/hyperframes -y` if the HyperFrames skills are missing.
5. `bash scripts/setup_engine.sh` (animation library + sound effects).
6. Speech recognition: connect ElevenLabs Scribe (section «Connecting ElevenLabs Scribe» below). It is required: there is no local recogniser, so nothing large is downloaded. Walk them through creating the key in one short step at a time.
7. `mkdir -p ~/reels/fonts ~/reels/assets` (the reels workspace).
8. `bash scripts/doctor.sh` and tell them in one sentence that everything is ready and that next time they open the Code tab with the folder `reels` and write «змонтуй рілс».
Explain each step in one short Ukrainian sentence: the person is a beginner.

## Check the tools (once per machine)

`bash scripts/doctor.sh` - checks ffmpeg, Node, the HyperFrames skills and (if the brand file says CapCut) the CapCut connector. Fix anything it flags before editing. Install steps are in the repo README.

## The edit, in order

Each reel gets its own folder: `~/reels/<yyyy-mm-dd>-<short-name>/`. Copy the raw clip in (never edit the original).

1. **Transcribe** - `python3 scripts/transcribe.py <clip> transcript.json`. Uses ElevenLabs Scribe with `ELEVENLABS_API_KEY` from `~/.config/reels/.env` (tight word timing; it writes "ем"/"um" as words, which is how fillers are found). There is no local fallback: exit code 2 = no key (connect it), 1 = key, balance or network problem (say which, then retry).
2. **Clean the voice** - `bash scripts/clean_audio.sh <clip> voice.wav` (add `--denoise` if there is background noise). Targets -14 LUFS, the level Instagram and TikTok expect.
**Face zone:** `python3 scripts/face_box.py <folder>` (macOS Vision, ~30 s) before the review export, so graphics and captions keep off the face (see «Face, captions and «За мною»» in references/review.md).
3. **Review (their call)** - propose: lines to cut (repeats, false starts, rambles), fillers to drop, CTA moved to the end, target under 60 s, and the graphics plan. **Wait for their yes before cutting.** This is the step people care most about.
   **Look at the start and end before proposing cuts:** grab a frame every 0.5 s for the first and last 4 s. Cut any camera setup (pointing at the floor/garden, flipping the camera, reaching for the phone) even if words are spoken over it. Start on the first frame where they're settled in shot, and on a word that works as an opener.
   - **Main path: the Reel Review page.** ALWAYS run a tool search for `Artifact` and `ArtifactData` first (they are usually deferred and only appear after the search). Never decide they are missing without searching. If they do, follow `references/review.md`: they tap words to cut, watch the live rough cut, check graphics, captions, sound and colour, then say "build preview". Its import step writes `edl.json` + `edit.json`, so skip to step 4's cut and step 5.4's render.
   - **Several clips at once (3-5):** one page with a reel picker and a render queue (`scripts/render_queue.py`): prepare reel 1 first and send the link, prepare the rest while they review, renders queue one at a time. See «Several reels at once» in `references/review.md`.
   - **Fallback: review in chat** only when the search found no such tools. Say so in one line first: «Сторінку перевірки відкрити не можу: в цій сесії немає інструментів Artifact/ArtifactData, тому перевіряємо в чаті». Show the transcript as numbered lines (format in `references/rough-cut.md`), then the card list in step 5.
4. **Tighten, then cut + speed** - write `edl.json` from the approved lines, then `python3 scripts/tighten.py <folder>`: it removes fillers and shortens pauses inside the kept lines, as hard as the brand's `"pacing"` says (`natural` default, `tight`, `fast`; presets in `scripts/pacing.py`). They never approve these one by one. Then `python3 scripts/snap_joins.py <folder>` (moves every join into the nearest quiet gap: transcript times are never exact, and a cut on them clips words), then `python3 scripts/cut.py <folder>`. Speed comes from the same preset unless `brand.json` sets `"speed"`.
5. **Graphics + captions: fill the template, don't design.** You are the editor here, not the designer - the look is already built from the brand file.
   1. `python3 scripts/transcribe.py master.mp4 master_transcript.json`
   2. `python3 scripts/auto_edit.py <folder>` → drafts `edit.json` (captions in their caption mode, punch-ins)
   3. Edit `edit.json` yourself, in one pass: set `"accent": true` on the one key word per sentence, and add cards at the density `brand.json` `"graphics"` asks for: `minimal` about one every 8-12 s, `balanced` (default) every 4-6 s, `busy` every 2-4 s. A line with nothing to show gets no card; don't chart every number or screenshot every tool just to fill the gap. Card types and fields are in the header of `scripts/build_reel.py`; HyperFrames catalog motions (carousels, charts, counters, notifications, cursor, follow cards) are in `references/motions.md`. Every card must show what that exact line says.
      - **Hook title: always ASK the person for the exact hook text before adding the title card. Never write or pick it yourself, not even from the transcript.** Text they typed in the hook / CTA fields on the review page («Графіка») IS their approved text: `review_sync.py import` prints it as `HOOK (their text, use as is)` / `CTA (their text)`; use it word for word and don't ask again. The hook stays on screen at least 3.5 s. You may offer 2-3 options in their words if they ask for ideas, but the card goes in only with the text they approved. Layout: max ~10 characters per line, 2-3 lines (`"still / uploading / screenshots?"`), so it renders big. It's the only text with an outline.
      - **Carousel:** if `brand.json` has `"require_carousel": true`, every reel gets one (`motion` card, a `carousel-*` name, `images` from screenshots/their assets). If no line suits one, ask them; if they say no, set `"no_carousel_ok": true`.
      - **Screenshots:** for a tool or site they name that the line is about, run `bash scripts/screenshot.sh <url> shots/<name>.png`. Exit code 2 means the site blocked it: try the tool's marketing page, or ask them for a screenshot. Never use a blank one.
      - **Their own photos/videos come first.** They place them on the review page's «Накладення» tab (or drop files in the reel folder and say where) before you plan anything else; then your cards and motion go around them, never in the same moment and area (`review_sync.py overlays` lists them and flags CONFLICTs; two rounds, see `references/review.md`). Each becomes an `overlay` card (sizes small-r/small-l/big/full or a dragged `box`, effects soft/slide/polaroid/glass/zoom; header of `scripts/build_reel.py`).
      - **«За мною» (behind the person):** `"behind": true` on any card (text, sticker, photo, motion) puts it between the background and the person. The person is cut out locally with `npx hyperframes remove-background` ONLY for the windows of those cards (~13 s of work per second of video, cached in `<reel>/cutouts`, so re-renders don't redo it). On the page it's the «За мною» checkbox. Use it where it reads better, not on every card.
      - **`bigtext` card:** huge words in the head font (`{"type": "bigtext", "text": "big / words", "y": 330}`, "/" breaks lines), usually with `"behind": true` so they sit behind the head. Fields in the header of `scripts/build_reel.py`. Transparent PNGs (their elements) go in without a frame.
      - Mix the kinds: website shots, a colour block, a list card (`"glass": true` for liquid glass), a sticker from their assets, a `follow` card for the big moment, a counter or chart when they say a number.
   4. **Before the first render, always:** `python3 scripts/precheck.py <folder>`. It hears `master.mp4` again, re-times captions/cards/punch-ins to it, and lists every JOIN (read each: no clipped, doubled or stray word), MISSING speech with no caption, and CHECK words the caption has wrong (misheard words: fix the spelling to what they said). Fix all of it in `edit.json` (a bad join: edl + snap_joins + cut, then precheck again) so the draft they see is already right. A render takes ~6 min: never render to find these.
   5. Drafts: `REEL_DRAFT=1 REEL_PREVIEW=1 bash scripts/render.sh <folder>` → `draft.mp4` at 540x960 (a quarter of the pixels, from a 540p copy of the master; final.mp4 untouched). Fast, for review only; every notes round renders a new draft. **The final renders once**, after they approve: `REEL_PREVIEW=1 bash scripts/render.sh <folder>` (1080x1920, or `--final` for a 4K brand) → `final.mp4`, then QA and deliver. On an 8 GB Mac keep `REEL_WORKERS=1` for the final: two Chrome workers run out of memory, time out and redo the frames.
   6. **When a render finishes, send a phone notification** (`PushNotification`; run a tool search for it first, it is usually deferred): reel name + what to check. `render.sh` only shows a Mac notification, and they may be away from the screen.
   Do **not** hand-write composition HTML or use other HyperFrames workflows here: they are slower and ignore the brand template. Exception: own motion design on a phrase or sentence (see "Own motion design on phrases" below) goes in as a `custom` card.
6. **QA** - `python3 scripts/qa.py <folder>` (loudness, size, length, missing words). Then grab a frame at every card and look: text inside the frame, readable over the background, on brand. Fix `edit.json` and re-run render.sh until it passes.
7. **Deliver** - `bash scripts/deliver.sh <final.mp4> "<clear name>"` → upload-ready MP4 in their delivery folder.
   **Covers** (skip when brand.json `"covers": false`): then `python3 scripts/cover.py <reel> ["hook / text"]` → `cover_1.jpg`..`cover_3.jpg` + `covers.jpg` side by side: the sharpest camera frames from three parts of the reel with the approved hook in the brand's head font, text off the face and inside the 4:5 area the profile grid shows. Show `covers.jpg` and let them pick. The hook text is theirs (argument or the title card); never invent it.
8. **CapCut** - `brand.json` `"capcut"`: `true` = always build the CapCut draft; `"ask"` = after delivering the MP4, ask once «Відправити ще в CapCut?» and build it only on a yes; `false` = never. Building it means one extra render with `--capcut` (no captions/sfx baked in), then `references/capcut.md`.

Tell them what changed, and what to check by ear (cuts, names, brand words spelled right).

## Own motion design on phrases
Besides the template cards, the person can ask for their own motion on a phrase or sentence: over the video, or a full-screen takeover that covers them for a few seconds. Offer it in the graphics plan where a line deserves it; they decide.
- Effects, rules and timings: `references/motion-effects.md`. Colours and fonts come ONLY from `~/reels/brand.json` / `brand.md`.
- Build each one as a HyperFrames sub-composition in `<reel>/motion/<name>.html` (1080x1920 unless boxed; own `data-composition-id`, `data-width`, `data-height`; GSAP timeline registered in `window.__timelines["<id>"]`, seek-safe; copy the brand font files and `engine/gsap.min.js` next to it). Use the `hyperframes` skill for authoring.
- Time it on `master_transcript.json` (the cut reel), then add to `edit.json`: `{"type": "custom", "src": "motion/<name>.html", "start": .., "end": .., "layer": "front", "full": true|false, "sfx": "whoosh"}`. Full-screen takeovers set `"full": true` (captions step aside).
- Text behind the head / card behind the person: set `"behind": true` on the card (see «За мною» in step 5.3); the cutout runs only on those windows and is cached. Say it adds a few minutes before the first render with it.
- Before the draft, grab a frame at the peak of every custom motion and check it.

## Connecting ElevenLabs Scribe (required, once)
Scribe gives exact word timing and hears "е/ем"; under 2 cents a reel ($0.22 per hour of audio, ElevenAPI tab → Add credits; keep Auto Top Up off).
1. They create a key at elevenlabs.io → Developers → API Keys → Create: Restrict Key on, only **Speech to Text = Access**, everything else No Access. The real key starts with `sk_` and is shown once (the key ID is not the key).
2. Never ask them to paste it in chat. Open a hidden-input dialog on their Mac and write it straight to the env file, printing only its length:
   `K="$(osascript -e 'text returned of (display dialog "Встав API-ключ ElevenLabs (починається з sk_)" default answer "" with hidden answer buttons {"Скасувати","OK"} default button "OK" giving up after 600)')"`, then check it starts with `sk_`, replace the `ELEVENLABS_API_KEY=` line in `~/.config/reels/.env`, `chmod 600`.
3. Test it on 20 s of audio with `scripts/transcribe.py` (it should say "transcribed with ElevenLabs"). A bad key stops transcription with a clear message: fix the key or the balance, never work around it.

## Language
`brand.json` "language" (e.g. `"uk"`) drives transcription, filler words and QA. Talk to the person in their language. The Reel Review page UI is in Ukrainian: write every `kind` and `what` in proposal.json in Ukrainian too, and treat «збери чернетку» as "build preview" and «фінал» as "final".
Transcription is ElevenLabs Scribe for every language; fillers are hesitation sounds only (е, ем, ммм, хм; "ну" only on tight/fast pacing).

## Their brand rules win

If the brand file and your taste disagree, the brand file wins. If they correct something during an edit ("no, never outline captions"), add it to `brand.md` under "Rules" straight away so the next edit gets it right.

## Common mistakes

| Mistake | Instead |
|---|---|
| Editing before a brand file exists | Run the setup interview |
| Cutting on transcript word times blindly | `snap_joins.py` before `cut.py`, then read the JOIN lines from `precheck.py` |
| Finding wrong words or late captions on the draft or final | `precheck.py` before the first render; one draft + one final is the target |
| Graphics that decorate instead of illustrate | Each card shows what this exact line says |
| Captions in a font the brand file bans | Re-read brand.md "Rules" before step 5 |
| Saying CapCut works everywhere | It doesn't (see capcut.md). The MP4 route always works |
| Fixing QA failures by lowering the bar | Fix the edit, re-run QA |
