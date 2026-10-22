import React from "react";
import { interpolate } from "remotion";
import { z } from "zod";
import {
  Backdrop,
  baseSchema,
  Chrome,
  Eyebrow,
  riseStyle,
  Stage,
  useInOut,
} from "../lib/ui";
import { C, EASE, F } from "../lib/brand";

// A real number only (CLAUDE.md: numbers are real). The value is what she says, as she says it.
export const counterSchema = baseSchema.extend({
  eyebrow: z.string().default(""),
  value: z.number().default(100),
  from: z.number().default(0),
  decimals: z.number().int().min(0).max(2).default(0),
  prefix: z.string().default(""), // "$", "+"
  suffix: z.string().default(""), // "%", " грн", "x"
  label: z.string().default("підпис до цифри"),
  seconds: z.number().default(1.4), // how long the count runs
});

const fmt = (n: number, d: number) =>
  n
    .toLocaleString("uk-UA", {
      minimumFractionDigits: d,
      maximumFractionDigits: d,
    })
    .replace(/ /g, " ");

export const Counter: React.FC<z.infer<typeof counterSchema>> = ({
  bg,
  chrome,
  eyebrow,
  value,
  from,
  decimals,
  prefix,
  suffix,
  label,
  seconds,
}) => {
  const { enter, exit, frame } = useInOut(0);
  const labelIn = useInOut(10).enter;
  const t = interpolate(frame, [6, 6 + seconds * 30], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const done = interpolate(
    frame,
    [6 + seconds * 30, 12 + seconds * 30],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const n = from + (value - from) * t;
  return (
    <>
      <Backdrop bg={bg} />
      <Chrome id={chrome} corner="br" size={360} />
      <Stage gap={24}>
        <Eyebrow text={eyebrow} enter={enter} exit={exit} />
        <div
          style={{
            fontFamily: F.head,
            fontWeight: 700,
            fontSize: 260,
            lineHeight: 0.9,
            letterSpacing: "-0.06em",
            color: C.lime,
            fontVariantNumeric: "tabular-nums",
            textShadow: `0 0 ${60 * done}px rgba(210,219,118,.45)`,
            transform: `scale(${1 + done * 0.04 - Math.max(0, done - 0.5) * 0.08})`,
            transformOrigin: "left center",
            ...riseStyle(enter, exit, 80),
          }}
        >
          {prefix}
          {fmt(n, decimals)}
          {suffix}
        </div>
        <div
          style={{
            fontFamily: F.head,
            fontWeight: 400,
            fontSize: 52,
            color: C.tx,
            ...riseStyle(labelIn, exit, 30),
          }}
        >
          {label}
        </div>
      </Stage>
    </>
  );
};
