import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { z } from "zod";
import { Backdrop, baseSchema, Chrome, Stage, useInOut } from "../lib/ui";
import { C, EASE, F } from "../lib/brand";

// DM / chat bubbles (Remotion Elements: On-Screen Messages). Only real messages she shows (screens from clients
// are real, never made up): CLAUDE.md, reviews and cases are never invented.
export const chatSchema = baseSchema.extend({
  title: z.string().default(""), // e.g. the chat name shown on top
  messages: z
    .array(z.object({ from: z.enum(["them", "me"]), text: z.string() }))
    .default([
      { from: "them", text: "повідомлення співрозмовника" },
      { from: "me", text: "твоя відповідь" },
    ]),
  gap: z.number().default(26), // frames between messages
});

const Dots: React.FC<{ frame: number }> = ({ frame }) => (
  <span style={{ display: "inline-flex", gap: 10 }}>
    {[0, 1, 2].map((i) => (
      <span
        key={i}
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: C.tx2,
          opacity: 0.4 + 0.6 * Math.abs(Math.sin((frame + i * 5) / 6)),
        }}
      />
    ))}
  </span>
);

export const Chat: React.FC<z.infer<typeof chatSchema>> = ({
  bg,
  chrome,
  title,
  messages,
  gap,
}) => {
  const frame = useCurrentFrame();
  const { enter, exit } = useInOut(0);
  return (
    <>
      <Backdrop bg={bg} />
      <Chrome id={chrome} corner="tl" size={300} />
      <Stage gap={22}>
        {title ? (
          <div
            style={{
              alignSelf: "center",
              fontFamily: F.mono,
              fontSize: 26,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: C.tx3,
              opacity: enter * (1 - exit),
            }}
          >
            {title}
          </div>
        ) : null}
        {messages.map((m, i) => {
          const at = 8 + i * gap;
          const typing = m.from === "them" && frame >= at - 14 && frame < at;
          const e = interpolate(frame, [at, at + 12], [0, 1], {
            easing: EASE,
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const me = m.from === "me";
          if (e === 0 && !typing) return null;
          return (
            <div
              key={i}
              style={{
                alignSelf: me ? "flex-end" : "flex-start",
                maxWidth: "82%",
                padding: "28px 36px",
                borderRadius: 40,
                borderBottomRightRadius: me ? 12 : 40,
                borderBottomLeftRadius: me ? 40 : 12,
                background: me ? C.lime : "rgba(255,255,255,.1)",
                backdropFilter: "blur(18px)",
                border: me ? "none" : `1px solid ${C.bd2}`,
                color: me ? C.ink : C.tx,
                fontFamily: F.head,
                fontWeight: me ? 700 : 400,
                fontSize: 46,
                lineHeight: 1.2,
                opacity: (typing ? 1 : e) * (1 - exit),
                transform: `scale(${typing ? 1 : 0.85 + 0.15 * e})`,
                transformOrigin: me ? "right bottom" : "left bottom",
              }}
            >
              {typing ? <Dots frame={frame} /> : m.text}
            </div>
          );
        })}
      </Stage>
    </>
  );
};
