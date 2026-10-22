#!/usr/bin/env python3
"""Options for one «Знайти» request on the review page: 10-15 pictures / GIFs / videos / meme templates she picks from.

  find_options.py <reel> <request id> photo|gif|video|meme "<english query>" ["<another angle>" ...] [-n 12]

She wrote the meaning (an emotion, a state, a vibe) in Ukrainian; turn it into 2-3 short English queries (stock libraries
index English tags) that SHOW that meaning, e.g. «паніка, коли клієнт пише дорого» -> "panic" "shocked face" "stressed woman phone".
Runs scripts/find_media.py for each query into <reel>/finds/<request id>/, then makes light previews for the page
(pv/<n>.jpg 480 px, or pv/<n>.mp4 360 px <= 4 s + pv/<n>.jpg poster) and writes finds/<request id>/options.json.
Upload the pv/ files (Artifact asset: true, file_paths), then write reel/current "finds": {<request id>: [{id: <asset id>,
url, poster?, kind: "image"|"video", label, source, license, file}]}. Never pick for her: every option goes on the page.
Memes: the options are templates; she picks one and types HER text on the page (finds[i].memeText), then
find_media.py meme --id <template> --text "<her text>" --into <request id> makes the picture that goes in."""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
args = sys.argv[1:]
n = int(args[args.index("-n") + 1]) if "-n" in args else 12
if "-n" in args: i = args.index("-n"); args = args[:i] + args[i + 2:]
if len(args) < 4: sys.exit(__doc__)
reel, rid, kind, queries = Path(args[0]).expanduser(), args[1], args[2], args[3:]
d = reel / "finds" / rid; d.mkdir(parents=True, exist_ok=True)
per = max(2, -(-n // len(queries)))   # ceil
for q in queries:
    subprocess.run([sys.executable, str(HERE / "find_media.py"), str(reel), kind, q, "-n", str(per), "--into", rid])
log = d / "finds.json"
found = json.load(open(log)) if log.exists() else []
seen, opts = set(), []
pv = d / "pv"; pv.mkdir(exist_ok=True)
for f in found:
    src = reel / f["file"]
    if not src.exists() or src.name in seen or "-caption" in src.name: continue
    seen.add(src.name); k = len(opts) + 1
    if src.suffix.lower() == ".mp4":
        prev, poster = pv / f"{k}.mp4", pv / f"{k}.jpg"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-t", "4", "-vf", "scale=360:-2", "-an", "-c:v", "libx264", "-crf", "28",
                        "-preset", "veryfast", "-movflags", "+faststart", str(prev)])
        for ss in ("0.5", "0"):   # very short GIFs have no frame at 0.5 s
            subprocess.run(["ffmpeg", "-nostdin", "-v", "quiet", "-y", "-ss", ss, "-i", str(src), "-frames:v", "1", "-vf", "scale=360:-2", str(poster)])
            if poster.exists() and poster.stat().st_size: break
        opts.append({"n": k, "kind": "video", "file": f["file"], "preview": str(prev.relative_to(reel)), "poster": str(poster.relative_to(reel)),
                     "label": f.get("name") or f.get("query", ""), "source": f.get("source"), "license": f.get("license")})
    else:
        prev = pv / f"{k}.jpg"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-vf", "scale=480:-2", "-q:v", "4", str(prev)])
        opts.append({"n": k, "kind": "image", "file": f["file"], "preview": str(prev.relative_to(reel)),
                     "label": f.get("name") or f.get("query", ""), "source": f.get("source"), "license": f.get("license"), **({"template": f["id"]} if f.get("id") else {})})
    if len(opts) >= n: break
json.dump(opts, open(d / "options.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(opts)} options -> {d / 'options.json'}; upload:")
for o in opts: print(reel / o["preview"], *( [reel / o["poster"]] if o.get("poster") else []))
