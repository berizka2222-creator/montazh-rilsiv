// Brand motion on a website (Remotion Player). One script, drop-in for static sites (Netlify):
//   <div data-motion="CtaEnd" data-props='{"title":"...","button":"..."}' data-loop data-autoplay></div>
//   <script src="/motion-assets/motion-embed.js"></script>
// data-url-props="name:title,city:sub" puts URL params into props (?name=Олена → title), for personalised video.
// data-play="view" starts it when it scrolls into view. data-controls shows the player controls.
import "./base";
import "../lib/fonts";
import React from "react";
import { createRoot } from "react-dom/client";
import { Player, PlayerRef } from "@remotion/player";
import { ELEMENTS } from "../elements";
import { FORMATS } from "../lib/brand";
import { LayoutContext } from "../lib/ui";
import { MotionReel, motionReelSchema } from "../reel/MotionReel";

const FPS = 30;

type Resolved = {
  component: React.FC<any>;
  props: any;
  frames: number;
  size: { width: number; height: number };
};

const resolve = (id: string, raw: Record<string, unknown>): Resolved => {
  if (id === "MotionReel") {
    const props = motionReelSchema.parse(raw);
    const total = props.scenes.reduce(
      (s, sc) => s + Math.round(sc.seconds * props.fps),
      0,
    );
    const overlaps = props.scenes
      .slice(0, -1)
      .filter((sc) => (sc.transition || props.transition) !== "cut").length;
    return {
      component: MotionReel,
      props,
      frames: total - overlaps * props.transitionFrames,
      size: FORMATS[props.format],
    };
  }
  const el = Object.values(ELEMENTS).find((e) => e.id === id);
  if (!el) throw new Error(`motion-embed: no element "${id}"`);
  const props = el.schema.parse(raw) as { duration: number; format: string };
  const El = el.component;
  const component: React.FC<any> = (p) => (
    <LayoutContext.Provider value={{ bg: p.bg, place: p.place }}>
      <El {...p} />
    </LayoutContext.Provider>
  );
  return {
    component,
    props,
    frames: Math.round(props.duration * FPS),
    size: FORMATS[props.format as keyof typeof FORMATS],
  };
};

const Embed: React.FC<{ node: HTMLElement }> = ({ node }) => {
  const ref = React.useRef<PlayerRef>(null);
  const raw = JSON.parse(node.dataset.props || "{}");
  const q = new URLSearchParams(location.search);
  for (const pair of (node.dataset.urlProps || "").split(",").filter(Boolean)) {
    const [param, prop] = pair.split(":");
    if (q.get(param)) raw[prop] = q.get(param);
  }
  const { component, props, frames, size } = resolve(
    node.dataset.motion || "",
    raw,
  );
  React.useEffect(() => {
    if (node.dataset.play !== "view") return;
    const io = new IntersectionObserver(
      ([e]) => (e.isIntersecting ? ref.current?.play() : ref.current?.pause()),
      {
        threshold: 0.5,
      },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [node]);
  return (
    <Player
      ref={ref}
      component={component}
      inputProps={props}
      durationInFrames={Math.max(1, frames)}
      fps={FPS}
      compositionWidth={size.width}
      compositionHeight={size.height}
      loop={"loop" in node.dataset}
      autoPlay={"autoplay" in node.dataset}
      controls={"controls" in node.dataset}
      acknowledgeRemotionLicense
      style={{
        width: "100%",
        borderRadius: node.dataset.radius ? Number(node.dataset.radius) : 28,
        overflow: "hidden",
      }}
    />
  );
};

document
  .querySelectorAll<HTMLElement>("[data-motion]")
  .forEach((node) => createRoot(node).render(<Embed node={node} />));
