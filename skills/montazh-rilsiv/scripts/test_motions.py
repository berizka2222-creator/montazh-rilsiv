#!/usr/bin/env python3
"""Re-test catalog motions on a real reel, each ALONE, so a HyperFrames update or a new item can be judged by eye.

  test_motions.py <sample reel> <out dir> [--status manual,candidate | --names a,b] [--previews] [--workers 2]

<sample reel> is any cut reel folder (master.mp4, master_transcript.json, face.json). For every motion it builds a one-card
draft (the motion from 1.0 to 4.0 s, Ukrainian sample text, the catalog's tested placement) and:
  check (default)  snapshots at 0.4 s and 2.6 s -> <out>/<name>_pre.png, <name>_mid.png. The 0.4 s frame must be the plain
                   video: anything else means the motion leaks outside its window (flagged LEAK in the summary).
                   Then contact sheets <out>/sheet_000.jpg ... (16 per sheet, in the printed order) to look through.
  --fit            measure each motion drawn at zoom 1.0 (REEL_FIT_MEASURE) against the plain video and lower the catalog
                   card "zoom" where the usual blow-up (low 1.5, split 1.25, dim 1.2, size-free low 1.9) pushes it past the
                   frame sides or under the bottom: <out>/fit.json + fit_sheet.jpg; --write saves the zooms to the catalog.
                   Re-render those previews after (delete their .mp4, run --previews --names ...).
  --previews       a real 3 s looping clip per motion -> <out>/<name>.mp4 (540x960, rendered at 24 fps; give it a SHORT reel, menu_previews.py does): the «Тільки вручну» previews on the
                   review page (upload them as page assets, map name -> url in <REELS_HOME>/.motion_previews.json).
Already done items are skipped, so a run can be stopped and resumed. Two workers is the most an 8 GB Mac takes.
Verdicts go into references/motion_catalog.json by hand (status, card placement, replace, note): see references/motions.md."""
import argparse, glob, json, os, re, shutil, statistics, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("reel"); ap.add_argument("out")
ap.add_argument("--status", default="candidate"); ap.add_argument("--names", default="")
ap.add_argument("--previews", action="store_true"); ap.add_argument("--fit", action="store_true"); ap.add_argument("--write", action="store_true"); ap.add_argument("--workers", type=int, default=2)
A = ap.parse_args()
SRC, OUT = Path(A.reel).expanduser().resolve(), Path(A.out).expanduser().resolve()
OUT.mkdir(parents=True, exist_ok=True)
cat = json.load(open(SK / "references/motion_catalog.json"))["motions"]
names = [n for n in A.names.split(",") if n]
items = [m for m in cat if (m["name"] in names if names else m.get("status") in A.status.split(","))]
EXT = ".mp4" if A.previews else "_fit.json" if A.fit else "_mid.png"
items = [m for m in items if not (OUT / f"{m['name']}{EXT}").exists()]
if not (SRC / "master_540.mp4").exists():          # one 540p copy for every test, never one per motion
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(SRC / "master.mp4"), "-vf", "scale=540:960", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "20", "-c:a", "copy", str(SRC / "master_540.mp4")], check=True)
ELEMS = sorted(p for p in (HOME / "assets" / "elements").glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[:5]

POOL = "клієнт ціна цінність оффер таргет реклама питання бюджет результат заявка діалог".split()
def ua(n):                                         # Ukrainian sample text about as long as the English default
    out, i = [], 0
    while len(" ".join(out)) < n: out.append(POOL[i % len(POOL)]); i += 1
    return " ".join(out)[:max(n, 3)].strip()
SKIP_IDS = re.compile(r"^(cues|accent|exit|layout|columns|type|tail|delivered|surface|image\d*|background|cardImage|brandLogo|count|value|"
                      r"percent|speed|duration|tone|theme|mode|path|times|data|beats|url)$", re.I)

def sample_vars(src):
    vars_ = {}
    mm = re.search(r"data-composition-variables='(\[.*?\])'", src.read_text(), re.S) if src else None
    if not mm: return vars_
    try:
        for v in json.loads(mm.group(1)):
            dv = v.get("default")
            if v.get("type") == "string" and isinstance(dv, str) and dv.strip() and not SKIP_IDS.match(v["id"]) and not dv.startswith(("assets/", "http", "#")):
                sep = "," if "," in dv and v["id"] in ("options", "items", "words", "rows", "list", "labels") else ("|" if "|" in dv else None)
                vars_[v["id"]] = sep.join(ua(min(int(len(x) * 1.1), 12)) for x in dv.split(sep)) if sep else ua(min(int(len(dv) * 1.1), 14))
    except ValueError: pass
    return vars_

def preview_clip(proj, out, a, b):
    """Render the draft project for real (24 fps) and keep seconds a..b as a looping clip (540x960, no sound: big enough to open full screen)."""
    tmp = proj.parent / "pv.mp4"
    r = subprocess.run(["npx", "-y", "hyperframes@0.8.145", "render", str(proj), "--workers", "1", "--fps", "24",
                        "--quality", "draft", "--quiet", "-o", str(tmp)], capture_output=True, text=True)
    if r.returncode or not tmp.exists(): print("render error:", (r.stderr or r.stdout).strip()[-300:], flush=True); return False
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", str(tmp), "-vf", "scale=540:960:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-movflags", "+faststart", "-an", str(out)])
    return out.exists()

def one(m):
    name = m["name"]; d = OUT / "w" / name
    d.mkdir(parents=True, exist_ok=True)
    for f in ("master.mp4", "master_540.mp4", "master_transcript.json", "face.json"):
        if (SRC / f).exists() and not (d / f).exists(): os.symlink(SRC / f, d / f)
    src = next((SK / "engine/hf/compositions").rglob(f"{name}.html"), None)
    card = {"type": "motion", "name": name, "start": 1.0, "end": 4.0, "vars": sample_vars(src), "id": name}
    if m.get("replace"): card["replace"] = {en: ua(min(len(en), 16)) for en in m["replace"] if str(m["replace"][en]).startswith("<")}
    if ELEMS and (m.get("image_vars") or "carousel" in name or "картин" in (m.get("note") or "")):
        card["images"] = [str(p) for p in ELEMS]
    json.dump({"captions": [], "punch": [], "cards": [card], "style": "brand", "no_carousel_ok": True}, open(d / "edit.json", "w"), ensure_ascii=False)
    b = subprocess.run([sys.executable, str(SK / "scripts/build_reel.py"), str(d)], capture_output=True, text=True,
                       env={**os.environ, "REEL_DRAFT": "1", **({"REEL_FIT_MEASURE": "1"} if A.fit else {})})
    if b.returncode: return name, "build_fail " + b.stderr.strip()[-160:]
    if A.fit: return fit_snap(name, d)
    if A.previews:   # a real clip of the motion (rendered, smooth), not a slideshow of snapshots
        ok = preview_clip(d / "proj", OUT / f"{name}.mp4", 0.9, 4.1)
        shutil.rmtree(d, ignore_errors=True)
        return name, "ok" if ok else "render_fail"
    subprocess.run(["npx", "-y", "hyperframes@0.8.145", "snapshot", str(d / "proj"), "--at", "0.4,2.6", "--no-end", "--describe", "false",
                    "--timeout", "25000", "-o", str(d / "snaps")], capture_output=True, text=True)
    pngs = sorted(glob.glob(str(d / "snaps/frame-*.png")))
    if len(pngs) < 2: return name, "snap_fail"
    if False: pass
    else:
        os.replace(pngs[0], OUT / f"{name}_pre.png"); os.replace(pngs[1], OUT / f"{name}_mid.png")
    shutil.rmtree(d)                                # only links and the throwaway project: nothing to keep
    return name, "ok"

FT = (1.8, 2.6, 3.4)
def fit_snap(name, d):
    log = json.load(open(d / "fit.json")) if (d / "fit.json").exists() else {}
    if not log.get(name, {}).get("box"): shutil.rmtree(d, ignore_errors=True); json.dump({}, open(OUT / f"{name}_fit.json", "w")); return name, "no blow-up"
    subprocess.run(["npx", "-y", "hyperframes@0.8.145", "snapshot", str(d / "proj"), "--at", ",".join(map(str, FT)), "--no-end", "--describe", "false",
                    "--timeout", "25000", "-o", str(d / "snaps")], capture_output=True, text=True)
    pngs = sorted(glob.glob(str(d / "snaps/frame-*.png")))
    if len(pngs) < len(FT): return name, "snap_fail"
    for k, p in enumerate(pngs): os.replace(p, OUT / f"{name}_fit{k}.png")
    json.dump(log[name], open(OUT / f"{name}_fit.json", "w")); shutil.rmtree(d, ignore_errors=True)
    return name, "measured"

print(f"{len(items)} motions to test on {SRC.name}", flush=True)
with ThreadPoolExecutor(max(1, A.workers)) as ex:
    for name, st in ex.map(one, items): print(f"{st[:60]:12s} {name}", flush=True)
shutil.rmtree(OUT / "w", ignore_errors=True)
if A.previews: sys.exit(0)
if A.fit:   # content box at zoom 1.0 -> the largest zoom that keeps it inside x 60..1020 and above y 1880
    def g(p):   # 108x192 RGB: one pixel = 10 px of the 1080x1920 frame; the stage is magenta, so anything else is the motion
        return subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", "scale=108:192,format=rgb24", "-f", "rawvideo", "-"], capture_output=True).stdout
    res = {}
    for m in cat:
        n = m["name"]; f = OUT / f"{n}_fit.json"
        if not f.exists(): continue
        info = json.load(open(f))
        if not info.get("box"): continue
        cols, rows = set(), set()
        for k in range(len(FT)):
            px = g(OUT / f"{n}_fit{k}.png")
            for i in range(0, len(px) - 2, 3):
                if abs(px[i] - 255) + px[i + 1] + abs(px[i + 2] - 255) > 60: cols.add(i // 3 % 108); rows.add(i // 3 // 108)
        cols = [c for c in cols if c - 1 in cols or c + 1 in cols]; rows = [r for r in rows if r - 1 in rows or r + 1 in rows]
        if not cols or not rows: res[n] = {"empty": True}; continue
        x, y, bw, bh = info["box"]; cx, cy = x + bw / 2, y + bh / 2
        x0, x1, y0, y1 = min(cols) * 10, max(cols) * 10 + 10, min(rows) * 10, max(rows) * 10 + 10
        hw, down = max(cx - x0, x1 - cx, 1), max(y1 - cy, 1)
        cur = float((m.get("card") or {}).get("zoom", info["default"]))
        z = max(1.0, min(cur, 480 / hw, (1880 - cy) / down)); z = int(z * 20) / 20
        bg = x0 <= max(0, x) + 15 and x1 >= min(1080, x + bw) - 15      # spans its whole box: an opaque background, judge by eye
        res[n] = {"content": [x0, y0, x1, y1], "box": info["box"], "zoom_was": cur, "zoom": z, "bg": bg}
    json.dump(res, open(OUT / "fit.json", "w"), indent=1)
    low = {n: r for n, r in res.items() if r.get("zoom") and r["zoom"] < r["zoom_was"] - 0.02}
    for n, r in sorted(low.items()): print(f"{'BG? ' if r['bg'] else ''}{n}: zoom {r['zoom_was']} -> {r['zoom']}  content x {r['content'][0]}..{r['content'][2]}")
    print(f"{len(low)} of {len(res)} measured motions would crop at their zoom")
    if A.write:
        for m in cat:
            r = low.get(m["name"])
            if r: m.setdefault("card", {})["zoom"] = r["zoom"]   # opaque ones too: at 1.0 the whole card shows
        full = json.load(open(SK / "references/motion_catalog.json")); full["motions"] = cat
        json.dump(full, open(SK / "references/motion_catalog.json", "w"), ensure_ascii=False, indent=1)
        print("catalog: zoom written for", sum(1 for r in low.values() if not r["bg"]), "(BG? ones left for a look)")
    sys.exit(0)

# leak check + contact sheets. The median pre-start frame is the plain video (most motions don't leak); a motion whose
# 0.4 s frame differs from it shows something outside its own window.
done = sorted(p.name[:-8] for p in OUT.glob("*_mid.png"))
def gray(p):   # 54x96 grey pixels via ffmpeg, no extra Python packages needed
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vf", "scale=54:96,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    return r.stdout
pres = {n: gray(OUT / f"{n}_pre.png") for n in done if (OUT / f"{n}_pre.png").exists()}
if pres:
    base = bytes(int(statistics.median(px)) for px in zip(*list(pres.values())[:60]))
    leak = {n: round(sum(abs(a - b) for a, b in zip(v, base)) / max(1, len(base)), 1) for n, v in pres.items()}
    json.dump(leak, open(OUT / "leaks.json", "w"), indent=0)
for k in range(0, len(done), 16):
    sel = done[k:k + 16]
    ins = sum((["-i", str(OUT / f"{n}_mid.png")] for n in sel), [])
    pads = "".join(f"[{j}]scale=225:400[s{j}];" for j in range(len(sel)))
    lay = "|".join(f"{(j % 8) * 225}_{(j // 8) * 400}" for j in range(len(sel)))
    if len(sel) == 1: subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-vf", "scale=225:400", str(OUT / f"sheet_{k:03d}.jpg")]); continue
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", pads + "".join(f"[s{j}]" for j in range(len(sel))) +
                    f"xstack=inputs={len(sel)}:layout={lay}:fill=white", str(OUT / f"sheet_{k:03d}.jpg")])
for i, n in enumerate(done):
    flag = " LEAK" if pres and leak.get(n, 0) > 6 else ""
    print(f"{i:3d} {n}{flag}", end="   " if (i + 1) % 4 else "\n")
print(f"\nsheets: {OUT}/sheet_*.jpg (16 per sheet, in this order)")
