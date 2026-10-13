#!/usr/bin/env python3
"""Move every join in edl.json into the quietest moment nearby, so no cut lands inside a word.
Transcript word times are never exact; the gap between two words is where the voice actually drops.
Usage: python3 snap_joins.py <reel-folder> [--window 0.3]
Run after edl.json exists (review_sync import or a hand-written edl) and before cut.py."""
import array, json, math, subprocess, sys, tempfile, wave
from pathlib import Path

reel = Path(sys.argv[1]).expanduser()
WIN = float(sys.argv[sys.argv.index("--window") + 1]) if "--window" in sys.argv else 0.3
edl = json.load(open(reel / "edl.json"))
audio = reel / edl.get("audio", "voice.wav")

with tempfile.TemporaryDirectory() as tmp:
    wav = Path(tmp) / "a.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(audio), "-ac", "1", "-ar", "16000", str(wav)], check=True)
    w = wave.open(str(wav)); sr = w.getframerate(); pcm = array.array("h"); pcm.frombytes(w.readframes(w.getnframes()))
dur = len(pcm) / sr

def db(t, n=0.03):   # level of the n seconds starting at t
    s = pcm[max(0, int(t * sr)):int((t + n) * sr)] or [0]
    return 20 * math.log10(max(1.0, math.sqrt(sum(x * x for x in s) / len(s))) / 32768)

def quietest(t):
    """The quiet moment nearest t: among points within 6 dB of the quietest in the window, the closest one.
    (The single quietest point can sit in a short dip inside the next word, past the real gap.)"""
    pts = [(db(t + k * 0.01 - 0.015), t + k * 0.01) for k in range(int(-WIN * 100), int(WIN * 100) + 1) if 0 < t + k * 0.01 < dur]
    floor = min(p[0] for p in pts)
    lv, nt = min((p for p in pts if p[0] <= floor + 6), key=lambda p: abs(p[1] - t))
    return round(nt, 3), lv, db(t - 0.015)

keep, moved = [list(s) for s in edl["keep"]], []
for i, (a, b) in enumerate(keep):
    if i > 0 and a > 0.05:                               # start of a span: begin in the silence before its first word
        na, lv, was = quietest(a)
        if na != a: moved.append(f"span {i} start {a:.2f} -> {na:.2f} ({was:.0f} -> {lv:.0f} dB)"); keep[i][0] = na
    if i < len(keep) - 1 or b < dur - 0.05:              # end of a span: stop in the silence after its last word
        nb, lv, was = quietest(b)
        if nb != b: moved.append(f"span {i} end {b:.2f} -> {nb:.2f} ({was:.0f} -> {lv:.0f} dB)"); keep[i][1] = nb
    if keep[i][1] - keep[i][0] < 0.2: sys.exit(f"span {i} collapsed after snapping ({keep[i]}): check edl.json by hand")
edl["keep"] = keep
json.dump(edl, open(reel / "edl.json", "w"))
print("\n".join(moved) or "joins already sit in quiet gaps")
