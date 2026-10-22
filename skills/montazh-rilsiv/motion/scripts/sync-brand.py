#!/usr/bin/env python3
"""The person's brand -> this Remotion project. Reads <REELS_HOME>/brand.json (colours, fonts), copies the font files into
public/fonts and their own 3D / sticker elements (<REELS_HOME>/assets/chrome/*.png|webp) into public/chrome, and writes
src/lib/brand.generated.json, which src/lib/brand.ts and fonts.ts read. Every render script runs it first, so a change in
brand.json shows up in the next render. Safe to run any time."""
import colorsys, json, os, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
bp = HOME / "brand.json"
if not bp.exists():
    print(f"sync-brand: no {bp} yet, keeping the neutral defaults"); sys.exit(0)
b = json.load(open(bp)); col = b.get("colors", {})

def rgb(h):
    h = h.lstrip("#"); h = "".join(c * 2 for c in h) if len(h) == 3 else h[:6]
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
def hexc(t): return "#" + "".join(f"{round(max(0, min(1, v)) * 255):02X}" for v in t)
def mix(a, c, t): return hexc(tuple(x + (y - x) * t for x, y in zip(rgb(a), rgb(c))))
def lum(h): r, g, bb = rgb(h); return 0.2126 * r + 0.7152 * g + 0.0722 * bb
def rgba(h, a): r, g, bb = (round(v * 255) for v in rgb(h)); return f"rgba({r},{g},{bb},{a})"

main = col.get("main", "#111111")
deep = col.get("deep") or mix(main, "#000000", .35)
light = col.get("light") or col.get("caption") or "#F5F5F0"
dark_bg = lum(main) < .45                          # most brands: dark panels, light text
acc1 = col.get("pop") or col.get("caption_accent") or "#FFD24C"     # labels, buttons, the counted number ("lime" role)
acc2 = col.get("soft") or col.get("caption_accent_2") or mix(acc1, light, .5)   # italic accent words, strike-through ("pink" role)
if acc2.lower() == acc1.lower(): acc2 = mix(acc1, light, .45)
base = col.get("bg") or main
C = {
    "c0": mix(deep, "#000000", .3) if dark_bg else mix(base, "#FFFFFF", .5),
    "c1": base,
    "c2": mix(base, light, .04) if dark_bg else mix(base, "#000000", .03),
    "c3": mix(base, light, .08) if dark_bg else mix(base, "#000000", .06),
    "main": main, "deep": deep,
    "lime": acc1, "limeHi": mix(acc1, "#FFFFFF", .3),
    "pink": acc2, "pinkDk": mix(acc2, "#000000", .45),
    "cream": light if lum(light) > .7 else "#F1F0E7",
    "ink": min((deep, main, "#141414"), key=lum),   # text on the accent colours and on cream
    "tx": light if dark_bg else min([v for v in col.values() if isinstance(v, str) and v.startswith("#")] + ["#161616"], key=lum),
}
if not dark_bg and lum(C["tx"]) > .3: C["tx"] = "#161616"   # text on a light brand must stay dark enough to read
C["tx2"] = rgba(C["tx"], .66); C["tx3"] = rgba(C["tx"], .42)
C["bd"] = "rgba(255,255,255,.1)" if dark_bg else "rgba(0,0,0,.1)"
C["bd2"] = "rgba(255,255,255,.2)" if dark_bg else "rgba(0,0,0,.2)"

# fonts: every file of the brand's head / body / accent families in <REELS_HOME>/fonts (plus the exact files brand.json names)
fd = ROOT / "public" / "fonts"; fd.mkdir(parents=True, exist_ok=True)
for old in fd.iterdir(): old.unlink()
WEIGHT = [("thin", 100), ("extralight", 200), ("ultralight", 200), ("light", 300), ("regular", 400), ("book", 400), ("medium", 500),
          ("semibold", 600), ("demibold", 600), ("extrabold", 800), ("heavy", 900), ("black", 900), ("bold", 700)]
def guess(p):
    s = re.sub(r"[^a-z]", "", p.stem.lower()); w = next((v for k, v in WEIGHT if k in s), 400)
    return w, "italic" if ("italic" in s or s.endswith("it")) else "normal"
fonts, fam = [], {}
F = b.get("fonts", {})
for role in ("head", "body", "accent"):
    f = F.get(role) or {}
    if not f.get("family"): continue
    fam[role] = f["family"]
    key = re.sub(r"[^a-z]", "", f["family"].lower())
    files = {Path(f["file"]).expanduser()} if f.get("file") else set()
    files |= {p for p in (HOME / "fonts").glob("*") if p.suffix.lower() in (".ttf", ".otf", ".woff", ".woff2")
              and re.sub(r"[^a-z]", "", p.stem.lower()).startswith(key)}
    for p in sorted(x for x in files if x.exists()):
        if any(x["file"] == p.name for x in fonts): continue
        shutil.copy(p, fd / p.name); w, st = guess(p)
        if p.name == Path(f.get("file", "")).name: w, st = int(f.get("weight", w)), f.get("style", st)
        fonts.append({"family": f["family"], "file": p.name, "weight": str(w), "style": st})

# their own 3D / sticker elements (optional): <REELS_HOME>/assets/chrome/<id>.png|webp -> public/chrome/<id>.webp
cd = ROOT / "public" / "chrome"; cd.mkdir(parents=True, exist_ok=True)
for p in sorted((HOME / "assets" / "chrome").glob("*")) if (HOME / "assets" / "chrome").exists() else []:
    if p.suffix.lower() == ".webp": shutil.copy(p, cd / p.name)
    elif p.suffix.lower() in (".png", ".jpg", ".jpeg") and not (cd / f"{p.stem}.webp").exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), "-c:v", "libwebp", "-lossless", "0", "-q:v", "85", str(cd / f"{p.stem}.webp")])
chrome = sorted(p.stem for p in cd.glob("*.webp"))

out = {"source": str(bp), "C": C, "F": {"head": fam.get("head", "Helvetica Neue"), "accent": fam.get("accent", fam.get("head", "Georgia")),
       "body": fam.get("body", fam.get("head", "Helvetica Neue")), "mono": "IBM Plex Mono"}, "fonts": fonts, "chrome": chrome,
       "name": b.get("name", ""), "handle": b.get("handle", "")}
dst = ROOT / "src" / "lib" / "brand.generated.json"
if not dst.exists() or json.load(open(dst)) != out:
    json.dump(out, open(dst, "w"), ensure_ascii=False, indent=1)
print(f"sync-brand: {b.get('name', '?')} · accents {acc1} / {acc2} · {len(fonts)} font files · {len(chrome)} chrome elements")
