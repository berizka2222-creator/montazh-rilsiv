// Reel Review page logic (the page itself is markup + styles; core.js holds the timing maths shared with review_sync.py)
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const v = $("#v"), ov = $("#ov");
// ---------- safe zones: the Instagram Reels screen over the video (ReelCore.SAFE) ----------
function drawZones() { $("#sz").innerHTML = zonesSvg((R && R.handle) || ""); }
function zonesSvg(nick) {
  const Z = ReelCore.SAFE, r = (b, cls) => `<rect class="${cls}" x="${b[0]}" y="${b[1]}" width="${b[2]}" height="${b[3]}" rx="${cls === "line" ? 24 : 0}"/>`;
  const [bx, by] = Z.covered.find(z => z.id === "buttons").box;
  const icons = [0, 1, 2, 3].map(k => `<circle class="ic" cx="${bx + 75}" cy="${by + 70 + k * 120}" r="30"/>`).join("");
  const handle = (nick || "твій_нік").replace(/^@/, "");
  return `<svg viewBox="0 0 1080 1920" preserveAspectRatio="none">${Z.crop.map(b => r(b, "crop")).join("")}${Z.covered.map(z => r(z.box, "cov")).join("")}
    ${r(Z.safe, "line")}${icons}<text x="70" y="130">Reels</text>
    <circle class="ic" cx="105" cy="1590" r="34"/><text x="160" y="1601">${handle.replace(/[<&]/g, "")} · Стежити</text>
    <text x="70" y="1690" opacity=".7">Підпис до рілса…</text><text x="70" y="1790" opacity=".7">♫ Оригінальний звук</text></svg>`;
}
function zonesOn(on) {
  $("#sz").hidden = !on; $("#szbtn").setAttribute("aria-pressed", on); $("#szbtn").classList.toggle("on", on);
  if (on) drawZones();
  try { localStorage.setItem("reelZones", on ? "1" : ""); } catch (e) {}
}
const fmt = t => `${Math.floor(t / 60)}:${(Math.max(0, t) % 60).toFixed(1).padStart(4, "0")}`;
let R = null, B = null, CB = null, S = blank(), P = null, CAPS = [], GFX = [];
// the cut on its own (db builds/cut): rendered right after step 1 so the cuts are checked before the graphics
const cutHash = d => { const x = JSON.stringify([d.cut, d.restoredFillers, d.restoredPauses, d.trimmedPauses]); let h = 5381; for (let i = 0; i < x.length; i++) h = ((h << 5) + h + x.charCodeAt(i)) | 0; return (h >>> 0).toString(36); };
const cutVid = () => tab === "graphics" && !!CB?.url;
let tab = "cuts", ref = null, saving = Promise.resolve(), timer = null, undo = [], mode = "idle", loop = null;
function blank() { return { cut: null, restoredFillers: [], restoredPauses: [], trimmedPauses: [], captions: null, board: {}, sfxOff: {}, overlays: [], effects: [], notes: {}, brandRequest: "", revisions: [], buildRequest: null }; }

// ---------- saving, undo ----------
const pill = (t, err) => { $("#save").textContent = t; $("#save").classList.toggle("err", !!err); $("#retry").hidden = !err; };
let dirty = false, mine = null;   // dirty: local edits not yet sent; mine: updatedAt of our last write (to spot other writers)
function queueSave() {
  clearTimeout(timer); dirty = true; pill("Є незбережені зміни…");
  timer = setTimeout(saveNow, 600);
}
function saveNow() {
  if (!ref) { pill("Немає з'єднання: зміни не збережуться", true); return; }
  dirty = false;
  const body = JSON.parse(JSON.stringify({ ...S, updatedAt: new Date().toISOString() }));
  mine = body.updatedAt;
  pill("Зберігаю…");
  saving = saving.then(() => ref.set(body)).then(() => pill("Збережено " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })),
    e => pill("Не вдалося зберегти (" + (e?.code || "error") + ")", true));
}
$("#retry").addEventListener("click", saveNow);
function mutate(fn) {
  undo.push(JSON.stringify(S)); if (undo.length > 60) undo.shift();
  fn(); $("#undo").disabled = false; recompute(); renderAll(); setPos(pos); queueSave();
}
function doUndo() { if (!undo.length) return; S = JSON.parse(undo.pop()); $("#undo").disabled = !undo.length; recompute(); renderAll(); queueSave(); }
$("#undo").addEventListener("click", doUndo);
$("#szbtn").addEventListener("click", () => zonesOn($("#sz").hidden));
try { if (localStorage.getItem("reelZones")) zonesOn(true); } catch (e) {}
document.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === "z" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) { e.preventDefault(); doUndo(); } });

// ---------- derived timeline ----------
function decisions() { return { ...S, cut: S.cut || R.proposedCut, captions: S.captions || R.captions }; }
function recompute() { const d = decisions(); P = ReelCore.plan(R, d); CAPS = ReelCore.captions(R, d, P); GFX = ReelCore.graphics(R, d, P); ReelCore.capsAround(R, d, CAPS, GFX); }

// ---------- tabs ----------
const STEP_OF = { cuts: 1, overlays: 1, effects: 1, captions: 1, sound: 1, mystyle: 1, graphics: 2, preview: 3 };
let lastSub = "cuts";
function showTab(t) {
  tab = t;
  if (STEP_OF[t] === 1) lastSub = t;
  $$("#steps .st").forEach(b => b.classList.toggle("here", +b.dataset.s === STEP_OF[t]));
  $("#stylelink").classList.toggle("here", t === "style");
  $(".tabs").classList.toggle("off", STEP_OF[t] !== 1);
  $$(".tab").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t));
  $$("section[data-p]").forEach(s => s.hidden = s.dataset.p !== t);
  $("#notesbox").hidden = t === "style"; document.querySelector(".wrap").classList.toggle("stylemode", t === "style");
  if (t === "style") { $("#nextbox").hidden = true; stopPlay(); renderStyle(); renderStage(); return; }
  if (!R) return;
  placeTimeline(t);
  $("#notetab").textContent = { cuts: "нарізка", overlays: "накладення", effects: "ефекти", graphics: "графіка", captions: "субтитри", sound: "звук і колір", mystyle: "стиль монтажу", preview: "чернетка" }[t];
  $("#notes").value = S.notes[t] || ""; $("#notesdet").open = !!(S.notes[t] || "").trim() || !!((S.refs || {})[t] || []).length; $("#resetbox").hidden = t === "preview";
  renderRefs();
  $("#nextbox").hidden = true;   // the steps on top and the bar at the bottom lead the way now
  $("#notesbox").hidden = !(S.notes[t] || "").trim() && !((S.refs || {})[t] || []).length;
  stopPlay();
  if (t !== "overlays" && placing && !placing.id) stopPlacing();
  if (t === "overlays" && assets && $("#ovbox").open && !placing) setTimeout(() => startPlacing(OV_PLACE[ovMode()]), 0);
  $("#noprev").hidden = !(t === "preview" && !B?.url);
  $("#mode").hidden = t === "preview" || (t === "graphics" && !!CB?.url); $("#szbtn").hidden = t === "preview";
  $("#sz").hidden = t === "preview" || $("#szbtn").getAttribute("aria-pressed") !== "true";
  if (cutVid()) { $("#clock").hidden = true; if (v.getAttribute("src") !== CB.url) { v.setAttribute("src", CB.url); v.load(); } $("#rough").hidden = $("#back5").hidden = $("#fwd5").hidden = true; $(".scrub").hidden = true; v.controls = true; mode = "cutvid"; }
  else if (t === "preview") { $("#clock").hidden = true; if (B?.url && v.getAttribute("src") !== B.url) { v.setAttribute("src", B.url); v.load(); } $("#rough").hidden = $("#back5").hidden = $("#fwd5").hidden = true; $(".scrub").hidden = true; v.controls = true; }
  else { if (v.getAttribute("src") !== R.srcUrl) { v.setAttribute("src", R.srcUrl); v.load(); } $("#rough").hidden = $("#back5").hidden = $("#fwd5").hidden = false; $(".scrub").hidden = false; v.controls = false; }
  if (t === "captions" && R) { mode = "roughPaused"; v.currentTime = P.toSrc(pos); $("#clock").hidden = false; }
  gradeView(); overlay(pos); renderStage();
}
$$(".tab").forEach(b => b.addEventListener("click", () => showTab(b.dataset.tab)));
// the steps in order: a number on each tab and a «Далі» button under each section
const ORDER = $$(".tab:not(.tabx)").map(b => b.dataset.tab);   // «Стиль» is not a step of the reel
$$("#steps .st, #stylelink").forEach(b => b.addEventListener("click", () => { const go = b.dataset.go;
  if (b.classList.contains("locked")) { $("#banner").textContent = b.dataset.s === "2" ? "Крок 2 відкриється, коли натиснеш «Готово → пропозиції Claude» внизу: Claude збере нарізку й запропонує графіку." : "Чернетка з'явиться після «Зібрати чернетку» на кроці 2."; $("#banner").hidden = false; return; } showTab(go === "cuts" ? lastSub : go); scrollTo({ top: 0, behavior: "smooth" }); }));
$$(".notebtn").forEach(b => b.addEventListener("click", () => { $("#notesbox").hidden = false; $("#notesdet").open = true; $("#notesdet").scrollIntoView({ block: "center", behavior: "smooth" }); setTimeout(() => $("#notes").focus(), 300); }));
$$(".helpbtn").forEach(b => b.addEventListener("click", () => { const on = $("#legend").hidden; $("#legend").hidden = !on; b.setAttribute("aria-expanded", String(on)); }));
$("#nextbtn").addEventListener("click", () => { const k = ORDER.indexOf(tab); if (k < ORDER.length - 1) { showTab(ORDER[k + 1]); scrollTo({ top: 0, behavior: "smooth" }); } });
$("#notes").addEventListener("input", e => { S.notes[tab] = e.target.value; queueSave(); });
$("#brand").addEventListener("input", e => { S.brandRequest = e.target.value; queueSave(); });
$("#reset").addEventListener("click", () => {
  const box = $("#resetbox"); box.textContent = "";
  const msg = document.createElement("span"); msg.className = "confirm"; msg.textContent = "Повернути цей розділ до моєї пропозиції? ";
  const yes = document.createElement("button"); yes.className = "b"; yes.type = "button"; yes.textContent = "Скинути";
  const no = document.createElement("button"); no.className = "b quiet"; no.type = "button"; no.textContent = "Скасувати";
  const back = () => { box.textContent = ""; box.append(resetBtn); };
  yes.addEventListener("click", () => { mutate(() => {
    if (tab === "cuts") Object.assign(S, { cut: null, restoredFillers: [], restoredPauses: [], trimmedPauses: [] });
    if (tab === "graphics") S.board = {};
    if (tab === "captions") S.captions = null;
    if (tab === "sound") { S.sfxOff = {}; S.grade = null; }
    if (tab === "overlays") S.overlays = [];
    if (tab === "effects") S.effects = [];
  }); back(); });
  no.addEventListener("click", back); msg.append(yes, no); box.append(msg);
});
const resetBtn = $("#reset");

// ---------- playback: line (raw) and continuous rough cut ----------
let pos = 0;   // where the rough cut is, in cut time: pause, scrub and ±5 s all keep it
v.addEventListener("timeupdate", () => { if (mode === "cutvid") { pos = v.currentTime; overlay(v.currentTime); tlPlayhead(); } else if (tab === "preview") { pos = v.currentTime; tlPlayhead(); } });
v.addEventListener("seeked", () => { if (mode === "cutvid") { pos = v.currentTime; overlay(v.currentTime); } });
function renderCutBox() {   // notes on the cut video (S.cutNotes, cut seconds) and whether the video still matches her cuts
  const box = $("#cutnotes"); if (!box) return; box.textContent = "";
  const st = $("#cutstate");
  if (CB?.url) st.textContent = CB.cutHash && S.graphicsRequest && cutHash(decisions()) !== CB.cutHash ? "Ти змінила нарізку після цього відео: Claude врахує це в чернетці." : "Відео нарізки: склейки справжні, графіка рамками.";
  else st.textContent = S.graphicsRequest ? "Claude збирає відео нарізки (~2–3 хв)…" : "Відео нарізки з'явиться після «Готово → Claude» на кроці 1.";
  $("#cutadd").disabled = !CB?.url;
  for (const [k, n] of (S.cutNotes || []).entries()) {
    const row = document.createElement("div"); row.className = "rev";
    const t = document.createElement("button"); t.className = "ts"; t.type = "button"; t.innerHTML = `<span class="tc">${fmt(n.t)}</span>`;
    t.addEventListener("click", () => { if (cutVid()) { v.currentTime = n.t; v.play().catch(() => {}); } });
    const x = document.createElement("span"); x.textContent = n.text;
    const del = document.createElement("button"); del.type = "button"; del.className = "b quiet"; del.textContent = "Видалити";
    del.addEventListener("click", () => mutate(() => S.cutNotes.splice(k, 1)));
    row.append(t, x, del); box.appendChild(row);
  }
}
$("#cutadd").addEventListener("click", () => {
  const text = $("#cutnote").value.trim(); if (!text) { $("#cutnote").focus(); return; }
  if (!cutVid()) { pill("Нотатки до нарізки ставляться на відео нарізки.", true); return; }
  mutate(() => { S.cutNotes = [...(S.cutNotes || []), { t: +v.currentTime.toFixed(2), text }].sort((a, b) => a.t - b.t); }); $("#cutnote").value = "";
});
function stopPlay() { mode = "idle"; cancelAnimationFrame(loop); v.pause(); v.playbackRate = 1; $("#rough").textContent = "▶ Нарізка"; }
function setPos(c) {
  pos = Math.max(0, Math.min(c, P.cutDur - 0.05)); tlPlayhead();
  $("#scrub").max = P.cutDur.toFixed(1); $("#scrub").value = pos.toFixed(1);
  $("#pos").textContent = `${fmt(pos)} / ${fmt(P.cutDur)}`; $("#clock").textContent = `монтаж ${fmt(pos)} / ${fmt(P.cutDur)}`;
  $("#ovat").textContent = fmt(pos); $("#efat").textContent = fmt(pos);
}
function seekCut(c) {   // jump within the rough cut; keeps playing if it was playing, else shows that frame
  setPos(c); v.currentTime = P.toSrc(pos); $("#clock").hidden = false;
  if (mode !== "rough") { mode = "roughPaused"; overlay(pos); }
}
$("#scrub").addEventListener("input", e => seekCut(+e.target.value));
$("#back5").addEventListener("click", () => seekCut(pos - 5));
$("#fwd5").addEventListener("click", () => seekCut(pos + 5));
function playLine(s, e) {
  stopPlay(); mode = "line"; v.currentTime = s; v.play().catch(() => { stopPlay(); pill("Відтворення заблоковано. Тапни час ще раз.", true); });
  const tick = () => { if (mode !== "line") return; if (v.currentTime >= e) { stopPlay(); return; } overlay(); loop = requestAnimationFrame(tick); };
  loop = requestAnimationFrame(tick);
}
function playRough(fromCut = pos) {
  if (fromCut >= P.cutDur - 0.1) fromCut = 0;
  stopPlay(); mode = "rough"; v.playbackRate = P.speed; setPos(fromCut); v.currentTime = P.toSrc(pos); $("#clock").hidden = false;
  $("#rough").textContent = "❚❚ Пауза";
  v.play().catch(() => { stopPlay(); pill("Відтворення заблоковано. Натисни «Дивитись» ще раз.", true); });
  const tick = () => {
    if (mode !== "rough") return;
    const t = v.currentTime, sp = P.spans;
    const k = sp.findIndex(([a, b]) => t < b);
    if (k === -1) { stopPlay(); mode = "roughPaused"; setPos(P.cutDur); return; }
    if (t < sp[k][0] - 0.02) v.currentTime = sp[k][0];          // inside a cut: jump to the next kept span
    const c = P.toCut(Math.max(t, sp[k][0]));
    setPos(c); overlay(c); loop = requestAnimationFrame(tick);
  };
  loop = requestAnimationFrame(tick);
}
$("#rough").addEventListener("click", () => { if (mode === "rough") { stopPlay(); mode = "roughPaused"; overlay(pos); } else playRough(pos); });
v.addEventListener("loadedmetadata", () => { if (mode === "idle" && tab !== "preview" && v.currentTime === 0) v.currentTime = 0.05; });   // show a frame, not black
v.addEventListener("error", () => pill("Відео не завантажилось. Онови сторінку; якщо не допоможе, попроси Claude завантажити його знову.", true));

// overlay at a cut time: approximate graphic boxes + caption style preview
function overlay(c) {
  ov.textContent = "";
  if (!R || tab === "preview" || c == null || (mode !== "rough" && mode !== "roughPaused" && mode !== "cutvid" && !placing)) { highlight(null); return; }
  for (const g of GFX) if (!g.gone && g.state !== "d" && c >= g.start && c < g.end && !(placing && g.id === placing.id)) {
    if ((g.type === "title" || g.type === "cta") && (g.text || "").trim()) { const h = hookEl(g); ov.appendChild(h); fitHook(h); }
    else if (g.user && g.type === "bigtext") { const t = txtEl(g.text, g.place, lookOf("ov:" + g.id)); ov.appendChild(t); fitHook(t); }
    else ov.appendChild(box(g, true)); }
  if (placing) {
    const pt = placing.id ? (GFX.find(x => x.id === placing.id && x.type === "bigtext") || {}).text : ovKind() === "text" && $("#ovtext").value.trim();
    if (pt) { const t = txtEl(pt, placing.place, lookOf(placing.id ? "ov:" + placing.id : "txt")); ov.appendChild(t); fitHook(t); }
    const ph = placing.id && GFX.find(x => x.id === placing.id && (x.type === "title" || x.type === "cta"));
    if (ph && (ph.text || "").trim()) { const h = hookEl({ ...ph, place: placing.place }); h.classList.add("placing"); ov.appendChild(h); fitHook(h); }
    ov.appendChild(placeBox());
  }
  let cap = GFX.some(g => g.capsAside && !g.gone && g.state !== "d" && c >= g.start && c < g.end) ? null : CAPS.find(x => !x.gone && c >= x.start && c < x.end);
  const place = tab === "captions" && mode !== "rough";
  if (!cap && place) cap = CAPS.find(x => !x.gone && x.start >= c) || CAPS.filter(x => !x.gone).pop();   // something to drag
  if (cap) { const el = capEl(cap); ov.appendChild(el); fitCap(el); if (place) dragCap(el); }
  highlight(c, cap);
}
function box(g, label) {
  const [x, y, w, h] = g.place || [90, 200, 900, 500];
  const el = document.createElement("div"); el.className = "gbox";
  Object.assign(el.style, { left: x / 10.8 + "%", top: y / 19.2 + "%", width: w / 10.8 + "%", height: h / 19.2 + "%" });
  if (g.imgUrl) el.style.backgroundImage = `linear-gradient(rgba(237,132,176,.15),rgba(237,132,176,.15)),url(${JSON.stringify(g.imgUrl)})`;
  if (g.imgUrl && g.user) Object.assign(el.style, { backgroundSize: "contain", backgroundRepeat: "no-repeat", backgroundPosition: "center" });   // their own pictures: shown whole
  if (label) {   // the card's own words, so the rough cut says what will be there (the real look is in the draft)
    const words = (g.text || g.title || g.top || "").replace(/\s*\/\s*/g, " ").trim() || (g.what || "");
    el.textContent = g.kind + (words ? ": " + (words.length > 70 ? words.slice(0, 68) + "…" : words) : "");
    el.style.whiteSpace = "normal"; el.style.textAlign = "center"; el.style.lineHeight = "1.2";
  }
  return el;
}
function capEl(cap) {
  const st = R.style, W = $("#player").clientWidth, one = cap.words.length === 1, L = lookOf("cap"), k = W / 1080, big = L.acc.look === "big";
  const el = document.createElement("div"); el.className = "capov" + (big && !one ? " ed" : "");
  const base = (S.capSize ?? st.capSize) / 1080 * W * (one ? 1.35 : 1);
  const cf = S.capFont || {};
  Object.assign(el.style, { top: (cap.y ?? ReelCore.capY(R, decisions())) / 19.2 + "%", fontFamily: cf.body ? (cf.body.brandFile ? cf.body.base : `"${cf.body.family}", sans-serif`) : "rb, var(--f-body)",
    fontWeight: cf.body ? cf.body.weight : "", fontSize: base + "px", textShadow: "none" });
  const run = document.createDocumentFragment();
  const wbg = L.bg === "word" ? lookBg(L, k) : "";
  let n = L.acc.a2 ? accBefore(cap) : 0;   // two accent colours alternate across the reel, as in the render
  for (const w of cap.words) {
    const s = document.createElement("span"), t = w.text.replace(/[.,!?;:]+$/, ""), tx = st.case === "lower" ? t.toLowerCase() : t;   // captions carry no punctuation
    if (w.accent) {
      const col = L.acc.a2 && n++ % 2 ? L.acc.a2 : L.acc.a1; s.className = "a";
      s.style.cssText = `font-family:${cf.accent ? (cf.accent.brandFile ? cf.accent.base : `"${cf.accent.family}", serif`) : "ra, Georgia, serif"};font-style:${cf.accent ? cf.accent.style : "italic"};font-weight:${cf.accent ? cf.accent.weight : ""};font-size:${big ? 1.7 : 1.12}em;` + accCss(L, col) + (L.acc.look === "box" ? "" : wbg);   // a «Плашка» accent keeps its own box
      if (L.acc.look === "echo") { s.style.position = "relative"; s.style.display = "inline-block"; s.style.zIndex = 0;
        for (const e of [1, 2]) { const i = document.createElement("i"); i.textContent = tx; i.setAttribute("aria-hidden", "true");
          i.style.cssText = `position:absolute;left:0;top:${-0.42 * e}em;z-index:-1;font-style:inherit;opacity:${0.42 / e};color:${col};-webkit-text-fill-color:${col};-webkit-text-stroke:0;text-shadow:none`; s.appendChild(i); } }
      s.appendChild(document.createTextNode(tx));
    } else { s.textContent = tx; if (wbg) s.style.cssText = wbg; }
    run.appendChild(s); run.appendChild(document.createTextNode(" "));
  }
  const look = lookRun(L, k, (() => { const w = document.createElement("span"); w.appendChild(run); return w; })());
  if (L.bg === "line") { const bx = document.createElement("span"); bx.style.cssText = lookBg(L, k); bx.appendChild(look); el.appendChild(bx); } else el.appendChild(look);
  return el;
}
function dragCap(el) {   // move the captions up or down on the player; saved as this reel's caption height
  el.classList.add("capdrag"); el.title = "Перетягни вгору або вниз";
  el.addEventListener("pointerdown", e => {
    e.preventDefault(); el.setPointerCapture(e.pointerId);
    const k = 1920 / $("#player").clientHeight, sy = e.clientY, y0 = ReelCore.capY(R, decisions()); let y = y0;
    const mv = ev => { y = Math.round(Math.max(150, Math.min(1560, y0 + (ev.clientY - sy) * k))); el.style.top = y / 19.2 + "%"; $("#capyval").textContent = capWhere(y); };
    const up = () => { el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up); if (y !== y0) mutate(() => { S.capY = y; }); };
    el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up);
  });
}
// caption fonts: the design system first, then free Google Fonts checked to have Ukrainian letters (Ї Є Ґ І); the brand's banned fonts are left out
// the design system's own list comes from brand.json "caption_fonts" (reel.json fontChoices): {body|accent: [{label, file|gf, weight, style}]}
const brandName = role => ((R && R.fontChoices && R.fontChoices.names) || {})[role] || (role === "body" ? "Бренд: основний" : "Бренд: акцент");
const brandFonts = role => [["brand", brandName(role) + (role === "accent" ? " italic" : ""), null, 400, role === "body" ? "normal" : "italic"]]
  .concat(((R && R.fontChoices) || {})[role]?.map(f => [f.label, f.label, f.gf || null, f.weight || 400, f.style || "normal", f.file]) || []);
const GF = {
  "Без засічок": "Golos Text|Golos+Text:wght@600;Rubik|Rubik:wght@600;Nunito|Nunito:wght@700;Nunito Sans|Nunito+Sans:wght@700;Raleway|Raleway:wght@600;Commissioner|Commissioner:wght@600;Geologica|Geologica:wght@600;Exo 2|Exo+2:wght@600;Comfortaa|Comfortaa:wght@700;Fira Sans|Fira+Sans:wght@600;Fira Sans Condensed|Fira+Sans+Condensed:wght@600;IBM Plex Sans|IBM+Plex+Sans:wght@600;PT Sans|PT+Sans:wght@700;PT Sans Narrow|PT+Sans+Narrow:wght@700;Noto Sans|Noto+Sans:wght@600;Ubuntu|Ubuntu:wght@500;Ubuntu Condensed|Ubuntu+Condensed;Source Sans 3|Source+Sans+3:wght@600;Mulish|Mulish:wght@700;Wix Madefor Display|Wix+Madefor+Display:wght@600;Wix Madefor Text|Wix+Madefor+Text:wght@600;Sofia Sans|Sofia+Sans:wght@600;Sofia Sans Condensed|Sofia+Sans+Condensed:wght@700;Oswald|Oswald:wght@500;Play|Play:wght@700;Philosopher|Philosopher:wght@700;Tektur|Tektur:wght@600;Jura|Jura:wght@600;Scada|Scada:wght@700;Cuprum|Cuprum:wght@600;Didact Gothic|Didact+Gothic;Arimo|Arimo:wght@600;Geist|Geist:wght@600;Podkova|Podkova:wght@600;Yanone Kaffeesatz|Yanone+Kaffeesatz:wght@600",
  "З засічками": "Lora|Lora:ital,wght@1,400|i;Playfair Display|Playfair+Display:ital,wght@1,400|i;Cormorant Garamond|Cormorant+Garamond:ital,wght@1,500|i;Cormorant|Cormorant:ital,wght@1,500|i;PT Serif|PT+Serif:ital,wght@1,400|i;EB Garamond|EB+Garamond:ital,wght@1,400|i;Merriweather|Merriweather:ital,wght@1,400|i;Noto Serif|Noto+Serif:ital,wght@1,400|i;Literata|Literata:ital,wght@1,400|i;Spectral|Spectral:ital,wght@1,400|i;Alice|Alice;Old Standard TT|Old+Standard+TT:ital@1|i;Prata|Prata;Ledger|Ledger;Vollkorn|Vollkorn:ital,wght@1,400|i;Tinos|Tinos:ital@1|i;Gabriela|Gabriela;El Messiri|El+Messiri:wght@600",
  "Виразні": "Russo One|Russo+One;Days One|Days+One;Prosto One|Prosto+One;Dela Gothic One|Dela+Gothic+One;Rubik Mono One|Rubik+Mono+One;Seymour One|Seymour+One;Ruslan Display|Ruslan+Display;Kelly Slab|Kelly+Slab;Yeseva One|Yeseva+One;Forum|Forum;Oranienbaum|Oranienbaum;Underdog|Underdog;Climate Crisis|Climate+Crisis;Rubik Doodle Shadow|Rubik+Doodle+Shadow;Rubik Wet Paint|Rubik+Wet+Paint",
  "Рукописні": "Caveat|Caveat:wght@600;Marck Script|Marck+Script;Bad Script|Bad+Script;Neucha|Neucha;Amatic SC|Amatic+SC:wght@700;Kurale|Kurale;Pangolin|Pangolin;Comforter|Comforter;Great Vibes|Great+Vibes;Pacifico|Pacifico;Lobster|Lobster;Pattaya|Pattaya" };
const GF_LIST = Object.entries(GF).map(([cat, str]) => [cat, str.split(";").map(x => { const [fam, gf, it] = x.split("|"); const w = +(gf.match(/@(?:1,)?(\d{3})$/) || [])[1] || 400; return { family: fam, gf, weight: w, style: it ? "italic" : "normal" }; })]);
const brandSpec = r => r[0] === "brand" ? null : r[2] ? { family: r[0], gf: r[2], weight: r[3], style: r[4] || "normal" } : { family: r[1], brandFile: r[5], weight: r[3], style: r[4] || "normal", base: "bf_" + r[5].replace(/\W/g, "_") + ", " + (r[5].startsWith("Nyght") ? "ra" : "rb") };
const gfLoaded = new Set();
function loadGf(spec) { if (!spec || !spec.gf || gfLoaded.has(spec.gf)) return; gfLoaded.add(spec.gf);
  document.head.appendChild(Object.assign(document.createElement("link"), { rel: "stylesheet", href: `https://fonts.googleapis.com/css2?family=${spec.gf}&display=swap` })); }
let previewsLoaded = false;
function loadPreviews() {   // every family's name in its own face: one small request (only the letters of the names)
  if (previewsLoaded) return; previewsLoaded = true;
  const fams = GF_LIST.flatMap(([, l]) => l).concat(["body", "accent"].flatMap(r => brandFonts(r).filter(x => x[2]).map(x => ({ gf: x[2] }))));
  const text = encodeURIComponent([...new Set(GF_LIST.flatMap(([, l]) => l.map(f => f.family)).join("") + "ManropeOnest" + "Їжак ґаву з'їв")].join(""));
  for (let i = 0; i < fams.length; i += 25)
    document.head.appendChild(Object.assign(document.createElement("link"), { rel: "stylesheet", href: "https://fonts.googleapis.com/css2?" + fams.slice(i, i + 25).map(f => "family=" + f.gf).join("&") + "&text=" + text + "&display=swap" }));
}
const faceCss = (spec, role) => spec ? (spec.brandFile ? `font-family:${spec.base};font-weight:${spec.weight};font-style:${spec.style}` : `font-family:"${spec.family}";font-weight:${spec.weight};font-style:${spec.style}`)
  : (role === "body" ? "font-family:rb, var(--f-body)" : "font-family:ra, Georgia, serif;font-style:italic");
function fillFontSelects() {
  for (const [role, id] of [["body", "#capfont"], ["accent", "#capacc"]]) {
    const sp = (S.capFont || {})[role]; loadGf(sp);
    const b = $(id); b.textContent = sp ? sp.family : brandName(role); b.style.cssText = faceCss(sp, role);
  }
}
let popRole = null;
function openFonts(role) {
  popRole = role; loadPreviews(); const pop = $("#fontpop"); pop.hidden = false; $("#fontq").value = ""; renderFontList(); $("#fontq").focus();
  const btn = role === "body" ? $("#capfont") : $("#capacc"); btn.after(pop);
}
function renderFontList() {
  const q = $("#fontq").value.trim().toLowerCase(), box = $("#fontlist"); box.textContent = "";
  const cur = ((S.capFont || {})[popRole] || {}).family || "brand";
  const groups = [["Дизайн-система", brandFonts(popRole).map(r => ({ id: r[0], label: r[1], spec: brandSpec(r) }))]]
    .concat((popRole === "accent" ? [GF_LIST[1], GF_LIST[3], GF_LIST[2], GF_LIST[0]] : GF_LIST).map(([cat, l]) => [cat, l.map(f => ({ id: f.family, label: f.family, spec: f }))]));
  for (const [cat, items] of groups) {
    const list = items.filter(it => !q || it.label.toLowerCase().includes(q)); if (!list.length) continue;
    const h = document.createElement("div"); h.className = "gtitle"; h.textContent = cat; box.appendChild(h);
    for (const it of list) {
      const b = document.createElement("button"); b.type = "button"; b.className = "fontopt"; b.setAttribute("aria-pressed", it.id === cur || (it.spec && it.spec.family === cur));
      b.innerHTML = `<span></span><small>Їжак ґаву з'їв</small>`; b.firstChild.textContent = it.label; b.firstChild.style.cssText = faceCss(it.spec, popRole); b.lastChild.style.cssText = faceCss(it.spec, popRole);
      if (it.spec && it.spec.gf) b.addEventListener("mouseenter", () => loadGf(it.spec), { once: true });
      b.addEventListener("click", () => { loadGf(it.spec); const role = popRole;
        mutate(() => { const f = { ...(S.capFont || {}) }; if (it.spec) f[role] = it.spec; else delete f[role]; S.capFont = Object.keys(f).length ? f : null; });
        $("#fontpop").hidden = true; setTimeout(() => overlay(pos), 400); });
      box.appendChild(b);
    }
  }
  if (!box.children.length) box.innerHTML = `<div class="mode" style="padding:8px">Нічого не знайшлось.</div>`;
}
$("#capfont").addEventListener("click", () => $("#fontpop").hidden || popRole !== "body" ? openFonts("body") : ($("#fontpop").hidden = true));
$("#capacc").addEventListener("click", () => $("#fontpop").hidden || popRole !== "accent" ? openFonts("accent") : ($("#fontpop").hidden = true));
$("#fontq").addEventListener("input", renderFontList);
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#fontpop").hidden = true; });
document.addEventListener("click", e => { if (!$("#fontpop").hidden && !e.target.closest("#fontpop,.fontbtn")) $("#fontpop").hidden = true; });
function capWhere(y) { const F = R.face; if (!F) return Math.round(y / 19.2) + "% висоти";
  return y + 150 < F[1] ? "над головою" : y > F[1] + F[3] ? (y > 1350 ? "внизу" : "під підборіддям") : "на обличчі"; }
function renderCapPlace() {
  const F = R.face || [300, 540, 480, 620], y = ReelCore.capY(R, decisions()), box = $("#capplace"); box.textContent = "";
  const opts = [["Над головою", Math.max(150, F[1] - 280)], ["Під підборіддям", F[1] + F[3] + 20], ["Внизу", 1400]];
  for (const [name, val] of opts) { const b = document.createElement("button"); b.type = "button"; b.textContent = name; b.setAttribute("aria-pressed", Math.abs(val - y) < 30);
    b.addEventListener("click", () => { mutate(() => { S.capY = val; }); if (tab === "captions") { mode = "roughPaused"; overlay(pos); } }); box.appendChild(b); }
  $("#capyval").textContent = capWhere(y);
  fillFontSelects();
  const sz = S.capSize ?? R.style.capSize; $("#capsz").value = sz; $("#capszv").textContent = sz + " px" + (S.capSize == null ? " (бренд)" : "");
  renderLooks();
}
$("#capsz").addEventListener("input", e => { S.capSize = +e.target.value; $("#capszv").textContent = S.capSize + " px"; overlay(pos); });
$("#capsz").addEventListener("change", () => mutate(() => { if (S.capSize === R.style.capSize) delete S.capSize; }));

// ---------- text look: captions + hook (colour or gradient, outline, shadow, box, accent word, 2nd hook line) ----------
// stored partial in S.look {cap, hook, keep}: only what was changed; brand.json "text_look" (R.look) and LDEF fill the rest.
// The render (build_reel.py look_fill / look_bg) uses the same numbers on the 1080 frame.
const LDEF = {
  cap: () => ({ c1: R.style.cap || "#FFFFFF", c2: null, gd: 90, sw: 0, sc: "#000000", sh: 30, ss: 28, bg: "none", bc: R.style.main, bo: 70, br: 16,
    acc: { look: R.style.editorial ? "big" : "color", a1: R.style.acc, a2: R.style.acc2 || null } }),
  cta: () => ({ c1: R.style.main || "#0D1A0F", c2: null, gd: 90, sw: 0, sc: "#000000", sh: 0, ss: 28, bg: "line", bc: "#FFFFFF", bo: 100, br: 40, l2: { c1: null, c2: null }, l2acc: false }),
  hook: () => ({ c1: R.titleColor || "#FFFFFF", c2: null, gd: 90, sw: 0, sc: "#000000", sh: 40, ss: 68, bg: "none", bc: R.style.main, bo: 70, br: 16,
    l2: { c1: null, c2: null }, l2acc: false }),
  // text they add on «Накладення»: "txt" = the look of the next text (and the brand default), "ov:<id>" = one added text (overlay.look)
  txt: () => ({ c1: "#FFFFFF", c2: null, gd: 90, sw: 0, sc: "#000000", sh: 0, ss: 28, bg: "none", bc: R.style.main, bo: 70, br: 16, font: "head", px: null }) };
const ovById = id => (S.overlays || []).find(o => o.id === id);
function lookPart(k) { return k.startsWith("ov:") ? (ovById(k.slice(3)) || {}).look : (S.look || {})[k]; }
function lookOf(k) {
  if (k.startsWith("ov:")) { const t = lookOf("txt"); return { ...t, ...(lookPart(k) || {}) }; }
  const d = LDEF[k](), b = (R.look || {})[k] || {}, s = (S.look || {})[k] || {};
  const L = { ...d, ...b, ...s, acc: { ...d.acc, ...(b.acc || {}), ...(s.acc || {}) }, l2: { ...d.l2, ...(b.l2 || {}), ...(s.l2 || {}) } };
  if (k === "hook" || k === "cta") { const bl = b.lines || [], sl = s.lines || []; L.lines = Array.from({ length: Math.max(bl.length, sl.length) }, (_, i) => ({ ...(bl[i] || {}), ...(sl[i] || {}) })); }
  if (!L.l2.c1) L.l2.c1 = L.c1;
  return L;
}
const hexA = (h, a) => { h = (h || "#000000").replace("#", ""); return `rgba(${parseInt(h.slice(0, 2), 16)},${parseInt(h.slice(2, 4), 16)},${parseInt(h.slice(4, 6), 16)},${a})`; };
function lookShadow(L, k, filt) {
  const a = L.sh / 100, blur = L.ss * 0.5 * k, sh = `0 ${blur * 0.18 + (a ? 2 * k : 0)}px ${blur}px rgba(0,0,0,${a})`;
  return filt ? (a ? `filter:drop-shadow(${sh});` : "") : `text-shadow:${a ? sh : "none"};`;
}
const lookFill = (L, k) => `color:${L.c1};-webkit-text-fill-color:${L.c1};` + (L.sw > 0 ? `-webkit-text-stroke:${L.sw * 2 * k}px ${L.sc};paint-order:stroke fill;` : "-webkit-text-stroke:0;") + lookShadow(L, k);
function lookRun(L, k, node, cls) {   // same layers as build_reel.py look_run: gradient clipped to the letters, its outline a copy underneath
  const run = document.createElement("span"); run.className = cls || "cf"; run.appendChild(node);
  if (!L.c2) { run.style.cssText = lookFill(L, k); return run; }
  run.style.cssText = `background:linear-gradient(${L.gd}deg,${L.c1},${L.c2});-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;-webkit-text-stroke:0;text-shadow:none;`;
  const gw = document.createElement("span"); gw.className = "gw"; gw.style.cssText = lookShadow(L, k, true);
  if (L.sw > 0) { const go = document.createElement("span"); go.className = "go"; go.setAttribute("aria-hidden", "true"); go.style.setProperty("--oc", L.sc); go.style.setProperty("--ow", L.sw * 2 * k + "px");
    go.appendChild(node.cloneNode(true)); gw.appendChild(go); }
  gw.appendChild(run); return gw;
}
const lookBg = (L, k) => L.bg === "none" ? "" : `background:${hexA(L.bc, L.bo / 100)};padding:.06em .26em .1em;border-radius:${L.br * k}px;box-decoration-break:clone;-webkit-box-decoration-break:clone;`;
function accCss(L, col) {
  if (L.acc.look === "box") return `color:${R.style.main};-webkit-text-fill-color:${R.style.main};background:${col};padding:0 .16em;border-radius:.14em;text-shadow:none;filter:none;-webkit-text-stroke:0;box-decoration-break:clone;-webkit-box-decoration-break:clone;`;
  if (L.acc.look === "underline") return `color:${L.c1};-webkit-text-fill-color:${L.c1};box-shadow:inset 0 -.2em 0 ${col};`;
  return `color:${col};-webkit-text-fill-color:${col};`;
}
function hookEl(g) {   // the hook / CTA on the rough cut, in the picked look (the draft shows the real animation)
  const K = g.type === "cta" ? "cta" : "hook", L = lookOf(K), k = $("#player").clientWidth / 1080, el = document.createElement("div"); el.className = "hookov";
  const lines = g.text.split("/").map(x => x.trim()).filter(Boolean).map(x => K === "hook" && R.style.case === "lower" ? x.toLowerCase() : x);
  const bold = Object.keys((R.fonts || {}).extra || {}).find(f => /bold/i.test(f));   // the brand's head face (Gilroy Bold) when it was uploaded
  Object.assign(el.style, { top: ((g.place || [])[1] ?? R.titleY ?? 360) / 19.2 + "%", transform: `translateX(${(((g.place || [])[0] ?? 90) - 90) / 10.8}%)`, fontFamily: bold ? "bf_" + bold.replace(/\W/g, "_") + ", rb, var(--f-body)" : "rb, var(--f-body)", fontWeight: bold ? 400 : 700 });
  lines.forEach((x, j) => {
    const d = document.createElement("div"), s = document.createElement("span"), alt = j % 2 === 1;
    const M = K === "cta" ? { ...L, font: "head", ...((L.lines || [])[j] || {}) } : lineLook(L, j), al = L.align || (K === "hook" && R.titleAlign) || "center";
    d.className = "hl"; d.style.textAlign = al === "zigzag" ? (lines.length > 1 ? (alt ? "right" : "left") : "center") : al; d.style.fontSize = (K === "cta" ? 96 : 130) * (L.scale || 100) / 100 * k + "px";
    if (M.font !== "head") Object.assign(d.style, txtFace(M.font));
    s.style.cssText = lookBg(M, k); s.appendChild(lookRun(M, k, document.createTextNode(x), "hk")); d.appendChild(s); el.appendChild(d);
  });
  return el;
}
function fitHook(el) { for (const d of el.children) { let fs = parseFloat(d.style.fontSize); for (let i = 0; i < 25 && d.scrollWidth > d.clientWidth + 1; i++) { fs *= 0.92; d.style.fontSize = fs + "px"; } } }
function setLook(k, key, val, sub, live) {   // live = while dragging (no undo step, no save yet)
  const apply = () => {
    if (k.startsWith("ov:")) { const ov = ovById(k.slice(3)); if (ov) ov.look = { ...(ov.look || {}), [key]: val }; return; }
    S.look = { ...(S.look || {}) }; const o = { ...(S.look[k] || {}) }; if (sub) o[sub] = { ...(o[sub] || {}), [key]: val }; else o[key] = val; S.look[k] = o; };
  if (live) { apply(); lookPreview(k); } else { mutate(apply); lookPreview(k); }
}
function lookPreview(k) {   // show the change on the player: the hook's seconds for the hook, captions where they are
  if (k === "hook" || k === "cta") { const g = GFX.find(x => x.type === (k === "cta" ? "cta" : "title") && !x.gone && x.state !== "d"); if (g && (pos < g.start || pos >= g.end)) seekCut(g.start + 0.5); }
  if (k.startsWith("ov:")) { const g = GFX.find(x => x.id === k.slice(3)); if (g && !g.gone && (pos < g.start || pos >= g.end)) seekCut(g.start + 0.3); }
  if (!["rough", "roughPaused", "cutvid"].includes(mode)) mode = "roughPaused";
  overlay(pos);
}
const LSW = () => [...new Set(["#FFFFFF", "#000000", R.style.main, R.style.acc, R.style.acc2, (R.theme || {}).soft].filter(Boolean).map(x => x.toUpperCase()))];
// «Мої кольори» (db library/colors): colours she picked herself (10 minus the brand ones, at least 3), next to the brand ones, on every reel
let MYCOL = [], colRef = null;
function rememberColor(c) {
  c = (c || "").toUpperCase(); if (!/^#[0-9A-F]{6}$/.test(c) || LSW().includes(c)) return;
  MYCOL = [c, ...MYCOL.filter(x => x !== c)].slice(0, Math.max(3, 10 - LSW().length));   // 10 swatches in all: the design system always, her own fill the rest, the oldest goes first
  if (colRef) colRef.set({ items: MYCOL, updatedAt: new Date().toISOString() }).catch(() => pill("Колір не зберігся в «Мої кольори»", true));
}
function lColor(label, val, set, live) {
  const r = document.createElement("div"); r.className = "lrow"; r.innerHTML = `<span class="gl"></span><div class="sws"></div>`; r.firstChild.textContent = label;
  const box = r.lastChild;
  const brandSw = LSW();
  for (const c of [...brandSw, ...MYCOL.filter(x => !brandSw.includes(x))]) { const b = document.createElement("button"); b.type = "button"; b.style.background = c; b.title = c + (brandSw.includes(c) ? "" : " · мій колір"); b.setAttribute("aria-label", label + " " + c);
    if (!brandSw.includes(c)) b.classList.add("mine");
    b.setAttribute("aria-pressed", (val || "").toUpperCase() === c); b.addEventListener("click", () => set(c)); box.appendChild(b); }
  const i = document.createElement("input"); i.type = "color"; i.value = /^#[0-9a-f]{6}$/i.test(val || "") ? val : "#ffffff"; i.setAttribute("aria-label", label + ": свій колір");
  i.addEventListener("input", () => live(i.value)); i.addEventListener("change", () => { rememberColor(i.value); set(i.value); }); i.title = "Свій колір: запам'ятається в «Мої кольори»"; box.appendChild(i);
  return r;
}
function lSlider(label, min, max, step, val, show, set, live) {
  const r = document.createElement("label"); r.className = "gs"; r.innerHTML = `<span class="gl"></span><span class="gv"></span><input type="range" min="${min}" max="${max}" step="${step}">`;
  r.firstChild.textContent = label; const v = r.children[1], i = r.lastChild; i.value = val; v.textContent = show(+val); i.setAttribute("aria-label", label);
  i.addEventListener("input", () => { v.textContent = show(+i.value); live(+i.value); }); i.addEventListener("change", () => set(+i.value));
  return r;
}
function lSeg(label, opts, val, set) {
  const r = document.createElement("div"); r.className = "lrow"; r.innerHTML = `<span class="gl"></span><div class="gpre" role="group"></div>`; r.firstChild.textContent = label;
  for (const [t, v] of opts) { const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.setAttribute("aria-pressed", v === val); b.addEventListener("click", () => set(v)); r.lastChild.appendChild(b); }
  return r;
}
function lChk(label, on, set) {
  const r = document.createElement("label"); r.className = "lchk"; r.innerHTML = `<input type="checkbox"><span></span>`; r.lastChild.textContent = label;
  r.firstChild.checked = !!on; r.firstChild.addEventListener("change", e => set(e.target.checked)); return r;
}
function lGroup(title, ...rows) { const g = document.createElement("div"); g.className = "ggroup"; g.innerHTML = `<div class="gtitle"></div>`; g.firstChild.textContent = title; rows.filter(Boolean).forEach(x => g.appendChild(x)); return g; }
function lineLook(L, j) {   // one hook line: its own "lines"[j] over the old 2nd-line fields (same as build_reel.py)
  const leg = j % 2 && L.l2 ? { c1: L.l2.c1 || L.c1, c2: L.l2.c2 || null } : {};
  return { ...L, ...leg, font: L.l2acc && j % 2 ? "accent" : "head", ...((L.lines || [])[j] || {}) };
}
function hookLines() { const t = (S.hook != null ? S.hook : (GFX.find(g => g.type === "title") || {}).text) || ""; return t.split("/").map(x => x.trim()).filter(Boolean); }
function setLine(K, j, key, val, live) {
  const apply = () => { S.look = { ...(S.look || {}) }; const o = { ...(S.look[K] || {}) }; const ls = [...(o.lines || [])];
    for (let i = 0; i <= j; i++) ls[i] = ls[i] || {}; ls[j] = { ...ls[j], [key]: val }; o.lines = ls; S.look[K] = o; };
  if (live) { apply(); lookPreview(K); } else { mutate(apply); lookPreview(K); }
}
function blockLines(K) {
  const t = K === "cta" ? ((S.cta || {}).text || "") : (S.hook != null ? S.hook : (GFX.find(g => g.type === "title") || {}).text) || "";
  return t.split("/").map(x => x.trim()).filter(Boolean);
}
function rebalance(text, n) {   // the same words in n lines of about equal length
  const w = text.replace(/\s*\/\s*/g, " ").split(/\s+/).filter(Boolean); if (n <= 1 || w.length <= 1) return w.join(" ");
  n = Math.min(n, w.length); const total = w.join(" ").length, out = []; let cur = [];
  for (let i = 0; i < w.length; i++) {
    cur.push(w[i]); const left = w.length - i - 1, need = n - out.length - 1;
    if (need > 0 && (left === need || cur.join(" ").length >= total / n - 1)) { out.push(cur.join(" ")); cur = []; }
  }
  if (cur.length) out.push(cur.join(" ")); return out.join(" / ");
}
function renderHookLook(root, K = "hook") {   // hook and CTA: the same controls
  const L = lookOf(K), lines = blockLines(K), n = Math.max(1, lines.length), set = key => v => setLook(K, key, v), live = key => v => setLook(K, key, v, null, true);
  root.textContent = "";
  const grid = document.createElement("div"); grid.className = "ggrid lookcards"; root.appendChild(grid);
  const how = document.createElement("p"); how.className = "mode"; how.textContent = "Рядки ділить «/» у тексті: «750 грн / → 600€». Або обери кількість рядків вище.";
  const cnt = lines.length, setCnt = n => { const t = rebalance(lines.join(" "), n); mutate(() => { if (K === "cta") S.cta = { ...(S.cta || { dur: 4 }), text: t }; else S.hook = t; }); syncHookCta(); lookPreview(K); };
  grid.appendChild(lGroup("Розташування і розмір",
    lSeg("Скільки рядків", [["1", 1], ["2", 2], ["3", 3], ["4", 4]], cnt, setCnt),
    lSeg("Рядки", [["По центру", "center"], ["Зигзаг", "zigzag"], ["Ліворуч", "left"], ["Праворуч", "right"]], L.align || R.titleAlign || "center", set("align")),
    lSlider("Розмір", 50, 150, 5, L.scale || 100, v => v + "%", set("scale"), live("scale")), how));
  for (let j = 0; j < n; j++) {
    const M = lineLook(L, j), s1 = key => v => setLine(K, j, key, v), lv = key => v => setLine(K, j, key, v, true);
    const t = lines[j] || "", name = `Рядок ${j + 1}` + (t ? ` · «${t.length > 18 ? t.slice(0, 17) + "…" : t}»` : "");
    grid.appendChild(lGroup(name,
      lSeg("Шрифт", [["Заголовків", "head"], ["Основний", "body"], ["Акцентний", "accent"]], M.font, s1("font")),
      lColor("Колір", M.c1, s1("c1"), lv("c1")),
      lChk("Градієнт", !!M.c2, on => setLine(K, j, "c2", on ? (R.style.acc2 || R.style.acc) : null)),
      M.c2 ? lColor("Другий колір градієнта", M.c2, s1("c2"), lv("c2")) : null,
      M.c2 ? lSeg("Напрямок", [["→", 90], ["↓", 180], ["↘", 135]], M.gd, s1("gd")) : null,
      lSlider("Контур", 0, 16, 0.5, M.sw || 0, v => v ? v + " px" : "без контуру", s1("sw"), lv("sw")),
      M.sw > 0 ? lColor("Колір контуру", M.sc, s1("sc"), lv("sc")) : null,
      lSeg("Фон", [["Немає", "none"], ["Під рядком", "line"]], (M.bg || "none") === "none" ? "none" : "line", s1("bg")),
      M.bg && M.bg !== "none" ? lColor("Колір фону", M.bc, s1("bc"), lv("bc")) : null,
      M.bg && M.bg !== "none" ? lSlider("Прозорість", 0, 95, 1, 100 - M.bo, v => v + "%", v => setLine(K, j, "bo", 100 - v), v => setLine(K, j, "bo", 100 - v, true)) : null,
      M.bg && M.bg !== "none" ? lSlider("Кути", 0, 60, 1, M.br, v => v ? v + " px" : "чіткі", s1("br"), lv("br")) : null));
  }
  grid.appendChild(lGroup("Тінь (для всіх рядків)",
    lSlider("Сила", 0, 100, 1, L.sh, v => v ? v + "%" : "без тіні", set("sh"), live("sh")),
    L.sh > 0 ? lSlider("М'якість", 0, 100, 1, L.ss, v => v < 15 ? "чітка" : v > 70 ? "дуже м'яка" : "м'яка", set("ss"), live("ss")) : null));
  const foot = document.createElement("div"); foot.className = "lookfoot";
  const reset = document.createElement("button"); reset.type = "button"; reset.className = "b"; reset.textContent = "Повернути як у бренді"; reset.disabled = !lookPart(K);
  reset.addEventListener("click", () => { mutate(() => { const o = { ...(S.look || {}) }; delete o[K]; S.look = o; }); lookPreview(K); });
  foot.append(reset, lChk("Робити так у всіх наступних рілсах", (S.look || {}).keep, on => mutate(() => { S.look = { ...(S.look || {}), keep: on }; })));
  root.appendChild(foot);
}
function renderLook(k, root) {
  if (k === "hook" || k === "cta") { renderHookLook(root, k); return; }
  const L = lookOf(k), set = (key, sub) => v => setLook(k, key, v, sub), live = (key, sub) => v => setLook(k, key, v, sub, true);
  root.textContent = "";
  const grid = document.createElement("div"); grid.className = "ggrid lookcards"; root.appendChild(grid);
  const fillRows = (c1, c2, sub, name) => [
    lColor(name, c1, set("c1", sub), live("c1", sub)),
    lChk("Градієнт", !!c2, on => setLook(k, "c2", on ? (k === "cap" ? R.style.acc : R.style.acc2 || R.style.acc) : null, sub)),
    c2 ? lColor("Другий колір градієнта", c2, set("c2", sub), live("c2", sub)) : null];
  grid.appendChild(lGroup(k === "hook" ? "Колір першого рядка" : "Колір тексту", ...fillRows(L.c1, L.c2, null, "Колір"),
    L.c2 || (k === "hook" && L.l2.c2) ? lSeg("Напрямок градієнта", [["→", 90], ["↓", 180], ["↘", 135]], L.gd, set("gd")) : null));
  if (k === "txt" || k.startsWith("ov:")) grid.insertBefore(lGroup("Шрифт і розмір",
    lSeg("Шрифт", [["Заголовків", "head"], ["Основний", "body"], ["Акцентний (курсив)", "accent"]], L.font, set("font")),
    lSlider("Розмір", 24, 400, 2, L.px != null ? L.px : lookAutoPx(k), v => v + " px" + (L.px == null ? " (авто)" : ""), set("px"), live("px")),
    L.px != null ? lChk("Авто: за розміром рамки", false, on => { if (on) setLook(k, "px", null); }) : null), grid.firstChild);
  if (k === "hook") grid.appendChild(lGroup("Другий рядок", ...fillRows(L.l2.c1, L.l2.c2, "l2", "Колір"),
    lChk("Акцентним шрифтом (з засічками, курсив)", L.l2acc, set("l2acc"))));
  grid.appendChild(lGroup("Контур",
    lSlider("Товщина", 0, 16, 0.5, L.sw, v => v ? v + " px" : "без контуру", set("sw"), live("sw")),
    L.sw > 0 ? lColor("Колір контуру", L.sc, set("sc"), live("sc")) : null));
  grid.appendChild(lGroup("Тінь під текстом",
    lSlider("Сила", 0, 100, 1, L.sh, v => v ? v + "%" : "без тіні", set("sh"), live("sh")),
    L.sh > 0 ? lSlider("М'якість", 0, 100, 1, L.ss, v => v < 15 ? "чітка" : v > 70 ? "дуже м'яка" : "м'яка", set("ss"), live("ss")) : null));
  grid.appendChild(lGroup("Фон під текстом",
    lSeg("Фон", [["Немає", "none"], ["Під рядком", "line"], ["Під кожним словом", "word"]], L.bg, set("bg")),
    L.bg !== "none" ? lColor("Колір фону", L.bc, set("bc"), live("bc")) : null,
    L.bg !== "none" ? lSlider("Прозорість", 0, 95, 1, 100 - L.bo, v => v + "%", v => setLook(k, "bo", 100 - v), v => setLook(k, "bo", 100 - v, null, true)) : null,
    L.bg !== "none" ? lSlider("Кути", 0, 60, 1, L.br, v => v ? "заокруглені, " + v + " px" : "чіткі", set("br"), live("br")) : null));
  if (k === "cap") grid.insertBefore(lGroup("Слово-акцент",
    lSeg("Як виділяти", [["Колір", "color"], ["Плашка", "box"], ["Підкреслення", "underline"], ["Велике", "big"], ["Ехо", "echo"]], L.acc.look, set("look", "acc")),
    lColor("Колір акценту", L.acc.a1, set("a1", "acc"), live("a1", "acc")),
    lChk("Чергувати з другим кольором", !!L.acc.a2, on => setLook(k, "a2", on ? (R.style.acc2 || R.style.acc) : null, "acc")),
    L.acc.a2 ? lColor("Другий колір акценту", L.acc.a2, set("a2", "acc"), live("a2", "acc")) : null), grid.children[1] || null);
  const foot = document.createElement("div"); foot.className = "lookfoot";
  const reset = document.createElement("button"); reset.type = "button"; reset.className = "b"; reset.textContent = "Повернути як у бренді"; reset.disabled = !lookPart(k);
  reset.addEventListener("click", () => { mutate(() => { if (k.startsWith("ov:")) { const ov = ovById(k.slice(3)); if (ov) delete ov.look; return; } const o = { ...(S.look || {}) }; delete o[k]; S.look = o; }); lookPreview(k); });
  if (k.startsWith("ov:")) reset.textContent = "Як решта тексту";
  foot.appendChild(reset);
  if (!k.startsWith("ov:")) foot.appendChild(lChk("Робити так у всіх наступних рілсах", (S.look || {}).keep, on => mutate(() => { S.look = { ...(S.look || {}), keep: on }; })));
  root.appendChild(foot);
}
function renderLooks() { if (!R) return; renderLook("cap", $("#caplook")); renderLook("hook", $("#hooklook")); renderLook("cta", $("#ctalook")); if (!$("#txtlookdet").hidden) renderLook("txt", $("#txtlook")); }
function txtFace(f) {   // same faces as the render: head = brand bold, body = brand regular, accent = italic serif
  const bold = Object.keys((R.fonts || {}).extra || {}).find(x => /bold/i.test(x));
  return f === "accent" ? { fontFamily: "ra, Georgia, serif", fontStyle: "italic", fontWeight: 400 } : f === "body" ? { fontFamily: "rb, var(--f-body)", fontWeight: 400, fontStyle: "normal" }
    : { fontFamily: bold ? "bf_" + bold.replace(/\W/g, "_") + ", rb, var(--f-body)" : "rb, var(--f-body)", fontWeight: bold ? 400 : 700, fontStyle: "normal" };
}
function lookAutoPx(k) {   // the size an added text gets from its frame when she hasn't set one
  if (k.startsWith("ov:")) { const o = ovById(k.slice(3)); return o ? ReelCore.autoPx(o.text, o.place || [90, 300, 900, 300]) : 120; }
  return ReelCore.autoPx($("#ovtext").value || "Текст", (placing && placing.place) || [90, 300, 900, 300]);
}
function txtEl(text, place, L) {   // a text they added, in its look (build_reel.py bigtext draws the same)
  const k = $("#player").clientWidth / 1080, el = document.createElement("div");
  const lines = text.split("/").map(x => x.trim()).filter(Boolean);   // her text exactly as she typed it (caps stay caps)
  const px = L.px || ReelCore.autoPx(text, place);
  Object.assign(el.style, { position: "absolute", left: 0, width: "100%", top: place[1] / 19.2 + "%", textAlign: "center", lineHeight: ".9", letterSpacing: "-.03em", pointerEvents: "none", ...txtFace(L.font) });
  for (const x of lines) {
    const d = document.createElement("div"); d.style.fontSize = px * k + "px"; d.style.whiteSpace = "nowrap";
    const piece = t => { const s = document.createElement("span"); s.style.cssText = lookBg(L, k); s.appendChild(lookRun(L, k, document.createTextNode(t))); return s; };
    if (L.bg === "word") x.split(/\s+/).forEach((w, i) => { if (i) d.appendChild(document.createTextNode(" ")); d.appendChild(piece(w)); }); else d.appendChild(piece(x));
    el.appendChild(d);
  }
  return el;
}
function accBefore(cap) { let n = 0; for (const c of CAPS) { if (c === cap) break; if (!c.gone) n += c.words.filter(w => w.accent).length; } return n; }
function fitCap(el) {   // shrink until the widest word fits the frame, measured in the real fonts (the render does the same)
  let fs = parseFloat(el.style.fontSize);
  for (let i = 0; i < 25 && el.scrollWidth > el.clientWidth + 1; i++) { fs *= 0.92; el.style.fontSize = fs + "px"; }
}
function highlight(c, cap) {
  $$(".card").forEach(el => { const g = GFX.find(x => x.id === el.dataset.id); el.classList.toggle("now", c != null && g && !g.gone && c >= g.start && c < g.end); });
  $$(".caprow").forEach(el => el.classList.toggle("now", !!cap && +el.dataset.ci === cap.ci));
  if (mode === "line" || mode === "rough") { const t = v.currentTime; $$(".w[data-i]").forEach(e => { const w = R.words[+e.dataset.i]; e.classList.toggle("now", t >= w.s && t < w.e); }); }
}

// ---------- 1. cuts ----------
function renderCuts() {
  const tx = $("#tx"); tx.textContent = "";
  const cut = new Set(S.cut || R.proposedCut), fb = new Set(S.restoredFillers);
  const pz = new Map(P.pauses.map(p => [p.after, p]));
  const sents = []; let cur = [];
  R.words.forEach((w, i) => { cur.push(i); if (/[.?!]$/.test(w.text) || i === R.words.length - 1) { sents.push(cur); cur = []; } });
  for (const idx of sents) {
    const row = document.createElement("div"); row.className = "sent";
    const ts = document.createElement("button"); ts.className = "ts"; ts.type = "button";
    ts.innerHTML = `<span class="src">${fmt(R.words[idx[0]].s)}</span>`; ts.title = "Слухати цей рядок з оригіналу";
    ts.addEventListener("click", () => playLine(R.words[idx[0]].s, R.words[idx[idx.length - 1]].e + 0.2));
    const ws = document.createElement("div"); ws.className = "words";
    for (const i of idx) {
      const w = R.words[i], s = document.createElement("span");
      s.className = "w" + (w.filler ? " filler" + (fb.has(i) ? " back" : "") : cut.has(i) ? " cut" : "");
      s.tabIndex = 0; s.setAttribute("role", "button"); s.dataset.i = i; s.textContent = w.text;
      s.title = w.filler ? (fb.has(i) ? "Слово-паразит залишено (тапни, щоб прибрати)" : "Слово-паразит прибрано автоматично (тапни, щоб залишити)") : "";
      ws.appendChild(s);
      const p = pz.get(i);
      if (p) {
        const b = document.createElement("button"); b.type = "button"; b.className = "pz" + (p.kept ? " kept" : "");
        b.textContent = `⏸ ${p.len.toFixed(2)}s ${p.kept ? "залишено" : "скорочено"}`;
        b.title = p.kept ? "Паузу залишено. Тапни, щоб скоротити" : "Паузу скорочено до ~0,1 с. Тапни, щоб залишити";
        b.addEventListener("click", () => mutate(() => {
          const keepDefault = (R.keepPauses || []).includes(i);
          S.restoredPauses = S.restoredPauses.filter(x => x !== i); S.trimmedPauses = S.trimmedPauses.filter(x => x !== i);
          if (p.kept) { if (keepDefault) S.trimmedPauses.push(i); } else if (!keepDefault) S.restoredPauses.push(i);
        }));
        ws.appendChild(b);
      }
    }
    row.append(ts, ws); tx.appendChild(row);
  }
  const words = [...cut].length, fills = R.words.filter((w, i) => w.filler && !fb.has(i)).length, pt = P.pauses.filter(p => !p.kept).length;
  $("#ctally").innerHTML = `<span>рілс <b>${fmt(P.cutDur)}</b></span><span>вирізано слів: <b>${words}</b></span><span>прибрано паразитів: <b>${fills}</b></span><span>скорочено пауз: <b>${pt}</b> з ${P.pauses.length}</span>`;
}
(function wireCuts() {
  const tx = $("#tx"); let drag = null;
  const toggle = (i, val) => { const set = new Set(S.cut || R.proposedCut); val ? set.add(i) : set.delete(i); S.cut = [...set].sort((a, b) => a - b); };
  tx.addEventListener("pointerdown", e => {
    const w = e.target.closest(".w"); if (!w) return; e.preventDefault();
    const i = +w.dataset.i;
    if (R.words[i].filler) { mutate(() => { const fb = new Set(S.restoredFillers); fb.has(i) ? fb.delete(i) : fb.add(i); S.restoredFillers = [...fb]; }); return; }
    undo.push(JSON.stringify(S)); $("#undo").disabled = false;
    drag = { start: i, val: !(S.cut || R.proposedCut).includes(i), base: JSON.stringify(S.cut || R.proposedCut) };
    toggle(i, drag.val); recompute(); renderCuts();
  });
  tx.addEventListener("pointermove", e => {
    if (!drag) return;
    const w = document.elementFromPoint(e.clientX, e.clientY)?.closest?.(".w"); if (!w) return;
    S.cut = JSON.parse(drag.base); const j = +w.dataset.i, [lo, hi] = drag.start < j ? [drag.start, j] : [j, drag.start];
    for (let i = lo; i <= hi; i++) if (!R.words[i].filler) toggle(i, drag.val);
    recompute(); renderCuts();
  });
  window.addEventListener("pointerup", () => { if (drag) { drag = null; renderAll(); queueSave(); } });
  tx.addEventListener("keydown", e => {
    const w = e.target.closest(".w"); if (!w || (e.key !== "Enter" && e.key !== " ")) return; e.preventDefault();
    const i = +w.dataset.i;
    mutate(() => { if (R.words[i].filler) { const fb = new Set(S.restoredFillers); fb.has(i) ? fb.delete(i) : fb.add(i); S.restoredFillers = [...fb]; } else toggle(i, !(S.cut || R.proposedCut).includes(i)); });
  });
})();

// ---------- 2. graphics ----------
const LABEL = { k: "Залишити", c: "Змінити", d: "Прибрати" };
function placeText(g) {
  const [x, y, w, h] = g.place || [0, 0, 1080, 1920];
  if (w >= 1000 && h >= 1800) return "На весь екран";
  const mid = y + h / 2; return (mid < 700 ? "Вгорі, над головою" : mid < 1250 ? "Посередині" : "Внизу") + (w < 600 ? (x + w / 2 < 540 ? ", ліворуч" : ", праворуч") : "");
}
function renderGraphics() {
  const byTime = (a, b) => (!!a.gone - !!b.gone) || (a.start || 0) - (b.start || 0);   // cut-out ones last
  const all = [...GFX].sort(byTime), mine = all.filter(g => g.user);
  const own = all.filter(g => g.user || g.own).length;
  const n = cardList($("#cards"), all), m = cardList($("#ovcards"), mine); renderInspector();
  $("#gtally").innerHTML = `<span>усього: <b>${all.length}</b></span><span>твоїх: <b>${own}</b></span><span>від Claude: <b>${all.length - own}</b></span><span>змінити: <b>${n.c}</b></span><span>прибрати: <b>${n.d}</b></span>`;
  $("#otally").innerHTML = mine.length ? `<span>твоїх накладень: <b>${mine.length}</b></span>` : "";
  if (!mine.length) $("#ovcards").innerHTML = `<div class="empty">Накладень ще немає.</div>`;
}
const openLook = new Set();
function cardList(box, list) {
  box.textContent = ""; const n = { k: 0, c: 0, d: 0 };
  for (const g of list) {
    const st = (S.board[g.id] || {}).state || "k"; n[st]++;
    const el = document.createElement("div"); el.className = "card" + (st === "d" ? " dropped" : ""); el.dataset.id = g.id;
    const th = document.createElement("div");
    const tb = document.createElement("div"); tb.className = "thumb";
    if (g.storyUrl && !g.placed) {   // storyboard: their frame with this very graphic on it (scripts/storyboard.py), tap to see it big
      tb.classList.add("story"); tb.style.backgroundImage = `url(${JSON.stringify(g.storyUrl)})`; tb.title = "Так буде виглядати. Натисни, щоб збільшити";
      tb.addEventListener("click", () => showBig(g.storyUrl, g.kind)); th.append(tb);
    } else {
      if (g.thumbUrl) tb.style.backgroundImage = `url(${JSON.stringify(g.thumbUrl)})`;
      tb.appendChild(box_(g)); const ap = document.createElement("div"); ap.className = "approx"; ap.textContent = "Приблизно";
      th.append(tb, ap);
    }
    const body = document.createElement("div");
    const kind = document.createElement("div"); kind.className = "kind";
    const who = document.createElement("span"); who.className = "who" + (g.user || g.own ? " mine" : ""); who.textContent = g.user || g.own ? "твоє" : "від Claude";
    kind.append(who, document.createTextNode(g.kind));
    const what = document.createElement("div"); what.className = "what"; what.textContent = g.what;
    const meta = document.createElement("div"); meta.className = "meta";
    if (g.gone) meta.innerHTML = `<span class="warnline">Її рядок вирізано, тому ця графіка не з'явиться.</span>`;
    else {
      const t = document.createElement("button"); t.className = "ts"; t.type = "button"; t.innerHTML = `<span class="tc">${fmt(g.start)}</span>`;
      t.title = "Дивитись чорновий монтаж з цього місця"; t.addEventListener("click", () => playRough(g.start));
      meta.append(t);
      const d = document.createElement("span"); d.textContent = `${(g.end - g.start).toFixed(1)} с на екрані`; meta.append(d);
      const p = document.createElement("span"); p.textContent = placeText(g); meta.append(p);
      if (g.shifted) p.title = g.behind ? "Над головою, щоб було видно за тобою" : "Відсунуто, щоб не перекривати обличчя й субтитри";
      if (g.user && g.type !== "bigtext") { const fx = document.createElement("span"); fx.textContent = "ефект: " + ({ soft: "плавна поява", slide: "виліт збоку", polaroid: "полароїд", glass: "скло", zoom: "наближення" }[g.effect] || g.effect); meta.append(fx); }
      if (g.user || ["title", "bigtext", "card", "tag", "cta"].includes(g.type)) {   // their overlays, and Claude's text cards (the hook first of all), can be dragged
        const mvb = document.createElement("button"); mvb.type = "button"; mvb.className = "b quiet"; const on = placing?.id === g.id;
        mvb.textContent = on ? "Готово" : "Перемістити"; mvb.title = "Перетягни рамку на відео, щоб змінити місце";
        mvb.addEventListener("click", () => { if (on) stopPlacing(); else { setPos(g.start + 0.3); startPlacing(g.place, g.id); } }); meta.append(mvb); }
      if (g.afterHook) { const m = document.createElement("span"); m.className = "warnline"; m.textContent = "Стоїть одразу після хука: поки на екрані хук, іншої графіки немає."; meta.append(m); }
      if (g.moved) { const m = document.createElement("span"); m.className = "warnline"; m.textContent = "Її перше слово вирізано, тому вона зсунулась на наступне слово."; meta.append(m); }
    }
    const seg = document.createElement("div"); seg.className = "seg"; seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Рішення для " + g.kind);
    for (const k of ["k", "c", "d"]) {
      const b = document.createElement("button"); b.type = "button"; b.className = k; b.textContent = LABEL[k]; b.setAttribute("aria-pressed", st === k);
      b.addEventListener("click", () => { mutate(() => { S.board[g.id] = { ...(S.board[g.id] || {}), state: k }; }); if (k === "c") setTimeout(() => document.getElementById("note-" + g.id)?.focus(), 0); });
      seg.appendChild(b);
    }
    const acts = document.createElement("div"); acts.className = "acts"; acts.append(seg);
    const full = (g.place || [0, 0, 1080, 1920])[2] >= 1000 && (g.place || [0, 0, 1080, 1920])[3] >= 1800;
    if (!g.gone && (!full || g.behind)) {
      const bb = document.createElement("button"); bb.type = "button"; bb.className = "behindbtn"; bb.setAttribute("aria-pressed", !!g.behind);
      bb.innerHTML = `<span class="sw"></span>За мною`; bb.title = "Поставити за тебе: стане над головою, де його видно, субтитри на цей час опустяться";
      bb.addEventListener("click", () => mutate(() => { S.board[g.id] = { ...(S.board[g.id] || {}), behind: !g.behind }; })); acts.append(bb);
    }
    body.append(kind, what, meta, acts);
    if (g.user && g.type === "bigtext" && !g.gone) {   // change one added text's look later
      const det = document.createElement("details"); det.className = "lookdet"; det.open = openLook.has(g.id);
      det.innerHTML = `<summary>Вигляд цього тексту: шрифт, розмір, колір, контур, тінь, фон</summary><div></div>`;
      det.addEventListener("toggle", () => { if (det.open) { openLook.add(g.id); renderLook("ov:" + g.id, det.lastChild); lookPreview("ov:" + g.id); } else openLook.delete(g.id); });
      if (det.open) renderLook("ov:" + g.id, det.lastChild);
      body.appendChild(det);
    }
    if (st === "c") {
      const inp = document.createElement("input"); inp.type = "text"; inp.id = "note-" + g.id; inp.placeholder = "Що змінити?"; inp.value = (S.board[g.id] || {}).note || "";
      inp.addEventListener("input", () => { S.board[g.id] = { ...(S.board[g.id] || { state: "c" }), note: inp.value }; queueSave(); });
      body.appendChild(inp);
    }
    el.append(th, body); box.appendChild(el);
    if (box.id === "cards") el.addEventListener("click", e => { if (e.target.closest("button,input,select,textarea,summary,a,label")) return; tlSelect("g:" + g.id, true); $("#tl").scrollIntoView({ block: "center", behavior: "smooth" }); });
  }
  return n;
}
const box_ = g => box(g, false);

// ---------- overlays they upload: an image or video from the current rough-cut moment ----------
let assets = null;
// where an overlay goes: a box they drag on the player (1080x1920 frame units); size presets set its width and height
const ovMode = () => $("#ovfull").checked ? "full" : "box";
const OV_PLACE = { box: [600, 170, 400, 500], tiny: [760, 260, 200, 200], "small-r": [600, 170, 400, 500], "small-l": [80, 170, 400, 500], big: [90, 150, 900, 640], full: [0, 0, 1080, 1920], text: [40, 360, 1000, 280] };
const ovKind = () => document.querySelector('input[name="ovkind"]:checked').value;
document.querySelectorAll('input[name="ovkind"]').forEach(r => r.addEventListener("change", () => {
  const txt = ovKind() === "text"; $("#ovtextrow").hidden = !txt; $("#ovfilerow").hidden = txt; $("#ovsaverow").hidden = txt; $("#libbox").hidden = txt || !LIB.length; $("#txtlookdet").hidden = !txt; if (txt) renderLook("txt", $("#txtlook"));
  if (txt) { $("#ovbehind").checked = true; if (placing && !placing.id) { placing.place = [...OV_PLACE.text]; placing.img = null; overlay(pos); } }
}));
let placing = null;   // {place: [x, y, w, h], id?: overlay being moved, img?: preview of the chosen file}
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
function startPlacing(place, id, quiet) {
  stopPlay(); placing = { place: [...place], id, img: placing?.img }; const cv = cutVid(); if (cv) { mode = "cutvid"; v.currentTime = pos; } else { mode = "roughPaused"; $("#clock").hidden = false; v.currentTime = P.toSrc(pos); }
  overlay(pos); renderGraphics();
  if (id && !quiet) setTimeout(() => $("#player").scrollIntoView({ block: "center" }), 0);   // narrow screens: the player is not sticky, bring it to the box
}
function fitToImage(url) {   // the box takes the picture's proportions, so nothing gets cropped
  if (!url || !placing) return;
  const im = new Image(); im.onload = () => {
    if (!placing || !im.naturalWidth) return;
    const p = placing.place; if (p[2] >= 1080 && p[3] >= 1920) return;
    const cx = p[0] + p[2] / 2, cy = p[1] + p[3] / 2, r = im.naturalHeight / im.naturalWidth;
    let w = p[2], h = Math.round(w * r); if (h > 1800) { h = 1800; w = Math.round(h / r); }
    placing.place = [Math.round(clamp(cx - w / 2, 0, 1080 - w)), Math.round(clamp(cy - h / 2, 0, 1920 - h)), w, h]; overlay(pos);
  }; im.src = url;
}
function stopPlacing() { placing = null; overlay(pos); renderGraphics(); }
function placeBox() {
  const p = placing.place, full = p[2] >= 1080 && p[3] >= 1920;
  const tx = !placing.id && ovKind() === "text" && $("#ovtext").value.trim();
  const el = box({ place: p, imgUrl: placing.img, kind: full ? "На весь екран" : tx ? "" : "Перетягни мене" }, true); el.classList.add("place");
  if (full) return el;
  el.addEventListener("pointerdown", e => {
    e.preventDefault(); el.setPointerCapture(e.pointerId);
    const k = 1080 / $("#player").clientWidth, sx = e.clientX, sy = e.clientY, x0 = p[0], y0 = p[1];
    const mv = ev => { p[0] = Math.round(clamp(x0 + (ev.clientX - sx) * k, 0, 1080 - p[2])); p[1] = Math.round(clamp(y0 + (ev.clientY - sy) * k, 0, 1920 - p[3]));
                       el.style.left = p[0] / 10.8 + "%"; el.style.top = p[1] / 19.2 + "%";
                       ov.querySelectorAll(".hookov.placing").forEach(h => { h.style.top = p[1] / 19.2 + "%"; h.style.transform = `translateX(${(p[0] - 90) / 10.8}%)`; }); };   // the hook / CTA text follows the frame
    const up = () => { el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up);
      if (placing?.id) { const id = placing.id, np = [...p]; mutate(() => { const o = (S.overlays || []).find(x => x.id === id);
        if (o) o.place = np; else S.board = { ...S.board, [id]: { ...(S.board[id] || {}), place: np } }; }); } };
    el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up);
  });
  if (p[2] < 300 || p[3] < 160) el.style.fontSize = "0";   // a sticker-sized box: no label, just the picture and the corner
  const rz = document.createElement("div"); rz.className = "rz"; rz.title = "Тягни, щоб змінити розмір"; el.appendChild(rz);
  rz.addEventListener("pointerdown", e => {   // the corner: any size from a sticker (~80 px) up to the whole frame
    e.preventDefault(); e.stopPropagation(); rz.setPointerCapture(e.pointerId);
    const k = 1080 / $("#player").clientWidth, sx = e.clientX, sy = e.clientY, w0 = p[2], h0 = p[3];
    const mv = ev => { p[2] = Math.round(clamp(w0 + (ev.clientX - sx) * k, 80, 1080 - p[0])); p[3] = Math.round(clamp(h0 + (ev.clientY - sy) * k, 80, 1920 - p[1]));
                       el.style.width = p[2] / 10.8 + "%"; el.style.height = p[3] / 19.2 + "%"; };
    const up = () => { rz.removeEventListener("pointermove", mv); rz.removeEventListener("pointerup", up);
      if (placing?.id) { const id = placing.id, np = [...p]; mutate(() => { const o = (S.overlays || []).find(x => x.id === id); if (o) o.place = np; }); } };
    rz.addEventListener("pointermove", mv); rz.addEventListener("pointerup", up);
  });
  return el;
}
$("#ovbox").addEventListener("toggle", () => { if (!R || tab !== "overlays") return; if ($("#ovbox").open) startPlacing(OV_PLACE[ovMode()]); else if (placing && !placing.id) stopPlacing(); });
$("#ovfull").addEventListener("change", () => {   // full screen on/off; any other size is the box they drag and resize
  const np = [...OV_PLACE[ovMode()]];
  if (placing) { placing.place = np; overlay(pos); } else startPlacing(np);
});
$("#ovtext").addEventListener("input", () => { if (placing && !placing.id) overlay(pos); });
$("#ovfile").addEventListener("change", () => { const f = $("#ovfile").files[0];
  if (placing) { placing.img = f && f.type.startsWith("image") ? URL.createObjectURL(f) : null; overlay(pos); fitToImage(placing.img); } });
function wordAtCut(c) {   // the kept word nearest this rough-cut moment: overlays hang on words so they move with the cut
  const src = P.toSrc(c); let best = null;
  for (const i of P.kept) if (!R.words[i].filler && (best === null || Math.abs(R.words[i].s - src) < Math.abs(R.words[best].s - src))) best = i;
  return best;
}
$("#ovadd").addEventListener("click", async () => {
  const msg = $("#ovmsg"), btn = $("#ovadd"), behindOn = $("#ovbehind").checked;
  if (ovKind() === "text") {   // big text, usually behind them: no file, nothing to upload
    const text = $("#ovtext").value.trim(); if (!text) { msg.textContent = "Впиши текст."; $("#ovtext").focus(); return; }
    const w0 = wordAtCut(pos); if (w0 === null) { msg.textContent = "Тут немає жодного слова в нарізці."; return; }
    const at = pos, dur = Math.min(30, Math.max(0.5, +$("#ovdur").value || 3));
    mutate(() => { S.overlays = [...(S.overlays || []), { id: "ov" + Date.now().toString(36), kind: "text", text, name: text, behind: behindOn, dur, w0, look: { ...((S.look || {}).txt || {}) },
      place: placing && !placing.id ? [...placing.place] : [...OV_PLACE.text] }]; });
    msg.textContent = `Текст додано з ${fmt(at)}.`; $("#ovtext").value = ""; return;
  }
  const f = $("#ovfile").files[0], pick = !f && libPick;
  if (!f && !pick) { msg.textContent = "Спершу вибери файл або щось із «Моїх файлів»."; $("#ovfile").focus(); return; }
  if (!assets) { msg.textContent = "Завантаження тут недоступне. Кинь файл у папку рілса й напиши Claude."; return; }
  if (f && f.size > 20 * 1024 * 1024) { msg.textContent = "Файл більший за 20 МБ. Кинь його в папку рілса й напиши Claude, на якій секунді."; return; }
  const w0 = wordAtCut(pos); if (w0 === null) { msg.textContent = "Тут немає жодного слова в нарізці."; return; }
  const at = pos, mode = ovMode(), effect = $("#oveffect").value, dur = Math.min(30, Math.max(0.5, +$("#ovdur").value || 3));
  btn.disabled = true; msg.textContent = "Завантажую…";
  try {
    const up = pick ? { id: pick.id, url: pick.url } : await assets.upload(f);
    const name = pick ? pick.name : f.name, kind = pick ? pick.kind : f.type.startsWith("video") ? "video" : "image";
    if (!pick && $("#ovsave").checked && libRef) await saveToLib({ id: up.id, url: up.url, name, kind });
    mutate(() => { S.overlays = [...(S.overlays || []), { id: "ov" + Date.now().toString(36), assetId: up.id, url: up.url, name,
      kind, mode, effect, dur, w0, behind: behindOn, place: placing && !placing.id ? [...placing.place] : OV_PLACE[mode] }]; });
    libPick = null; renderLib();
    msg.textContent = `Додано з ${fmt(at)}. Воно в списку нижче.`; $("#ovfile").value = "";
  } catch (e) { msg.textContent = "Не вдалося завантажити (" + (e?.code || "помилка") + "). Спробуй ще раз або кинь файл у папку рілса."; }
  finally { btn.disabled = false; }
});

// ---------- storyboard: a big view of one frame, and the hook options as pictures (reel.json "hookOptions": [{text, img}]) ----------
function showBig(url, label) {
  const d = document.createElement("div"); d.className = "bigview"; d.setAttribute("role", "dialog"); d.setAttribute("aria-label", label || "Кадр");
  const im = document.createElement("img"); im.src = url; im.alt = label || ""; d.appendChild(im);
  const close = () => { d.remove(); document.removeEventListener("keydown", esc); }; const esc = e => { if (e.key === "Escape") close(); };
  d.addEventListener("click", close); document.addEventListener("keydown", esc); document.body.appendChild(d);
}
function renderHookOpts() {
  const all = ((R && R.hookOptions) || []).filter(o => o.text); $("#hookoptbox").hidden = !all.length; if (!all.length) return;
  const box = $("#hookopts"), cur = ($("#hooktext").value || "").trim(); box.textContent = "";
  all.forEach((o, i) => {
    const b = document.createElement("button"); b.type = "button"; b.className = "hookopt"; b.setAttribute("aria-pressed", o.text.trim() === cur);
    if (o.img) { const im = document.createElement("img"); im.src = o.img; im.alt = ""; im.loading = "lazy"; b.appendChild(im); }
    const t = document.createElement("span"); t.textContent = String.fromCharCode(65 + i) + ": " + o.text.replace(/\s*\/\s*/g, " "); b.appendChild(t);
    b.addEventListener("click", () => { $("#hooktext").value = o.text; mutate(() => { S.hook = o.text; }); });
    box.appendChild(b);
  });
}

// ---------- «Стиль монтажу» on step 1: every style as a looping example to pick by look (style/list + reel.json "stylePreviews") ----------
function renderStyleGrid() {
  const box = $("#stylegrid1"); if (!box || !R) return; box.textContent = "";
  const SP = R.stylePreviews || {}, cur = S.style || "";
  const opts = [...STYLE_LIST.map(x => ({ n: x.name, t: x.title || x.name, w: x.what || "", u: x.url, p: x.posterUrl })),
    { n: "minimal", t: "Мінімал", w: "Нарізка, субтитри, хук, заклик і твої картинки, гіфки чи меми. Без анімацій від Claude.", u: SP.minimal },
    { n: "brand", t: "Тільки бренд", w: "Твої кольори й шрифти, фірмові картки й списки, спокійно й впізнавано.", u: SP.brand },
    { n: "mix", t: "Без стилю: мікс ефектів", w: "Ефекти з усієї бібліотеки, щоразу інші: два рілси не схожі.", u: SP.mix }];
  for (const o of opts) {
    const b = document.createElement("button"); b.type = "button"; b.className = "stpick"; b.setAttribute("aria-pressed", o.n === cur);
    if (o.u) { const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.preload = "none"; if (o.p) v.poster = o.p;
      v.dataset.src = o.u; manObs.observe(v); b.appendChild(v); }
    const t = document.createElement("b"); t.textContent = o.t; const w = document.createElement("span"); w.textContent = o.w; b.append(t, w);
    b.addEventListener("click", () => mutate(() => { S.style = o.n; }));
    box.appendChild(b);
  }
}

// ---------- reference reels by link (S.refs), import prints REFERENCE: <url> ----------
function renderRefs() {
  const box = $("#reflist"); if (!box) return; box.textContent = "";
  for (const u of S.refs || []) {
    const r = document.createElement("div"); r.className = "manrow"; const a = document.createElement("span"); a.textContent = u; a.style.wordBreak = "break-all";
    const x = document.createElement("button"); x.type = "button"; x.className = "b quiet"; x.textContent = "Прибрати";
    x.addEventListener("click", () => mutate(() => { S.refs = (S.refs || []).filter(v => v !== u); })); r.append(a, x); box.appendChild(r);
  }
}
$("#refadd").addEventListener("click", () => { const u = $("#refurl").value.trim();
  if (!/^https?:\/\/\S+$/.test(u)) { $("#refurl").focus(); return; }
  mutate(() => { S.refs = [...new Set([...(S.refs || []), u])]; }); $("#refurl").value = ""; });

// ---------- «Мої марки»: graphics their finished reels kept (reel.json "stamps": [{key, ua, uses, img}]) ----------
function renderStamps() {
  const all = (R && R.stamps) || []; $("#stamplib").hidden = !all.length; if (!all.length) return;
  $("#stampcount").textContent = all.length; const box = $("#stamplist"); box.textContent = "";
  for (const m of all) {
    const b = document.createElement("button"); b.type = "button"; b.className = "capopt"; b.title = "На цю секунду";
    if (m.img) { const im = document.createElement("img"); im.src = m.img; im.alt = ""; im.loading = "lazy"; im.style.cssText = "width:100%;aspect-ratio:9/16;object-fit:cover;border-radius:8px"; b.appendChild(im); }
    const t = document.createElement("span"); t.textContent = m.ua + (m.uses > 1 ? ` · ×${m.uses}` : ""); b.appendChild(t);
    b.addEventListener("click", () => { $("#eftext").value = `моя марка ${m.key}: ${m.ua}. `; $("#efbox").scrollIntoView({ behavior: "smooth", block: "center" });
      $("#eftext").focus(); $("#efmsg").textContent = "Допиши свої слова, перевір секунду й натисни «Додати»."; });
    box.appendChild(b);
  }
}

// ---------- «Анімація субтитрів»: a caption style from the catalog (reel.json "capStyles"), saved as S.capStyle -> edit.json "caption_style" ----------
function renderCapStyles() {
  const box = $("#capgrid"), all = (R && R.capStyles) || []; $("#capstylebox").hidden = !all.length; if (!all.length) return;
  const cur = S.capStyle || ""; box.textContent = "";
  const pick = all.find(x => x.n === cur); $("#capstylecur").textContent = pick ? "· " + pick.ua : "· мої субтитри";
  const bigList = all.filter(x => x.p).map(m => ({ ...m, acts: () => [[S.capStyle === m.n ? "✓ Обрано" : "Обрати цей стиль", () => mutate(() => { S.capStyle = m.n; }), S.capStyle !== m.n]] }));
  for (const m of [{ n: "", ua: "Мої субтитри (бренд)" }, ...all]) {
    const b = document.createElement("div"); b.setAttribute("role", "button"); b.tabIndex = 0; b.className = "capopt menuopt"; b.setAttribute("aria-pressed", m.n === cur);
    b.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); b.click(); } });
    if (m.p) bigBtn(b, () => openBig(bigList, all.filter(x => x.p).indexOf(m)));
    if (m.p) { const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.preload = "none"; v.dataset.src = m.p; manObs.observe(v); b.appendChild(v); }
    else { const d = document.createElement("div"); d.className = "capnone"; d.textContent = m.n ? "без прев'ю" : "як у бренді"; b.appendChild(d); }
    const t = document.createElement("span"); t.textContent = m.ua; b.appendChild(t);
    b.addEventListener("click", () => mutate(() => { if (m.n) S.capStyle = m.n; else delete S.capStyle; }));
    box.appendChild(b);
  }
}

// ---------- a preview opened big: tap ⤢ on any effect / caption-style card (arrows or ← → go through the same list) ----------
let BIG = null;
function openBig(list, i) {
  let d = $("#bigpv");
  if (!d) { d = document.createElement("dialog"); d.id = "bigpv"; d.setAttribute("aria-label", "Прев'ю на весь екран");
    d.innerHTML = `<div class="bigin"><button class="bigx" type="button" aria-label="Закрити">✕</button>
      <button class="bignav prev" type="button" aria-label="Попереднє">‹</button><video muted loop playsinline autoplay controls></video><button class="bignav next" type="button" aria-label="Наступне">›</button>
      <div class="bigcap"><b class="bigt"></b><div class="bigact"></div></div></div>`;
    document.body.appendChild(d);
    d.addEventListener("click", e => { if (e.target === d) d.close(); });
    d.querySelector(".bigx").addEventListener("click", () => d.close());
    d.querySelector(".prev").addEventListener("click", () => openBig(BIG.list, BIG.i - 1));
    d.querySelector(".next").addEventListener("click", () => openBig(BIG.list, BIG.i + 1));
    d.addEventListener("keydown", e => { if (e.key === "ArrowLeft") openBig(BIG.list, BIG.i - 1); if (e.key === "ArrowRight") openBig(BIG.list, BIG.i + 1); });
    d.addEventListener("close", () => d.querySelector("video").pause()); }
  list = list.filter(x => x.p); if (!list.length) return; i = (i + list.length) % list.length; BIG = { list, i }; const m = list[i];
  const v = d.querySelector("video"); if (v.getAttribute("src") !== m.p) v.src = m.p; v.play().catch(() => {});
  d.querySelector(".bigt").textContent = (m.no ? m.no + " · " : "") + m.ua + `  (${i + 1} з ${list.length})`;
  const act = d.querySelector(".bigact"); act.textContent = "";
  for (const [t, f, main] of (m.acts ? m.acts() : [])) { const b = document.createElement("button"); b.type = "button"; b.className = main ? "b" : "b quiet"; b.textContent = t;
    b.addEventListener("click", () => { f(); if (d.open) openBig(BIG.list, BIG.i); }); act.appendChild(b); }
  d.querySelectorAll(".bignav").forEach(b => b.hidden = list.length < 2);
  if (!d.open) d.showModal();
}
function bigBtn(card, open) {
  const b = document.createElement("button"); b.type = "button"; b.className = "menubig"; b.textContent = "⤢"; b.title = "Подивитися більше"; b.setAttribute("aria-label", "Подивитися більше");
  b.addEventListener("click", e => { e.stopPropagation(); open(); }); card.appendChild(b);
}

// ---------- «Тільки вручну»: catalog effects Claude never suggests on its own (reel.json "manual"), one tap puts one on this second ----------
const manObs = new IntersectionObserver(es => { for (const e of es) { const v = e.target;   // previews load and play only while on screen
  if (e.isIntersecting) { if (!v.src) v.src = v.dataset.src; v.play().catch(() => {}); } else v.pause(); } }, { rootMargin: "200px" });
let MENU_F = "all";
function renderManual() {
  const box = $("#manlist"), all = (R && R.manual) || []; $("#manlib").hidden = !all.length; if (!all.length) return;
  const fb = $("#menufilter"); fb.textContent = "";
  for (const [k, t] of [["all", "Усі"], ["a", "Claude пропонує"], ["m", "Тільки вручну"], ["mine", "Мій вибір"]]) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.setAttribute("aria-pressed", MENU_F === k);
    b.addEventListener("click", () => { MENU_F = k; renderManual(); }); fb.appendChild(b); }
  const picks = new Set(S.picks || []), q = ($("#mansearch").value || "").trim().toLowerCase();
  const list = all.filter(m => (MENU_F === "all" || (MENU_F === "mine" ? picks.has(m.n) : (m.k || "m") === MENU_F))
                              && (!q || (/^\d+$/.test(q) ? String(m.no) === q : (m.no + " " + m.ua + " " + m.n + " " + m.g).toLowerCase().includes(q))));
  $("#mancount").textContent = list.length === all.length ? `${all.length}` : `${list.length} з ${all.length}`;
  const bk = $("#basket"); bk.hidden = !picks.size; bk.textContent = "";
  if (picks.size) { const t = document.createElement("span"); t.innerHTML = `<b>Мій вибір: ${picks.size}</b> · Claude поставить їх у рілс, коли натиснеш велику кнопку внизу`;
    const c = document.createElement("button"); c.type = "button"; c.className = "b quiet"; c.textContent = "Очистити";
    c.addEventListener("click", () => mutate(() => { delete S.picks; })); bk.append(t, c); }
  box.textContent = ""; let g = null, grid = null;
  const isPick = n => new Set(S.picks || []).has(n);
  const at = m => { $("#bigpv")?.close(); $("#eftext").value = m.no ? String(m.no) : `${m.n}: ${m.ua}`; efHint(); $("#efbox").scrollIntoView({ behavior: "smooth", block: "center" });
    $("#eftext").focus(); $("#efmsg").textContent = "Перевір секунду й натисни «Додати»."; };
  const bigList = list.filter(x => x.p).map(m => ({ ...m, acts: () => [[isPick(m.n) ? "✓ У моєму виборі · прибрати" : "Додати в мій вибір",
    () => mutate(() => { const p = new Set(S.picks || []); p.has(m.n) ? p.delete(m.n) : p.add(m.n); S.picks = [...p]; if (!S.picks.length) delete S.picks; }), !isPick(m.n)],
    ["⏱ На цю секунду", () => at(m)]] }));
  for (const m of list) {
    if (m.g !== g) { g = m.g; const h = document.createElement("h4"); h.textContent = g; grid = document.createElement("div"); grid.className = "capgrid"; box.append(h, grid); }
    const card = document.createElement("div"); card.className = "capopt menuopt"; card.setAttribute("role", "button"); card.tabIndex = 0;
    card.setAttribute("aria-pressed", picks.has(m.n)); card.title = picks.has(m.n) ? "Прибрати з мого вибору" : "Додати в мій вибір";
    if (m.p) { const v = document.createElement("video"); v.muted = true; v.loop = true; v.playsInline = true; v.preload = "none"; v.dataset.src = m.p; manObs.observe(v); card.appendChild(v); }
    else { const d = document.createElement("div"); d.className = "capnone"; d.textContent = "прев'ю ще готується"; card.appendChild(d); }
    const t = document.createElement("span"); if (m.no) { const no = document.createElement("b"); no.className = "menuno"; no.textContent = m.no; t.appendChild(no); } t.appendChild(document.createTextNode((picks.has(m.n) ? "✓ " : "") + m.ua)); card.appendChild(t);
    const at = document.createElement("button"); at.type = "button"; at.className = "menuat"; at.textContent = "⏱"; at.title = "На цю секунду";
    at.addEventListener("click", e => { e.stopPropagation(); $("#eftext").value = m.no ? String(m.no) : `${m.n}: ${m.ua}`; efHint(); $("#efbox").scrollIntoView({ behavior: "smooth", block: "center" });
      $("#eftext").focus(); $("#efmsg").textContent = "Перевір секунду й натисни «Додати»."; });
    card.appendChild(at);
    if (m.p) bigBtn(card, () => openBig(bigList, list.filter(x => x.p).indexOf(m)));
    const tog = () => mutate(() => { const p = new Set(S.picks || []); p.has(m.n) ? p.delete(m.n) : p.add(m.n); S.picks = [...p]; if (!S.picks.length) delete S.picks; });
    card.addEventListener("click", tog); card.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tog(); } });
    grid.appendChild(card);
  }
}
$("#mansearch").addEventListener("input", renderManual);

// ---------- effects they ask for: a moment, what to do (a library name or their words) and files for it ----------
function renderEffects() {
  const box = $("#eflist"); box.textContent = "";
  const list = [...(S.effects || [])].sort((a, b) => a.at - b.at);
  if (!list.length) return;
  for (const e of list) {
    const el = document.createElement("div"); el.className = "card"; el.style.gridTemplateColumns = "1fr";
    const body = document.createElement("div");
    const kind = document.createElement("div"); kind.className = "kind"; kind.textContent = "Ефект";
    const what = document.createElement("div"); what.className = "what"; what.textContent = e.text;
    const meta = document.createElement("div"); meta.className = "meta";
    const t = document.createElement("button"); t.className = "ts"; t.type = "button"; t.innerHTML = `<span class="tc">${fmt(e.at)}</span>`;
    t.title = "Дивитись чорновий монтаж з цього місця"; t.addEventListener("click", () => playRough(e.at)); meta.append(t);
    const d = document.createElement("span"); d.textContent = `${e.dur} с`; meta.append(d);
    const del = document.createElement("button"); del.type = "button"; del.className = "b quiet"; del.textContent = "Прибрати";
    del.addEventListener("click", () => mutate(() => { S.effects = S.effects.filter(x => x.id !== e.id); })); meta.append(del);
    body.append(kind, what, meta);
    if ((e.files || []).length) {
      const fl = document.createElement("div"); fl.className = "lib";
      for (const f of e.files) { const b = document.createElement("span"); b.className = "efthumb"; b.title = f.name;
        if (f.kind === "image") b.style.backgroundImage = `url(${JSON.stringify(f.url)})`; else b.textContent = "▶"; fl.appendChild(b); }
      body.appendChild(fl);
    }
    el.appendChild(body); box.appendChild(el);
  }
}
function efNums() {   // the field holds only menu numbers ("12" or "5, 10 20"): the effects they stand for
  const t = $("#eftext").value.trim(); if (!/^[№#\s\d,;]+$/.test(t) || !/\d/.test(t)) return null;
  const all = (R && R.manual) || []; return t.match(/\d+/g).map(x => ({ no: +x, m: all.find(m => m.no === +x) }));
}
function efHint() {
  const n = efNums(), h = $("#efhint"); if (!n) { h.textContent = ""; return; }
  h.textContent = n.map(x => x.m ? `№${x.no}: ${x.m.ua}` : `№${x.no}: такого номера немає`).join(" · ");
}
$("#eftext").addEventListener("input", efHint);
$("#eftext").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); $("#efadd").click(); } });
$("#efadd").addEventListener("click", async () => {
  const msg = $("#efmsg"), btn = $("#efadd"), nums = efNums();
  if (nums && nums.some(x => !x.m)) { msg.textContent = "Такого номера в меню немає."; $("#eftext").focus(); return; }
  const text = nums ? nums.map(x => `№${x.no} ${x.m.n}: ${x.m.ua}`).join("; ") : $("#eftext").value.trim();
  if (!text) { msg.textContent = "Опиши ефект або встав його назву."; $("#eftext").focus(); return; }
  const w0 = wordAtCut(pos); if (w0 === null) { msg.textContent = "Тут немає жодного слова в нарізці."; return; }
  const files = [...$("#effiles").files], at = pos, dur = Math.min(30, Math.max(0.5, +$("#efdur").value || 3));
  if (files.length && !assets) { msg.textContent = "Файли тут не завантажуються: кинь їх у папку рілса й напиши Claude."; return; }
  if (files.some(f => f.size > 20 * 1024 * 1024)) { msg.textContent = "Один з файлів більший за 20 МБ. Кинь його в папку рілса."; return; }
  btn.disabled = true; msg.textContent = files.length ? "Завантажую файли…" : "";
  try {
    const up = [];
    for (const f of files) { const u = await assets.upload(f); up.push({ id: u.id, url: u.url, name: f.name, kind: f.type.startsWith("video") ? "video" : "image" }); }
    mutate(() => { S.effects = [...(S.effects || []), { id: "ef" + Date.now().toString(36), w0, at: +at.toFixed(2), dur, text, files: up }]; });
    $("#eftext").value = ""; $("#effiles").value = ""; efHint(); msg.textContent = `Додано на ${fmt(at)}.`;
  } catch (e) { msg.textContent = "Не вдалося завантажити (" + (e?.code || "помилка") + "). Спробуй ще раз."; }
  finally { btn.disabled = false; }
});

// ---------- the editing style for this reel (db style/list, built on «Стиль»); saved as S.style, import writes <reel>/style.txt ----------
let STYLE_LIST = [], STYLE_DEFAULT = null;
function useDefaultStyle() {   // a reel with no style picked yet takes the one marked «Завжди цей»
  if (R && !S.style && STYLE_DEFAULT && STYLE_LIST.some(x => x.name === STYLE_DEFAULT) && !B?.url) { S.style = STYLE_DEFAULT; recompute(); renderAll(); queueSave(); }
}
function placeStyleTab() {   // no styles yet: «Мої стилі» stands out, it is the first thing to do
  const l = $("#stylelink"); l.classList.toggle("first", !STYLE_LIST.length); l.firstChild.textContent = STYLE_LIST.length ? "Мої стилі " : "Зібрати стиль ";
}
const SPEEDS = [[0.75, "Повільніше"], [1, "Як у стилі"], [1.3, "Швидше"]];
function renderSpeedPick() {
  const box = $("#speedpick"); if (!box) return; box.textContent = "";
  for (const [v, t] of SPEEDS) { const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.setAttribute("aria-pressed", (S.speedMul || 1) === v);
    b.addEventListener("click", () => mutate(() => { if (v === 1) delete S.speedMul; else S.speedMul = v; })); box.appendChild(b); }
}
function renderStylePick() {
  renderSpeedPick();
  const box = $("#stylepick"); if (!box) return; box.textContent = "";
  const cur = S.style || null, opts = [...STYLE_LIST.map(x => [x.name, x.title || x.name, x.what || ""]), ["minimal", "Мінімал", "Субтитри, хук, заклик і твої картинки чи гіфки. Без анімацій від Claude"], ["brand", "Тільки бренд", "Кольори й шрифти бренду, без стилю"], ["mix", "Без стилю: мікс ефектів", "Без стилю: графіка з усієї бібліотеки ефектів, щоразу інші анімації"]];
  for (const [name, title, what] of opts) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = title; b.title = what; b.setAttribute("aria-pressed", cur === name);
    b.addEventListener("click", () => mutate(() => { S.style = cur === name ? null : name; })); box.appendChild(b);
  }
  const pick = STYLE_LIST.find(x => x.name === cur);
  { const o = opts.find(x => x[0] === cur), sp = SPEEDS.find(x => x[0] === (S.speedMul || 1));
    $("#stylecur").textContent = "· " + (o ? o[1] : "не обрано") + (S.speedMul ? " · " + sp[1].toLowerCase() : "");
    if (!cur && !$("#styledet").dataset.touched) $("#styledet").open = true; }
  const go = document.createElement("button"); go.type = "button"; go.className = "b quiet"; go.textContent = "Зібрати стилі"; go.addEventListener("click", () => showTab("style"));
  $("#stylehint").textContent = (!STYLE_LIST.length ? "Стилів ще немає. Збери їх на вкладці «Стиль» або монтуй тільки з брендом." : cur === "minimal" ? "Мінімал: нарізка, субтитри, хук і заклик, плюс те, що ти сама обереш у «Накладення → Знайти». Claude не додає анімацій." : cur === "brand" ? "Монтаж у кольорах і шрифтах бренду, без стилю: картки й списки бренду плюс кілька ефектів з бібліотеки." : cur === "mix" ? `Без стилю: Claude бере ефекти з бібліотеки (${R && R.libCount ? R.libCount : "понад 100"} анімацій, перевірених у вертикальному відео), щоразу інші, ніколи не повторює в одному рілсі. Кольори й шрифти бренду.` : pick ? pick.what : "Обери стиль до «Готово → Claude»: пропозиції графіки й звуки будуть у ньому.") + " ";
  if (STYLE_LIST.length) go.textContent = "Подивитись приклади стилів";
  $("#stylehint").appendChild(go);
  const box1 = $("#stylepick1"); if (!box1) return; box1.textContent = "";   // the same picker on step 1 («Стиль монтажу» tab)
  for (const [name, title, what] of opts) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = title; b.title = what; b.setAttribute("aria-pressed", cur === name);
    b.addEventListener("click", () => mutate(() => { S.style = cur === name ? null : name; })); box1.appendChild(b);
  }
  $("#stylehint1").textContent = $("#stylehint").firstChild ? $("#stylehint").firstChild.textContent : "";
  const go1 = go.cloneNode(true); go1.addEventListener("click", () => showTab("style")); $("#stylehint1").appendChild(go1);
}

// ---------- hook + CTA typed on the page ----------
function syncHookCta() {
  const hook = GFX.find(g => g.type === "title");
  $("#hooktext").value = S.hook != null ? S.hook : (hook?.text || "");
  $("#ctatext").value = (S.cta || {}).text || ""; $("#ctadur").value = (S.cta || {}).dur || 4;
}
$("#hookmove").addEventListener("click", () => {
  const g = GFX.find(x => x.type === "title" && !x.gone); if (!g) { $("#hookmovemsg").textContent = "Спершу впиши хук."; return; }
  if (placing?.id === g.id) { stopPlacing(); $("#hookmove").textContent = "Перемістити хук на відео"; $("#hookmovemsg").textContent = "Збережено."; return; }
  setPos(g.start + 0.3); startPlacing(g.place || [90, 1000, 900, 320], g.id);
  $("#hookmove").textContent = "Готово"; $("#hookmovemsg").textContent = "Тягни рамку на відео зліва.";
});
$("#styledet").addEventListener("toggle", () => { $("#styledet").dataset.touched = "1"; });
$("#hooktext").addEventListener("change", e => mutate(() => { S.hook = e.target.value.trim(); }));
const setCta = () => mutate(() => { const tx = $("#ctatext").value.trim(); S.cta = tx ? { text: tx, dur: Math.min(10, Math.max(2, +$("#ctadur").value || 4)) } : null; });
$("#ctatext").addEventListener("change", setCta); $("#ctadur").addEventListener("change", setCta);

// ---------- «Мої файли»: photos/videos kept on the page for every reel (db library/files) ----------
let libRef = null, LIB = [], libPick = null;
function renderLib() {
  const box = $("#lib"); box.textContent = ""; $("#libbox").hidden = !LIB.length;
  for (const it of LIB) {
    const b = document.createElement("button"); b.type = "button"; b.title = it.name; b.setAttribute("aria-pressed", libPick?.id === it.id);
    if (it.kind === "image") b.style.backgroundImage = `url(${JSON.stringify(it.url)})`; else b.textContent = "▶ " + it.name;
    b.addEventListener("click", () => { libPick = libPick?.id === it.id ? null : it; $("#ovfile").value = "";
      if (placing) { placing.img = libPick && libPick.kind === "image" ? libPick.url : null; overlay(pos); fitToImage(placing.img); } renderLib(); });
    box.appendChild(b);
  }
}
async function saveToLib(item) { LIB = [...LIB, item]; renderLib(); try { await libRef.set({ items: LIB, updatedAt: new Date().toISOString() }); } catch (e) { pill("Не вдалося зберегти в «Мої файли»", true); } }

// ---------- search & replace across captions ----------
$("#srgo").addEventListener("click", () => {
  const f = $("#srfind").value.trim(), r = $("#srrepl").value.trim(), msg = $("#srmsg");
  if (!f) { msg.textContent = "Впиши слово, яке шукаємо."; $("#srfind").focus(); return; }
  const esc = f.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), re = new RegExp(`(^|\\s)${esc}(?=$|\\s|[.,!?;:])`, "giu");
  let n = 0;
  mutate(() => { const arr = capsEditable();
    for (const c of CAPS) { if (c.gone) continue;
      const before = c.words.map(w => w.text).join(" "), after = before.replace(re, (m, sp) => { n++; return sp + r; });
      if (after !== before) { const cc = arr[c.ci], keep = after.split(/\s+/).length === c.words.length;
        cc.text = after; cc.accText = keep ? c.words.map((w, k) => w.accent ? k : -1).filter(k => k >= 0) : []; } } });
  msg.textContent = n ? `Замінено: ${n}` : "Такого слова в субтитрах немає.";
});

// ---------- 3. captions ----------
function capsEditable() { if (!S.captions) S.captions = JSON.parse(JSON.stringify(R.captions)); return S.captions; }
function renderCaptions() {
  const box = $("#caps"); box.textContent = "";
  const live = CAPS.filter(c => !c.gone);
  for (const c of CAPS) {
    const src = (S.captions || R.captions)[c.ci];
    const row = document.createElement("div"); row.className = "caprow" + (c.gone ? " gone" : ""); row.dataset.ci = c.ci;
    const ts = document.createElement("button"); ts.className = "ts"; ts.type = "button";
    const cw = document.createElement("div"); cw.className = "cw";
    if (c.gone) {
      ts.textContent = "вирізано"; ts.disabled = true;
      cw.textContent = src.text || src.w.map(i => R.words[i].text).join(" ");
      row.append(ts, cw, document.createElement("span")); box.appendChild(row); continue;
    }
    ts.innerHTML = `<span class="tc">${fmt(c.start)}</span>`; ts.addEventListener("click", () => playRough(c.start));
    c.words.forEach((w, k) => {
      const b = document.createElement("button"); b.type = "button"; b.className = "x" + (w.accent ? " acc" : ""); b.textContent = w.text;
      b.title = w.accent ? "Акцент (тапни, щоб зробити звичайним)" : "Тапни, щоб зробити акцентом";
      b.addEventListener("click", () => mutate(() => {
        const cc = capsEditable()[c.ci];
        if (cc.text) { const a = new Set(cc.accText || []); a.has(k) ? a.delete(k) : a.add(k); cc.accText = [...a]; }
        else { const a = new Set(cc.acc || []); a.has(w.i) ? a.delete(w.i) : a.add(w.i); cc.acc = [...a]; }
      }));
      cw.appendChild(b);
    });
    if (c.overlapFixed) { const f = document.createElement("span"); f.className = "flag"; f.textContent = "скорочено"; f.title = "Скорочено, щоб не накладався на наступний субтитр"; cw.appendChild(f); }
    const tools = document.createElement("div"); tools.className = "tools";
    const tool = (label, title, fn) => { const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.title = title; b.addEventListener("click", fn); tools.appendChild(b); };
    tool("правити", "Виправити текст", () => {
      const inp = document.createElement("input"); inp.type = "text"; inp.id = "cap-" + c.ci; inp.value = c.words.map(w => w.text).join(" ");
      let done = false;
      const finish = keep => { if (done) return; done = true; if (!keep) { renderCaptions(); return; }
        const val = inp.value.trim(), orig = src.w.filter(i => !P.removed(i)).map(i => R.words[i].text).join(" ");
        mutate(() => { const cc = capsEditable()[c.ci]; if (!val || val === orig) { delete cc.text; delete cc.accText; } else { cc.text = val; cc.accText = []; } }); };
      inp.addEventListener("keydown", e => { if (e.key === "Enter") finish(true); if (e.key === "Escape") finish(false); });
      inp.addEventListener("blur", () => finish(true));
      cw.replaceWith(inp); inp.focus();
    });
    tool("−0.1", "Почати на 0,1 с раніше", () => mutate(() => { const cc = capsEditable()[c.ci]; cc.nudge = +Math.max(-1, (cc.nudge || 0) - 0.1).toFixed(2); }));
    tool("+0.1", "Почати на 0,1 с пізніше", () => mutate(() => { const cc = capsEditable()[c.ci]; cc.nudge = +Math.min(1, (cc.nudge || 0) + 0.1).toFixed(2); }));
    const nextLive = live[live.indexOf(c) + 1];
    if (nextLive) tool("об'єднати", "Склеїти з наступним субтитром", () => mutate(() => {
      const arr = capsEditable(), a = arr[c.ci], b = arr[nextLive.ci];
      if (a.text || b.text) { a.text = [a.text || a.w.map(i => R.words[i].text).join(" "), b.text || b.w.map(i => R.words[i].text).join(" ")].join(" "); a.accText = []; }
      a.w = a.w.concat(b.w); a.acc = (a.acc || []).concat(b.acc || []); arr.splice(nextLive.ci, 1);
    }));
    if (src.w.length > 1) tool("роз'єднати", "Кожне слово окремим субтитром", () => mutate(() => {
      const arr = capsEditable(), a = arr[c.ci], parts = a.text ? a.text.split(/\s+/) : null, same = parts && parts.length === a.w.length;
      arr.splice(c.ci, 1, ...a.w.map((i, k) => ({ w: [i], acc: (a.acc || []).filter(x => x === i),
        ...(same ? { text: parts[k], accText: (a.accText || []).includes(k) ? [0] : [] } : {}), ...(k === 0 && a.nudge ? { nudge: a.nudge } : {}) })));
    }));
    row.append(ts, cw, tools); box.appendChild(row);
  }
  const acc = live.reduce((n, c) => n + c.words.filter(w => w.accent).length, 0);
  $("#captally").innerHTML = `<span>субтитрів: <b>${live.length}</b></span><span>вирізано разом зі словами: <b>${CAPS.length - live.length}</b></span><span>слів-акцентів: <b>${acc}</b></span>`;
}

// ---------- 4. sound & colour ----------
function renderSound() {
  const A = R.assets || {};
  { // one button: clean the voice or keep the original sound
    const vc = $("#voiceclean"), on = typeof S.voiceClean === "boolean" ? S.voiceClean : R.cleanVoice !== false; vc.textContent = "";   // untouched = the brand's setting
    const seg = document.createElement("div"); seg.className = "seg"; seg.setAttribute("role", "group"); seg.setAttribute("aria-label", "Чистка голосу");
    for (const [cls, val, label] of [["k", true, "Чистити голос"], ["d", false, "Залишити звук як є"]]) {
      const b = document.createElement("button"); b.type = "button"; b.className = cls; b.textContent = label; b.setAttribute("aria-pressed", on === val);
      b.addEventListener("click", () => mutate(() => { S.voiceClean = val; })); seg.appendChild(b);
    }
    vc.appendChild(seg);
  }
  const fig = (label, el) => { const f = document.createElement("figure"); const c = document.createElement("figcaption"); c.textContent = label; f.append(c, el); return f; };
  const au = u => { const a = document.createElement("audio"); a.controls = true; a.preload = "none"; a.src = u; return a; };
  const im = (u, alt) => { const i = document.createElement("img"); i.src = u; i.alt = alt; return i; };
  $("#audio").replaceChildren(...(A.audioOriginal ? [fig("Оригінал", au(A.audioOriginal)), fig("Після чистки", au(A.audioCleaned))] : [Object.assign(document.createElement("div"), { className: "empty", textContent: "Для цього рілса ще немає порівняння звуку." })]));
  if (A.colourBefore) {
    const cv = document.createElement("canvas"); cv.setAttribute("aria-label", "Той самий кадр після кольорокорекції");
    $("#colour").replaceChildren(fig("Оригінал", im(A.colourBefore, "Кадр до кольорокорекції")), fig("Після корекції", cv));
    gAfterGL = glFor(cv); gAfter = new Image(); gAfter.onload = () => gAfterGL && gAfterGL.draw(gAfter, ReelCore.gradeParams(curGrade())); gAfter.src = A.colourBefore;
  } else $("#colour").textContent = "";
  renderGrade();
  const cues = $("#cues"); cues.textContent = "";
  const lib = sfxLib(), names = Object.keys(lib);
  for (const g of GFX.filter(g => g.sfx && !g.gone && g.state !== "d")) {
    const off = !!S.sfxOff[g.id], cur = (S.sfxSwap || {})[g.id] || g.sfx.name;
    const row = document.createElement("div"); row.className = "cue" + (off ? " off" : "");
    const t = document.createElement("span"); t.className = "tc"; t.textContent = fmt(g.start);
    const w = document.createElement("span"); w.className = "what"; w.textContent = g.kind;
    const ctl = document.createElement("span"); ctl.className = "ctl";
    const sel = document.createElement("select"); sel.className = "sfxsel"; sel.setAttribute("aria-label", "Звук для " + g.kind);
    const groups = {}; for (const n of new Set([cur, ...names])) (groups[(lib[n] || {}).cat || "Інше"] ||= []).push(n);
    for (const [cat, ns] of Object.entries(groups)) { const og = document.createElement("optgroup"); og.label = cat;
      for (const n of ns) { const o = document.createElement("option"); o.value = n; o.textContent = (lib[n] || {}).label || n; o.selected = n === cur; og.appendChild(o); } sel.appendChild(og); }
    sel.addEventListener("change", () => { playSfx(sel.value, g.sfx.db); mutate(() => { S.sfxSwap = { ...(S.sfxSwap || {}) }; if (sel.value === g.sfx.name) delete S.sfxSwap[g.id]; else S.sfxSwap[g.id] = sel.value; }); });
    const play = document.createElement("button"); play.type = "button"; play.className = "b quiet"; play.textContent = "▶"; play.title = "Слухати";
    play.addEventListener("click", () => playSfx(sel.value, g.sfx.db));
    const tg = document.createElement("button"); tg.type = "button"; tg.className = "b quiet"; tg.textContent = off ? "Увімкнути" : "Вимкнути";
    tg.addEventListener("click", () => mutate(() => { if (off) delete S.sfxOff[g.id]; else S.sfxOff[g.id] = true; }));
    ctl.append(sel, play, tg); row.append(t, w, ctl); cues.appendChild(row);
  }
  if (!cues.children.length) cues.innerHTML = `<div class="empty">Звуків на графіці ще немає.</div>`;
  // the whole library to listen through, by category
  const det = document.createElement("details"); det.className = "sfxlib"; det.innerHTML = `<summary>Бібліотека звуків (${names.length})</summary>`;
  const byCat = {}; for (const n of names) (byCat[lib[n].cat || "Інше"] ||= []).push(n);
  for (const [cat, ns] of Object.entries(byCat)) {
    const g = document.createElement("div"); g.className = "ggroup"; g.innerHTML = `<div class="gtitle"></div>`; g.firstChild.textContent = cat;
    const row = document.createElement("div"); row.className = "gpre";
    for (const n of ns) { const b = document.createElement("button"); b.type = "button"; b.textContent = "▶ " + lib[n].label; b.addEventListener("click", () => playSfx(n)); row.appendChild(b); }
    g.appendChild(row); det.appendChild(g);
  }
  cues.appendChild(det);
}

// ---------- colour grade: iPhone-style sliders, previewed with WebGL using the render's exact maths (core.js gradeParams) ----------
const GRADE_UI = [["Світло", [["ex", "Експозиція"], ["hi", "Світлі ділянки"], ["sh", "Тіні"], ["co", "Контраст"], ["br", "Яскравість"]]],
  ["Колір", [["sa", "Насиченість"], ["vi", "Кольоровість"], ["wa", "Теплота"]]], ["Деталі", [["cl", "Чіткість"], ["sp", "Різкість"]]]];
const GRADE_PRESETS = [["Без корекції", {}], ["Природний", { ex: 5, sh: 15, co: 8, vi: 15, wa: 10 }], ["Теплий", { ex: 3, co: 10, sa: 5, vi: 20, wa: 35 }],
  ["Холодний", { sh: 10, co: 10, sa: -5, wa: -25 }], ["Яскравий", { ex: 8, hi: -15, sh: 20, co: 15, vi: 35, cl: 20 }]];
const curGrade = () => ReelCore.gradeNorm(S.grade && !("c" in S.grade) ? S.grade : {});   // {b,c,s,w} = the old 4-slider format: start fresh
function glFor(canvas) {   // one WebGL program: tone LUT -> saturation matrix -> vibrance -> clarity/sharpen (luma unsharp), like ffmpeg
  const gl = canvas.getContext("webgl", { premultipliedAlpha: false, preserveDrawingBuffer: true }); if (!gl) return null;
  const vs = "attribute vec2 p;varying vec2 v;void main(){v=vec2(p.x*.5+.5,.5-p.y*.5);gl_Position=vec4(p,0.,1.);}";
  const fs = `precision highp float;uniform sampler2D I,L;uniform mat3 M;uniform float V,C,S;uniform vec2 X;varying vec2 v;
    vec3 col(vec2 u){vec3 c=texture2D(I,u).rgb;c=vec3(texture2D(L,vec2(c.r*255./256.+.5/256.,.5)).r,texture2D(L,vec2(c.g*255./256.+.5/256.,.5)).g,texture2D(L,vec2(c.b*255./256.+.5/256.,.5)).b);
      c=clamp(M*c,0.,1.);float mx=max(c.r,max(c.g,c.b)),mn=min(c.r,min(c.g,c.b)),l=dot(c,vec3(.2126,.7152,.0722));float k=1.+V*(1.-sign(V)*(mx-mn));return clamp(l+(c-l)*k,0.,1.);}
    float Y(vec3 c){return dot(c,vec3(.2126,.7152,.0722));}
    void main(){vec3 c=col(v);float y=Y(c),d=0.;
      if(C>0.){float s=0.;for(int i=-3;i<=3;i++)for(int j=-3;j<=3;j++)s+=Y(col(v+vec2(float(i),float(j))*X*2.));d+=(y-s/49.)*C;}
      if(S>0.){float s=0.;for(int i=-2;i<=2;i++)for(int j=-2;j<=2;j++)s+=Y(col(v+vec2(float(i),float(j))*X));d+=(y-s/25.)*S;}
      gl_FragColor=vec4(clamp(c+d,0.,1.),1.);}`;
  const sh = (t, src) => { const o = gl.createShader(t); gl.shaderSource(o, src); gl.compileShader(o); return o; };
  const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, vs)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return null;
  gl.useProgram(pr);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer()); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const ap = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(ap); gl.vertexAttribPointer(ap, 2, gl.FLOAT, false, 0, 0);
  const tex = u => { const t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + u); gl.bindTexture(gl.TEXTURE_2D, t);
    for (const [k, val] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, val); return t; };
  const ti = tex(0), tl = tex(1); gl.uniform1i(gl.getUniformLocation(pr, "I"), 0); gl.uniform1i(gl.getUniformLocation(pr, "L"), 1);
  const U = n => gl.getUniformLocation(pr, n); let lastKey = "";
  return { draw(src, P) {
    const dpr = Math.min(2, devicePixelRatio || 1), w = Math.round(canvas.clientWidth * dpr), h = Math.round(canvas.clientHeight * dpr);
    if (!w || !h) return; if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
    gl.viewport(0, 0, w, h);
    const key = JSON.stringify(P.n); if (key !== lastKey) { lastKey = key;
      const b = new Uint8Array(256 * 4); P.lut.forEach((c, i) => { b[i * 4] = Math.round(c[0] * 255); b[i * 4 + 1] = Math.round(c[1] * 255); b[i * 4 + 2] = Math.round(c[2] * 255); b[i * 4 + 3] = 255; });
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, tl); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 256, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, b);
      const m = P.sat; gl.uniformMatrix3fv(U("M"), false, [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]]);
      gl.uniform1f(U("V"), P.vib); gl.uniform1f(U("C"), P.clar); gl.uniform1f(U("S"), P.sharp); gl.uniform2f(U("X"), 1 / 1080, 1 / 1920); }
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, ti);
    try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, src); } catch (e) { return; }
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  } };
}
let GV = null, gLoop = null, gAfter = null, gAfterGL = null;
function gradeView() {   // live graded video over the player while a grade is set (the built draft already has it baked in)
  const cv = $("#gcv"), on = tab !== "preview" && !cutVid() && !ReelCore.isNeutral(curGrade());   // the built videos have the grade baked in
  cv.hidden = !on; cancelAnimationFrame(gLoop);
  if (!on) return;
  if (!GV) GV = glFor(cv); if (!GV) { cv.hidden = true; return; }
  const P = ReelCore.gradeParams(curGrade());
  const tick = () => { if (v.readyState >= 2) GV.draw(v, P); gLoop = requestAnimationFrame(tick); }; tick();
  if (gAfter && gAfter.complete && gAfterGL) gAfterGL.draw(gAfter, P);
}
function renderGrade() {
  const g = curGrade(), box = $("#gradebox"); box.textContent = "";
  for (const [title, rows] of GRADE_UI) {
    const grp = document.createElement("div"); grp.className = "ggroup";
    const t = document.createElement("div"); t.className = "gtitle"; t.textContent = title;
    const grid = document.createElement("div"); grid.className = "ggrid";
    for (const [k, name] of rows) {
      const row = document.createElement("label"); row.className = "gs" + (g[k] ? " on" : "");
      const min = k === "cl" || k === "sp" ? 0 : -100;
      row.innerHTML = `<span class="gl"></span><span class="gv"></span><input type="range" min="${min}" max="100" step="1">`;
      row.querySelector(".gl").textContent = name; const val = row.querySelector(".gv"), inp = row.querySelector("input");
      const show = x => { val.textContent = x > 0 ? "+" + x : String(x); row.classList.toggle("on", !!+x); };
      inp.value = g[k]; inp.setAttribute("aria-label", name); show(g[k]);
      inp.addEventListener("input", () => { S.grade = { ...curGrade(), [k]: +inp.value }; show(+inp.value); gradeView(); markPresets(); });
      inp.addEventListener("change", () => mutate(() => { if (ReelCore.isNeutral(S.grade)) S.grade = null; }));
      row.querySelector(".gl").addEventListener("dblclick", e => { e.preventDefault(); mutate(() => { S.grade = { ...curGrade(), [k]: 0 }; if (ReelCore.isNeutral(S.grade)) S.grade = null; }); });
      grid.appendChild(row);
    }
    grp.append(t, grid); box.appendChild(grp);
  }
  const pre = $("#gradepre"); pre.textContent = "";
  for (const [name, p] of GRADE_PRESETS) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = name; b.dataset.p = JSON.stringify(ReelCore.gradeNorm(p));
    b.addEventListener("click", () => mutate(() => { S.grade = ReelCore.isNeutral(p) ? null : ReelCore.gradeNorm(p); })); pre.appendChild(b);
  }
  markPresets(); gradeView();
}
function markPresets() { const now = JSON.stringify(curGrade()); $$("#gradepre button").forEach(b => b.setAttribute("aria-pressed", b.dataset.p === now)); }

// ---------- sound library: the reel's own sounds plus «library/sfx» (kept on the page for every reel) ----------
let SFXLIB = [];
const SFX_LABEL = { whoosh: "Свіш", swish: "Шурх", pop: "Поп", snap: "Клац", chime: "Дзвіночок", typing: "Друк" };
function sfxLib() {
  const o = {}; if (!SFXLIB.length) for (const [n, u] of Object.entries((R && R.assets && R.assets.sfx) || {})) o[n] = { url: u, label: SFX_LABEL[n] || n };
  for (const it of SFXLIB) o[it.name] = { url: it.url, label: it.label || SFX_LABEL[it.name] || it.name, cat: it.cat };
  return o;
}
function playSfx(name, db = -12) { const u = (sfxLib()[name] || {}).url; if (!u) return; const a = new Audio(u); a.volume = Math.min(1, Math.pow(10, (db + 8) / 20)); a.play().catch(() => {}); }

// ---------- references for a section: pictures or videos of what she likes («як тут»), up to 5 per section ----------
function renderRefs() {
  const box = $("#reflist"); if (!box) return; box.textContent = "";
  const list = (S.refs || {})[tab] || [];
  $("#reffile").hidden = !assets || list.length >= 5; $(".reflabel").hidden = !assets && !list.length;
  list.forEach((f, k) => {
    const b = document.createElement("button"); b.type = "button"; b.title = f.name + " (тапни, щоб прибрати)";
    if (f.kind === "image") b.style.backgroundImage = `url(${JSON.stringify(f.url)})`; else b.textContent = "▶ " + f.name;
    b.addEventListener("click", () => mutate(() => { S.refs = { ...(S.refs || {}) }; S.refs[tab] = list.filter((_, j) => j !== k); }));
    box.appendChild(b);
  });
}
$("#reffile").addEventListener("change", async e => {
  const files = [...e.target.files], msg = $("#refmsg"), have = ((S.refs || {})[tab] || []).length;
  if (!files.length || !assets) return;
  if (have + files.length > 5) { msg.textContent = "Можна до 5 файлів у розділі."; e.target.value = ""; return; }
  if (files.some(f => f.size > 20 * 1024 * 1024)) { msg.textContent = "Файл більший за 20 МБ: кинь його Claude в чат."; e.target.value = ""; return; }
  msg.textContent = "Завантажую…"; const t = tab;
  try {
    const up = [];
    for (const f of files) { const u = await assets.upload(f); up.push({ id: u.id, url: u.url, name: f.name, kind: f.type.startsWith("video") ? "video" : "image" }); }
    mutate(() => { S.refs = { ...(S.refs || {}) }; S.refs[t] = [...(S.refs[t] || []), ...up]; });
    msg.textContent = "Додано."; renderRefs();
  } catch (er) { msg.textContent = "Не вдалося завантажити (" + (er?.code || "помилка") + "). Спробуй ще раз."; }
  e.target.value = "";
});

// ---------- 5. preview ----------
function renderPublish() {
  const box = $("#igbox"); if (!box) return; box.hidden = !B?.final;
  if (B?.published) $("#igstate").innerHTML = `Опубліковано: <a href="${String(B.published).replace(/"/g, "")}" target="_blank" rel="noopener">відкрити в Instagram ↗</a>`;
  else $("#igstate").textContent = "";
  if (document.activeElement !== $("#igcap")) $("#igcap").value = S.igCaption || "";
}
function renderPreview() { renderPublish();
  if (P) $("#preveta").textContent = "~" + Math.max(4, Math.round((240 + P.cutDur * 2.2) / 60)) + " хв";
  const h = ReelCore.hash(decisions()), st = $("#bstate");
  st.className = "state";
  if (B?.url && B.hash === h) { st.textContent = `Чернетка актуальна (зібрано ${new Date(B.at).toLocaleString("uk-UA")}). Натисни play на відео.`; st.classList.add("ok"); }
  else if (B?.url) { st.textContent = "Чернетка застаріла: рішення змінились. Збери ще раз."; st.classList.add("out"); }
  else if (S.buildRequest?.hash === h) st.textContent = S.buildRequest.sent ? "Claude збирає чернетку (~6–15 хв). Прийде сповіщення, а тут відкриється відео." : "Запит збережено. Напиши Claude «збери чернетку».";
  else st.textContent = "Чернетку ще не зібрано.";
  const busy = stage().wait, fresh = B?.url && B.hash === h;
  $("#build").disabled = busy || fresh; $("#build").textContent = busy ? "Чернетка збирається…" : fresh ? "Чернетка актуальна" : "Зібрати чернетку";
  const revs = $("#revs"); revs.textContent = "";
  S.revisions.forEach((r, k) => {
    const row = document.createElement("div"); row.className = "rev";
    const t = document.createElement("button"); t.className = "ts"; t.type = "button"; t.innerHTML = `<span class="tc">${fmt(r.t)}</span>`;
    t.addEventListener("click", () => { if (B?.url) { v.currentTime = r.t; v.play().catch(() => {}); } });
    const x = document.createElement("span"); x.textContent = r.text;
    const del = document.createElement("button"); del.type = "button"; del.className = "b quiet"; del.textContent = "Видалити";
    del.addEventListener("click", () => mutate(() => S.revisions.splice(k, 1)));
    row.append(t, x, del); revs.appendChild(row);
  });
  if (!S.revisions.length) revs.innerHTML = `<div class="empty">Нотаток ще немає.</div>`;
}
$("#build").addEventListener("click", () => askStep("build"));
$("#igcap").addEventListener("input", e => { S.igCaption = e.target.value; queueSave(); });

// ---------- steps: 1 her edit -> 2 Claude's proposals -> 3 draft -> 4 final; one big button moves to the next ----------
// She presses it; the page saves, marks the request in her review doc and sends Claude a «Send to Claude» comment, which
// reaches the Claude session watching this page. Without that (no session / not an editor) it tells her the chat word.
let comments = null;
function stage() {
  if (B?.final) return { n: 4, wait: false };
  if (B?.url && S.finalRequest?.hash === B.hash) return { n: 4, wait: true };
  if (B?.url && S.fixRequest?.hash === B.hash && B.fixedFor !== S.fixRequest.at) return { n: 3, wait: true };   // notes sent: waiting for the draft that answers them (builds doc carries fixedFor)
  if (B?.url && S.buildRequest && S.buildRequest.hash !== B.hash && S.buildRequest.hash === ReelCore.hash(decisions())) return { n: 3, wait: true };   // asked to rebuild after a change
  if (B?.url) return { n: 3, wait: false };
  if (S.buildRequest) return { n: 3, wait: true };
  if ((R?.claudeRound || 0) > 0) return { n: 2, wait: false };
  if (S.graphicsRequest) return { n: 2, wait: true };
  return { n: 1, wait: false };
}
const STEP = {
  graphics: { title: "Віддати Claude на пропозиції?", yes: "Так, готово → Claude",
    body: () => `<p class="lede">Усе твоє збережено: нарізка, накладення, ефекти, хук, субтитри, колір.</p><ol>
      <li><b>Збере відео нарізки</b> (~2–3 хв): справжні склейки, щоб ти перевірила їх до графіки.</li>
      <li><b>Додасть графіку</b> у вибраному стилі: картки, motion на ключові фрази, лічильники. Твоє не чіпає й не перекриває.</li>
      <li><b>Сторінка оновиться сама</b> (~5–10 хв) і відкриє крок 2 «Нарізка і графіка». Потім одна кнопка: <b>Зібрати чернетку</b>.</li></ol>
      ${STYLE_LIST.length ? `<p class="lede" style="margin-top:4px"><b>Яким стилем монтуємо?</b></p><div class="gpre" id="mstylepick"></div>` : ""}`,
    say: "графіка", text: "▶ Кнопка «Готово → Claude»: мій монтаж готовий, зроби пропозиції графіки (раунд 2)." },
  build: { title: "Зібрати чернетку?", yes: "Так, збирай",
    body: `<p class="lede">Claude збере відео з усіма рішеннями: твоїми і погодженими пропозиціями.</p><ol>
      <li><b>Перевірить склейки й субтитри</b> до рендеру, щоб чернетка вже була чистою.</li>
      <li><b>Рендер ~6 хв.</b> Коли готово, прийде сповіщення, а тут відкриється «Чернетка».</li>
      <li>Ти дивишся й лишаєш нотатки на потрібних секундах. Погоджена чернетка = фінал.</li></ol>`,
    say: "збери чернетку", text: "▶ Кнопка «Зібрати чернетку»: збери чернетку." },
  fixes: { title: "Віддати нотатки Claude?", yes: "Так, виправляй",
    body: `<p class="lede">Claude виправить усе з твоїх нотаток і збере нову чернетку.</p>`,
    say: "виправ нотатки", text: "▶ Кнопка «Виправити за нотатками»: виправ нотатки до чернетки і збери нову." },
  publish: { title: "Опублікувати в Instagram?", yes: "Так, публікуй",
    body: () => `<p class="lede">Claude ще раз покаже в чаті акаунт і підпис і опублікує тільки після твого «так». Відео на годину стане доступне за тимчасовим посиланням (так вимагає Instagram), потім саме зникне.</p>
      <p class="lede"><b>Підпис:</b> ${((S.igCaption || "").trim() || "без підпису").replace(/[<&]/g, "")}</p>`,
    say: "опублікуй в інстаграм", text: "▶ Кнопка «Опублікувати в Instagram»: фінал погоджено, опублікуй рілс з моїм підписом." },
  final: { title: "Це фінал?", yes: "Так, це фінал",
    body: `<p class="lede">Claude перевірить звук і довжину й покладе готовий MP4 у папку Reels.</p>`,
    say: "фінал", text: "▶ Кнопка «Це фінал»: чернетка погоджена, видай фінал." },
};
function renderEta() {   // a rough clock for the draft: import + cut + precheck ~4 min, render ~2.2 s per second of reel at 540p (1 worker)
  const at = (S.fixRequest && S.fixRequest.hash === B?.hash && B?.fixedFor !== S.fixRequest.at) ? S.fixRequest.at : S.buildRequest?.at;
  if (!at || !P) return null;
  const total = Math.max(4, Math.round((240 + P.cutDur * 2.2) / 60)), done = Math.max(0, Math.round((Date.now() - Date.parse(at)) / 60000));
  return { done: Math.min(done, total + 5), total, pct: Math.min(95, Math.round(done / total * 100)) };
}
setInterval(() => { if (R && tab !== "style" && stage().wait) renderStage(); }, 30000);
function renderStage() {
  if (tab === "style") { styleBar(); return; }
  if (!R) return;
  const st = stage();
  $$("#steps .st").forEach(b => { const n = +b.dataset.s, sn = Math.min(st.n, 3); b.classList.toggle("done", n < sn || (st.n === 4 && !st.wait)); b.classList.toggle("next", n === sn); b.classList.toggle("locked", n > sn); b.title = n > sn ? "Ще не відкрито" : ""; });
  const bar = $("#gobar"), txt = $("#gotext"), btn = $("#gobtn"); bar.hidden = false; btn.disabled = false;
  const set = (t, sub, label, kind) => { txt.innerHTML = `<b>${t}</b><span class="sub">${sub}</span>`; btn.innerHTML = label; btn.dataset.kind = kind || ""; btn.disabled = !kind; };
  const newRevs = S.revisions.filter(r => B && r.hash === B.hash && !r.sent).length;
  if (st.n === 1) set("Крок 1 · твій монтаж", "Коли все своє зроблено, передай Claude.", "Готово → пропозиції Claude", "graphics");
  else if (st.n === 2 && st.wait) set("Claude готує пропозиції", "Сторінка оновиться сама. Можеш далі правити своє.", `<span class="spin"></span>Claude працює`);
  else if (st.n === 2) set("Крок 2 · пропозиції Claude", "На «Графіці» все з позначкою «від Claude»: залиш, зміни або прибери.", "Зібрати чернетку", "build");
  else if (st.n === 3 && st.wait) { const r = renderEta(); set("Claude збирає чернетку", r ? `Минуло ${r.done} хв з ~${r.total}. Сторінка відкриє «Чернетку» сама.` : "~6–10 хв. Сторінка відкриє «Чернетку» сама.", `<span class="spin"></span>${r ? r.pct + "%" : "Рендериться"}`); }
  else if (st.n === 3 && B?.url && B.hash !== ReelCore.hash(decisions())) set("Крок 3 · рішення змінились", "Чернетка зібрана до твоїх змін (стиль, нарізка, графіка). Збери її заново.", "Зібрати чернетку заново", "build");
  else if (st.n === 3 && newRevs) set("Крок 3 · чернетка", `Нотаток: ${newRevs}. Віддай їх Claude одним натиском.`, "Виправити за нотатками", "fixes");
  else if (st.n === 3) set("Крок 3 · чернетка", "Подивись чернетку. Є що змінити? Лиши нотатку на секунді.", "Це фінал", "final");
  else if (st.wait) set("Claude видає фінал", "Перевірка звуку, MP4 у папку Reels.", `<span class="spin"></span>Готується`);
  else if (B?.published) set("Опубліковано ✓", "Рілс в Instagram.", "Готово ✓");
  else if (S.publishRequest && !B?.published) set("Claude публікує", "Підтвердь акаунт і підпис у чаті.", `<span class="spin"></span>Публікується`);
  else set("Крок 4 · фінал", "Рілс готовий: MP4 у папці Reels. Можна одразу в Instagram.", "Опублікувати в Instagram", "publish");
}
$("#gobtn").addEventListener("click", () => { const k = $("#gobtn").dataset.kind; if (k === "style") askStyle(); else if (k === "tographics") { showTab("graphics"); scrollTo({ top: 0, behavior: "smooth" }); } else if (k) askStep(k); });
function missingNotes() {   // «Змінити» with no note: Claude would have to guess what to change
  return Object.entries(S.board || {}).filter(([id, b]) => b.state === "c" && !(b.note || "").trim()).map(([id]) => ({ id, kind: (GFX.find(g => g.id === id) || {}).kind || id }));
}
function askStep(kind) {
  const miss = (kind === "graphics" || kind === "build") ? missingNotes() : [];
  if (miss.length) {
    $("#mtitle").textContent = "Що саме змінити?";
    $("#mbody").innerHTML = `<p class="lede">Ти позначила «Змінити», але не написала що: ${miss.map(m => "<b>" + m.kind.replace(/[<&]/g, "") + "</b>").join(", ")}. Допиши коротко, і Claude зробить саме це.</p>`;
    $("#myes").textContent = "Дописати"; $("#mno").textContent = "Надіслати так";
    $("#myes").hidden = false; $("#modal").hidden = false; $("#myes").focus();
    $("#myes").onclick = () => { $("#modal").hidden = true; showTab("graphics"); setTimeout(() => { const i = document.getElementById("note-" + miss[0].id); if (i) { i.scrollIntoView({ block: "center" }); i.focus(); } }, 50); };
    $("#mno").onclick = () => { $("#mno").onclick = null; askStepGo(kind); };
    return;
  }
  askStepGo(kind);
}
function fillModalStyles() {   // the style is picked as she hands step 1 over (Claude makes the graphics in it)
  const box = document.getElementById("mstylepick"); if (!box) return; box.textContent = "";
  for (const [name, title] of [...STYLE_LIST.map(x => [x.name, x.title || x.name]), ["minimal", "Мінімал"], ["brand", "Тільки бренд"], ["mix", "Без стилю: мікс ефектів"]]) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = title; b.setAttribute("aria-pressed", S.style === name);
    b.addEventListener("click", () => { mutate(() => { S.style = name; }); fillModalStyles(); }); box.appendChild(b);
  }
}
function askStepGo(kind) {
  const c = STEP[kind]; $("#mtitle").textContent = c.title; $("#mbody").innerHTML = typeof c.body === "function" ? c.body() : c.body; $("#myes").textContent = c.yes; $("#mno").textContent = "Ще ні";
  $("#myes").hidden = false; $("#modal").hidden = false; $("#myes").focus();
  if (kind === "graphics") fillModalStyles();
  $("#myes").onclick = () => sendStep(kind);
}
$("#mno").addEventListener("click", () => { $("#modal").hidden = true; });
$("#modal").addEventListener("click", e => { if (e.target.id === "modal") $("#modal").hidden = true; });
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#modal").hidden = true; });
async function sendStep(kind) {
  const c = STEP[kind], at = new Date().toISOString();
  $("#myes").disabled = true;
  // the send must come from her click, so it goes first; the decision is saved either way
  let sent = false, why = "";
  try {
    const can = comments ? await comments.canSendToClaude() : "off";
    if (can === "available") { await comments.sendToClaude({ anchor: await comments.anchorFor($("#gobtn")), text: c.text }); sent = true; }
    else why = can;
  } catch (e) { why = e?.code || "error"; }
  mutate(() => {
    if (kind === "graphics") S.graphicsRequest = { at, sent, cutHash: cutHash(decisions()) };
    if (kind === "build") S.buildRequest = { hash: ReelCore.hash(decisions()), at, sent };
    if (kind === "fixes") { S.revisions.forEach(r => { if (B && r.hash === B.hash) r.sent = true; }); S.fixRequest = { at, hash: B?.hash, sent }; S.buildRequest = null; }
    if (kind === "final") S.finalRequest = { at, hash: B?.hash, sent };
    if (kind === "publish") S.publishRequest = { at, sent, caption: (S.igCaption || "").trim() };
  });
  $("#myes").disabled = false;
  if (sent) { $("#modal").hidden = true; pill("Передано Claude"); }
  else {   // no Claude session listening right now: the request is saved, one chat word wakes Claude up
    $("#mtitle").textContent = "Збережено. Ще один крок";
    $("#mbody").innerHTML = `<p class="lede">Claude зараз не на зв'язку зі сторінкою${why === "writers_only" ? " (кнопка працює тільки для власниці сторінки)" : ""}. Напиши йому в чаті одне слово:</p><p style="font-size:22px;font-weight:700;margin:6px 0 14px">«${c.say}»</p>`;
    $("#myes").hidden = true; $("#mno").textContent = "Зрозуміло";
  }
  renderStage();
}
$("#revadd").addEventListener("click", () => {
  const text = $("#revtext").value.trim(); if (!text) { $("#revtext").focus(); return; }
  if (!B?.url) { pill("Спочатку збери чернетку, потім додавай нотатки до моментів у ній.", true); return; }
  mutate(() => { S.revisions.push({ t: +v.currentTime.toFixed(2), text, hash: B.hash }); S.revisions.sort((a, b) => a.t - b.t); }); $("#revtext").value = "";
});

// ---------- timeline: every graphic as a block on its track; drag = move (snaps to the nearest kept word), edge = longer/shorter,
// tap = select, ✕ = remove. Writes the same decisions the cards do: board[id].w0 / .dur, overlay.w0 / .dur, effect.w0 / .dur, cta.dur
let TLSEL = null;
const TL_TABS = ["graphics", "preview"];   // step 2: edit; step 3: the same timeline with the draft notes as pins   // only once Claude's proposals are there: before that the timeline holds just the hook
function placeTimeline(t) {
  const el = $("#tl"); if (!el) return;
  if (!TL_TABS.includes(t) || !R) { el.hidden = true; return; }
  const sec = document.querySelector(`section[data-p="${t}"]`), lede = sec && sec.querySelector(".lede");
  if (t === "preview") { const st = $("#bstate"); if (st && el.previousElementSibling !== st) st.after(el); el.hidden = !B?.url; renderTimeline(); return; }
  const insp = t === "graphics" && $("#insp");
  if (insp) { if (el.nextElementSibling !== insp) insp.before(el); }   // step 2: the timeline sits right above the picked element's panel
  else if (lede && el.previousElementSibling !== lede) lede.after(el);
  el.hidden = false; renderTimeline();
}
function tlItems() {
  const items = [];
  for (const g of GFX) {
    if (g.gone) continue;
    const track = g.type === "title" || g.type === "cta" ? 0 : g.type === "camera" ? 3 : g.user ? 2 : 1;
    items.push({ key: "g:" + g.id, track, start: g.start, end: g.end, label: g.kind + ((g.text || g.title) ? ": " + String(g.text || g.title).replace(/\s*\/\s*/g, " ") : ""),
                 off: g.state === "d", kind: g.id === "cta" ? "cta" : g.user ? "ov" : "board", id: g.id });
  }
  if (!((S.cta || {}).text || "").trim()) items.push({ key: "cta:new", track: 0, start: Math.max(0, P.cutDur - 4), end: P.cutDur, label: "+ CTA", kind: "ctanew", ghost: true });
  if (tab === "preview") (S.revisions || []).forEach((r, k) => items.push({ key: "n:" + k, track: 4, start: r.t, end: r.t + 0.2, label: r.text, kind: "note", pin: true }));
  for (const e of S.effects || []) { const w = R.words[e.w0]; if (!w || P.removed(e.w0)) continue; const st = P.toCut(w.s);
    items.push({ key: "e:" + e.id, track: 2, start: st, end: Math.min(st + (e.dur || 3), P.cutDur), label: "Ефект: " + e.text, kind: "ef", id: e.id }); }
  return items;
}
const TL_TRACKS = ["Хук і CTA", "Від Claude", "Твоє", "Камера"];
function renderTimeline() {
  const el = $("#tl"); if (!el || el.hidden || !P) return;
  const D = P.cutDur, items = tlItems(), pct = t => (t / D * 100).toFixed(3) + "%";
  el.innerHTML = `<div class="tlhead"><b>Таймлайн</b><span class="mode">Тягни блок, щоб змістити. Тягни край, щоб подовжити. Тапни, щоб обрати й прибрати.</span></div>
    <div class="tlbody"><div class="tlrow tlruler"><span></span><div class="tllane" data-ruler></div></div></div>`;
  const body = el.querySelector(".tlbody"), ruler = el.querySelector("[data-ruler]");
  const narrow = el.clientWidth < 520;
  for (let t = 0; t <= D; t += D > 40 ? 5 : narrow ? (D > 20 ? 5 : 2) : D > 20 ? 2 : 1) { const m = document.createElement("span"); m.className = "tltick"; m.style.left = pct(t); m.textContent = Math.round(t) + "с"; ruler.appendChild(m); }
  ruler.addEventListener("pointerdown", tlScrub);
  (tab === "preview" ? [...TL_TRACKS, "Нотатки"] : TL_TRACKS).forEach((name, k) => {
    const row = document.createElement("div"); row.className = "tlrow";
    row.innerHTML = `<span class="tllab"></span><div class="tllane"></div>`; row.firstChild.textContent = name;
    const lane = row.lastChild; lane.addEventListener("pointerdown", e => { if (e.target === lane) tlScrub(e); });   // empty spot on a track: scrub too
    for (const it of items.filter(x => x.track === k)) {
      const b = document.createElement("div"); b.className = "tlb t" + k + (it.off ? " off" : "") + (it.ghost ? " ghost" : "") + (it.pin ? " pin" : "") + (TLSEL === it.key ? " sel" : "");
      b.style.left = pct(it.start); b.style.width = pct(Math.max(0.2, it.end - it.start)); b.title = `${it.label} · ${fmt(it.start)}–${fmt(it.end)}`;
      const lab = document.createElement("span"); lab.textContent = it.label; b.appendChild(lab);
      if (it.pin) { b.title = `${fmt(it.start)} · ${it.label}`; b.addEventListener("click", () => tlGo(it.start)); lane.appendChild(b); continue; }
      if (!it.off && !it.ghost) { const h = document.createElement("i"); h.className = it.kind === "cta" ? "lh" : "rh"; h.title = "Тягни, щоб змінити тривалість"; b.appendChild(h); }
      tlDrag(b, it, lane);
      lane.appendChild(b);
    }
    body.appendChild(row);
  });
  const caps = document.createElement("div"); caps.className = "tlrow"; caps.innerHTML = `<span class="tllab">Субтитри</span><div class="tllane thin"></div>`;
  for (const c of CAPS) if (!c.gone) { const s = document.createElement("i"); s.className = "tlcap"; s.style.left = pct(c.start); s.style.width = pct(Math.max(0.05, c.end - c.start)); caps.lastChild.appendChild(s); }
  body.appendChild(caps);
  const ph = document.createElement("div"); ph.className = "tlplay"; ph.id = "tlplay"; ph.title = "Тягни, щоб перемотати"; ph.addEventListener("pointerdown", tlScrub); body.appendChild(ph);
  tlPlayhead();
}
function tlScrub(e) {   // drag the playhead (or press the ruler / an empty track) to scrub: the frame above follows
  if (e.button) return;
  const lane = document.querySelector("#tl [data-ruler]"); if (!lane || !P) return;
  e.preventDefault(); e.stopPropagation();
  const el = e.currentTarget, r = lane.getBoundingClientRect(), at = x => Math.max(0, Math.min(1, (x - r.left) / r.width)) * P.cutDur;
  el.setPointerCapture(e.pointerId);
  if (cutVid() || tab === "preview") v.pause(); else if (mode === "rough") { stopPlay(); mode = "roughPaused"; }
  tlGo(at(e.clientX)); document.body.classList.add("scrubbing");
  const mv = ev => tlGo(at(ev.clientX));
  const up = () => { el.removeEventListener("pointermove", mv); el.removeEventListener("pointerup", up); el.removeEventListener("pointercancel", up); document.body.classList.remove("scrubbing"); };
  el.addEventListener("pointermove", mv); el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
}
function tlSelect(key, go) {
  TLSEL = key; renderTimeline(); renderInspector();
  const it = tlItems().find(x => x.key === key); if (go && it) tlGo(it.start + 0.05);
}
function keptWords() { return [...P.kept].filter(i => !R.words[i].filler).sort((a, b) => a - b); }
function renderInspector() {
  const insp = $("#insp"), holder = $("#holder"); if (!insp || !holder || !P) return;
  holder.append($("#hookbox"), $("#ctabox"));
  const items = tlItems();
  if (TLSEL === "cta:new" && items.some(x => x.key === "g:cta")) TLSEL = "g:cta";   // she just typed the CTA: stay on it
  if (TLSEL === "g:cta" && !items.some(x => x.key === "g:cta")) TLSEL = "cta:new";
  if (!TLSEL || !items.some(x => x.key === TLSEL)) TLSEL = (items.find(x => x.key === "g:hook") || items[0] || {}).key || null;
  const it = items.find(x => x.key === TLSEL);
  insp.textContent = ""; if (!it) { insp.innerHTML = '<div class="empty">Тапни елемент на таймлайні.</div>'; return; }
  let body;
  if (it.kind === "ctanew" || it.kind === "ef") {
    const c = document.createElement("div"); c.className = "card"; c.style.gridTemplateColumns = "1fr"; body = document.createElement("div");
    const k = document.createElement("div"); k.className = "kind"; k.innerHTML = `<span class="who mine">твоє</span>`; k.append(it.kind === "ef" ? "Ефект" : "Заклик у кінці (CTA)");
    const w = document.createElement("div"); w.className = "what"; w.textContent = it.kind === "ef" ? it.label.replace(/^Ефект: /, "") : "Впиши заклик, і він з'явиться в кінці рілса. Без тексту CTA немає.";
    body.append(k, w); c.append(body); insp.append(c);
  } else {
    const g = GFX.find(x => x.id === it.id); if (!g) return;
    cardList(insp, [g]); body = insp.querySelector(".card > div:last-child");
  }
  if (!it.off && !it.ghost) body.appendChild(timeRow(it));
  if (it.kind === "ef") { const del = document.createElement("button"); del.type = "button"; del.className = "b quiet"; del.textContent = "✕ Прибрати ефект"; del.addEventListener("click", () => tlRemove(it)); body.appendChild(del); }
  const g = (it.kind === "board" || it.kind === "cta") && GFX.find(x => x.id === it.id);
  if (g && g.type === "title") body.appendChild($("#hookbox"));
  const txt = g && (g.type === "title" || g.type === "cta") && !g.gone && g.state !== "d" && (g.text || "").trim();   // picked hook / CTA: drag it right on the video
  if (txt && tab === "graphics" && placing?.id !== g.id) setTimeout(() => { if (TLSEL === it.key) startPlacing(g.place || [90, 1000, 900, 320], g.id, true); }, 0);
  else if (!txt && placing?.id && GFX.some(x => x.id === placing.id && (x.type === "title" || x.type === "cta"))) setTimeout(stopPlacing, 0);
  if (txt) { const h = document.createElement("p"); h.className = "mode"; h.textContent = "Тягни текст прямо на відео, щоб поставити, де подобається."; body.insertBefore(h, body.children[2] || null); }
  if (it.kind === "cta" || it.kind === "ctanew") body.appendChild($("#ctabox"));
}
function timeRow(it) {
  const r = document.createElement("div"); r.className = "insptime";
  const btn = (t, title, fn) => { const b = document.createElement("button"); b.type = "button"; b.className = "b quiet"; b.textContent = t; b.title = title; b.addEventListener("click", fn); return b; };
  const val = t => { const b = document.createElement("b"); b.textContent = t; return b; };
  const lab = t => { const l = document.createElement("span"); l.className = "il"; l.textContent = t; return l; };
  if (it.kind !== "cta") {
    const ws = keptWords(), cur = wordAtCut(it.start), k = ws.indexOf(cur);
    const goWord = d => { const w = ws[Math.max(0, Math.min(ws.length - 1, k + d))]; if (w == null || w === cur) return; tlApply(it, P.toCut(R.words[w].s), P.toCut(R.words[w].s) + (it.end - it.start), null); tlGo(P.toCut(R.words[w].s) + 0.05); };
    const grp = document.createElement("span"); grp.className = "ig";
    grp.append(lab("Початок"), btn("◀", "На слово раніше", () => goWord(-1)), val(fmt(it.start) + (cur != null ? " · «" + R.words[cur].text.replace(/[.,!?;:]+$/, "") + "»" : "")), btn("▶", "На слово пізніше", () => goWord(1)));
    r.appendChild(grp);
  }
  const d = +(it.end - it.start).toFixed(1), setD = nd => { nd = Math.max(0.5, Math.min(P.cutDur, nd)); tlApply(it, it.kind === "cta" ? P.cutDur - nd : it.start, it.kind === "cta" ? P.cutDur : it.start + nd, it.kind === "cta" ? "lh" : "rh"); };
  const g2 = document.createElement("span"); g2.className = "ig";
  g2.append(lab("Тривалість"), btn("−", "Коротше на 0,5 с", () => setD(d - 0.5)), val(d.toFixed(1) + " с"), btn("+", "Довше на 0,5 с", () => setD(d + 0.5)));
  r.append(g2, btn("▶ Дивитись", "Програти з цього моменту", () => tlGo(it.start + 0.05, true)));
  return r;
}
function tlPlayhead() { const ph = document.getElementById("tlplay"); if (ph && P) ph.style.setProperty("--p", Math.min(1, pos / P.cutDur)); }
function tlGo(t, play) {
  t = Math.max(0, Math.min(t, P.cutDur - 0.05));
  if (cutVid() || tab === "preview") { v.currentTime = t; pos = t; tlPlayhead(); if (play) v.play().catch(() => {}); }
  else if (play) playRough(t); else seekCut(t);
}
function tlDrag(b, it, lane) {
  b.addEventListener("pointerdown", e => {
    if (e.button) return; e.preventDefault(); b.setPointerCapture(e.pointerId);
    const D = P.cutDur, W = lane.getBoundingClientRect().width, x0 = e.clientX, edge = e.target.tagName === "I" ? e.target.className : null;
    let s = it.start, en = it.end, moved = false;
    const mv = ev => {
      const dt = (ev.clientX - x0) / W * D; if (Math.abs(ev.clientX - x0) > 3) moved = true; if (!moved || it.off || it.ghost) return;
      if (edge === "rh") { en = Math.max(it.start + 0.5, Math.min(D, it.end + dt)); s = it.start; }
      else if (edge === "lh") { s = Math.max(0, Math.min(it.end - 0.5, it.start + dt)); en = it.end; }
      else if (it.kind !== "cta") { const len = it.end - it.start; s = Math.max(0, Math.min(D - len, it.start + dt)); en = s + len; }
      b.style.left = (s / D * 100) + "%"; b.style.width = ((en - s) / D * 100) + "%";
      b.title = `${fmt(s)}–${fmt(en)}`;
    };
    const up = () => {
      b.removeEventListener("pointermove", mv); b.removeEventListener("pointerup", up);
      if (!moved) { tlSelect(it.key, true); return; }
      if (it.off || it.ghost) return;
      TLSEL = it.key; tlApply(it, s, en, edge);
    };
    b.addEventListener("pointermove", mv); b.addEventListener("pointerup", up);
  });
}
function tlApply(it, s, en, edge) {
  const dur = +(en - s).toFixed(2), w = edge ? null : wordAtCut(s);   // a moved block starts on the nearest kept word, so later cuts keep it on its words
  if (!edge && w === null) return;
  mutate(() => {
    if (it.kind === "board") { const b = { ...(S.board[it.id] || {}) }; if (!edge) b.w0 = w; b.dur = dur; S.board = { ...S.board, [it.id]: b }; }
    else if (it.kind === "ov") { const o = (S.overlays || []).find(x => x.id === it.id); if (o) { if (!edge) o.w0 = w; o.dur = dur; } }
    else if (it.kind === "ef") { const e = (S.effects || []).find(x => x.id === it.id); if (e) { if (!edge) { e.w0 = w; e.at = +P.toCut(R.words[w].s).toFixed(2); } e.dur = dur; } }
    else if (it.kind === "cta" && S.cta) S.cta = { ...S.cta, dur: Math.min(10, Math.max(1, dur)) };
  });
  overlay(pos);
}
function tlRemove(it) {
  mutate(() => {
    if (it.kind === "board") S.board = { ...S.board, [it.id]: { ...(S.board[it.id] || {}), state: it.off ? "k" : "d" } };
    else if (it.kind === "ov") S.overlays = (S.overlays || []).filter(x => x.id !== it.id);
    else if (it.kind === "ef") S.effects = (S.effects || []).filter(x => x.id !== it.id);
    else if (it.kind === "cta") S.cta = null;
  });
  if (it.kind !== "board") TLSEL = null; overlay(pos); renderInspector();
}
document.addEventListener("keydown", e => {
  if (!TLSEL || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || (e.key !== "Delete" && e.key !== "Backspace")) return;
  const it = tlItems().find(x => x.key === TLSEL); if (it && !it.off) { e.preventDefault(); tlRemove(it); }
});

// ---------- «Знайти»: she asks for a photo / GIF / full-screen video / meme with a meaning; Claude puts 10-15 options in
// reel.json "finds" {<request id>: [{id, url, poster?, kind, label, source, license}]}; she picks; picks become her overlays
const FIND_KINDS = [["photo", "Фото"], ["gif", "Гіфка"], ["video", "Відео на весь екран"], ["meme", "Мем"]];
let FINDK = "photo";
function renderFindKinds() {
  const box = $("#findkind"); if (!box) return; box.textContent = "";
  for (const [k, t] of FIND_KINDS) { const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.setAttribute("aria-pressed", FINDK === k);
    b.addEventListener("click", () => { FINDK = k; renderFindKinds(); }); box.appendChild(b); }
}
$("#findgo").addEventListener("click", async () => {
  const q = $("#findq").value.trim(), msg = $("#findmsg"); if (!q) { msg.textContent = "Напиши, що воно має передати."; $("#findq").focus(); return; }
  const w0 = wordAtCut(pos); if (w0 === null) { msg.textContent = "Тут немає жодного слова в нарізці."; return; }
  const id = "fd" + Date.now().toString(36), kindT = FIND_KINDS.find(x => x[0] === FINDK)[1];
  mutate(() => { S.finds = [...(S.finds || []), { id, kind: FINDK, meaning: q, w0, at: +pos.toFixed(2), asked: new Date().toISOString(), picked: [] }]; });
  $("#findq").value = "";
  let sent = false;
  try { if (comments && await comments.canSendToClaude() === "available") { await comments.sendToClaude({ anchor: await comments.anchorFor($("#findgo")), text: `▶ Знайди варіанти (${kindT}) на ${fmt(pos)}: «${q}»` }); sent = true; } } catch (e) {}
  msg.textContent = sent ? "Claude шукає варіанти, вони з'являться тут." : "Збережено. Напиши Claude в чаті: «знайди варіанти».";
});
function syncFindOverlays(f) {   // her picks -> her overlays at that moment (kept where she already dragged them)
  const opts = ((R.finds || {})[f.id]) || [], keep = new Set(f.picked || []);
  S.overlays = (S.overlays || []).filter(o => o.fromFind !== f.id || keep.has(o.findOpt));
  const ws = keptWords(); let k0 = ws.indexOf(f.w0); if (k0 < 0) k0 = 0;
  (f.picked || []).forEach((oid, k) => {
    if ((S.overlays || []).some(o => o.fromFind === f.id && o.findOpt === oid)) return;
    const o = opts.find(x => x.id === oid); if (!o) return;
    const full = f.kind === "video", gif = f.kind === "gif";
    S.overlays = [...(S.overlays || []), { id: "ov" + f.id + k, fromFind: f.id, findOpt: oid, assetId: o.id, url: o.url, name: o.label || f.meaning,
      file: o.file, kind: o.kind === "video" ? "video" : "image", mode: full ? "full" : "box", effect: "soft", dur: full ? 3 : 2, behind: false,
      w0: ws[Math.min(ws.length - 1, k0 + k * 4)] ?? f.w0,   // several photos: one after another
      place: full ? [0, 0, 1080, 1920] : gif ? [600, 230, 420, 420] : [140, 220, 800, 620], ...(f.kind === "meme" ? { memeText: f.memeText || "" } : {}) }];
  });
}
function renderFinds() {
  const box = $("#findlist"); if (!box || !R) return; box.textContent = "";
  for (const f of [...(S.finds || [])].reverse()) {
    const opts = ((R.finds || {})[f.id]) || [], single = f.kind === "gif" || f.kind === "video" || f.kind === "meme";
    const el = document.createElement("div"); el.className = "freq";
    const h = document.createElement("div"); h.className = "fhead";
    h.innerHTML = `<b></b><span class="tc"></span><span class="mode"></span>`;
    h.children[0].textContent = (FIND_KINDS.find(x => x[0] === f.kind) || [, ""])[1]; h.children[1].textContent = fmt(f.at);
    h.children[2].textContent = "«" + f.meaning + "»" + (opts.length ? (single ? " · обери одну" : " · обери скільки хочеш") : " · Claude шукає…");
    const del = document.createElement("button"); del.type = "button"; del.className = "b quiet"; del.textContent = "Прибрати";
    del.addEventListener("click", () => mutate(() => { S.finds = S.finds.filter(x => x.id !== f.id); S.overlays = (S.overlays || []).filter(o => o.fromFind !== f.id); }));
    h.appendChild(del); el.appendChild(h);
    if (opts.length) {
      const grid = document.createElement("div"); grid.className = "fgrid";
      for (const o of opts) {
        const b = document.createElement("button"); b.type = "button"; b.className = "fopt"; b.setAttribute("aria-pressed", (f.picked || []).includes(o.id));
        b.title = [o.label, o.source, o.license].filter(Boolean).join(" · ");
        if (o.kind === "video") { const vd = document.createElement("video"); vd.muted = true; vd.loop = true; vd.playsInline = true; vd.preload = "none"; if (o.poster) vd.poster = o.poster; vd.dataset.src = o.url; manObs.observe(vd); b.appendChild(vd); }
        else { const im = document.createElement("img"); im.src = o.url; im.alt = o.label || ""; im.loading = "lazy"; b.appendChild(im); }
        const src = document.createElement("span"); src.className = "fsrc"; src.textContent = o.source || ""; b.appendChild(src);
        b.addEventListener("click", () => mutate(() => {
          const ff = S.finds.find(x => x.id === f.id), cur = new Set(ff.picked || []);
          if (cur.has(o.id)) cur.delete(o.id); else { if (single) cur.clear(); cur.add(o.id); }
          ff.picked = [...cur]; syncFindOverlays(ff);
        }));
        grid.appendChild(b);
      }
      el.appendChild(grid);
      if (f.kind === "meme" && (f.picked || []).length) {
        const inp = document.createElement("input"); inp.type = "text"; inp.placeholder = "Твій текст на мемі: верх / низ"; inp.value = f.memeText || ""; inp.style.marginTop = "8px";
        inp.addEventListener("change", () => mutate(() => { const ff = S.finds.find(x => x.id === f.id); ff.memeText = inp.value.trim(); (S.overlays || []).forEach(o => { if (o.fromFind === f.id) o.memeText = ff.memeText; }); }));
        el.appendChild(inp);
      }
      if (f.kind === "gif" || f.kind === "photo") { const p = document.createElement("p"); p.className = "mode"; p.style.margin = "6px 0 0"; p.textContent = "Обране з'явиться в «Накладеннях» нижче: там його можна посунути по екрану й по часу."; el.appendChild(p); }
    }
    box.appendChild(el);
  }
}

function renderAll() {
  renderCuts(); renderGraphics(); renderEffects(); renderManual(); renderCapStyles(); renderCaptions(); renderSound(); renderPreview(); syncHookCta(); renderHookOpts(); renderStyleGrid(); renderRefs(); renderStamps(); renderStage(); renderCapPlace(); renderStylePick(); renderCutBox(); renderTimeline(); renderFindKinds(); renderFinds();
  const sent = { mystyle: !!S.style, cuts: S.cut != null, overlays: (S.overlays || []).length, effects: (S.effects || []).length, graphics: Object.keys(S.board).length || (S.hook != null) || !!S.cta || !!S.style || !!S.speedMul, captions: S.captions != null, sound: Object.keys(S.sfxOff).length || S.voiceClean === false || !ReelCore.isNeutral(S.grade) };
  $$(".tab:not(.tabx)").forEach(b => { const d = b.querySelector(".dot"); if (d) d.hidden = !sent[b.dataset.tab]; });
  styleDot();
}


// ---------- «Стиль»: rounds of rendered variants (db style/round, written by Claude) and her verdicts (db style/votes) ----------
// Each variant: a muted looping preview, «Зі звуком» plays it from the start with sound; Залишити / Можливо / Прибрати + a note.
// «Готово → Claude» sends the round with the same «Send to Claude» comment as the reel steps; scripts/style_lab.py apply reads it.
let STR = null, STV = null, stRef = null, stTimer = null, stZones = false;
const ST_V = { keep: "Залишити", maybe: "Можливо", drop: "Прибрати" };
const stBlank = () => ({ round: STR?.id || null, verdicts: {}, note: "", refs: [], sent: null });
function stVariants() { return (STR?.sections || []).flatMap(s => s.variants || []); }
function stCount() { const c = { keep: 0, maybe: 0, drop: 0 }; for (const v of stVariants()) { const x = STV?.verdicts?.[v.id]?.v; if (x) c[x]++; } return c; }
function stWaiting() { return !!(STR && STV?.sent && STV.round === STR.id); }
function styleDot() { const d = document.querySelector('#stylelink .dot'); if (d) d.hidden = !(STR && !STR.closed && !stWaiting()); }
function stSave() {
  clearTimeout(stTimer);
  stTimer = setTimeout(async () => {
    if (!stRef) return;
    try { await stRef.set(JSON.parse(JSON.stringify({ ...STV, updatedAt: new Date().toISOString() }))); pill("Оцінки збережено"); }
    catch (e) { pill("Оцінки не збереглись (" + (e?.code || "error") + ")", true); }
  }, 500);
}
function stVote(id, v) {
  const cur = STV.verdicts[id] || {}; STV.verdicts[id] = { ...cur, v: cur.v === v ? null : v };
  renderStyle(); styleBar(); stSave();
}
function stPlayer(url, poster, label) {   // a muted looping example with a «Зі звуком» button (one plays with sound at a time)
  const w = document.createElement("div"); w.className = "stpl";
  w.innerHTML = `<video muted loop playsinline autoplay preload="metadata"></video><div class="sz" hidden aria-hidden="true"></div><button class="stsound" type="button" aria-pressed="false">Зі звуком</button>`;
  const vid = w.querySelector("video"), sb = w.querySelector(".stsound"); vid.src = url; if (poster) vid.poster = poster; vid.setAttribute("aria-label", label || "Приклад");
  sb.addEventListener("click", () => {
    const on = vid.muted;
    $$("section[data-p=style] video").forEach(x => { x.muted = true; const b = x.parentElement.querySelector(".stsound"); if (b) { b.setAttribute("aria-pressed", "false"); b.textContent = "Зі звуком"; } });
    if (on) { vid.muted = false; vid.currentTime = 0; vid.play().catch(() => {}); sb.setAttribute("aria-pressed", "true"); sb.textContent = "Без звуку"; }
  });
  return w;
}
// «Доточити»: a round for one element of a saved style (scripts/style_lab.py element <style> <element>)
const TUNE = [["captions", "Субтитри"], ["hook", "Хук"], ["lists", "Списки"], ["numbers", "Цифри"], ["split", "Розбивки екрану"], ["transitions", "Переходи"], ["cta", "CTA"], ["sounds", "Звуки"], ["motion", "Швидкість руху"]];
function askTune(x, el, label) {
  $("#mtitle").textContent = `Доточити «${x.title || x.name}»?`; $("#myes").textContent = "Так, роби раунд"; $("#mno").textContent = "Ще ні";
  $("#mbody").innerHTML = `<p class="lede">Claude зробить раунд «${label}»: 3–5 варіантів цього стилю, у кожному змінено одну річ, слова ті самі. Він з'явиться тут, на «Стилі».</p>`;
  $("#myes").hidden = false; $("#modal").hidden = false; $("#myes").focus();
  $("#myes").onclick = async () => {
    $("#myes").disabled = true; let sent = false;
    try { if (comments && await comments.canSendToClaude() === "available") { await comments.sendToClaude({ anchor: await comments.anchorFor($("#mystyles")), text: `▶ «Стиль»: доточи стиль ${x.name} (${x.title || x.name}): ${el} (${label}).` }); sent = true; } } catch (e) {}
    try { await DB.doc("style/request").set({ style: x.name, element: el, at: new Date().toISOString(), sent }); } catch (e) {}
    $("#myes").disabled = false;
    if (sent) { $("#modal").hidden = true; pill("Передано Claude"); }
    else { $("#mtitle").textContent = "Збережено. Ще один крок"; $("#mbody").innerHTML = `<p class="lede">Claude зараз не на зв'язку зі сторінкою. Напиши йому в чаті:</p><p style="font-size:20px;font-weight:700;margin:6px 0 14px">«доточи ${(x.title || x.name).replace(/[<&]/g, "")}: ${label.toLowerCase()}»</p>`; $("#myes").hidden = true; $("#mno").textContent = "Зрозуміло"; }
  };
}
function startPlan() {   // a new person: where they are on the way to the first reel
  const done = [true, STYLE_LIST.length > 0, false], now = done.indexOf(false);
  const steps = [["Бренд", "кольори, шрифти, елементи: Claude питає в чаті"], ["Стиль", "9 варіантів на 5 секундах твого відео, обираєш свої"], ["Перший рілс", "надішли Claude відео, тут з'явиться нарізка"]];
  $("#banner").innerHTML = "<b>Як почати</b><ol style=\"margin:6px 0 0;padding-left:20px\">" + steps.map(([t, d], k) => `<li style="${k === now ? "font-weight:700" : "opacity:.75"}">${done[k] ? "✓ " : ""}${t}: ${d}</li>`).join("") + "</ol>";
  $("#banner").hidden = false;
}
function renderMyStyles() {   // the styles already saved (db style/list, each with the example it was kept from)
  const box = $("#mystyles"); if (!box) return; box.textContent = "";
  if (!STYLE_LIST.length) return;
  const h = document.createElement("h2"); h.style.marginTop = "0"; h.textContent = `Мої стилі (${STYLE_LIST.length})`;
  const p = document.createElement("p"); p.className = "lede"; p.textContent = "Затверджені стилі з прикладами. Для рілса стиль обираєш на «Графіці».";
  const grid = document.createElement("div"); grid.className = "stgrid";
  for (const x of STYLE_LIST) {
    const c = document.createElement("div"); c.className = "stv"; c.dataset.style = x.name;
    if (x.url) c.appendChild(stPlayer(x.url, x.posterUrl, x.title));
    const t = document.createElement("div"); t.className = "stt"; t.textContent = x.title || x.name;
    if (R && S.style === x.name) { const b = document.createElement("span"); b.className = "stbadge"; b.textContent = "цей рілс"; t.appendChild(b); }
    if (STYLE_DEFAULT === x.name) { const b = document.createElement("span"); b.className = "stbadge"; b.textContent = "завжди"; t.appendChild(b); }
    const w = document.createElement("p"); w.className = "stw"; w.textContent = x.what || "";
    const acts = document.createElement("div"); acts.className = "stacts";
    const def = document.createElement("button"); def.type = "button"; def.className = "b quiet"; def.textContent = STYLE_DEFAULT === x.name ? "Не за замовчуванням" : "Завжди цей";
    def.title = "Новий рілс одразу бере цей стиль (на «Графіці» можна змінити)";
    def.addEventListener("click", async () => { const v = STYLE_DEFAULT === x.name ? null : x.name;
      try { await DB.doc("style/list").update({ default: v }); STYLE_DEFAULT = v; renderMyStyles(); pill(v ? "Стиль за замовчуванням: " + (x.title || x.name) : "Стиль за замовчуванням прибрано"); }
      catch (e) { pill("Не збереглось (" + (e?.code || "error") + ")", true); } });
    const sel = document.createElement("select"); sel.className = "sfxsel"; sel.setAttribute("aria-label", "Що доточити в стилі " + (x.title || x.name));
    sel.innerHTML = `<option value="">Доточити…</option>` + TUNE.map(([k, t]) => `<option value="${k}">${t}</option>`).join("");
    sel.addEventListener("change", () => { if (sel.value) askTune(x, sel.value, sel.selectedOptions[0].textContent); sel.value = ""; });
    acts.append(def, sel);
    c.append(t, w, acts); grid.appendChild(c);
  }
  box.append(h, p, grid);
  if (stZones) box.querySelectorAll(".sz").forEach(z => { z.hidden = false; z.innerHTML = zonesSvg(STR?.handle || (R && R.handle) || ""); });
}
function renderStyle() {
  const box = $("#stbox"); styleDot(); renderMyStyles();
  if (STR?.closed) { box.innerHTML = `<div class="empty">Оцінки записані у стилі вище. Новий раунд з'явиться тут, коли попросиш Claude.</div>`; $("#stnotebox").hidden = true; $("#sttally").textContent = ""; box.dataset.round = ""; return; }
  if (!STR) { box.innerHTML = `<div class="empty">Раундів стилю ще немає. Попроси Claude почати «Стиль».</div>`; $("#stnotebox").hidden = true; $("#sttally").textContent = ""; return; }
  if (STR.lede) $("#stlede").textContent = STR.lede;
  const playing = [...box.querySelectorAll("video")].find(x => !x.muted)?.dataset.id;   // keep the one with sound playing across re-renders
  if (box.dataset.round === STR.id && box.children.length) { stPaint(); return; }
  box.dataset.round = STR.id; box.textContent = "";
  const h = document.createElement("h2"); h.textContent = STR.title || "Раунд"; h.style.marginTop = "0"; box.appendChild(h);
  for (const sec of STR.sections || []) {
    const el = document.createElement("div"); el.className = "stsec";
    el.innerHTML = `<h2></h2><p class="lede"></p><div class="stgrid"></div>`;
    el.querySelector("h2").textContent = sec.title || ""; el.querySelector(".lede").textContent = sec.what || "";
    const grid = el.querySelector(".stgrid");
    for (const v of sec.variants || []) {
      const c = document.createElement("div"); c.className = "stv"; c.dataset.id = v.id;
      c.innerHTML = `<div class="stpl"><video muted loop playsinline autoplay preload="metadata"></video><div class="sz" hidden aria-hidden="true"></div>
          <button class="stsound" type="button" aria-pressed="false">Зі звуком</button></div>
        <div class="stt"></div><p class="stw"></p>
        <div class="stvote" role="group"><button type="button" data-v="keep" aria-pressed="false">Залишити</button><button type="button" data-v="maybe" aria-pressed="false">Можливо</button><button type="button" data-v="drop" aria-pressed="false">Прибрати</button></div>
        <textarea placeholder="Що подобається або що змінити"></textarea>`;
      const vid = c.querySelector("video"); vid.dataset.id = v.id; vid.src = v.url; if (v.posterUrl) vid.poster = v.posterUrl;
      vid.setAttribute("aria-label", v.title || "Варіант");
      c.querySelector(".stt").textContent = v.title || ""; c.querySelector(".stw").textContent = v.what || "";
      c.querySelector(".stvote").setAttribute("aria-label", "Оцінка: " + (v.title || ""));
      c.querySelectorAll(".stvote button").forEach(b => b.addEventListener("click", () => stVote(v.id, b.dataset.v)));
      const ta = c.querySelector("textarea"); ta.setAttribute("aria-label", "Нотатка: " + (v.title || ""));
      ta.addEventListener("input", () => { STV.verdicts[v.id] = { ...(STV.verdicts[v.id] || {}), note: ta.value }; stSave(); });
      const sb = c.querySelector(".stsound");
      sb.addEventListener("click", () => {
        const on = vid.muted;
        box.querySelectorAll("video").forEach(x => { x.muted = true; x.closest(".stv").querySelector(".stsound").setAttribute("aria-pressed", "false"); x.closest(".stv").querySelector(".stsound").textContent = "Зі звуком"; });
        if (on) { vid.muted = false; vid.currentTime = 0; vid.play().catch(() => {}); sb.setAttribute("aria-pressed", "true"); sb.textContent = "Без звуку"; }
      });
      grid.appendChild(c);
    }
    box.appendChild(el);
  }
  if (playing) box.querySelector(`video[data-id="${CSS.escape(playing)}"]`)?.closest(".stv").querySelector(".stsound").click();
  $("#stnotebox").hidden = false;
  stPaint();
}
function stPaint() {   // verdicts, notes, zones onto the cards already built (videos keep playing)
  for (const c of $$("#stbox .stv")) {
    const x = STV?.verdicts?.[c.dataset.id] || {};
    c.dataset.v = x.v || "";
    c.querySelectorAll(".stvote button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === x.v)));
    const ta = c.querySelector("textarea"); if (document.activeElement !== ta) ta.value = x.note || "";
    const z = c.querySelector(".sz"); z.hidden = !stZones; if (stZones && !z.innerHTML) z.innerHTML = zonesSvg(STR?.handle || (R && R.handle) || "");
  }
  $$("#mystyles .sz").forEach(z => { z.hidden = !stZones; if (stZones && !z.innerHTML) z.innerHTML = zonesSvg(STR?.handle || (R && R.handle) || ""); });
  if (document.activeElement !== $("#stnote")) $("#stnote").value = STV?.note || "";
  renderStRefs();
  const n = stCount(), all = stVariants().length;
  $("#sttally").textContent = all ? `Оцінено ${n.keep + n.maybe + n.drop} з ${all} · залишити ${n.keep} · можливо ${n.maybe} · прибрати ${n.drop}` : "";
}
$("#stnote").addEventListener("input", e => { if (!STV) return; STV.note = e.target.value; stSave(); });
// references for the round: links to reels they like (Instagram, TikTok, YouTube) and their own files, up to 10 in all
function renderStRefs() {
  const refs = STV?.refs || [], links = $("#stlinks"), files = $("#streflist"); links.textContent = ""; files.textContent = "";
  refs.forEach((r, k) => {
    const del = () => { STV.refs = refs.filter((_, j) => j !== k); renderStRefs(); stSave(); };
    if (r.kind === "link") {
      const c = document.createElement("span"); c.className = "stlink";
      const a = document.createElement("a"); a.href = r.url; a.target = "_blank"; a.rel = "noopener"; a.textContent = "↗ " + r.url.replace(/^https?:\/\/(www\.)?/, "");
      const x = document.createElement("button"); x.type = "button"; x.textContent = "×"; x.title = "Прибрати"; x.setAttribute("aria-label", "Прибрати посилання"); x.addEventListener("click", del);
      c.append(a, x); links.appendChild(c);
    } else {
      const b = document.createElement("button"); b.type = "button"; b.title = r.name + " (тапни, щоб прибрати)";
      if (r.kind === "image") b.style.backgroundImage = `url(${JSON.stringify(r.url)})`; else b.textContent = "▶ " + r.name;
      b.addEventListener("click", del); files.appendChild(b);
    }
  });
  $("#streffile").hidden = !assets || refs.length >= 10;
}
$("#stlinkadd").addEventListener("click", () => {
  const inp = $("#streflink"), u = inp.value.trim(), msg = $("#strefmsg");
  if (!STV) return;
  if (!/^https:\/\/\S+\.\S+/.test(u)) { msg.textContent = "Встав посилання, що починається з https://"; inp.focus(); return; }
  if ((STV.refs || []).length >= 10) { msg.textContent = "Можна до 10 референсів."; return; }
  STV.refs = [...(STV.refs || []), { kind: "link", url: u }]; inp.value = ""; msg.textContent = "Посилання додано."; renderStRefs(); stSave();
});
$("#streflink").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); $("#stlinkadd").click(); } });
$("#streffile").addEventListener("change", async e => {
  const fs = [...e.target.files], msg = $("#strefmsg"); if (!fs.length || !assets || !STV) return;
  if ((STV.refs || []).length + fs.length > 10) { msg.textContent = "Можна до 10 референсів."; e.target.value = ""; return; }
  if (fs.some(f => f.size > 20 * 1024 * 1024)) { msg.textContent = "Файл більший за 20 МБ: кинь посилання на рілс замість файлу."; e.target.value = ""; return; }
  msg.textContent = "Завантажую…";
  try {
    for (const f of fs) { const u = await assets.upload(f); STV.refs = [...(STV.refs || []), { kind: f.type.startsWith("video") ? "video" : "image", id: u.id, url: u.url, name: f.name }]; }
    msg.textContent = "Додано."; renderStRefs(); stSave();
  } catch (er) { msg.textContent = "Не вдалося завантажити (" + (er?.code || "помилка") + "). Спробуй ще раз."; }
  e.target.value = "";
});
$("#stzbtn").addEventListener("click", () => { stZones = !stZones; $("#stzbtn").classList.toggle("on", stZones); $("#stzbtn").setAttribute("aria-pressed", String(stZones)); stPaint(); });
function styleBar() {
  const bar = $("#gobar"), txt = $("#gotext"), btn = $("#gobtn"); bar.hidden = false;
  const set = (t, sub, label, kind) => { txt.innerHTML = `<b>${t}</b><span class="sub">${sub}</span>`; btn.innerHTML = label; btn.dataset.kind = kind || ""; btn.disabled = !kind; };
  if (!STR || STR.closed) return STYLE_LIST.length ? set("Мої стилі", "Стиль для рілса обираєш на «Графіці».", "До «Графіки»", R ? "tographics" : "") : set("Стиль", "Claude ще не підготував раунд.", "Готово → Claude");
  const n = stCount(), done = n.keep + n.maybe + n.drop, all = stVariants().length;
  if (stWaiting()) return set("Claude готує наступний раунд", "Сторінка оновиться сама. Оцінки можна ще правити.", `<span class="spin"></span>Claude працює`);
  if (!done) return set(STR.title || "Стиль", "Оціни варіанти: залишити, можливо або прибрати.", "Готово → Claude");
  set(STR.title || "Стиль", done < all ? `Оцінено ${done} з ${all}. Неоцінені Claude пропустить.` : "Усе оцінено. Передай Claude.", "Готово → Claude", "style");
}
function askStyle() {
  const n = stCount();
  $("#mtitle").textContent = "Віддати раунд Claude?"; $("#myes").textContent = "Так, готово → Claude"; $("#mno").textContent = "Ще ні";
  $("#mbody").innerHTML = `<p class="lede">Залишити: ${n.keep} · Можливо: ${n.maybe} · Прибрати: ${n.drop}${(STV.refs || []).length ? ` · референсів: ${STV.refs.length}` : ""}</p><ol>
    <li><b>«Залишити»</b> Claude запише у твій стиль${STR?.kind === "directions" ? " (кожен напрям окремим стилем)" : ""}.</li>
    <li><b>«Можливо»</b> виправить за нотатками й покаже ще раз.</li>
    <li><b>«Прибрати»</b> більше не з'явиться, причину запише.</li></ol>`;
  $("#myes").hidden = false; $("#modal").hidden = false; $("#myes").focus();
  $("#myes").onclick = sendStyle;
}
async function sendStyle() {
  const n = stCount(), at = new Date().toISOString(); $("#myes").disabled = true;
  let sent = false, why = "";
  const text = `▶ Кнопка «Готово → Claude» у «Стилі»: раунд ${STR.id} оцінено (залишити ${n.keep}, можливо ${n.maybe}, прибрати ${n.drop}${(STV.refs || []).length ? `, референсів ${STV.refs.length}` : ""}).`;
  try {
    const can = comments ? await comments.canSendToClaude() : "off";
    if (can === "available") { await comments.sendToClaude({ anchor: await comments.anchorFor($("#gobtn")), text }); sent = true; }
    else why = can;
  } catch (e) { why = e?.code || "error"; }
  STV.sent = { at, sent }; clearTimeout(stTimer);
  try { await stRef.set(JSON.parse(JSON.stringify({ ...STV, updatedAt: at }))); } catch (e) { pill("Оцінки не збереглись (" + (e?.code || "error") + ")", true); }
  $("#myes").disabled = false;
  if (sent) { $("#modal").hidden = true; pill("Передано Claude"); }
  else {
    $("#mtitle").textContent = "Збережено. Ще один крок";
    $("#mbody").innerHTML = `<p class="lede">Claude зараз не на зв'язку зі сторінкою${why === "writers_only" ? " (кнопка працює тільки для власниці сторінки)" : ""}. Напиши йому в чаті одне слово:</p><p style="font-size:22px;font-weight:700;margin:6px 0 14px">«стиль»</p>`;
    $("#myes").hidden = true; $("#mno").textContent = "Зрозуміло";
  }
  styleBar(); styleDot();
}
async function loadStyle() {
  const rr = DB.doc("style/round"); stRef = DB.doc("style/votes");
  try { const x = await rr.get(); STR = x.exists ? JSON.parse(JSON.stringify(x.data())) : null; } catch (e) { STR = null; }
  try { const x = await stRef.get(); STV = x.exists ? JSON.parse(JSON.stringify(x.data())) : null; } catch (e) { STV = null; }   // a copy: db data can be read-only
  if (!STV || STV.round !== STR?.id) STV = stBlank();
  STV.verdicts = STV.verdicts || {};
  if (STR?.theme && !R) { const rt = document.documentElement; for (const [k, val] of Object.entries(STR.theme)) if (k !== "scheme" && k !== "label") rt.style.setProperty("--" + k, val); rt.setAttribute("data-theme", STR.theme.scheme || "light"); }
  styleDot(); if (tab === "style") { renderStyle(); styleBar(); }
  else if (STR && !STR.closed && !stWaiting() && !Object.keys(STV.verdicts).length) { $("#banner").textContent = `${STR.title || "Новий раунд стилю"}: відкрий вкладку «Стиль».`; $("#banner").hidden = false; }
  let first = true;
  rr.onSnapshot(x => {   // Claude put up the next round: show it in place
    if (first) { first = false; return; }
    const prev = STR?.id; STR = x.exists ? JSON.parse(JSON.stringify(x.data())) : null;
    if (STR && STR.id !== prev) { STV = stBlank(); $("#stbox").dataset.round = ""; showTab("style"); $("#banner").textContent = `${STR.title || "Новий раунд"}: оціни варіанти й натисни «Готово → Claude».`; $("#banner").hidden = false; pill("Новий раунд стилю"); }
    else if (tab === "style") { $("#stbox").dataset.round = ""; renderStyle(); styleBar(); }
    styleDot();
  }, () => {});
}

// ---------- load ----------
// One reel: docs reel/current, review/current, builds/latest. A batch: reel/index lists them, and each has reel/<id>, review/<id>, builds/<id>.
let DB = null, subs = [], LIST = [], loadNo = 0;   // loadNo: listeners of a reel we switched away from ignore their events
const docsFor = id => ({ reel: "reel/" + id, review: "review/" + id, build: id === "current" ? "builds/latest" : "builds/" + id, cut: id === "current" ? "builds/cut" : "builds/" + id + "-cut" });
function pickReel() { let id = null; try { id = localStorage.getItem("reelPick"); } catch (e) {} return LIST.some(x => x.id === id) ? id : (LIST.find(x => !/фінал/i.test(x.status || "")) || LIST[0]).id; }
function renderPick(cur) {
  const sel = $("#reelsel"); sel.textContent = ""; $("#reelpick").hidden = LIST.length < 2;
  LIST.forEach((x, k) => { const o = document.createElement("option"); o.value = x.id; o.textContent = `${k + 1}. ${x.title || x.id}${x.status ? " · " + x.status : ""}`; o.selected = x.id === cur; sel.appendChild(o); });
}
$("#reelsel").addEventListener("change", async e => {
  try { localStorage.setItem("reelPick", e.target.value); } catch (er) {}
  if (dirty) { clearTimeout(timer); saveNow(); }
  await saving.catch(() => {});
  load(e.target.value);
});
async function load(id) {
  for (const u of subs) if (typeof u === "function") try { u(); } catch (e) {}
  subs = []; stopPlay(); placing = null; R = null; B = null; CB = null; S = blank(); undo = []; $("#undo").disabled = true; dirty = false; mine = null; pos = 0;
  renderPick(id); $("#reelname").textContent = "Завантажую рілс…"; pill("Завантажую…");
  const d = docsFor(id), my = ++loadNo, live = () => my === loadNo;
  try {
    const rs = await DB.doc(d.reel).get(); if (!live()) return;
    if (!rs.exists) { $("#reelname").textContent = "Рілс ще не завантажено. Попроси Claude його завантажити."; pill("Нічого переглядати", true); startPlan(); if (STR || !STYLE_LIST.length) showTab("style"); return; }
    R = rs.data();
    if (!$("#sz").hidden) drawZones();   // their own handle on the Instagram screen
    if (R.theme) {   // brand colours from brand.json
      const rt = document.documentElement;
      for (const [k, val] of Object.entries(R.theme)) if (k !== "scheme" && k !== "label") rt.style.setProperty("--" + k, val);
      if (R.theme.label) $("#eyebrow").textContent = R.theme.label;
      if (R.theme.library) $("#eflib").href = R.theme.library;
      rt.setAttribute("data-theme", R.theme.scheme || "light"); rt.style.colorScheme = R.theme.scheme || "light";
    }
    try { if (R.fonts) localStorage.setItem("reelFonts", JSON.stringify(R.fonts)); } catch (e) {}
    if (R.fonts) {   // brand fonts, so the caption preview uses the real faces (replaces the copy remembered from the last visit)
      document.getElementById("brandfonts")?.remove();
      const css = [["rb", R.fonts.body], ["ra", R.fonts.accent], ...Object.entries(R.fonts.extra || {}).map(([f, u]) => ["bf_" + f.replace(/\W/g, "_"), u])]
        .filter(f => f[1]).map(([n, u]) => `@font-face{font-family:${n};src:url(${u});font-display:swap}`).join("");   // extra: the brand's other weights
      document.head.appendChild(Object.assign(document.createElement("style"), { id: "brandfonts", textContent: css }));
      const rt = document.documentElement;   // the brand's fonts for the whole page
      if (R.fonts.accent) rt.style.setProperty("--f-display", '"ra", Georgia, serif');
      if (R.fonts.body) rt.style.setProperty("--f-body", '"rb", system-ui, sans-serif');
    }
    ref = DB.doc(d.review);
    const rv = await ref.get(); if (!live()) return; if (rv.exists) S = { ...blank(), ...JSON.parse(JSON.stringify(rv.data())) };
    // someone else (Claude, another tab) changed the decisions: take theirs instead of saving a stale copy over it
    subs.push(ref.onSnapshot(s => {
      if (!live() || !R) return;
      if (!s.exists) {   // Claude cleared the decisions (a new reel in the same slot): drop the old ones held in this tab
        if (!dirty && JSON.stringify(S) !== JSON.stringify(blank())) { S = blank(); undo = []; mine = null; $("#undo").disabled = true; recompute(); renderAll(); setPos(0); pill("Новий рілс: старі рішення скинуто"); }
        return;
      }
      const d = s.data(); if (d.updatedAt === mine || dirty) return;
      if (JSON.stringify({ ...blank(), ...JSON.parse(JSON.stringify(d)) }) === JSON.stringify({ ...S })) return;   // same decisions (fields blank() adds included): nothing changed
      S = { ...blank(), ...JSON.parse(JSON.stringify(d)) }; undo = []; $("#undo").disabled = true;
      recompute(); renderAll(); setPos(pos); pill("Оновлено Claude");
    }, () => {}));
    let firstReel = true;
    subs.push(DB.doc(d.reel).onSnapshot(async s => {   // Claude changed the reel (e.g. added proposals): take it in place
      if (!live()) return; if (firstReel) { firstReel = false; return; } if (!s.exists) return;
      if (dirty) { clearTimeout(timer); saveNow(); } await saving.catch(() => {});
      const before = R.claudeRound || 0; R = s.data(); recompute(); renderAll(); setPos(pos); overlay(pos);
      if ((R.claudeRound || 0) > before) { showTab("graphics"); const n = GFX.filter(g => !g.user && !g.own && !g.gone).length;
        $("#banner").textContent = `Claude додав пропозиції (${n}). Переглянь кожну: залиш, зміни або прибери. Потім «Зібрати чернетку» внизу.`; $("#banner").hidden = false; pill("Пропозиції Claude готові"); }
      else pill("Claude оновив рілс");
    }, () => {}));
    let firstBuild = true;
    let firstCut = true;
    subs.push(DB.doc(d.cut).onSnapshot(s => { if (!live()) return; const had = CB?.url; CB = s.exists ? s.data() : null;
      if (!firstCut && CB?.url && CB.url !== had && tab === "graphics") { showTab("graphics"); $("#banner").textContent = "Відео нарізки готове: перевір склейки в плеєрі."; $("#banner").hidden = false; }
      else if (tab === "graphics") showTab("graphics"); renderCutBox(); firstCut = false; }, () => {}));
    subs.push(DB.doc(d.build).onSnapshot(s => { if (!live()) return; const had = B?.url; B = s.exists ? s.data() : null; if (R) { renderPreview(); renderStage(); }
      if (!firstBuild && B?.url && B.url !== had) { showTab("preview"); $("#banner").textContent = "Чернетка готова. Натисни play на відео, лиши нотатки на секундах або «Це фінал»."; $("#banner").hidden = false; }
      else if (tab === "preview") showTab("preview"); firstBuild = false; }, () => {}));
    recompute();
    $("#reelname").textContent = `${R.title} · оригінал ${fmt(R.srcDur)} → рілс ${fmt(P.cutDur)}`; setPos(0);
    $("#brand").value = S.brandRequest || "";
    renderAll(); showTab(["cuts", "overlays", "effects", "graphics", "captions", "sound", "mystyle", "preview", "style"].includes(location.hash.slice(1)) ? location.hash.slice(1) : tab || "cuts");
    pill(rv.exists ? "Збережені рішення завантажено" : "Готово");
    useDefaultStyle();
  } catch (e) { if (live()) pill("Не вдалося завантажити рілс (" + (e?.code || "error") + "). Онови сторінку.", true); }
}
(async () => {
  DB = await window.claude?.use?.("db");
  if (!DB) { pill("Тут рілс не завантажиться. Відкрий сторінку за посиланням з claude.ai.", true); $("#reelname").textContent = "Немає з'єднання."; return; }
  assets = await window.claude?.use?.("assets");
  comments = await window.claude?.use?.("comments");   // «Send to Claude» from the big button   // only editors get it; others don't see the overlay button
  $("#ovbox").hidden = !assets; $("#ovnone").hidden = !!assets;
  await loadStyle();
  const takeList = x => { const d = x.exists ? JSON.parse(JSON.stringify(x.data())) : {}; STYLE_LIST = d.items || []; STYLE_DEFAULT = d.default || null; };
  try { takeList(await DB.doc("style/list").get()); } catch (e) { STYLE_LIST = []; }
  placeStyleTab();
  DB.doc("style/list").onSnapshot(x => { takeList(x); useDefaultStyle(); if (R) renderStylePick(); if (tab === "style") { renderMyStyles(); styleBar(); } placeStyleTab(); }, () => {});
  if (tab === "style") { renderMyStyles(); styleBar(); }
  colRef = DB.doc("library/colors");   // «Мої кольори»
  try { const x = await colRef.get(); MYCOL = x.exists ? (x.data().items || []) : []; } catch (e) { MYCOL = []; }
  colRef.onSnapshot(x => { MYCOL = x.exists ? [...(x.data().items || [])] : []; if (R) renderLooks(); }, () => {});
  libRef = DB.doc("library/files");   // «Мої файли» live across reels
  try { const l = await libRef.get(); LIB = l.exists ? (l.data().items || []) : [];
    if (l.exists && /^https:\/\//.test(l.data().libraryUrl || "")) $("#eflib").href = l.data().libraryUrl;   // their own effects gallery, for every reel
  } catch (e) { LIB = []; }
  renderLib();
  try { const x = await DB.doc("library/sfx").get(); SFXLIB = x.exists ? (x.data().items || []) : []; } catch (e) { SFXLIB = []; }
  DB.doc("library/sfx").onSnapshot(x => { SFXLIB = x.exists ? (x.data().items || []) : []; if (R) renderSound(); }, () => {});   // new sounds show up without a refresh
  const idx = DB.doc("reel/index");   // a batch of reels; without it the page shows reel/current as before
  try { const x = await idx.get(); LIST = x.exists ? (x.data().items || []) : []; } catch (e) { LIST = []; }
  if (!LIST.length) LIST = [{ id: "current" }];
  const first = pickReel(); load(first);
  idx.onSnapshot(s => {   // Claude adds the next reel or changes a status while they review: refresh the picker only
    const items = s.exists ? (s.data().items || []) : []; if (!items.length) return;
    const added = items.length > LIST.length; LIST = items; renderPick($("#reelsel").value || first);
    if (added) pill("Наступний рілс готовий до перевірки: обери його зверху");
  }, () => {});
})();
