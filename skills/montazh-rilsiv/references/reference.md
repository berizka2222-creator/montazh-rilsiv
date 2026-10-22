# Reference reel («зроби як тут»)

The person sends a reel they love (a link in chat, or on the review page: «Ефекти» → «Рілс-референс»; `review_sync.py import`
prints `REFERENCE: <url>`). Take its techniques, never its content: their words, brand colours and fonts stay theirs.

1. `python3 scripts/reference.py <url> [<out>] --transcribe` → `ref.mp4`, `info.json` (author, caption), `cuts.json` (shot
   changes, average shot length), `sheet_NN.jpg` (a frame every 1.5 s, 12 per sheet: sheet k = seconds 18(k-1)..18k),
   `cut_<t>.jpg` at every shot change, `transcript.json`. Instagram refuses anonymous downloads: the script retries with
   the Chrome, then the Safari login (macOS asks once for the Mac password: «Дозволити завжди»; it only reads the post).
   Exit 2 = no way in: look at it in their browser (Claude in Chrome: seek the `<video>`, grab frames) or ask for a screen
   recording.
2. Read every sheet and the transcript. Write down, with the second it happens:
   - hook: what is on screen in the first 3 s (title, collage, sticker, b-roll) and how long it stays;
   - captions: font kind, size, position, words per line, accent words (colour / italic / pill);
   - pace: `avg_shot` from cuts.json, zoom punches, how often b-roll or full-screen graphics cut in;
   - graphics by moment: section titles («Step 1»), app / UI cards, lists, numbers, logos, screen recordings, stickers;
   - transitions and sound (flash, whoosh, music under the voice).
3. Map each technique to this skill: catalog motions (`motions.py menu <moment>`), caption styles (`caption_style`),
   camera moves, template cards (title, push, list, split, steps, bigtext), real logos (`inserts.py`), brand elements
   (`brand:<Element>`). Say plainly what has no match.
4. Tell them in a short table (their technique → what we use), then plan proposal.json with it: same pace and moments,
   their own words. The storyboard shows how it will look before any render.
