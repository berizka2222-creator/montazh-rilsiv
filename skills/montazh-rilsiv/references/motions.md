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
- The tested placement comes from the catalog automatically (layout, place, tone, ink, css); set them on the card only to move it.
  `box: [x, y, w, h]` on the 1080x1920 frame; `scale` shows a 1920-wide overlay bigger than the frame (lower thirds, light
  leaks: x may go negative).
- `tone`: `dark` (default: the brand's deep green panel, white text, pink accents), `light` (white card, dark text) or
  `clear` (no panel, light text on the video). `ink: "light" | "pop" | "#hex"` forces the text colour of text-only motions.
- `replace` (status `replace` motions: lower thirds, the IG follow card...): `{"<exact English text>": "their text"}`. The
  catalog lists the strings; build_reel warns when one isn't found.
- Fonts: every catalog motion is drawn in the brand fonts (body weight for regular text, head for bold), whatever the motion
  ships with. `"keep_fonts": true` keeps its own (rarely: a terminal's monospace).
- `full` and `split` motions take over the frame for their seconds: keep them 2-4 s, at most two `full` per reel. Light
  leaks and the flash (`layout: "transition"`) are see-through and go between two thoughts.
- Carousels take `"images": [..]`, every slot is filled for you.

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
