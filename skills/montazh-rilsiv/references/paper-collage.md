# Paper collage (Vox style)

The editorial paper-collage look made popular by Vox explainers: hand-torn paper, tape, halftone dots, real paper
shadows, bold flat colour, big cut-out words. Ideas adapted from vox-director (Alisa0808, MIT); everything here runs
locally in the reel engine, nothing is uploaded and nothing costs money except the optional AI inserts at the end.

## The four own motions (`motions/rf-*.html`, catalog group «Свої: паперовий колаж (Vox)»)

| Motion | Card | Use it for |
|---|---|---|
| `rf-paper-cutout` | `{"type":"motion","name":"rf-paper-cutout","start","end","vars":{"text":"ЦЕ / *НЕ* ПРОМТ","entrance":"auto"}}` | a key phrase of 2-6 words; `*word*` = key word on a brand-coloured scrap; `entrance` auto (cycles fly, slap, drop, pop) or one of them |
| `rf-starburst` | `{"type":"motion","name":"rf-starburst","start","end","vars":{"text":"-50$","sub":"за квиток"}}` | the one number or word of the reel that must hit; `side` auto / right / left |
| `rf-paper-caption` | edit.json `"caption_style": "rf-paper-caption"` (+ optional `"caption_vars": {"paper": "#F3EBDD", "tilt": 3}`) | captions as cut-out paper words, key word on a coloured scrap with a keyline |
| `rf-scrapbook` | `{"type":"motion","name":"rf-scrapbook","layout":"full","start","end","images":[...],"vars":{"text":"ОСЬ ЩО / ВИЙШЛО"}}` | 2-6 of THEIR photos / screenshots as taped prints on a cream table, cut-paper headline at the end; results, cases, the closing card before the CTA |

Rules:
- The look is a style decision, not decoration: on a reel in this look use 2-4 paper pieces, not one lonely scrap among
  neon effects. Don't mix `rf-paper-caption` with neon / glitch caption styles or glass cards in the same reel.
- Paper and ink colours: paper `#F3EBDD` cream by default, key scraps in the brand's pop colour, letters in the brand's
  deepest colour (build_reel fills `brand_pop`, `brand_main`, `brand_deep`). A brand with a light palette can set `"paper"`.
- `rf-scrapbook` only with their own pictures. No pictures, no scrapbook.
- All four keep the face clear (cutout and starburst read face.json) and hide captions for their seconds like every graphic.

## Retro theme presets (for the paper look, a reel or a style round)

Offer one when they want the reel to «look like» an era; it sets the paper, scrap and ink colours (pass them as
`vars` / `caption_vars`) and the mood of the plan. Their brand fonts stay; only the palette and pace shift.

| Preset | Palette (paper / scrap / ink) | Mood, pace |
|---|---|---|
| Ретро 50-х (american-retro) | cream `#F4E9D2` / red `#C8322B`, blue `#1F4E8C` / `#1B1414` | ads and pulp covers, punchy |
| Швейцарський модерн (swiss-modern) | white `#F5F3EE` / red `#E1251B` / black `#111` | calm grid, few pieces, big type |
| Панк-зин (punk-zine) | photocopy grey `#E6E3DC` / fluorescent `#FF3EA5` or `#D4FF3A` / black | ransom-note words, max energy |
| Конструктивізм (soviet-constructivist) | cream `#EFE6D2` / red `#C1121F` / black | diagonals, tilted pieces, bold |
| Плакати 30-х (wpa-propaganda) | ochre paper `#E8D9B5` / teal `#2F6F73`, rust `#B5512E` / `#20201E` | stencil, calm |
| 70-ті (70s-groovy) | cream `#F2E3C2` / mustard `#D9A42B`, rust `#B4532A`, avocado `#7A8B3A` / brown `#3B2416` | warm, rounded, riso grain |
| Туш (chinese-ink) | rice paper `#F3EEE2` / vermilion `#D2381B` / ink `#151515` | quiet, one seal-red accent |
| Атомна доба (atomic-age) | cream `#F1E8D6` / turquoise `#2BB3B1`, orange `#F28C28` / `#1C2A33` | starbursts, retro-future |
| Газета (newsprint-editorial) | newsprint `#ECE8DF` / black, one red `#B3261E` / `#111` | heavy halftone, editorial |
| Ар-деко (gilded-deco) | black `#141210` / gold `#C9A25A` / cream `#F3EBDD` | luxury, slow; gold scraps on dark |

## AI inserts in the Vox style (optional, paid by them)

When they want a moving collage insert (a 3-5 s scene between their talking): you write the prompt, they generate it in
their video model (Seedance, Kling, Veo...) and drop the file in `<reel>/overlays/` or «Накладення»; it goes in as an
`overlay` card (`"size": "full"`). Never generate it yourself, never pay for anything.

Prompt rules:
- **Image / first frame:** one finished collage poster: «hand-cut paper collage, editorial zine, torn and scissor-cut
  edges, tape corners, halftone dots, newspaper clippings, real paper drop shadows, printed cut-outs, not CGI, not 3D, not
  photoreal, print grain, bold flat <colour> background». Describe the scene as separate paper layers (that gives depth).
- **Video:** describe the motion, not the picture. One camera move per shot (static, slow push in, pull out, pan, tilt,
  parallax). Say how it ends: «…then settles». Never write «snap», «punch-in», «slam» or «quick zoom»: models jump inside
  the shot. Keep it flat: «flat 2D, camera parallel to the paper, rigid paper, no morphing, one continuous move».
- **Their face or product:** if their photo is in it, the face stays a clean photo cut-out (no halftone on the face, pose
  changes only in the body); a product label stays letter-perfect.
- Text that must be read goes on in the edit (a card), never inside the AI video.
