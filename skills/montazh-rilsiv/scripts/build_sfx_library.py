#!/usr/bin/env python3
"""Builds the CC0 sound library in ~/reels/assets/sfx (wav, peak -3 dBFS, 48 kHz) + library.json.
Usage: python3 build_sfx_library.py <unzipped Kenney packs dir> references/sfx_library.tsv
Kenney packs (CC0): interface-sounds, ui-audio, impact-sounds, digital-audio, casino-audio from kenney.nl.
Rows: name, source (pack path | synth:<lavfi> || <filters> | seq:file@sec,...), label, category."""
import subprocess, re, sys, os, csv, json
D, L, LIST = sys.argv[1], os.path.expanduser("~/reels/assets/sfx"), sys.argv[2]
os.makedirs(L, exist_ok=True)
def run(*a): subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
def peak(f):
    o = subprocess.run(["ffmpeg", "-i", f, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.search(r"max_volume: (-?[\d.]+) dB", o).group(1))
def norm(src, dst, target=-3.0):
    tmp = dst + ".tmp.wav"; os.replace(src, tmp) if src == dst else None
    s = tmp if src == dst else src
    g = target - peak(s); run("-i", s, "-af", f"volume={g:.2f}dB", "-ar", "48000", "-ac", "2", dst)
    if src == dst: os.remove(tmp)
meta = []
for row in csv.reader(open(LIST), delimiter="\t"):
    if not row or row[0].startswith("#"): continue
    name, src, label, cat = row
    out = f"{L}/{name}.wav"
    if src.startswith("synth:"):
        spec = src[6:]; inp, af = spec.split(" || ") if " || " in spec else (spec, "anull")
        run("-f", "lavfi", "-i", inp, "-af", af, "-ar", "48000", "-ac", "2", out + ".raw.wav")
        norm(out + ".raw.wav", out); os.remove(out + ".raw.wav"); lic = "CC0 (made for this library)"
    elif src.startswith("seq:"):   # keyboard: several Kenney clicks in a row
        parts = src[4:].split(","); inputs = []; fl = []
        for k, p in enumerate(parts):
            f, t = p.split("@"); inputs += ["-i", os.path.join(D, f)]; fl.append(f"[{k}]adelay={int(float(t)*1000)}|{int(float(t)*1000)},aresample=48000[a{k}]")
        run(*inputs, "-filter_complex", ";".join(fl) + ";" + "".join(f"[a{k}]" for k in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0[o]", "-map", "[o]", "-ac", "2", out + ".raw.wav")
        norm(out + ".raw.wav", out); os.remove(out + ".raw.wav"); lic = "CC0 (Kenney.nl, arranged)"
    else:
        run("-i", os.path.join(D, src), "-af", "silenceremove=start_periods=1:start_threshold=-55dB", "-ar", "48000", "-ac", "2", out + ".raw.wav")
        norm(out + ".raw.wav", out); os.remove(out + ".raw.wav"); lic = "CC0 (Kenney.nl)"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout)
    meta.append({"name": name, "label": label, "cat": cat, "dur": round(dur, 2), "license": lic})
json.dump(meta, open(f"{L}/library.json", "w"), ensure_ascii=False, indent=1)
print(len(meta), "sounds")
