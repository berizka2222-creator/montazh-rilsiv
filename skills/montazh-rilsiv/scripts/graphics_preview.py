#!/usr/bin/env python3
"""Step 2 video WITH the graphics (2026-10-24: the person sees the finished look, not boxes).
After Claude's proposals are on the board: import her decisions, cut (cached when nothing changed), render a 540p draft with
every graphic and the captions, and print the db doc for builds/<id>-cut. The page then plays this video on «Графіка» and
draws only what isn't in the picture yet; she removes or adds on the timeline, then «Зібрати чернетку».
Usage: graphics_preview.py <reel> <review.json>     -> <reel>/gfx_preview.mp4 + <reel>/gfx_preview.json (the db doc)
A hook with no text yet (she hasn't picked A/B/C) stays out of the picture: the page draws it live."""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
S = Path(__file__).resolve().parent
reel, review = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser()
run = lambda *a, **k: subprocess.run([*a], check=True, **k)
run(sys.executable, str(S / "review_sync.py"), "import", str(reel), str(review))
run(sys.executable, str(S / "snap_joins.py"), str(reel))
run(sys.executable, str(S / "cut.py"), str(reel), env={**os.environ, "REEL_PREVIEW": "1"})
d = json.load(open(review)); d = d.get("data", d)
e = json.load(open(reel / "edit.json"))
if not (d.get("hook") or "").strip():   # placeholder hook: not baked, the page shows her pick live
    e["cards"] = [c for c in e["cards"] if not (c["type"] == "title" and c.get("id") == "hook")]
    json.dump(e, open(reel / "edit.json", "w"), ensure_ascii=False, indent=1)
run(sys.executable, str(S / "precheck.py"), str(reel))
run("bash", str(S / "render.sh"), str(reel), env={**os.environ, "REEL_DRAFT": "1", "REEL_PREVIEW": "1"})
shutil.copy(reel / "draft.mp4", reel / "gfx_preview.mp4")
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(reel / "gfx_preview.mp4")], capture_output=True, text=True).stdout)
doc = {"url": "<upload gfx_preview.mp4, put its /_blob/ url here>", "cutHash": (d.get("graphicsRequest") or {}).get("cutHash"),
       "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cutDur": round(dur, 2), "rendered": True,
       "ids": [c["id"] for c in e["cards"] if c.get("id")], "hash": e.get("hash")}
json.dump(doc, open(reel / "gfx_preview.json", "w"), ensure_ascii=False, indent=1)
print("graphics preview:", reel / "gfx_preview.mp4", f"({dur:.1f}s, {len(doc['ids'])} graphics baked)")
print("next: upload it (asset: true), set doc url, ArtifactData set builds/<id>-cut from", reel / "gfx_preview.json")
