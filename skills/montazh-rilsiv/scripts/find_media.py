#!/usr/bin/env python3
"""Find a picture for a phrase when she has none of her own: stock photo, short stock video, reaction GIF or a meme.

  find_media.py <reel> photo "<query>" [-n 4]        Pixabay photos (free for ads and organic); Pexels instead when PEXELS_API_KEY is set
  find_media.py <reel> video "<query>" [-n 3]        Pixabay / Pexels short videos (b-roll)
  find_media.py <reel> gif   "<query>" [-n 4]        GIPHY reactions, saved as mp4 (organic reels; GIFs are not cleared for ads)
  find_media.py <reel> meme  "<keywords>" [-n 4]     Imgflip meme templates whose name matches (English names: "drake",
                                                     "distracted", "this is fine"...); without keywords: the 30 most used
  find_media.py <reel> meme --id <template id> --text "top line / bottom line"
                                                     the meme with HER words, in the brand's head font, white with a dark
                                                     outline, as the classic top / bottom layout -> finds/meme-<id>.png

Queries in English: the stock libraries index English tags (a Ukrainian word finds next to nothing).
Files land in <reel>/finds/ with finds/finds.json (file, kind, source, author, page, license note) so the page can show
them as options and the credits stay with the reel. Keys live in ~/.config/reels/.env (PIXABAY_API_KEY or PEXELS_API_KEY, GIPHY_API_KEY);
a missing key exits with code 2 and says how to add it (scripts/set_key.sh). Imgflip needs no key.
Licences: Pixabay / Pexels = free for commercial use; GIPHY = organic only; meme templates = organic only (no ads)."""
import argparse, json, os, re, sys, urllib.parse, urllib.request
from pathlib import Path

ENV = Path("~/.config/reels/.env").expanduser()
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
UA = {"User-Agent": "reel-editor/1.0"}

def key(name):
    v = os.environ.get(name)
    if not v and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith(name + "="): v = line.split("=", 1)[1].strip().strip('"')
    if not v:
        print(f"NO KEY: {name}. Add it once: bash scripts/set_key.sh {name}", file=sys.stderr); sys.exit(2)
    return v

def get(url, headers=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=30) as r:
        return json.load(r)

def save(url, path):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: path.write_bytes(r.read())
    return path

slug = lambda s: re.sub(r"[^\w]+", "-", s.lower()).strip("-")[:30] or "x"

def has(name):
    return bool(os.environ.get(name)) or (ENV.exists() and any(l.startswith(name + "=") and l.split("=", 1)[1].strip() for l in ENV.read_text().splitlines()))

def pixabay(q, n, vid):
    base = "https://pixabay.com/api/videos/" if vid else "https://pixabay.com/api/"
    d = get(base + "?" + urllib.parse.urlencode({"key": key("PIXABAY_API_KEY"), "q": q, "lang": "uk", "per_page": max(3, n * 2), "safesearch": "true",
                                                 **({} if vid else {"image_type": "photo", "orientation": "vertical"})}))
    hits = d.get("hits", [])
    if not hits and not vid:   # few vertical shots: any orientation
        d = get(base + "?" + urllib.parse.urlencode({"key": key("PIXABAY_API_KEY"), "q": q, "lang": "uk", "per_page": max(3, n * 2), "safesearch": "true", "image_type": "photo"})); hits = d.get("hits", [])
    for k, h in enumerate(hits[:n]):
        meta = {"source": "Pixabay", "author": h.get("user"), "page": h.get("pageURL"), "license": "Pixabay: free, also for ads"}
        if vid:
            v = h.get("videos", {}); f = v.get("medium") or v.get("small") or v.get("large") or {}
            if f.get("url"): yield save(f["url"], OUT / f"video-{slug(q)}-{k + 1}.mp4"), meta
        else: yield save(h.get("largeImageURL") or h["webformatURL"], OUT / f"photo-{slug(q)}-{k + 1}.jpg"), meta

def photo(q, n):
    if not has("PEXELS_API_KEY"): yield from pixabay(q, n, False); return   # Pexels stopped issuing keys (10.2026): Pixabay is the default
    d = get("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": n, "orientation": "portrait", "locale": "uk-UA"}),
            {"Authorization": key("PEXELS_API_KEY")})
    for k, p in enumerate(d.get("photos", [])[:n]):
        yield save(p["src"]["large"], OUT / f"photo-{slug(q)}-{k + 1}.jpg"), {"source": "Pexels", "author": p.get("photographer"), "page": p.get("url"),
                                                                            "license": "Pexels: free, also for ads"}

def video(q, n):
    if not has("PEXELS_API_KEY"): yield from pixabay(q, n, True); return
    d = get("https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": q, "per_page": n * 2, "orientation": "portrait", "size": "medium", "locale": "uk-UA"}),
            {"Authorization": key("PEXELS_API_KEY")})
    for k, v in enumerate(d.get("videos", [])[:n]):
        files = sorted((f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and (f.get("height") or 0) <= 1920),
                       key=lambda f: -(f.get("height") or 0))
        if files: yield save(files[0]["link"], OUT / f"video-{slug(q)}-{k + 1}.mp4"), {"source": "Pexels", "author": (v.get("user") or {}).get("name"),
                                                                                    "page": v.get("url"), "license": "Pexels: free, also for ads"}

def gif(q, n):
    d = get("https://api.giphy.com/v1/gifs/search?" + urllib.parse.urlencode({"api_key": key("GIPHY_API_KEY"), "q": q, "limit": n, "lang": "uk", "rating": "pg-13"}))
    for k, g in enumerate(d.get("data", [])[:n]):
        mp4 = (g.get("images", {}).get("original_mp4") or g.get("images", {}).get("fixed_height") or {}).get("mp4")
        if mp4: yield save(mp4, OUT / f"gif-{slug(q)}-{k + 1}.mp4"), {"source": "GIPHY", "author": g.get("username") or None, "page": g.get("url"),
                                                                     "license": "GIPHY: organic posts only, not for ads"}

def memes(q, n):
    all_ = get("https://api.imgflip.com/get_memes")["data"]["memes"]
    words = [w for w in q.lower().split() if w]
    hits = [m for m in all_ if all(w in m["name"].lower() for w in words)] if words else all_[:30]
    for m in hits[:n if words else 30]:
        yield save(m["url"], OUT / f"meme-{m['id']}.jpg"), {"source": "Imgflip template", "name": m["name"], "id": m["id"], "boxes": m["box_count"],
                                                             "license": "meme template: organic posts only, not for ads"}

def caption(mid, text):
    """Her words on a meme template: brand head font, white with a dark outline, top / bottom."""
    from PIL import Image, ImageDraw, ImageFont
    src = next(OUT.glob(f"meme-{mid}.*"), None) or save(next(m["url"] for m in get("https://api.imgflip.com/get_memes")["data"]["memes"] if m["id"] == mid), OUT / f"meme-{mid}.jpg")
    brand = json.load(open(HOME / "brand.json")); fpath = Path(brand["fonts"]["head"]["file"]).expanduser()
    if fpath.suffix == ".woff2":   # PIL reads ttf/otf: convert the brand's woff2 once
        from fontTools.ttLib import TTFont
        ttf = fpath.with_suffix(".ttf")
        if not ttf.exists(): f = TTFont(str(fpath)); f.flavor = None; f.save(str(ttf))
        fpath = ttf
    im = Image.open(src).convert("RGB"); W, H = im.size; d = ImageDraw.Draw(im)
    parts = [p.strip() for p in text.split("/")] + [""]
    for line, top in ((parts[0], True), (parts[1], False)):
        if not line: continue
        size = int(W / 9)
        while size > 18:
            font = ImageFont.truetype(str(fpath), size); w = d.textbbox((0, 0), line, font=font)[2]
            if w <= W * 0.92: break
            size -= 2
        h = d.textbbox((0, 0), line, font=font)[3]
        y = int(H * 0.04) if top else H - h - int(H * 0.06)
        d.text(((W - w) / 2, y), line, font=font, fill="white", stroke_width=max(2, size // 12), stroke_fill="#0D1A0F")
    out = OUT / f"meme-{mid}-caption.png"; im.save(out); return out

try: import PIL  # noqa: the meme caption needs Pillow + fontTools: they live in the skill's venv
except ImportError:
    vpy = HOME / ".venv/bin/python"
    if "--text" in sys.argv and vpy.exists() and Path(sys.prefix).resolve() != (HOME / ".venv").resolve(): os.execv(str(vpy), [str(vpy), *sys.argv])
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("reel"); ap.add_argument("kind", choices=["photo", "video", "gif", "meme"]); ap.add_argument("query", nargs="?", default="")
ap.add_argument("-n", type=int, default=4); ap.add_argument("--id"); ap.add_argument("--text")
ap.add_argument("--into", default="", help="sub-folder of finds/ (one per request on the page: finds/<request id>/)")
A = ap.parse_args()
OUT = Path(A.reel).expanduser() / "finds" / A.into if A.into else Path(A.reel).expanduser() / "finds"; OUT.mkdir(parents=True, exist_ok=True)
log = OUT / "finds.json"
REL = Path(A.reel).expanduser(); found = json.load(open(log)) if log.exists() else []
if A.kind == "meme" and A.id and A.text:
    out = caption(A.id, A.text); found.append({"file": str(out.relative_to(REL)), "kind": "meme", "id": A.id, "text": A.text,
                                               "license": "meme template: organic posts only, not for ads"}); print(out)
else:
    for path, meta in {"photo": photo, "video": video, "gif": gif, "meme": memes}[A.kind](A.query, A.n):
        found.append({"file": str(path.relative_to(REL)), "kind": A.kind, "query": A.query, **meta}); print(path, "|", meta.get("name") or meta.get("author") or "")
json.dump(found, open(log, "w"), ensure_ascii=False, indent=1)
