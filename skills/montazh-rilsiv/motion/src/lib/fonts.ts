import { loadFont } from "@remotion/fonts";
import { loadFont as loadPlexMono } from "@remotion/google-fonts/IBMPlexMono";
import { staticFile } from "remotion";
import G from "./brand.generated.json";

loadPlexMono("normal", {
  weights: ["400", "500"],
  subsets: ["latin", "cyrillic", "cyrillic-ext"],
});

// The brand's own font files (public/fonts, copied by scripts/sync-brand.py from <REELS_HOME>/fonts)
export const fontsReady = Promise.all(
  G.fonts.map((f) =>
    loadFont({
      family: f.family,
      url: staticFile(`fonts/${f.file}`),
      weight: f.weight,
      style: f.style,
    }),
  ),
);
