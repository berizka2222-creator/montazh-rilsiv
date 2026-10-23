#!/usr/bin/env python3
"""Storyboard: how each proposed graphic will really look, before any draft is rendered.

  storyboard.py <reel> [<out dir>] [--only id,id]        (run after review_sync.py export: it reads <reel>/review_reel.json)

For every graphic on the board (and every hook option in proposal.json "hookOptions") it cuts the few seconds of their
video around it, puts that one card on it with build_reel (brand colours, fonts, the catalog's tested placement) and
snapshots its peak: <out>/story_<id>.jpg (540x960), <out>/hook_<n>.jpg for the hook options. No full render: ~10 s a card.
Upload them to the page and set each board item's "storyUrl" and each "hookOptions" item's "img" in reel/current: the
«Графіка» tab then shows the real look instead of a frame with a text box, and the hook as pictures to pick from."""
import argparse, glob, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / "scripts"))
from review_sync import raw_clip

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("reel"); ap.add_argument("out", nargs="?"); ap.add_argument("--only", default=""); ap.add_argument("--workers", type=int, default=2)
A = ap.parse_args()
reel = Path(A.reel).expanduser().resolve(); out = Path(A.out).expanduser().resolve() if A.out else reel / "storyboard"
out.mkdir(parents=True, exist_ok=True)
R = json.load(open(reel / "review_reel.json")); words = R["words"]
prop = json.load(open(reel / "proposal.json")) if (reel / "proposal.json").exists() else {}
src = raw_clip(reel)
PAGE_KEYS = ("id", "kind", "what", "w0", "w1", "state", "place", "moved", "gone", "own", "shifted", "capsAside", "thumbUrl", "imgUrl", "storyUrl", "user")
only = {x for x in A.only.split(",") if x}

def jobs():
    for g in R.get("board", []):
        if only and g["id"] not in only: continue
        if g.get("type") == "overlay": continue          # their own uploads: the page already shows the real thing
        t0 = words[g["w0"]]["s"]; t1 = words[g["w1"]]["e"] if g.get("w1") is not None else t0 + float(g.get("dur", 3.0))
        spec = {k: v for k, v in g.items() if k not in PAGE_KEYS}
        yield f"story_{g['id']}", spec, t0, max(t1, t0 + 1.2)
    hook = next((g for g in R.get("board", []) if g.get("type") == "title"), None)
    for n, text in enumerate(prop.get("hookOptions") or [], 1):
        if only and f"hook_{n}" not in only: continue
        spec = {k: v for k, v in (hook or {"type": "title"}).items() if k not in PAGE_KEYS}
        spec["text"] = text
        t0 = words[hook["w0"]]["s"] if hook else 0.0
        yield f"hook_{n}", spec, t0, t0 + 3.5

def one(job):
    name, spec, t0, t1 = job
    d = out / "w" / name; shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
    a = max(0.0, t0 - 0.6); dur = (t1 - a) + 0.6
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(src), "-t", f"{dur:.3f}", "-vf",
                    "scale=540:960:force_original_aspect_ratio=increase,crop=540:960", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                    "-an", str(d / "master.mp4")], check=True)
    seg = [{"text": w["text"], "start": round(w["s"] - a, 3), "end": round(w["e"] - a, 3)} for w in words if a <= w["s"] < a + dur]
    json.dump(seg, open(d / "master_transcript.json", "w"), ensure_ascii=False)
    if (reel / "face.json").exists(): shutil.copy(reel / "face.json", d / "face.json")
    for sub in ("elements", "shots", "overlays", "motion"):        # the files a card may point at, relative to the reel
        if (reel / sub).exists(): os.symlink(reel / sub, d / sub)
    st, en = round(t0 - a, 3), round(t1 - a, 3)
    card = {**spec, "start": st, "end": en, "sfx": False}
    json.dump({"captions": [], "punch": [], "cards": [card], "style": json.load(open(reel / "edit.json")).get("style", "brand")
               if (reel / "edit.json").exists() else "brand", "no_carousel_ok": True}, open(d / "edit.json", "w"), ensure_ascii=False)
    b = subprocess.run([sys.executable, str(SK / "scripts/build_reel.py"), str(d)], capture_output=True, text=True, env={**os.environ, "REEL_DRAFT": "1"})
    if b.returncode: return name, "build_fail " + b.stderr.strip()[-160:]
    peak = st + min(1.4, (en - st) * 0.6)                  # far enough in that the card has fully arrived
    if spec.get("type") == "head" or str(spec.get("name", "")).startswith("head-"): peak = max(st + 0.6, en - 0.35)   # a head layout: all its words are on
    subprocess.run(["npx", "-y", "hyperframes@0.8.145", "snapshot", str(d / "proj"), "--at", f"{peak:.2f}", "--no-end", "--describe", "false",
                    "--timeout", "25000", "-o", str(d / "snaps")], capture_output=True, text=True)
    png = sorted(glob.glob(str(d / "snaps/frame-*.png")))
    if not png: return name, "snap_fail"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", png[0], "-vf", "scale=540:960", "-q:v", "4", str(out / f"{name}.jpg")])
    shutil.rmtree(d)
    return name, "ok"

js = list(jobs()); print(f"storyboard: {len(js)} frames for {reel.name}", flush=True)
with ThreadPoolExecutor(max(1, A.workers)) as ex:
    for name, st in ex.map(one, js): print(f"{st[:60]:12s} {name}", flush=True)
shutil.rmtree(out / "w", ignore_errors=True)
print(f"done: {out}")
