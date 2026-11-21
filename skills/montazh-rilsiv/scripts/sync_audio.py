#!/usr/bin/env python3
"""Put the sound from a separate mic (lav, recorder, a second phone) under the camera picture, in sync.
Approach from ffmpeg-skill's sync.py (MIT, github.com/kajisho5/ffmpeg-skill): both tracks to mono 8 kHz, loudness
envelopes cross-correlated (10 ms), then refined on the waveform (1 ms); clock drift measured at the start and the end.

    python3 sync_audio.py <camera video> <mic audio> [-o out.mov] [--max-offset 120] [--check]
  --check   only measure: prints the offset (+ = the mic started later than the camera), the drift and the confidence
  default   writes the camera picture (stream copy, untouched) with the mic sound aligned under it, as long as the picture;
            in a reel folder: keep the camera file as raw-camera.<ext> and write raw.mov, then transcribe / clean_audio as usual.
A low confidence (< 4) means the two recordings may not share the same moment: say so and don't use the result.
This aligns sound to sound; it can't see lips. Watch a few seconds with clear «п / б / м» before going on."""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
VENV = next((v for v in (HOME / ".venv" / "bin" / "python", HOME / ".venv" / "Scripts" / "python.exe") if v.exists()), HOME / ".venv" / "bin" / "python")
try:
    import numpy as np
except ImportError:
    if VENV.exists() and Path(sys.prefix).resolve() != (HOME / ".venv").resolve():
        os.execv(str(VENV), [str(VENV), *sys.argv])
    sys.exit("needs numpy: ~/reels/.venv/bin/pip install numpy (Windows: ~/reels/.venv/Scripts/pip install numpy)")

SR = 8000


def pcm(path, start=None, dur=None):
    cmd = ["ffmpeg", "-nostdin", "-v", "error"] + (["-ss", f"{start:.3f}"] if start else []) + ["-i", str(path)] + \
          (["-t", f"{dur:.3f}"] if dur else []) + ["-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768


def env(x, hop=80):          # 10 ms loudness envelope, onsets emphasised
    n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1) + 1e-9)
    e = np.log(e); d = np.maximum(0, np.diff(e, prepend=e[0]))
    return (d - d.mean()) / (d.std() + 1e-9)


def xcorr_lag(a, b, maxlag):
    """lag (samples) at which b best matches a: b[t] ~ a[t + lag]; + = b starts later. Returns (lag, peak/median)"""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    c = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    c = np.concatenate([c[-(len(b) - 1):], c[:len(a)]])        # lags -(len(b)-1) .. len(a)-1
    lags = np.arange(-(len(b) - 1), len(a))
    m = np.abs(lags) <= maxlag
    c, lags = c[m], lags[m]
    k = int(np.argmax(c))
    conf = float(c[k] / (np.median(np.abs(c)) + 1e-9))
    return int(lags[k]), conf


def measure(cam, mic, cs, cd, ms, md, maxlag):
    """d (seconds) with mic time = camera time + d, from camera cs..cs+cd against mic ms..ms+md; + confidence"""
    a, b = env(pcm(cam, cs, cd)), env(pcm(mic, ms, md))
    k, conf = xcorr_lag(a, b, int(maxlag * 100))        # camera local tau <-> mic local tau - k (10 ms steps)
    d = ms - cs - k / 100.0
    # refine on the waveform: +-30 ms in 1 ms steps over up to 20 s
    L = min(cd or 20, 20)
    A = pcm(cam, cs, L)
    B = pcm(mic, max(0.0, cs + d - 0.05), L + 0.1)
    b0 = max(0.0, cs + d - 0.05)
    best, bd = -1e18, d
    for j in range(-30, 31):
        dd = d + j / 1000
        o = int(round((cs + dd - b0) * SR))
        if o < 0: continue
        n = min(len(A), len(B) - o)
        if n < SR: continue
        v = float(np.dot(A[:n], B[o:o + n]))
        if v > best: best, bd = v, dd
    return bd, conf


def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True, check=True).stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("mic"); ap.add_argument("-o"); ap.add_argument("--max-offset", type=float, default=120)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    D = dur(a.video)
    Dm = dur(a.mic)
    d0, c0 = measure(a.video, a.mic, 0.0, min(D, 90), 0.0, Dm, a.max_offset + min(D, 90))
    drift = 0.0
    if D > 90 and c0 >= 4:                             # long take: measure again near the end, the clocks may drift
        cs = D - 60
        ms = max(0.0, cs + d0 - 5)
        d1, c1 = measure(a.video, a.mic, cs, 60, ms, 70, 6)
        if c1 >= 4 and abs(d1 - d0) < 0.5: drift = (d1 - d0) / cs      # mic = camera * (1 + drift) + d0
    print(json.dumps({"mic_second_at_camera_start": round(d0, 3),
                      "meaning": (f"the mic started {d0:.3f} s before the camera: its first {d0:.3f} s are dropped") if d0 >= 0
                      else (f"the mic started {-d0:.3f} s after the camera: it is delayed by {-d0:.3f} s"),
                      "drift_ms_per_min": round(drift * 60000, 1), "confidence": round(c0, 1)}, ensure_ascii=False))
    if c0 < 4: print("LOW CONFIDENCE: these two may not be the same moment; don't use the result")
    if a.check: return
    out = Path(a.o or Path(a.video).with_name(Path(a.video).stem + "-synced.mov")).expanduser()
    af = []
    if d0 > 0: af.append(f"atrim=start={d0:.4f},asetpts=PTS-STARTPTS")
    elif d0 < 0: af.append(f"adelay={int(round(-d0 * 1000))}:all=1")
    if abs(drift) > 1e-5: af.append(f"atempo={1 + drift:.6f}")
    af.append(f"apad,atrim=end={D:.3f}")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", a.video, "-i", a.mic, "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy", "-af", ",".join(af), "-c:a", "pcm_s24le" if out.suffix.lower() == ".mov" else "aac", "-b:a", "256k",
                    "-map_metadata", "0", str(out)], check=True)
    print(f"-> {out}  (camera picture untouched, mic sound under it)")


if __name__ == "__main__":
    main()
