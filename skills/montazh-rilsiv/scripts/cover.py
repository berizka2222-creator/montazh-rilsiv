#!/usr/bin/env python3
"""Three cover options for the reel: the sharpest camera frames (spread across the reel) with the hook text on top,
in the brand's head font and colours. Text sits inside the centre 4:5 area, the part Instagram shows in the profile grid.
Usage: python3 cover.py <reel-folder> ["hook / text"]   -> <reel>/cover_1.jpg .. cover_3.jpg + covers.jpg (side by side)
The hook comes from the argument, else the title card in edit.json. Frames come from master.mp4 (camera only, no cards)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

reel = Path(sys.argv[1]).expanduser()
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
brand = json.load(open(HOME / "brand.json"))
edit = json.load(open(reel / "edit.json")) if (reel / "edit.json").exists() else {}
hook = sys.argv[2] if len(sys.argv) > 2 else next((c.get("text", "") for c in edit.get("cards", []) if c.get("type") == "title"), "")
if not hook.strip(): sys.exit("no hook text: pass it as the second argument (ask them for it, never invent it)")
lines = [x.strip() for x in hook.split("/") if x.strip()]
if brand.get("captions", {}).get("case", "lower") == "lower": lines = [x.lower() for x in lines]
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = (H - 1350) // 2, (H + 1350) // 2          # the 4:5 crop of the profile grid

def font_file(role):
    f = brand.get("fonts", {}).get(role, {}).get("file")
    return str(Path(f).expanduser()) if f and Path(f).expanduser().exists() else None
HEAD = font_file("head") or font_file("body")
if not HEAD: sys.exit("brand.json has no head font file")
TEXT = brand.get("title_color") or brand.get("colors", {}).get("light", "#FFFFFF")

master = reel / "master.mp4"
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(master)],
                           capture_output=True, text=True).stdout)
with tempfile.TemporaryDirectory() as tmp:
    # one small frame every 0.5 s: score sharpness (edge energy) and keep the best three at least 8 s apart
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(master), "-vf", "fps=2,scale=270:-2", f"{tmp}/f%04d.jpg"], check=True)
    scored = []
    for p in sorted(Path(tmp).glob("f*.jpg")):
        t = (int(p.stem[1:]) - 1) / 2
        if t < 0.3 or t > dur - 1: continue
        g = Image.open(p).convert("L")
        scored.append((ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0], t))
    picks = []   # the sharpest frame in each third of the reel, so the three options differ
    for k in range(3):
        part = [x for x in scored if k * dur / 3 <= x[1] < (k + 1) * dur / 3]
        if part: picks.append(max(part)[1])
    outs = []
    for k, t in enumerate(picks, 1):
        fp = Path(tmp) / f"full{k}.png"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(master), "-frames:v", "1",
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", str(fp)], check=True)
        img = Image.open(fp).convert("RGB")
        # a soft dark fade behind the text so white type reads on any background
        draw = ImageDraw.Draw(img)
        def fit(band_h):   # biggest size whose lines fit 900 px wide and the band's height
            s = 150
            while s > 50:
                f = ImageFont.truetype(HEAD, s)
                if max(draw.textlength(x, font=f) for x in lines) <= 900 and s * 0.92 * len(lines) <= band_h: return s, f
                s -= 4
            return s, ImageFont.truetype(HEAD, s)
        # two places that keep the face clear: above the head (short hooks) or over the chest (long ones), inside the 4:5 grid crop
        TOP_BAND, LOW_BAND = (SAFE_TOP + 30, 560), (1170, SAFE_BOTTOM - 40)
        size, fnt = fit(TOP_BAND[1] - TOP_BAND[0])
        band = TOP_BAND
        if size < 96: size, fnt = fit(LOW_BAND[1] - LOW_BAND[0]); band = LOW_BAND
        block = int(size * 0.92 * len(lines)); top = band[0] + (band[1] - band[0] - block) // 2
        fade = Image.new("L", (W, H), 0); d = ImageDraw.Draw(fade)   # soft dark band behind the text so white type reads anywhere
        for yy in range(max(0, top - 220), min(H, top + block + 220)):
            d.line([(0, yy), (W, yy)], fill=int(160 * max(0, 1 - abs(yy - (top + block / 2)) / (block / 2 + 220))))
        img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, fade)
        draw = ImageDraw.Draw(img)
        y = top
        for j, x in enumerate(lines):
            w = draw.textlength(x, font=fnt)
            xpos = (W - w) / 2 if len(lines) == 1 else (90 if j % 2 == 0 else W - 90 - w)   # alternating, like the hook in the reel
            shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
            sd.text((xpos, y + 6), x, font=fnt, fill=(0, 0, 0, 150))
            img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(10))).convert("RGB")
            draw = ImageDraw.Draw(img)
            draw.text((xpos, y), x, font=fnt, fill=TEXT)
            y += int(size * 0.92)
        out = reel / f"cover_{k}.jpg"; img.save(out, quality=95); outs.append(out)
        print(f"{out.name}: frame at {t:.1f}s")
sheet = Image.new("RGB", (W * len(outs) // 3, H // 3), (13, 26, 15))
for k, p in enumerate(outs): sheet.paste(Image.open(p).resize((W // 3, H // 3)), (k * W // 3, 0))
sheet.save(reel / "covers.jpg", quality=90)
print(reel / "covers.jpg")
