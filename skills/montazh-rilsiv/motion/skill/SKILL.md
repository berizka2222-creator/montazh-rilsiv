---
name: motion-brand
description: Motion design in the person's own brand on Remotion (project ~/motion, installed with the reel skill). Use for «моушн-ролик», «моушн дизайн», «анімований ролик без мене в кадрі», «зроби анімацію / анімовану графіку», «анімований елемент для рілса» (цифра, список, було → стало, чат, плашка з іменем, CTA), «анімація на сайт / лендинг», «персоналізоване відео». Also when the reel editor needs an element its HyperFrames catalog doesn't have. Not for cutting a talking-head reel itself: that is the reel skill (this one feeds it transparent overlays).
---

# Motion brand (Remotion)

A motion design system in code: the person's brand (their `brand.json` / `brand.md` from the reel skill) built once as
Remotion elements, then reused for three things:

| Job | Output | How |
|---|---|---|
| **Motion reel** (no camera, all graphics) | MP4 1080x1920 (or 4:5, 1:1) | scene list JSON → `MotionReel` → `scripts/render.sh` |
| **Element for a talking-head reel** | transparent WebM → reel overlay card | `scripts/render-overlay.sh` |
| **Motion on a website / landing** | `motion-assets/` folder + one `<div>` per animation | `scripts/build-embed.sh <site>` (references/player.md) |

Project: `~/motion` (Remotion 4; free for individuals and teams up to 3 people). The workspace is `~/reels` unless
`REELS_HOME` is set.
**Their brand, automatically:** `scripts/sync-brand.py` (every render script runs it first) reads `<REELS_HOME>/brand.json`:
colours → `src/lib/brand.generated.json` (roles: `lime` = main accent for labels, buttons, numbers; `pink` = second accent
for italic words and strike-through), font files from `<REELS_HOME>/fonts` → `public/fonts`, their own 3D / sticker
elements from `<REELS_HOME>/assets/chrome/*.png|webp` → `public/chrome` (the `chrome` prop takes the file name).
Change the brand in `brand.json`, never in the code. Remotion know-how (APIs, rendering, Player): the
`remotion-best-practices` skill if installed. This skill decides *what* and *in which look*.

## The rules (their brand wins over any skill default)

- Read `<REELS_HOME>/brand.md` first: its «Rules» section is a hard yes / no for every render.
- Colours and fonts only from the brand (they come in through `brand.ts`): never a default Inter / Roboto or a random palette.
- Headlines sentence case, 1-2 accent words per title written as `*слово*` (italic, second accent colour); `/` breaks lines.
- Eyebrows / labels / row numbers: mono, UPPERCASE, main accent. No bullets: 01 / 02 or `·`.
- Text is theirs. Hook, CTA, button text, numbers, chat messages, reviews: from them or their files, never invented.
  Numbers only real. Buttons say an action. No free-seat counts.
- Over their video (overlay): fully clear of the face (`place: "top"` above the head or `"chest"`) or the whole frame
  (`place: "center"`, a takeover). Never half over the face.
- Every render gets looked at: grab stills at the key frames (`npx remotion still <Id> out/x.png --props=... --frame=N`)
  before showing them anything.

## Element library

Short text everywhere: 2-6 words a line. All take `duration` (s), `format` ("9:16" | "4:5" | "1:1" | "16:9"),
`bg` ("brand" | "none" = transparent), `place` ("center" | "top" | "chest"), `chrome` ("" or the file name of one of
their own elements).

| key (scene type) | Composition | Moment | Props |
|---|---|---|---|
| `hook` | HookTitle | хук / ключова фраза | eyebrow, text, sub, size |
| `marker` | Marker | хук / ключова фраза | text with `*part*`, mode: highlight / circle / underline / strike |
| `counter` | Counter | цифра | value, from, decimals, prefix, suffix, label, seconds |
| `bars` | Bars | ріст / падіння | title, unit, bars: [{label, value, hi}] |
| `list` | ListReveal | список / кроки | eyebrow, title, rows, rowGap (frames), check |
| `beforeAfter` | BeforeAfter | до / після | beforeLabel, before, afterLabel, after |
| `chat` | Chat | повідомлення / чат | title, messages: [{from: them/me, text}], gap |
| `lowerThird` | LowerThird | ім'я / хто я | name, role, handle (default: brand.json name / handle), y |
| `cta` | CtaEnd | заклик (CTA) | eyebrow, title, button, note |

More to pull in (Remotion packages: light leaks, shapes, noise, transitions...): `references/library.md`.
A new element = a file in `src/elements/` + one line in `src/elements/index.ts` + one entry in `~/motion/library.json`
(moments, ua, text fields: that is what the reel skill's `motions.py ideas` suggests from).

## 1. Motion reel

1. Get the script from them: the lines, the hook, the CTA. A voice-over goes in `public/audio/` (music too); time the
   scenes to it (transcribe it with the reel skill's `scripts/transcribe.py`).
2. Write `props/<yyyy-mm-dd>-<name>.json`:
   ```json
   {"format": "9:16", "transition": "slide", "voice": "audio/voice.mp3", "music": "",
    "scenes": [
      {"type": "hook", "seconds": 3, "props": {"eyebrow": "тема", "text": "Їхній / *хук*"}},
      {"type": "counter", "seconds": 2.6, "props": {"value": 0, "suffix": "%", "label": "їхній підпис"}},
      {"type": "cta", "seconds": 3.4, "transition": "fade", "props": {"title": "Їхній *заклик*", "button": "Їхня кнопка"}}
    ]}
   ```
   Transitions: `slide` (default), `fade`, `wipe`, `cut`. Never three scenes of the same type in a row. 2.5-4 s a scene,
   the hook at least 3 s.
3. Check stills at the middle of every scene, fix, then `scripts/render.sh MotionReel props/<file>.json out/<name>.mp4`.
4. Deliver to `~/Movies/Reels` with a clear name. Offer a 4:5 version for the feed / ads when it fits.

`props/demo-reel.json` shows every element once (placeholder text): a quick look at the whole library in their brand.

## 2. Element for a talking-head reel (with the reel skill)

1. Take the exact phrase and its times from the cut reel (`master_transcript.json`), their words as the text.
2. `scripts/render-overlay.sh <Composition> '<props json>' <REELS_HOME>/<reel>/overlays/brand-<Composition>-<slug>.webm`
   with `"duration"` = the phrase length and `"place"` from `face.json` (`top` when there's room above the head, else `chest`).
3. Card in edit.json: `{"type": "overlay", "brand": "<Composition>", "src": "overlays/brand-<Composition>-<slug>.webm", "start": .., "end": ..}`.
4. Check the draft frame at that moment like any other card.

## 3. Website / landing

`references/player.md`. In short: `scripts/build-embed.sh <site folder>` copies `motion-assets/` into the site, then
`<div data-motion="CtaEnd" data-props='{...}' data-loop data-autoplay></div>` + one `<script>`. For a plain looping clip,
a rendered MP4 / WebM in a `<video>` tag is lighter: offer that first.

## Studio

`cd ~/motion && npm run dev` opens Remotion Studio: every element with a props form, for a quick look.
