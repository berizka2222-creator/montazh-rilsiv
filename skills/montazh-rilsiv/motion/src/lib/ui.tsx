import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";

import { C, EASE, EASE_IN, F, SAFE, CHROME } from "./brand";

// Inside a MotionReel the transitions do the exit, so scenes stay put to the end (no blank frame between scenes).
export const ExitContext = React.createContext(true);
// bg + place of the element being rendered (set by withLayout in Root, read by Stage).
export const LayoutContext = React.createContext<{
  bg: "brand" | "none";
  place: "center" | "top" | "chest";
}>({
  bg: "brand",
  place: "center",
});

// Every element takes these. bg "none" = transparent overlay for a reel (render with scripts/render-overlay.sh).
export const baseSchema = z.object({
  duration: z.number().min(0.5).max(60).default(3), // seconds (standalone render; inside a reel the scene sets it)
  format: z.enum(["9:16", "4:5", "1:1", "16:9"]).default("9:16"),
  bg: z.enum(["brand", "none"]).default("brand"),
  chrome: z.string().default(""), // a chrome element id from public/chrome ("" = none)
  // Over a talking head (bg "none") it is either clear of her face or it replaces the frame (the placement rule):
  // "top" = band above the head, "chest" = low band above the captions, "center" = full-screen takeover / motion reel.
  place: z.enum(["center", "top", "chest"]).default("center"),
});
export type Base = z.infer<typeof baseSchema>;

/** 0 → 1 entrance starting at `delay` frames, and 0 → 1 exit over the last `outFrames` frames. */
export const useInOut = (delay = 0, inFrames = 18, outFrames = 12) => {
  const frame = useCurrentFrame();
  const exits = React.useContext(ExitContext);
  const { durationInFrames } = useVideoConfig();
  const enter = interpolate(frame, [delay, delay + inFrames], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exit = exits
    ? interpolate(
        frame,
        [durationInFrames - outFrames, durationInFrames],
        [0, 1],
        {
          easing: EASE_IN,
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        },
      )
    : 0;
  return { enter, exit, frame };
};

/** Rise + unblur on enter, sink + fade on exit. */
export const riseStyle = (
  enter: number,
  exit: number,
  dist = 60,
): React.CSSProperties => ({
  opacity: enter * (1 - exit),
  transform: `translateY(${(1 - enter) * dist + exit * -dist * 0.5}px)`,
  filter: `blur(${(1 - enter) * 12}px)`,
});

export const Backdrop: React.FC<{
  bg: Base["bg"];
  tone?: "c1" | "c0" | "c2";
}> = ({ bg, tone = "c1" }) => {
  const frame = useCurrentFrame();
  if (bg === "none") return null;
  const drift = Math.sin(frame / 90) * 40;
  return (
    <AbsoluteFill style={{ background: C[tone], overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.03) 1px,transparent 1px)",
          backgroundSize: "72px 72px",
          WebkitMaskImage:
            "radial-gradient(ellipse 80% 70% at 50% 45%,#000 25%,transparent 80%)",
        }}
      />
      <div style={glow(C.lime, 0.16, { top: -220 + drift, left: -200 })} />
      <div style={glow(C.pink, 0.14, { bottom: -240 - drift, right: -200 })} />
    </AbsoluteFill>
  );
};

const glow = (
  color: string,
  opacity: number,
  pos: React.CSSProperties,
): React.CSSProperties => ({
  position: "absolute",
  width: 640,
  height: 640,
  borderRadius: "50%",
  background: color,
  opacity,
  filter: "blur(90px)",
  ...pos,
});

/** Chrome 3D element in a corner, slowly floating, partly off the frame. Never over text. */
export const Chrome: React.FC<{
  id: string;
  corner?: "tr" | "bl" | "tl" | "br";
  size?: number;
}> = ({ id, corner = "tr", size = 420 }) => {
  const frame = useCurrentFrame();
  if (!id || !CHROME.includes(id)) return null; // only their own elements that exist in public/chrome
  const float = Math.sin(frame / 45) * 18;
  const off = -size * 0.22;
  const pos: React.CSSProperties = {
    tr: { top: SAFE.top - 120 + float, right: off },
    tl: { top: SAFE.top - 120 + float, left: off },
    br: { bottom: 380 + float, right: off },
    bl: { bottom: 380 + float, left: off },
  }[corner];
  return (
    <Img
      src={staticFile(`chrome/${id}.webp`)}
      style={{
        position: "absolute",
        width: size,
        filter: "drop-shadow(0 10px 28px rgba(0,0,0,.5))",
        ...pos,
      }}
    />
  );
};

/** "Чому реклама / *не продає*": "/" breaks lines, *word* = italic accent in the second accent colour. */
export const RichText: React.FC<{
  text: string;
  size: number;
  color?: string;
  weight?: number;
  align?: "left" | "center";
  stagger?: number; // frames between words (0 = all at once)
  delay?: number;
}> = ({
  text,
  size,
  color = C.tx,
  weight = 700,
  align = "left",
  stagger = 3,
  delay = 0,
}) => {
  const frame = useCurrentFrame();
  const { exit } = useInOut(0);
  let n = 0;
  return (
    <div style={{ textAlign: align }}>
      {text.split("/").map((line, li) => (
        <div key={li} style={{ display: "block" }}>
          {line
            .trim()
            .split(/(\*[^*]+\*)/)
            .filter(Boolean)
            .flatMap((part, pi) => {
              const accent = part.startsWith("*");
              return part
                .replace(/\*/g, "")
                .split(/\s+/)
                .filter(Boolean)
                .map((word, wi) => {
                  const i = n++;
                  const e = interpolate(
                    frame,
                    [delay + i * stagger, delay + i * stagger + 16],
                    [0, 1],
                    {
                      easing: EASE,
                      extrapolateLeft: "clamp",
                      extrapolateRight: "clamp",
                    },
                  );
                  return (
                    <span
                      key={`${pi}-${wi}`}
                      style={{
                        display: "inline-block",
                        marginRight: size * 0.24,
                        fontFamily: accent ? F.accent : F.head,
                        fontStyle: accent ? "italic" : "normal",
                        fontWeight: accent ? 300 : weight,
                        color: accent ? C.pink : color,
                        fontSize: accent ? size * 1.04 : size,
                        letterSpacing: accent ? "-0.02em" : "-0.045em",
                        lineHeight: 1.02,
                        ...riseStyle(e, exit, size * 0.5),
                      }}
                    >
                      {word}
                    </span>
                  );
                });
            })}
        </div>
      ))}
    </div>
  );
};

export const Eyebrow: React.FC<{
  text: string;
  enter: number;
  exit: number;
  size?: number;
}> = ({ text, enter, exit, size = 28 }) =>
  text ? (
    <div
      style={{
        fontFamily: F.mono,
        fontSize: size,
        letterSpacing: "0.18em",
        textTransform: "uppercase",
        color: C.lime,
        display: "flex",
        alignItems: "center",
        gap: 18,
        opacity: enter * (1 - exit),
      }}
    >
      <span style={{ width: 54 * enter, height: 2, background: C.lime }} />
      {text}
    </div>
  ) : null;

/** Lime pill button with the ink arrow circle (BRAND_INNA "Кнопка-пілюля"). */
export const PillButton: React.FC<{
  text: string;
  scale?: number;
  arrowTurn?: number;
}> = ({ text, scale = 1, arrowTurn = 0 }) => (
  <div
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 26 * scale,
      background: C.lime,
      color: C.ink,
      fontFamily: F.head,
      fontWeight: 700,
      fontSize: 46 * scale,
      padding: `${14 * scale}px ${14 * scale}px ${14 * scale}px ${48 * scale}px`,
      borderRadius: 100,
      boxShadow: "0 24px 60px -20px rgba(210,219,118,.6)",
      letterSpacing: "-0.02em",
    }}
  >
    {text}
    <span
      style={{
        width: 84 * scale,
        height: 84 * scale,
        borderRadius: "50%",
        background: C.ink,
        color: C.lime,
        display: "grid",
        placeItems: "center",
        transform: `rotate(${arrowTurn}deg)`,
      }}
    >
      <svg
        width={36 * scale}
        height={36 * scale}
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
      >
        <path d="M3 8h10M9 4l4 4-4 4" />
      </svg>
    </span>
  </div>
);

/** Content area inside the Reels safe zone. */
export const Stage: React.FC<{
  children: React.ReactNode;
  justify?: "center" | "flex-start" | "flex-end";
  gap?: number;
}> = ({ children, justify, gap = 40 }) => {
  const { width, height } = useVideoConfig();
  const { bg, place } = React.useContext(LayoutContext);
  const tall = height / width > 1.6; // 9:16 keeps off the Reels bars; 4:5 / 1:1 use the carousel margins
  justify =
    justify ??
    ({ center: "center", top: "flex-start", chest: "flex-end" }[
      place
    ] as "center");
  return (
    <AbsoluteFill
      style={{
        // over video: a soft shadow under every glyph so light text reads on any background
        filter:
          bg === "none" ? "drop-shadow(0 4px 22px rgba(0,0,0,.55))" : undefined,
        padding: tall
          ? `${SAFE.top}px ${SAFE.side + 26}px ${height - SAFE.bottom}px`
          : `72px ${SAFE.side + 26}px`,
        display: "flex",
        flexDirection: "column",
        justifyContent: justify,
        gap,
      }}
    >
      {children}
    </AbsoluteFill>
  );
};
