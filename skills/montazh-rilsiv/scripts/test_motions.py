#!/usr/bin/env python3
"""Re-test catalog motions on a real reel, each ALONE, so a HyperFrames update or a new item can be judged by eye.

  test_motions.py <sample reel> <out dir> [--status manual,candidate | --names a,b] [--previews] [--workers 2]

<sample reel> is any cut reel folder (master.mp4, master_transcript.json, face.json). For every motion it builds a one-card
draft (the motion from 1.0 to 4.0 s, Ukrainian sample text, the catalog's tested placement) and:
  check (default)  snapshots at 0.4 s and 2.6 s -> <out>/<name>_pre.png, <name>_mid.png. The 0.4 s frame must be the plain
                   video: anything else means the motion leaks outside its window (flagged LEAK in the summary).
                   Then contact sheets <out>/sheet_000.jpg ... (16 per sheet, in the printed order) to look through.
  --previews       a 3 s looping clip per motion -> <out>/<name>.mp4 (216x384, ~30 KB): the «Тільки вручну» previews on the
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
ap.add_argument("--previews", action="store_true"); ap.add_argument("--workers", type=int, default=2)
A = ap.parse_args()
SRC, OUT = Path(A.reel).expanduser().resolve(), Path(A.out).expanduser().resolve()
OUT.mkdir(parents=True, exist_ok=True)
cat = json.load(open(SK / "references/motion_catalog.json"))["motions"]
names = [n for n in A.names.split(",") if n]
items = [m for m in cat if (m["name"] in names if names else m.get("status") in A.status.split(","))]
EXT = ".mp4" if A.previews else "_mid.png"
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
    b = subprocess.run([sys.executable, str(SK / "scripts/build_reel.py"), str(d)], capture_output=True, text=True, env={**os.environ, "REEL_DRAFT": "1"})
    if b.returncode: return name, "build_fail " + b.stderr.strip()[-160:]
    at = "1.15,1.5,1.9,2.3,2.7,3.1,3.5" if A.previews else "0.4,2.6"
    subprocess.run(["npx", "-y", "hyperframes@0.8.145", "snapshot", str(d / "proj"), "--at", at, "--no-end", "--describe", "false",
                    "--timeout", "25000", "-o", str(d / "snaps")], capture_output=True, text=True)
    pngs = sorted(glob.glob(str(d / "snaps/frame-*.png")))
    if len(pngs) < 2: return name, "snap_fail"
    if A.previews:
        lst = d / "list.txt"; lst.write_text("".join(f"file '{p}'\nduration 0.4\n" for p in pngs) + f"file '{pngs[-1]}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "scale=216:384:flags=lanczos,fps=10,format=yuv420p",
                        "-c:v", "libx264", "-crf", "30", "-movflags", "+faststart", "-an", str(OUT / f"{name}.mp4")])
    else:
        os.replace(pngs[0], OUT / f"{name}_pre.png"); os.replace(pngs[1], OUT / f"{name}_mid.png")
    shutil.rmtree(d)                                # only links and the throwaway project: nothing to keep
    return name, "ok"

print(f"{len(items)} motions to test on {SRC.name}", flush=True)
with ThreadPoolExecutor(max(1, A.workers)) as ex:
    for name, st in ex.map(one, items): print(f"{st[:60]:12s} {name}", flush=True)
shutil.rmtree(OUT / "w", ignore_errors=True)
if A.previews: sys.exit(0)

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
