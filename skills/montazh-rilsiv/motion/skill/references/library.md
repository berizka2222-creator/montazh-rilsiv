# Library: what to take from Remotion (checked 2026-10-21, remotion.dev)

Take the **pattern**, never another brand's look: every piece is rebuilt in `~/motion/src/elements/` with brand.ts colours
and fonts. Preview of each Remotion Element: `https://www.remotion.dev/elements/<category>/<name>/` (video on the page).
In Studio (`npm run dev`) «Browse Elements» shows the same catalog and can paste the source into the project as a start.

Status: **ready** = built in brand in ~/motion · **pkg** = the package is installed, element not built yet ·
**idea** = worth building when a reel asks for it · **skip** = not for us (reason).

## Remotion Elements → reel moments

| Element | Moment (reel-editor) | Status / ours |
|---|---|---|
| Text Marker, Circle Marker, Strike Through, Crossed Off | хук / ключова фраза | ready: `Marker` (modes highlight, circle, strike, underline) |
| Number Counter | цифра | ready: `Counter` |
| Horizontal Bar Chart | ріст / падіння | ready: `Bars` |
| Vertical Bar Chart, Line Chart, Pie Chart | цифра / ріст | idea: CPL / ROAS over weeks (line), budget split (pie). Real numbers only |
| On-Screen Messages | повідомлення / чат | ready: `Chat` |
| Name Lower Third | ім'я / хто я | ready: `LowerThird` |
| Location Lower Third | ім'я / хто я | idea: city / event plate (same look as LowerThird) |
| YouTube End Card, Subscribe Nudge | заклик (CTA) | ready as `CtaEnd`; idea: an IG «Підпишись» nudge in brand |
| YouTube Comment Highlight | відгук / доказ | idea: IG comment / review highlight, only her real comments as screenshots or text |
| News Article Highlight | відгук / доказ | idea: a screenshot with a marker sweep over the quoted line (case, news about Meta) |
| Polaroid Pictures | картинки / приклади | idea: photos/screens dropping as polaroids (reel-editor has a polaroid overlay too) |
| Speed Lines | перехід / проблема | idea: comic speed lines behind a punch word |
| Rotating Cards | картинки / приклади | idea: 3-5 creatives / screenshots rotating (good for «ось креативи, що зайшли») |
| Wiggling Callout | заклик (CTA) | idea: a sticker «новий потік», «подарунок» wiggling on the CTA |
| Shine | хук | idea: light sweep over a chrome element or the button |
| Peel, Tear apart | перехід / до-після | idea: peel the «було» card off to show «стало» |
| Picture in Picture Transition, Slide to Split Screen | перехід | reel-editor already does split / camera shrink; for motion reels: idea |
| Social Safe Zones | (check) | ours: `SAFE` in brand.ts + reel-editor «Зони»; use the Element in Studio to eyeball |
| Backgrounds: Notebook Paper, Paper Texture | фон | idea: «нотатки» look for a lesson-style reel |
| Backgrounds: Rotating Starburst, Moving Waves, Zigzags, Liquid Contours | фон | idea: only in brand colours, very subtle (.03-.08) under text |
| Audio: Oscilloscope, Voice Note, Mirrored Spectrum | аудіо | idea: «голосове повідомлення» from a client (real one) or a podcast clip |
| Maps: A-to-B Flyover, Spinning Globe, Watercolor Map | гео | idea: «працюю з клієнтами з N країн» (real list). Watercolor Map is paid: skip |
| Captions (Basic, Rounded, Moving Pill, Popping Word, Word Highlight) | субтитри | skip: reel-editor captions on ElevenLabs Scribe already do this in brand |

## Packages (installed in ~/motion unless marked)

| Package | Use |
|---|---|
| `@remotion/transitions` | scene transitions (slide, fade, wipe in MotionReel; also flip, clockWipe, iris, none) |
| `@remotion/rough-notation` | hand-drawn marks (Marker) |
| `@remotion/light-leaks` | warm light leak between two thoughts (pkg: add as a transition or overlay scene) |
| `@remotion/shapes`, `@remotion/paths` | circles, stars, arrows drawn on (`evolvePath`): arrows pointing at a number, a ring filling |
| `@remotion/noise` | organic drift for glows and chrome elements |
| `@remotion/player` | the website embed (references/player.md) |
| `@remotion/media` | audio / video inside reels (voice-over, music, a screen recording scene) |
| `@remotion/fonts`, `@remotion/google-fonts` | brand fonts |
| not installed: `@remotion/lottie` | Lottie animations (stickers, icons) if she has .json ones |
| not installed: `@remotion/three` | 3D (chrome objects in real 3D); heavy on an 8 GB Mac, only on request |
| not installed: `@remotion/motion-blur` | trail on fast moves (whip-in titles) |
| not installed: `@remotion/animated-emoji` | Google's animated emoji (only if she likes emoji in reels) |
| not installed: `@remotion/gif` | GIFs inside a scene |
| not installed: `@remotion/sfx` | sound effects; reel-editor has its own sfx library in `reel-editor/sfx` (reuse those files) |

Install: `cd ~/motion && npx remotion add <package>` (same version as remotion).

## Templates (remotion.dev/templates) worth knowing

| Template | For us |
|---|---|
| Stills | dynamic PNG/JPEG from the same elements: carousel slides, reel covers, ad statics from one design. Strong fit later |
| Audiogram / Music Visualization | podcast or voice clip with waveform + captions |
| Recorder | screen + camera recording app in the browser: screencasts of Ads Manager for lessons |
| Overlay | overlays for other editors (ProRes with alpha): same idea as our `render-overlay.sh`, for CapCut / Premiere use `--codec=prores --prores-profile=4444` |
| Prompt to Video, Prompt to Motion Graphics | AI story / motion generators; reference only |
| Render Server (Express), Next.js, React Router | needed only for automated batch rendering (batch-ads.md) |
| Element Library | if we ever publish our elements as a library for students |
| skip: Blank, Hello World, Electron, Skia, Code Hike, Stargazer, TikTok captions (ours are better), Editor Starter / Timeline (paid) |

Third party: `remotion-bits` (github.com/av/remotion-bits) has ready animated text, 3D cards, etc. Read its code before installing
(read third-party code before installing it) and restyle to brand.

## Exporting for other editors

- Reel-editor / HyperFrames: VP9 WebM with alpha (`scripts/render-overlay.sh`).
- CapCut, Premiere, Final Cut, DaVinci: ProRes 4444 with alpha:
  `npx remotion render <Id> out/x.mov --props='{"bg":"none",...}' --codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png`
