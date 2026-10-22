import React from "react";
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
import { C, F } from "../lib/brand";

export const hookTitleSchema = baseSchema.extend({
  eyebrow: z.string().default(""),
  text: z.string().default("Текст хука / *акцент*"), // "/" = new line, *word* = pink italic accent
  sub: z.string().default(""), // pink italic subtitle under the title
  size: z.number().min(60).max(180).default(124),
});

export const HookTitle: React.FC<z.infer<typeof hookTitleSchema>> = ({
  bg,
  chrome,
  eyebrow,
  text,
  sub,
  size,
}) => {
  const { enter, exit } = useInOut(0);
  const subIn = useInOut(14).enter;
  return (
    <>
      <Backdrop bg={bg} tone="c0" />
      <Chrome id={chrome} corner="tr" />
      <Stage gap={36}>
        <Eyebrow text={eyebrow} enter={enter} exit={exit} />
        <RichText text={text} size={size} stagger={3} delay={4} />
        {sub ? (
          <div
            style={{
              fontFamily: F.accent,
              fontStyle: "italic",
              fontWeight: 300,
              fontSize: size * 0.38,
              color: C.pink,
              opacity: subIn * (1 - exit),
            }}
          >
            {sub}
          </div>
        ) : null}
      </Stage>
    </>
  );
};
