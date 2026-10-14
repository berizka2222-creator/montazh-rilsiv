#!/usr/bin/env python3
"""Where the face sits in the clip, so graphics and captions keep off it.
Usage: python3 face_box.py <reel>   -> writes <reel>/face.json {"box": [x, y, w, h]} in 1080x1920 frame units
12 frames across raw.*; macOS Vision finds the face (+ hair above, chin below); the union of all frames is kept.
Without macOS/swift it falls back to the usual talking-head zone (25%..55% of the height)."""
import json, subprocess, sys, tempfile
from pathlib import Path
reel = Path(sys.argv[1]).expanduser()
src = next(iter(sorted(reel.glob("raw.*"))))
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout)
W, H = 1080, 1920
box = [W * 0.22, H * 0.25, W * 0.56, H * 0.30]   # fallback
with tempfile.TemporaryDirectory() as d:
    imgs = []
    for k in range(12):
        f = f"{d}/f{k:02d}.jpg"; t = dur * (k + 0.5) / 12
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1", "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", f], check=True)
        imgs.append(f)
    try:
        out = subprocess.run(["swift", str(Path(__file__).with_name("face_box.swift")), *imgs], capture_output=True, text=True, timeout=300).stdout.split("\n")
        faces = [list(map(float, l.split())) for l in out if l.strip() and l.strip() != "none"]
    except Exception as e:
        faces = []; print("face detection unavailable:", e)
    if faces:
        med = lambda v: sorted(v)[len(v) // 2]               # the usual position, not the one frame she leaned in
        x0 = med([f[0] for f in faces]) * W; x1 = med([f[0] + f[2] for f in faces]) * W
        y0 = med([f[1] for f in faces]) * H; y1 = med([f[1] + f[3] for f in faces]) * H
        h = y1 - y0; y0 -= h * 0.55; y1 += h * 0.08          # hair above the detected face (forehead..chin), a margin under the chin
        box = [max(0, x0 - 40), max(0, y0), min(W, x1 + 40) - max(0, x0 - 40), min(H, y1) - max(0, y0)]
        print(f"{len(faces)}/12 frames with a face")
    else: print("no face found: using the default zone")
box = [round(v) for v in box]
json.dump({"box": box}, open(reel / "face.json", "w"))
print("face box", box, f"(y {box[1]}..{box[1] + box[3]})")
