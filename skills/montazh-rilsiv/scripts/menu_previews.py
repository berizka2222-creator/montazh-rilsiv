#!/usr/bin/env python3
"""The effects menu on their own face: a 3 s looping clip of every effect in the library, made on THEIR reel in THEIR brand.

  menu_previews.py <reel> [--only manual|caption|suggested] [--workers 2]

Run it once in the background during the person's first reel (~40-60 min on an 8 GB Mac; it resumes where it stopped).
Order: «Тільки вручну» effects, then the caption styles (with their own words), then everything Claude suggests
(ready / replace / full_only). Clips land in <REELS_HOME>/menu/<name>.mp4 (360x640, a real 24 fps render of ~3-4 s, ~100-200 KB). Upload them to the review
page (25 per call) and map name -> url in <REELS_HOME>/.motion_previews.json: the page's «Меню ефектів» shows each effect
on them, with a basket «Мій вибір»."""
import argparse, glob, json, os, shutil, subprocess, sys
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("reel"); ap.add_argument("--only", default=""); ap.add_argument("--workers", type=int, default=2)
A = ap.parse_args()
reel = Path(A.reel).expanduser().resolve(); OUT = HOME / "menu"; OUT.mkdir(parents=True, exist_ok=True)
cat = json.load(open(SK / "references/motion_catalog.json"))["motions"]

# Every clip renders on a SHORT copy of the reel (its first SHORT s), so each preview is a real ~3 s render, not a slideshow.
SHORT = 4.4
SRC = reel / "_menu_src"; SRC.mkdir(exist_ok=True)
for f, vf in (("master.mp4", []), ("master_540.mp4", ["-vf", "scale=540:960"])):
    if not (SRC / f).exists():
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(reel / "master.mp4"), "-t", str(SHORT), *vf, "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "18", "-c:a", "aac", str(SRC / f)], check=True)
json.dump([w for w in json.load(open(reel / "master_transcript.json")) if w["start"] < SHORT - 0.2] if (reel / "master_transcript.json").exists() else [],
          open(SRC / "master_transcript.json", "w"), ensure_ascii=False)
if (reel / "face.json").exists() and not (SRC / "face.json").exists(): shutil.copy(reel / "face.json", SRC / "face.json")

def preview_clip(proj, out, a, b):
    """Render the draft project for real (24 fps) and keep seconds a..b as a looping clip (540x960, no sound: big enough to open full screen)."""
    tmp = proj.parent / "pv.mp4"
    r = subprocess.run(["npx", "-y", "hyperframes@0.8.145", "render", str(proj), "--workers", "1", "--fps", "24",
                        "--quality", "draft", "--quiet", "-o", str(tmp)], capture_output=True, text=True)
    if r.returncode or not tmp.exists(): print("render error:", (r.stderr or r.stdout).strip()[-300:], flush=True); return False
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(a), "-to", str(b), "-i", str(tmp), "-vf", "scale=540:960:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-crf", "27", "-preset", "slow", "-movflags", "+faststart", "-an", str(out)])
    return out.exists()

def motions(statuses):
    subprocess.run([sys.executable, str(SK / "scripts/test_motions.py"), str(SRC), str(OUT), "--status", statuses, "--previews",
                    "--workers", str(A.workers)])

def captions():
    """Each caption style over the first ~9 s of their reel, with their own words and timing."""
    edit = json.load(open(reel / "edit.json")) if (reel / "edit.json").exists() else {}
    caps = [c for c in edit.get("captions", []) if c["end"] < SHORT - 0.1]
    if not caps:   # no edit yet: group the cut transcript in threes
        words = [w for w in json.load(open(SRC / "master_transcript.json")) if w.get("text", "").strip()]
        caps = [{"start": g[0]["start"], "end": g[-1]["end"], "words": [{"text": w["text"], "t": w["start"]} for w in g]}
                for g in (words[i:i + 3] for i in range(0, len(words), 3))]
    d = OUT / "w" / "_captions"; d.mkdir(parents=True, exist_ok=True)
    for f in ("master.mp4", "master_540.mp4", "master_transcript.json", "face.json"):
        if (SRC / f).exists() and not (d / f).exists(): os.symlink(SRC / f, d / f)
    for m in [m for m in cat if m.get("status") == "caption"]:
        n = m["name"]
        if (OUT / f"{n}.mp4").exists(): continue
        json.dump({"captions": caps, "punch": [], "cards": [], "style": "brand", "no_carousel_ok": True, "caption_style": n},
                  open(d / "edit.json", "w"), ensure_ascii=False)
        b = subprocess.run([sys.executable, str(SK / "scripts/build_reel.py"), str(d)], capture_output=True, text=True, env={**os.environ, "REEL_DRAFT": "1"})
        if b.returncode: print("build_fail", n, flush=True); continue
        ok = preview_clip(d / "proj", OUT / f"{n}.mp4", 0.2, SHORT - 0.1)
        print("ok" if ok else "render_fail", n, flush=True)
    shutil.rmtree(OUT / "w", ignore_errors=True)

steps = {"manual": lambda: motions("manual"), "caption": captions, "suggested": lambda: motions("ready,replace,full_only")}
for k in ([A.only] if A.only else ["manual", "caption", "suggested"]):
    print(f"== {k}", flush=True); steps[k]()
done = sorted(p.stem for p in OUT.glob("*.mp4"))
print(f"menu: {len(done)} clips in {OUT}")
