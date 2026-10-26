#!/usr/bin/env python3
"""Effects check BEFORE any render (2026-10-26: a wrong effect found on the draft costs a second 10-minute render).

  fx_check.py <reel> [--no-frames] [--only id,id]

Every mistake we used to find on a finished draft is visible on one frame or in the card itself, so it is caught here:
1. Text check of edit.json (seconds, no render):
   - an effect on their black list (<REELS_HOME>/blacklist.json)                            -> ERROR
   - a motion var the composition doesn't have, a list joined with «|» where it wants commas -> ERROR
   - a number the motion shows that the card didn't set (it would show its test value, e.g. 42) -> ERROR
   - a text field left empty, so the motion's English sample shows                          -> WARN
   - a «replace» motion missing one of its English texts                                    -> WARN
   - a Vibha effect that would print someone else's nick (@vibha.in.progress) or English sample -> ERROR / WARN
   - long text on a one-line effect (may run off the frame: look at its frame)              -> WARN
2. Frames (unless --no-frames): one still per graphic at its peak, on their cut, in their brand -> <reel>/check/<id>.jpg
   and one contact sheet <reel>/check/sheet.jpg with the id and name under each still.
   - fx cards: fx_pass.py in draft mode, the same cache render.sh uses, so these seconds are NOT rendered twice;
   - everything else: that one card alone on a few seconds of the cut (build_reel + hyperframes snapshot, ~10 s a card).
Exit code 1 when there is an ERROR. Look at sheet.jpg and fix every card that looks wrong in edit.json (and proposal.json)
before render.sh: text off the frame, tiny or dim, someone else's words, numbers that aren't theirs, a face covered."""
import argparse, glob, json, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
CAT = {m["name"]: m for m in json.load(open(SK / "references" / "motion_catalog.json"))["motions"]}
FXPY = SK / "vendor" / "vibha-fx" / "scripts" / "fx.py"
sys.path.insert(0, str(SK / "scripts"))

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("reel"); ap.add_argument("--no-frames", action="store_true"); ap.add_argument("--only", default="")
ap.add_argument("--workers", type=int, default=2)
ap.add_argument("--verify", action="store_true", help="render.sh: exit 3 when the graphics changed since the last clean check")
A = ap.parse_args()
reel = Path(A.reel).expanduser().resolve()
edit = json.load(open(reel / "edit.json"))
only = {x for x in A.only.split(",") if x}

def cards_key(e):
    """What the check looked at: every graphic's settings, without the times precheck / a re-cut nudge."""
    import hashlib
    g = [{k: v for k, v in c.items() if k not in ("start", "end", "quiet", "y", "x")} for c in e.get("cards", []) if c.get("type") != "punch"]
    return hashlib.sha1(json.dumps(g, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

if A.verify:
    if not any(c.get("type") != "punch" for c in edit.get("cards", [])): sys.exit(0)
    st = reel / "check" / "checked.key"
    if st.exists() and st.read_text().strip() == cards_key(edit): sys.exit(0)
    print("render: the graphics were not checked before this render (or changed since). Run first:\n"
          f"  python3 scripts/fx_check.py {reel}\nfix every ERROR, look at check/sheet.jpg, then render. "
          "REEL_NO_CHECK=1 skips this (only for a reel with no new graphics).", file=sys.stderr)
    sys.exit(3)
cards = [c for c in edit.get("cards", []) if c.get("type") != "punch" and (not only or c.get("id") in only)]
problems = []   # (level, id, text)

def say(level, c, text): problems.append((level, c.get("id") or c.get("type"), text))

def black():
    f = HOME / "blacklist.json"
    try: return {i["name"]: i for i in json.load(open(f)).get("items", [])} if f.exists() else {}
    except Exception: return {}

def comp_vars(name):
    """data-composition-variables of a catalog motion's HTML (list of {id, type, role, description, default})."""
    hits = sorted(glob.glob(str(SK / "engine" / "hf" / "compositions" / "**" / f"{name}.html"), recursive=True))
    if not hits: return None
    m = re.search(r"data-composition-variables='(\[.*?\])'", open(hits[0], encoding="utf-8").read(), re.S)
    try: return json.loads(m.group(1)) if m else []
    except Exception: return None

def baked_english(name, vs, m):
    """Visible English words written straight into a motion's HTML (not a variable, not a «replace» text): «Community»."""
    hits = sorted(glob.glob(str(SK / "engine" / "hf" / "compositions" / "**" / f"{name}.html"), recursive=True))
    if not hits: return []
    h = open(hits[0], encoding="utf-8").read()
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", h, flags=re.S | re.I)
    texts = {t.strip() for t in re.findall(r">([^<>]+)<", h) if re.search(r"[A-Za-z]{3,}", t)}
    known = {str(v.get("default", "")) for v in vs} | set((m.get("replace") or {})) | set((m.get("replace_default") or {}))
    own = lambda t: t.lower().replace(" ", "-") == name
    return sorted(t for t in texts if t not in known and not own(t) and not any(t in k for k in known))[:4]

def fx_defaults():
    """Per Vibha effect: the option defaults its code falls back to when the card leaves them out."""
    src = open(FXPY, encoding="utf-8").read(); out = {}
    parts = re.split(r"^@effect\('([^']+)'", src, flags=re.M)
    for i in range(1, len(parts), 2):
        body = parts[i + 1]
        out[parts[i]] = {k: v for k, v in re.findall(r"e\.o\.get\('(\w+)',\s*'([^']*)'", body)}
        out[parts[i]]["__hard_vibha__"] = bool(re.search(r"(?<!get\('handle', )'@?vibha\.in\.progress", body))
    return out

def label(c):
    return c.get("name") or (c.get("fx") and "fx-" + c["fx"]) or (c.get("brand") and "brand:" + c["brand"]) or \
        (isinstance(c.get("look"), str) and "head-" + c["look"]) or c.get("type")   # a text she added carries a look object (font, colour...), not a head style

# 1. text check
BL = black(); FXD = fx_defaults()
try:
    from fx_pass import BRAND_OPTS, SAMPLE
except Exception:
    BRAND_OPTS, SAMPLE = {}, {}
LATIN = re.compile(r"[A-Za-z]{3,}")
for c in cards:
    name = label(c)
    if name in BL: say("ERROR", c, f"{name} у чорному списку: {BL[name].get('why', '')}")
    if c["type"] == "motion":
        m = CAT.get(c["name"], {})
        vs = comp_vars(c["name"])
        given = c.get("vars") or {}
        if vs is not None:
            ids = {v["id"]: v for v in vs}
            for k, val in given.items():
                if k not in ids: say("ERROR", c, f"{c['name']}: поля «{k}» немає (є: {', '.join(ids)})"); continue
                v = ids[k]; d = (v.get("description") or "").lower()
                if isinstance(val, str) and "|" in val and "comma" in d and "," not in val:
                    say("ERROR", c, f"{c['name']}.{k}: список через «|», а ефект чекає коми: «{val.replace('|', ',')}»")
                if isinstance(val, str) and v.get("type") == "number":
                    say("ERROR", c, f"{c['name']}.{k}: має бути число, а стоїть «{val}»")
            for v in vs:
                if v.get("role") != "content" or v["id"] in given: continue
                if v.get("type") == "number":
                    say("ERROR", c, f"{c['name']}: покаже свою тестову цифру {v.get('default')} ({v['id']}). Дай її цифру або обери інший ефект")
                elif v.get("type") == "string" and LATIN.search(str(v.get("default", ""))):
                    say("WARN", c, f"{c['name']}: поле {v['id']} не задане, покаже англійське «{v.get('default')}»")
        for word in baked_english(c["name"], vs or [], m):
            say("WARN", c, f"{c['name']}: у самому ефекті зашитий англійський напис «{word}»: подивись кадр, прибери його в HTML ефекту")
        for en in (m.get("replace") or {}):
            if en not in (c.get("replace") or {}) and en.lower().replace(" ", "-") != c["name"]:   # «Grid Card Assemble» = its own hidden title
                say("WARN", c, f"{c['name']}: replace без «{en}», лишиться англійський текст")
        texts = [str(x) for x in list(given.values()) + list((c.get("replace") or {}).values()) if isinstance(x, str)]
        oneline = (m.get("card") or {}).get("place") == "low" or (m.get("card") or {}).get("layout") == "front"
        total = sum(len(t) for t in (c.get("replace") or {}).values())
        if oneline and (total > 16 or any(len(t) > 18 for t in texts)):
            say("WARN", c, f"{c['name']}: довгий текст ({max([total] + [len(t) for t in texts])} знаків) в однорядковому ефекті, може вилізти за кадр: подивись кадр")
    elif c["type"] == "fx":
        fx = c["fx"]; d = FXD.get(fx, {}); opt = c.get("opt") or {}
        have = set(opt) | ({"text"} if c.get("text") else set()) | set(BRAND_OPTS.get(fx, []))
        if d.get("__hard_vibha__"): say("ERROR", c, f"fx-{fx}: у коді ефекту зашитий чужий нік @vibha.in.progress")
        for k, v in d.items():
            if k.startswith("__") or k in have: continue
            if "vibha" in v.lower(): say("ERROR", c, f"fx-{fx}: {k} не задане, покаже чужий нік «{v}» (дай opt.{k} або \"\")")
            elif k == "text" and fx in SAMPLE: say("WARN", c, f"fx-{fx}: без text покаже зразок «{SAMPLE[fx]}»")
            elif LATIN.search(v) and k in ("text", "label", "title", "name", "pill", "tag", "total"):
                say("WARN", c, f"fx-{fx}: {k} не задане, покаже англійське «{v}»")

for lvl, cid, text in problems: print(f"{lvl:5s} {cid}: {text}")
errors = sum(1 for p in problems if p[0] == "ERROR")
print(f"text check: {len(cards)} graphics, {errors} error(s), {len(problems) - errors} warning(s)")

# 2. frames
if A.no_frames: sys.exit(1 if errors else 0)
out = reel / "check"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
master = reel / "master.mp4"; words = json.load(open(reel / "master_transcript.json"))

def peak_of(c):
    st, en = c["start"], c.get("end", c["start"] + 3)
    if c["type"] == "head" or str(c.get("name", "")).startswith("head-"): return max(st + 0.6, en - 0.35)
    return st + min(1.4, (en - st) * 0.6)

fxc = [c for c in cards if c["type"] == "fx"]
if fxc:   # the real thing, cached: render.sh reuses these pieces
    r = subprocess.run([sys.executable, str(SK / "scripts" / "fx_pass.py"), str(reel)], env={**os.environ, "REEL_DRAFT": "1"},
                       capture_output=True, text=True)
    src = reel / "master_fx_540.mp4"
    if r.returncode or not src.exists(): print("fx_pass failed:", (r.stdout + r.stderr)[-600:])
    else:
        for c in fxc:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{peak_of(c):.2f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=540:960",
                            "-q:v", "4", str(out / f"{c['id']}.jpg")])

def one(c):
    name = c.get("id") or c["type"]; d = out / "w" / name; d.mkdir(parents=True)
    st, en = c["start"], c.get("end", c["start"] + 3); a = max(0.0, st - 0.6); dur = (en - a) + 0.6
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(master), "-t", f"{dur:.3f}", "-vf", "scale=540:960",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-an", str(d / "master.mp4")], check=True)
    json.dump([{**w, "start": round(w["start"] - a, 3), "end": round(w["end"] - a, 3)} for w in words if a <= w["start"] < a + dur],
              open(d / "master_transcript.json", "w"), ensure_ascii=False)
    if (reel / "face.json").exists(): shutil.copy(reel / "face.json", d / "face.json")
    for sub in ("elements", "shots", "overlays", "motion", "finds", "effects"):
        if (reel / sub).exists(): os.symlink(reel / sub, d / sub)
    card = {**c, "start": round(st - a, 3), "end": round(en - a, 3), "sfx": False}
    json.dump({**{k: v for k, v in edit.items() if k not in ("cards", "captions", "punch")}, "captions": [], "punch": [], "cards": [card],
               "no_carousel_ok": True}, open(d / "edit.json", "w"), ensure_ascii=False)
    b = subprocess.run([sys.executable, str(SK / "scripts" / "build_reel.py"), str(d)], capture_output=True, text=True, env={**os.environ, "REEL_DRAFT": "1"})
    if b.returncode: return name, "build_fail " + b.stderr.strip()[-200:]
    subprocess.run(["npx", "-y", "hyperframes@0.8.145", "snapshot", str(d / "proj"), "--at", f"{peak_of(card):.2f}", "--no-end", "--describe", "false",
                    "--timeout", "25000", "-o", str(d / "snaps")], capture_output=True, text=True)
    png = sorted(glob.glob(str(d / "snaps/frame-*.png")))
    if not png: return name, "snap_fail"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", png[0], "-vf", "scale=540:960", "-q:v", "4", str(out / f"{name}.jpg")])
    shutil.rmtree(d, ignore_errors=True)
    return name, "ok"

rest = [c for c in cards if c["type"] != "fx"]
with ThreadPoolExecutor(max(1, A.workers)) as ex:
    for name, st in ex.map(one, rest):
        if st != "ok": print(f"frame {name}: {st}")
shutil.rmtree(out / "w", ignore_errors=True)

# contact sheet: 5 per row, id + effect name under each
done = [c for c in sorted(cards, key=lambda c: c["start"]) if (out / f"{c.get('id') or c['type']}.jpg").exists()]
if done:
    # ffmpeg only (no Pillow on a fresh Mac): each still 270x480 with its label under it, 5 per row
    W, H, T, N = 270, 480, 34, 5
    DRAWTEXT = " drawtext " in subprocess.run(["ffmpeg", "-v", "error", "-filters"], capture_output=True, text=True).stdout
    font = next((f for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
                             "C:/Windows/Fonts/arial.ttf") if os.path.exists(f)), None)
    esc = lambda t: t.replace("\\", "").replace(":", "\\:").replace("'", "").replace("%", "")
    ins, fl = [], []
    for i, c in enumerate(done):
        ins += ["-i", str(out / f"{c.get('id') or c['type']}.jpg")]
        txt = f"{c.get('id')} {label(c)} {c['start']:.1f}s"[:30]
        dt = f",drawtext=fontfile='{font.replace(':', chr(92) + ':')}':text='{esc(txt)}':x=6:y={H + 8}:fontsize=17:fontcolor=black" if font and DRAWTEXT else ""
        fl.append(f"[{i}:v]scale={W}:{H},pad={W}:{H + T}:0:0:white{dt}[p{i}]")
    rows = (len(done) + N - 1) // N; cols = min(N, len(done))
    for k in range(len(done), rows * cols):
        fl.append(f"color=white:s={W}x{H + T}:d=1[p{k}]")
    lay = "|".join(f"{(k % cols) * W}_{(k // cols) * (H + T)}" for k in range(rows * cols))
    fl.append("".join(f"[p{k}]" for k in range(rows * cols)) + (f"xstack=inputs={rows * cols}:layout={lay}" if rows * cols > 1 else "null") + "[o]")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fl), "-map", "[o]", "-frames:v", "1", "-q:v", "3",
                        str(out / "sheet.jpg")], capture_output=True, text=True)
    if r.returncode and DRAWTEXT:   # a label the text filter can't take must never cost the sheet: again without labels
        DRAWTEXT = False
        fl = [re.sub(r",drawtext=[^\[]*", "", x) for x in fl]
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fl), "-map", "[o]", "-frames:v", "1", "-q:v", "3",
                            str(out / "sheet.jpg")], capture_output=True, text=True)
    print(f"frames: {len(done)} -> {out / 'sheet.jpg'}" if r.returncode == 0 else "sheet failed: " + r.stderr[-300:])
    if not DRAWTEXT:   # this ffmpeg has no text filter: the order, left to right, top to bottom
        for i, c in enumerate(done, 1): print(f"  {i:2d}. {c.get('id')} {label(c)} {c['start']:.1f}s")
missing = [c.get("id") for c in cards if c not in done]
if missing: print("no frame for:", ", ".join(map(str, missing)))
if not errors and not only: (out / "checked.key").write_text(cards_key(edit))   # render.sh lets the render through
print("next: LOOK at check/sheet.jpg (text inside the frame, readable, big enough, their words and numbers only, face clear), fix, then render")
sys.exit(1 if errors else 0)
