import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";
import {
  Backdrop,
  baseSchema,
  Chrome,
  Eyebrow,
  RichText,
  Stage,
  useInOut,
} from "../lib/ui";
import { C, EASE, F, R } from "../lib/brand";

// Horizontal bars (Remotion Elements: Horizontal Bar Chart), e.g. cost per lead before / after. Real numbers only.
export const barsSchema = baseSchema.extend({
  eyebrow: z.string().default(""),
  title: z.string().default("Заголовок *графіка*"),
  unit: z.string().default(""),
  bars: z
    .array(
      z.object({
        label: z.string(),
        value: z.number(),
        hi: z.boolean().default(false),
      }),
    )
    .default([
      { label: "перший", value: 40, hi: false },
      { label: "другий", value: 100, hi: true },
    ]),
});

export const Bars: React.FC<z.infer<typeof barsSchema>> = ({
  bg,
  chrome,
  eyebrow,
  title,
  unit,
  bars,
}) => {
  const frame = useCurrentFrame();
  const { enter, exit } = useInOut(0);
  const max = Math.max(...bars.map((b) => b.value), 1);
  return (
    <>
      <Backdrop bg={bg} />
      <Chrome id={chrome} corner="br" size={300} />
      <Stage gap={30}>
        <Eyebrow text={eyebrow} enter={enter} exit={exit} />
        <RichText text={title} size={84} stagger={2} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 34,
            marginTop: 20,
          }}
        >
          {bars.map((b, i) => {
            const d = 14 + i * 10;
            const g = interpolate(frame, [d, d + 26], [0, 1], {
              easing: EASE,
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            return (
              <div key={i} style={{ opacity: Math.min(1, g * 3) * (1 - exit) }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    fontFamily: F.head,
                    fontSize: 44,
                    color: C.tx2,
                    marginBottom: 14,
                  }}
                >
                  <span>{b.label}</span>
                  <span
                    style={{
                      color: b.hi ? C.lime : C.tx,
                      fontWeight: 700,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {Math.round(b.value * g)
                      .toLocaleString("uk-UA")
                      .replace(/ /g, " ")}
                    {unit}
                  </span>
                </div>
                <div
                  style={{
                    height: 64,
                    borderRadius: R.pill,
                    background: "rgba(255,255,255,.06)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      height: "100%",
                      width: `${(b.value / max) * 100 * g}%`,
                      borderRadius: R.pill,
                      background: b.hi ? C.lime : "rgba(255,195,204,.55)",
                      boxShadow: b.hi
                        ? "0 0 40px rgba(210,219,118,.4)"
                        : "none",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Stage>
    </>
  );
};
