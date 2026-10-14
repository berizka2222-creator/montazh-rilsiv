#!/usr/bin/env python3
"""Cut one recording (video or audio: sound, silence, sound, silence...) into separate sound effects.
Usage: python3 slice_sfx.py <video-or-audio> [names.txt] [--prefix my_] [--gap 0.35] [--floor -45]
Each sound -> ~/reels/assets/sfx/<prefix><name>.wav (48 kHz stereo, 15 ms pre-roll, faded tail, peak -3 dBFS).
names.txt: one name per line in the order the sounds play («клік мишки» etc.); without it they are numbered.
Prints every sound with its start time in the recording, so a missing or merged one is easy to spot."""
import argparse, json, os, re, subprocess
ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("names", nargs="?")
ap.add_argument("--prefix", default="my_"); ap.add_argument("--gap", type=float, default=0.35); ap.add_argument("--floor", type=float, default=-45)
a = ap.parse_args()
out = os.path.expanduser("~/reels/assets/sfx"); os.makedirs(out, exist_ok=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.src], capture_output=True, text=True).stdout)
log = subprocess.run(["ffmpeg", "-i", a.src, "-vn", "-af", f"silencedetect=noise={a.floor}dB:d={a.gap}", "-f", "null", "-"], capture_output=True, text=True).stderr
ss = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]; se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
# sounds are the gaps between silences
edges, t = [], 0.0
for s, e in zip(ss, se + [dur] * (len(ss) - len(se))):
    if s - t > 0.03: edges.append((t, s))
    t = e
if dur - t > 0.03: edges.append((t, dur))
names = [l.strip() for l in open(a.names, encoding="utf-8")] if a.names else []
names = [n for n in names if n]
slug = lambda s: re.sub(r"[^\w]+", "_", s.lower()).strip("_") or "sound"
made = []
for k, (s, e) in enumerate(edges, 1):
    nm = slug(names[k - 1]) if k <= len(names) else f"{k:02d}"
    f = f"{out}/{a.prefix}{nm}.wav"; s0 = max(0, s - 0.015); ln = e - s0 + 0.05
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s0:.3f}", "-t", f"{ln:.3f}", "-i", a.src, "-vn", "-af",
                    f"afade=t=out:st={max(0, ln - 0.06):.3f}:d=0.06", "-ar", "48000", "-ac", "2", f + ".raw.wav"], check=True)
    pk = float(re.search(r"max_volume: (-?[\d.]+)", subprocess.run(["ffmpeg", "-i", f + ".raw.wav", "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr).group(1))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f + ".raw.wav", "-af", f"volume={-3 - pk:.2f}dB", f], check=True); os.remove(f + ".raw.wav")
    made.append({"name": a.prefix + nm, "label": names[k - 1] if k <= len(names) else f"Звук {k}", "from": round(s, 2), "dur": round(e - s, 2)})
    print(f"{k:2d}. {a.prefix + nm:28s} at {s:7.2f}s  {e - s:5.2f}s")
if names and len(names) != len(edges): print(f"WARNING: {len(names)} names but {len(edges)} sounds found: check the list above (try --gap or --floor)")
json.dump(made, open(f"{out}/my_sounds_last_cut.json", "w"), ensure_ascii=False, indent=1)
