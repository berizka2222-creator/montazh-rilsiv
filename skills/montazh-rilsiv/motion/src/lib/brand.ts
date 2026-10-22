// Brand tokens: written by scripts/sync-brand.py from the person's brand.json (colours, fonts, own 3D elements).
// Every element, reel and overlay reads these, so a change in brand.json shows up in the next render.
// Roles: lime = main accent (labels, buttons, numbers), pink = second accent (italic words, strike-through).
import { Easing } from "remotion";
import G from "./brand.generated.json";

export const C = G.C as Record<
  | "c0" | "c1" | "c2" | "c3" | "main" | "deep" | "lime" | "limeHi" | "pink" | "pinkDk"
  | "cream" | "ink" | "tx" | "tx2" | "tx3" | "bd" | "bd2",
  string
>;

export const F = {
  head: G.F.head, // headlines, numbers, body
  accent: G.F.accent, // italic accent words, 1-2 per title
  mono: G.F.mono, // eyebrows, labels, row numbers (UPPERCASE)
} as const;

export const EASE = Easing.bezier(0.2, 0.7, 0.2, 1);
export const EASE_IN = Easing.bezier(0.6, 0, 0.8, 0.3);

// Radii from the design system
export const R = { photo: 12, card: 18, glass: 28, pill: 100 } as const;

// Instagram Reels screen on 1080x1920: keep text out of these.
export const SAFE = {
  top: 220,
  bottom: 1500,
  side: 64,
  buttonsX: 950,
} as const;

export const FORMATS = {
  "9:16": { width: 1080, height: 1920 },
  "4:5": { width: 1080, height: 1350 },
  "1:1": { width: 1080, height: 1080 },
  "16:9": { width: 1920, height: 1080 },
} as const;
export type Format = keyof typeof FORMATS;

// Their own 3D / sticker elements in public/chrome (from <REELS_HOME>/assets/chrome), by file name
export const CHROME: readonly string[] = G.chrome;
