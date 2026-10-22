import React from "react";
import { interpolate } from "remotion";
import {
  Circle,
  Highlight,
  StrikeThrough,
  Underline,
} from "@remotion/rough-notation";
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

// Hand-drawn mark on one part of a phrase (Remotion Elements: Text Marker / Circle Marker / Strike Through).
export const markerSchema = baseSchema.extend({
  eyebrow: z.string().default(""),
  text: z.string().default("фраза з *ключовим* словом"), // *part* = what gets marked
  mode: z
    .enum(["highlight", "circle", "underline", "strike"])
    .default("highlight"),
  size: z.number().default(104),
});

export const Marker: React.FC<z.infer<typeof markerSchema>> = ({
  bg,
  chrome,
  eyebrow,
  text,
  mode,
  size,
}) => {
  const { enter, exit, frame } = useInOut(0);
  const progress = interpolate(frame, [16, 34], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const parts = text.split(/(\*[^*]+\*)/).filter(Boolean);
  const color = {
    highlight: C.lime,
    circle: C.pink,
    underline: C.lime,
    strike: C.pink,
  }[mode];
  return (
    <>
      <Backdrop bg={bg} />
      <Chrome id={chrome} corner="bl" size={340} />
      <Stage gap={34}>
        <Eyebrow text={eyebrow} enter={enter} exit={exit} />
        <div
          style={{
            fontFamily: F.head,
            fontWeight: 700,
            fontSize: size,
            lineHeight: 1.1,
            letterSpacing: "-0.045em",
            color: C.tx,
            ...riseStyle(enter, exit, 50),
          }}
        >
          {parts.map((p, i) => {
            if (!p.startsWith("*")) return <span key={i}>{p}</span>;
            const word = p.replace(/\*/g, "");
            const inner = (
              <span
                style={{
                  color: mode === "highlight" ? C.ink : C.tx,
                  position: "relative",
                  zIndex: 1,
                }}
              >
                {word}
              </span>
            );
            const common = {
              progress,
              color,
              seed: 7,
              style: { display: "inline-block" },
            };
            if (mode === "highlight")
              return (
                <Highlight
                  key={i}
                  {...common}
                  padding={{ left: 10, right: 10 }}
                >
                  {inner}
                </Highlight>
              );
            if (mode === "circle")
              return (
                <Circle
                  key={i}
                  {...common}
                  strokeWidth={6}
                  padding={{ left: 22, right: 22, top: 10, bottom: 10 }}
                >
                  {inner}
                </Circle>
              );
            if (mode === "underline")
              return (
                <Underline key={i} {...common} strokeWidth={8}>
                  {inner}
                </Underline>
              );
            return (
              <StrikeThrough key={i} {...common} strokeWidth={8}>
                {inner}
              </StrikeThrough>
            );
          })}
        </div>
      </Stage>
    </>
  );
};
