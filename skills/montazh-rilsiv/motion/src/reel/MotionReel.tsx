// A whole motion-design video from a scene list (JSON). This is the "ролик" format: scenes from the element library,
// brand transitions between them, optional voice-over and music from public/.
import React from "react";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  interpolate,
  staticFile,
  useVideoConfig,
} from "remotion";
import { Audio } from "@remotion/media";
import {
  linearTiming,
  TransitionPresentation,
  TransitionSeries,
} from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import { slide } from "@remotion/transitions/slide";
import { wipe } from "@remotion/transitions/wipe";
import { z } from "zod";
import { ELEMENTS, ElementKey } from "../elements";
import { C, FORMATS } from "../lib/brand";
import { ExitContext } from "../lib/ui";

const keys = Object.keys(ELEMENTS) as [ElementKey, ...ElementKey[]];

export const motionReelSchema = z.object({
  format: z.enum(["9:16", "4:5", "1:1", "16:9"]).default("9:16"),
  fps: z.number().default(30),
  transition: z.enum(["fade", "slide", "wipe", "cut"]).default("slide"),
  transitionFrames: z.number().default(12),
  voice: z.string().default(""), // file in public/, e.g. "audio/voice.mp3"
  music: z.string().default(""), // file in public/, plays quietly under the voice
  musicVolume: z.number().default(0.12),
  scenes: z
    .array(
      z.object({
        type: z.enum(keys),
        seconds: z.number().min(0.5),
        transition: z.enum(["fade", "slide", "wipe", "cut", ""]).default(""), // into the NEXT scene; "" = reel default
        props: z.record(z.string(), z.any()).default({}),
      }),
    )
    .default([
      { type: "hook", seconds: 3, transition: "", props: {} },
      { type: "counter", seconds: 3, transition: "", props: {} },
      { type: "cta", seconds: 3.5, transition: "", props: {} },
    ]),
});
export type MotionReelProps = z.infer<typeof motionReelSchema>;

const presentation = (t: string): TransitionPresentation<any> =>
  (t === "fade"
    ? fade()
    : t === "wipe"
      ? wipe({ direction: "from-bottom-left" })
      : slide({ direction: "from-bottom" })) as TransitionPresentation<any>;

export const calculateReelMetadata: CalculateMetadataFunction<
  MotionReelProps
> = ({ props }) => {
  const fps = props.fps;
  const total = props.scenes.reduce(
    (s, sc) => s + Math.round(sc.seconds * fps),
    0,
  );
  const overlaps = props.scenes
    .slice(0, -1)
    .filter((sc) => (sc.transition || props.transition) !== "cut").length;
  return {
    fps,
    durationInFrames: Math.max(1, total - overlaps * props.transitionFrames),
    ...FORMATS[props.format],
  };
};

export const MotionReel: React.FC<MotionReelProps> = ({
  scenes,
  transition,
  transitionFrames,
  voice,
  music,
  musicVolume,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: C.c1 }}>
      <ExitContext.Provider value={false}>
        <TransitionSeries>
          {scenes.flatMap((sc, i) => {
            const el = ELEMENTS[sc.type];
            const Comp = el.component;
            const props = el.schema.parse({ ...sc.props, bg: "brand" });
            const t = sc.transition || transition;
            const out = [
              <TransitionSeries.Sequence
                key={`s${i}`}
                durationInFrames={Math.round(sc.seconds * fps)}
              >
                <Comp {...props} />
              </TransitionSeries.Sequence>,
            ];
            if (i < scenes.length - 1 && t !== "cut")
              out.push(
                <TransitionSeries.Transition
                  key={`t${i}`}
                  presentation={presentation(t)}
                  timing={linearTiming({ durationInFrames: transitionFrames })}
                />,
              );
            return out;
          })}
        </TransitionSeries>
      </ExitContext.Provider>
      {voice ? <Audio src={staticFile(voice)} /> : null}
      {music ? (
        <Audio
          src={staticFile(music)}
          volume={(f) =>
            musicVolume *
            interpolate(
              f,
              [0, 15, durationInFrames - 30, durationInFrames],
              [0, 1, 1, 0],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              },
            )
          }
        />
      ) : null}
    </AbsoluteFill>
  );
};
