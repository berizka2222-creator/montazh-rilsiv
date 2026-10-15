# Style lab («Стиль»)

The person's own editing style, built in rounds of rendered variants they rate on the review page's «Стиль» tab. Each person gets their own style; never start a student from someone else's. Script: `scripts/style_lab.py` (all commands in its header). Output: `~/reels/styles/<name>.json` (build_reel.py reads it) and `~/reels/styles/STYLE.md` (Затверджено / Можливо / Відхилено, with her reasons).

## Where the base comes from (step 0)
- **They have a design system** (brand book, site, Figma, their own brand file, or the brand.json/brand.md the setup interview wrote): take colours, fonts, shapes and elements from it. They only confirm.
- **No design system:** ask for 3-5 references (reels, screenshots, posts) and 4 short mood questions (calm or energetic? clean or playful? big bold words or small neat ones? sounds: none, soft, punchy?). The 9 starting directions still come in their colours and fonts; swap the ones their references rule out for directions built from those references.

## The fragment
`python3 scripts/style_lab.py fragment <reel-folder | raw clip> <start> <end> --hook "line / line"`: 5 seconds of their own video where they say something with a point (a reel folder reuses its master + transcript + face.json; a raw clip is transcribed and face-checked). Then fill `~/reels/styles/_lab/fragment/fragment.json`:
- `hook`: their own hook text (ask; never invent it), `accents`: 2-3 spoken words, at least one outside the graphic's seconds so the accent look shows;
- `graphic`: `{start, end, title?, rows, row_times}` on spoken words (rows = what they say, word for word), `transition_at`: a seconds mark between thoughts;
- `number` `{value, suffix, text, t}` and `cta` only if they say one in those seconds (or ask for their CTA words).

## Round 1: 9 directions (the whole look)
Everyone gets 9 directions. `python3 scripts/style_lab.py directions` writes them from the archetypes (calm premium, bright editorial, lively scrapbook, chrome luxe, magazine cover, phone notes, kinetic type, quiet, split screen), recoloured with their brand colours, their head/accent fonts and the other display fonts of their design system (brand.json `caption_fonts`), and their first element from `~/reels/assets/elements_clean` or `elements`. Open the json and adjust before rendering: swap a direction their references or answers rule out for one built from a reference (each variant is a whole style json: `motion.speed`, `captions.anim`/`accent`, `brand` overrides like `title_glass`, `title_color`, `fonts`, `cta_bg`, `captions`, `layouts.list`/`camera`, `sounds.events`, plus its cards: hook, one graphic, one camera move). Same words, same fragment. Keep the hook below the chin or above the head, never on the face (check frames).
`python3 scripts/style_lab.py round <round.json>` renders every variant at 540p (~15 s each) into `_lab/rounds/<id>/`. Grab 4 frames per variant and look before uploading.

## Putting a round on the page
1. Upload the printed `.mp4` + `.jpg` files (`Artifact` `asset: true`, `file_paths`).
2. Write `{file name: url}` to `uploads.json`, then `python3 scripts/style_lab.py page <round-dir> uploads.json` → `doc.json`.
3. `ArtifactData set style/round` from `doc.json` (`file_path`); delete `style/votes` if it holds the previous round. The page shows the round in place, with a banner, even when no reel is loaded.
4. Tell them: «Стиль» tab, watch each (muted loop; «Зі звуком» plays it with sound), «Зони» lays the Instagram screen over every variant, Залишити / Можливо / Прибрати + a note, then «Готово → Claude».

## When the round comes back
The button sends «▶ Кнопка «Готово → Claude» у «Стилі»: раунд <id> оцінено…» (or they write «стиль»).
1. `ArtifactData get style/votes` → save to a file; `python3 scripts/style_lab.py votes <round-dir> votes.json` and read her notes. It also lists her **references** (the page takes reel links and files): download a link with `yt-dlp -o <lab>/refs/%(id)s.%(ext)s <url>` (Instagram may need `--cookies-from-browser safari`; if it still fails, ask for a screen recording), a file with `Artifact` `action: "read"`, `path` = its asset id, `out_dir` = `~/reels/styles/_lab/refs`. Grab frames, name what she likes in it (caption look, pace, transitions, sounds) and build the next round's variants from that.
2. `python3 scripts/style_lab.py apply <round-dir> votes.json`:
   - directions: every «Залишити» becomes its own style (`styles/<id>.json`); «Прибрати» goes to Відхилено with her reason; «Можливо» waits in `_lab/directions.json`. No keeps: the next round is the «Можливо» ones fixed by her notes plus new directions.
   - elements: «Залишити» is merged into the style (list looks and camera moves add up), «Прибрати» is never offered again (a dropped push/steps also goes to `layouts.deny`), «Можливо» is listed to refine.
3. Show her `STYLE.md` in two lines, then `ArtifactData set style/list` from `~/reels/styles/list.json` (apply writes it, with each style's example video from the round's `uploads.json`): that list is the «Мої стилі» gallery on «Стиль» and the «Стиль монтажу» picker on «Графіка», where she chooses the style per reel. Put up the next round if there is one; if not, `ArtifactData update style/round` with `{"closed": true}` so the page stops saying a round is coming. «Дай ще варіанти» or no keeps at all: a new directions round (other archetypes, their references, the «Можливо» ones fixed by the notes), never a dead end.

## «Доточити» and «Завжди цей» (from the page)
- A style card in «Мої стилі» has «Доточити…»: she picks an element and it sends «▶ «Стиль»: доточи стиль <name> (…): <element> (…)» (also saved in db `style/request`). Run `python3 scripts/style_lab.py element <name> <element>`, then `round`, upload, `page`, `ArtifactData set style/round` (and delete `style/votes`).
- «Завжди цей» writes `default` into db `style/list`; a new reel with no style picked takes it. So when you refresh the list after a round, use `ArtifactData update style/list` with `{"items": [...]}` (never `set`), or her default is lost.

## Rounds 2+: element by element
`python3 scripts/style_lab.py element <style> <element>` writes the round json from the catalogue (one change per variant, same words, rejected ones skipped), then `round`. Order: `captions`, `hook`, `lists`, `numbers`, `split` (split / push / steps), `transitions` (camera moves), `cta`, `sounds` (each sound on its own mini animation), `motion` (speed). A round may hold several sections: merge the generated jsons' `sections` into one file if she wants fewer rounds. «Можливо» variants come back fixed by her note (edit the variant's style patch by hand).

## What build_reel does with a style
Which style: edit.json `"style"`, else `<reel>/style.txt`, else `REEL_STYLE`, else brand.json `"style"`. It deep-merges the style's `brand` block over brand.json, keeps lists to `layouts.list` (no repeat rule still applies), maps camera moves outside `layouts.camera` to an allowed one (a shrink carrying words becomes big text), turns `layouts.deny` types into lists, scales every tween by `motion.speed`, sets the caption entrance (`pop`/`rise`/`blur`/`slam`/`none`) and accent look (`color`/`box`/`underline`), and re-voices sounds per event (`transition`, `row`, `title`, `hit`, `accent`, `cta`, `typing`; `null` = silent; a sound she picked on the page still wins). It prints a `style:` line for every change. `layouts.number` / `layouts.split` are guidance for planning the graphics: read them when writing proposal.json.
