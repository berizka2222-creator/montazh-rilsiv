# Split screen (розділення екрану навпіл)

2026-10-26: splits were used too rarely. Reference: instagram.com/reel/De4kuo5tJPL (a 73 s tutorial
«Весь монтаж зробив Claude»). Measured on its frames. This replaces the old «splits are rare, at most one» rule.

## How it looks

- **Exactly half.** The seam is at y = 960 of 1920. Top half: the graphic (a demo, a window, a scene). Bottom half: she keeps
  talking, her sound never stops.
- **Her framing in the lower half.** About 10% of the window (~100 px) between the seam and the top of her hair, hair to chin
  about a third of the window, eyes at about a quarter of the window, face centred. Her video is zoomed in when she was filmed wide
  (the reference zooms ~1.4x). Never ceiling and lamp over her, never the forehead cut off. `split_frame()` in build_reel.py
  does this from face.json; check the first split frame on the contact sheet anyway.
- **The top half's content sits low**, near the seam: title around y 350-400, the window or card below it ending ~30 px above
  the seam. Nothing under Instagram's top bar (y < 240). Light or brand panel, a soft shadow on the seam.
- **Hard cut in and out** on a phrase boundary, no sliding. The panel content animates in after the cut (0.1-0.3 s). Coming back
  to full frame: a cut, often with a quick punch-in on her (`punch`).
- **Long blocks.** One split lasts 6-16 s and its top changes with every step (2-4 motions back to back), while she goes on in
  the bottom. Split cards placed back to back (end of one = start of the next) render as one continuous split.
- **Her half stays light:** a step number like `[2]` beside the head, one-word captions beside the head or under the chin.
  Never a caption or graphic over the seam.

## When

- Step-by-step and «дивись, як це працює» moments: instructions, a tool or app in action, screen recordings, typing into a chat
  or terminal, a file being uploaded, before/after of a process, a list of actions she walks through.
- Not for the hook, emotion or a single punch word: those stay full frame (her) or a full takeover.
- Rhythm of the reference: her full frame → full takeover → her → **split** (steps 2-3, ~16 s) → her → full takeovers → her →
  **split** (~7 s) → full takeover → her CTA. So 1-3 split blocks per reel, alternated with her full frame and full takeovers.
- Two split blocks never touch through a short gap (< 2 s of full frame): merge them into one.

## In edit.json

- Template list: `{"type": "split", "start", "end", "title", "rows": [...]}`. Default panel 960, hard cut. `"enter": "slide"` =
  the old animated split, `"side": "left"` = left/right (rare).
- Any catalog motion: `{"type": "motion", "name": "...", "layout": "split"}`. The catalog's own band (low/top/chest) is
  ignored when the card says `"layout": "split"`. `"panel": 960` is the default, change only with a reason.

## Effects in the reference and what we have

| Moment in the reference | Ours |
|---|---|
| Stopwatch pill counting the whole reel (proof «за хвилину») | `rf-stopwatch` (on top of everything, splits too) |
| Round «1:00» timer badge popping next to her | `fx-countdown-flip`, `count-up` (partial) |
| Typewriter caption `// Давай я тобі розповім` with one bold word | `typewriter`, `streaming-text` |
| Emoji row + current word beside the head (karaoke) | `rf-emoji-caption` (caption style, `caption_vars.emojis`) |
| Step number `[1] [2] [3]` beside the head | `rf-step-tag` (follows her face inside a split) |
| Full pink takeover: list rows appear with icons, earlier rows dim | `line-swap`, `focus-swap`, list `drop` (partial: no dimming) |
| Dark neon progress ring 44→100% + segmented bar «МОНТУЄ CLAUDE» | `conic-progress-ring`, `mk-progress-stat` |
| Browser window: URL typed, page opens, cursor clicks «Копіювати» → «Скопійовано» | `browser-device-stage` + `oversized-cursor` / `press-ripple` (combine) |
| Split: Claude Code window, command typed, install log, spinner → «все встановлено» | `typed-prompt`, `terminal-simulator`, `success-check` |
| Split: file chip uploads with a progress line | `rf-file-upload` |
| Split: waveform with pauses, pauses close up («без вирізаних пауз») | `rf-pause-cut` |
| Neon dropdown, cursor picks «Opus 5.5», spinner → check | `cursor-context-menu` (replace) |
| White screen, typed text with `[опишемо]` and `/наприклад/` | `typewriter` |
| Small word trail over a big word: «субтитри / заголовок / ХУК» | `kinetic-type-swap` (partial) |
| Fan of cards with frames of her own reel | `fx-phone-fan`, `spring-stack-shuffle` |
| Phone with Instagram share sheet, «Копіювати посилання» → toast | `share-sheet-carousel` (full only) |
| Rounded thumbnail of her reel + pill «змонтовано в Claude» | `bubble` layout / `head-window` |
| 3D cloud of reel thumbnails flying around a 3D phone | `gallery-tunnel`, `fx-profile-wall`, `avatar-cloud` (partial) |
| Chat: picture dropped in, tag chips pop (шрифти, кольори, субтитри...) | `fx-check-pills` (partial) |
| Three checks pop one by one + «ДУЖЕ ПРОСТО» | `fx-checklist`, `success-check` |
| CTA: «пиши мені слово МОНТАЖ», dashed arrow, comment bar types the word | `fx-comment-box`, `hw-arrow` |
| Punch-in on her right after a takeover / split | `punch` in edit.json |

## Our own reference motions (`rf-*`, catalog group «Свої (з рілс-референсу)»)

They take the brand colours, the face position (mapped into the lower half during a split) and their own duration from the
reel, so the card needs only the words. Example of one split step:

```json
{"type": "motion", "name": "rf-file-upload", "layout": "split", "start": 21, "end": 25,
 "vars": {"headline": "Скидаємо сирий Reels", "file": "IMG_8899.MOV", "label": "сирий Reels"}},
{"type": "motion", "name": "rf-pause-cut", "layout": "split", "start": 25, "end": 29, "vars": {"badge": "−12 пауз"}},
{"type": "motion", "name": "rf-step-tag", "start": 21, "end": 29, "vars": {"step": "3"}},
{"type": "motion", "name": "rf-stopwatch", "start": 0, "end": 73}
```
