#!/usr/bin/env python3
"""The effects menu on their own face: a 3 s looping clip of every effect in the library, made on THEIR reel in THEIR brand.

  menu_previews.py <reel> [--only manual|caption|suggested] [--workers 2]

Run it once in the background during the person's first reel (~40-60 min on an 8 GB Mac; it resumes where it stopped).
Order: «Тільки вручну» effects, then the caption styles (with their own words), then everything Claude suggests
(ready / replace / full_only). Clips land in <REELS_HOME>/menu/<name>.mp4 (216x384, ~30-60 KB). Upload them to the review
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

def motions(statuses):
    subprocess.run([sys.executable, str(SK / "scripts/test_motions.py"), str(reel), str(OUT), "--status", statuses, "--previews",
                    "--workers", str(A.workers)])

def captions():
    """Each caption style over the first ~9 s of their reel, with their own words and timing."""
    edit = json.load(open(reel / "edit.json")) if (reel / "edit.json").exists() else {}
    caps = [c for c in edit.get("captions", []) if c["start"] < 9]
    if not caps:   # no edit yet: group the cut transcript in threes
        words = [w for w in json.load(open(reel / "master_transcript.json")) if w.get("text", "").strip() and w["start"] < 9]
        caps = [{"start": g[0]["start"], "end": g[-1]["end"], "words": [{"text": w["text"], "t": w["start"]} for w in g]}
                for g in (words[i:i + 3] for i in range(0, len(words), 3))]
    d = OUT / "w" / "_captions"; d.mkdir(parents=True, exist_ok=True)
    for f in ("master.mp4", "master_540.mp4", "master_transcript.json", "face.json"):
        if (reel / f).exists() and not (d / f).exists(): os.symlink(reel / f, d / f)
    for m in [m for m in cat if m.get("status") == "caption"]:
        n = m["name"]
        if (OUT / f"{n}.mp4").exists(): continue
        json.dump({"captions": caps, "punch": [], "cards": [], "style": "brand", "no_carousel_ok": True, "caption_style": n},
                  open(d / "edit.json", "w"), ensure_ascii=False)
        b = subprocess.run([sys.executable, str(SK / "scripts/build_reel.py"), str(d)], capture_output=True, text=True, env={**os.environ, "REEL_DRAFT": "1"})
        if b.returncode: print("build_fail", n, flush=True); continue
        shutil.rmtree(d / "snaps", ignore_errors=True)
        subprocess.run(["npx", "-y", "hyperframes@0.8.145", "snapshot", str(d / "proj"), "--at", ",".join(f"{0.4 * k:.1f}" for k in range(1, 13)),
                        "--no-end", "--describe", "false", "--timeout", "25000", "-o", str(d / "snaps")], capture_output=True, text=True)
        pngs = sorted(glob.glob(str(d / "snaps/frame-*.png")))
        if len(pngs) < 3: print("snap_fail", n, flush=True); continue
        lst = d / "list.txt"; lst.write_text("".join(f"file '{p}'\nduration 0.4\n" for p in pngs) + f"file '{pngs[-1]}'\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "scale=216:384:flags=lanczos,fps=10,format=yuv420p",
                        "-c:v", "libx264", "-crf", "28", "-movflags", "+faststart", "-an", str(OUT / f"{n}.mp4")])
        print("ok", n, flush=True)
    shutil.rmtree(OUT / "w", ignore_errors=True)

steps = {"manual": lambda: motions("manual"), "caption": captions, "suggested": lambda: motions("ready,replace,full_only")}
for k in ([A.only] if A.only else ["manual", "caption", "suggested"]):
    print(f"== {k}", flush=True); steps[k]()
done = sorted(p.stem for p in OUT.glob("*.mp4"))
print(f"menu: {len(done)} clips in {OUT}")
