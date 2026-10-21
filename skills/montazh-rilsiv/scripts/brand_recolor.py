#!/usr/bin/env python3
"""Recolour a catalog motion (HyperFrames composition HTML) into a person's brand, and make it sit over the video.

  recolor(html, colors)      every colour literal (#hex, rgb[a](), hsl[a]()) mapped to a brand role, alpha kept:
                             near-black -> brand dark, near-white -> brand light, greys -> a blend of the two,
                             saturated colours -> the brand accents (the motion's most used hue -> pop, the next -> soft).
  transparent_bg(html, cid)  drops the full-frame background (body, root, inset:0 layers) so the motion floats over the video.

colors: brand.json "colors" ({main, deep?, pop, soft?, light}). Real product UIs (ChatGPT, Claude, iPhone, Instagram) are
marked "keep_ui" in the catalog and are not recoloured: they have to look like the real thing.
python3 brand_recolor.py <in.html> <brand.json> [out.html]   recolours a file (for checking by eye)."""
import colorsys, json, re, sys
from collections import Counter

HEX = re.compile(r"(?<![&\w])#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])")   # not &#8220; entities
FUNC = re.compile(r"(rgba?|hsla?)\(\s*([^)]*?)\s*\)", re.I)


def _hex(h):
    h = h.lstrip("#")
    if len(h) in (3, 4): h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r, g, b, a


def _num(x, scale):
    x = x.strip()
    return float(x[:-1]) / 100 if x.endswith("%") else float(x) / scale


def _func(kind, args):
    parts = [p for p in re.split(r"[\s,/]+", args.strip()) if p]
    if len(parts) < 3: return None
    try:
        if kind.lower().startswith("rgb"):
            r, g, b = (_num(p, 255) for p in parts[:3])
        else:
            h = float(parts[0].replace("deg", "")) / 360
            s, l = (float(p.rstrip("%")) / 100 for p in parts[1:3])
            r, g, b = colorsys.hls_to_rgb(h % 1, l, s)
        a = 1.0 if len(parts) < 4 else (float(parts[3][:-1]) / 100 if parts[3].endswith("%") else float(parts[3]))
    except ValueError:
        return None
    return r, g, b, a


def _out(r, g, b, a):
    r, g, b = (max(0, min(255, round(v * 255))) for v in (r, g, b))
    return f"rgba({r},{g},{b},{round(a, 3)})" if a < 0.999 else f"#{r:02x}{g:02x}{b:02x}"


def _mix(c1, c2, t):
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(3))


def recolor(html, colors, over=False):
    dark = _hex(colors.get("deep") or colors["main"])[:3]
    main = _hex(colors["main"])[:3]
    light = _hex(colors.get("light") or "#FFFFFF")[:3]
    pop = _hex(colors["pop"])[:3]
    soft = _hex(colors.get("soft") or colors["pop"])[:3]

    found = [_hex(m.group(0)) for m in HEX.finditer(html)] + [c for m in FUNC.finditer(html) if (c := _func(m.group(1), m.group(2)))]
    hues = Counter()
    for r, g, b, a in found:
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if s >= 0.25 and 0.15 < l < 0.92: hues[round(h * 12) % 12] += 1
    rank = [h for h, _ in hues.most_common()]

    def role(r, g, b, a):
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        if s < 0.25 or l <= 0.12 or l >= 0.94:           # neutrals: brand dark .. brand light
            if l < 0.2: return (*(dark if l < 0.1 else main), a)
            if l > 0.88: return (*light, a)
            return (*_mix(main, light, (l - 0.2) / 0.68), a)
        hk = round(h * 12) % 12
        acc = soft if hk in rank and rank.index(hk) % 2 else pop   # most used hue -> pop, next -> soft, ...
        if l < 0.25: return (*_mix(dark, acc, 0.35), a)   # deep tints of an accent: a dark accent-tinted brand colour
        if l > 0.85: return (*_mix(light, acc, 0.25), a)  # pale tints: a light accent wash
        return (*acc, a)

    if over:   # over the video: a dark TEXT colour would vanish on a dark shirt or room, so text inks go light (cards keep theirs)
        def ink(m):
            v = m.group(2); c = _hex(v) if v.startswith("#") else (_func(*FUNC.match(v).groups()) if FUNC.match(v) else None)
            if c and colorsys.rgb_to_hls(*c[:3])[1] < 0.45 and colorsys.rgb_to_hls(*c[:3])[2] < 0.5: return m.group(1) + _out(*light, c[3])
            return m.group(0)
        html = re.sub(r"((?<![\w-])(?:color|fill|--fg|--ink|--text|--text-color|--foreground|--hf-ink)\s*:\s*)(#[0-9a-fA-F]{3,8}|(?:rgba?|hsla?)\([^)]*\))", ink, html)
    html = HEX.sub(lambda m: _out(*role(*_hex(m.group(0)))), html)
    return FUNC.sub(lambda m: _out(*role(*c)) if (c := _func(m.group(1), m.group(2))) else m.group(0), html)


FULL = re.compile(r"(inset\s*:\s*0|width\s*:\s*100%[^}]*height\s*:\s*100%|height\s*:\s*100%[^}]*width\s*:\s*100%|"
                  r"width\s*:\s*1920px[^}]*height\s*:\s*1080px|width\s*:\s*1080px[^}]*height\s*:\s*1920px)", re.I)


def transparent_bg(html, cid):
    """Full-frame backgrounds off: body / html / the composition root / any rule that covers the whole canvas."""
    def rule(m):
        sel, body = m.group(1), m.group(2)
        whole = re.search(r"(^|[\s,])(html|body|:root)\b", sel) or f'data-composition-id="{cid}"' in sel or "#root" in sel or FULL.search(body)
        if whole and re.search(r"background", body, re.I):
            body = re.sub(r"background(-color|-image)?\s*:[^;}]*;?", "", body, flags=re.I) + ";background:transparent!important;"
        return sel + "{" + body + "}"
    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", lambda m: m.group(1) + re.sub(r"([^{}]+)\{([^{}]*)\}", rule, m.group(2)) + m.group(3), html, flags=re.S)
    return html.replace("<style>", f'<style>\n[data-composition-id="{cid}"]{{background:transparent!important}}\n', 1)


DARK_FRAME = ("paper", "dark", "on-dark", "inverse", "white", "light-on-dark", "night")


def over_vars(txt, vals):
    """Over the video the frame is dark (a person, a room): switch tone-like enum vars to their 'for dark frames' option."""
    m = re.search(r"data-composition-variables='(\[.*?\])'", txt, re.S)
    if not m: return vals
    try: defs = json.loads(m.group(1))
    except ValueError: return vals
    for v in defs:
        if v.get("type") != "enum" or v["id"] in vals or v["id"] not in ("tone", "theme", "surface", "mode", "scheme", "ink", "palette"): continue
        opts = [o.get("value") if isinstance(o, dict) else o for o in v.get("options") or []]
        pick = next((o for o in DARK_FRAME if o in opts), None)
        if pick: vals[v["id"]] = pick
    return vals


if __name__ == "__main__":
    src, bj = sys.argv[1], json.load(open(sys.argv[2]))
    out = recolor(open(src).read(), bj["colors"])
    (open(sys.argv[3], "w").write(out) if len(sys.argv) > 3 else print(out))
