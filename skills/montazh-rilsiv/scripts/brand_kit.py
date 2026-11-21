#!/usr/bin/env python3
"""A kit for a tool, app or company a reel talks about (Claude, Figma, CapCut...), so its cards look like the real thing.
Idea and approach from ghost-editor's brand_kit.py (MIT, github.com/kurbaitaev/ghost-editor); this version is smaller:
no Gemini and no font matching (her brand fonts always win), everything comes from public sources.

    brand_kit.py <reel> <site URL> [--name "CapCut"] [--slug capcut] [--no-shots]
    brand_kit.py <reel> --name Claude                 (no site: Simple Icons only)

-> <reel>/brand/<slug>/
   kit.json      name, url, accent (the brand colour) + accent_source, logo / logo_white / logo_black / icon, shots
   logo.svg      the official mark from Simple Icons (pinned 16.35.0, the same source inserts.py uses), recoloured:
                 logo_white.svg for dark grounds, logo_black.svg for light ones, logo.svg in the brand colour
   icon.png      the app icon: apple-touch-icon / manifest icon / the biggest favicon the site declares
   shots/        og:image / twitter:image and big page pictures, >= 600 px; any with a face goes to shots/rejected/
                 (strangers never reach a card; her own photos come from her, not from here)
   sheet.jpg     logo on light + dark, icon, colour, shots: LOOK at it before a card uses the kit
Accent order of trust: Simple Icons' official hex, then the site's theme-color, then the icon's commonest strong colour.
Use: a `logo` card with "src": "brand/<slug>/logo_white.svg" on dark cards, the accent for that card's highlight only
(never for her captions or her brand elements), shots as `photo` inserts. Logos name the thing she reviews; never edited."""
import argparse, colorsys, html, json, os, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
VENV = HOME / ".venv" / "bin" / "python"
try:
    from PIL import Image, ImageDraw
except ImportError:
    if VENV.exists() and Path(sys.prefix).resolve() != (HOME / ".venv").resolve():
        os.execv(str(VENV), [str(VENV), *sys.argv])
    sys.exit(f"needs Pillow: {HOME}/.venv/bin/pip install pillow")

SI = "https://cdn.jsdelivr.net/npm/simple-icons@16.35.0/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}
CACHE = Path("~/.cache/reel-editor").expanduser()


def get(url, binary=True, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        b = r.read()
    return b if binary else b.decode("utf-8", "replace")


def si_data():
    p = CACHE / "simple-icons-16.35.0.json"
    if not p.exists():
        CACHE.mkdir(parents=True, exist_ok=True); p.write_bytes(get(SI + "data/simple-icons.json"))
    return json.load(open(p))


def si_find(name, slug, url):
    D = si_data()
    host = urllib.parse.urlparse(url or "").netloc.replace("www.", "")
    key = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    for x in D:
        if slug and x.get("slug", key(x["title"])) == slug: return x
    for x in D:
        if name and key(x["title"]) == key(name): return x
    for x in D:
        if host and host in (x.get("source") or ""): return x
    return None


def recolor(svg, hexcol):
    svg = re.sub(r'\sfill="[^"]*"', "", svg)
    return svg.replace("<svg ", f'<svg fill="#{hexcol}" ', 1)


def strong(img):
    """the commonest saturated colour of an image"""
    im = img.convert("RGBA").resize((64, 64)); seen = {}
    px = im.tobytes()
    for i in range(0, len(px), 4):
        r, g, b, a = px[i], px[i + 1], px[i + 2], px[i + 3]
        if a < 200: continue
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if s < 0.35 or l < 0.15 or l > 0.85: continue
        k = (r // 24, g // 24, b // 24); seen[k] = seen.get(k, 0) + 1
    if not seen: return None
    r, g, b = max(seen, key=seen.get)
    return "%02X%02X%02X" % (r * 24 + 12, g * 24 + 12, b * 24 + 12)


def has_face(path):
    """True when the picture shows a face (OpenCV YuNet via own_footage.py's helpers), None when it can't check"""
    try:
        r = subprocess.run([str(VENV), "-c", "import sys,cv2;sys.path.insert(0,sys.argv[2]);import own_footage as o;"
                            "im=cv2.imread(sys.argv[1]);print(len(o.faces().detect(im,0.7)) if im is not None else -1)", str(path),
                            str(Path(__file__).resolve().parent)], capture_output=True, text=True, timeout=120)
        n = int(r.stdout.strip().splitlines()[-1]); return None if n < 0 else n > 0
    except Exception:
        return None


def page_assets(url):
    h = get(url, binary=False)
    metas = {m.group(1).lower(): html.unescape(m.group(2)) for m in re.finditer(
        r'<meta[^>]+(?:property|name)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']', h, re.I)}
    links = [(m.group(0), html.unescape(m.group(1))) for m in re.finditer(r'<link[^>]+href=["\']([^"\']+)["\'][^>]*>', h, re.I)]
    icons = []
    for tag, href in links:
        if re.search(r'rel=["\'][^"\']*(apple-touch-icon|icon)[^"\']*["\']', tag, re.I):
            sz = re.search(r'sizes=["\'](\d+)x', tag); icons.append((int(sz.group(1)) if sz else (180 if "apple" in tag else 32), urllib.parse.urljoin(url, href)))
    man = next((urllib.parse.urljoin(url, href) for tag, href in links if re.search(r'rel=["\']manifest', tag, re.I)), None)
    if man:
        try:
            for ic in json.loads(get(man, binary=False)).get("icons", []):
                sz = re.match(r"(\d+)", ic.get("sizes", "0")); icons.append((int(sz.group(1)) if sz else 0, urllib.parse.urljoin(man, ic["src"])))
        except Exception: pass
    shots = [metas[k] for k in ("og:image", "og:image:url", "twitter:image") if k in metas]
    shots += [urllib.parse.urljoin(url, m.group(1)) for m in re.finditer(r'<img[^>]+src=["\']([^"\']+\.(?:png|jpe?g|webp))["\']', h, re.I)][:12]
    return {"theme": metas.get("theme-color"), "icons": sorted(icons, reverse=True), "shots": list(dict.fromkeys(urllib.parse.urljoin(url, s) for s in shots))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reel"); ap.add_argument("url", nargs="?"); ap.add_argument("--name"); ap.add_argument("--slug"); ap.add_argument("--no-shots", action="store_true")
    a = ap.parse_args()
    if not (a.url or a.name): sys.exit("give a site URL or --name")
    si = si_find(a.name, a.slug, a.url)
    name = a.name or (si or {}).get("title") or urllib.parse.urlparse(a.url).netloc.replace("www.", "").split(".")[0].title()
    slug = a.slug or (si or {}).get("slug") or re.sub(r"[^a-z0-9]", "", name.lower())
    out = Path(a.reel).expanduser() / "brand" / slug; (out / "shots" / "rejected").mkdir(parents=True, exist_ok=True)
    kit = {"name": name, "url": a.url, "accent": None, "accent_source": None, "logo": None, "icon": None, "shots": []}
    if si:
        svg = get(SI + f"icons/{si.get('slug', slug)}.svg", binary=False)
        for fn, col in (("logo.svg", si["hex"]), ("logo_white.svg", "FFFFFF"), ("logo_black.svg", "111111")):
            (out / fn).write_text(recolor(svg, col))
        kit.update(logo="logo.svg", logo_white="logo_white.svg", logo_black="logo_black.svg", accent="#" + si["hex"], accent_source="simple-icons")
        print(f"logo: Simple Icons «{si['title']}», colour #{si['hex']}")
    else:
        print("no official logo in Simple Icons: use the icon, a screenshot or a text tag (never draw one)")
    P = {"theme": None, "icons": [], "shots": []}
    if a.url:
        try: P = page_assets(a.url)
        except Exception as e: print(f"site unreachable ({e}): logo/colour only")
    for size, iu in P["icons"]:
        try:
            b = get(iu); ext = ".svg" if b.lstrip()[:5] in (b"<svg ", b"<?xml") else ".png"
            if ext == ".png":
                im = Image.open(__import__("io").BytesIO(b)); im.load()
                if min(im.size) < 64: continue
                im.convert("RGBA").save(out / "icon.png")
            else: (out / "icon.svg").write_bytes(b)
            kit["icon"] = "icon" + ext; print(f"icon: {iu}"); break
        except Exception: continue
    if not kit["accent"]:
        if P["theme"] and re.fullmatch(r"#[0-9a-fA-F]{6}", P["theme"]) and P["theme"].lower() not in ("#ffffff", "#000000"):
            kit.update(accent=P["theme"].upper(), accent_source="theme-color")
        elif kit["icon"] == "icon.png" and (c := strong(Image.open(out / "icon.png"))):
            kit.update(accent="#" + c, accent_source="icon")
    if not a.no_shots:
        for k, su in enumerate(P["shots"]):
            if len(kit["shots"]) >= 4: break
            try:
                b = get(su); im = Image.open(__import__("io").BytesIO(b)); im.load()
                if max(im.size) < 600: continue
                f = out / "shots" / f"shot{k}.jpg"; im.convert("RGB").save(f, quality=90)
                face = has_face(f)
                if face:
                    f.rename(out / "shots" / "rejected" / f.name); print(f"shot {su}: a person in it -> rejected"); continue
                kit["shots"].append({"file": f"shots/{f.name}", "w": im.size[0], "h": im.size[1], "source": su, "people": "none" if face is False else "unchecked"})
            except Exception: continue
    json.dump(kit, open(out / "kit.json", "w"), ensure_ascii=False, indent=1)
    # the sheet: logo on light and dark, icon, colour swatch, shots
    W = 1200; sheet = Image.new("RGB", (W, 640), "#FDFDFD"); d = ImageDraw.Draw(sheet)
    d.rectangle([600, 0, W, 300], fill="#141414")
    def svg_png(svgf, px):
        try:
            tmp = CACHE / "sheet_logo.png"
            subprocess.run(["sips", "-s", "format", "png", "-Z", str(px), str(svgf), "--out", str(tmp)], capture_output=True, check=True)
            return Image.open(tmp).convert("RGBA")
        except Exception: return None
    for fn, x in (("logo_black.svg", 250), ("logo_white.svg", 850)):
        if (out / fn).exists() and (im := svg_png(out / fn, 140)): sheet.paste(im, (x, 80), im)
    if kit["icon"] == "icon.png":
        ic = Image.open(out / "icon.png").convert("RGBA"); ic.thumbnail((120, 120)); sheet.paste(ic, (40, 340), ic)
    if kit["accent"]:
        d.rectangle([200, 340, 320, 460], fill=kit["accent"]); d.text((200, 470), f"{kit['accent']} ({kit['accent_source']})", fill="#141414")
    x = 360
    for s in kit["shots"][:3]:
        im = Image.open(out / s["file"]); im.thumbnail((270, 260)); sheet.paste(im, (x, 340)); x += im.size[0] + 10
    d.text((20, 610), f"{name}  {a.url or ''}", fill="#141414")
    sheet.save(out / "sheet.jpg", quality=88)
    print(f"-> {out}/kit.json, LOOK at {out / 'sheet.jpg'}")


if __name__ == "__main__":
    main()
