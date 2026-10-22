import "./lib/fonts";
import React from "react";
import { CalculateMetadataFunction, Composition, Folder } from "remotion";
import { ELEMENTS } from "./elements";
import { FORMATS } from "./lib/brand";
import { Base, LayoutContext } from "./lib/ui";
import {
  calculateReelMetadata,
  MotionReel,
  motionReelSchema,
} from "./reel/MotionReel";

const FPS = 30;

// Gives each element its bg / place through context, so Stage can lay it out without every element passing them on.
const withLayout = (El: React.FC<any>): React.FC<any> => {
  const Wrapped: React.FC<any> = (p) => (
    <LayoutContext.Provider value={{ bg: p.bg, place: p.place }}>
      <El {...p} />
    </LayoutContext.Provider>
  );
  return Wrapped;
};
const WRAPPED = Object.fromEntries(
  Object.values(ELEMENTS).map((el) => [el.id, withLayout(el.component)]),
);

// Element length and frame size come from its own props (duration, format), so one CLI call can set them.
const elementMetadata: CalculateMetadataFunction<any> = ({
  props,
}: {
  props: Base;
}) => ({
  durationInFrames: Math.round(props.duration * FPS),
  ...FORMATS[props.format],
});

export const RemotionRoot: React.FC = () => (
  <>
    <Folder name="Elements">
      {Object.values(ELEMENTS).map((el) => (
        <Composition
          key={el.id}
          id={el.id}
          component={WRAPPED[el.id]}
          schema={el.schema}
          defaultProps={el.schema.parse({})}
          calculateMetadata={elementMetadata}
          fps={FPS}
          durationInFrames={90}
          width={1080}
          height={1920}
        />
      ))}
    </Folder>
    <Folder name="Reels">
      <Composition
        id="MotionReel"
        component={MotionReel}
        schema={motionReelSchema}
        defaultProps={motionReelSchema.parse({})}
        calculateMetadata={calculateReelMetadata}
        fps={FPS}
        durationInFrames={300}
        width={1080}
        height={1920}
      />
    </Folder>
  </>
);
