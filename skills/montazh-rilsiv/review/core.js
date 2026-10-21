// Reel review core: turns review decisions into the cut timeline. The review page and the render bridge
// (scripts/review_sync.py, which runs this same file with node) both use it, so what you approve is what renders.
// Times: "src" = seconds in the raw clip; "cut" = seconds in the finished reel (after cuts and speed-up).
(function (root) {
  function autoPx(text, place) {   // an added text's size from its frame: as tall as the frame allows, but never wider than it
    const lines = String(text || "").split("/").map(x => x.trim()).filter(Boolean), n = Math.max(1, lines.length);
    const longest = Math.max(1, ...lines.map(x => x.length));
    return Math.max(24, Math.round(Math.min(place[3] / n / 0.9, place[2] / (longest * 0.62))));
  }

  // defaults (tight pacing) when a reel has no pacing: pause = gap between kept words over 0.25 s, 0.06 s air at every edit

  // decisions: {cut: [wordIdx...], restoredFillers: [wordIdx...], restoredPauses: [wordIdx...]}
  // A pause is keyed by the index of the word BEFORE it.
  function plan(reel, d) {
    const PAUSE = (reel.pacing || {}).pause_min ?? 0.25, PAD = (reel.pacing || {}).air ?? 0.06;   // from brand pacing
    const W = reel.words, cut = new Set(d.cut || []);
    const fillerBack = new Set(d.restoredFillers || []), pauseBack = new Set(d.restoredPauses || []);
    const removed = i => cut.has(i) || (W[i].filler && !fillerBack.has(i));
    const kept = []; for (let i = 0; i < W.length; i++) if (!removed(i)) kept.push(i);
    const spans = [], pauses = [];
    let a = null;
    for (let k = 0; k < kept.length; k++) {
      const i = kept[k], w = W[i];
      if (a === null) a = Math.max(0, w.s - PAD);
      const j = kept[k + 1];
      if (j === undefined) { spans.push([a, Math.min(reel.srcDur, w.e + 0.1)]); break; }
      const nxt = W[j], gap = nxt.s - w.e, adjacent = j === i + 1;
      const isPause = adjacent && gap > PAUSE;
      if (isPause) pauses.push({ after: i, s: w.e, e: nxt.s, len: gap, kept: pauseBack.has(i) || (reel.keepPauses || []).includes(i) && !(d.trimmedPauses || []).includes(i) });
      const pauseKept = isPause && pauses[pauses.length - 1].kept;
      if (!adjacent || (isPause && !pauseKept)) { spans.push([a, w.e + PAD]); a = Math.max(w.e + PAD, nxt.s - PAD); }
    }
    // cut-timeline map (speed applied)
    const speed = reel.speed || 1.1, starts = []; let acc = 0;
    for (const [s, e] of spans) { starts.push(acc); acc += (e - s) / speed; }
    const cutDur = acc;
    function toCut(t) {   // source time -> cut time; a time inside a removed stretch snaps to the next kept moment
      for (let k = 0; k < spans.length; k++) {
        const [s, e] = spans[k];
        if (t < s) return starts[k];
        if (t <= e) return starts[k] + (t - s) / speed;
      }
      return cutDur;
    }
    function toSrc(c) {   // cut time -> source time (for rough-cut playback seeking)
      for (let k = 0; k < spans.length; k++) {
        const len = (spans[k][1] - spans[k][0]) / speed;
        if (c <= starts[k] + len) return spans[k][0] + (c - starts[k]) * speed;
      }
      return spans.length ? spans[spans.length - 1][1] : 0;
    }
    return { spans, pauses, kept, removed, toCut, toSrc, cutDur, speed };
  }

  // captions: [{w:[idx...], acc:[idx...], text?:"override", nudge?:sec}] in source words -> cut-time captions
  function captions(reel, d, P) {
    const caps = d.captions || reel.captions, out = [];
    caps.forEach((c, ci) => {
      const live = c.w.filter(i => !P.removed(i));
      if (!live.length) { out.push({ ci, gone: true }); return; }
      const t0 = P.toCut(reel.words[live[0]].s) + (c.nudge || 0);
      const last = reel.words[live[live.length - 1]];
      let words;
      if (c.text) {   // reworded: spread the new words across the caption's span
        const toks = c.text.split(/\s+/).filter(Boolean), span = Math.max(P.toCut(last.e) - t0, 0.12);
        words = toks.map((t, k) => ({ text: t, t: t0 + span * k / toks.length, accent: (c.accText || []).includes(k) }));
      } else words = live.map(i => ({ text: reel.words[i].text, t: Math.max(t0, P.toCut(reel.words[i].s)), accent: (c.acc || []).includes(i), i }));
      out.push({ ci, start: t0, end: P.toCut(last.e) + 0.2, words });
    });
    // overlaps and boundaries: each caption ends where the next begins; never shorter than 0.12 s; clamp to the reel
    const live = out.filter(c => !c.gone).sort((a, b) => a.start - b.start);
    for (let k = 0; k < live.length; k++) {
      const c = live[k], n = live[k + 1];
      c.start = Math.max(0, Math.min(c.start, P.cutDur - 0.12));
      if (n) c.end = Math.min(c.end, Math.max(n.start, c.start + 0.12));
      c.end = Math.min(Math.max(c.end, c.start + 0.12), P.cutDur);
      if (n && n.start < c.start + 0.12) { n.start = c.start + 0.12; c.overlapFixed = true; }
    }
    return out;
  }

  // where an uploaded overlay sits on the 1080x1920 frame, per size choice (build_reel.py uses the same boxes)
  const OVERLAY_PLACE = { full: [0, 0, 1080, 1920], big: [90, 150, 900, 640], box: [90, 150, 900, 640],
                          "small-r": [600, 170, 400, 500], "small-l": [80, 170, 400, 500], tiny: [760, 260, 200, 200] };

  // graphics anchored to source words -> cut-time windows; a card ends with its phrase unless endWord is set
  function graphics(reel, d, P) {
    const W = reel.words, firstKeptFrom = i => { for (let k = i; k < W.length; k++) if (!P.removed(k)) return k; return null; };
    const out = reel.board.map(g => {
      const state = ((d.board || {})[g.id] || {}).state || "k";
      const a = firstKeptFrom(g.w0);
      if (a === null) return { ...g, state, gone: true };
      let endSrc;
      if (g.w1 != null && !P.removed(g.w1)) endSrc = W[g.w1].e;
      else { let k = a; while (k < W.length - 1 && !/[.,!?;:]$/.test(W[k].text) && W[k + 1].s - W[k].e < 0.35 && P.toCut(W[k].e) - P.toCut(W[a].s) < 4) k++; endSrc = W[k].e; }
      const minDur = g.type === "block" ? 2.2 : ["card", "list", "split", "steps"].includes(g.type) ? 2.5 : g.type === "push" ? 2 : g.type === "follow" ? 2.5 : 1;   // long enough to read past the entrance animation
      const start = P.toCut(W[a].s), end = Math.max(start + minDur, P.toCut(endSrc) + 0.15);
      return { ...g, state, start, end: Math.min(end, P.cutDur), moved: a !== g.w0 };
    }).concat((d.overlays || []).map(o => {   // overlays they added on the page: an uploaded image/video (or big text) from a word, for o.dur seconds
      const state = ((d.board || {})[o.id] || {}).state || "k", a = firstKeptFrom(o.w0);
      const place = o.place || OVERLAY_PLACE[o.mode] || OVERLAY_PLACE.big, lines = (o.text || "").split("/").filter(x => x.trim()).length || 1;
      const g = o.kind === "text"
        ? { id: o.id, type: "bigtext", kind: o.behind ? "Текст за тобою" : "Текст", what: o.text, text: o.text, y: place[1], size: (o.look || {}).px || autoPx(o.text, place),
            look: o.look && Object.keys(o.look).length ? o.look : undefined,
            behind: !!o.behind, place, w0: o.w0, user: true }
        : { id: o.id, type: "overlay", kind: o.behind ? "Накладення за тобою" : "Накладення", what: o.name, mode: o.mode, effect: o.effect || "soft", media: o.kind, assetId: o.assetId,
            place, box: o.place || undefined, imgUrl: o.kind === "image" ? o.url : null, behind: !!o.behind, w0: o.w0, user: true };
      if (a === null) return { ...g, state, gone: true };
      const start = P.toCut(W[a].s);
      return { ...g, state, start, end: Math.min(start + (o.dur || 3), P.cutDur), moved: a !== o.w0 };
    }));
    // the hook text and the CTA they typed on the page (their words, so they count as theirs)
    if ((d.hook || "").trim()) for (const g of out) if (g.type === "title") Object.assign(g, { text: d.hook.trim(), what: d.hook.replace(/\s*\/\s*/g, " ").trim(), own: true });
    for (const g of out) if (g.type === "title" && !g.gone) g.end = Math.min(Math.max(g.end, g.start + 3.5), P.cutDur);   // a hook needs ~3.5 s to be read
    for (const g of out) { const b = (d.board || {})[g.id]; if (b && typeof b.behind === "boolean") g.behind = b.behind; }   // «За мною» toggled on the page
    layout(reel, d, out);
    if (((d.cta || {}).text || "").trim()) {
      const dur = Math.min(d.cta.dur || 4, P.cutDur);
      out.push({ id: "cta", type: "cta", kind: "Заклик (CTA)", what: d.cta.text.trim(), text: d.cta.text.trim(), own: true,
                 state: ((d.board || {}).cta || {}).state || "k", place: [90, 1300, 900, 170], start: P.cutDur - dur, end: P.cutDur });
    }
    return out;
  }

  // keep graphics off the face and off the captions: reel.face = [x,y,w,h] (scripts/face_box.py), captions at capY.
  // A box that hits either moves below the face, or above it, inside the frame Instagram leaves clear (top 200, bottom ~280).
  // Full-screen cards, graphics behind the person and their own dragged overlays stay where they are.
  const TOP_SAFE = 200, BOTTOM_SAFE = 1640, CAP_H = 170, GAP = 30;
  function capY(reel, d) { return d.capY != null ? d.capY : ((reel.style || {}).capY ?? 1250); }
  function layout(reel, d, out) {
    const F = reel.face; if (!F) return;
    const cy = capY(reel, d), zones = [[F[1] - 20, F[1] + F[3] + 20], [cy - 10, cy + CAP_H]];
    const hits = (y, h) => zones.some(([a, b]) => y < b && a < y + h);
    for (const g of out) {
      const p = g.place; if (!p || g.gone || (g.user && g.box) || (p[2] >= 1000 && p[3] >= 1800)) continue;
      if (g.behind) {   // behind the person only shows where the background is: above the head, tucked a little behind the hair
        const tuck = g.type === "bigtext" || g.type === "title" ? 0.35 : 0.08;   // big words may hide behind the hair; lists and cards stay readable
        let h = p[3], w = p[2], x = p[0], y = Math.round(F[1] - h * (1 - tuck));
        if (y < TOP_SAFE) {   // too tall for the space above the head: shrink it to fit, centred where it was
          const z = Math.max(0.55, (F[1] - TOP_SAFE) / (h * (1 - tuck)));
          const w2 = Math.round(w * z), h2 = Math.round(h * z); x = Math.round(x + (w - w2) / 2); w = w2; h = h2; y = TOP_SAFE; g.zoom = +z.toFixed(3);
        }
        if (y !== p[1] || g.zoom) { g.place = [x, y, w, h]; g.shifted = true; }
        continue;
      }
      if (!hits(p[1], p[3])) continue;
      const h = p[3], tries = [F[1] + F[3] + GAP, cy + CAP_H + GAP, F[1] - h - GAP, cy - h - GAP];
      let y = tries.find(t => t >= TOP_SAFE && t + h <= BOTTOM_SAFE && !hits(t, h));
      let aside = false;
      if (y == null) { y = Math.min(Math.max(F[1] + F[3] + GAP, TOP_SAFE), BOTTOM_SAFE - h); aside = true; }   // no clean spot: under the chin, and the captions step aside while it shows
      g.place = [p[0], Math.round(y), p[2], h]; g.shifted = true; if (aside) g.capsAside = true;
    }
  }

  // captions make room for a graphic behind the person: while one shows above the head, captions there drop under the chin
  function capsAround(reel, d, caps, gfx) {
    const F = reel.face; if (!F) return caps;
    const cy = capY(reel, d), alt = F[1] + F[3] + 20;
    for (const c of caps) {
      if (c.gone) continue;
      const hit = gfx.some(g => g.behind && !g.gone && g.state !== "d" && g.place && c.start < g.end && g.start < c.end &&
        cy < g.place[1] + g.place[3] && g.place[1] < cy + CAP_H);
      if (hit) c.y = alt; else delete c.y;
    }
    return caps;
  }

  // a fingerprint of everything that changes the render, to tell whether a built preview is outdated
  function hash(d) {
    const s = JSON.stringify([d.cut, d.restoredFillers, d.restoredPauses, d.trimmedPauses, d.captions, d.board, d.sfxOff, d.voiceClean === false]
      .concat((d.overlays || []).length ? [d.overlays] : [])   // later fields only when set, so older builds keep their hash
      .concat((d.hook || "").trim() ? [d.hook.trim()] : []).concat(((d.cta || {}).text || "").trim() ? [d.cta] : [])
      .concat((d.effects || []).length ? [d.effects] : [])
      .concat(d.grade && !isNeutral(d.grade) ? [d.grade] : [])
      .concat(Object.keys(d.sfxSwap || {}).length ? [d.sfxSwap] : [])
      .concat(d.capY != null ? [d.capY] : [])
      .concat(d.capSize != null ? ["sz" + d.capSize] : [])
      .concat(d.capFont ? [d.capFont] : [])
      .concat(d.style ? ["st:" + d.style] : [])
      .concat(d.speedMul ? ["sp" + d.speedMul] : [])
      .concat(d.look && (d.look.cap || d.look.hook) ? [{ cap: d.look.cap, hook: d.look.hook }] : []));
    let h = 5381; for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
    return (h >>> 0).toString(36);
  }

  // colour grade set on the page, iPhone-style sliders, each -100..100 (clarity and sharpness 0..100), 0 = untouched:
  // ex exposure, hi highlights, sh shadows, co contrast, br brightness, sa saturation, vi vibrance («кольоровість»), wa warmth,
  // cl clarity, sp sharpness. One model for the page (WebGL) and the render (ffmpeg lut1d + colorchannelmixer + vibrance + unsharp).
  const GKEYS = ["ex", "hi", "sh", "co", "br", "sa", "vi", "wa", "cl", "sp"];
  function gradeNorm(g) { const o = {}; for (const k of GKEYS) o[k] = Math.max(-100, Math.min(100, +((g || {})[k]) || 0)); o.cl = Math.max(0, o.cl); o.sp = Math.max(0, o.sp); return o; }
  function isNeutral(g) { const n = gradeNorm(g); return GKEYS.every(k => Math.abs(n[k]) < 0.5); }
  const s2l = x => x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4), l2s = x => x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
  const sm = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  function mono(x, S, H) {   // a smooth monotone curve through points pulled by shadows (S) and highlights (H), -1..1
    const X = [0, 0.15, 0.3, 0.5, 0.7, 0.85, 1], Y = [0, 0.15 + 0.12 * S, 0.3 + 0.06 * S, 0.5, 0.7 + 0.06 * H, 0.85 + 0.12 * H, 1];
    const n = X.length, d = [], m = [];
    for (let i = 0; i < n - 1; i++) d.push((Y[i + 1] - Y[i]) / (X[i + 1] - X[i]));
    m.push(d[0]); for (let i = 1; i < n - 1; i++) m.push(d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2); m.push(d[n - 2]);
    for (let i = 0; i < n - 1; i++) { if (d[i] === 0) { m[i] = m[i + 1] = 0; continue; }   // Fritsch-Carlson: no overshoot
      const a = m[i] / d[i], b = m[i + 1] / d[i], h = a * a + b * b; if (h > 9) { const t = 3 / Math.sqrt(h); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; } }
    let k = 0; while (k < n - 2 && x > X[k + 1]) k++;
    const h = X[k + 1] - X[k], t = (x - X[k]) / h, t2 = t * t, t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * Y[k] + (t3 - 2 * t2 + t) * h * m[k] + (-2 * t3 + 3 * t2) * Y[k + 1] + (t3 - t2) * h * m[k + 1];
  }
  function tone(x, n) {   // one channel 0..1 through exposure, highlights, shadows, brightness, contrast
    x = l2s(Math.min(1, s2l(x) * Math.pow(2, n.ex / 100)));                       // exposure: up to ±1 stop, in linear light
    x = mono(x, n.sh / 100, n.hi / 100);                                             // shadows / highlights: black and white stay put
    x = Math.pow(Math.max(0, x), Math.pow(2, -n.br / 100 * 0.45));                  // brightness: mid-tones, ends stay put
    const k = Math.pow(2, n.co / 100 * 0.9);                                         // contrast: S-curve around the middle
    x = x < 0.5 ? 0.5 * Math.pow(2 * x, k) : 1 - 0.5 * Math.pow(2 - 2 * x, k);
    return Math.max(0, Math.min(1, x));
  }
  function gradeLut(g, N = 256) {   // per-channel tone curve incl. warmth: [[r,g,b] x N] for inputs i/(N-1)
    const n = gradeNorm(g), W = n.wa / 100, gain = [1 + 0.07 * W, 1, 1 - 0.07 * W], out = [];
    for (let i = 0; i < N; i++) { const t = tone(i / (N - 1), n); out.push(gain.map(k => Math.max(0, Math.min(1, t * k)))); }
    return out;
  }
  function gradeParams(g) {
    const n = gradeNorm(g), s = Math.max(0, 1 + n.sa / 100 * 0.6);
    return { n, lut: gradeLut(n), vib: n.vi / 100 * 0.6, clar: n.cl / 100 * 0.8, sharp: n.sp / 100 * 1.2,
             sat: [0.2126 + 0.7874 * s, 0.7152 - 0.7152 * s, 0.0722 - 0.0722 * s, 0.2126 - 0.2126 * s, 0.7152 + 0.2848 * s, 0.0722 - 0.0722 * s,
                   0.2126 - 0.2126 * s, 0.7152 - 0.7152 * s, 0.0722 + 0.9278 * s] };
  }
  function gradeCube(g) { return "LUT_1D_SIZE 256\n" + gradeLut(g).map(v => v.map(x => x.toFixed(6)).join(" ")).join("\n") + "\n"; }
  function gradeFilter(g, cubePath) {   // ffmpeg chain ("" when untouched); cubePath = where gradeCube(g) was written
    if (isNeutral(g)) return "";
    const P = gradeParams(g), f = x => (+x.toFixed(4)).toString(), out = [`lut1d=file=${cubePath}:interp=linear`];
    if (Math.abs(P.n.sa) >= 0.5) out.push("colorchannelmixer=" + ["rr", "rg", "rb", "gr", "gg", "gb", "br", "bg", "bb"].map((k, i) => `${k}=${f(P.sat[i])}`).join(":"));
    if (Math.abs(P.vib) > 1e-3) out.push(`vibrance=intensity=${f(P.vib)}:alternate=1:rlum=0.2126:glum=0.7152:blum=0.0722`);
    if (P.clar > 1e-3) out.push(`unsharp=13:13:${f(P.clar)}:3:3:0`);
    if (P.sharp > 1e-3) out.push(`unsharp=5:5:${f(P.sharp)}:3:3:0`);
    return out.join(",");
  }

  // Instagram Reels screen over a 1080x1920 frame (measured off an iPhone; keep in sync with scripts/safezones.py).
  // covered = the app draws over it; crop = cut off at the sides on taller phones; safe = where text and graphics belong.
  const SAFE = {
    covered: [{ id: "top", box: [0, 0, 1080, 220], label: "Верхня панель" },
              { id: "bottom", box: [0, 1500, 1080, 420], label: "Нік, підпис, музика" },
              { id: "buttons", box: [950, 1000, 130, 500], label: "Кнопки" }],
    crop: [[0, 0, 60, 1920], [1020, 0, 60, 1920]],
    safe: [60, 220, 960, 1280],
  };

  const api = { SAFE, autoPx, plan, captions, graphics, hash, capY, capsAround, gradeNorm, gradeParams, gradeLut, gradeCube, gradeFilter, isNeutral, GKEYS };
  if (typeof module !== "undefined") module.exports = api; else root.ReelCore = api;
})(this);
