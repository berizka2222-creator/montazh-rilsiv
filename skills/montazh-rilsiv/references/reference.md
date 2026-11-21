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
   (`brand:<Element>`), «подачі голови» when the person's video itself shrinks into a window / circle / polaroid / collage
   on a coloured background (`head` cards, «Подачі голови» in motions.md). Say plainly what has no match.
4. **Concepts before the reel (idea from OpenMontage).** When the reference can be read more than one way (it
   has a distinct pace AND a caption look AND a structure, or they said only «зроби як тут»), don't plan the reel yet:
   - `python3 scripts/ref_concepts.py prep <reel> <start> <end> --hook "<their hook text>"`: 5 s of THEIR video with a point
     (ask for the hook text, never invent it);
   - write `<reel>/concepts/<id>.json`: 2 concepts (3 only when it truly reads three ways), each taking a DIFFERENT thing
     from the reference (pace / caption look / structure / graphics / sound), their colours and fonts always, with the
     `full` estimate for the whole reel (graphics per minute, «за мною» seconds, anything paid like Krea);
   - `python3 scripts/ref_concepts.py round <reel> <that json>`: samples + measured render time + cost → `summary.md`.
     LOOK at every sample, upload the mp4s (Artifact asset) and show them one short block per concept: what it takes from
     the reference, what stays hers, the cost line, the sample. One question: which one (or «A, але субтитри з B»).
   - their answer → `python3 scripts/ref_concepts.py pick <reel> <id> [--name ...] [--mix "their note"]` (apply a mix in the
     saved style json by hand), then plan proposal.json in that style as below. If they like it for future reels too,
     it is already in «Мої стилі».
   Skip this step when the reference is one clear thing («такі самі субтитри», «такий самий хук»): go straight to 5.
5. Tell them in a short table (their technique → what we use), then plan proposal.json with it: same pace and moments,
   their own words. The storyboard shows how it will look before any render.
