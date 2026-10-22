# Motion (Remotion, in your brand)

Installed by the reel skill (`scripts/setup_motion.sh`). Colours, fonts and your own 3D elements come from
`<REELS_HOME>/brand.json` via `scripts/sync-brand.py`, which every render script runs first.
Skill: `~/.claude/skills/motion-brand/SKILL.md` — how to use everything here.

- `src/lib/brand.ts` brand tokens (read from `src/lib/brand.generated.json`) · `src/lib/fonts.ts` fonts · `src/elements/` the element library · `src/reel/MotionReel.tsx` scene-list reels
- `scripts/render.sh <Id> <props.json> <out.mp4>` finished video
- `scripts/render-overlay.sh <Id> '<props>' <out.webm>` transparent element for the reel editor
- `scripts/build-embed.sh [site]` website embed (Remotion Player)
- `npm run dev` Remotion Studio
