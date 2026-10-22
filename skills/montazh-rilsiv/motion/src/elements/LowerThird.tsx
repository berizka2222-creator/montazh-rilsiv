import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { z } from "zod";
import { Backdrop, baseSchema, useInOut } from "../lib/ui";
import { C, EASE, F, R } from "../lib/brand";
import G from "../lib/brand.generated.json";

// Name plate (Remotion Elements: Name Lower Third). Sits on the chest band, off the face, inside the safe zone.
export const lowerThirdSchema = baseSchema.extend({
  name: z.string().default(G.name || "Ім'я"),
  role: z.string().default("роль"),
  handle: z.string().default(G.handle || "@nickname"),
  y: z.number().default(1180), // top of the plate on the 1080x1920 frame
});

export const LowerThird: React.FC<z.infer<typeof lowerThirdSchema>> = ({
  bg,
  name,
  role,
  handle,
  y,
}) => {
  const { enter, exit, frame } = useInOut(0, 20);
  const line = interpolate(frame, [4, 22], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const text = interpolate(frame, [10, 28], [0, 1], {
    easing: EASE,
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <>
      <Backdrop bg={bg} />
      <AbsoluteFill>
        <div
          style={{
            position: "absolute",
            left: 90,
            top: y,
            padding: "30px 44px 34px 40px",
            borderRadius: R.glass,
            background:
              "linear-gradient(180deg,rgba(13,26,15,.86),rgba(7,12,7,.86))",
            border: `1px solid ${C.bd2}`,
            backdropFilter: "blur(18px)",
            clipPath: `inset(0 ${(1 - enter) * 100}% 0 0 round ${R.glass}px)`,
            opacity: 1 - exit,
            transform: `translateX(${exit * -60}px)`,
            display: "flex",
            gap: 26,
          }}
        >
          <div
            style={{
              width: 6,
              borderRadius: 3,
              background: C.lime,
              transform: `scaleY(${line})`,
              transformOrigin: "top",
            }}
          />
          <div
            style={{
              opacity: text,
              transform: `translateY(${(1 - text) * 16}px)`,
            }}
          >
            <div
              style={{
                fontFamily: F.head,
                fontWeight: 700,
                fontSize: 58,
                color: C.tx,
                letterSpacing: "-0.03em",
              }}
            >
              {name}
            </div>
            <div
              style={{
                fontFamily: F.accent,
                fontStyle: "italic",
                fontWeight: 300,
                fontSize: 42,
                color: C.pink,
                marginTop: 4,
              }}
            >
              {role}
            </div>
            {handle ? (
              <div
                style={{
                  fontFamily: F.mono,
                  fontSize: 24,
                  letterSpacing: "0.14em",
                  color: C.lime,
                  marginTop: 14,
                  textTransform: "uppercase",
                }}
              >
                {handle}
              </div>
            ) : null}
          </div>
        </div>
      </AbsoluteFill>
    </>
  );
};
