import React from "react";
import { interpolate } from "remotion";
import { z } from "zod";
import {
  Backdrop,
  baseSchema,
  Chrome,
  riseStyle,
  Stage,
  useInOut,
} from "../lib/ui";
import { C, EASE, F, R } from "../lib/brand";

// «було → стало»: the pain gets struck through in pink (BRAND_INNA rule), the result lands in lime.
export const beforeAfterSchema = baseSchema.extend({
  beforeLabel: z.string().default("було"),
  before: z.string().default("як було"),
  afterLabel: z.string().default("стало"),
  after: z.string().default("як стало"),
});

export const BeforeAfter: React.FC<z.infer<typeof beforeAfterSchema>> = ({
  bg,
  chrome,
  beforeLabel,
  before,
  afterLabel,
  after,
}) => {
  const { enter, exit, frame } = useInOut(0);
  const strike = interpolate(frame, [16, 28], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const afterIn = interpolate(frame, [26, 44], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const card = (label: string, text: string, good: boolean, e: number) => (
    <div
      style={{
        padding: "40px 44px",
        borderRadius: R.glass,
        border: `1px solid ${good ? "rgba(210,219,118,.45)" : C.bd2}`,
        background: good
          ? "linear-gradient(180deg,rgba(210,219,118,.14),rgba(210,219,118,.04))"
          : bg === "none"
            ? "rgba(7,12,7,.72)"
            : `linear-gradient(180deg,${C.c3},${C.c2})`,
        ...riseStyle(e, exit, 60),
      }}
    >
      <div
        style={{
          fontFamily: F.mono,
          fontSize: 28,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: good ? C.lime : C.pink,
          marginBottom: 18,
        }}
      >
        {label}
      </div>
      <div
        style={{
          position: "relative",
          display: "inline-block",
          fontFamily: F.head,
          fontWeight: good ? 700 : 400,
          fontSize: 64,
          lineHeight: 1.1,
          letterSpacing: "-0.03em",
          color: good ? C.tx : C.tx2,
        }}
      >
        {text}
        {!good ? (
          <span
            style={{
              position: "absolute",
              left: -6,
              top: "52%",
              height: 7,
              borderRadius: 4,
              background: C.pink,
              width: `calc(${strike * 100}% + 12px)`,
            }}
          />
        ) : null}
      </div>
    </div>
  );
  return (
    <>
      <Backdrop bg={bg} />
      <Chrome id={chrome} corner="tr" size={320} />
      <Stage gap={26}>
        {card(beforeLabel, before, false, enter)}
        <div
          style={{
            alignSelf: "center",
            fontFamily: F.head,
            fontSize: 70,
            color: C.lime,
            opacity: afterIn * (1 - exit),
            transform: `translateY(${(1 - afterIn) * -20}px) rotate(90deg)`,
          }}
        >
          →
        </div>
        {card(afterLabel, after, true, afterIn)}
      </Stage>
    </>
  );
};
