#!/usr/bin/env python3
"""A reference reel by link («зроби як тут»): download it, measure its pace and lay its frames out for Claude to read.

  reference.py <url> [<out dir>] [--transcribe]

1. Downloads with yt-dlp. Instagram often refuses anonymous downloads: then it retries with the login of the browser the
   person uses (Chrome, then Safari: `--cookies-from-browser`; macOS may ask once for the Mac password to read Chrome's
   login, «Дозволити завжди»). It only reads the post. If every way fails it exits 2: look at the reel in their browser
   instead (Claude in Chrome: seek the video and grab frames) or ask for a screen recording.
2. Writes <out>/ref.mp4, info.json (author, caption, duration), cuts.json (every shot change and the average shot length)
   and contact sheets sheet_00.jpg… (one frame every 1.5 s, 12 per sheet, time-stamped in the file name order), plus
   frames at every shot change (cut_<t>.jpg).
3. --transcribe: what they say, with ElevenLabs Scribe (scripts/transcribe.py), into transcript.json.
Then read the sheets and name the techniques (hook type and length, caption style, cut pace, zooms, graphics and their
moments, transitions, sound) and map each to this skill's tools: `motions.py menu`, caption styles, camera moves, template
cards (references/reference.md)."""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("url"); ap.add_argument("out", nargs="?"); ap.add_argument("--transcribe", action="store_true")
A = ap.parse_args()
slug = re.sub(r"[^A-Za-z0-9_-]", "", A.url.rstrip("/").split("/")[-1].split("?")[0])[:40] or "ref"
out = Path(A.out or f"~/reels/_refs/{slug}").expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
SK = Path(__file__).resolve().parent.parent

def dl(extra):
    try:   # with a browser login macOS may wait for the Mac password in a dialog: give them two minutes, never hang
        r = subprocess.run(["yt-dlp", "-q", "--no-warnings", "--no-playlist", "-f", "mp4/best", "--write-info-json", "-o", str(out / "ref.%(ext)s"), *extra, A.url],
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False, ["timed out waiting (the Mac password dialog for the browser login was not answered)"]
    return r.returncode == 0 and any(out.glob("ref.mp4")), (r.stderr or "").strip().splitlines()[-1:] or [""]
if not (out / "ref.mp4").exists():
    ok, err = dl([])
    for browser in ("chrome", "safari"):
        if ok: break
        print(f"plain download refused ({err[0][:90]}); trying with the {browser} login…", flush=True)
        ok, err = dl(["--cookies-from-browser", browser])
    if not ok:
        print("could not download:", err[0][:200]); sys.exit(2)
info = json.load(open(next(out.glob("ref*.info.json")))) if any(out.glob("ref*.info.json")) else {}
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out / "ref.mp4")],
                           capture_output=True, text=True).stdout or 0)
json.dump({"url": A.url, "author": info.get("uploader") or info.get("channel"), "caption": info.get("description"),
           "duration": round(dur, 2)}, open(out / "info.json", "w"), ensure_ascii=False, indent=1)
for f in out.glob("ref*.info.json"): f.unlink()

# shot changes: ffmpeg scene score; the average shot length is the cut pace
r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(out / "ref.mp4"), "-vf", "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"],
                   capture_output=True, text=True)
cuts = [round(float(m), 2) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
cuts = [t for i, t in enumerate(cuts) if not i or t - cuts[i - 1] > 0.25]
json.dump({"cuts": cuts, "count": len(cuts), "avg_shot": round(dur / (len(cuts) + 1), 2) if dur else None}, open(out / "cuts.json", "w"), indent=1)
for t in cuts[:40]:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t + 0.15:.2f}", "-i", str(out / "ref.mp4"), "-frames:v", "1", "-vf", "scale=270:-2",
                    str(out / f"cut_{t:06.2f}.jpg")])
# contact sheets: a frame every 1.5 s, 12 to a sheet (6 x 2), in time order
for old in out.glob("sheet_*.jpg"): old.unlink()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out / "ref.mp4"), "-vf", "fps=1/1.5,scale=216:-2,tile=6x2", str(out / "sheet_%02d.jpg")])
if A.transcribe:
    subprocess.run([sys.executable, str(SK / "scripts/transcribe.py"), str(out / "ref.mp4"), str(out / "transcript.json")])
n = len(list(out.glob("sheet_*.jpg")))
print(f"reference: {info.get('uploader', '?')} · {dur:.1f} s · {len(cuts)} shot changes (avg shot {dur / (len(cuts) + 1):.1f} s) · "
      f"{n} sheets (sheet k covers {18}k-{18}(k+1) s) → {out}")
