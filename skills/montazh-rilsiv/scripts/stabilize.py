#!/usr/bin/env python3
"""Calm a shaky hand-held clip (b-roll from the phone in hand, a walk, a car).
After ffmpeg-skill's stabilize.py (MIT, github.com/kajisho5/ffmpeg-skill): two-pass vidstab when this Mac has an
ffmpeg with it (brew install ffmpeg-full: keg-only, sits next to the usual ffmpeg, found here automatically),
else OpenCV in ~/reels/.venv (feature tracking + a smoothed camera path; ffmpeg's built-in deshake made a driving
clip shakier in tests, so it isn't used).

    python3 stabilize.py <in> <out.mp4> [--strength 1|2|3] [--tripod]
  --strength 1 light (default 2; 3 for walking / running)   --tripod  lock the frame dead still (meant-to-be-static shots)
The edges stabilising reveals are cropped by a small zoom (3-8 % by strength). Audio is copied.
A talking head is not stabilised unless she asks: a slight natural sway reads as alive, a locked face can look pasted."""
import argparse, subprocess, sys, tempfile
from pathlib import Path

FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")


def has(exe, flt):
    return f" {flt} " in subprocess.run([str(exe), "-hide_banner", "-filters"], capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("out"); ap.add_argument("--strength", type=int, choices=[1, 2, 3], default=2)
    ap.add_argument("--tripod", action="store_true")
    a = ap.parse_args()
    zoom = {1: 3, 2: 5, 3: 8}[a.strength]
    exe = next((e for e in (FULL, Path("ffmpeg")) if (e == Path("ffmpeg") or e.exists()) and has(e, "vidstabdetect")), None)
    enc = ["-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy"]
    if exe:
        shk, smooth = {1: (4, 10), 2: (6, 20), 3: (9, 40)}[a.strength]
        with tempfile.TemporaryDirectory() as d:
            trf = f"{d}/t.trf"
            subprocess.run([str(exe), "-nostdin", "-v", "error", "-y", "-i", a.input, "-vf",
                            f"vidstabdetect=shakiness={shk}:accuracy=15:result={trf}" + (":tripod=1" if a.tripod else ""), "-f", "null", "-"], check=True)
            vf = f"vidstabtransform=input={trf}:zoom={zoom}:smoothing={smooth}:crop=keep" + (":tripod=1" if a.tripod else "") + ",unsharp=5:5:0.6:3:3:0.0"
            subprocess.run([str(exe), "-nostdin", "-v", "error", "-y", "-i", a.input, "-vf", vf, *enc, a.out], check=True)
        print(f"vidstab (2 passes), zoom {zoom} % -> {a.out}")
    else:
        venv = Path("~/reels/.venv/bin/python").expanduser()
        subprocess.run([str(venv), __file__, "--cv", a.input, a.out, str(a.strength), "1" if a.tripod else "0"], check=True)


def cv_stabilize(src, out, strength, tripod):
    """OpenCV: track corners frame to frame, sum the moves into the camera path, smooth it, warp each frame onto the
    smooth path, zoom a little to hide the edges. Two decodes, no temp frames on disk."""
    import json, numpy as np, cv2
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate",
                                   "-of", "json", src], capture_output=True, text=True, check=True).stdout)["streams"][0]
    # decoded (rotation applied) size from one frame
    probe = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    w, h = int(j["width"]), int(j["height"])
    if len(probe) != w * h: w, h = h, w
    fps = j["avg_frame_rate"]
    def frames(pix="bgr24"):
        p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", src, "-f", "rawvideo", "-pix_fmt", pix, "-"], stdout=subprocess.PIPE)
        n = w * h * (3 if pix == "bgr24" else 1)
        while True:
            b = p.stdout.read(n)
            if len(b) < n: break
            yield np.frombuffer(b, np.uint8).reshape((h, w, 3) if pix == "bgr24" else (h, w))
        p.wait()
    sc = 480 / min(w, h)
    moves, prev, pts = [], None, None
    for g in frames("gray"):
        g = cv2.resize(g, (int(w * sc), int(h * sc)))
        if prev is not None:
            pts = cv2.goodFeaturesToTrack(prev, 300, 0.01, 20, blockSize=3)
            m = None
            if pts is not None and len(pts) >= 8:
                nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, g, pts, None)
                ok = st.flatten() == 1
                if ok.sum() >= 8: m, _ = cv2.estimateAffinePartial2D(pts[ok], nxt[ok], method=cv2.RANSAC)
            if m is None: moves.append((0.0, 0.0, 0.0))
            else: moves.append((m[0, 2] / sc, m[1, 2] / sc, float(np.arctan2(m[1, 0], m[0, 0]))))
        prev = g
    moves = np.array([(0.0, 0.0, 0.0)] + moves)
    path = np.cumsum(moves, 0)
    if tripod: smooth = np.zeros_like(path)
    else:
        r = {1: 8, 2: 20, 3: 45}[strength]
        k = np.ones(2 * r + 1) / (2 * r + 1)
        pad = np.pad(path, ((r, r), (0, 0)), mode="edge")
        smooth = np.stack([np.convolve(pad[:, i], k, mode="valid") for i in range(3)], 1)
    fix = smooth - path
    zoom = 1 + {1: 0.03, 2: 0.05, 3: 0.08}[strength]
    enc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", fps, "-i", "-",
                            "-i", src, "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-shortest", out], stdin=subprocess.PIPE)
    for i, f in enumerate(frames()):
        dx, dy, da = fix[min(i, len(fix) - 1)]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), -np.degrees(da), zoom)   # OpenCV turns by -angle
        M[0, 2] += dx * zoom; M[1, 2] += dy * zoom
        enc.stdin.write(cv2.warpAffine(f, M, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT).tobytes())
    enc.stdin.close(); enc.wait()
    print(f"OpenCV stabilise, strength {strength}{', tripod' if tripod else ''}, zoom {round((zoom - 1) * 100)} % -> {out}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cv":
        cv_stabilize(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5] == "1")
    else:
        main()
