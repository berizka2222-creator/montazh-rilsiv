# Врізки під кожну фразу

A graphics density for talking-head reels: under every meaningful phrase (every 2-4 s) something appears that shows
exactly what she is saying right then: the real logo of the service she names, a live screenshot of a site, the number she
says, or 1-3 of her own words. Triggers: «врізки під кожну фразу», «врізки», «щільна графіка», brand.json `"graphics": "inserts"`.

## Steps (inside reel-editor step 5.3, after auto_edit.py)

1. `python3 scripts/inserts.py <reel> --fetch` splits the cut reel's speech into phrases (`master_transcript.json`) and, per
   phrase, lists brands (real logo downloaded to `<reel>/logos/`, or a live screenshot to `<reel>/shots/`) and numbers. It writes
   `<reel>/inserts.json`. It only proposes.
2. Go through the phrases in order and give each one at most ONE insert:
   - she names a service with a logo → `{"type": "logo", "src": "logos/<slug>.svg", "label": "Zoom"}` (2-3 services in one
     phrase: `"src": [..]`, label left out or a short shared word);
   - a site worth seeing (her own site, a tool's landing page) → `shot` with the screenshot from `shots/`;
   - a number → the `count-up` motion (references/motions.md) or `bigtext` for "170+ учнів" style facts;
   - nothing to show but the phrase carries the point → `tag` or `bigtext` with 1-3 of HER words from that phrase;
   - a filler phrase («я в курсі», «і так далі») → nothing. An empty 2-3 s is fine, a decorative insert is not.
3. Keep the variety rule: never the same card type three times in a row (build_reel prints `variety:`).
4. Precheck, draft at 540p and the review page as usual.

## Rules (each one is a mistake that already happened somewhere)

- **No invented interfaces.** A logo only from `logos/` (Simple Icons, the official mark) or her own files; a screenshot only of a
  live page. Never draw, generate or "recreate" a logo or an app screen. No source → a text `tag` with the name.
- **Ads Manager, Business Suite and other logged-in screens can't be screenshotted by the script** (login). Use her own
  screenshots from «Мої файли» / `~/reels/assets`, or ask for one; until then it's the Meta logo with the label.
- **«мета» in Ukrainian is «goal»**: only Latin "Meta" maps to the Meta logo (inserts.py already ignores the Cyrillic word).
- **ChatGPT, OpenAI, Canva, CapCut have no logo in Simple Icons** (the brands asked to be removed): text tag, or a screenshot of
  the public site if it isn't blocked. Don't fetch a logo from elsewhere.
- **One text per frame.** An insert and a caption accent may share the moment; two text inserts may not.
- **Numbers exactly as said.** «більше ста сімдесяти» = "170+", «відсотків двадцять» = "20%". inserts.py reads number words,
  but «один, два, три курси» is a list, not "123": check every stat against the phrase text in inserts.json.
- **Off the face, inside the safe zones.** `logo` moves itself off the face like lists; check `safe zone:` lines anyway.
- **Her words, not yours.** Text inserts quote the phrase, they don't summarise it in new words.
