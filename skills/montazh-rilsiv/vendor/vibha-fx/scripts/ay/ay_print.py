# ay "print" group: printed-matter looks rebuilt from the 2026-11-13 reference reel, in the person's brand.
#   ay-banknote    engraved banknote with her live portrait in an oval, a number counting up
#   ay-press       newspaper front page with a live halftone photo of her
#   ay-paper-tear  the page tears down the middle and falls away, revealing her video
#   ay-impact      two-tone impact frame with radial speed lines and a giant word
#   ay-code-body   she turns into mono characters on a dark code background
# Helpers are prefixed _pr_. Everything is drawn at 2x then LANCZOS-downsampled where it is static.

import datetime as _pr_dt

_PR_CACHE = {}          # shared between effects (ay-press -> ay-paper-tear use the same page layout)
_PR_INK_BN = (18, 60, 36)        # banknote ink: deep green
_PR_PAPER_BN = (226, 233, 215)   # pale green-cream paper
_PR_INK_NP = (20, 26, 14)        # newspaper ink (brand ink)
_PR_PAPER_NP = (241, 240, 231)   # newsprint (brand cream)
_PR_UA_MONTHS = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня',
                 'листопада', 'грудня']
_PR_UA_DAYS = ['понеділок', 'вівторок', 'середа', 'четвер', "п'ятниця", 'субота', 'неділя']


def _pr_smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


_pr_fc = {}


def _pr_light(size):
    """Playfair at its lightest weight (banknote numbers)."""
    k = int(size)
    if k not in _pr_fc:
        f = ImageFont.truetype(AY_FONT['s'], max(6, k))
        try: f.set_variation_by_axes([400])
        except Exception: pass
        _pr_fc[k] = f
    return _pr_fc[k]


def _pr_word(s, size, kind, fill, cond=1.0, track=0.0, alpha=255):
    """Tight RGBA text image, optionally condensed horizontally (cond < 1). kind 'sl' = Playfair light."""
    if kind == 'sl':
        f = _pr_light(size); bb = f.getbbox(s); pad = int(size * 0.12) + 2
        im = Image.new('RGBA', (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), s, font=f, fill=tuple(fill) + (alpha,))
    else:
        im = ay_text(s, size, kind, fill=fill, track=track, alpha=alpha)
    if abs(cond - 1) > 0.01:
        im = im.resize((max(1, int(im.width * cond)), im.height), Image.LANCZOS)
    return im


def _pr_paste(canvas, im, x, y, anchor='mm'):
    """alpha_composite im onto canvas with anchor l/m/r + t/m/b."""
    ax = {'l': 0, 'm': 0.5, 'r': 1}[anchor[0]]; ay_ = {'t': 0, 'm': 0.5, 'b': 1}[anchor[1]]
    canvas.alpha_composite(im, (int(round(x - im.width * ax)), int(round(y - im.height * ay_))))


def _pr_gray(img):
    return img @ np.float32([0.299, 0.587, 0.114])


def _pr_clahe(g, clip=2.2, tiles=4):
    u = (np.clip(g, 0, 1) * 255).astype(np.uint8)
    return cv2.createCLAHE(clipLimit=clip, tileGridSize=(tiles, tiles)).apply(u).astype(np.float32) / 255


def _pr_portrait(c, bw, bh, face_frac, face_y):
    """Crop of the frame (and mask) around her face into a bw x bh box: face width = face_frac * bw, face centre at
    face_y of the box height. Returns (rgb, mask)."""
    sc = clamp(face_frac * bw / max(1.0, c.fw), 0.5, 3.0)
    tx = bw / 2 - c.fx * sc; ty = bh * face_y - c.fy * sc
    M = np.float32([[sc, 0, tx], [0, sc, ty]])
    rgb = cv2.warpAffine(c.img, M, (int(bw), int(bh)), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    m = cv2.warpAffine(c.m, M, (int(bw), int(bh)), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return rgb, m


def _pr_tone(rgb, m, bg_level=None, bg_mix=0.5, gamma=1.0, clip=2.2, pct=(3, 97)):
    """Luminance for print: CLAHE-normalised on her, background pushed light (or flat bg_level)."""
    g = _pr_gray(rgb)
    sel = m > 0.5
    if sel.sum() > 50:
        lo, hi = np.percentile(g[sel], pct)
        g = np.clip((g - lo) / max(0.05, hi - lo), 0, 1)
    if clip: g = _pr_clahe(g, clip)
    if gamma != 1: g = np.power(g, gamma)
    bg = (bg_level if bg_level is not None else (1 - bg_mix) + bg_mix * g)
    return g * m + bg * (1 - m)


def _pr_halftone(L, period, angle=45.0, gain=1.0):
    """Real halftone dots (rotated grid), ink coverage = 1 - L. Returns ink alpha 0..1 with anti-aliased dots."""
    h, w = L.shape
    Ls = cv2.GaussianBlur(L, (0, 0), period * 0.45)
    ink = np.clip((1 - Ls) * gain, 0, 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angle); ca, sa = math.cos(a), math.sin(a)
    u = (xx * ca + yy * sa) / period; v = (-xx * sa + yy * ca) / period
    fu = u - np.floor(u) - 0.5; fv = v - np.floor(v) - 0.5
    d = np.sqrt(fu * fu + fv * fv) * period
    r = period * np.sqrt(ink / math.pi) * 1.06
    return np.clip(r - d + 0.5, 0, 1) * (ink > 0.015)


# ===================================================================== ay-banknote

def _pr_fmt_num(n, sep=' '):
    s = str(int(round(n)))
    out = ''
    while len(s) > 3: out = sep + s[-3:] + out; s = s[:-3]
    return s + out


def _pr_parse_num(v, default):
    s = str(v if v not in (None, '') else default)
    digits = ''.join(ch for ch in s if ch.isdigit())
    i0 = next((i for i, ch in enumerate(s) if ch.isdigit()), len(s))
    i1 = max((i for i, ch in enumerate(s) if ch.isdigit()), default=-1)
    pre, suf = s[:i0], s[i1 + 1:].rstrip('. ')
    return (int(digits) if digits else 0), pre, suf


def _pr_bn_static(W, H, o):
    """Banknote static layer: paper, frame, guilloche, text ring, boxes, seal. Returns float RGB (H, W, 3)."""
    s = W / 1080; k = 2; S = s * k
    ink = _PR_INK_BN
    im = Image.new('RGBA', (int(W * k), int(H * k)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    P = lambda x, y: (x * S, y * S)
    A = lambda a: tuple(ink) + (int(a),)
    lw = lambda px: max(1, int(round(px * S)))
    # faint wavy background lines over the whole note
    xs = np.arange(0, 1081, 6, dtype=np.float32)
    for y0 in range(150, 1800, 16):
        ys = y0 + 3.0 * np.sin(xs / 41 + y0 * 0.07) + 2.0 * np.sin(xs / 13 + y0 * 0.31)
        d.line([P(x, y) for x, y in zip(xs, ys)], fill=A(16), width=lw(1))
    # double border
    d.rounded_rectangle([*P(22, 22), *P(1058, 1898)], radius=int(14 * S), outline=A(255), width=lw(5))
    d.rounded_rectangle([*P(40, 40), *P(1040, 1880)], radius=int(8 * S), outline=A(200), width=lw(1.6))
    # side guilloche strips
    yy = np.arange(160, 1761, 2, dtype=np.float32)
    for x0 in (46, 990):
        d.rectangle([*P(x0, 160), *P(x0 + 28, 1760)], outline=A(150), width=lw(1))
        for j in range(9):
            xq = x0 + 14 + 11 * np.sin(yy / 19 + j * 0.7) * np.cos(yy / 157 + j * 0.3)
            d.line([P(x, y) for x, y in zip(xq, yy)], fill=A(120), width=lw(1))
    # rosette band around the oval
    cx, cy = 540, 670
    th = np.linspace(0, 2 * np.pi, 1600, dtype=np.float32)
    for i in range(34):
        f = i / 33
        ax_, by_ = 352 + 108 * f, 422 + 110 * f
        mod = 1 + 0.055 * np.sin(9 * th + i * 0.37) + 0.03 * np.sin(23 * th - i * 0.23) + 0.012 * np.sin(61 * th + i)
        X = cx + ax_ * mod * np.cos(th); Y = cy + by_ * mod * np.sin(th)
        d.line([P(x, y) for x, y in zip(X, Y)], fill=A(105), width=lw(1))
    # a second, tighter rosette around the seal
    sx_, sy_ = 540, 1655
    for i in range(12):
        mod = 1 + 0.045 * np.sin(18 * th + i * 0.45)
        r = 134 + i * 1.6
        d.line([P(sx_ + r * mod[j] * math.cos(t), sy_ + r * mod[j] * math.sin(t)) for j, t in enumerate(th)], fill=A(70), width=lw(1))
    # oval portrait frame
    d.ellipse([*P(cx - 341, cy - 411), *P(cx + 341, cy + 411)], outline=A(255), width=lw(6))
    d.ellipse([*P(cx - 352, cy - 422), *P(cx + 352, cy + 422)], outline=A(170), width=lw(1.4))
    # text ring (mono, tangential, upside down at the bottom like an engraved note)
    ring = str(o.get('ring') or '· META ADS · ТАРГЕТ · КРЕАТИВИ · ЛІДИ · КОНТЕНТ · ' + ay_handle_s(o).upper() + ' ')
    f = ay_font('mb', 24 * S); trk = 7 * S
    ra, rb = 405 * S, 494 * S
    t = math.radians(-112)
    perim = 2 * math.pi * math.sqrt((ra * ra + rb * rb) / 2)
    adv_total = sum(f.getlength(ch) + trk for ch in ring)
    txt = ring
    while sum(f.getlength(ch) + trk for ch in txt) < perim * 0.9: txt += ring
    while sum(f.getlength(ch) + trk for ch in txt) > perim * 0.9 and '·' in txt[:-1]:
        txt = txt[:txt[:-1].rstrip().rfind('·') + 1]
    txt = txt.strip()
    for ch in txt:
        adv = f.getlength(ch) + trk
        tx_, ty_ = -ra * math.sin(t), rb * math.cos(t); tl = math.hypot(tx_, ty_)
        t += adv / 2 / tl
        px, py = cx * S + ra * math.cos(t), cy * S + rb * math.sin(t)
        tx_, ty_ = -ra * math.sin(t), rb * math.cos(t)
        rot = math.degrees(math.atan2(-ty_, tx_))
        if ch.strip():
            g = Image.new('RGBA', (int(40 * S), int(40 * S)), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((g.width / 2, g.height / 2), ch, font=f, fill=A(235), anchor='mm')
            g = g.rotate(rot, Image.BICUBIC)
            im.alpha_composite(g, (int(px - g.width / 2), int(py - g.height / 2)))
        t += adv / 2 / tl
    # corner value boxes + serial
    to, pre, suf = _pr_parse_num(o.get('to'), '10 000')
    val = pre + _pr_fmt_num(to) + suf + '.'
    for (x0, y0) in ((70, 70), (800, 70), (70, 1780), (800, 1780)):
        d.rectangle([*P(x0, y0), *P(x0 + 210, y0 + 70)], outline=A(255), width=lw(2))
        sz = ay_fit(val, 170 * S / 0.84, 's', start=int(44 * S))
        _pr_paste(im, _pr_word(val, sz, 's', ink, cond=0.84), (x0 + 105) * S, (y0 + 35) * S)
    d.rectangle([*P(380, 70), *P(700, 130)], outline=A(255), width=lw(2))
    serial = str(o.get('serial') or 'ІБ 0100000 МА')
    sz = ay_fit(serial, 280 * S, 'mb', start=int(25 * S), track=4 * S)
    _pr_paste(im, ay_text(serial, sz, 'mb', fill=AY['pink_dk'], track=4 * S), 540 * S, 100 * S)
    # number box (double rule)
    d.rectangle([*P(110, 1160), *P(970, 1500)], outline=A(255), width=lw(2))
    d.rectangle([*P(122, 1172), *P(958, 1488)], outline=A(160), width=lw(1))
    # sub line
    sub = str(o.get('sub') or 'META ADS · ТАРГЕТ · КОНТЕНТ')
    sz = ay_fit(sub, 760 * S / 0.86, 's', start=int(50 * S))
    _pr_paste(im, _pr_word(sub, sz, 's', ink, cond=0.86), 540 * S, 1442 * S)
    # seal
    d.ellipse([*P(sx_ - 126, sy_ - 126), *P(sx_ + 126, sy_ + 126)], outline=A(200), width=lw(1.4))
    for j in range(120):
        a = j / 120 * 2 * math.pi; r = 116
        d.ellipse([*P(sx_ + r * math.cos(a) - 1.3, sy_ + r * math.sin(a) - 1.3), *P(sx_ + r * math.cos(a) + 1.3, sy_ + r * math.sin(a) + 1.3)], fill=A(200))
    d.ellipse([*P(sx_ - 106, sy_ - 106), *P(sx_ + 106, sy_ + 106)], outline=A(255), width=lw(3))
    nm = ay_name_s(o).split()
    l1, l2 = (nm[0], ' '.join(nm[1:])) if len(nm) > 1 else (nm[0], '')
    sz = ay_fit(max(l1, l2, key=len), 170 * S, 'i', start=int(50 * S))
    _pr_paste(im, ay_text(l1, sz, 'i', fill=ink), sx_ * S, (sy_ - 32) * S)
    if l2: _pr_paste(im, ay_text(l2, sz, 'i', fill=ink), sx_ * S, (sy_ + 16) * S)
    role = str(o.get('role') or 'ЕКСПЕРТ')
    _pr_paste(im, ay_text(role, 14 * S, 'mb', fill=ink, track=4 * S), sx_ * S, (sy_ + 66) * S)
    lay = ay_np(ay_down(im, W, H))
    paper = ay_paper(W, H, color=_PR_PAPER_BN, grain=0.014, seed=11)
    return paper * (1 - lay[..., 3:4]) + lay[..., :3] * lay[..., 3:4]


def ay_handle_s(o): return o.get('handle') or '@your.handle'


def ay_name_s(o): return o.get('name') or 'Твоє Імʼя'


def _pr_engrave(L, period, seed_phase=0.0):
    """Line-screen engraving: wavy horizontal lines whose thickness follows the tone, bending around the forms,
    plus a cross-hatch in the deepest shadows. Returns ink alpha."""
    h, w = L.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    Lb = cv2.GaussianBlur(L, (0, 0), period * 2.2)
    tone = np.clip(1 - cv2.GaussianBlur(L, (0, 0), period * 0.25), 0.03, 0.97)
    ph = (yy + period * 0.55 * np.sin(xx / (period * 7.5) + seed_phase) - Lb * period * 2.4) / period
    dd = np.abs(ph - np.floor(ph) - 0.5)
    a1 = np.clip((tone * 0.5 - dd) * period + 0.5, 0, 1)
    # cross-hatch at ~ -55 deg where it is very dark
    ph2 = (xx * 0.82 + yy * 0.57 - Lb * period * 1.5) / (period * 1.15)
    d2 = np.abs(ph2 - np.floor(ph2) - 0.5)
    t2 = np.clip((tone - 0.62) / 0.38, 0, 1) * 0.42
    a2 = np.clip((t2 - d2) * period + 0.5, 0, 1) * (t2 > 0.01)
    return np.maximum(a1, a2)


@effect('ay-banknote', 'full-frame engraved banknote with your live portrait in an oval and a number counting up')
def fx_ay_banknote(c, e):
    W, H = c.W, c.H; s = W / 1080
    key = ('bn', W, H, json.dumps({k: e.o.get(k) for k in ('to', 'sub', 'ring', 'serial', 'name', 'role', 'handle')}, ensure_ascii=False))
    if key not in _PR_CACHE: _PR_CACHE[key] = _pr_bn_static(W, H, e.o)
    base = _PR_CACHE[key]
    ink = np.float32(_PR_INK_BN) / 255; paper = np.float32(_PR_PAPER_BN) / 255
    # portrait in the oval
    cx, cy, a, b = 540 * s, 670 * s, 336 * s, 406 * s
    bw, bh = int(2 * a) + 2, int(2 * b) + 2
    x0, y0 = int(cx - bw / 2), int(cy - bh / 2)
    rgb, m = _pr_portrait(c, bw, bh, 0.40, 0.43)
    L = _pr_tone(rgb, m, bg_level=None, bg_mix=0.25, gamma=1.0)
    L = np.clip(1.0 - np.power(1 - L, 0.62) * 1.02, 0, 1)   # stronger midtones: every face plane gets a line
    # background inside the oval: pale with a soft guilloche shimmer
    yy, xx = np.mgrid[0:bh, 0:bw].astype(np.float32)
    bgL = 0.80 + 0.07 * np.sin(np.hypot(xx - bw / 2, (yy - bh / 2) * 0.8) / (14 * s) + np.arctan2(yy - bh / 2, xx - bw / 2) * 6)
    mm = cv2.GaussianBlur(m, (0, 0), 1.5)
    L = L * mm + np.maximum(L, bgL) * (1 - mm)
    inkA = _pr_engrave(L, max(4.0, 8.5 * s), seed_phase=0.0)
    port = paper * (1 - inkA[..., None]) + ink * inkA[..., None]
    om = cached(e, 'ovalm', lambda: np.clip((1 - np.sqrt(((xx - bw / 2) / a) ** 2 + ((yy - bh / 2) / b) ** 2)) * min(a, b) + 0.5, 0, 1)[..., None])
    img = base.copy()
    reg = img[y0:y0 + bh, x0:x0 + bw]
    reg[:] = reg * (1 - om) + port * om
    # the number counting up
    to, pre, suf = _pr_parse_num(e.o.get('to'), '10 000')
    fr, _, _ = _pr_parse_num(e.o.get('from'), '0')
    cnt = float(e.o.get('count', min(0.85, e.d * 0.72)))
    p = ease_out(clamp((c.lt - 0.06) / cnt)) if cnt > 0 else 1
    n = fr + (to - fr) * p
    s_final = pre + _pr_fmt_num(to) + suf + '.'
    s_now = pre + _pr_fmt_num(n) + suf + '.'
    size = cached(e, 'nsz', lambda: min(int(250 * s), ay_fit(s_final, 780 * s / 0.74, 's', start=int(270 * s))))
    nim = cached(e, 'n_' + s_now, lambda: _pr_word(s_now, size, 'sl', _PR_INK_BN, cond=0.74))
    if len(e.state) > 400: [e.state.pop(k) for k in [k for k in e.state if k.startswith('n_')][:300]]
    c2 = Ctx(); c2.W, c2.H, c2.img, c2.m = W, H, img, c.m
    c2.fx = c2.fy = -1e4; c2.fw = 1
    place(c2, nim, 540 * s, 1300 * s)
    img = c2.img
    # slam in: quick scale-down + small rotation, then a decaying shake
    lt = c.lt
    z = 1 + 0.24 * (1 - ease_out(clamp(lt / 0.2)))
    rot = 2.2 * (1 - ease_out(clamp(lt / 0.2)))
    sh = math.exp(-max(0, lt - 0.17) * 16) if lt > 0.17 else 0
    rnd = random.Random(int(lt * c.fps) * 7 + 3)
    dx = (rnd.uniform(-1, 1) * 14 * s) * sh; dy = (rnd.uniform(-1, 1) * 10 * s) * sh
    z += 0.02 * sh
    if z > 1.001 or abs(dx) + abs(dy) > 0.2 or abs(rot) > 0.02:
        M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, z); M[0, 2] += dx; M[1, 2] += dy
        img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    al = 1.0
    out_t = float(e.o.get('out', 0))
    if out_t > 0: al *= clamp((e.d - lt) / out_t)
    c.img = c.img * (1 - al) + img * al


# ===================================================================== ay-press

def _pr_today_ua():
    d = _pr_dt.date.today()
    return f'{_PR_UA_DAYS[d.weekday()]}, {d.day} {_PR_UA_MONTHS[d.month - 1]} {d.year}'.upper()


def _pr_justify(d, words, x, y, w, f_r, f_i, lh, fill, last_left=True):
    """Justified paragraph of (word, italic) tokens. Returns the y after it."""
    sp = f_r.getlength(' ')
    lines, cur, cw = [], [], 0
    for wd, it in words:
        ww = (f_i if it else f_r).getlength(wd)
        if cur and cw + sp + ww > w: lines.append(cur); cur, cw = [], 0
        cw += (sp if cur else 0) + ww; cur.append((wd, it, ww))
    if cur: lines.append(cur)
    for li, ln in enumerate(lines):
        tot = sum(t[2] for t in ln)
        gap = (w - tot) / (len(ln) - 1) if len(ln) > 1 and (li < len(lines) - 1 or not last_left) else sp
        if gap > sp * 2.6: gap = sp      # too loose: leave the line ragged
        xx = x
        for wd, it, ww in ln:
            d.text((xx, y), wd, font=f_i if it else f_r, fill=fill, anchor='ls'); xx += ww + gap
        y += lh
    return y


def _pr_tokens(s):
    """'*italic words* regular words' -> [(word, italic)]"""
    out, it = [], False
    for part in s.split('*'):
        out += [(wd, it) for wd in part.split()]
        it = not it
    return out


_PR_COND = 0.82   # the whole page is drawn wide and squeezed to this: Playfair becomes a condensed news serif


def _pr_press_static(W, H, o):
    """Newspaper page without the photo. Returns (float RGB page, photo box (x0, y0, w, h) in px)."""
    s = W / 1080; k = 2; cd = _PR_COND
    LW = int(W / cd * k); LH = int(H * k)
    S = s * k
    X = lambda x: x / cd * S          # final-px x (1080 base) -> canvas x
    Y = lambda y: y * S
    ink = _PR_INK_NP; A = tuple(ink) + (255,)
    im = Image.new('RGBA', (LW, LH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lw = lambda px: max(1, int(round(px * S)))
    F = lambda kind, px: ay_font(kind, px * S)
    # edition boxes
    boxes = [(o.get('left') or 'Ранковий випуск|читати за 20 секунд'), (o.get('right') or 'Свіжі новини|пиши «ЕФЕКТИ»')]
    for j, bx in enumerate(boxes):
        x0 = 50 if j == 0 else 870
        d.rectangle([X(x0), Y(52), X(x0 + 160), Y(148)], outline=A, width=lw(2.2))
        l1, _, l2 = str(bx).partition('|')
        d.text((X(x0 + 80), Y(86)), l1, font=F('s', min(25, ay_fit(l1, 140 * s / cd, 's', start=int(25 * s)) / s)), fill=A, anchor='mm')
        if l2: d.text((X(x0 + 80), Y(114)), l2, font=F('s', min(16, ay_fit(l2, 140 * s / cd, 's', start=int(16 * s)) / s)), fill=A, anchor='mm')
    # masthead
    title = str(o.get('title') or 'Щоденний рілс')
    tsz = min(120, ay_fit(title, 610 * s / cd, 's', start=int(120 * s)) / s)
    d.text((X(540), Y(100)), title, font=F('s', tsz), fill=A, anchor='mm')
    d.rectangle([X(50), Y(172), X(1030), Y(176)], fill=A)
    d.rectangle([X(50), Y(214), X(1030), Y(215.5)], fill=A)
    fm = F('mb', 17)
    tr = 3.2 * S
    def mono(txt, x, y, anc):
        imt = ay_text(txt, 17 * S, 'mb', fill=ink, track=tr)
        _pr_paste(im, imt, x, y, anc)
    mono(ay_handle_s(o).upper(), X(50), Y(195), 'lm')
    mono(str(o.get('date') or _pr_today_ua()), X(540), Y(195), 'mm')
    mono(str(o.get('issue') or 'ВИПУСК № 22'), X(1030), Y(195), 'rm')
    # headline + deck
    head = str(o.get('text') or '22 ЕФЕКТИ ДЛЯ РІЛС')
    hsz = ay_fit(head, 960 * s / cd, 's', start=int(150 * s)) / s
    d.text((X(540), Y(378)), head, font=F('s', hsz), fill=A, anchor='ms')
    sub = str(o.get('sub') or 'які зупиняють скрол і приводять ліди.')
    ssz = ay_fit(sub, 860 * s / cd, 'si', start=int(66 * s)) / s
    d.text((X(540), Y(458)), sub, font=F('si', ssz), fill=A, anchor='ms')
    d.rectangle([X(50), Y(498), X(1030), Y(501)], fill=A)
    # columns
    fr, fi = F('s', 19), F('si', 19)
    colw = 160 / cd * S
    d.text((X(130), Y(552)), str(o.get('col1') or 'Що всередині'), font=F('s', 30), fill=A, anchor='ms')
    left = o.get('body1') or ('*Живий курсор.* Рамка ходить за мною. *Клони.* Сім копій в один ряд. *Циферблат.* '
                              'День за секунду. *Клавіатура.* Вгадує наступне слово. *Орбіта.* Літери навколо голови. '
                              '*Код.* Я зібрана з символів. *Стіна постів.* Один квадрат на день. *Пірнання.* Відео живе в літерах.')
    _pr_justify(d, _pr_tokens(left), X(50), Y(590), colw, fr, fi, 23.6 * S, A)
    d.text((X(950), Y(552)), str(o.get('col2') or 'Запит'), font=F('s', 30), fill=A, anchor='ms')
    y2 = _pr_justify(d, _pr_tokens(o.get('body2') or 'Напиши ЕФЕКТИ в коментарях, і я надішлю тобі всі.'), X(870), Y(590), colw, fr, fi, 23.6 * S, A)
    d.text((X(950), y2 / S * S + 26 * S), str(o.get('col3') or 'Решта'), font=F('s', 30), fill=A, anchor='ms')
    _pr_justify(d, _pr_tokens(o.get('body3') or '*Банкнота.* Цифра росте. *Голосове.* Хвиля звуку. *Удар.* Кадр-вибух. '
                                                 '*Газета.* Ти зараз тут. *Розрив.* Папір навпіл. *Рідке скло.* Фінал.'),
                X(870), y2 + 64 * S, colw, fr, fi, 23.6 * S, A)
    # photo frame + caption
    px0, py0, pw, ph = 230, 690, 620, 776
    d.rectangle([X(px0 - 2), Y(py0 - 2), X(px0 + pw + 2), Y(py0 + ph + 2)], outline=A, width=lw(2))
    cap = str(o.get('caption') or 'Автор у своїй студії.')
    csz = ay_fit(cap, 620 * s / cd, 'si', start=int(23 * s)) / s
    d.text((X(540), Y(1497)), cap, font=F('si', csz), fill=A, anchor='ms')
    d.rectangle([X(50), Y(1520), X(1030), Y(1523)], fill=A)
    # bottom row: index with dot leaders, pull quote, a box
    d.text((X(50), Y(1574)), str(o.get('col4') or 'У цьому випуску'), font=F('s', 30), fill=A, anchor='ls')
    items = [x.strip() for x in str(o.get('list') or 'Таргет::01|Креативи::02|Ліди::03|Аналітика::04|Контент::05').split('|') if x.strip()]
    fl = F('s', 20)
    for j, it in enumerate(items):
        nm, _, num = it.partition('::')
        yb = Y(1606 + j * 28.5)
        d.text((X(50), yb), nm, font=fl, fill=A, anchor='ls')
        d.text((X(212), yb), num, font=fl, fill=A, anchor='rs')
        xa = X(50) + fl.getlength(nm) + 5 * S; xb = X(212) - fl.getlength(num) - 5 * S
        xx = xa
        while xx < xb:
            d.ellipse([xx, yb - 2.2 * S, xx + 2.4 * S, yb + 0.2 * S], fill=A); xx += 6.5 * S
    quote = str(o.get('quote') or '«Напиши ЕФЕКТИ в коментарях, і я надішлю всі.»')
    fq = F('si', 50)
    qw = 450 / cd * S
    words = quote.split(); qlines, cur = [], ''
    for wd in words:
        tst = (cur + ' ' + wd).strip()
        if cur and fq.getlength(tst) > qw: qlines.append(cur); cur = wd
        else: cur = tst
    qlines.append(cur)
    qsz = 50 if len(qlines) <= 3 else 40
    fq = F('si', qsz)
    y0q = 1592 + (3 - min(3, len(qlines))) * 22
    for j, ln in enumerate(qlines[:3]):
        d.text((X(590), Y(y0q + j * qsz * 1.05)), ln, font=fq, fill=A, anchor='ms')
    d.rectangle([X(830), Y(1550), X(1030), Y(1698)], outline=A, width=lw(2))
    bx = str(o.get('box') or 'Прогноз|Ліди ростуть, коли креатив чесний.')
    b1, _, b2 = bx.partition('|')
    d.text((X(930), Y(1588)), b1, font=F('s', 25), fill=A, anchor='ms')
    fb = F('s', 17.5); yb = Y(1620)
    cur = ''
    for wd in b2.split():
        tst = (cur + ' ' + wd).strip()
        if cur and fb.getlength(tst) > 172 / cd * S: d.text((X(930), yb), cur, font=fb, fill=A, anchor='ms'); yb += 25 * S; cur = wd
        else: cur = tst
    if cur: d.text((X(930), yb), cur, font=fb, fill=A, anchor='ms')
    # thin rule + footer
    d.rectangle([X(50), Y(1748), X(1030), Y(1749.5)], fill=A)
    mono(str(o.get('footer') or 'ДРУКУЄТЬСЯ ЩОДНЯ · ' + ay_handle_s(o).upper()), X(540), Y(1772), 'mm')
    lay = ay_np(im.resize((W, H), Image.LANCZOS))
    paper = ay_paper(W, H, color=_PR_PAPER_NP, grain=0.009, seed=5)
    # a little newsprint mottling + darker edges
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    v = ((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2)
    paper *= (1 - 0.06 * v)[..., None]
    page = paper * (1 - lay[..., 3:4]) + (np.float32(ink) / 255) * lay[..., 3:4] * 0.96 + paper * lay[..., 3:4] * 0.04
    return page.astype(np.float32), (int(px0 * s), int(py0 * s), int(pw * s), int(ph * s))


_PR_PAGE_KEYS = ('title', 'text', 'sub', 'quote', 'date', 'issue', 'caption', 'left', 'right', 'list', 'box', 'body1', 'body2',
                 'body3', 'col1', 'col2', 'col3', 'col4', 'footer', 'handle', 'name')


def _pr_press_page(c, o):
    """Full newspaper page for this frame (live halftone photo). Float RGB (H, W, 3)."""
    W, H = c.W, c.H; s = W / 1080
    key = ('np', W, H, json.dumps({k: o.get(k) for k in _PR_PAGE_KEYS}, ensure_ascii=False))
    if key not in _PR_CACHE: _PR_CACHE[key] = _pr_press_static(W, H, o)
    base, (x0, y0, pw, ph) = _PR_CACHE[key]
    rgb, m = _pr_portrait(c, pw, ph, 0.36, 0.40)
    L = _pr_tone(rgb, m, bg_mix=0.5, gamma=1.35, clip=1.3, pct=(1, 99.7))
    L = np.clip(L * 0.97, 0, 1)
    dots = _pr_halftone(L, max(4.0, 9.5 * s), 45, gain=1.0)
    paper = base[y0:y0 + ph, x0:x0 + pw]
    ink = np.float32(_PR_INK_NP) / 255
    page = base.copy()
    page[y0:y0 + ph, x0:x0 + pw] = paper * (1 - dots[..., None]) + ink * dots[..., None]
    return page


def _pr_word_page(c, o, key_text='text', default='ДАЛІ'):
    W, H = c.W, c.H; s = W / 1080
    word = str(o.get(key_text) or default)
    key = ('wp', W, H, word)
    if key not in _PR_CACHE:
        k = 2; im = Image.new('RGBA', (W * k, H * k), (0, 0, 0, 0))
        lines = word.split('|')
        sz = min(ay_fit(max(lines, key=len), 900 * s * k / 0.82, 's', start=int(360 * s * k)), int(H * k / (len(lines) + 1)))
        for j, ln in enumerate(lines):
            wi = _pr_word(ln, sz, 's', _PR_INK_NP, cond=0.82)
            _pr_paste(im, wi, W * k / 2, H * k * 0.5 + (j - (len(lines) - 1) / 2) * sz * 1.0)
        lay = ay_np(im.resize((W, H), Image.LANCZOS))
        paper = ay_paper(W, H, color=_PR_PAPER_NP, grain=0.02, seed=5)
        _PR_CACHE[key] = (paper * (1 - lay[..., 3:4]) + np.float32(_PR_INK_NP) / 255 * lay[..., 3:4]).astype(np.float32)
    return _PR_CACHE[key]


def _pr_page_over(c, page, M, shadow=0.45, s=1.0):
    """Composite a full-frame page warped by the 2x3 affine M over c.img, with a soft drop shadow."""
    W, H = c.W, c.H
    warped = cv2.warpAffine(page, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    one = np.ones((H, W), np.float32)
    a = cv2.warpAffine(one, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    if shadow > 0:
        q = 4
        sa = cv2.resize(a, (W // q, H // q), interpolation=cv2.INTER_AREA)
        sa = cv2.GaussianBlur(sa, (0, 0), 18 * s / q)
        sa = cv2.warpAffine(sa, np.float32([[1, 0, 6 * s / q], [0, 1, 22 * s / q]]), (W // q, H // q))
        sa = cv2.resize(sa, (W, H), interpolation=cv2.INTER_LINEAR)
        c.img = c.img * (1 - shadow * sa[..., None])
    c.img = c.img * (1 - a[..., None]) + warped * a[..., None]


@effect('ay-press', 'full-frame newspaper front page with your live halftone photo; it drops in like a page landing')
def fx_ay_press(c, e):
    W, H = c.W, c.H; s = W / 1080
    page = _pr_press_page(c, e.o)
    lt = c.lt
    land = float(e.o.get('land', 0.42))
    if lt < land * 1.6:
        # damped settle: starts rotated, a bit large and high, lands with one small overshoot
        rot = -4.5 * math.exp(-7.5 * lt) * math.cos(10.5 * lt)
        z = 1 + 0.13 * math.exp(-10 * lt)
        dy = -60 * s * math.exp(-10 * lt)
        M = cv2.getRotationMatrix2D((W / 2, H * 0.55), rot, z); M[1, 2] += dy
        under = c.img * (0.55 + 0.45 * (1 - clamp(lt / 0.12)))
        c.img = under
        _pr_page_over(c, page, M, 0.5, s)
    else:
        c.img = page
    # no exit: hard cut by default, or ay-paper-tear right after continues the same page


# ===================================================================== ay-paper-tear

def _pr_tear_path(H, W, s, seed):
    """Jagged tear line: x(y) for every row. Zig-zag segments + fine fibre noise."""
    rnd = np.random.default_rng(seed)
    ys = [0.0]; xs = [W * 0.5 + rnd.uniform(-20, 20) * s]
    while ys[-1] < H:
        ys.append(ys[-1] + rnd.uniform(28, 75) * s)
        nx = xs[-1] + rnd.normal(0, 26) * s
        nx += (W * 0.5 - nx) * 0.18
        xs.append(nx)
    row = np.arange(H, dtype=np.float32)
    x = np.interp(row, ys, xs).astype(np.float32)
    fine = cv2.GaussianBlur(rnd.normal(0, 1, (H, 1)).astype(np.float32), (0, 0), 1.2)[:, 0] * 1.6 * s
    return x + fine


def _pr_fibres(H, W, path, s, seed, side):
    """Alpha mask of little paper fibres sticking out of the edge (side -1 = left half, +1 = right half)."""
    k = 2; im = Image.new('L', (W * k, H * k), 0); d = ImageDraw.Draw(im)
    rnd = random.Random(seed)
    for _ in range(int(H / (5 * s))):
        y = rnd.uniform(0, H - 1); x = float(path[int(y)])
        ln = rnd.uniform(3, 13) * s; ang = rnd.uniform(-0.9, 0.9)
        dx = side * math.cos(ang) * ln; dy = math.sin(ang) * ln
        d.line([(x * k, y * k), ((x + dx) * k, (y + dy) * k)], fill=rnd.randint(150, 255), width=max(1, int(rnd.uniform(0.6, 1.3) * s * k)))
    return np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255


def _pr_halves(c, e, page, tip, gapmax):
    """RGBA left/right halves of the torn page. Rim and gap only above the tear tip (row index)."""
    W, H = c.W, c.H; s = W / 1080
    st = e.state
    if 'path' not in st:
        st['path'] = _pr_tear_path(H, W, s, int(e.o.get('seed', 7)))
        rnd = np.random.default_rng(3)
        st['rimL'] = (6 + 5 * np.abs(cv2.GaussianBlur(rnd.normal(0, 1, (H, 1)).astype(np.float32), (0, 0), 6)[:, 0] * 3)) * s
        st['rimR'] = (2 + 2.5 * np.abs(cv2.GaussianBlur(rnd.normal(0, 1, (H, 1)).astype(np.float32), (0, 0), 5)[:, 0] * 3)) * s
        st['fibL'] = _pr_fibres(H, W, st['path'], s, 5, -1)
        st['fibR'] = _pr_fibres(H, W, st['path'] - st['rimL'] * 0.5, s, 9, +1)
        st['xx'] = np.arange(W, dtype=np.float32)[None, :]
        st['rimcol'] = np.clip(ay_paper(W, H, color=(250, 249, 243), grain=0.03, seed=21), 0, 1)
    path, xx = st['path'], st['xx']
    row = np.arange(H, dtype=np.float32)
    above = np.clip((tip - row) / (40 * s), 0, 1)[:, None]               # tear exists here
    g = gapmax * np.clip((tip - row - 120 * s) / (520 * s), 0, 1)        # gap opening behind the tip
    pL = path[:, None]; pR = (path - st['rimL'] * 0.55)[:, None]
    dl = pL - xx; dr = xx - pR
    aL = np.clip(dl + 0.5, 0, 1); aR = np.clip(dr + 0.5, 0, 1)
    rimL = np.clip(st['rimL'][:, None] - dl + 0.5, 0, 1) * aL * above
    rimR = np.clip(st['rimR'][:, None] - dr + 0.5, 0, 1) * aR * above
    fibL = st['fibL'] * (1 - aL) * above; fibR = st['fibR'] * (1 - aR) * above
    # a faint grey shading just inside the rim (paper thickness)
    shL = np.clip(st['rimL'][:, None] + 3 * s - dl, 0, 1) * (1 - rimL) * aL * above * 0.18
    rc = st['rimcol']
    rgbL = page * (1 - rimL[..., None]) + rc * rimL[..., None]
    rgbL = rgbL * (1 - shL[..., None])
    rgbL = rgbL * (1 - fibL[..., None]) + rc * fibL[..., None]
    rgbR = page * (1 - rimR[..., None]) + rc * rimR[..., None]
    rgbR = rgbR * (1 - fibR[..., None]) + rc * fibR[..., None]
    AL = np.maximum(aL, fibL); AR = np.maximum(aR, fibR)
    # where the tear has not reached yet the halves are one page: right half takes over the seam
    AR = np.where(above > 0.999, AR, np.maximum(AR, (1 - above) * (xx >= pL - 1)))
    left = np.dstack([rgbL, AL]).astype(np.float32); right = np.dstack([rgbR, AR]).astype(np.float32)
    if gapmax > 0:
        mapy = np.repeat(row[:, None], W, 1)
        mxL = (xx + g[:, None] * 0.5).astype(np.float32); mxR = (xx - g[:, None] * 0.5).astype(np.float32)
        left = cv2.remap(left, mxL, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        right = cv2.remap(right, mxR, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return left, right


def _pr_over_rgba(c, L, M, shadow, s):
    W, H = c.W, c.H
    if M is not None: L = cv2.warpAffine(L, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    a = L[..., 3]
    if shadow > 0:
        q = 4
        sa = cv2.GaussianBlur(cv2.resize(a, (W // q, H // q), interpolation=cv2.INTER_AREA), (0, 0), 10 * s / q)
        sa = cv2.warpAffine(sa, np.float32([[1, 0, 5 * s / q], [0, 1, 16 * s / q]]), (W // q, H // q))
        sa = cv2.resize(sa, (W, H), interpolation=cv2.INTER_LINEAR)
        c.img = c.img * (1 - shadow * sa[..., None])
    c.img = c.img * (1 - a[..., None]) + L[..., :3] * a[..., None]


@effect('ay-paper-tear', 'the page tears down the middle along a jagged edge and the halves fall away, revealing you')
def fx_ay_paper_tear(c, e):
    W, H = c.W, c.H; s = W / 1080
    page = _pr_word_page(c, e.o) if str(e.o.get('page', 'press')) == 'word' else _pr_press_page(c, e.o)
    lt, d = c.lt, e.d
    t_hold = float(e.o.get('hold', min(0.3, d * 0.28)))
    t_rip = float(e.o.get('rip', 0.22))
    t_split = t_hold + t_rip
    if lt < t_hold:
        c.img = page; return
    gapmax = 26 * s
    if lt < t_split:
        p = (lt - t_hold) / t_rip
        tip = (ease_inout(p) * 1.12) * H
        left, right = _pr_halves(c, e, page, tip, gapmax * ease_out(p))
        # the video is visible only through the gap
        _pr_over_rgba(c, right, None, 0.0, s); _pr_over_rgba(c, left, None, 0.25, s)
        return
    left, right = _pr_halves(c, e, page, H * 1.2, gapmax)
    q = clamp((lt - t_split) / max(0.1, d - t_split - 0.04))
    qi = q * q * (0.6 + 0.4 * q)                       # accelerating, like falling
    # right half: hinges out to the right and drops; left half: swings out to the left
    Mr = cv2.getRotationMatrix2D((W * 0.75, H * 0.2), -13 * qi, 1.0)
    Mr[0, 2] += 0.78 * W * qi; Mr[1, 2] += 0.42 * H * qi
    Ml = cv2.getRotationMatrix2D((W * 0.25, H * 0.2), 10 * qi, 1.0)
    Ml[0, 2] -= 0.72 * W * qi; Ml[1, 2] += 0.55 * H * qi
    sh = 0.42 * (1 - 0.5 * q)
    _pr_over_rgba(c, right, Mr, sh, s); _pr_over_rgba(c, left, Ml, sh, s)


# ===================================================================== ay-impact

def _pr_speed_lines(W, H, cx, cy, s, seed, ink):
    k = 2; im = Image.new('L', (W * k, H * k), 0); d = ImageDraw.Draw(im)
    rnd = random.Random(seed); R = 2.2 * max(W, H) * k
    a = 0.0
    while a < 2 * math.pi:
        w = math.radians(rnd.uniform(0.5, 2.6)); a += w * 0.5
        r0 = rnd.uniform(330, 620) * s * k * (1.0 + 0.25 * abs(math.sin(a)))
        tip = (cx * k + r0 * math.cos(a), cy * k + r0 * math.sin(a))
        p1 = (cx * k + R * math.cos(a - w / 2), cy * k + R * math.sin(a - w / 2))
        p2 = (cx * k + R * math.cos(a + w / 2), cy * k + R * math.sin(a + w / 2))
        if rnd.random() < 0.86: d.polygon([tip, p1, p2], fill=255)
        a += w * 0.5 + math.radians(rnd.uniform(0.6, 2.4))
    return np.asarray(im.resize((W, H), Image.LANCZOS), np.float32) / 255


@effect('ay-impact', 'impact frame: two-tone you, radial speed lines behind, a giant word, flash and shake')
def fx_ay_impact(c, e):
    W, H = c.W, c.H; s = W / 1080; st = e.state
    look = str(e.o.get('look', 'cream'))
    ink = np.float32(AY['c1']) / 255
    light = np.float32(AY['lime'] if look == 'lime' else AY['cream']) / 255
    if 'ctr' not in st: st['ctr'] = (c.fx, c.fy + c.fw * 0.55)
    cx, cy = st['ctr']
    lines = cached(e, 'lines', lambda: [_pr_speed_lines(W, H, cx, cy, s, 11 + j * 17, ink) for j in range(3)])
    ln = lines[(int(c.lt * c.fps) // 2) % 3]
    # two-tone her: global threshold at her median + local-contrast linework
    g = _pr_gray(c.img)
    m = c.m
    sel = m > 0.5
    g = cv2.GaussianBlur(g, (0, 0), 1.1 * s)
    if sel.sum() > 100:
        lo, hi = np.percentile(g[sel], [2, 98]); g = np.clip((g - lo) / max(0.05, hi - lo), 0, 1)
        # threshold from the face area so her face gets real shadows (not the whole body median)
        y0, y1 = int(max(0, c.fy - c.fw * 0.9)), int(min(H, c.fy + c.fw * 0.9))
        x0, x1 = int(max(0, c.fx - c.fw * 0.6)), int(min(W, c.fx + c.fw * 0.6))
        fsel = sel[y0:y1, x0:x1]
        if fsel.sum() > 100: med = float(np.percentile(g[y0:y1, x0:x1][fsel], float(e.o.get('dark', 46))))
        else: med = float(np.percentile(g[sel], 50))
    else: med = 0.5
    st['thr'] = med if 'thr' not in st else st['thr'] * 0.7 + med * 0.3
    T = st['thr']
    loc = cv2.GaussianBlur(g, (0, 0), 7 * s)
    inkA = np.maximum(np.clip((T - g) / 0.03 + 0.5, 0, 1), np.clip((loc - g - 0.05) / 0.025 + 0.5, 0, 1))
    person = light * (1 - inkA[..., None]) + ink * inkA[..., None]
    # hard cut-out edge + a crisp ink outline around her
    mm = cv2.GaussianBlur(_pr_smooth(m, 0.42, 0.58).astype(np.float32), (0, 0), 0.7)
    kk = int(9 * s) | 1
    ring = np.clip(cv2.dilate(mm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kk, kk))) - mm, 0, 1)
    bg = light * (1 - ln[..., None]) + ink * ln[..., None]
    bg = bg * (1 - ring[..., None]) + ink * ring[..., None]
    img = bg * (1 - mm[..., None]) + person * mm[..., None]
    # flash frames: cream, then inverted, then the frame
    fi = int(c.lt * c.fps + 0.001)
    if fi == 0: img = np.ones_like(img) * light
    elif fi == 1: img = light + ink - img
    # giant word over the chest (never over the face)
    word = ay_words(e, default='ВАЖЛИВО')[0]
    sz = cached(e, 'wsz', lambda: ay_fit(word, W * 0.86, 'hb', start=int(260 * s)))
    wcol = AY['cream'] if look != 'lime' else AY['cream']
    def _word():
        k = 2; st_ = max(3, int(sz * 0.05)) * k
        t1 = ay_text(word, sz * k, 'hb', fill=wcol, stroke=st_, stroke_fill=AY['c1'])
        t0 = ay_text(word, sz * k, 'hb', fill=AY['c1'], stroke=st_, stroke_fill=AY['c1'])
        off = int(sz * 0.06) * k
        im = Image.new('RGBA', (t1.width + off, t1.height + off), (0, 0, 0, 0))
        im.alpha_composite(t0, (off, off)); im.alpha_composite(t1, (0, 0))
        return im.resize((im.width // k, im.height // k), Image.LANCZOS)
    wim = cached(e, 'wim', _word)
    wy = max(c.fy + c.fw * 1.25 + sz * 0.5, H * 0.62)
    wy = min(wy, H * 0.82)
    c2 = Ctx(); c2.W, c2.H, c2.img, c2.m, c2.fx, c2.fy, c2.fw = W, H, img, m, c.fx, c.fy, c.fw
    if fi >= 1:
        sc = 1 + 0.35 * (1 - ease_out(clamp((c.lt - 1 / c.fps) / 0.12)))
        place(c2, wim, W / 2, wy, sc, 0, 1.0, guard=True)
    img = c2.img
    # camera shake (decays), slight punch zoom
    sh = math.exp(-c.lt * 9)
    rnd = random.Random(fi * 13 + 1)
    dx, dy = rnd.uniform(-1, 1) * 16 * s * sh, rnd.uniform(-1, 1) * 12 * s * sh
    z = 1.035 + 0.05 * sh
    M = cv2.getRotationMatrix2D((W / 2, H / 2), rnd.uniform(-1, 1) * 0.8 * sh, z); M[0, 2] += dx; M[1, 2] += dy
    c.img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


# ===================================================================== ay-code-body

_PR_CODE = """const campaign = { objective: 'ЛІДИ', budget: 'тест 3 дні', placement: 'reels' };
audience.add({ age: [25, 45], interests: ['таргет', 'Meta Ads', 'бізнес'], geo: 'UA' });
creative.render({ hook: 'Стоп, це про тебе', format: '9:16', captions: true, cta: 'Записатися' });
if (cpl > target) { creative.rotate(); adset.pause('втома креативу'); }
pixel.track('Lead', { source: '@your.handle', form: 'анкета' });
for (const ad of ads) { ad.test({ variants: 3, metric: 'CTR', days: 4 }); }
const offer = expert.build({ weeks: 6, format: 'курс', calls: 'щотижня' });
report.send({ spend, leads, cpl, roas, insights: 'що масштабувати' });
export default function reel() { return hook + value + proof + cta; }
const funnel = ['рілс', 'профіль', 'директ', 'анкета', 'дзвінок'];
await meta.ads.create({ name: 'лідген_весна', bid: 'lowest_cost', optimise: 'leads' });
style.body = { color: '#D2DB76', accent: '#FFC3CC', background: '#070c07', font: 'Gilroy' };
"""


def _pr_atlas(chars, size, cw, ch):
    f = ay_font('mm', size)
    asc = f.getmetrics()[0]
    out = np.zeros((len(chars), ch, cw), np.float32)
    for i, chr_ in enumerate(chars):
        im = Image.new('L', (cw, ch), 0)
        ImageDraw.Draw(im).text((cw / 2, ch * 0.52), chr_, font=f, fill=255, anchor='mm')
        out[i] = np.asarray(im, np.float32) / 255
    return out


@effect('ay-code-body', 'background goes dark with code, and you are rendered as mono characters, made of code')
def fx_ay_code_body(c, e):
    W, H = c.W, c.H; s = W / 1080; st = e.state
    size = float(e.o.get('size', 17)) * s
    if 'atlas' not in st:
        f = ay_font('mm', size)
        cw = max(4, int(round(f.getlength('M')))); chh = max(8, int(round(size * 1.28)))
        code = str(e.o.get('code') or _PR_CODE).replace('\n', '   ')
        chars = sorted(set(code) | set(' '))
        st['cw'], st['ch'] = cw, chh
        st['atlas'] = _pr_atlas(chars, size, cw, chh)
        st['cols'], st['rows'] = W // cw + 1, H // chh + 1
        idx = {ch_: i for i, ch_ in enumerate(chars)}
        st['stream'] = np.array([idx[ch_] for ch_ in code], np.int32)
        rnd = np.random.default_rng(4)
        st['roff'] = rnd.integers(0, len(code), st['rows'])
        st['rspd'] = rnd.uniform(3, 9, st['rows']) * rnd.choice([-1, 1], st['rows'])
        st['rbri'] = np.clip(rnd.normal(0.13, 0.045, st['rows']), 0.06, 0.28)
        st['rin'] = rnd.random((st['rows'], st['cols'])).astype(np.float32)
        st['rout'] = rnd.random((st['rows'], st['cols'])).astype(np.float32)
        st['space'] = idx[' ']
    cw, chh, rows, cols = st['cw'], st['ch'], st['rows'], st['cols']
    atlas, stream = st['atlas'], st['stream']
    n = len(stream)
    lt, d = c.lt, e.d
    # per-cell values
    big = np.zeros((rows * chh, cols * cw, 3), np.float32); big[:H, :W] = c.img
    bm = np.zeros((rows * chh, cols * cw), np.float32); bm[:H, :W] = c.m
    small = cv2.resize(big, (cols, rows), interpolation=cv2.INTER_AREA)
    msk = cv2.resize(bm, (cols, rows), interpolation=cv2.INTER_AREA)
    g = _pr_gray(small)
    sel = msk > 0.5
    if sel.sum() > 20:
        lo, hi = np.percentile(g[sel], [4, 97]); v = np.clip((g - lo) / max(0.05, hi - lo), 0, 1)
    else: v = g
    v = _pr_clahe(v, clip=2.6, tiles=4)
    # characters: one code stream per row (background rows scroll, she stays steady so she reads)
    ci = np.arange(cols)[None, :]
    bg_i = (st['roff'][:, None] + ci + (st['rspd'][:, None] * lt).astype(np.int64)) % n
    p_i = (st['roff'][:, None] * 7 + ci) % n
    pm = msk > 0.45
    gi = np.where(pm, p_i, bg_i)
    gi = stream[gi]
    rnd = np.random.default_rng(int(lt * c.fps) + 1)
    # appearance / dissolve per cell
    t_in = float(e.o.get('in', min(0.35, d * 0.3))); t_out = float(e.o.get('out', min(0.3, d * 0.28)))
    pin = clamp(lt / t_in) if t_in > 0 else 1
    pout = clamp((d - lt) / t_out) if t_out > 0 else 1
    a_cell = np.clip((pin * 1.25 - st['rin']) / 0.25, 0, 1) * np.clip((pout * 1.25 - st['rout']) / 0.25, 0, 1)
    resolving = (a_cell > 0) & (a_cell < 1)
    scram = rnd.integers(0, len(atlas), (rows, cols))
    gi = np.where(resolving | (rnd.random((rows, cols)) < 0.012), scram, gi)
    # colours
    lime = np.float32(AY['lime']) / 255; cream = np.float32(AY['cream']) / 255; pink = np.float32(AY['pink']) / 255
    pinkd = np.float32(AY['pink_dk']) / 255; green = np.float32(AY['green']) / 255; c1 = np.float32(AY['c1']) / 255
    fg = np.zeros((rows, cols, 3), np.float32); cb = np.zeros((rows, cols, 3), np.float32) + c1
    bri = st['rbri'][:, None, None]
    fg[:] = green * bri * 1.5
    # render the glyph grid
    G = atlas[gi]                                    # rows, cols, ch, cw
    G = G.transpose(0, 2, 1, 3).reshape(rows * chh, cols * cw)[:H, :W]
    up = lambda a: np.repeat(np.repeat(a, chh, 0), cw, 1)[:H, :W]
    A = up(a_cell)[..., None]
    # her tones at pixel resolution, so the code keeps her features (eyes, mouth, hair strands)
    gp = _pr_gray(c.img); sp = c.m > 0.5
    if sp.sum() > 100:
        lo, hi = np.percentile(gp[sp], [3, 98]); gp = np.clip((gp - lo) / max(0.05, hi - lo), 0, 1)
    vp = cv2.GaussianBlur(np.power(gp, 0.85), (0, 0), 1.2 * s)
    mp = cv2.GaussianBlur(_pr_smooth(c.m, 0.35, 0.6).astype(np.float32), (0, 0), 1.0)
    stops = [0.0, 0.25, 0.42, 0.62, 0.8, 1.0]
    cols_ = np.float32([pinkd * 0.6, pinkd * 1.05 + pink * 0.08, lime * 0.5, lime * 0.95, cream * 0.95, cream])
    pc = np.dstack([np.interp(vp, stops, cols_[:, k]) for k in range(3)]).astype(np.float32)
    hiA = (_pr_smooth(vp, float(e.o.get('hi', 0.6)), float(e.o.get('hi', 0.6)) + 0.1) * mp)[..., None]          # brightest skin: inverse cells (cream, dark glyph)
    FGb = up(fg)
    FG = FGb * (1 - mp[..., None]) + pc * mp[..., None]
    FG = FG * (1 - hiA) + c1 * hiA
    D = ease_inout(pin) * ease_inout(pout)
    out = c.img * (1 - D) + c1 * D
    # a faint tone under her glyphs (her image glowing through the code), stronger on the light planes
    tint = (mp[..., None] * (0.10 + 0.26 * vp[..., None] ** 1.5)) * A
    out = out * (1 - tint) + pc * tint
    HB = hiA * A * up(pm.astype(np.float32))[..., None]
    out = out * (1 - HB) + cream * (0.86 + 0.14 * vp[..., None]) * HB
    Ga = G[..., None] * A
    c.img = out * (1 - Ga) + FG * Ga
