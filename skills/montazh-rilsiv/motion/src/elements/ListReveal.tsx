import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";
import {
  Backdrop,
  baseSchema,
  Chrome,
  Eyebrow,
  RichText,
  riseStyle,
  Stage,
  useInOut,
} from "../lib/ui";
import { C, EASE, F, R } from "../lib/brand";

// Carousel-row look from BRAND_INNA: 01/02 in mono lime, rounded bordered rows. No bullets.
export const listRevealSchema = baseSchema.extend({
  eyebrow: z.string().default(""),
  title: z.string().default("Заголовок *списку*"),
  rows: z
    .array(z.string())
    .default(["перший пункт", "другий пункт", "третій пункт"]),
  rowGap: z.number().default(14), // frames between rows (match her speech: 1 row per spoken item)
  check: z.boolean().default(false), // tick each row after it lands
});

export const ListReveal: React.FC<z.infer<typeof listRevealSchema>> = ({
  bg,
  chrome,
  eyebrow,
  title,
  rows,
  rowGap,
  check,
}) => {
  const frame = useCurrentFrame();
  const { enter, exit } = useInOut(0);
  const start = 14;
  return (
    <>
      <Backdrop bg={bg} />
      <Chrome id={chrome} corner="tr" size={340} />
      <Stage gap={30}>
        <Eyebrow text={eyebrow} enter={enter} exit={exit} />
        <RichText text={title} size={88} stagger={2} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 18,
            marginTop: 10,
          }}
        >
          {rows.map((r, i) => {
            const d = start + i * rowGap;
            const e = interpolate(frame, [d, d + 16], [0, 1], {
              easing: EASE,
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const tick = interpolate(frame, [d + 14, d + 24], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 30,
                  padding: "34px 38px",
                  borderRadius: R.glass,
                  border: `1px solid ${C.bd2}`,
                  background:
                    bg === "none"
                      ? "rgba(7,12,7,.72)"
                      : `linear-gradient(180deg,${C.c3},${C.c2})`,
                  backdropFilter: bg === "none" ? "blur(18px)" : undefined,
                  ...riseStyle(e, exit, 50),
                  transform: `translateX(${(1 - e) * -80}px)`,
                }}
              >
                <span
                  style={{
                    fontFamily: F.mono,
                    fontSize: 30,
                    color: C.lime,
                    letterSpacing: "0.08em",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span
                  style={{
                    fontFamily: F.head,
                    fontWeight: 400,
                    fontSize: 48,
                    color: C.tx,
                    flex: 1,
                    lineHeight: 1.15,
                  }}
                >
                  {r}
                </span>
                {check ? (
                  <span
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: "50%",
                      background: C.lime,
                      color: C.ink,
                      display: "grid",
                      placeItems: "center",
                      transform: `scale(${tick})`,
                    }}
                  >
                    <svg
                      width="28"
                      height="28"
                      viewBox="0 0 16 16"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.4"
                    >
                      <path
                        d="M3 8.5l3.2 3L13 4.5"
                        strokeDasharray="16"
                        strokeDashoffset={16 * (1 - tick)}
                      />
                    </svg>
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </Stage>
    </>
  );
};
