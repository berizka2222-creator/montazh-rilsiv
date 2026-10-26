#!/usr/bin/env python3
"""Vibha's 42 talking-head effects (vendor/vibha-fx, MIT, by @vibha.in.progress) on the cut, before the reel's own graphics.

  fx_pass.py <reel>                       render.sh runs it before build_reel.py (REEL_DRAFT=1: at 540 px, like the draft)
  fx_pass.py <reel> --previews [--names orbit,spotlight]   menu clips <REELS_HOME>/menu/fx-<name>.mp4 on this reel

An edit.json card {"type": "fx", "fx": "orbit", "start": 3.2, "end": 6.0, "text"?: "...", "images"?: "<folder in the reel>",
"opt"?: {"color": "#FFC3CC", ...}} puts one effect on those seconds (names, options: references/motions.md «Ефекти Vibha»).
Only the seconds with an effect are processed (effects that overlap go through together, so they stack); each piece is
cached by its settings, and the pieces are laid over master.mp4 into master_fx.mp4 (master_fx_540.mp4 for drafts), which
build_reel.py then uses as the video under the captions and graphics. The effects are drawn in the brand's fonts (hers have
no Cyrillic) and accent colours; real interfaces in them (Instagram comment, iPhone toggles) keep their own look."""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VD = HERE.parent / "vendor" / "vibha-fx"
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
MAC = sys.platform == "darwin"
DRAFT = bool(os.environ.get("REEL_DRAFT"))
BRAND = json.load(open(HOME / "brand.json", encoding="utf-8")) if (HOME / "brand.json").exists() else {}

# a sample line for every effect: the menu clips («+ Додати») and the defaults when a card gives no text
SAMPLE = {"lineup": "ціна|оффер|цінність", "locked-on": "ТИ", "backdrop-word": "ЦІНА", "spotlight": "ЦІНА", "the-bill": "питання|задачі|бюджет|ціна",
          "todo": "питання|оффер|ціна", "comment-box": "ЦІНА", "pause-point": "оце я", "uninstall": "старі звички", "reel-frame": "@reels",
          "shortcut-rain": "⌘|C|V|Z", "reject-stamp": "НІ", "cover-star": "ЦІНА", "scribble": "я", "glass-widgets": "100%",
          "red-collage": "ЦІНА", "split-headline": "три питання|до ціни", "pastel-word": "ЦІНА", "check-pills": "питання|оффер|ціна",
          "timeline": "монтаж", "headline-box": "три питання|до ціни", "tier-list": "", "phone-fan": "мої|рілси",
          "headline-wall": "питання::1|оффер::2|ціна::3", "checklist": "питання::крок 1|оффер::крок 2|ціна::крок 3",
          "liquid-glass-graph": "охоплення", "match-cut": "ЦІНА", "apple-toggles": "питання|оффер|ціна", "led-sign": "ЦІНА"}


# text options that carry Vibha's own English words / handle when a card leaves them out: Claude fills them with the
# person's words (fx_pass warns about any it finds empty); name / handle come from brand.json
MUST = {"locked-on": ["text"], "backdrop-word": ["text"], "the-bill": ["text"], "todo": ["text", "title"], "pause-point": ["text"],
        "uninstall": ["text"], "shortcut-rain": ["text"], "reject-stamp": ["text"], "cover-star": ["text", "issue", "lines"], "scribble": ["text"],
        "glass-widgets": ["text"], "red-collage": ["text", "lines", "tag"], "split-headline": ["text", "hl", "pill"], "pastel-word": ["text", "role"],
        "check-pills": ["text", "board"], "timeline": ["text", "sub", "reply", "chip"], "headline-box": ["text"], "profile-wall": ["label", "sub"],
        "tier-list": ["title", "item", "others"], "broll-split": ["text"], "phone-fan": ["text"], "headline-wall": ["text", "label", "total"],
        "checklist": ["text", "title"], "liquid-glass-graph": ["text", "to"], "carousel-spin": ["text"], "match-cut": ["text"],
        "apple-toggles": ["text"], "led-sign": ["text"], "comment-box": ["text"], "lineup": ["text"], "spotlight": [], "slow-push": []}
BRAND_OPTS = {"pastel-word": ["name", "handle"], "check-pills": ["handle"], "timeline": ["handle"], "profile-wall": ["name"],
              "glass-widgets": ["name", "handle"], "reel-frame": ["text"]}
# the menu clips: Ukrainian sample words for every option, so no clip shows her English defaults
SAMPLE_OPT = {"todo": {"title": "ЗРОБИТИ"}, "cover-star": {"issue": "ЖОВТЕНЬ · 2026", "lines": "три питання|до ціни|оффер|результат"},
              "red-collage": {"lines": "ЦІНА.|ОФФЕР.|РЕЗУЛЬТАТ.", "tag": "REC · ЦІНА"}, "split-headline": {"hl": "питання", "pill": "до ціни ↗"},
              "pastel-word": {"role": "таргетолог"}, "check-pills": {"board": "Рілси · 3 питання"},
              "timeline": {"sub": "монтаж з Claude", "reply": "надіслала прайс", "chip": "3 питання"}, "profile-wall": {"label": "переглядів", "sub": "топ рілс"},
              "tier-list": {"title": "що спитати першим?", "item": "задачі", "others": "ціна|бюджет|терміни"}, "broll-split": {"text": "1 год → 5 хв"},
              "headline-wall": {"label": "з 3 рілсів"}, "checklist": {"title": "Claude монтує твій рілс"}, "liquid-glass-graph": {"to": "59%"},
              "carousel-spin": {"text": "рілси"}, "glass-widgets": {}}


def run(*a, **k): return subprocess.run([str(x) for x in a], check=True, **k)


def dur_of(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                           capture_output=True, text=True, check=True).stdout)


def vpython():
    for p in (VD / ".venv" / "bin" / "python", VD / ".venv" / "Scripts" / "python.exe"):
        if p.exists(): return p
    print("first use: setting up Python for the effects (about 1 minute)...", flush=True)
    run("bash", HERE / "setup_fx.sh")
    for p in (VD / ".venv" / "bin" / "python", VD / ".venv" / "Scripts" / "python.exe"):
        if p.exists(): return p
    sys.exit("setup_fx.sh did not create the Python for the effects")


def models_env():
    """MediaPipe / OpenCV can't open a model under a non-Latin path (C:\\Users\\Інна...): use a Latin-only copy then."""
    src = VD / "models"
    if str(src).isascii(): return {}
    import tempfile
    dst = (Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "montazh-rilsiv" / "fx-models") if os.name == "nt" else Path(tempfile.gettempdir()) / "montazh-rilsiv-fx-models"
    dst.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file() and (not (dst / f.name).exists() or (dst / f.name).stat().st_size != f.stat().st_size): shutil.copy(f, dst / f.name)
    return {"FX_MODELS": str(dst)}


def brand_env(py):
    """FX_FONTS / FX_COLORS: the brand's head / body / accent fonts (as .ttf: Pillow can't read .woff2) and accent colours."""
    b = json.load(open(HOME / "brand.json", encoding="utf-8")) if (HOME / "brand.json").exists() else {}
    cache = HOME / ".cache" / "fxfonts"; cache.mkdir(parents=True, exist_ok=True)
    def ttf(role):
        f = ((b.get("fonts") or {}).get(role) or {}).get("file")
        if not f: return None
        p = Path(f).expanduser()
        if not p.exists(): return None
        if p.suffix.lower() in (".ttf", ".otf"): return str(p)
        for ext in (".ttf", ".otf"):   # the same face next to it as .ttf / .otf
            if p.with_suffix(ext).exists(): return str(p.with_suffix(ext))
        out = cache / (p.stem + ".ttf")
        if not out.exists():
            subprocess.run([str(py), "-c", "import sys; from fontTools.ttLib import TTFont; f = TTFont(sys.argv[1]); f.flavor = None; f.save(sys.argv[2])",
                            str(p), str(out)], check=False)
        return str(out) if out.exists() else None
    head, body, acc = ttf("head"), ttf("body"), ttf("accent")
    vf = VD / "fonts"
    head = head or str(vf / "Montserrat.ttf"); body = body or str(vf / "Inter.ttf"); acc = acc or str(vf / "PlayfairDisplay-Italic.ttf")
    fonts = {k: head for k in ("bold", "anton", "montb", "mont", "monts", "uib", "didoneb")}
    fonts.update({k: body for k in ("ui", "uim", "mono")}); fonts.update({k: acc for k in ("serif", "didone", "didonei", "hand")})
    c = b.get("colors") or {}
    colors = {k: v for k, v in (("PEACH", c.get("pop")), ("YELLOW", c.get("soft") or c.get("pop"))) if v}
    return {"FX_FONTS": json.dumps(fonts), "FX_COLORS": json.dumps(colors)}


def thumbs(reel, base):
    """10 stills across the whole cut: the «cards» of orbit / noise / phone-fan / profile-wall when she gives no pictures."""
    d = reel / ".cache" / "fx" / "thumbs"
    if d.exists() and len(list(d.glob("*.jpg"))) >= 10 and d.stat().st_mtime >= base.stat().st_mtime: return d
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    D = dur_of(base)
    for j in range(10):
        run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{D * (j + 0.5) / 10:.2f}", "-i", base, "-frames:v", "1", "-vf", "scale=540:-2", d / f"{j:02d}.jpg")
    return d


def fx_plan(cards, a0, reel, th, brand=None):
    plan = []; brand = brand or {}
    for c in cards:
        d = {"fx": c["fx"], "start": round(c["start"] - a0, 3), "end": round(c["end"] - a0, 3)}
        t = c.get("text", SAMPLE.get(c["fx"]) if c.get("sample") else None)
        if t: d["text"] = t
        img = c.get("images")
        d["images"] = str((reel / img) if img and not Path(img).is_absolute() else img) if img else str(th)
        if c.get("sample"): d.update(SAMPLE_OPT.get(c["fx"], {}))
        d.update({k: v for k, v in (c.get("opt") or {}).items()})
        h = str(brand.get("handle") or "").lstrip("@")
        for k in BRAND_OPTS.get(c["fx"], []):   # her name / handle, never Vibha's
            if k not in d:
                v = ("@" + h if h else "") if (k == "handle" or c["fx"] == "reel-frame") else brand.get("name", "")
                if v: d[k] = v
        miss = [k for k in MUST.get(c["fx"], []) if k not in d]
        if miss: print(f"WARNING fx {c['fx']} at {c['start']:.1f}s: {', '.join(miss)} not set: Vibha's English sample words would show. Put her words in the card.")
        plan.append(d)
    return plan


def enc_args(final):
    if MAC: return ["-c:v", "h264_videotoolbox", "-b:v", "40M" if final else "4M", "-allow_sw", "1"]
    return ["-c:v", "libx264", "-preset", "medium" if final else "veryfast", "-crf", "14" if final else "20"]


def main():
    reel = Path(sys.argv[1]).expanduser().resolve()
    edit = json.load(open(reel / "edit.json", encoding="utf-8"))
    cards = sorted([c for c in edit.get("cards", []) if c.get("type") == "fx"], key=lambda c: c["start"])
    out = reel / ("master_fx_540.mp4" if DRAFT else "master_fx.mp4")
    if not cards:
        for f in ("master_fx.mp4", "master_fx_540.mp4"): (reel / f).unlink(missing_ok=True)
        print("fx: no effects in this reel"); return
    base = reel / "master.mp4"
    small = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "csv=p=0", str(base)],
                               capture_output=True, text=True).stdout or 1920) <= 960
    if DRAFT and not small:   # the same 540p copy build_reel.py makes for drafts (a 540p draft master is used as it is)
        m540 = reel / "master_540.mp4"
        if not m540.exists() or m540.stat().st_mtime < base.stat().st_mtime:
            run("ffmpeg", "-nostdin", "-v", "error", "-y", "-i", base, "-vf", "scale=540:960", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-g", "30", "-c:a", "copy", m540)
        base = m540
    width = 540 if DRAFT else int(os.environ.get("REEL_FX_WIDTH", "1080"))
    py = vpython(); env = {**os.environ, **brand_env(py), **models_env(), "PYTHONUTF8": "1"}
    th = thumbs(reel, reel / "master.mp4"); D = dur_of(base)
    # effects whose seconds (with 0.4 s around them) overlap go through the effect engine together, so they stack
    groups = []
    for c in cards:
        a, b = max(0.0, c["start"] - 0.4), min(D, c["end"] + 0.4)
        if groups and a <= groups[-1][1]: groups[-1][1] = max(groups[-1][1], b); groups[-1][2].append(c)
        else: groups.append([a, b, [c]])
    bk = f"{base.stat().st_size}:{base.stat().st_mtime_ns}:{width}:{env['FX_FONTS']}:{env['FX_COLORS']}"
    cache = reel / ".cache" / "fx"; cache.mkdir(parents=True, exist_ok=True)
    segs = []
    for a, b, cs in groups:
        plan = fx_plan(cs, a, reel, th, BRAND)
        key = hashlib.sha1((bk + json.dumps(plan, sort_keys=True, ensure_ascii=False) + f"{a:.3f}{b:.3f}").encode()).hexdigest()[:16]
        seg = cache / f"{key}.mp4"
        if not seg.exists():
            src, pj = cache / f"{key}_in.mp4", cache / f"{key}.json"
            run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", base, "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "12", "-c:a", "aac", src)
            json.dump({"effects": plan}, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"fx {', '.join(c['fx'] for c in cs)} at {a:.1f}-{b:.1f}s ...", flush=True)
            r = subprocess.run([str(py), str(VD / "scripts" / "fx.py"), "--plan", str(pj), str(src), str(seg), "--width", str(width)],
                               env=env, capture_output=True, text=True)
            if r.returncode or not seg.exists():
                sys.exit(f"fx: the effect engine failed on {', '.join(c['fx'] for c in cs)}:\n{(r.stdout + r.stderr)[-1500:]}")
            src.unlink(missing_ok=True)
        segs.append((a, b, seg))
    key = hashlib.sha1((bk + "".join(str(s) for s in segs)).encode()).hexdigest()
    stamp = out.with_suffix(".key")
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        print(f"fx: {out.name} is up to date ({len(cards)} effects)"); return
    # each processed piece over the cut, exactly on its seconds; the sound stays the cut's own
    ins, fl, last = ["-i", str(base)], [], "0:v"
    for k, (a, b, seg) in enumerate(segs, 1):
        ins += ["-itsoffset", f"{a:.3f}", "-i", str(seg)]
        fl.append(f"[{k}:v]scale={'540:960' if DRAFT else 'iw:ih'},setsar=1[s{k}];[{last}][s{k}]overlay=eof_action=pass:enable='between(t,{a:.3f},{b - 0.02:.3f})'[v{k}]")
        last = f"v{k}"
    run("ffmpeg", "-nostdin", "-v", "error", "-y", *ins, "-filter_complex", ";".join(fl), "-map", f"[{last}]", "-map", "0:a?",
        *enc_args(not DRAFT), "-g", "30", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out)
    stamp.write_text(key)
    print(f"fx: {len(cards)} effects in {len(segs)} pieces -> {out.name}")


def previews():
    """3 s menu clips of every effect on this reel (the «+ Додати» library shows them)."""
    reel = Path(sys.argv[1]).expanduser().resolve()
    names = sys.argv[sys.argv.index("--names") + 1].split(",") if "--names" in sys.argv else None
    py = vpython(); env = {**os.environ, **brand_env(py), **models_env(), "PYTHONUTF8": "1"}
    base = reel / "master.mp4"; th = thumbs(reel, base)
    D = dur_of(base); a = min(max(1.0, D * 0.3), max(0.0, D - 4.0))
    menu = HOME / "menu"; menu.mkdir(parents=True, exist_ok=True)
    src = reel / ".cache" / "fx" / "preview_in.mp4"; src.parent.mkdir(parents=True, exist_ok=True)
    run("ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.2f}", "-t", "3.6", "-i", base, "-vf", "scale=360:640", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "16", "-an", src)
    cat = json.load(open(HERE.parent / "references" / "motion_catalog.json", encoding="utf-8"))["motions"]
    todo = [m for m in cat if m.get("engine") == "fx" and (not names or m["fx"] in names)]
    for m in todo:
        out = menu / f"{m['name']}.mp4"
        if out.exists() and not names: continue
        plan = fx_plan([{"fx": m["fx"], "start": 0.3, "end": 3.4, "sample": True}], 0, reel, th, BRAND)
        pj = src.parent / "preview.json"; json.dump({"effects": plan}, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([str(py), str(VD / "scripts" / "fx.py"), "--plan", str(pj), str(src), str(out), "--width", "360"], env=env,
                           capture_output=True, text=True)
        print(("ok   " if r.returncode == 0 and out.exists() else "FAIL ") + m["name"] + ("" if r.returncode == 0 else "  " + (r.stderr or r.stdout)[-300:]), flush=True)


if __name__ == "__main__":
    previews() if "--previews" in sys.argv else main()
