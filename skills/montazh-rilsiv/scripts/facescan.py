#!/usr/bin/env python3
"""Head pose and eyes on every 0.1 s of the raw clip, so takes.py can prefer the take where she looks into the lens.
Usage: python3 facescan.py <reel> [--fps 10]   -> <reel>/facescan.json rows [t, yaw, pitch, roll, eyeOpen, pupilDown]
macOS Vision (scripts/facescan.swift, compiled once to ~/.cache/reel-editor/facescan), local: no frame leaves the Mac.
About 1 min for a 3 min clip. No macOS/swift: exits 3 and takes.py works from the words alone.
Importable: load(reel) -> rows, badframes(rows, a, b) -> problem windows inside one take (the take-relative rules).
Rules adapted from ghost-editor (MIT, github.com/kurbaitaev/ghost-editor, references/take-selection.md rule 8):
blinks, quick glances and nods are part of talking and never count; only these do:
  turn   = head turned > 12 deg off the take's own median for >= 0.3 s (looking away)
  read   = pupils drop > 0.18 eye heights below the take's median for >= 0.3 s, eyes open (reading the script / phone)
  closed = eyes shut for >= 0.5 s
  noface = no face for >= 0.3 s (walked out of frame, camera moved)"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BIN = Path("~/.cache/reel-editor/facescan").expanduser()


def binary():
    src = HERE / "facescan.swift"
    if not BIN.exists() or BIN.stat().st_mtime < src.stat().st_mtime:
        BIN.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", "-o", str(BIN), str(src)], check=True, capture_output=True)
    return BIN


def load(reel):
    p = Path(reel).expanduser() / "facescan.json"
    return json.load(open(p)) if p.exists() else []


def _runs(ts, mask, minlen):
    out, k = [], 0
    while k < len(mask):
        if mask[k]:
            j = k
            while j + 1 < len(mask) and mask[j + 1]: j += 1
            if j - k + 1 >= minlen: out.append((ts[k], ts[j]))
            k = j + 1
        else: k += 1
    return out


def badframes(rows, a, b, step=0.1):
    """problem windows [(t0, t1, kind)] between a and b (source seconds), against the take's own median pose"""
    R = [r for r in rows if a - 0.05 <= r[0] <= b + 0.05]
    if len(R) < 3: return []
    ts = [r[0] for r in R]
    face = [r for r in R if r[1] is not None]
    if not face: return [(round(a, 2), round(b, 2), "noface")]
    med = lambda k: sorted(r[k] for r in face)[len(face) // 2]
    yaw, opn, dwn = med(1), med(4), med(5)
    n3, n5 = max(2, round(0.3 / step)), max(3, round(0.5 / step))
    closed = [r[1] is not None and r[4] >= 0 and opn > 0 and r[4] < 0.5 * opn for r in R]
    ev = []
    ev += [(x, y, "noface") for x, y in _runs(ts, [r[1] is None for r in R], n3)]
    ev += [(x, y, "turn") for x, y in _runs(ts, [r[1] is not None and abs(r[1] - yaw) > 12 for r in R], n3)]
    ev += [(x, y, "read") for x, y in _runs(ts, [r[1] is not None and r[5] > -1 and r[5] - dwn > 0.18 and not c for r, c in zip(R, closed)], n3)]
    ev += [(x, y, "closed") for x, y in _runs(ts, closed, n5)]
    return sorted((round(x, 2), round(y + step, 2), k) for x, y, k in ev)


def main():
    reel = Path(sys.argv[1]).expanduser()
    fps = float(sys.argv[sys.argv.index("--fps") + 1]) if "--fps" in sys.argv else 10.0
    src = next(iter(sorted(reel.glob("raw.*"))), None)
    if not src: sys.exit(f"no raw.* in {reel}")
    try:
        exe = binary()
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"facescan unavailable (needs macOS with swiftc): {e}"); sys.exit(3)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-an", "-vf", f"fps={fps},scale=540:-2",
                        "-q:v", "4", f"{d}/f%06d.jpg"], check=True)
        frames = sorted(Path(d).glob("f*.jpg"))
        out = subprocess.run([str(exe)], input="\n".join(map(str, frames)) + "\n", capture_output=True, text=True, check=True).stdout.split("\n")
    rows = []
    for i, line in enumerate(out[:len(frames)]):
        t = round(i / fps, 3)
        v = line.split()
        rows.append([t] + ([float(x) for x in v] if len(v) == 5 else [None] * 5))
    json.dump(rows, open(reel / "facescan.json", "w"))
    seen = sum(1 for r in rows if r[1] is not None)
    print(f"{len(rows)} frames, face on {seen} ({100 * seen // max(1, len(rows))}%) -> {reel / 'facescan.json'}")


if __name__ == "__main__":
    main()
