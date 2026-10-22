import React from "react";
import { interpolate, spring, useVideoConfig } from "remotion";
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
import { PillButton } from "../lib/ui";
import { C, F } from "../lib/brand";

// End screen. The button says an action («Записатися в анкету», «Забрати подарунки»): the text is hers, never invented.
export const ctaEndSchema = baseSchema.extend({
  eyebrow: z.string().default(""),
  title: z.string().default("Заклик *до дії*"),
  button: z.string().default("Текст кнопки"),
  note: z.string().default(""), // e.g. «Напиши АНКЕТА в коментарях»
});

export const CtaEnd: React.FC<z.infer<typeof ctaEndSchema>> = ({
  bg,
  chrome,
  eyebrow,
  title,
  button,
  note,
}) => {
  const { fps } = useVideoConfig();
  const { enter, exit, frame } = useInOut(0);
  const pop = spring({
    frame: frame - 18,
    fps,
    config: { damping: 12, stiffness: 140 },
  });
  const turn = interpolate(frame, [40, 52], [0, -45], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <>
      <Backdrop bg={bg} tone="c0" />
      <Chrome id={chrome} corner="tr" />
      <Stage gap={48}>
        <Eyebrow text={eyebrow} enter={enter} exit={exit} />
        <RichText text={title} size={110} stagger={3} />
        <div
          style={{
            transform: `scale(${pop})`,
            transformOrigin: "left center",
            opacity: 1 - exit,
          }}
        >
          <PillButton text={button} arrowTurn={turn} />
        </div>
        {note ? (
          <div
            style={{
              fontFamily: F.accent,
              fontStyle: "italic",
              fontWeight: 300,
              fontSize: 46,
              color: C.pink,
              opacity: pop * (1 - exit),
            }}
          >
            {note}
          </div>
        ) : null}
      </Stage>
    </>
  );
};
