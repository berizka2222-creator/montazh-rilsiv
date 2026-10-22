#!/usr/bin/env python3
"""«Мої стилі» examples that show how the styles differ: ~10 s on their own video (hook, camera move, the style's own graphic,
then several seconds of captions in that style), one per saved style. Made ONCE per person (like the effect previews) and
reused on every reel; run it again only after a style changes.

  style_examples.py [--secs 10] [--only kinetic,editorial]

Takes the source, hook and graphic of the style lab fragment (styles/_lab/fragment/fragment.json: their own approved hook),
cuts a longer piece of the same clip into styles/_lab/example, renders each saved style with the card recipe of its
direction (style_lab.directions), and prints the files to upload. Then map the urls into styles/list.json (url, posterUrl)
and the page's db style/list."""
import json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import style_lab as L

DIRECTION = {"quiet-bigger": "quiet"}   # saved style name -> its round-1 direction (same name otherwise; quiet-bigger = old name of quiet)
args = sys.argv[1:]
secs = float(args[args.index("--secs") + 1]) if "--secs" in args else 10.0
only = args[args.index("--only") + 1].split(",") if "--only" in args else None

lab = json.load(open(L.FRAG / "fragment.json"))
L.FRAG = L.LAB / "example"                     # never touch the lab fragment the rounds use
src = Path(lab["src"])
if not (L.FRAG / "fragment.json").exists() or json.load(open(L.FRAG / "fragment.json")).get("dur") != round(secs, 2):
    L.fragment(src, lab["start"], lab["start"] + secs, lab["hook"])
ex = json.load(open(L.FRAG / "fragment.json"))
g = dict(lab.get("graphic") or {}); g["end"] = round(min(secs - 3.0, max(g.get("end", 4.8), (g.get("start") or 3.2) + 2.6)), 2)   # graphic, then ~3+ s of captions
ex.update({"graphic": g, "transition_at": lab.get("transition_at"), "accents": lab.get("accents", []), "hook": lab["hook"]})
json.dump(ex, open(L.FRAG / "fragment.json", "w"), ensure_ascii=False, indent=1)

saved = [p.stem for p in sorted(L.STYLES.glob("*.json")) if p.stem != "list"]
if only: saved = [s for s in saved if s in only]
L.directions("examples", [DIRECTION.get(s, s) for s in saved])
spec_path = L.LAB / "examples.json"; spec = json.load(open(spec_path))
by_dir = {v["id"]: v for v in spec["sections"][0]["variants"]}
variants = []
for s in saved:
    v = by_dir.get(DIRECTION.get(s, s))
    if not v: print(f"skip {s}: no direction recipe"); continue
    st = json.load(open(L.STYLES / f"{s}.json"))
    for k in ("locked", "rejected", "maybe", "sample", "name"): st.pop(k, None)
    cards = v["cards"]
    if st.get("signature") == "bigwords":   # kinetic: huge words over the person, line by line, with a jolt, instead of a panel
        rows, rt = g.get("rows", []), g.get("row_times") or []
        cards = [c for c in cards if c.get("type") != "push"] + [
            {"type": "bigtext", "text": " / ".join(rows), "y": 400, "size": 128, "color": "#FFFFFF", "start": g.get("start", 3.2), "end": g["end"]}] + [
            {"type": "camera", "move": "shake", "start": t} for t in rt]
    variants.append({**v, "id": s, "title": st.get("title", v["title"]), "what": st.get("what", v["what"]), "style": st, "cards": cards})
spec["sections"][0]["variants"] = variants
spec["title"], spec["lede"] = "Приклади стилів", "Кожен стиль на тих самих 10 секундах."
json.dump(spec, open(spec_path, "w"), ensure_ascii=False, indent=1)
L.run_round(spec_path)
out = L.ROUNDS / "examples"
for v in variants:   # poster on the style's own graphic, not on the hook every style shares
    L.sh(["ffmpeg", "-v", "error", "-y", "-ss", str(round((g.get("start", 3.2) + g["end"]) / 2, 2)), "-i", str(out / f"dir.{v['id']}.mp4"),
          "-frames:v", "1", "-vf", "scale=270:480", "-q:v", "4", str(out / f"dir.{v['id']}.jpg")])
print("examples:", ", ".join(v["id"] for v in variants))
