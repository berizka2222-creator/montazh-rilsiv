# Reel skill: own effects from a reference reel (2026-11-06, instagram.com/reel/De6rKILOEaN).
# Not part of Vibha's original: fx.py runs this file at its end (exec), so it uses fx.py's helpers and registers
# into the same EFFECTS. Names start with "rf-". Colours: YELLOW = the brand's soft accent (lime), PEACH = pop (pink).
# Word timing: fx_pass.py passes `words` = [[start, end, text], ...] of the card's seconds (from master_transcript.json);
# a card's `text` (words split by "|" or spaces) wins and is spread over the card.

RF_MAIN = (13, 26, 15)


def rf_u(c): return c.W / 1080.0


def rf_list(e, key='text', sep='|'):
    v = e.o.get(key)
    if v is None: return []
    if isinstance(v, list): return [str(x) for x in v]
    v = str(v)
    return [x.strip() for x in (v.split(sep) if sep in v else v.split()) if x.strip()]


def rf_timed(e, key='text', step=None, lead=0.05):
    """[(t0, t1, word)] relative to the card: the card's own words spread over it, else the spoken words."""
    ws = rf_list(e, key)
    if ws:
        n = len(ws); st = step or min(0.42, max(0.12, (e.d - 0.5) / max(1, n)))
        return [(lead + i * st, e.d, w) for i, w in enumerate(ws)]
    out = []
    for w in e.o.get('words') or []:
        try: a, b, t = float(w[0]), float(w[1]), str(w[2]).strip(' .,!?;:…"«»“”')
        except Exception: continue
        if t.strip(): out.append((max(0.0, a), min(e.d, b), t.strip()))
    return out


def rf_line_layer(c, pts, color, width, glow=0.0):
    """An anti-aliased polyline as an RGBA float layer (with an optional soft glow)."""
    L = np.zeros((c.H, c.W, 4), np.float32)
    if len(pts) < 2: return L
    p = np.int32(np.round(np.asarray(pts) * 16))
    a = np.zeros((c.H, c.W), np.float32)
    cv2.polylines(a, [p], False, 1.0, max(1, int(round(width))), cv2.LINE_AA, shift=4)
    if glow > 0:
        g = cv2.GaussianBlur(a, (0, 0), glow); a = np.clip(a + g * 1.6, 0, 1)
    L[..., :3] = np.float32(color) / 255.0; L[..., 3] = a
    return L


def rf_comp_mask(c, L, alpha=1.0, part=None):
    """Composite a full-frame layer; part: 'behind' (hidden by the person) / 'front' / None."""
    a = L[..., 3:4] * alpha
    if part == 'behind': a = a * (1 - c.m[..., None])
    c.img[:] = c.img * (1 - a) + L[..., :3] * a


def rf_txt(s, size, kind='bold', fill=(255, 255, 255), halo=None):
    """White text that stays readable on light clothes: a soft shadow, and a dark halo for small text."""
    size = int(size); halo = (size < 60) if halo is None else halo
    return text_img(s, size, kind, fill=fill, shadow=max(3, int(size * 0.14)), glow=((0, 0, 0), max(2, size * 0.18)) if halo else None)


def rf_squeeze(im, k):
    """Condense a text image horizontally (a bold brand face reads as a condensed display face)."""
    return im.resize((max(1, int(im.width * k)), im.height), Image.LANCZOS) if abs(k - 1) > 0.01 else im


def rf_pill(s, size, bg, fg, pad_x=0.55, pad_y=0.28):
    t = text_img(s, size, 'ui', fill=fg)
    f = font('ui', size); bb = f.getbbox(s)
    w, h = int(bb[2] - bb[0] + size * pad_x * 2), int(size * (1 + pad_y * 2))
    im = rrect(w, h, h / 2, tuple(bg) + (255,))
    im.alpha_composite(t, (int((w - t.width) / 2), int((h - t.height) / 2 - size * 0.04)))
    return shadowed(im, blur=max(4, int(size * 0.3)), dy=max(2, int(size * 0.12)), alpha=90)


def rf_body_box(c):
    ys, xs = np.where(c.m > 0.5)
    if len(xs) < 50: return (c.fx - c.fw * 1.6, c.fy - c.fw * 0.8, c.fx + c.fw * 1.6, c.H)
    return (float(np.percentile(xs, 2)), float(ys.min()), float(np.percentile(xs, 98)), float(ys.max()))


# ---------- 1-4: lines and outlines around the person ----------
@effect('rf-neon-trace', 'a thin neon line wraps around you: behind the head, in front of the chest')
def fx_rf_neon_trace(c, e):
    u = rf_u(c); col = rgb(e.o.get('color'), YELLOW)
    sweep = min(e.d, float(e.o.get('speed', 1.3)))
    k = clamp(c.lt / sweep)
    cx, cy = c.fx, c.fy + c.fw * 0.6
    rx, ry = c.fw * 0.92, c.fw * 1.45
    rot = math.radians(float(e.o.get('tilt', -20)))
    n = 220
    th = np.linspace(-0.55 * math.pi, 1.75 * math.pi, n)   # starts low on one side, over the head, crosses the chest
    xs = rx * np.cos(th); ys = ry * np.sin(th) * -1
    pts = np.stack([cx + xs * math.cos(rot) - ys * math.sin(rot), cy + xs * math.sin(rot) + ys * math.cos(rot)], 1)
    head = ease_inout(k) * 1.25; tail = max(0.0, head - 0.55)
    i0, i1 = int(clamp(tail) * (n - 1)), int(clamp(head) * (n - 1))
    if i1 - i0 < 2: return
    seg = pts[i0:i1 + 1]
    out = clamp((e.d - c.lt) / 0.2)
    L = rf_line_layer(c, seg, col, 3.2 * u, glow=5 * u)
    # the arc over the head goes behind her, the rest passes in front (never over the face)
    up = (seg[:, 1] < c.fy + c.fw * 0.55)
    if up.any():
        Lb = rf_line_layer(c, seg[up], col, 3.2 * u, glow=5 * u); rf_comp_mask(c, Lb, out, 'behind')
    lo = ~up
    if lo.any():
        idx = np.where(lo)[0]
        for grp in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
            if len(grp) > 1: rf_comp_mask(c, rf_line_layer(c, seg[grp], col, 3.2 * u, glow=5 * u), out)


@effect('rf-outline', 'a thin white line runs exactly along your outline, like a selection')
def fx_rf_outline(c, e):
    u = rf_u(c); col = rgb(e.o.get('color'), (255, 255, 255))
    m8 = (c.m > 0.5).astype(np.uint8)
    cs, _ = cv2.findContours(m8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs: return
    cnt = max(cs, key=cv2.contourArea)[:, 0, :].astype(np.float32)
    if len(cnt) < 20: return
    # leave out the frame edges (where the body leaves the picture)
    edge = (cnt[:, 0] < 3) | (cnt[:, 0] > c.W - 4) | (cnt[:, 1] > c.H - 4)
    top = int(np.argmin(cnt[:, 1])); cnt = np.roll(cnt, -top, 0); edge = np.roll(edge, -top)
    k = ease_out(c.lt / float(e.o.get('speed', 0.6)))
    n = len(cnt); half = int(n / 2 * k)
    keep = np.zeros(n, bool); keep[:half] = True; keep[n - half:] = True   # draws from the top of the head down both sides
    keep &= ~edge
    out = clamp((e.d - c.lt) / 0.25)
    idx = np.where(keep)[0]
    for grp in np.split(idx, np.where(np.diff(idx) > 1)[0] + 1):
        if len(grp) > 3:
            pts = cv2.GaussianBlur(cnt[grp].reshape(-1, 1, 2), (1, 9), 0).reshape(-1, 2) if len(grp) > 12 else cnt[grp]
            rf_comp_mask(c, rf_line_layer(c, pts, col, 1.8 * u, glow=1.2 * u), 0.9 * out)


@effect('rf-glow', 'a short glow flares around your whole outline (an accent on one word)')
def fx_rf_glow(c, e):
    u = rf_u(c); col = np.float32(rgb(e.o.get('color'), YELLOW)) / 255
    up, dn = 0.1, float(e.o.get('fade', 0.55))
    k = clamp(c.lt / up) * clamp(1 - (c.lt - up) / dn) * clamp((e.d - c.lt) / 0.1)
    if k <= 0: return
    m = c.m
    halo = cv2.GaussianBlur(m, (0, 0), 22 * u) * 1.7 + cv2.GaussianBlur(m, (0, 0), 6 * u) * 1.2
    edge = np.clip(cv2.dilate(m, np.ones((3, 3), np.uint8)) - cv2.erode(m, np.ones((5, 5), np.uint8)), 0, 1)
    a = np.clip(halo * (1 - m) + edge * 0.9, 0, 1)[..., None] * k
    c.img[:] = np.clip(c.img + col * a, 0, 1)


@effect('rf-track-dots', 'small tracking marks sit on your clothes, as if a program follows you')
def fx_rf_track_dots(c, e):
    u = rf_u(c); col = rgb(e.o.get('color'), (255, 255, 255))
    spots = [(-1.15, 1.55, 'o'), (1.2, 1.6, 'o'), (0.05, 2.25, '^'), (-0.7, 3.0, '+'), (0.9, 2.95, 'o'), (-1.5, 2.6, '^'), (1.55, 2.3, '+')]
    out = clamp((e.d - c.lt) / 0.25)
    L = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    r = 10 * u; w = max(1, int(round(2.2 * u)))
    for i, (ox, oy, kind) in enumerate(spots):
        a = clamp((c.lt - 0.06 * i) / 0.15) * out
        if a <= 0: continue
        x = c.fx + ox * c.fw + math.sin(c.t * 2.1 + i) * 1.5 * u; y = c.fy + oy * c.fw + math.cos(c.t * 1.7 + i) * 1.5 * u
        xi, yi = int(np.clip(x, 0, c.W - 1)), int(np.clip(y, 0, c.H - 1))
        if c.m[yi, xi] < 0.5: continue
        fill = tuple(col) + (int(230 * a),)
        if kind == 'o': d.ellipse([x - r, y - r, x + r, y + r], outline=fill, width=w)
        elif kind == '^': d.polygon([(x, y - r), (x + r, y + r * 0.8), (x - r, y + r * 0.8)], outline=fill, width=w)
        else: d.line([x - r, y, x + r, y], fill=fill, width=w); d.line([x, y - r, x, y + r], fill=fill, width=w)
        d.ellipse([x - 1.6 * u, y - 1.6 * u, x + 1.6 * u, y + 1.6 * u], fill=fill)
    comp(c, L, 0, 0)


# ---------- 5-9: pills and labels ----------
@effect('rf-tilt-pills', 'two tilted pills pop in on both sides of a word under your chin')
def fx_rf_tilt_pills(c, e):
    u = rf_u(c); ws = rf_list(e)[:2] or ['новий', 'драйвер']
    bg = rgb(e.o.get('color'), YELLOW); fg = rgb(e.o.get('ink'), RF_MAIN)
    size = int(float(e.o.get('size', 34)) * u)
    pills = cached(e, 'p', lambda: [rf_pill(w, size, bg, fg) for w in ws])
    mid = e.o.get('mid'); y = c.fy + c.fw * float(e.o.get('y', 1.05))
    out = clamp((e.d - c.lt) / 0.2)
    gap = c.fw * 0.62 if mid else c.fw * 0.1
    rots = (9, -8)
    for i, p in enumerate(pills):
        k = pop(c, 0.05 + 0.14 * i, 0.32)
        if k <= 0: continue
        side = -1 if i == 0 else 1
        x = c.fx + side * (gap + p.width * 0.42)
        x = min(max(x, p.width * 0.55), c.W - p.width * 0.55)
        place(c, p, x, y - (8 * u if i == 0 else -6 * u), k, rots[i], out, guard=True)
    if mid:
        t = cached(e, 'mid', lambda: rf_txt(str(mid), int(size * 1.15), 'bold', halo=True))
        place(c, t, c.fx, y, pop(c, 0.0, 0.25), 0, out, guard=True)


@effect('rf-glass-flash', 'a word gets a quick tinted glass box with a glitch, then is clean again')
def fx_rf_glass_flash(c, e):
    u = rf_u(c); word = str(e.o.get('text') or 'слово')
    size = int(float(e.o.get('size', 64)) * u)
    t = cached(e, 't', lambda: rf_txt(word, size, 'bold', halo=True))
    y = c.fy + c.fw * float(e.o.get('y', 1.75)); x = c.fx
    out = clamp((e.d - c.lt) / 0.2)
    place(c, t, x, y, 0.85 + 0.15 * ease_out(c.lt / 0.25), 0, clamp(c.lt / 0.12) * out, guard=True)
    a0, a1 = 0.18, 0.18 + float(e.o.get('hold', 0.45))
    if a0 <= c.lt <= a1 + 0.12:
        k = clamp((c.lt - a0) / 0.08) * clamp((a1 + 0.12 - c.lt) / 0.12)
        bw, bh = t.width * 1.02, size * 1.25
        tint = rgb(e.o.get('color'), (80, 120, 255))
        g = glass(c, bw, bh, 6 * u, x, y, amt=0.42, tint=tint, alpha=int(235 * k))
        jitter = (math.sin(c.t * 90) * 10 * u) if c.lt - a0 < 0.12 or a1 - c.lt < 0.1 else 0
        place(c, g, x + jitter, y, 1, 0, 1, guard=True)
        # glitch: a few shifted slices in the box's tint
        if abs(jitter) > 0:
            for j in range(3):
                sy = int(y - bh / 2 + (j + 0.5) * bh / 3); sh = max(2, int(3 * u))
                y0, y1 = max(0, sy), min(c.H, sy + sh); x0, x1 = int(max(0, x - bw / 2)), int(min(c.W, x + bw / 2))
                if y1 > y0 and x1 > x0: c.img[y0:y1, x0:x1] = np.roll(c.img[y0:y1, x0:x1], int(jitter * (j + 1)), 1)
        place(c, t, x, y, 1, 0, k, guard=True)


@effect('rf-anchor-word', 'a big word stays on your chest, small [labels] change above it')
def fx_rf_anchor_word(c, e):
    u = rf_u(c); word = str(e.o.get('text') or 'ЧАС')
    tags = rf_list(e, 'tags') or [w for _, _, w in rf_timed(e, 'none')][:5]
    big = cached(e, 'b', lambda: rf_squeeze(rf_txt(word.upper(), int(float(e.o.get('size', 120)) * u), 'bold'), 0.9))
    out = clamp((e.d - c.lt) / 0.2)
    yb = c.fy + c.fw * float(e.o.get('y', 1.95))
    k = ease_back(c.lt / 0.35)
    place(c, big, c.fx, yb + (1 - k) * 40 * u, 0.9 + 0.1 * k, 0, clamp(c.lt / 0.15) * out, guard=True)
    if not tags: return
    st = max(0.3, (e.d - 0.3) / len(tags)); i = min(len(tags) - 1, int(max(0, c.lt - 0.3) / st)) if c.lt >= 0.3 else -1
    if i < 0: return
    lt = c.lt - 0.3 - i * st
    lab = cached(e, f'l{i}', lambda: rf_txt(f'[ {tags[i]} ]', int(40 * u), 'ui'))
    a = clamp(lt / 0.12) * (clamp((st - lt) / 0.1) if i < len(tags) - 1 else 1) * out
    place(c, lab, c.fx, yb - big.height * 0.48 - 8 * u - (1 - clamp(lt / 0.15)) * 12 * u, 1, 0, a, guard=True)


@effect('rf-side-note', 'three or four small left-aligned lines beside you, like a note in the margin')
def fx_rf_side_note(c, e):
    u = rf_u(c); lines = rf_list(e)[:5] or ['спершу', 'вивчи', 'систему']
    size = int(float(e.o.get('size', 40)) * u)
    ims = cached(e, 'l', lambda: [rf_txt(s, size, 'ui') for s in lines])
    left = e.o.get('side', 'left') != 'right'
    bx0, _, bx1, _ = cached(e, 'box', lambda: rf_body_box(c))
    wmax = max(i.width for i in ims)
    x = (max(24 * u, min(c.fx - c.fw * 1.25, bx0 + c.fw * 0.2) - wmax)) if left else min(c.W - 24 * u - wmax, max(c.fx + c.fw * 1.25, bx1 - c.fw * 0.2))
    x = max(24 * u, x)
    y = c.fy + c.fw * float(e.o.get('y', 1.35))
    out = clamp((e.d - c.lt) / 0.2)
    for i, im in enumerate(ims):
        a = clamp((c.lt - 0.1 * i) / 0.14) * out
        if a <= 0: continue
        comp(c, im, x - (1 - clamp((c.lt - 0.1 * i) / 0.2)) * 18 * u, y + i * size * 1.05, a)


@effect('rf-quote-title', 'a condensed bold title with a small «quoted» word tucked between its lines')
def fx_rf_quote_title(c, e):
    u = rf_u(c); parts = rf_list(e) or ['ПИШИ В КОМЕНТАР', '«бренд»', 'І Я НАДІШЛЮ']
    W0 = c.W * 0.78
    def build():
        out = []
        for p in parts:
            q = p.startswith(('«', '"', '“')) or p.startswith("'")
            if q: im = rf_txt(p, int(46 * u), 'serif', fill=rgb(e.o.get('accent'), PEACH), halo=True)
            else:
                im = rf_squeeze(rf_txt(p.upper(), int(86 * u), 'bold'), 0.78)
                if im.width > W0: im = im.resize((int(W0), int(im.height * W0 / im.width)), Image.LANCZOS)
            out.append((q, im))
        return out
    rows = cached(e, 'r', build)
    y = c.fy + c.fw * float(e.o.get('y', 1.45))
    out = clamp((e.d - c.lt) / 0.2); step = min(0.35, max(0.12, (e.d - 0.6) / max(1, len(rows))))
    for i, (q, im) in enumerate(rows):
        t0 = 0.05 + step * i; a = clamp((c.lt - t0) / 0.12) * out
        if a > 0:
            k = ease_back((c.lt - t0) / 0.3)
            place(c, im, c.fx, y + (0 if q else (1 - k) * 22 * u), 0.92 + 0.08 * k, 0, a, guard=True)
        y += im.height * (0.62 if q else 0.78)


# ---------- 10-14: moving words ----------
@effect('rf-letter-drop', 'a word falls in letter by letter from different heights and settles')
def fx_rf_letter_drop(c, e):
    u = rf_u(c); word = str(e.o.get('text') or 'ЧАС').upper()
    size = int(float(e.o.get('size', 130)) * u); col = rgb(e.o.get('color'), (255, 255, 255))
    f = font('bold', size)
    def setup():
        rnd = random.Random(len(word) * 13 + 5)
        ims = [rf_txt(ch, size, 'bold', fill=col) if ch.strip() else None for ch in word]
        adv = [f.getlength(ch) for ch in word]; tot = sum(adv)
        xs, x = [], -tot / 2
        for a in adv: xs.append(x + a / 2); x += a
        return ims, xs, [(rnd.uniform(-0.9, -0.25), rnd.uniform(-25, 25), rnd.uniform(-0.35, 0.35)) for _ in word]
    ims, xs, rr = cached(e, 's', setup)
    y = c.fy + c.fw * float(e.o.get('y', 2.0)); out = clamp((e.d - c.lt) / 0.2)
    for i, im in enumerate(ims):
        if im is None: continue
        t0 = 0.07 * i; k = ease_back((c.lt - t0) / 0.42)
        if c.lt < t0: continue
        dy0, rot0, dx0 = rr[i]
        yy = y + (1 - k) * dy0 * c.H * 0.35; xx = c.fx + xs[i] + (1 - k) * dx0 * c.fw
        place(c, im, xx, yy, 1, (1 - k) * rot0, clamp((c.lt - t0) / 0.1) * out, guard=True)


@effect('rf-word-cloud', 'the spoken words float past you at different depths, one letter in the accent colour')
def fx_rf_word_cloud(c, e):
    u = rf_u(c); acc = rgb(e.o.get('color'), PEACH); key = str(e.o.get('accent') or '').lower()
    ws = rf_timed(e, step=0.22)
    if not ws: return
    def setup():
        rnd = random.Random(11); out = []
        for j, (a, b, w) in enumerate(ws):
            z = rnd.choice([0.35, 0.55, 0.8, 1.0, 1.35])   # depth: small and soft far away, big and sharp close
            x = ((j * 0.61) % 1) * 0.8 + 0.1; y = ((j * 0.37 + 0.15) % 1)
            out.append((a, w, z, x, y, rnd.choice([-1, 1])))
        return out
    items = cached(e, 'it', setup)
    bx0, bx1 = max(c.W * 0.16, c.fx - c.fw * 1.8), min(c.W * 0.84, c.fx + c.fw * 1.8)
    by0 = c.fy + c.fw * 1.0; by1 = max(by0 + c.H * 0.12, min(c.H * 0.86, c.fy + c.fw * 3.3))
    life = float(e.o.get('life', 1.9)); end = clamp((e.d - c.lt) / 0.2)
    for j, (a, w, z, x, y, sd) in enumerate(items):
        lt = c.lt - a
        if lt < 0 or lt > life: continue
        def mk(w=w, z=z):
            size = int(96 * z * u)
            if key and key in w.lower():
                i0 = w.lower().index(key); pieces = [(w[:i0], (255, 255, 255)), (w[i0:i0 + len(key)], acc), (w[i0 + len(key):], (255, 255, 255))]
            elif z >= 1.0 and len(w) > 3:
                i0 = len(w) // 2; pieces = [(w[:i0], (255, 255, 255)), (w[i0], acc), (w[i0 + 1:], (255, 255, 255))]
            else: pieces = [(w, (255, 255, 255))]
            ims = [text_img(p, size, 'bold', fill=col, shadow=max(3, int(size * 0.14))) for p, col in pieces if p]
            pad = int(size * 0.2 + max(3, int(size * 0.14)) * 2.5) + 4
            tw_ = sum(i.width - 2 * pad for i in ims) + 2 * pad; th_ = max(i.height for i in ims)
            im = Image.new('RGBA', (tw_, th_), (0, 0, 0, 0)); xx = 0
            for i in ims: im.alpha_composite(i, (xx, 0)); xx += i.width - 2 * pad
            blur = (0.55 - z) * 10 * u if z < 0.55 else (z - 1.2) * 14 * u if z > 1.2 else 0
            return im.filter(ImageFilter.GaussianBlur(blur)) if blur > 0.5 else im
        im = cached(e, f'w{j}', mk)
        k = lt / life
        xx = bx0 + (bx1 - bx0) * x + sd * (k - 0.3) * 160 * u * z
        yy = by0 + (by1 - by0) * y - k * 40 * u
        a = clamp(lt / 0.15) * clamp((life - lt) / 0.3) * end * (0.55 + 0.45 * min(1, z))
        place(c, im, xx, yy, 0.9 + 0.25 * k, 0, a, guard=True)


@effect('rf-spread-words', 'three small words stand far apart across the frame, each when it is said')
def fx_rf_spread_words(c, e):
    u = rf_u(c); ws = rf_timed(e, step=0.3)[:4]
    if not ws: return
    size = int(float(e.o.get('size', 42)) * u)
    y = c.fy + c.fw * float(e.o.get('y', 1.6)); out = clamp((e.d - c.lt) / 0.2)
    n = len(ws); xs = [c.W * (0.14 + 0.72 * i / max(1, n - 1)) for i in range(n)] if n > 1 else [c.fx]
    for i, (a, b, w) in enumerate(ws):
        im = cached(e, f's{i}', lambda w=w: rf_txt(w, size, 'uib'))
        if c.lt < a: continue
        k = ease_out((c.lt - a) / 0.25)
        place(c, im, xs[i], y + (1 - k) * 14 * u + (i % 2) * 6 * u, 1, 0, clamp((c.lt - a) / 0.12) * out, guard=True)


@effect('rf-vertical-word', 'one word turned on its side beside your head, typed letter by letter')
def fx_rf_vertical_word(c, e):
    u = rf_u(c); word = str(e.o.get('text') or 'легко')
    size = int(float(e.o.get('size', 64)) * u); col = rgb(e.o.get('color'), (255, 255, 255))
    n = len(word); k = clamp(c.lt / max(0.2, min(0.6, n * 0.06)))
    shown = word[:max(1, int(math.ceil(n * k)))]
    im = cached(e, f'v{len(shown)}', lambda: rf_txt(shown, size, 'bold', fill=col))
    side = 1 if e.o.get('side', 'right') != 'left' else -1
    x = c.fx + side * c.fw * float(e.o.get('x', 0.95)); x = min(max(x, size), c.W - size)
    y0 = c.fy - c.fw * 0.2   # reads top to bottom, starting at eye level
    rim = im.rotate(-90 if side > 0 else 90, Image.BICUBIC, expand=True)
    comp(c, rim, x - rim.width / 2, y0 if side > 0 else y0, clamp((e.d - c.lt) / 0.2), guard=True)


@effect('rf-texture-title', 'a giant condensed word behind you, filled with a blurred picture and a brand gradient')
def fx_rf_texture_title(c, e):
    u = rf_u(c); word = str(e.o.get('text') or 'РЕКЛАМА').upper()
    top, bot = rgb(e.o.get('color'), YELLOW), rgb(e.o.get('color2'), PEACH)
    def mask():
        im = rf_squeeze(text_img(word, int(330 * u), 'bold'), 0.62)
        if im.width > c.W * 0.96: im = im.resize((int(c.W * 0.96), int(im.height * c.W * 0.96 / im.width)), Image.LANCZOS)
        return np.asarray(im.split()[3], np.float32) / 255
    M = cached(e, 'm', mask); h, w = M.shape
    x0 = int(c.W / 2 - w / 2); y0 = int(max(c.H * 0.06, c.fy - c.fw * 0.9 - h * 0.55))
    ys, xs = np.clip(np.arange(y0, y0 + h), 0, c.H - 1), np.clip(np.arange(x0, x0 + w), 0, c.W - 1)
    reg = cv2.GaussianBlur(np.ascontiguousarray(c.img[np.ix_(ys, xs)]), (0, 0), 14 * u)
    g = np.linspace(0, 1, h)[:, None, None]; grad = (np.float32(top) * (1 - g) + np.float32(bot) * g) / 255
    fill = np.clip((reg - reg.mean()) * 1.6 + grad * 0.95, 0, 1)   # the picture shows through the gradient
    k = ease_out(c.lt / 0.45); out = clamp((e.d - c.lt) / 0.25)
    a = M * clamp(c.lt / 0.2) * out
    if k < 1:   # focuses in from a soft blow-up
        a = cv2.GaussianBlur(a, (0, 0), max(0.1, (1 - k) * 12 * u))
    L = np.dstack([fill, a[..., None]]).astype(np.float32)
    comp(c, L, x0, y0 - (1 - k) * 30 * u, 1.0, behind=True)
    sub = e.o.get('sub')
    if sub:
        s = cached(e, 'sub', lambda: rf_txt(f'[ {sub} ]', int(40 * u), 'ui'))
        place(c, s, c.W / 2, y0 + h * 0.98, 1, 0, clamp((c.lt - 0.25) / 0.15) * out, behind=True)


# ---------- 15: transition ----------
@effect('rf-color-wash', 'a cream flash that melts into a short colour wash (a cut between two thoughts)')
def fx_rf_color_wash(c, e):
    cream = np.float32(rgb(e.o.get('flash'), CREAM)) / 255; tint = np.float32(rgb(e.o.get('color'), PEACH)) / 255
    t = c.lt; f_in, f_hold = 0.07, float(e.o.get('hold', 0.1))
    if t < f_in + f_hold:
        k = clamp(t / f_in); c.img[:] = c.img * (1 - k) + cream * k; return
    k = 1 - clamp((t - f_in - f_hold) / max(0.15, e.d - f_in - f_hold))
    flash = clamp(1 - (t - f_in - f_hold) / 0.12)
    screen = 1 - (1 - c.img) * (1 - tint * 0.75)
    c.img[:] = c.img * (1 - k * 0.85) + screen * k * 0.85
    if flash > 0: c.img[:] = c.img * (1 - flash) + cream * flash
