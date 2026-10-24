# Motions (HyperFrames catalog, tested, cached in engine/hf)

86 catalog motions are installed and tested on a real reel with Ukrainian text, in the brand's colours and fonts. The list,
with what each one is for, its moment and its tested placement, is `references/motion_catalog.json`. Read it through
`scripts/motions.py`, not by memory:

- `python3 scripts/motions.py menu` - every ready motion by moment («цифра», «список / кроки», «до / після», «питання / ШІ»,
  «повідомлення / чат», «відгук / доказ», «проблема / тиск», «ім'я / хто я», «заклик (CTA)», «картинки / приклади»,
  «успіх / готово», «перехід», «хук / ключова фраза»). Motions the last 3 reels used are marked.
- `python3 scripts/motions.py ideas <reel>` - for each phrase of the cut reel, 1-3 motions that fit it, freshest first
  (not in this reel yet, not in the last reels). Use it when planning the graphics, before writing proposal.json.
- `python3 scripts/motions.py log <reel>` - after delivering, so the next reels reach for other ones.

## How many and how varied (the rule)

- Every reel uses catalog motions, not only the template cards: `minimal` 2+, `balanced` 4+, `busy` / `inserts` 6+.
- Never the same motion twice in one reel. Prefer ones the last 3 reels didn't use (`menu` / `ideas` show them).
- Mix moments: a reel with a number, a list and a CTA gets a number motion, a list motion and a CTA motion, not three text
  effects. The template cards (list, split, push, steps, camera) still go in alongside.
- Scenes first: a reel of plain text effects looks basic. `ideas` marks every motion `[складне]` (a scene: phone, chat,
  notification, chart, carousel, lower third, hand-drawn picture, head layout, transition) or `[просте]` (one word, number or
  phrase animating over the video, `motions.py` `is_simple`). At least two thirds of a reel's motions are `[складне]`, `[просте]`
  at most a third and never two in a row. Add 1-2 catalog transitions (`use: transition`) where the topic changes.
- `split`, `push` and `steps` are rare: at most one of them per reel unless the person asked, none when the previous reel had one.
- A motion still has to show what that exact line says. «ideas» suggests, it doesn't decide.

## Vertical frame and Ukrainian text (checked 2026-10-21 on all 86, big-face framing)

- A catalog motion never moves or crops the person to make room: it plays over the video in a free area (chest, low third,
  above the head). Split and full-screen layouts only when the person picked them.
- Keep every text field short: 2-4 words, about 18 characters a line. Ukrainian words are longer than the English defaults and
  one-line effects clip or run off the frame past that.
- Statuses: `ready` / `replace` = checked in the frame, suggested by `menu` / `ideas`; `full_only` = only as a whole-frame takeover
  (2-3 s), suggested marked «на весь кадр», at most one per phrase and below the overlays; `manual` = works but small or niche, only
  when the person asks (menu lists it at the end); `candidate` = not checked in the frame yet, never suggested; `skip` = don't use.
  Elements from an own Remotion library (~/motion, `brand:<Element>`) are suggested next to the catalog like `ready` ones.
  `hyperframes snapshot` shows transparent WebM overlays as black: check them with a short real render (`REEL_DRAFT=1 render.sh`).

## The card

```json
{"type": "motion", "name": "conic-progress-ring", "start": 12.4, "end": 15.0, "vars": {"value": 87, "label": "окупність"}}
```

- `vars`: their words. The catalog's `text` field names the fields; the motion file's `data-composition-variables` header
  lists every one with its default. Numbers exactly as said.
- **Placement rule: a motion is either fully clear of the face or it replaces the frame. Never a panel
  half over the person.** Every catalog entry has its tested `layout`, applied automatically; change it on the card if needed:
  - `front`: transparent, light text on the video, in a band above the head (`place: "top"`) or on the chest (`"chest"`);
  - `behind`: like front, cut out behind the person (text behind the head);
  - `bubble`: a rounded brand window in that band, `"shape": "circle"` for a circle;
  - `split`: the screen divides, the motion on a brand panel at the top, the person slides into the lower part (`"panel": 820` = its height);
  - `full`: the whole frame is the motion on the brand colour for its seconds (phones, CTA end screens).
  - `low`: transparent, over the video from the chin down, text inks made light (most text effects);
  - `dim`: the video stays as a darkened background (`"dim": 0.82` = how dark), the effect on top over the whole frame;
    captions step aside. For effects that can't keep off the face: charts, carousels and galleries with their photos,
    phone chats and notes, maps, before/after, device mocks. Status `full_only`, marked «на весь кадр».
- Image slots (carousels, galleries, collage / pile / picture heads, device and placeholder grids). Claude picks one of these on
  its own only when it has real pictures that show THIS line, in this order:
  1. their own: the overlays and «Мої файли» they put on the page, `~/reels/assets/elements`;
  2. screenshots of a tool, site or account the line names (`scripts/screenshot.sh`);
  3. stills from their own reel at the moments the line talks about (`ffmpeg -ss <t> -i master.mp4 -frames:v 1`).
  Never stock photos or invented pictures in their slots, never an empty slot. In proposal.json say in `what` which pictures went
  in («3 кадри з твого відео»), so on the page they can swap them for their own. No real pictures for a line = pick a scene
  without image slots.
- Follow cards (`instagram-follow`, `tiktok-follow`, `yt-lower-third`, `x-post`) are suggested. Name and handle come from
  brand.json `name` / `handle` (stage 1 files already give them); the person can change them for one reel (card `replace`,
  e.g. `{"HeyGen": "Інна"}`) or for good (brand.json). The buttons stay in English, as in the real apps. The photo is
  brand.json `"avatar"`: the first time a follow card is planned and there is none, ask «Дай фото для картки підписки
  (як на аватарці)», save it to `<REELS_HOME>/assets/avatar.jpg` and set `"avatar": "avatar.jpg"`. Never crop it from the
  reel or leave the example logo: until the photo comes, the slot shows their initial on the brand colour. A follower count
  shows only if `replace` gives a real one.
- Effects that work but are never suggested on their own (`manual`: maps, shader transitions, caption styles, 3D scenes) are
  listed on the review page under «Ефекти» → «Тільки вручну»; the person picks one for a second there.
- The tested placement comes from the catalog automatically (layout, place, tone, ink, css); set them on the card only to move it.
  `box: [x, y, w, h]` on the 1080x1920 frame; `scale` shows a 1920-wide overlay bigger than the frame (lower thirds, light
  leaks: x may go negative).
- `tone`: `dark` (default: the brand's deep green panel, white text, pink accents), `light` (white card, dark text) or
  `clear` (no panel, light text on the video). `ink: "light" | "pop" | "#hex"` forces the text colour of text-only motions.
- `replace` (status `replace` motions: lower thirds, the IG follow card...): `{"<exact English text>": "their text"}`. The
  catalog lists the strings; build_reel warns when one isn't found.
- Fonts: every catalog motion is drawn in the brand fonts (body weight for regular text, head for bold), whatever the motion
  ships with. `"keep_fonts": true` keeps its own (rarely: a terminal's monospace).
- `full` and `split` motions take over the frame for their seconds: keep them 2-4 s, at most two `full` per reel.
- **Shader transitions on a cut** (`layout: "transition"`, moment «перехід»). Ready: cross-warp-morph, sdf-iris, swirl-vortex,
  ripple-waves, light-leak, glitch, whip-pan, cinematic-zoom, flash-through-white, chromatic-radial-split, thermal-distortion.
  Manual: domain-warp-dissolve (neon pink/cyan edge baked into the shader), gravitational-lens (a black hole over the face),
  ridged-burn (fire edge). Card: `{"type": "motion", "name": "sdf-iris", "start": <the join>}`; no `end`.
  build_reel snaps `start` to the nearest join of edl.json (within 1.5 s; `"join": 24.92` to name it exactly), takes the frame of
  master.mp4 at join-0.19 s and at join+0.19 s, embeds them in the shader as its two scenes and plays the warp over those ~0.38 s
  with a snappy cubic ease (`"half"` changes it, default 0.19). The shader starts on the live picture and lands on the live
  picture, so neither side jumps. Captions stay on top; the whoosh is quiet (whoosh_soft at -24 dB, under the voice).
  **They are loud effects: at most 2 per reel, only where the topic changes (a new thought or section), never on neighbouring
  joins, at least 12 s apart.** build_reel warns (`variety:`) when a reel has more or they sit closer. Check them with a short draft render (`REEL_DRAFT=1 render.sh`),
  not `hyperframes snapshot`.
- Carousels take `"images": [..]`, every slot is filled for you.

## Подачі голови (head layouts, `scripts/heads.py`)

The person's own video becomes the graphic: for one phrase the frame shrinks into a shape on a brand background and their
key words, photos or a picture gather around it, then the frame comes back. It is the look of reels that «rearrange the
talking head» on every phrase. Catalog entries `head-<look>` (use `head`, group «Подачі голови» in the effects menu, №299-309).

```json
{"type": "head", "look": "circle", "start": 4.2, "end": 8.1, "words": ["гроші", "сертифікат", "без клієнтів"]}
```
(`{"type": "motion", "name": "head-circle", "words": [...]}` works the same: that is what a pick from the menu becomes.)

| look | № | what | words | photos | bg |
|---|---|---|---|---|---|
| `window` | 299 | rounded window on the light colour, words stacked in head / accent (on a pop box) / body font | 1-3 | - | light |
| `circle` | 300 | circle with a dark ring on the pop colour with dots, words above, the last one in a dark pill | 1-3 | - | pop |
| `cloud` | 301 | cloud-shaped window, words in [brackets] gather around it | 2-4 | - | soft |
| `soft` | 302 | window with blurred edges on the dark colour; the shortest word (a number: «20%») goes huge | 1-3 | - | main |
| `polaroid` | 303 | tilted polaroid, a label above, words written on its frame; the background changes on each word | label + 1-3 | 1-3 optional | duo |
| `bigword` | 304 | one huge blurred word over a small window, it snaps into focus when said | 1 (`word`) | - | pop |
| `top` | 305 | the person in the top half, words in [brackets] drop onto the light bottom | 2-4 | - | light |
| `collage` | 306 | numbered photos (1)-(5), the person is (4), words beside | 1-2 | 2-4 required | light |
| `pile` | 307 | black-and-white photos fly into a pile, the person on top in a white frame, words in a pop plate | 1-2 | 3-6 required | light |
| `around` | 308 | full frame, words in [brackets] appear around the head, the last in a dark pill | 2-3 | - | none |
| `picture` | 309 | a picture above, the person below (soft edges), a pill caption changes word by word | 1-3 | 1 required | light |

- `words`: THEIR words from that very phrase, short (one word or two). Each appears the moment they say it: heads.py finds it
  in `master_transcript.json` by its first letters (so «знання» finds «знаннями»); `{"text", "t"}` forces a time.
  More words than the look holds are dropped with a printed line.
- `bg`: `main` / `deep` / `pop` / `soft` / `light` / `"#hex"`; default as in the table. `duo` (polaroid): their photos as a
  changing background, or without photos their own video blown up, black-and-white and tinted main → pop → soft, with a
  halftone dot texture. `"brackets": false` drops the [ ].
- `images`: only their photos (uploaded on the page, «Мої файли», `<reel>/` or `~/reels/assets/`) or pictures they picked in
  «Знайти». Never stock you chose, never frames from another of their videos without asking. collage / pile / picture
  without enough photos fall back to `window` (printed).
- Timing: one card = one phrase, 1.5-5 s, `start` on the phrase's first word, `end` on its last. The style of the reference
  reels is 2-5 different looks in a row on consecutive phrases, then back to the full frame; never the same look twice in a
  row (build_reel's `variety:` check tells looks apart), at most 6 per reel unless the person asks for more.
- Fonts and colours are the brand's (or the reel's style); captions step aside for the card's seconds (it carries the
  words); punch-ins don't fire inside it; the frame comes back on its own at `end`. Full frame on the page: `place` =
  `[0, 0, 1080, 1920]`, the storyboard still is taken near its end with all words on.
- Tested 2026-10-23 on two different reels (540p drafts, every look, captions around them) and as menu previews.

## Transparent motion elements (WebM with alpha, ProRes 4444)

A second source of motions besides the catalog: an element rendered with a transparent background in any tool (Remotion,
After Effects, Jitter...). Remotion: `npx remotion render <Element> out.webm --codec=vp9 --pixel-format=yuva420p --image-format=png`.

```json
{"type": "overlay", "src": "overlays/roi.webm", "start": 12.4, "end": 15.0}
```
- build_reel detects the alpha channel: full frame, no border, no extra entrance or sfx (the element animates itself), captions
  step aside for its seconds (`"captions": true` keeps them). A `box` on the card places a smaller one (and gets the safe-zone check).
- Render it with the element above the head or on the chest (`face.json` says where the face is), full screen only as a takeover.
  Never half over the face.
- Their words in every text, numbers exactly as said. Counts toward the reel's motion number and the «never twice» rule;
  `motions.py log` sees it only with `"brand"` set (below).
- Own Remotion library: with `~/motion/library.json` (or `$MOTION_HOME/library.json`: `{"elements": [{"element", "ua",
  "moments", "text_vars"}]}`), `motions.py menu` / `ideas` offer its elements next to the catalog as `brand:<Element>`.
  Name the file `overlays/brand-<Element>-<slug>.webm` and set `"brand": "<Element>"` on the card so `ideas` and `log` count it.

## Caption styles (status `caption`)

11 catalog styles can draw all the captions instead of the brand's own: highlight, pill-karaoke, neon-accent, neon-glow,
gradient-fill, glitch-rgb, matrix-decode, particle-burst, emoji-pop, clip-wipe, weight-shift. The person picks one on the
review page («Субтитри» → «Анімація субтитрів», with a preview of each); `review_sync.py import` writes edit.json
`"caption_style": "<name>"` (prints `CAPTION STYLE:`). build_reel feeds it their words and timing, the caption groups and
accent words, the brand fonts and colours, at the brand caption height (`"cap_at"` in the catalog = where the style's line
sits in its 1920x1080 frame). brand.json `captions.anim` makes one the default for every reel. The page shows the brand
captions while reviewing; the style appears on the draft. editorial-emphasis, texture and blend-difference stay manual: they
show no text with fed-in words on this HyperFrames version.

## «Мої марки» (stamps)

After each final, `motions.py stamp <reel>` collects every graphic the reel kept (catalog motion, brand element, template
card, camera move) into `<REELS_HOME>/stamps.json`: key, Ukrainian name, moments, the settings that worked (`spec`), which
reels used it and a still. `ideas` offers up to two stamps per phrase before the catalog (★ моя марка), `menu` lists them.
The review page shows them under «Ефекти» → «Мої марки». Reuse a stamp's `spec` as the card's settings, with new words.

## Re-testing the library (after a HyperFrames update or for new items)

`python3 scripts/test_motions.py <any cut reel> <out dir> --status candidate` (or `--names a,b`, or `--status manual`)
renders every motion alone on that reel with Ukrainian sample text and prints an index; look through
`<out>/sheet_*.jpg` and the LEAK flags (something visible before the motion starts). Write the verdicts into
`references/motion_catalog.json` (status, card placement, replace, note). `--previews` makes the 3 s clips for the
review page's «Тільки вручну» list. Two workers at most on an 8 GB Mac; the run resumes where it stopped.

## Adding more from the catalog (447 items)

`cd engine/hf && npx hyperframes add <name>`, then `python3 scripts/wrap_snippets.py` (paste-in snippets get their own
composition), then test it before using it in a reel: one card on a short test reel, `REEL_DRAFT=1 python3 build_reel.py`,
`npx hyperframes@0.8.145 snapshot proj --at <t>`, look at the frame. Add it to `motion_catalog.json` with its moment, `ua`
line, tested `card` and status. Skip ones whose text is English with no field to change it, ones with another brand's look
baked in, and 3D/WebGPU shaders (slow on an 8 GB Mac). The 88 already rejected are in the catalog as `skip` with the reason.

## Captions next to a motion

Captions step aside while a motion sits on their line. With captions above the head (`caption_y` ~370), a `top` band motion
and the captions share the spot, so for those seconds the motion carries the words: keep it to the phrase it shows, or use
`chest`. Every text field needs a value: an empty string falls back to the motion's English default.
