---
name: montazh-rilsiv
description: Монтаж рілсів з говорячою головою у власному стилі людини (українська мова) - нарізка, прибирання «ем» і пауз, субтитри, хук-заголовок, графіка, власний моушн на фразах, сторінка перевірки перед рендером. ТРИГЕРИ - «змонтуй рілс», «зроби з цього рілс», «монтаж рілса», «обріж відео», «додай субтитри», «виріж паузи й ем», «налаштуй мій бренд для рілсів», а також будь-яке сире відео-говоряча голова, яке людина дає для монтажу. Based on getgitgirl's claude-reel-editor (MIT).
---

# Reel editor

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
6. Ukrainian speech: `npx hyperframes models install parakeet` (~640 MB, once). If huggingface.co is blocked, say so plainly.
7. `mkdir -p ~/reels/fonts ~/reels/assets` (the reels workspace).
8. `bash scripts/doctor.sh` and tell them in one sentence that everything is ready and that next time they open the Code tab with the folder `reels` and write «змонтуй рілс».
Explain each step in one short Ukrainian sentence: the person is a beginner.

## Check the tools (once per machine)

`bash scripts/doctor.sh` - checks ffmpeg, Node, the HyperFrames skills and (if the brand file says CapCut) the CapCut connector. Fix anything it flags before editing. Install steps are in the repo README.

## The edit, in order

Each reel gets its own folder: `~/reels/<yyyy-mm-dd>-<short-name>/`. Copy the raw clip in (never edit the original).

1. **Transcribe** - `python3 scripts/transcribe.py <clip> transcript.json`. Uses ElevenLabs Scribe when `ELEVENLABS_API_KEY` is in `~/.config/reels/.env` (tight word timing; captions land on the word), else local Whisper (free, timing can drift ~0.3 s).
2. **Clean the voice** - `bash scripts/clean_audio.sh <clip> voice.wav` (add `--denoise` if there is background noise). Targets -14 LUFS, the level Instagram and TikTok expect.
3. **Review (their call)** - propose: lines to cut (repeats, false starts, rambles), fillers to drop, CTA moved to the end, target under 60 s, and the graphics plan. **Wait for their yes before cutting.** This is the step people care most about.
   **Look at the start and end before proposing cuts:** grab a frame every 0.5 s for the first and last 4 s. Cut any camera setup (pointing at the floor/garden, flipping the camera, reaching for the phone) even if words are spoken over it. Start on the first frame where they're settled in shot, and on a word that works as an opener.
   - **Main path: the Reel Review page.** First check that the `Artifact` and `ArtifactData` tools exist in this session (load them through tool search if they're deferred). If they do, follow `references/review.md`: they tap words to cut, watch the live rough cut, check graphics, captions, sound and colour, then say "build preview". Its import step writes `edl.json` + `edit.json`, so skip to step 4's cut and step 5.4's render.
   - **Fallback: review in chat** when those tools aren't there (older Claude Code, other apps). Show the transcript as numbered lines (format in `references/rough-cut.md`), then the card list in step 5.
4. **Tighten, then cut + speed** - write `edl.json` from the approved lines, then `python3 scripts/tighten.py <folder>`: it removes fillers and shortens pauses inside the kept lines, as hard as the brand's `"pacing"` says (`natural` default, `tight`, `fast`; presets in `scripts/pacing.py`). They never approve these one by one. Then `python3 scripts/cut.py <folder>`. Speed comes from the same preset unless `brand.json` sets `"speed"`. Listen-check: re-transcribe `master.mp4` and confirm no clipped words at the joins.
5. **Graphics + captions: fill the template, don't design.** You are the editor here, not the designer - the look is already built from the brand file.
   1. `python3 scripts/transcribe.py master.mp4 master_transcript.json`
   2. `python3 scripts/auto_edit.py <folder>` → drafts `edit.json` (captions in their caption mode, punch-ins)
   3. Edit `edit.json` yourself, in one pass: set `"accent": true` on the one key word per sentence, and add cards at the density `brand.json` `"graphics"` asks for: `minimal` about one every 8-12 s, `balanced` (default) every 4-6 s, `busy` every 2-4 s. A line with nothing to show gets no card; don't chart every number or screenshot every tool just to fill the gap. Card types and fields are in the header of `scripts/build_reel.py`; HyperFrames catalog motions (carousels, charts, counters, notifications, cursor, follow cards) are in `references/motions.md`. Every card must show what that exact line says.
      - **Hook title: always ASK the person for the exact hook text before adding the title card. Never write or pick it yourself, not even from the transcript.** You may offer 2-3 options in their words if they ask for ideas, but the card goes in only with the text they approved. Layout: max ~10 characters per line, 2-3 lines (`"still / uploading / screenshots?"`), so it renders big. It's the only text with an outline.
      - **Carousel:** if `brand.json` has `"require_carousel": true`, every reel gets one (`motion` card, a `carousel-*` name, `images` from screenshots/their assets). If no line suits one, ask them; if they say no, set `"no_carousel_ok": true`.
      - **Screenshots:** for a tool or site they name that the line is about, run `bash scripts/screenshot.sh <url> shots/<name>.png`. Exit code 2 means the site blocked it: try the tool's marketing page, or ask them for a screenshot. Never use a blank one.
      - Mix the kinds: website shots, a colour block, a list card (`"glass": true` for liquid glass), a sticker from their assets, a `follow` card for the big moment, a counter or chart when they say a number.
   4. `REEL_PREVIEW=1 bash scripts/render.sh <folder>` for the draft (1080p, low priority), then `bash scripts/render.sh <folder> --final` once they approve it (the resolution in `brand.json`; add `--capcut` on the CapCut route) → `final.mp4` + stage timings.
   Do **not** hand-write composition HTML or use other HyperFrames workflows here: they are slower and ignore the brand template. Exception: own motion design on a phrase or sentence (see "Own motion design on phrases" below) goes in as a `custom` card.
6. **QA** - `python3 scripts/qa.py <folder>` (loudness, size, length, missing words). Then grab a frame at every card and look: text inside the frame, readable over the background, on brand. Fix `edit.json` and re-run render.sh until it passes.
7. **Deliver** - `bash scripts/deliver.sh <final.mp4> "<clear name>"` → upload-ready MP4 in their delivery folder.
8. **CapCut (only if `brand.json` has `"capcut": true`)** - build the editable CapCut draft and give them the link. `references/capcut.md`.

Tell them what changed, and what to check by ear (cuts, names, brand words spelled right).

## Own motion design on phrases
Besides the template cards, the person can ask for their own motion on a phrase or sentence: over the video, or a full-screen takeover that covers them for a few seconds. Offer it in the graphics plan where a line deserves it; they decide.
- Effects, rules and timings: `references/motion-effects.md`. Colours and fonts come ONLY from `~/reels/brand.json` / `brand.md`.
- Build each one as a HyperFrames sub-composition in `<reel>/motion/<name>.html` (1080x1920 unless boxed; own `data-composition-id`, `data-width`, `data-height`; GSAP timeline registered in `window.__timelines["<id>"]`, seek-safe; copy the brand font files and `engine/gsap.min.js` next to it). Use the `hyperframes` skill for authoring.
- Time it on `master_transcript.json` (the cut reel), then add to `edit.json`: `{"type": "custom", "src": "motion/<name>.html", "start": .., "end": .., "layer": "front", "full": true|false, "sfx": "whoosh"}`. Full-screen takeovers set `"full": true` (captions step aside).
- Text behind the head / card behind the person needs a cutout (`npx hyperframes remove-background`): say it is slower before doing it.
- Before the draft, grab a frame at the peak of every custom motion and check it.

## Language
`brand.json` "language" (e.g. `"uk"`) drives transcription, filler words and QA. Talk to the person in their language. The Reel Review page UI is in Ukrainian: write every `kind` and `what` in proposal.json in Ukrainian too, and treat «збери чернетку» as "build preview" and «фінал» as "final".
Ukrainian: transcription uses Parakeet if installed, else Whisper large-v3; fillers are hesitation sounds only (е, ем, ммм, хм; "ну" only on tight/fast pacing).

## Their brand rules win

If the brand file and your taste disagree, the brand file wins. If they correct something during an edit ("no, never outline captions"), add it to `brand.md` under "Rules" straight away so the next edit gets it right.

## Common mistakes

| Mistake | Instead |
|---|---|
| Editing before a brand file exists | Run the setup interview |
| Cutting on Whisper word times blindly | Check the joins; nudge cuts into the quiet gap between words |
| Graphics that decorate instead of illustrate | Each card shows what this exact line says |
| Captions in a font the brand file bans | Re-read brand.md "Rules" before step 5 |
| Saying CapCut works everywhere | It doesn't (see capcut.md). The MP4 route always works |
| Fixing QA failures by lowering the bar | Fix the edit, re-run QA |
