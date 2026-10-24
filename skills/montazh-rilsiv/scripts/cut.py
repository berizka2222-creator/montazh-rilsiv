#!/usr/bin/env python3
"""Apply the approved rough cut: keep spans from edl.json (in play order), speed up, optional colour grade, scale to the
brand resolution. Writes master.mp4 in the reel folder.
Usage: python3 cut.py <reel-folder>      (reads <reel-folder>/edl.json and ~/reels/brand.json)"""
import json, os, subprocess, sys
from pathlib import Path

reel = Path(sys.argv[1]).expanduser()
home = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
brand = json.load(open(home / "brand.json"))
edl = json.load(open(reel / "edl.json"))

src, audio = reel / edl["source"], reel / edl.get("audio", "voice.wav")
spans = [[round(a * 30) / 30, round(b * 30) / 30] for a, b in edl["keep"]]   # on whole frames, so every span's picture and sound are the same length
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pacing import pacing
speed = pacing(brand)["speed"]
w, h = brand.get("resolution", [1080, 1920])
if os.environ.get("REEL_PREVIEW"): w, h = 1080, 1920          # previews cut at 1080p: a quarter of the work
DRAFT = bool(os.environ.get("REEL_DRAFT"))                      # fast review draft: 540x960, colour without the slow clarity/sharpen
if DRAFT: w, h = 540, 960
grade = edl.get("grade") or brand.get("grade")   # the page's colour grade (review_sync import writes it into edl.json) wins
if DRAFT and grade: grade = ",".join(f for f in grade.split(",") if not f.startswith("unsharp"))   # the final adds them back
FADE = 0.012  # tiny audio fades at every join so cuts never click

# every span is its own seeked input: ffmpeg decodes only the kept seconds, not the whole clip from the start
vp, ap, ins = [], [], []
for k, (a, b) in enumerate(spans):
    ins += [*(["-hwaccel", "videotoolbox"] if sys.platform == "darwin" else []), "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src), "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(audio)]
    vp.append(f"[{2 * k}:v]setpts=PTS-STARTPTS,trim=duration={b - a:.4f},setpts=PTS-STARTPTS[v{k}]")   # exact length: a seeked input can run a frame long, and that adds up to lip-sync drift
    ap.append(f"[{2 * k + 1}:a]asetpts=PTS-STARTPTS,atrim=duration={b - a:.4f},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d={FADE},afade=t=out:st={max(b - a - FADE, 0):.3f}:d={FADE}[a{k}]")
n = len(spans)
post = [f"setpts=PTS/{speed}", f"scale={w}:{h}:force_original_aspect_ratio=increase", f"crop={w}:{h}", "fps=30"]
if grade:
    if edl.get("grade_from") is not None:   # grade switches on at this reel second (a "before/after" moment)
        # shortcut: splits filters on commas, so a filter option containing a comma breaks; quote-aware split if one ever does
        grade = ",".join(f + (":" if "=" in f else "=") + f"enable='gte(t,{float(edl['grade_from']):.3f})'" for f in grade.split(","))
    post.append(grade)   # graded at the output size: on 4K frames the same filters cost ~4x more
vcat = "".join(f"[v{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0," + ",".join(post) + "[vout]"
acat = "".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1,atempo={speed}[aout]"

script = reel / "cut_filter.txt"
script.write_text(";".join(vp + ap) + ";" + vcat + ";" + acat)
kept = sum(b - a for a, b in spans)
print(f"{n} spans, {kept:.1f}s kept -> {kept / speed:.1f}s at {speed}x, {w}x{h}")
if kept / speed > brand.get("max_seconds", 60):
    print(f"warning: longer than {brand.get('max_seconds', 60)}s - suggest more cuts")

MAC = sys.platform == "darwin"
# master.mp4 is an intermediate: the renderer encodes it again into draft.mp4 / final.mp4. On a Mac the media engine decodes
# the HEVC and encodes the master at a high bitrate: ~4.5x faster than libx264 CRF 14 (a 91 s cut from 4K: ~1.5 min, not 6.5)
# and visually the same (SSIM 0.99 against CRF 14, measured 2026-10-24). Elsewhere libx264 as before.
if MAC:
    enc = ["-c:v", "h264_videotoolbox", "-b:v", "4M" if DRAFT else ("80M" if w >= 2160 else "40M"), "-allow_sw", "1"]
elif DRAFT or (os.environ.get("REEL_PREVIEW") and brand.get("resolution", [1080, 1920])[0] > 1080):
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
else:
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "14"]
cmd = ["nice", "-n", "15", "ffmpeg", "-y", "-v", "error", "-stats",
       *ins, "-/filter_complex", str(script), "-map", "[vout]", "-map", "[aout]", *enc,
       "-g", "30", "-keyint_min", "30", "-pix_fmt", "yuv420p",   # a keyframe every second: the renderer seeks frame by frame and freezes on sparse keyframes
       "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(reel / "master.mp4")]
# nothing changed since the last cut (same spans, grade, size, sources): keep master.mp4 instead of cutting again
import hashlib
st = lambda f: f"{f}:{f.stat().st_size}:{f.stat().st_mtime_ns}" if f.exists() else str(f)
key = hashlib.sha1("|".join([script.read_text(), " ".join(enc), st(src), st(audio)]).encode()).hexdigest()
stamp = reel / ".master_key"
if (reel / "master.mp4").exists() and stamp.exists() and stamp.read_text() == key and not os.environ.get("REEL_RECUT"):
    print("master.mp4 is up to date (same cut): not cutting again")
else:
    subprocess.run(cmd, check=True); stamp.write_text(key)
print(reel / "master.mp4")
