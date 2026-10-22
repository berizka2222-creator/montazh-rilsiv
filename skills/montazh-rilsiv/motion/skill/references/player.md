# Motion on a website (Remotion Player)

Two ways, pick the lighter one that does the job:

| Need | Do |
|---|---|
| A looping animation, the same for everyone (hero, section accent) | render it (`scripts/render.sh`, or `render-overlay.sh` for transparent WebM) and use `<video autoplay muted loop playsinline>`. A few hundred KB, no JS |
| It changes per visitor, per URL, or reacts (personalised greeting, quiz result, the visitor's niche, start on scroll) | the embed below (Remotion Player, ~1.6 MB JS once per site) |

## The embed

Build and copy into the site:
```bash
cd ~/motion && scripts/build-embed.sh "<site folder>"     # e.g. ~/Desktop/my-site
```
It writes `<site>/motion-assets/` (motion-embed.js + fonts + chrome). Then in the page:
```html
<div data-motion="CtaEnd"
     data-props='{"title":"Привіт, *гостю*","button":"Записатися в анкету","format":"4:5"}'
     data-url-props="name:title"
     data-loop data-play="view"></div>
<script src="/motion-assets/motion-embed.js"></script>
```
- `data-motion`: any composition id (HookTitle, Counter, ListReveal, Marker, BeforeAfter, Chat, LowerThird, CtaEnd, Bars) or
  `MotionReel` with a full scene list in `data-props`.
- `data-props`: the same props as in the renders (JSON). Texts are hers.
- `data-url-props="param:prop,..."`: `?name=Олена` puts «Олена» into `title`. Use for links sent from the quiz, bot or ads
  (utm-like params): the visitor sees a video made for them.
- `data-loop`, `data-autoplay` (starts at once, muted), `data-play="view"` (plays while half of it is on screen, pauses off
  screen), `data-controls`, `data-radius="28"` (corner radius, default 28 = brand glass).
- Width follows the container (`style="max-width:420px"` on the div); height keeps the format.

Check it locally before the site goes live: `cd ~/motion/dist-embed && python3 -m http.server 4807`, open
`http://127.0.0.1:4807/?name=Тест` (demo page with three embeds), look at it at phone width too.

## Notes

- Same-origin only: `motion-assets/` sits on the same site as the page (fonts load from there).
- Rebuild the embed after changing any element or brand.ts, then copy again.
- Licence: Remotion is free for individuals and teams of up to 3 people (remotion.dev/license). A bigger company or
  selling it as a product to others needs a company licence: check remotion.dev/license.
- Lighthouse: the script is ~1.6 MB; put the `<script>` at the end of `<body>` (or `defer`) so the page paints first.
