#!/usr/bin/env python3
"""Level a tilted clip (b-roll shot at an angle): turn it by a small angle and zoom just enough that no corner shows.
After ffmpeg-skill's straighten.py (MIT, github.com/kajisho5/ffmpeg-skill); added: --auto measures the tilt with
macOS Vision (VNDetectHorizonRequest, on the Mac) on 8 frames.

    python3 straighten.py <in> <out.mp4> --auto            # Vision finds the horizon; refuses when it sees none
    python3 straighten.py <in> <out.mp4> --degrees -2.5    # by hand: + turns the picture clockwise
    python3 straighten.py <in> --measure                   # only print what Vision sees per frame
The zoom for a 2 deg turn on a 9:16 clip is ~6 %: keep turns under ~5 deg, beyond that the crop eats the shot.
A talking head is never straightened by --auto (a face is not a horizon): only by hand, if she asks. Audio is copied."""
import argparse, json, math, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def swift_tool(name):
    src, exe = HERE / f"{name}.swift", Path(f"~/.cache/reel-editor/{name}").expanduser()
    if not exe.exists() or exe.stat().st_mtime < src.stat().st_mtime:
        exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", "-o", str(exe), str(src)], check=True, capture_output=True)
    return exe


def info(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", str(p)],
                                  capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]; w, h = int(s["width"]), int(s["height"])
    rot = next((int(x["rotation"]) for x in s.get("side_data_list", []) or [] if "rotation" in x), 0)
    if rot in (90, -90, 270, -270): w, h = h, w
    return w, h, float(j["format"]["duration"])


def measure(p):
    w, h, d = info(p)
    with tempfile.TemporaryDirectory() as t:
        fs = []
        for k in range(8):
            f = f"{t}/{k}.jpg"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{d * (k + .5) / 8:.2f}", "-i", str(p), "-frames:v", "1", "-vf", "scale=720:-2", f])
            fs.append(f)
        out = subprocess.run([str(swift_tool("horizon"))], input="\n".join(fs) + "\n", capture_output=True, text=True).stdout.split()
    return [float(x) for x in out if x != "none"], len(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input"); ap.add_argument("out", nargs="?"); ap.add_argument("--degrees", type=float)
    ap.add_argument("--auto", action="store_true"); ap.add_argument("--measure", action="store_true")
    a = ap.parse_args()
    if a.measure or a.auto:
        v, n = measure(a.input)
        print(f"horizon on {len(v)}/{n} frames: {v}")
        if a.measure: return
        if len(v) < 3: sys.exit("Vision sees no clear horizon here: give --degrees by eye (or leave the clip as it is)")
        v.sort(); deg = -v[len(v) // 2]            # Vision + = tilted clockwise: turn back counter-clockwise
        if abs(deg) < 0.4: print(f"tilt {deg:.2f} deg: already level, nothing to do"); return
    else:
        if a.degrees is None: sys.exit("give --auto or --degrees")
        deg = a.degrees
    if abs(deg) > 8: sys.exit(f"{deg:.1f} deg is too much to fix by turning (the crop would eat the shot)")
    if not a.out: sys.exit("give an output file")
    w, h, _ = info(a.input)
    th = math.radians(abs(deg))
    k = max(math.cos(th) + h / w * math.sin(th), math.cos(th) + w / h * math.sin(th))
    sw, sh = math.ceil(w * k / 2) * 2, math.ceil(h * k / 2) * 2
    vf = f"scale={sw}:{sh}:flags=lanczos,rotate={deg}*PI/180:ow={w}:oh={h}:c=black,format=yuv420p"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", a.input, "-vf", vf, "-c:v", "libx264", "-crf", "16",
                    "-preset", "medium", "-c:a", "copy", a.out], check=True)
    print(f"turned {deg:+.2f} deg, zoom {100 * (k - 1):.1f} % -> {a.out}")


if __name__ == "__main__":
    main()
