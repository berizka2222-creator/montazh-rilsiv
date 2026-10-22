// Must run before anything calls staticFile(): fonts and chrome load from the motion-assets folder next to this script.
const me = document.currentScript as HTMLScriptElement | null;
(window as unknown as { remotion_staticBase: string }).remotion_staticBase = me
  ? new URL(me.src).pathname.replace(/\/[^/]*$/, "") // a path on the same site, as staticFile() expects
  : "/motion-assets";
export {};
