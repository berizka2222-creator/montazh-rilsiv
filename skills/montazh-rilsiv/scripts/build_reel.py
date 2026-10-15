#!/usr/bin/env python3
"""Turn edit.json + brand.json into a HyperFrames project (one fixed template, no per-reel installs), ready to render.
Usage: python3 build_reel.py <reel-folder> [--capcut]
  --capcut  leave captions and sound effects out of the render and write captions.json + sfx.json for CapCut instead.

edit.json (written by auto_edit.py, then Claude marks accents and adds cards):
  captions: [{start, end, words: [{text, t, accent}], plain?}]   plain = basic white sans (a "before" look), not brand
  punch:    [seconds | [seconds, scale]]    quick zoom-ins on the camera (alternate in/out; [t, 1.25] forces a level)
  cards:    [{type, start, end, ...}]       types:
     title  {text: "line one / line two"}            big headline in the space above the head (hook)
     block  {top: "don't", bottom: "worry"}          full brand-colour screen with the clip framed in it (reveal)
     card   {title: "my stack", rows: ["a","b"], y?: 150}   white UI card, rows appear one by one (lists, steps, tools)
     tag    {text: "open source", y: 300}            small pill label that pops on (name drops)
     (every card: leave out "end" and it clears when the phrase it starts in finishes)
     cta    {text: "comment EDIT", y?: 1360}         call-to-action pill (kept above the bottom ~420 px IG covers); CAPS word = pop colour
     shot   {src: "shots/tool.png", label: "heyclicky.com", y?: 130}   website screenshot in a browser window (make it with screenshot.sh);
                                                     set y lower (e.g. 1000) when the face sits high in frame
     image  {src: ["a.png", "b.jpg"]}               1-3 images fanned out above the head (their own photos, screenshots, stock)
     sticker {src: "sticker.png", x: 760, y: 420, size: 260}  transparent PNG that bounces on (brand stickers, emoji, logos)
     page   {bg: "image.jpg" or "#hex", title: "how it works"}   full-screen background with the clip framed below it
                                                     (the fast green-screen look: no cut-out, renders in seconds)
     motion {name: "carousel-vision-1", vars: {...}, box: [x, y, w, h]}   any HyperFrames catalog motion cached in
                                                     engine/hf (see references/motions.md for names + vars). Carousels take
                                                     images: {"images": ["a.png", ...]} and the slots are filled for you.
     custom {src: "motion/key-phrase.html", layer?: "front"|"mid", box?: [x,y,w,h], full?: true, sfx?: "whoosh"}
                                                     a HyperFrames sub-composition written for this reel (own motion design
                                                     on a phrase or sentence, or a full-screen takeover). Everything in the
                                                     src file's folder is copied along (fonts, js). Default box = full frame.
     overlay {src: "overlays/<file or asset id>", mode: "tiny"|"small-r"|"small-l"|"big"|"full", effect: "soft"|"slide"|"polaroid"|"glass"|"zoom", box?: [x,y,w,h]}
                                                     an image or video they uploaded on the review page (or dropped in the folder):
                                                     a small card top right/left, a wide panel above the head, or full screen; video muted
     bigtext {text: "big / words", y?: 330, size?, color?}   huge words in the head font; with "behind": true they sit behind the person
     (any card) "behind": true   between the background and the person: the person is cut out for that window (local AI, ~13 s per second of video, cached)
     follow {words: [{text, accent}], framing: "wide"}   caption-camera-follow in brand colours/font: one sentence
                                                     written word by word across a camera that pulls back (hook moments)
     list   {title?, rows: [..], layout?: "drop"|"notes"|"stack"|"card", y?: 980, row_times?: [..]}
                                                     a list in one of four looks; no layout = next look in turn, never the previous list's
     split  {title, rows: [..], side?: "top"|"left", color?, focus?: 28}   the screen divides: brand panel with the list,
                                                     the person slides into the other half (focus = face height in %, object-position)
     push   {text: "big / words", rows?: [..], color?, y?: 600}   наїзд кадру: a brand panel pushes the camera out to the left,
                                                     then carries on out while the camera comes back from the right
     steps  {items: ["a", "b", "c"], y?, row_times?}   numbered step panels slide up one over another
     camera {move: "in"|"out"|"whip"|"shrink"|"shake", scale?, text?: "words / here" (shrink only)}   moves the clip itself:
                                                     in = slow push-in, out = starts close and pulls back, whip = fast zoom hit,
                                                     shrink = frame pulls back into a rounded window on the brand colour (words above), shake = jolt
     (list and steps never cover the face: face.json moves them below the chin or above the head, shrinking if needed)
     (every card and caption is checked against Instagram's Reels screen: scripts/safezones.py -> <reel>/safezones.json)
  Any card: "glass": true gives the frosted liquid-glass look (card, tag).
  Style: edit.json "style" / <reel>/style.txt / REEL_STYLE / brand "style" = a ~/reels/styles/<name>.json from scripts/style_lab.py
  (brand overrides, allowed list looks and camera moves, rejected types, motion speed, caption entrance + accent look, sounds per event).
  Image paths: relative to the reel folder, or to ~/reels/assets/, or absolute.
"""
import html, json, os, re, shutil, subprocess, sys
from pathlib import Path

reel = Path(sys.argv[1]).expanduser()
CAPCUT = "--capcut" in sys.argv
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
ENGINE = Path(__file__).resolve().parent.parent / "engine"
brand = json.load(open(HOME / "brand.json"))
edit = json.load(open(reel / "edit.json"))

# ---- style (scripts/style_lab.py writes ~/reels/styles/<name>.json). Which one: edit.json "style", else <reel>/style.txt
# (the name picked before the edit; survives review_sync import), else REEL_STYLE, else brand.json "style", else none --
# {"brand": {..brand.json keys, deep-merged}, "layouts": {"list": [..], "camera": [..], "deny": [types]},
#  "motion": {"speed": 1.0}, "captions": {"anim": "pop"|"rise"|"blur"|"slam"|"none", "accent": "color"|"box"|"underline"},
#  "sounds": {"level": "none"|"subtle"|"lots", "gain_db": 0, "events": {"transition"|"row"|"title"|"hit"|"accent"|"cta"|"typing": name|null}}}
def _merge(a, b):
    out = dict(a)
    for k, v in b.items(): out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out
_st = reel / "style.txt"
STYLE, STYLE_NAME = {}, edit.get("style") or (_st.read_text().strip() if _st.exists() else "") or os.environ.get("REEL_STYLE") or brand.get("style")
if STYLE_NAME:
    _sp = Path(STYLE_NAME).expanduser()
    if not _sp.suffix: _sp = HOME / "styles" / f"{STYLE_NAME}.json"
    if not _sp.exists(): sys.exit(f"style not found: {_sp} (ls ~/reels/styles)")
    STYLE = json.load(open(_sp)); brand = _merge(brand, STYLE.get("brand", {}))
    print(f"style: {STYLE.get('title') or _sp.stem}")
S_LAY, S_MOT, S_CAP, S_SND = STYLE.get("layouts", {}), STYLE.get("motion", {}), STYLE.get("captions", {}), STYLE.get("sounds", {})
if S_SND.get("level"): brand["sfx"] = S_SND["level"]
if "gain_db" in S_SND: brand["sfx_gain_db"] = brand.get("sfx_gain_db", 8) + S_SND["gain_db"]
SFX_EVENT = {"whoosh": "transition", "whoosh_soft": "transition", "whoosh_fast": "transition", "swish": "transition",
             "pop": "row", "hit_soft": "row", "tap": "row", "snap": "title", "hit_punch": "hit", "sparkle": "accent",
             "chime": "accent", "coin": "cta", "typing": "typing"}   # built-in sound -> the event a style can re-voice
# types the style rejects: lists/splits/pushes/steps become a list in an allowed look, camera moves are dropped
for c in edit.get("cards", []):
    if c["type"] not in S_LAY.get("deny", []): continue
    print(f"style: '{c['type']}' is rejected in this style ({c['start']:.1f}s)", end=" ")
    if c["type"] in ("split", "push", "steps"):
        rows = c.get("rows") or c.get("items") or []
        c.update(type="list", rows=rows or [x.strip() for x in c.get("text", "").split("/") if x.strip()],
                 title=c.get("title") or (c.get("text", "").replace("/", " ") if c.get("rows") else ""))
        c.pop("layout", None); print("-> list")
    else: c["type"] = "_skip"; print("-> left out")
for c in edit.get("cards", []):
    if c["type"] == "camera" and S_LAY.get("camera") and c.get("move", "out") not in S_LAY["camera"]:
        if c.get("text"):   # a shrink carrying words (a number, a credential): the words stay, as big text
            print(f"style: camera '{c.get('move')}' -> big text ({c['start']:.1f}s)"); c.update(type="bigtext", y=c.get("y", 300), quiet=True); continue
        print(f"style: camera '{c.get('move', 'out')}' -> '{S_LAY['camera'][0]}' ({c['start']:.1f}s)"); c["move"] = S_LAY["camera"][0]

C = brand["colors"]
MAIN, POP, LIGHT = C["main"], C["pop"], C.get("light", "#FFFFFF")
CAP, CAP_ACC = C.get("caption", "#FFFFFF"), C.get("caption_accent", POP)
ACC_COLS = [CAP_ACC] + ([C["caption_accent_2"]] if C.get("caption_accent_2") else [])   # 2 accent colours: accent words alternate
_acc_n = [0]
def next_acc():
    _acc_n[0] += 1; return ACC_COLS[(_acc_n[0] - 1) % len(ACC_COLS)]
CAPS = brand.get("captions", {})
GLASS_ALL = bool(brand.get("glass"))
def _rgba(hexc, a):
    h = hexc.lstrip("#"); return f"rgba({int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)},{a})"
GLASS_TINT = brand.get("glass_tint") or _rgba(C["main"], 0.38)
TITLE_COLOR = brand.get("title_color", C["main"])
CASE = CAPS.get("case", "lower")
CAP_PX, CAP_Y = edit.get("caption_size", CAPS.get("size", 96)), edit.get("caption_y", CAPS.get("y", 1250))   # a reel can move its captions (e.g. above the head)
W, H, FPS = 1080, 1920, 30                     # authored at 1080x1920; 4K brands render with --resolution portrait-4k
SAFE = 900                                     # guardrail: no text line may be wider than this (90 px margin each side)
EM = 0.66                                      # conservative average glyph width (bold display fonts run ~0.6-0.66 em)
# real text widths from the font files (fontTools, in ~/reels/.venv): wide display faces (NAMU, serif italics) no longer
# spill past the frame. Without fontTools the old estimate (EM per character) is used.
try:
    import fontTools.ttLib as _ftt
except ImportError:
    for _sp in sorted((HOME / ".venv" / "lib").glob("python*/site-packages")): sys.path.append(str(_sp))
    try: import fontTools.ttLib as _ftt
    except ImportError: _ftt = None
FONT_FILE, _FONT_CACHE = {}, {}   # role -> font file (filled where the fonts are copied in)
def _advance(text, role):
    """Width of `text` at 1 px in the role's font, or None when it can't be measured."""
    f = FONT_FILE.get(role)
    if not (_ftt and f): return None
    if f not in _FONT_CACHE:
        try:
            t = _ftt.TTFont(str(f), lazy=True); _FONT_CACHE[f] = (t.getBestCmap(), t["hmtx"].metrics, t["head"].unitsPerEm)
        except Exception: _FONT_CACHE[f] = None
    if not _FONT_CACHE[f]: return None
    cmap, hm, upm = _FONT_CACHE[f]
    space = hm.get(cmap.get(32), (upm * 0.3, 0))[0]
    return sum(hm.get(cmap.get(ord(ch)), (upm * 0.62, 0))[0] if ord(ch) in cmap else upm * 0.62 for ch in text) / upm or None
def fit(text, want, extra=0, role="head"):
    """Largest size <= want at which `text` stays inside the safe area (extra = outline px on each side). Measured in the
    role's real font (no letter-spacing credit, plus 4% spare), so every text line stays in the frame whatever the font."""
    adv = _advance(text, role)
    if adv: return max(24, min(int(want), int((SAFE - 2 * extra) / (adv * 1.04))))
    return max(24, min(int(want), int((SAFE - 2 * extra) / (max(len(text), 1) * EM))))

def dur_of(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout)
DUR = round(dur_of(reel / "master.mp4") - 0.02, 2)
q = lambda t: round(round(max(t, 0) * FPS) / FPS, 4)
esc = lambda s: html.escape(s, quote=False)
case = lambda s: s.lower() if CASE == "lower" else s

# ---- project folder: template files are copied, never installed -------------------------------------------------
proj = reel / "proj"
if proj.exists(): shutil.rmtree(proj)
(proj / "fonts").mkdir(parents=True); (proj / "sfx").mkdir(); (proj / "vendor").mkdir()
shutil.copy(ENGINE / "gsap.min.js", proj / "vendor/gsap.min.js")
DRAFT = bool(os.environ.get("REEL_DRAFT"))   # fast review draft: rendered at 540x960 from a 540p copy of the master (a quarter of the pixels)
_mh = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", str(reel / "master.mp4")], capture_output=True, text=True).stdout or 1920)
if DRAFT and _mh <= 960:   # cut.py already made a 540p draft master
    shutil.copy(reel / "master.mp4", proj / "master.mp4")
elif DRAFT:
    m540 = reel / "master_540.mp4"
    if not m540.exists() or m540.stat().st_mtime < (reel / "master.mp4").stat().st_mtime:
        subprocess.run(["nice", "-n", "10", "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(reel / "master.mp4"), "-vf", "scale=540:960",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "30", "-c:a", "copy", str(m540)], check=True)
    shutil.copy(m540, proj / "master.mp4")
else:
    try: os.link(reel / "master.mp4", proj / "master.mp4")
    except OSError: shutil.copy(reel / "master.mp4", proj / "master.mp4")
for f in (ENGINE / "sfx").glob("*.wav"): shutil.copy(f, proj / "sfx" / f.name)
for f in (Path(__file__).resolve().parent.parent / "sfx").glob("*.wav"): shutil.copy(f, proj / "sfx" / f.name)   # the skill's CC0 library
for f in (HOME / "assets" / "sfx").glob("*.wav"): shutil.copy(f, proj / "sfx" / f.name)   # their own sound library wins on a shared name
(proj / "img").mkdir()
HF = ENGINE / "hf"
if any(k["type"] in ("motion", "follow", "custom") for k in edit.get("cards", [])):
    (proj / "compositions/components").mkdir(parents=True); shutil.copytree(HF / "assets", proj / "assets", dirs_exist_ok=True)
def mount(src):
    """Copy one cached motion into the reel, minus any audio it ships with (our own sound effects do that job)."""
    rel = src.relative_to(HF).as_posix()
    (proj / rel).write_text(re.sub(r"<audio[^>]*>(</audio>)?", "", src.read_text()))
    return rel
def img(src):
    """Copy an image into the project and return its path there. Looks in the reel folder, ~/reels/assets/, then as given."""
    for cand in (reel / src, HOME / "assets" / src, Path(src).expanduser()):
        if cand.exists():
            dst = proj / "img" / f"{len(list((proj / 'img').iterdir()))}_{cand.stem}.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cand), "-vf", "scale='min(1280,iw)':-2", str(dst)], check=True)
            return f"img/{dst.name}"
    print(f"warning: image not found: {src}"); return ""

# fonts: brand.json "fonts": {"head": {...}, "body": {...}, "accent": {...}}, each {family, file?, weight?, style?}
FALLBACK = "'Helvetica Neue', Helvetica, Arial, sans-serif"   # single quotes: these go inside style="..." attributes
font_css, FAM = [], {}
for role, default in (("head", {"family": "Helvetica Neue", "weight": 700}), ("body", {"family": "Helvetica Neue", "weight": 500}),
                      ("accent", {"family": "Georgia", "weight": 400, "style": "italic"})):
    f = {**default, **brand.get("fonts", {}).get(role, {})}
    if f.get("file"):
        src = Path(f["file"]).expanduser()
        if src.exists():
            shutil.copy(src, proj / "fonts" / src.name); FONT_FILE[role] = src
            fmt = {"otf": "opentype", "ttf": "truetype", "woff2": "woff2", "woff": "woff"}.get(src.suffix[1:].lower(), "opentype")
            font_css.append(f'@font-face {{ font-family: "{f["family"]}-{role}"; src: url("fonts/{src.name}") format("{fmt}"); font-display: block; }}')
            f["family"] = f'{f["family"]}-{role}'
        else:
            print(f"warning: font file not found, using fallback: {src}")
    FAM[role] = (f"'{f['family']}', {FALLBACK}", f.get("weight", 400), f.get("style", "normal"))
# caption fonts picked on the review page (edit.json "caption_fonts": {"body"|"accent": {family, file, weight, style}}); default: brand body/accent
FAM["cap"], FAM["capacc"] = FAM["body"], FAM["accent"]
FONT_FILE["cap"], FONT_FILE["capacc"] = FONT_FILE.get("body"), FONT_FILE.get("accent")
for role, key in (("body", "cap"), ("accent", "capacc")):
    f = (edit.get("caption_fonts") or {}).get(role)
    if f and Path(f["file"]).expanduser().exists():
        src = Path(f["file"]).expanduser(); shutil.copy(src, proj / "fonts" / src.name)
        fmt = {"otf": "opentype", "ttf": "truetype", "woff2": "woff2", "woff": "woff"}.get(src.suffix[1:].lower(), "truetype")
        font_css.append(f'@font-face {{ font-family: "{f["family"]}-{key}"; src: url("fonts/{src.name}") format("{fmt}"); font-display: block; }}')
        FAM[key] = (f"'{f['family']}-{key}', {FALLBACK}", f.get("weight", 400), f.get("style", "normal")); FONT_FILE[key] = src
def font(role, px):
    fam, wt, st = FAM[role]
    return f"font-family:{fam};font-weight:{wt};font-style:{st};font-size:{px}px"

back, mid, front, audio, js = [], [], [], [], []
n_sfx = 0
CAPCUT_NAME = {"swish": "whoosh-short", "whoosh": "whoosh-short", "pop": "pop", "snap": "snap", "typing": "typing",
               "chime": "chime", "sparkle": "sparkle", "coin": "coin"}   # local file -> CapCut library sound (capcut_draft.py)
def sfx(name, t, db=-12, level="subtle", dur=None):
    """Subtle, ASMR-clean accents: every effect sits 10-15 dB under the voice (db = level relative to full scale).
    level = lowest brand sfx setting that still plays it. CapCut route: recorded for CapCut's real library sounds."""
    global n_sfx
    global CARD_SFX
    if CARD_MUTE: return                                  # this graphic's sound was switched off in the review
    if CARD_SFX and level == "subtle":                    # the sound approved in the review replaces the entrance sound
        name, db = {"sparkle": "chime"}.get(CARD_SFX["name"], CARD_SFX["name"]) if not CAPCUT else CARD_SFX["name"], CARD_SFX.get("db", db)
        CARD_SFX = None
    elif SFX_EVENT.get(name) in S_SND.get("events", {}):   # the style's sound for this event (null = silent)
        name = S_SND["events"][SFX_EVENT[name]]
        if not name: return
    if brand.get("sfx", "subtle") == "none" or (level == "lots" and brand.get("sfx") != "lots") or t >= DUR: return
    vol = round(min(1.0, 10 ** ((db + brand.get("sfx_gain_db", 8)) / 20)), 3)   # +8 dB: clearly audible under a voice with no music bed
    if CAPCUT:
        SFX_OUT.append({"name": CAPCUT_NAME.get(name, name), "t": round(max(t, 0), 2), "vol": vol, **({"dur": dur} if dur else {})}); return
    p = proj / "sfx" / f"{name}.wav"
    if not p.exists(): return
    n_sfx += 1
    d = min(dur or dur_of(p), dur_of(p), DUR - t)
    audio.append(f'<audio id="sx{n_sfx}" src="sfx/{name}.wav" data-start="{q(t)}" data-duration="{q(d)}" '
                 f'data-track-index="{20 + n_sfx}" data-volume="{vol}"></audio>')
SFX_OUT = []
CARD_MUTE = False
CARD_SFX = None
ZONES = []   # where each graphic and caption sits, for the Instagram safe-zone check (scripts/safezones.py)
def zone(cid, kind, a, b, box, text=True, full=False):
    ZONES.append({"id": cid, "kind": kind, "start": round(a, 2), "end": round(b, 2), "box": [int(v) for v in box], "text": text, "full": full})
def tw(text, px):   # rough rendered width of one line, centred
    w = min(W, len(text) * EM * px); return (W - w) / 2, w
def show(sel, a, b, fade=0.18):
    b = max(b, a + 0.12); fade = min(fade, (b - a) / 2)              # very short words: keep the fade after the reveal
    js.append(f'tl.set("{sel}",{{autoAlpha:1}},{q(a)});tl.to("{sel}",{{autoAlpha:0,duration:{fade}}},{q(b - fade)});')

# ---- camera punch-ins ---------------------------------------------------------------------------------------------
CAM_WIN = [(k["start"] - 0.3, (k.get("end") or k["start"] + 1.5) + 0.3) for k in edit.get("cards", []) if k["type"] in ("camera", "push")]
for k, t in enumerate(edit.get("punch", [])):   # [t, scale] forces a zoom level (e.g. a spoken "zoom in")
    t, z = t if isinstance(t, list) else (t, 1.0 if k % 2 else 1.07)
    if any(a0 <= t <= b0 for a0, b0 in CAM_WIN): continue   # a camera move owns the camera there
    js.append(f'tl.to("#cam",{{scale:{z},duration:0.22,ease:"power3.out",overwrite:"auto"}},{q(t)});')

# ---- cards --------------------------------------------------------------------------------------------------------
# Phrases from the cut's transcript: a phrase ends at punctuation or a gap over 0.35 s. A card with no "end" clears
# when the phrase it starts in finishes (min 1 s on screen), so overlays leave with their line.
_tw = json.load(open(reel / "master_transcript.json")) if (reel / "master_transcript.json").exists() else []
PHRASE_ENDS = [w["end"] for k, w in enumerate(_tw) if re.search(r"[.,!?;:]$", w["text"]) or k + 1 == len(_tw)
               or _tw[k + 1]["start"] - w["end"] > 0.35]
def phrase_end(t):
    return next((e + 0.15 for e in PHRASE_ENDS if e > t + 1.0), min(t + 2.5, DUR))

# the face (scripts/face_box.py -> face.json {"box": [x, y, w, h]}, cut-reel pixels): lists and steps never cover it
_fj = reel / "face.json"
FACE = json.load(open(_fj)).get("box") if _fj.exists() else None
def off_face(c, h, default_y):
    """Where a block of height h goes so it misses the face: (y, scale). Below the chin if it fits above Instagram's
    bottom bar, else above the head, else shrunk into the bigger of the two gaps. "behind": true or "keep_y": true = as given."""
    y = c.get("y", default_y)
    if not FACE or c.get("behind") or c.get("keep_y"): return y, 1.0
    fx, fy, fw, fh = FACE
    head, chin = fy - 0.12 * fh, fy + fh                       # hair above the face box counts too
    if (230 <= y and y + h <= head - 10) or (y >= chin + 10 and y + h <= 1480): return y, 1.0   # clear of the face and of Instagram's bars
    below, above = (chin + 30, 1480 - (chin + 30)), (230, head - 20 - 230)
    for top, room in (below, above):
        if h <= room: return int(top), 1.0
    top, room = max((below, above), key=lambda r: r[1])
    return int(top), max(0.5, room / h)
def zwrap(layer, y, z):
    """Shrink the block just added to a layer around its top centre (the block's own tweens stay untouched)."""
    if z < 0.999: layer[-1] = f'<div class="zw" style="transform:scale({z:.3f});transform-origin:540px {y}px">{layer[-1]}</div>'

def row_times(c, a, b, n, first=0.45):
    """When each row/step appears: the card's own "row_times" (spoken moments), else evenly spread, at most 0.9 s apart."""
    if c.get("row_times"): return c["row_times"][:n] + [c["row_times"][-1] + 0.4 * (k + 1) for k in range(n - len(c["row_times"]))]
    gap = min(0.9, max(0.3, (b - a - first - 0.8) / max(n, 1)))
    return [a + first + gap * k for k in range(n)]

# variety: a "list" card with no layout (or "auto") gets the next look in turn, never the one the previous list had.
# The previous list-like graphic counts too ("card" = the white UI card).
LIST_LAYOUTS = [l for l in ["drop", "notes", "stack", "card"] if l in S_LAY.get("list", ["drop", "notes", "stack", "card"])] or ["card"]
_prev, _turn = None, 0
for c in edit.get("cards", []):
    if c["type"] == "card": _prev = "card"
    if c["type"] != "list": continue
    if c.get("layout", "auto") not in LIST_LAYOUTS + ["auto"]:   # a look this style rejected
        print(f"style: list look '{c['layout']}' is not in this style ({c['start']:.1f}s) - using the style's looks"); c["layout"] = "auto"
    if c.get("layout", "auto") == "auto":
        pick = ([l for l in LIST_LAYOUTS[_turn:] + LIST_LAYOUTS[:_turn] if l != _prev] or LIST_LAYOUTS)[0]
        _turn = (LIST_LAYOUTS.index(pick) + 1) % len(LIST_LAYOUTS); c["layout"] = pick
    elif c["layout"] == _prev: print(f"variety: two lists in a row use the '{_prev}' layout ({c['start']:.1f}s) - pick another")
    _prev = c["layout"]
_seq = [(k["type"] + ("/" + k["layout"] if k.get("layout") else "")) for k in sorted(edit.get("cards", []), key=lambda k: k["start"])]
for k in range(len(_seq) - 2):
    if _seq[k] == _seq[k + 1] == _seq[k + 2]: print(f"variety: three '{_seq[k]}' graphics in a row - swap one for a list, split, push or steps")

quiet = []                                      # spans where a card carries its own words, so captions step aside
# "behind": true on a card puts it between the background and the person: the person is cut out (AI matting, local)
# for that window and laid back on top, so text, photos or motion sit behind them.
behind, BEHIND_WIN = [], []
_BACK, _MID, _FRONT = back, mid, front
for i, c in enumerate(edit.get("cards", [])):
    CARD_MUTE = c.get("sfx") is False
    CARD_SFX = c.get("sfx") if isinstance(c.get("sfx"), dict) else None
    a, b, cid = c["start"], c.get("end") or phrase_end(c["start"]), f"k{i}"
    b = min(b, DUR)
    kind = c["type"]
    back, mid, front = (behind, behind, behind) if c.get("behind") else (_BACK, _MID, _FRONT)
    if c.get("quiet"): quiet.append((a, b))      # review_sync: no room for this card and the captions at once
    if c.get("behind"): BEHIND_WIN.append((a, b))
    if kind == "_skip": continue                 # a type the style rejects (see the style block at the top)
    if kind == "bigtext":
        # big words in the brand's head font, usually behind the head ("behind": true); "/" breaks lines
        lines = [case(x.strip()) for x in c.get("text", "").split("/") if x.strip()]
        px = c.get("size") or min(fit(max(lines, key=len), 320), 320)
        front.append(f'<div id="{cid}" class="bigtext" style="top:{c.get("y", 430)}px;{font("head", px)};color:{c.get("color", LIGHT)}">'
                     + "".join(f'<div class="btl">{esc(x)}</div>' for x in lines) + "</div>")
        show(f"#{cid}", a, b, 0.2)
        js.append(f'tl.fromTo("#{cid} .btl",{{y:140,opacity:0}},{{y:0,opacity:1,duration:0.6,ease:"power3.out",stagger:0.12}},{q(a)});')
        sfx("whoosh", a - 0.05, -13)
        zone(cid, "bigtext", a, b, (*tw(max(lines, key=len), px)[:1], c.get("y", 430), tw(max(lines, key=len), px)[1], len(lines) * px * 0.86))
        continue
    if kind == "title":
        lines = [case(x.strip()) for x in c["text"].split("/")]
        if c.get("quiet", True): quiet.append((a, b))                    # the hook says it: captions step aside ("quiet": false keeps them)
        sizes = [c.get("size") or min(fit(x, 230, 230 // 16), brand.get("title_max_px", 999)) for x in lines]   # each line fitted on its own, outline included; "size" overrides (tight-tracked fonts fit bigger)
        ol = brand.get("title_outline", "#FFFFFF")                     # outline is for the hook title only, never captions
        olw = brand.get("title_outline_px")                            # fixed outline width (e.g. 2 for a faint hairline); default scales with size
        st = lambda px: f";-webkit-text-stroke:{olw or max(6, px // 16)}px {ol};paint-order:stroke fill" if ol else ""
        back.append(f'<div id="{cid}" class="title" style="{font("head", sizes[0])};top:{c.get("y", brand.get("title_y", 360))}px;color:{c.get("color", TITLE_COLOR)};letter-spacing:{brand.get("title_tracking", -0.045)}em">'
                    + ('<div class="tg glass">' if brand.get("title_glass") else "")
                    + "".join(f'<div class="tl" style="font-size:{px}px;text-align:{("left", "right")[j % 2] if len(lines) > 1 and not brand.get("title_glass") else "center"}{st(px)}">{esc(x)}</div>' for j, (x, px) in enumerate(zip(lines, sizes)))
                    + ("</div>" if brand.get("title_glass") else "") + "</div>")
        show(f"#{cid}", a, b)
        if brand.get("title_glass"): js.append(f'tl.fromTo("#{cid} .tg",{{scale:0.9,opacity:0,filter:"blur(10px)"}},{{scale:1,opacity:1,filter:"blur(0px)",duration:0.4,ease:"power3.out"}},{q(a - 0.05)});')
        js.append(f'tl.fromTo("#{cid} .tl",{{clipPath:"inset(-40% 100% -40% 0%)",x:-30}},{{clipPath:"inset(-40% 0% -40% 0%)",x:0,duration:0.34,ease:"power3.out",stagger:0.25}},{q(a)});')
        sfx("snap", a + 0.03, -11)
        _x, _w = tw(max(lines, key=len), max(sizes))
        zone(cid, "title", a, b, (_x, c.get("y", brand.get("title_y", 360)), _w, sum(sizes) * 0.88))
    elif kind == "block":
        quiet.append((a, b))
        mid.append(f'<div id="{cid}" class="block" style="opacity:0;visibility:hidden;background:{c.get("color", MAIN)}">'
                   f'<div class="frame"><video id="{cid}v" src="master.mp4" muted playsinline data-start="{q(a)}" data-duration="{q(b - a)}" data-media-start="{q(a)}" data-track-index="{9 + i}"></video></div>'
                   f'<div class="bl" style="{font("head", fit(c.get("top", ""), 210))};top:230px;text-align:left;color:{LIGHT}">{esc(case(c.get("top", "")))}</div>'
                   f'<div class="bl" style="{font("head", fit(c.get("bottom", ""), 210))};top:{1480 - int(fit(c.get("bottom", ""), 210) * 0.82)}px;text-align:right;color:#fff">{esc(case(c.get("bottom", "")))}</div></div>')
        js.append(f'tl.set("#{cid}",{{autoAlpha:1}},{q(a)});tl.fromTo("#{cid}",{{clipPath:"inset(0% 0% 0% 100%)"}},{{clipPath:"inset(0% 0% 0% 0%)",duration:0.22,ease:"power3.out"}},{q(a)});'
                  f'tl.fromTo("#{cid} .frame",{{scale:0.82}},{{scale:1,duration:0.5,ease:"back.out(1.6)"}},{q(a + 0.05)});'
                  f'tl.fromTo("#{cid} .bl",{{clipPath:"inset(-40% 100% -40% 0%)"}},{{clipPath:"inset(-40% 0% -40% 0%)",duration:0.34,ease:"power3.out",stagger:0.3}},{q(a + 0.12)});'
                  f'tl.to("#{cid}",{{clipPath:"inset(0% 100% 0% 0%)",duration:0.2,ease:"power3.in"}},{q(b - 0.2)});tl.set("#{cid}",{{autoAlpha:0}},{q(b)});')
        sfx("swish", a - 0.08, -12)
        zone(cid, "block", a, b, (0, 0, W, H), full=True)
        for _t, _y in ((c.get("top", ""), 230), (c.get("bottom", ""), 1480 - int(fit(c.get("bottom", ""), 210) * 0.82))):
            if _t: zone(cid, "block text", a, b, (90, _y, 900, fit(_t, 210) * 0.82))
    elif kind == "overlay":
        # an image or video they uploaded at a moment on the review page (or dropped in the reel folder).
        # mode (size): "full" covers the frame, "big" a wide panel above the head, "small-r"/"small-l" a small card top right/left.
        # effect: soft (fade + settle), slide (flies in from the side), polaroid (white frame, tilted), glass (brand frosted
        # frame), zoom (slow push-in). Video plays muted: her voice carries on.
        src = next((p for p in (reel / c["src"], HOME / "assets" / c["src"], Path(c["src"]).expanduser()) if p.is_file()), None) \
            or next(iter(sorted((reel / Path(c["src"]).parent).glob(Path(c["src"]).name + ".*"))), None)
        if not src: print(f"warning: overlay not found: {c['src']} (download it first)"); continue
        mode = {"box": "big"}.get(c.get("mode", "big"), c.get("mode", "big"))
        x, y, ow, oh = c.get("box") or {"full": (0, 0, 1080, 1920), "big": (90, 150, 900, 640), "small-r": (600, 170, 400, 500),
                        "small-l": (80, 170, 400, 500), "tiny": (760, 260, 200, 200)}.get(mode, (90, 150, 900, 640))   # "box": where they dragged it on the page
        full = ow >= 1080 and oh >= 1920
        if not full and y < CAP_Y + 150 and y + oh > CAP_Y - 60: quiet.append((a, b))   # sits on the caption line: captions step aside
        fx = c.get("effect", "soft")
        if full and fx in ("polaroid", "glass"): fx = "soft"                 # a frame needs a border around it: not on a full screen
        frame = {"polaroid": "padding:14px 14px 48px;background:#fff;border-radius:6px;box-shadow:0 30px 70px rgba(0,0,0,.35)",
                 "glass": f"padding:12px;background:{GLASS_TINT};border:1.5px solid rgba(255,255,255,.45);border-radius:30px;"
                          "backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);box-shadow:0 24px 60px rgba(0,0,0,.28)"}.get(fx,
                 "" if full else "border-radius:28px;border:3px solid rgba(255,255,255,.55);box-shadow:0 24px 60px rgba(0,0,0,.3)")
        inner_r = "0" if full else ("2px" if fx == "polaroid" else "20px" if fx == "glass" else "25px")
        cover = "width:100%;height:100%;object-fit:cover;display:block"
        if src.suffix.lower() in (".png", ".webp") and fx not in ("polaroid", "glass"):
            try:   # a cut-out element (transparent PNG, e.g. their chrome stickers): no frame, shown whole
                from PIL import Image as _I
                _im = _I.open(src)
                if _im.mode in ("RGBA", "LA", "P") and _im.convert("RGBA").getchannel("A").getextrema()[0] < 250:
                    frame, inner_r, cover = "", "0", "width:100%;height:100%;object-fit:contain;display:block"
            except Exception: pass
        if src.suffix.lower() in (".mp4", ".mov", ".m4v", ".webm"):
            b = min(b, a + dur_of(src))                                      # never outlast the clip
            dst = proj / "img" / f"ov{i}.mp4"                                # one clean H.264 copy at its display size, no audio
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" if full else "scale=1280:-2"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-an", "-vf", vf + ",fps=30", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "14", "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p", str(dst)], check=True)
            media = (f'<video id="{cid}v" src="img/{dst.name}" muted playsinline data-start="{q(a)}" data-duration="{q(b - a)}" '
                     f'data-media-start="0" data-track-index="{9 + i}" style="{cover}"></video>')
        else:
            media = f'<img src="{img(str(src))}" style="{cover}" />'
        (mid if full else front).append(
            f'<div id="{cid}" style="position:absolute;left:{x}px;top:{y}px;width:{ow}px;height:{oh}px;box-sizing:border-box;{frame};opacity:0;visibility:hidden">'
            f'<div class="m" style="width:100%;height:100%;overflow:hidden;border-radius:{inner_r}">{media}</div></div>')
        show(f"#{cid}", a, b, 0.15)
        side = -1 if x + ow / 2 < 540 else 1                               # flies in / tilts from the side of the frame it sits on
        js.append({
            "slide": f'tl.fromTo("#{cid}",{{x:{side * 760},rotation:{side * 6}}},{{x:0,rotation:0,duration:0.55,ease:"back.out(1.3)"}},{q(a)});',
            "polaroid": f'tl.fromTo("#{cid}",{{y:-260,rotation:{-side * 16},scale:0.9}},{{y:0,rotation:{-side * 4},scale:1,duration:0.6,ease:"back.out(1.5)"}},{q(a)});',
            "glass": f'tl.fromTo("#{cid}",{{scale:0.8,filter:"blur(10px)"}},{{scale:1,filter:"blur(0px)",duration:0.45,ease:"back.out(1.6)"}},{q(a)});',
        }.get(fx, f'tl.fromTo("#{cid}",{{scale:{1.04 if full else 0.85}}},{{scale:1,duration:0.4,ease:"power3.out"}},{q(a)});'))
        if fx == "zoom":   # slow push-in on the picture itself for the whole time it is on screen
            js.append(f'tl.fromTo("#{cid} .m > *",{{scale:1}},{{scale:1.14,duration:{max(b - a, 0.5):.2f},ease:"none"}},{q(a)});')
        sfx("whoosh" if fx == "slide" else "pop" if fx == "polaroid" else "swish", a - 0.05, -13)
        zone(cid, "overlay", a, b, (x, y, ow, oh), text=False, full=full)
    elif kind == "card":
        rows = c.get("rows", [])
        rt = c.get("row_times") or [a + 0.45 + 0.35 * j for j in range(len(rows))]
        front.append(f'<div id="{cid}" class="card{" glass" if c.get("glass", GLASS_ALL) else ""}"' + (f' style="top:{c["y"] / c.get("zoom", 1):.0f}px;left:{c.get("x", 90) / c.get("zoom", 1):.0f}px;zoom:{c.get("zoom", 1)}"' if "y" in c else "") + f'><div class="ch" style="background:{MAIN};{font("head", 40)}"><i></i>{esc(case(c.get("title", "")))}</div>'
                     + "".join(f'<div class="cr" id="{cid}r{j}" style="{font("body", 50)};color:{MAIN}"><b style="background:{POP}"></b>{esc(case(r))}</div>' for j, r in enumerate(rows)) + "</div>")
        show(f"#{cid}", a, b)
        js.append(f'tl.fromTo("#{cid}",{{y:-160,scale:0.85,rotation:-3}},{{y:0,scale:1,rotation:-1.5,duration:0.5,ease:"back.out(1.6)"}},{q(a)});')
        for j, t in enumerate(rt):
            js.append(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,x:-60}},{{autoAlpha:1,x:0,duration:0.3,ease:"back.out(2)"}},{q(t)});')
            sfx("pop", t, -16, "lots")
        sfx("swish", a - 0.05, -13)
        zone(cid, "card", a, b, (c.get("x", 90), c.get("y", 150), 900 * c.get("zoom", 1), (100 + 110 * len(rows)) * c.get("zoom", 1)))
    elif kind == "tag":
        front.append(f'<div id="{cid}" class="tagw" style="top:{c.get("y", 300)}px"><span class="tag{" glass" if c.get("glass", GLASS_ALL) else ""}" style="background:{c.get("color", POP)};{font("head", 58)}">{esc(case(c["text"]))}</span></div>')
        show(f"#{cid}", a, b)
        js.append(f'tl.fromTo("#{cid} .tag",{{scale:0.4,y:30,opacity:0}},{{scale:1,y:0,opacity:1,duration:0.42,ease:"back.out(3)"}},{q(a)});')
        sfx("pop", a, -14)
        zone(cid, "tag", a, b, (tw(c["text"], 58)[0] - 42, c.get("y", 300), tw(c["text"], 58)[1] + 84, 100))
    elif kind == "cta":
        quiet.append((a, b))
        words = c["text"].split()
        inner = " ".join(f'<span style="color:{MAIN if brand.get("cta_bg", LIGHT).lower() == POP.lower() else POP}">{esc(w)}</span>' if w.isupper() and len(w) > 1 else esc(case(w)) for w in words)
        front.append(f'<div id="{cid}" class="ctaw" style="top:{c.get("y", 1360)}px"><span class="cta{" glass" if c.get("glass", brand.get("cta_glass", GLASS_ALL)) else ""}" style="{font("head", brand.get("cta_px", 78))};color:{MAIN};background:{brand.get("cta_bg", LIGHT)}">{inner}</span></div>')
        show(f"#{cid}", a, b)
        js.append(f'tl.fromTo("#{cid} .cta",{{scale:0.5,y:60,opacity:0}},{{scale:1,y:0,opacity:1,duration:0.5,ease:"back.out(2.4)"}},{q(a)});')
        sfx("coin", a + 0.1, -12)
        _px = brand.get("cta_px", 78); zone(cid, "cta", a, b, (tw(c["text"], _px)[0] - 48, c.get("y", 1360), tw(c["text"], _px)[1] + 96, _px * 1.2 + 44))
    elif kind == "shot":
        if c.get("y", 130) + 700 > CAP_Y: quiet.append((a, b))         # screenshot covers the caption zone: captions step aside
        front.append(f'<div id="{cid}" class="shot" style="top:{c.get("y", 130)}px"><div class="bar"><i style="background:#FF5F57"></i><i style="background:#FEBC2E"></i><i style="background:#28C840"></i>'
                     f'<span style="{font("body", 30)}">{esc(c.get("label", ""))}</span></div><div class="vp"><img src="{img(c["src"])}" /></div></div>')
        show(f"#{cid}", a, b)
        js.append(f'tl.fromTo("#{cid}",{{y:-200,scale:0.8,rotation:3}},{{y:0,scale:1,rotation:1.5,duration:0.55,ease:"back.out(1.5)"}},{q(a)});'
                  f'tl.fromTo("#{cid} img",{{y:0}},{{y:-120,duration:{max(b - a - 0.8, 0.5):.2f},ease:"sine.inOut"}},{q(a + 0.6)});')
        sfx("swish", a - 0.05, -12); sfx("typing", a + 0.5, -17, dur=0.8)
        zone(cid, "shot", a, b, (70, c.get("y", 130), 940, 684), text=False)
    elif kind == "image":
        srcs = c["src"] if isinstance(c["src"], list) else [c["src"]]
        spots = {1: [(540, 0)], 2: [(380, -6), (700, 7)], 3: [(300, -8), (540, 3), (780, 9)]}[min(len(srcs), 3)]
        front.append(f'<div id="{cid}" class="imgs">' + "".join(
            f'<img class="ph" src="{img(s)}" style="left:{x - 210}px;transform:rotate({r}deg)" />' for s, (x, r) in zip(srcs, spots)) + "</div>")
        show(f"#{cid}", a, b)
        js.append(f'tl.fromTo("#{cid} .ph",{{y:-260,opacity:0,scale:0.7}},{{y:0,opacity:1,scale:1,duration:0.5,ease:"back.out(1.7)",stagger:0.18}},{q(a)});')
        sfx("swish", a, -13)
        zone(cid, "image", a, b, (90, 140, 900, 560), text=False)
    elif kind == "sticker":
        sz = c.get("size", 260)
        front.append(f'<div id="{cid}" class="stk" style="left:{c.get("x", 760) - sz // 2}px;top:{c.get("y", 420) - sz // 2}px;width:{sz}px"><img src="{img(c["src"])}" /></div>')
        show(f"#{cid}", a, b, 0.15)
        js.append(f'tl.fromTo("#{cid}",{{scale:0,rotation:-25}},{{scale:1,rotation:{c.get("rotate", 6)},duration:0.5,ease:"back.out(3)"}},{q(a)});')
        sfx("pop", a, -13)
        zone(cid, "sticker", a, b, (c.get("x", 760) - sz // 2, c.get("y", 420) - sz // 2, sz, sz), text=False)
    elif kind == "page":
        bg = c.get("bg", LIGHT)
        rgb = tuple(int(LIGHT.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4))
        fade = f"linear-gradient(rgba({rgb[0]},{rgb[1]},{rgb[2]},.92) 0%, rgba({rgb[0]},{rgb[1]},{rgb[2]},.55) 28%, rgba({rgb[0]},{rgb[1]},{rgb[2]},.15) 60%)"
        bgcss = f"background:{bg}" if bg.startswith("#") else f"background:{fade}, url('{img(bg)}') center/cover"   # fade keeps the title readable
        mid.append(f'<div id="{cid}" class="page" style="opacity:0;visibility:hidden;{bgcss}">'
                   + (f'<div class="pt" style="{font("head", 92)};color:{c.get("color", LIGHT if str(c.get("bg", "")).lower() in (MAIN.lower(), C.get("deep", "").lower()) else MAIN)}">{esc(case(c["title"]))}</div>' if c.get("title") else "")
                   + f'<div class="pf"><video id="{cid}v" src="master.mp4" muted playsinline data-start="{q(a)}" data-duration="{q(b - a)}" data-media-start="{q(a)}" data-track-index="{9 + i}"></video></div></div>')
        js.append(f'tl.set("#{cid}",{{autoAlpha:1}},{q(a)});tl.fromTo("#{cid}",{{clipPath:"inset(100% 0% 0% 0%)"}},{{clipPath:"inset(0% 0% 0% 0%)",duration:0.3,ease:"power3.out"}},{q(a)});'
                  f'tl.fromTo("#{cid} .pf",{{y:300}},{{y:0,duration:0.5,ease:"back.out(1.4)"}},{q(a + 0.08)});'
                  f'tl.to("#{cid}",{{clipPath:"inset(0% 0% 100% 0%)",duration:0.25,ease:"power3.in"}},{q(b - 0.25)});tl.set("#{cid}",{{autoAlpha:0}},{q(b)});')
        sfx("swish", a - 0.08, -12)
        zone(cid, "page", a, b, (0, 0, W, H), full=True)
        if c.get("title"): zone(cid, "page title", a, b, (*tw(c["title"], 92)[:1], 150, tw(c["title"], 92)[1], 92))
    elif kind == "motion":
        src = next((f for f in (HF / "compositions").rglob(f"{c['name']}.html")), None)
        if not src:
            print(f"warning: motion {c['name']!r} not cached - add it: cd {HF} && npx hyperframes add {c['name']}"); continue
        rel = mount(src); txt = src.read_text()
        comp_id = re.search(r'data-composition-id="([^"]+)"', txt).group(1)
        nw, nh = (int(re.search(r'data-width="(\d+)"', txt).group(1)), int(re.search(r'data-height="(\d+)"', txt).group(1))) \
            if re.search(r'data-width="(\d+)"', txt) else (1080, 1080)
        vars_ = dict(c.get("vars", {}))
        if c.get("images"):                              # carousels: fill every image slot, cycling the supplied images
            slots = sorted({int(m) for m in re.findall(r'"id":\s*"image(\d+)"', txt)})
            ims = [img(x) for x in c["images"]]
            for k, sl in enumerate(slots): vars_[f"image{sl}"] = ims[k % len(ims)]
            vars_.setdefault("background", "transparent")
        x, y, bw, bh = c.get("box", [0, 160, W, int(W * nh / nw)])
        sc = bw / nw
        if y + bh * 0.7 > CAP_Y: quiet.append((a, b))   # motion sits over the caption zone: captions step aside
        vals = html.escape(json.dumps(vars_), quote=True)
        mid.append(f'<div id="{cid}" class="clip" data-composition-id="{comp_id}" data-composition-src="{rel}" data-variable-values="{vals}" '
                   f'data-start="{q(a)}" data-duration="{q(b - a)}" data-track-index="{40 + i}" data-width="{nw}" data-height="{nh}" '
                   f'style="position:absolute;left:{x}px;top:{y}px;width:{nw}px;height:{nh}px;transform:scale({sc:.4f});transform-origin:0 0;'
                   f'--brand:{MAIN};--accent:{POP};--accent-2:{C.get("soft", POP)};--surface:{LIGHT};--fg:{MAIN};--muted:{C.get("soft", POP)}"></div>')
        sfx("swish", a - 0.05, -12)
        zone(cid, "motion", a, b, (x, y, bw, bh), text=False)
    elif kind == "custom":
        src = next((cand for cand in (reel / c["src"], HOME / "motion" / c["src"], Path(c["src"]).expanduser()) if cand.exists()), None)
        if not src:
            print(f"warning: custom motion not found: {c['src']}"); continue
        dst_dir = proj / "custom" / f"c{i}"
        shutil.copytree(src.parent, dst_dir, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.mp4", "*.mov", "proj", "renders"))
        rel = (dst_dir / src.name).relative_to(proj).as_posix()
        txt = src.read_text()
        m = re.search(r'data-composition-id="([^"]+)"', txt)
        if not m:
            print(f"warning: {src.name} has no data-composition-id, skipped"); continue
        comp_id = m.group(1)
        nw = int(re.search(r'data-width="(\d+)"', txt).group(1)) if re.search(r'data-width="(\d+)"', txt) else W
        nh = int(re.search(r'data-height="(\d+)"', txt).group(1)) if re.search(r'data-height="(\d+)"', txt) else H
        x, y, bw, bh = c.get("box", [0, 0, W, H])
        sc = bw / nw
        if c.get("full") or y + bh * 0.7 > CAP_Y: quiet.append((a, b))   # over the caption zone: captions step aside
        vals = html.escape(json.dumps(c.get("vars", {})), quote=True)
        (front if c.get("layer", "front") == "front" else mid).append(
            f'<div id="{cid}" class="clip" data-composition-id="{comp_id}" data-composition-src="{rel}" data-variable-values="{vals}" '
            f'data-start="{q(a)}" data-duration="{q(b - a)}" data-track-index="{40 + i}" data-width="{nw}" data-height="{nh}" '
            f'style="position:absolute;left:{x}px;top:{y}px;width:{nw}px;height:{nh}px;transform:scale({sc:.4f});transform-origin:0 0"></div>')
        if c.get("sfx", "whoosh"): sfx(c.get("sfx", "whoosh"), a - 0.05, -12)
        zone(cid, "custom", a, b, (x, y, bw, bh), text=False, full=bw >= W and bh >= H)
    elif kind == "follow":
        src = HF / "compositions/components/caption-camera-follow.html"
        t = src.read_text()
        words = [{"text": case(w["text"]), **({"accent": True} if w.get("accent") else {})} for w in c["words"]]
        n = max(len(words), 1); dur = b - a
        t = re.sub(r"var WORDS = \[.*?\];", lambda _: "var WORDS = " + json.dumps(words) + ";", t, flags=re.S)   # lambda: \u escapes from non-Latin words are not regex escapes
        t = t.replace("var DUR = 9;", f"var DUR = {dur:.2f};").replace("var STEP = 0.52;", f"var STEP = {max(0.22, (dur - 1.2) / n):.3f};")
        t = t.replace('var ACCENT = ACCENTS[pick(ACCENTS, vars.accent, "gold")];', f'var ACCENT = "{CAP_ACC}";')
        t = t.replace('data-duration="9"', f'data-duration="{dur:.2f}"')
        fam = FAM["head"][0].replace("'", '"')
        t = t.replace('font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;', f"font-family: {fam};")
        t = t.replace("'font-family:\"Helvetica Neue\",Helvetica,Arial,sans-serif;font-weight:700;'", "'font-family:" + fam.replace('"', '\\"') + ";font-weight:700;'")
        if CASE == "lower": t = t.replace("text-transform: uppercase;", "text-transform: none;").replace('"text-transform:uppercase;', '"text-transform:none;')
        t = t.replace("<style>", "<style>\n" + "\n".join(font_css), 1)   # sub-compositions need their own @font-face
        out = proj / "compositions" / f"follow-{i}.html"; out.write_text(t)
        vals = html.escape(json.dumps({"framing": c.get("framing", "wide"), "smear": c.get("smear", "subtle")}), quote=True)
        front.append(f'<div id="{cid}" class="clip" data-composition-id="caption-camera-follow" data-composition-src="compositions/follow-{i}.html" '
                     f'data-variable-values="{vals}" data-start="{q(a)}" data-duration="{q(dur)}" data-track-index="{40 + i}" '
                     f'style="position:absolute;inset:0;width:{W}px;height:{H}px"></div>')
        quiet.append((a, b)); sfx("sparkle", a, -12)
    elif kind == "list":
        # a list in one of several looks, so a reel with many lists never repeats one ("layout" picked in the pre-pass)
        quiet.append((a, b))
        lay, rows = c["layout"], [case(r) for r in c.get("rows", [])]
        rt = row_times(c, a, b, len(rows))
        ttl = case(c.get("title", ""))
        dpx = min(fit(max(rows, key=len, default="") + "00", 84), 84)
        lh = {"drop": (60 if ttl else 0) + len(rows) * dpx * 1.25, "notes": (70 if ttl else 20) + len(rows) * 78 + 48,
              "stack": (66 if ttl else 0) + len(rows) * 94 + 10}.get(lay, 100 + 110 * len(rows))
        y0, z = off_face(c, lh, 1180)
        if lay == "drop":      # big words drop in one by one over the video, numbered
            px = dpx
            front.append(f'<div id="{cid}" class="ld" style="top:{y0}px">'
                         + (f'<div class="ldt" style="{font("head", 44)};background:{POP};color:{MAIN}">{esc(ttl)}</div>' if ttl else "")
                         + "".join(f'<div class="ldr" id="{cid}r{j}" style="{font("head", px)};color:{LIGHT}"><span class="ldn" style="{font("head", px * 0.5)};background:{C.get("soft", POP)};color:{MAIN}">{j + 1}</span>{esc(r)}</div>' for j, r in enumerate(rows)) + "</div>")
            show(f"#{cid}", a, b)
            if ttl: js.append(f'tl.fromTo("#{cid} .ldt",{{clipPath:"inset(-40% 100% -40% 0%)"}},{{clipPath:"inset(-40% 0% -40% 0%)",duration:0.3,ease:"power3.out"}},{q(a)});')
            for j, t in enumerate(rt):
                js.append(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,y:-160,rotation:{(-5, 4)[j % 2]}}},{{autoAlpha:1,y:0,rotation:0,duration:0.5,ease:"bounce.out"}},{q(t)});')
                sfx("hit_soft" if j % 2 else "pop", t + 0.25, -15)
            zwrap(front, y0, z)
        elif lay == "notes":   # a phone-notes sheet: each line types on, then its circle ticks in the soft colour
            front.append(f'<div id="{cid}" class="ln" style="top:{y0}px">'
                         + (f'<div class="lnt" style="{font("head", 44)};color:{MAIN}">{esc(ttl)}</div>' if ttl else "")
                         + "".join(f'<div class="lnr" id="{cid}r{j}"><span class="lnc" style="border-color:{MAIN}"><svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" stroke="{MAIN}"/></svg></span>'
                                   f'<span class="lnx" style="{font("body", min(fit(r, 50, 70), 50))};color:{MAIN}">{esc(r)}</span></div>' for j, r in enumerate(rows)) + "</div>")
            show(f"#{cid}", a, b)
            js.append(f'tl.fromTo("#{cid}",{{y:80,opacity:0,scale:0.96}},{{y:0,opacity:1,scale:1,duration:0.4,ease:"power3.out"}},{q(a)});')
            soft = C.get("soft", POP)
            for j, t in enumerate(rt):
                js.append(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0}},{{autoAlpha:1,duration:0.05}},{q(t)});'
                          f'tl.fromTo("#{cid}r{j} .lnx",{{clipPath:"inset(-40% 100% -40% 0%)"}},{{clipPath:"inset(-40% 0% -40% 0%)",duration:0.45,ease:"steps(12)"}},{q(t)});'
                          f'tl.to("#{cid}r{j} .lnc",{{backgroundColor:"{soft}",borderColor:"{soft}",duration:0.15}},{q(t + 0.5)});'
                          f'tl.fromTo("#{cid}r{j} path",{{strokeDashoffset:30}},{{strokeDashoffset:0,duration:0.25,ease:"power2.out"}},{q(t + 0.52)});')
                sfx("typing", t, -19, dur=0.45); sfx("tap", t + 0.5, -14)
            zwrap(front, y0, z)
        elif lay == "stack":   # every item its own card, flying in from the side and piling up
            cols = [(LIGHT, MAIN), (POP, MAIN), (C.get("soft", POP), MAIN)]
            front.append(f'<div id="{cid}" class="ls" style="top:{y0}px">'
                         + (f'<div class="ldt" style="{font("head", 44)};background:{MAIN};color:{LIGHT}">{esc(ttl)}</div>' if ttl else "")
                         + "".join(f'<div class="lsr" id="{cid}r{j}" style="top:{(66 if ttl else 0) + j * 94}px;{font("head", min(fit(r, 54, 40), 54))};background:{cols[j % 3][0]};color:{cols[j % 3][1]};transform:rotate({(-1.5, 1.5)[j % 2]}deg)">{esc(r)}</div>' for j, r in enumerate(rows)) + "</div>")
            show(f"#{cid}", a, b)
            if ttl: js.append(f'tl.fromTo("#{cid} .ldt",{{scale:0.4,opacity:0}},{{scale:1,opacity:1,duration:0.35,ease:"back.out(3)"}},{q(a)});')
            for j, t in enumerate(rt):
                side = (1, -1)[j % 2]
                js.append(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,x:{side * 900},rotation:{side * 14}}},{{autoAlpha:1,x:0,rotation:{(-1.5, 1.5)[j % 2]},duration:0.5,ease:"back.out(1.4)"}},{q(t)});')
                sfx("swish", t - 0.04, -15)
            zwrap(front, y0, z)
        else:   # "card": the white UI card, same as type "card"
            rows_c = c.get("rows", [])
            front.append(f'<div id="{cid}" class="card{" glass" if c.get("glass", GLASS_ALL) else ""}" style="top:{y0}px"><div class="ch" style="background:{MAIN};{font("head", 40)}"><i></i>{esc(ttl)}</div>'
                         + "".join(f'<div class="cr" id="{cid}r{j}" style="{font("body", 50)};color:{MAIN}"><b style="background:{POP}"></b>{esc(case(r))}</div>' for j, r in enumerate(rows_c)) + "</div>")
            show(f"#{cid}", a, b)
            js.append(f'tl.fromTo("#{cid}",{{y:-160,scale:0.85,rotation:-3}},{{y:0,scale:1,rotation:-1.5,duration:0.5,ease:"back.out(1.6)"}},{q(a)});')
            for j, t in enumerate(rt):
                js.append(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,x:-60}},{{autoAlpha:1,x:0,duration:0.3,ease:"back.out(2)"}},{q(t)});')
            sfx("swish", a - 0.05, -13)
            zwrap(front, y0, z)
        zone(cid, "list " + lay, a, b, (540 - 450 * z, y0, 900 * z, lh * z))
    elif kind == "split":
        # the screen splits: the person slides into one half, a brand panel with the list fills the other
        quiet.append((a, b))
        side, rows = c.get("side", "top"), [case(r) for r in c.get("rows", [])]
        bg = c.get("color", MAIN); fg = LIGHT if bg.lower() in (MAIN.lower(), C.get("deep", "").lower()) else MAIN
        rt = row_times(c, a, b, len(rows))
        fx, fy, fw, fh = FACE or (300, 500, 480, 600)
        PANEL = c.get("panel", 760)          # the brand panel's share; the person keeps the rest (more of them than half)
        if side == "left":   # person left, panel right; the window is centred on the face
            win0, win1, pan, tx = "left:0;top:0;width:1080px;height:1920px", {"width": W - PANEL // 2}, f"left:{W - PANEL // 2}px;top:0;width:{PANEL // 2}px;height:1920px", (W - PANEL // 2 + 40, 300, PANEL // 2 - 80)
            clip0 = "inset(0% 0% 0% 100%)"
            pos = f"{max(0, min(100, (fx + fw / 2 - (W - PANEL // 2) / 2) / (PANEL // 2) * 100)):.0f}% 50%"
        else:                # "top": panel above, the person below from just over the head down (face stays clear of Instagram's bottom bar)
            win0, win1, pan, tx = "left:0;top:0;width:1080px;height:1920px", {"top": PANEL, "height": H - PANEL}, f"left:0;top:0;width:1080px;height:{PANEL}px", (90, 250, 900)
            clip0 = "inset(0% 0% 100% 0%)"
            src_top = max(0, fy - 0.12 * fh - c.get("headroom", 70))   # source row that lands at the window's top edge
            pos = f"50% {max(0, min(100, src_top / PANEL * 100)):.0f}%"   # cover at scale 1 hides PANEL px of height
        tpx = min(fit(c.get("title", ""), 104 if side != "left" else 64), 104)
        room = (PANEL if side != "left" else 1480) - 30 - tx[1] - tpx * 1.3     # rows must end inside the panel / above the bottom bar
        rpx = int(min(fit(max(rows, key=len, default=""), 64 if side != "left" else 46), 64, room / max(len(rows), 1) / 1.55))
        mid.append(f'<div id="{cid}" class="sp" style="opacity:0;visibility:hidden">'
                   f'<div class="spw" style="{win0}"><video id="{cid}v" src="master.mp4" muted playsinline data-start="{q(a)}" data-duration="{q(b - a)}" data-media-start="{q(a)}" data-track-index="{9 + i}" style="object-position:{pos}"></video></div>'
                   f'<div class="spp" style="{pan};background:{bg}">'
                   f'<div class="spt" style="left:{tx[0] - (540 if side == "left" else 0)}px;top:{tx[1]}px;width:{tx[2]}px;{font("head", tpx)};color:{fg}">{esc(case(c.get("title", "")))}</div>'
                   + "".join(f'<div class="spr" id="{cid}r{j}" style="left:{tx[0] - (540 if side == "left" else 0)}px;top:{tx[1] + tpx * 1.3 + j * rpx * 1.55:.0f}px;width:{tx[2]}px;{font("body", rpx)};color:{fg}"><b style="background:{POP}"></b>{esc(r)}</div>' for j, r in enumerate(rows))
                   + '</div></div>')
        prop = ",".join(f"{k}:{v}" for k, v in win1.items()); back_ = ",".join(f"{k}:{ {'width': W, 'top': 0, 'height': H}[k]}" for k in win1)
        js.append(f'tl.set("#{cid}",{{autoAlpha:1}},{q(a)});'
                  f'tl.to("#{cid} .spw",{{{prop},duration:0.55,ease:"power3.inOut"}},{q(a)});'
                  f'tl.fromTo("#{cid} .spp",{{clipPath:"{clip0}"}},{{clipPath:"inset(0% 0% 0% 0%)",duration:0.55,ease:"power3.inOut"}},{q(a)});'
                  f'tl.fromTo("#{cid} .spt",{{y:40,opacity:0}},{{y:0,opacity:1,duration:0.4,ease:"power3.out"}},{q(a + 0.35)});'
                  + "".join(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,x:-50}},{{autoAlpha:1,x:0,duration:0.3,ease:"back.out(2)"}},{q(t)});' for j, t in enumerate(rt))
                  + f'tl.to("#{cid} .spw",{{{back_},duration:0.45,ease:"power3.inOut"}},{q(b - 0.45)});'
                  f'tl.to("#{cid} .spp",{{clipPath:"{clip0}",duration:0.45,ease:"power3.inOut"}},{q(b - 0.45)});tl.set("#{cid}",{{autoAlpha:0}},{q(b)});')
        sfx("whoosh_soft", a - 0.05, -13); sfx("whoosh_soft", b - 0.45, -16)
        for t in rt: sfx("pop", t, -16, "lots")
        zone(cid, "split", a, b, (0, 0, W, H), full=True)
        zone(cid, "split text", a, b, (tx[0], tx[1], tx[2], tpx * 1.3 + len(rows) * rpx * 1.55))
    elif kind == "push":
        # a new frame pushes the camera out of the way (наїзд кадру): a brand panel slides in from the right,
        # the camera moves left with it; at the end the panel carries on out and the camera comes back from the right
        quiet.append((a, b))
        bg = c.get("color", POP); fg = LIGHT if bg.lower() in (MAIN.lower(), C.get("deep", "").lower()) else MAIN
        lines = [case(x.strip()) for x in c.get("text", "").split("/") if x.strip()]
        px = c.get("size") or min(fit(max(lines, key=len, default=""), 170), 170)
        rows = [case(r) for r in c.get("rows", [])]
        rt = row_times(c, a + 0.3, b, len(rows))
        top = c.get("y", 600)
        mid.append(f'<div id="{cid}" class="pu" style="opacity:0;visibility:hidden;background:{bg}">'
                   + "".join(f'<div class="put" style="top:{top + k * px * 0.92:.0f}px;{font("head", px)};color:{fg}">{esc(x)}</div>' for k, x in enumerate(lines))
                   + "".join(f'<div class="pur" id="{cid}r{j}" style="top:{top + len(lines) * px * 0.92 + 70 + j * 110:.0f}px;{font("body", min(fit(r, 64), 64))};color:{fg}"><b style="background:{MAIN if bg != MAIN else POP}"></b>{esc(r)}</div>' for j, r in enumerate(rows))
                   + "</div>")
        js.append(f'tl.set("#{cid}",{{autoAlpha:1}},{q(a)});'
                  f'tl.fromTo("#{cid}",{{x:1080}},{{x:0,duration:0.5,ease:"power4.inOut"}},{q(a)});'
                  f'tl.to("#cam",{{x:-540,duration:0.5,ease:"power4.inOut"}},{q(a)});'
                  f'tl.fromTo("#{cid} .put",{{x:200,opacity:0}},{{x:0,opacity:1,duration:0.45,ease:"power3.out",stagger:0.1}},{q(a + 0.2)});'
                  + "".join(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,y:30}},{{autoAlpha:1,y:0,duration:0.3,ease:"back.out(2)"}},{q(t)});' for j, t in enumerate(rt))
                  + f'tl.set("#cam",{{x:540}},{q(b - 0.5)});'
                  f'tl.to("#{cid}",{{x:-1080,duration:0.5,ease:"power4.inOut"}},{q(b - 0.5)});'
                  f'tl.to("#cam",{{x:0,duration:0.5,ease:"power4.inOut"}},{q(b - 0.5)});tl.set("#{cid}",{{autoAlpha:0}},{q(b)});')
        sfx("whoosh_fast", a - 0.08, -12); sfx("whoosh_fast", b - 0.55, -14)
        for t in rt: sfx("pop", t, -16, "lots")
        zone(cid, "push", a, b, (0, 0, W, H), full=True)
        zone(cid, "push text", a, b, (90, top, 900, len(lines) * px * 0.92 + 60 + len(rows) * 100))
    elif kind == "camera":
        # camera moves on the clip itself: in (slow push-in), out (starts close, pulls back), whip (fast zoom hit),
        # shrink (the frame pulls back into a rounded window on the brand colour, room for words around it), shake
        mv = c.get("move", "out")
        if mv == "in":
            js.append(f'tl.fromTo("#cam",{{scale:1}},{{scale:{c.get("scale", 1.18)},immediateRender:false,duration:{max(b - a, 0.5):.2f},ease:"sine.inOut"}},{q(a)});tl.set("#cam",{{scale:1}},{q(b)});')
        elif mv == "out":
            js.append(f'tl.fromTo("#cam",{{scale:{c.get("scale", 1.35)}}},{{scale:1,immediateRender:false,duration:{min(0.9, max(b - a, 0.4)):.2f},ease:"power3.out"}},{q(a)});')
            sfx("whoosh_soft", a - 0.05, -15)
        elif mv == "whip":
            js.append(f'tl.to("#cam",{{scale:{c.get("scale", 1.3)},filter:"blur(5px)",duration:0.12,ease:"power2.in"}},{q(a)});'
                      f'tl.to("#cam",{{scale:1.12,filter:"blur(0px)",duration:0.25,ease:"power3.out"}},{q(a + 0.12)});'
                      f'tl.to("#cam",{{scale:1,duration:0.3,ease:"power2.inOut"}},{q(max(b - 0.3, a + 0.4))});')
            sfx("whoosh_fast", a - 0.06, -13)
        elif mv == "shrink":
            z = c.get("scale", 0.74)
            js.append(f'tl.to("#cam",{{scale:{z},y:{c.get("shift", 120)},borderRadius:{int(44 / z)},duration:0.55,ease:"power3.inOut"}},{q(a)});'
                      f'tl.to("#cam",{{scale:1,y:0,borderRadius:0,duration:0.5,ease:"power3.inOut"}},{q(b - 0.5)});')
            sfx("swish", a - 0.05, -14)
            if c.get("text"):   # words in the space the frame leaves at the top
                lines = [case(x.strip()) for x in c["text"].split("/") if x.strip()]
                px = min(fit(max(lines, key=len), 120), 120)
                back_lines = "".join(f'<div class="btl">{esc(x)}</div>' for x in lines)
                mid.append(f'<div id="{cid}" class="bigtext" style="top:{c.get("y", 250)}px;{font("head", px)};color:{c.get("color", LIGHT)}">{back_lines}</div>')
                show(f"#{cid}", a + 0.2, b - 0.3, 0.2)
                js.append(f'tl.fromTo("#{cid} .btl",{{y:60,opacity:0}},{{y:0,opacity:1,duration:0.45,ease:"power3.out",stagger:0.1}},{q(a + 0.25)});')
                quiet.append((a, b))
                zone(cid, "camera text", a, b, (*tw(max(lines, key=len), px)[:1], c.get("y", 250), tw(max(lines, key=len), px)[1], len(lines) * px * 0.86))
        elif mv == "shake":
            js.append(f'tl.to("#cam",{{keyframes:[{{x:-14,rotation:-0.6}},{{x:12,rotation:0.5}},{{x:-8,rotation:-0.3}},{{x:5}},{{x:0,rotation:0}}],duration:0.4,ease:"none"}},{q(a)});')
            sfx("hit_punch", a, -13)
    elif kind == "steps":
        # step panels slide up one over another; the one underneath shrinks back (кадри наїжджають)
        quiet.append((a, b))
        items = [case(x) for x in c.get("items", [])]
        rt = row_times(c, a, b, len(items), first=0.0)
        hh, dy = 220, 26                     # panel height; each older panel peeks out dy px below the new one
        y0, z = off_face(c, hh + dy * max(len(items) - 1, 0), 1180)
        styles = [(MAIN, LIGHT, POP), (LIGHT, MAIN, MAIN), (POP, MAIN, MAIN), (C.get("soft", POP), MAIN, MAIN)]
        front.append(f'<div id="{cid}" class="st" style="top:{y0}px">' + "".join(
            f'<div class="stp" id="{cid}r{j}" style="background:{styles[j % 4][0]};color:{styles[j % 4][1]}">'
            f'<span class="stn" style="{font("head", 96)};color:{styles[j % 4][2]}">{j + 1:02d}</span>'
            f'<span class="stx" style="{font("head", min(int((900 - 100 - 34 - 130) / (max(len(w) for w in x.split()) * EM)), 66))}">{esc(x)}</span></div>' for j, x in enumerate(items)) + "</div>")
        show(f"#{cid}", a, b)
        for j, t in enumerate(rt):
            js.append(f'tl.fromTo("#{cid}r{j}",{{autoAlpha:0,y:900,rotation:{(3, -3)[j % 2]}}},{{autoAlpha:1,y:0,rotation:0,duration:0.55,ease:"power4.out"}},{q(t)});')
            for k in range(j):   # everything underneath steps back
                js.append(f'tl.to("#{cid}r{k}",{{y:{(j - k) * dy},scale:{1 - (j - k) * 0.05:.2f},filter:"brightness({1 - (j - k) * 0.18:.2f})",duration:0.5,ease:"power3.out"}},{q(t + 0.05)});')
            sfx("whoosh_soft" if j else "swish", t - 0.05, -14)
        zwrap(front, y0, z)
        zone(cid, "steps", a, b, (540 - 450 * z, y0, 900 * z, (hh + dy * max(len(items) - 1, 0)) * z))
    else:
        print(f"warning: unknown card type {kind!r} - skipped")

CARD_MUTE = False
# ---- brand rule: every edit has a carousel (unless the person said no for this reel) --------------------------------
if brand.get("require_carousel") and not edit.get("no_carousel_ok") and not any(
        k["type"] == "motion" and "carousel" in k.get("name", "") for k in edit.get("cards", [])):
    sys.exit("brand rule: add a carousel motion card (or ask them; if they say no, set \"no_carousel_ok\": true in edit.json)")

back, mid, front = _BACK, _MID, _FRONT
subj = []   # the person, cut out for every "behind" window (cached in <reel>/cutouts, so re-renders don't redo it)
if BEHIND_WIN:
    wins = []
    for a, b in sorted(BEHIND_WIN):
        a, b = max(0, a - 0.3), min(DUR, b + 0.3)
        if wins and a <= wins[-1][1]: wins[-1] = (wins[-1][0], max(wins[-1][1], b))
        else: wins.append((a, b))
    cache = reel / "cutouts"; cache.mkdir(exist_ok=True)
    for k, (s0, s1) in enumerate(wins):
        s0, s1 = q(s0), q(s1)
        out = cache / f"cut_{s0:.2f}_{s1:.2f}.webm"
        if not out.exists():
            seg = cache / f"seg_{k}.mp4"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{s0:.4f}", "-t", f"{s1 - s0:.4f}", "-i", str(reel / "master.mp4"),
                            "-an", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(seg)], check=True)
            print(f"cutting the person out for {s0:.1f}-{s1:.1f}s (about {int((s1 - s0) * 13) + 15} s)...")
            subprocess.run(["npx", "-y", "hyperframes@0.8.145", "remove-background", str(seg), "-o", str(out), "--quality", "best"],
                           check=True, capture_output=True)
            seg.unlink(missing_ok=True)
        shutil.copy(out, proj / "img" / out.name)
        subj.append(f'<video id="sj{k}" class="clip" src="img/{out.name}" muted playsinline data-start="{s0}" data-duration="{q(s1 - s0)}" '
                    f'data-media-start="0" data-track-index="{70 + k}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover"></video>')

# ---- captions -----------------------------------------------------------------------------------------------------
# how a caption comes on and how its accent word looks: the style's "captions" block (default = pop + accent colour)
CAP_ANIM = {"pop": 'tl.fromTo("#C",{scale:0.86,y:14},{scale:1,y:0,duration:0.16,ease:"back.out(2)"},@T);',
            "rise": 'tl.fromTo("#C",{y:46},{y:0,duration:0.24,ease:"power3.out"},@T);',
            "blur": 'tl.fromTo("#C",{filter:"blur(10px)",scale:1.05},{filter:"blur(0px)",scale:1,duration:0.28,ease:"power2.out"},@T);',
            "slam": 'tl.fromTo("#C",{scale:1.45},{scale:1,duration:0.13,ease:"power4.out"},@T);',
            "none": ""}
def acc_look(col):
    look = S_CAP.get("accent", "color")
    if look == "box": return f"color:{MAIN};background:{col};padding:0 .16em;border-radius:.14em;text-shadow:none;box-decoration-break:clone;-webkit-box-decoration-break:clone"
    if look == "underline": return f"color:{CAP};box-shadow:inset 0 -.2em 0 {col}"
    return f"color:{col}"
cap_json = []
for i, c in enumerate(edit.get("captions", [])):
    if any(a - 0.05 <= c["start"] < b for a, b in quiet): continue
    ws = c["words"]
    plain = c.get("plain")                                             # "before" captions: basic white sans, no brand styling
    cap_json.append({"start": c["start"], "end": c["end"], "over_light": False,
                     "lines": [[{"text": w["text"] if plain else case(w["text"]), "kind": "sm" if plain else "acc" if w.get("accent") else "big", "t": w["t"]} for w in ws]]})
    if CAPCUT: continue
    if plain:
        front.append(f'<div id="c{i}" class="cap" style="top:{c.get("y", CAP_Y)}px;font-family:-apple-system,Helvetica,Arial,sans-serif;font-weight:500;font-size:46px;letter-spacing:0;color:#fff">{esc(" ".join(w["text"] for w in ws))}</div>')
        show(f"#c{i}", c["start"], c["end"], 0.04); continue
    chars = sum(len(w["text"]) + 1 for w in ws)
    px = fit(" ".join(w["text"] for w in ws), CAP_PX * (1.35 if len(ws) == 1 else 1), role="cap")
    big = 1.7 if CAPS.get("style") == "editorial" else 1.12          # editorial = dramatic size contrast on the emphasis word
    big = min(big, min((fit(w["text"], px * big, role="capacc") / px) for w in ws if w.get("accent")) if any(w.get("accent") for w in ws) else big)
    blk = "display:block;line-height:.95;" if CAPS.get("style") == "editorial" and len(ws) > 1 else ""
    spans = "".join(f'<span class="acc" style="{blk}{font("capacc", int(px * big))};{acc_look(next_acc())}">{esc(case(w["text"]))}</span> ' if w.get("accent")
                    else f'<span>{esc(case(w["text"]))}</span> ' for w in ws)
    front.append(f'<div id="c{i}" class="cap" style="top:{c.get("y", CAP_Y)}px;{font("cap", int(px))};color:{CAP};letter-spacing:{CAPS.get("tracking", -0.02)}em">{spans.strip()}</div>')
    show(f"#c{i}", c["start"], c["end"], 0.06)
    _x, _w = tw(" ".join(w["text"] for w in ws), px)
    zone(f"c{i}", "субтитри", c["start"], c["end"], (max(60, _x), c.get("y", CAP_Y), min(960, _w), px * big * 1.05))
    js.append(CAP_ANIM.get(S_CAP.get("anim", "pop"), CAP_ANIM["pop"]).replace("#C", f"#c{i}").replace("@T", str(q(c["start"]))))

# ---- assemble -----------------------------------------------------------------------------------------------------
_sp = float(S_MOT.get("speed", 1)) * float(edit.get("motion_mul", 1))   # the style's speed x this reel's «Повільніше / Швидше»
if _sp != 1:   # every tween and stagger runs faster (>1) or calmer (<1); start times stay on the words
    js = [re.sub(r"\b(duration|stagger):([\d.]+)", lambda m: f"{m.group(1)}:{float(m.group(2)) / _sp:.3f}", x) for x in js]
doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8" />
<style>
{chr(10).join(font_css)}
html, body {{ margin: 0; background: #000; overflow: hidden; }}
#stage {{ position: relative; width: {W // 2 if DRAFT else W}px; height: {H // 2 if DRAFT else H}px; overflow: hidden; }}
#cam {{ position: absolute; inset: 0; transform-origin: 50% 38%; overflow: hidden; }}
#camBg {{ position: absolute; inset: 0; background: {MAIN}; }}   /* shows only when a camera move shrinks the frame */
#cam > video {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
#back, #mid, #front {{ position: absolute; inset: 0; }}
#back > :not(.clip):not(.zw), #mid > :not(.clip):not(.zw), #front > :not(.clip):not(.zw), #behind > :not(.clip):not(.zw) {{ visibility: hidden; opacity: 0; }}
.zw {{ position: absolute; inset: 0; pointer-events: none; }}
.zw > * {{ visibility: hidden; opacity: 0; }}   /* .clip = HyperFrames motions, timed by the runtime */
.title {{ position: absolute; left: 0; top: 170px; width: {W}px; padding: 0 90px; box-sizing: border-box; line-height: .88; letter-spacing: -.045em; text-shadow: 0 0 3px rgba(0,0,0,.18), 0 6px 34px rgba(0,0,0,.4); }}
.tl {{ white-space: nowrap; }}
.block {{ position: absolute; inset: 0; }}
#behind, #subj {{ position: absolute; inset: 0; }}
.bigtext {{ position: absolute; left: 0; width: {W}px; text-align: center; line-height: .86; letter-spacing: -.045em; opacity: 0; visibility: hidden; }}
.btl {{ white-space: nowrap; }}
.frame {{ position: absolute; left: 279px; top: 400px; width: 522px; height: 900px; overflow: hidden; border: 10px solid #fff; border-radius: 8px; box-shadow: 0 24px 60px rgba(0,0,0,.22); }}
.frame video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.bl {{ position: absolute; left: 0; width: {W}px; padding: 0 90px; box-sizing: border-box; line-height: .82; letter-spacing: -.05em; white-space: nowrap; }}
.card {{ position: absolute; left: 90px; top: 150px; width: 900px; background: #fff; border-radius: 40px; overflow: hidden; padding-bottom: 22px; box-shadow: 0 30px 70px rgba(0,0,0,.25); }}
.ch {{ color: #fff; padding: 24px 36px; display: flex; align-items: center; gap: 18px; letter-spacing: -.02em; }}
.ch i {{ width: 22px; height: 22px; border-radius: 50%; background: rgba(255,255,255,.7); display: inline-block; }}
.cr {{ display: flex; align-items: center; gap: 24px; height: 110px; margin: 0 36px; border-bottom: 3px solid rgba(0,0,0,.06); letter-spacing: -.02em; }}
.cr b {{ width: 26px; height: 26px; border-radius: 50%; flex: none; }}
.tagw, .ctaw {{ position: absolute; left: 0; right: 0; text-align: center; padding: 0 80px; box-sizing: border-box; }}
.ctaw {{ top: 1360px; }}   /* above Instagram's caption + buttons zone (bottom ~420 px) */
.tag, .cta {{ display: inline-block; color: #fff; padding: 18px 42px; border-radius: 80px; letter-spacing: -.02em; box-shadow: 0 14px 34px rgba(0,0,0,.2); }}
.shot {{ position: absolute; left: 70px; top: 130px; width: 940px; border-radius: 26px; overflow: hidden; background: #fff; box-shadow: 0 34px 80px rgba(0,0,0,.3); }}
.bar {{ height: 64px; display: flex; align-items: center; gap: 12px; padding: 0 24px; background: #F2F2F4; color: #555; }}
.bar i {{ width: 18px; height: 18px; border-radius: 50%; display: inline-block; }}
.bar span {{ margin-left: 18px; background: #fff; border-radius: 14px; padding: 6px 22px; }}
.vp {{ height: 620px; overflow: hidden; }}
.vp img {{ width: 100%; display: block; }}
.imgs {{ position: absolute; left: 0; top: 140px; width: {W}px; height: 560px; }}
.ph {{ position: absolute; top: 0; width: 420px; height: 520px; object-fit: cover; border: 12px solid #fff; border-radius: 18px; box-shadow: 0 26px 60px rgba(0,0,0,.28); }}
.stk {{ position: absolute; }}
.stk img {{ width: 100%; display: block; filter: drop-shadow(0 14px 22px rgba(0,0,0,.25)); }}
.page {{ position: absolute; inset: 0; }}
.pt {{ position: absolute; left: 0; right: 0; top: 150px; text-align: center; line-height: .9; letter-spacing: -.04em; padding: 0 60px; }}
.pf {{ position: absolute; left: 190px; top: 560px; width: 700px; height: 1240px; overflow: hidden; border: 12px solid #fff; border-radius: 34px; box-shadow: 0 30px 70px rgba(0,0,0,.28); }}
.pf video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.glass {{ background: linear-gradient(145deg, rgba(255,255,255,.16), rgba(255,255,255,.02) 55%), {GLASS_TINT} !important; backdrop-filter: blur(26px) saturate(1.5); -webkit-backdrop-filter: blur(26px) saturate(1.5); border: 1.5px solid rgba(255,255,255,.28); box-shadow: 0 24px 60px rgba(0,0,0,.22), inset 0 1px 0 rgba(255,255,255,.45), inset 0 -1px 0 rgba(255,255,255,.08); }}
.card.glass .ch {{ background: rgba(255,255,255,.07) !important; border-bottom: 1px solid rgba(255,255,255,.18); }}
.cta.glass {{ color: #fff !important; border-radius: 40px; line-height: 1.12; padding: 22px 48px 26px; max-width: 100%; box-sizing: border-box; }}
.tag.glass {{ max-width: 100%; box-sizing: border-box; }}
.tg {{ display: inline-block; padding: 34px 56px 42px; border-radius: 44px; }}
.title:has(.tg) {{ text-align: center; text-shadow: none; }}
.card.glass .cr {{ color: #fff !important; border-bottom-color: rgba(255,255,255,.25); }}
.ld {{ position: absolute; left: 90px; width: 900px; }}
.ldt {{ display: inline-block; padding: 12px 30px; border-radius: 60px; margin-bottom: 18px; letter-spacing: -.01em; }}
.ldr {{ display: flex; align-items: center; gap: 26px; line-height: 1.12; letter-spacing: -.035em; white-space: nowrap; text-shadow: 0 4px 26px rgba(0,0,0,.45); margin-bottom: .13em; }}
.ldn {{ width: 1.9em; height: 1.9em; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; flex: none; text-shadow: none; }}
.ln {{ position: absolute; left: 90px; width: 900px; box-sizing: border-box; padding: 24px 36px 20px; background: #FFFDF6; border-radius: 34px; box-shadow: 0 30px 70px rgba(0,0,0,.28); }}
.lnt {{ letter-spacing: -.02em; padding-bottom: 12px; margin-bottom: 4px; border-bottom: 3px solid rgba(0,0,0,.07); }}
.lnr {{ display: flex; align-items: center; gap: 24px; height: 78px; }}
.lnc {{ width: 46px; height: 46px; border-radius: 50%; border: 4px solid; flex: none; box-sizing: border-box; display: flex; align-items: center; justify-content: center; }}
.lnc svg {{ width: 30px; height: 30px; }}
.lnc path {{ fill: none; stroke-width: 3.2; stroke-linecap: round; stroke-linejoin: round; stroke-dasharray: 30; stroke-dashoffset: 30; }}
.lnx {{ letter-spacing: -.015em; white-space: nowrap; }}
.ls {{ position: absolute; left: 90px; width: 900px; }}
.lsr {{ position: absolute; left: 0; width: 900px; box-sizing: border-box; padding: 14px 40px; border-radius: 30px; letter-spacing: -.025em; white-space: nowrap; box-shadow: 0 20px 44px rgba(0,0,0,.25); }}
.sp {{ position: absolute; inset: 0; }}
.spw {{ position: absolute; overflow: hidden; }}
.spw video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.spp {{ position: absolute; overflow: hidden; }}
.spt {{ position: absolute; line-height: .95; letter-spacing: -.04em; }}
.spr {{ position: absolute; display: flex; align-items: center; gap: 22px; letter-spacing: -.02em; }}
.spr b, .pur b {{ width: 22px; height: 22px; border-radius: 50%; flex: none; }}
.pu {{ position: absolute; inset: 0; }}
.put {{ position: absolute; left: 90px; right: 90px; line-height: .92; letter-spacing: -.045em; white-space: nowrap; }}
.pur {{ position: absolute; left: 90px; right: 90px; display: flex; align-items: center; gap: 24px; letter-spacing: -.02em; }}
.st {{ position: absolute; left: 90px; width: 900px; height: 220px; }}
.stp {{ position: absolute; inset: 0; border-radius: 40px; display: flex; align-items: center; gap: 34px; padding: 0 50px; box-sizing: border-box; box-shadow: 0 30px 70px rgba(0,0,0,.3); transform-origin: 50% 100%; }}
.stn {{ line-height: 1; letter-spacing: -.05em; flex: none; }}
.stx {{ line-height: 1.02; letter-spacing: -.03em; }}
.cap {{ position: absolute; left: 60px; right: 60px; text-align: center; line-height: 1.02; letter-spacing: -.02em; text-shadow: 0 2px 14px rgba(0,0,0,.3); }}
.cap .acc {{ text-shadow: 0 0 2px rgba(0,0,0,.25), 0 3px 22px rgba(0,0,0,.5); }}   /* accent colour stays readable over white screens, no outline */
</style></head>
<body>
<div id="stage" data-composition-id="main" data-start="0" data-duration="{DUR}" data-fps="{FPS}" data-width="{W // 2 if DRAFT else W}" data-height="{H // 2 if DRAFT else H}">
  <div id="scaler" style="position:absolute;left:0;top:0;width:{W}px;height:{H}px;{'zoom:.5;' if DRAFT else ''}">
  <div id="camBg"></div>
  <div id="cam"><video id="bg" class="clip" src="master.mp4" playsinline data-has-audio="true" data-start="0" data-duration="{DUR}" data-track-index="1"></video>
    <div id="behind">{"".join(behind)}</div><div id="subj">{"".join(subj)}</div>
    <div id="back">{"".join(back)}</div></div>
  <div id="mid">{"".join(mid)}</div>
  <div id="front">{"".join(front)}</div>
  </div>
  {"".join(audio)}
  <script src="vendor/gsap.min.js"></script>
  <script>(function () {{ window.__timelines = window.__timelines || {{}};
    const tl = window.gsap.timeline({{ paused: true }});
    {chr(10).join(js)}
    window.__timelines["main"] = tl; }})();</script>
</div></body></html>"""
(proj / "index.html").write_text(doc)
sys.path.insert(0, str(Path(__file__).resolve().parent)); import safezones
safezones.save(reel, ZONES)
(proj / "package.json").write_text('{"name":"reel","private":true,"type":"module"}')
if CAPCUT:
    json.dump(cap_json, open(reel / "captions.json", "w"), indent=1)
    json.dump(SFX_OUT, open(reel / "sfx.json", "w"), indent=1)
print(f"built {proj/'index.html'}: {DUR}s, {len(edit.get('cards', []))} cards, {len(cap_json)} captions, {n_sfx} sounds"
      + (" (capcut: captions.json + sfx.json written)" if CAPCUT else ""))
