#!/usr/bin/env python3
"""Instagram Reels safe zones on a 1080x1920 frame (keep in sync with review/core.js SAFE).
build_reel.py records where every graphic and caption sits and calls check(); the result goes to <reel>/safezones.json,
which qa.py prints. Warnings only: a full-screen takeover is meant to cover everything.
Usage: python3 safezones.py <reel-folder>     print the last check"""
import json, re, sys
from pathlib import Path

COVERED = [("top", (0, 0, 1080, 220), "верхня панель Reels"),
           ("bottom", (0, 1500, 1080, 420), "нік, підпис, музика"),
           ("buttons", (950, 1000, 130, 500), "кнопки праворуч")]
CROP = [(0, 0, 60, 1920), (1020, 0, 60, 1920)]       # cut off at the sides on taller phones
SAFE = (60, 220, 960, 1280)


def overlap(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    return max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))


def check(items):
    """items: [{id, kind, start, end, box: [x,y,w,h], text: bool, full: bool}]. Returns warnings (dicts)."""
    out = []
    for it in items:
        if it.get("full"): continue                      # full-screen panels are backgrounds; their text is checked on its own box
        box, area = it["box"], max(1, it["box"][2] * it["box"][3])
        for zid, z, label in COVERED:
            o = overlap(box, z)
            # text: any real overlap matters; pictures may bleed a little under the UI
            if o and (o / area > (0.06 if it.get("text") else 0.2)):
                out.append({**{k: it[k] for k in ("id", "kind", "start", "end")}, "zone": zid,
                            "msg": f"{it['kind']} {it['start']:.1f}-{it['end']:.1f}s заходить під {label} ({o / area:.0%})"})
        if it.get("text") and any(overlap(box, c) / area > 0.02 for c in CROP):
            out.append({**{k: it[k] for k in ("id", "kind", "start", "end")}, "zone": "sides",
                        "msg": f"{it['kind']} {it['start']:.1f}-{it['end']:.1f}s текст біля краю, на довгих екранах обріжеться"})
    return out


def merge(warns):
    """Back-to-back captions with the same problem become one warning."""
    out = []
    for w in warns:
        o = out[-1] if out else None
        if o and o["kind"] == w["kind"] == "субтитри" and o["zone"] == w["zone"] and w["start"] - o["end"] < 1.0:
            o["end"] = w["end"]; o["msg"] = re.sub(r"\d+\.\d-\d+\.\ds", f"{o['start']:.1f}-{o['end']:.1f}s", o["msg"], 1)
        else: out.append(dict(w))
    return out


def save(reel, items):
    warns = merge(check(items))
    json.dump({"items": items, "warnings": warns}, open(Path(reel) / "safezones.json", "w"), ensure_ascii=False, indent=1)
    for w in warns: print("safe zone:", w["msg"])
    return warns


if __name__ == "__main__":
    f = Path(sys.argv[1]).expanduser() / "safezones.json"
    if not f.exists(): sys.exit("no safezones.json yet: run build_reel.py first")
    ws = json.load(open(f))["warnings"]
    print("\n".join(w["msg"] for w in ws) or "safe zones: усе в безпечній зоні")
