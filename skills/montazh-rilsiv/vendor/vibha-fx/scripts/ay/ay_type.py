# ay-* type group: big typographic set pieces (day dial, orbit ring, letter dive, sketch words, post wall).
# Exec'd by ay_fx.py inside fx.py's globals: uses place / comp / cached / ease_* / glass / shadowed and the ay_* helpers.
# Own helpers are prefixed _ty_.

from fontTools.ttLib import TTFont as _TyTT
from fontTools.pens.basePen import BasePen as _TyBasePen

_TY_GLYPH_CACHE = {}
_TY_INK = (22, 52, 30)          # deep green ink for light paper
_TY_INK2 = (64, 78, 52)         # softer green-grey ink (labels)


class _TyFlat(_TyBasePen):
    """Flattens a glyph outline into polylines (font units)."""

    def __init__(self, gs, steps=12):
        super().__init__(gs); self.cs = []; self.cur = None; self.st = steps

    def _moveTo(self, p): self.cur = [p]; self.cs.append(self.cur)

    def _lineTo(self, p): self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]; n = self.st
        for i in range(1, n + 1):
            t = i / n; mt = 1 - t
            self.cur.append((mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                             mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]; n = self.st
        for i in range(1, n + 1):
            t = i / n; mt = 1 - t
            self.cur.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0], mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self): pass

    def _endPath(self): pass


def _ty_glyphs(kind, text, wght=None):
    """Vector outlines of a line of text: list of (char, [contours as float arrays, font units, y up], x offset) + metrics."""
    path = AY_FONT[kind]
    key = (path, text, wght)
    if key in _TY_GLYPH_CACHE: return _TY_GLYPH_CACHE[key]
    tt = _TyTT(path)
    if wght and 'fvar' in tt:
        from fontTools.varLib import instancer
        tt = instancer.instantiateVariableFont(tt, {'wght': wght})
    upm = tt['head'].unitsPerEm; cmap = tt.getBestCmap(); gs = tt.getGlyphSet()
    pf = ImageFont.truetype(path, upm)
    if wght:
        try: pf.set_variation_by_axes([wght])
        except Exception: pass
    out = []
    for i, ch in enumerate(text):
        x = pf.getlength(text[:i])
        pen = _TyFlat(gs)
        g = cmap.get(ord(ch))
        if g: gs[g].draw(pen)
        out.append((ch, [np.float32(cn) for cn in pen.cs if len(cn) > 2], x))
    os2 = tt['OS/2']
    res = dict(chars=out, adv=pf.getlength(text), upm=upm, xh=getattr(os2, 'sxHeight', 0) or upm * 0.5,
               cap=getattr(os2, 'sCapHeight', 0) or upm * 0.7)
    _TY_GLYPH_CACHE[key] = res
    return res


def _ty_layout(G, size, x0, base, sy=1.0):
    """Glyph contours in px (y down) for a font size, origin x0 / baseline (sy: vertical stretch, a display-condensed look)."""
    s = size / G['upm']
    return [[np.stack([x0 + (cn[:, 0] + x) * s, base - cn[:, 1] * s * sy], 1) for cn in cs] for ch, cs, x in G['chars']]


def _ty_clip(p, x0, y0, x1, y1):
    """Sutherland-Hodgman: clip a closed polygon (N, 2) to a rectangle (keeps huge zoomed glyphs well-behaved in fillPoly)."""
    for axis, lim, keep_lt in ((0, x0, False), (0, x1, True), (1, y0, False), (1, y1, True)):
        if len(p) == 0: break
        q = np.roll(p, 1, 0); a, b = p[:, axis], q[:, axis]
        ins_p = (a <= lim) if keep_lt else (a >= lim); ins_q = (b <= lim) if keep_lt else (b >= lim)
        out = []
        den = np.where(np.abs(a - b) < 1e-9, 1e-9, a - b)
        t = (lim - b) / den
        X = q + (p - q) * t[:, None]
        for i in range(len(p)):
            if ins_p[i]:
                if not ins_q[i]: out.append(X[i])
                out.append(p[i])
            elif ins_q[i]: out.append(X[i])
        p = np.array(out, np.float32).reshape(-1, 2)
    return p


def _ty_fill(shape, contours, val=255, ss=1.0, ox=0.0, oy=0.0):
    """Anti-aliased NON-ZERO fill of a glyph's contours -> uint8 mask (h, w). Fonts draw some letters as one
    self-overlapping contour (Playfair «е»), which an even-odd fill (cv2.fillPoly) breaks; matplotlib's Agg does it right."""
    from matplotlib.backends.backend_agg import RendererAgg
    from matplotlib.path import Path as _MPath
    from matplotlib.transforms import IdentityTransform
    h, w = shape
    vs, cs = [], []
    for cn in contours:
        p = (cn - (ox, oy)) * ss
        # Agg mis-fills paths that run far off the canvas: clip to it first (Sutherland-Hodgman keeps the winding inside)
        if p[:, 0].min() < -4 or p[:, 1].min() < -4 or p[:, 0].max() > w + 4 or p[:, 1].max() > h + 4:
            p = _ty_clip(p.astype(np.float32), -4, -4, w + 4, h + 4)
        if len(p) < 3: continue
        vs.append(np.vstack([p, p[:1]])); cs.append(np.r_[_MPath.MOVETO, np.full(len(p) - 1, _MPath.LINETO), _MPath.CLOSEPOLY])
    if not vs: return np.zeros(shape, np.uint8)
    v = np.concatenate(vs).astype(np.float64); v[:, 1] = h - v[:, 1]          # Agg's y axis points up
    v = np.clip(v, -1e6, 1e6)
    r = RendererAgg(w, h, 72); gc = r.new_gc(); gc.set_antialiased(True); gc.set_linewidth(0)
    r.draw_path(gc, _MPath(v, np.concatenate(cs).astype(np.uint8)), IdentityTransform(), (1, 1, 1, 1))
    a = np.asarray(r.buffer_rgba())[..., 3]
    return (a.astype(np.float32) * (val / 255.0)).astype(np.uint8) if val != 255 else a.copy()


def _ty_grad(h, stops):
    """Vertical colour ramp (h, 3) float 0..1 from [(pos, rgb), ...]."""
    ys = np.linspace(0, 1, h)
    out = np.zeros((h, 3), np.float32)
    for ch in range(3):
        out[:, ch] = np.interp(ys, [p for p, _ in stops], [col[ch] for _, col in stops]) / 255
    return out


def _ty_star(size, col=(255, 255, 255)):
    """A soft 4-point sparkle."""
    S = int(size * 2) | 1; k = 2; im = Image.new('L', (S * k, S * k), 0); d = ImageDraw.Draw(im); c0 = S * k / 2
    a, b = S * k * 0.5, S * k * 0.07
    d.polygon([(c0, c0 - a), (c0 + b, c0 - b), (c0 + a, c0), (c0 + b, c0 + b), (c0, c0 + a), (c0 - b, c0 + b), (c0 - a, c0), (c0 - b, c0 - b)], fill=255)
    im = im.resize((S, S), Image.LANCZOS)
    glow = im.filter(ImageFilter.GaussianBlur(S * 0.12))
    al = np.maximum(np.asarray(im, np.float32), np.asarray(glow, np.float32) * 1.4).clip(0, 255).astype(np.uint8)
    out = Image.new('RGBA', (S, S), tuple(col) + (0,)); out.putalpha(Image.fromarray(al))
    return out


def _ty_person(c, src, bg=None):
    """Cut-out person over the new background c.img (or bg). The soft mask is choked ~1.5-2 px (at 1080) and feathered,
    and the edge colour is decontaminated: semi-transparent edge pixels take the colour of the person's interior pushed
    outwards (blurred, normalised fill), so the old room does not show as a grey rim. Hair keeps a soft edge."""
    W = c.W; sc = W / 1080
    m = np.clip(c.m, 0, 1).astype(np.float32)
    r = max(1, int(round(1.75 * sc)))
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    a = cv2.GaussianBlur(cv2.erode(m, ker), (0, 0), 1.1 * sc)
    a = np.clip((a - 0.3) / 0.45, 0, 1)                         # steep: the low-confidence fringe goes
    # interior colour pushed outwards: blur(src * w) / blur(w), w = a firmly-inside mask
    q = 2
    ms = cv2.resize(m, (W // q, c.H // q), interpolation=cv2.INTER_AREA)
    w = (cv2.erode(ms, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0.85).astype(np.float32)
    ss = cv2.resize(src, (W // q, c.H // q), interpolation=cv2.INTER_AREA)
    sig = 5 * sc
    num = cv2.GaussianBlur(ss * w[..., None], (0, 0), sig); den = cv2.GaussianBlur(w, (0, 0), sig)[..., None]
    fill = cv2.resize(num / np.maximum(den, 1e-4), (W, c.H), interpolation=cv2.INTER_LINEAR)
    has = cv2.resize(np.clip(den[..., 0] * 6, 0, 1), (W, c.H), interpolation=cv2.INTER_LINEAR)[..., None]
    t = np.clip((m - 0.55) / 0.4, 0, 1)[..., None]              # how sure the pixel is "her"
    col = src * t + (fill * has + src * (1 - has)) * (1 - t)
    # keep the luminance texture of hair strands from the original, take the hue from the interior
    lum = lambda x: x @ np.float32([0.299, 0.587, 0.114])
    col = np.clip(col + ((lum(src) - lum(col)) * 0.2 * (1 - t[..., 0]))[..., None], 0, 1)
    base = c.img if bg is None else bg
    a = a[..., None]
    c.img = base * (1 - a) + col * a


# =====================================================================================================================
# 1. ay-day-dial
# =====================================================================================================================

def _ty_dial(R, unit, word, ink, accent, k=2, part='dial', wa=-42.0):
    """The dial (RGBA, supersampled k x): ticks, rings, italic numbers 1..12, small unit words between (part='dial'),
    or the big curved word on the rim (part='word', same canvas, so it can stay still while the dial turns)."""
    Rk = R * k; S = int(Rk * 2.6); c0 = S / 2
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if part == 'word':
        fw_ = ay_font('i', R * 0.2 * k)
        L = fw_.getlength(word); rad = Rk * 1.06
        x = 0.0; a0 = wa - math.degrees(L / 2 / rad)
        for ch in word:
            cw = fw_.getlength(ch); a = a0 + math.degrees((x + cw / 2) / rad)
            bb = fw_.getbbox(ch); t = Image.new('RGBA', (int(bb[2] - bb[0] + 8 * k), int(fw_.getmetrics()[0] + fw_.getmetrics()[1] + 8 * k)), (0, 0, 0, 0))
            ImageDraw.Draw(t).text((4 * k - bb[0], 4 * k), ch, font=fw_, fill=tuple(accent) + (255,))
            t = t.rotate(-a, Image.BICUBIC, expand=True); ar = math.radians(a); rr_ = rad + R * 0.1 * k
            im.alpha_composite(t, (int(c0 + math.sin(ar) * rr_ - t.width / 2), int(c0 - math.cos(ar) * rr_ - t.height / 2)))
            x += cw
        return im
    col = tuple(ink) + (255,); lw = max(2, int(R * 0.006 * k))
    d.ellipse([c0 - Rk, c0 - Rk, c0 + Rk, c0 + Rk], outline=col, width=lw)
    r2 = Rk * 0.965
    d.ellipse([c0 - r2, c0 - r2, c0 + r2, c0 + r2], outline=tuple(ink) + (140,), width=max(1, lw // 2))
    ri = Rk * 0.6
    d.ellipse([c0 - ri, c0 - ri, c0 + ri, c0 + ri], outline=tuple(ink) + (200,), width=max(1, int(lw * 0.8)))
    ri2 = Rk * 0.575
    d.ellipse([c0 - ri2, c0 - ri2, c0 + ri2, c0 + ri2], outline=tuple(ink) + (90,), width=max(1, lw // 2))
    for i in range(120):                                            # ticks: 120 small, every 10th long
        a = math.radians(i * 3); major = i % 10 == 0; mid = i % 5 == 0
        r0 = Rk * (0.885 if major else 0.915 if mid else 0.935)
        w = lw * (1.3 if major else 0.9 if mid else 0.6)
        sa, ca = math.sin(a), math.cos(a)
        d.line([(c0 + sa * r0, c0 - ca * r0), (c0 + sa * r2, c0 - ca * r2)], fill=tuple(ink) + (255 if major else 190,), width=max(1, int(w)))
    fn = ay_font('i', R * 0.15 * k); fu = ay_font('i', R * 0.062 * k)

    def stamp(s, f, ang, rad, fill):
        bb = f.getbbox(s); tw, th = bb[2] - bb[0], bb[3] - bb[1]
        t = Image.new('RGBA', (int(tw + 8 * k), int(th + 8 * k)), (0, 0, 0, 0))
        ImageDraw.Draw(t).text((4 * k - bb[0], 4 * k - bb[1]), s, font=f, fill=fill)
        t = t.rotate(-ang, Image.BICUBIC, expand=True)
        a = math.radians(ang)
        im.alpha_composite(t, (int(c0 + math.sin(a) * rad - t.width / 2), int(c0 - math.cos(a) * rad - t.height / 2)))

    for i in range(12):
        n = 12 if i == 0 else i
        stamp(str(n), fn, i * 30, Rk * 0.755, col)
        stamp(unit, fu, i * 30 + 15, Rk * 0.765, tuple(ink) + (210,))
    return im


def _ty_door(c, layer, theta, hinge='r'):
    """Warp a full-frame float RGB layer as a door swung open by theta (0 = flat), hinged at the right edge.
    Returns (warped layer, alpha) so the caller can composite it over the frame."""
    W, H = c.W, c.H
    f = 1 / (1 + 0.9 * math.sin(theta)); xl = W - W * math.cos(theta) * f
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst = np.float32([[xl, H / 2 - H / 2 * f], [W, 0], [W, H], [xl, H / 2 + H / 2 * f]])
    M = cv2.getPerspectiveTransform(src, dst)
    lay = cv2.warpPerspective(layer, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    a = cv2.warpPerspective(np.ones((H, W), np.float32), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    # shading: the panel is darker while it is still turned away, plus a soft shadow on the frame left of its edge
    lay *= (1 - 0.35 * math.sin(theta))
    return lay, a, xl


@effect('ay-day-dial', 'the room turns to cream paper with a huge clock dial behind you; it ticks round a notch at a time')
def fx_ay_day_dial(c, e):
    W, H = c.W, c.H; src = c.img.copy()
    unit = str(e.o.get('unit') or 'день'); word = str(e.o.get('text') or 'щодня')
    R = W * float(e.o.get('size', 0.56))
    ink = _TY_INK; acc = AY['pink_dk']
    dial = cached(e, 'dial', lambda: np.asarray(_ty_dial(R, unit, word, ink, acc, 2), np.float32) / 255)
    paper = cached(e, 'paper', lambda: ay_paper(W, H, (244, 241, 230), grain=0.007, seed=11))
    # dial centre: behind the head, a touch left and up so it runs off the left edge
    cx = cached(e, 'cx', lambda: c.fx + W * float(e.o.get('dx', -0.12)))
    cy = cached(e, 'cy', lambda: c.fy + H * float(e.o.get('dy', -0.03)))

    def word_angle():
        # the rim word sits top-left if it fits in the frame, else the nearest free spot along the top of the rim
        if e.o.get('word_at') is not None: return float(e.o['word_at'])
        half = math.degrees(ay_font('i', R * 0.2).getlength(word) / 2 / (R * 1.06))
        for a in (-40, -30, -20, -50, 30, 40, 20, 50, -10, 10):
            ok = True
            for da in (-half, 0, half):
                ar = math.radians(a + da); x = cx + math.sin(ar) * R * 1.16; y = cy - math.cos(ar) * R * 1.16
                if not (W * 0.06 < x < W * 0.94 and H * 0.03 < y < H * 0.6): ok = False
            if ok: return a
        return -40.0
    wordl = cached(e, 'word', lambda: ay_np(_ty_dial(R, unit, word, ink, acc, 2, 'word', word_angle()).resize((dial.shape[1] // 2, dial.shape[0] // 2), Image.LANCZOS)))
    # rotation: one notch (15 deg, number -> word -> number) every `every` s, a mechanical step with a small overshoot
    every = float(e.o.get('every', 0.3)); step = 15.0
    k = max(0.0, (c.lt - 0.32) / every); n = int(k); fr = k - n
    q = clamp(fr / 0.42); mv = ease_back(q) if q < 1 else 1.0
    ang = (n + mv) * step                          # degrees, the dial turns anticlockwise (next day under the pointer)
    akey = round(ang, 1)
    if e.state.get('akey') != akey:
        S2 = dial.shape[0]
        M = cv2.getRotationMatrix2D((S2 / 2, S2 / 2), akey, 1.0)
        rot = cv2.warpAffine(dial, M, (S2, S2), flags=cv2.INTER_LINEAR)
        e.state['rot'] = cv2.resize(rot, (S2 // 2, S2 // 2), interpolation=cv2.INTER_AREA)
        e.state['akey'] = akey
    rot = e.state['rot']
    bg = paper.copy()
    # soft warm light falling from the top, like the reference wall
    lg = cached(e, 'lg', lambda: (1 - 0.06 * np.clip(np.linspace(-0.3, 1.0, H), 0, 1))[:, None, None].astype(np.float32))
    bg *= lg
    Lw = rot.shape[1]; x0 = int(round(cx - Lw / 2)); y0 = int(round(cy - Lw / 2))
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + Lw), min(H, y0 + Lw)
    if xb > xa and yb > ya:
        for lay_ in (rot, wordl):
            L = lay_[ya - y0:yb - y0, xa - x0:xb - x0]; al = L[..., 3:4]
            bg[ya:yb, xa:xb] = bg[ya:yb, xa:xb] * (1 - al) + L[..., :3] * al
    # the pendulum: a thin line from the top edge to the rim, with a small pink pointer at its end
    top = cy - R
    if top > 0:
        k2 = 2; pw = 40
        pim = Image.new('RGBA', (pw * k2, int(top + 30) * k2), (0, 0, 0, 0)); d = ImageDraw.Draw(pim)
        d.line([(pw * k2 / 2, 0), (pw * k2 / 2, top * k2)], fill=tuple(ink) + (255,), width=max(2, int(W * 0.0028 * k2)))
        tw = W * 0.011 * k2; ty = top * k2
        d.polygon([(pw * k2 / 2 - tw, ty - tw * 1.6), (pw * k2 / 2 + tw, ty - tw * 1.6), (pw * k2 / 2, ty + tw * 0.4)], fill=tuple(acc) + (255,))
        pim = ay_np(pim.resize((pw, int(top + 30)), Image.LANCZOS))
        px0 = int(round(cx - pw / 2)); h_ = min(H, pim.shape[0])
        xa, xb = max(0, px0), min(W, px0 + pw)
        if xb > xa:
            P = pim[:h_, xa - px0:xb - px0]; al = P[..., 3:4]
            bg[:h_, xa:xb] = bg[:h_, xa:xb] * (1 - al) + P[..., :3] * al
    # door swing in and out
    t_in, t_out = 0.34, 0.26
    if c.lt < t_in: th = (1 - ease_out(c.lt / t_in)) * math.radians(78)
    elif c.lt > e.d - t_out: th = ease_inout((c.lt - (e.d - t_out)) / t_out) ** 1.5 * math.radians(80)
    else: th = 0.0
    if th < 1e-3:
        c.img = bg
    else:
        lay, a, xl = _ty_door(c, bg, th)
        # contact shadow on the room, just left of the panel edge
        xx = np.arange(W, dtype=np.float32)[None, :]
        sh = np.clip(1 - (xl - xx) / (W * 0.08), 0, 1) * (xx < xl) * 0.35 * min(1.0, math.sin(th) * 3)
        base = src * (1 - sh[..., None])
        c.img = base * (1 - a[..., None]) + lay * a[..., None]
    _ty_person(c, src)


# =====================================================================================================================
# 2. ay-orbit-ring
# =====================================================================================================================

_ty_fc = {}


def _ty_font(kind, size, wght):
    """A brand font at a given weight (Playfair is variable)."""
    key = (kind, int(size), wght)
    if key not in _ty_fc:
        f = ImageFont.truetype(AY_FONT[kind], max(6, int(size)))
        try: f.set_variation_by_axes([wght])
        except Exception: pass
        _ty_fc[key] = f
    return _ty_fc[key]


def _ty_front(c, im, x, y, a, rot=0.0):
    """Place in front of her, hidden only over the face itself (forehead to chin), not over the neck / chest."""
    fw = c.fw; c.fw = fw * 0.5
    try: place(c, im, x, y, 1.0, rot, a, guard=True)
    finally: c.fw = fw


def _ty_metal_letter(ch, size, look='lime', k=2):
    """A chunky serif capital in polished metal (lime->cream or pink->cream): vertical ramp, a bevel lit from the top
    left (highlight band on the upper edges, darker lower edges), a gloss streak, a thin dark outline, a soft drop shadow."""
    f = _ty_font('s', size * k, 900)
    bb = f.getbbox(ch); pad = int(size * 0.14 * k)
    w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).text((pad - bb[0], pad - bb[1]), ch, font=f, fill=255)
    rim = Image.new('L', (w, h), 0); ImageDraw.Draw(rim).text((pad - bb[0], pad - bb[1]), ch, font=f, fill=255, stroke_width=max(2, int(size * 0.012 * k)))
    if look == 'pink':
        stops = [(0, (255, 246, 240)), (0.3, (255, 204, 212)), (0.48, (226, 140, 160)), (0.54, (255, 236, 238)), (0.75, (244, 172, 188)), (1, (176, 74, 100))]
        edge, dark = (110, 34, 56), (120, 40, 64)
    else:
        stops = [(0, (255, 255, 244)), (0.3, (238, 242, 186)), (0.48, (194, 202, 112)), (0.54, (252, 252, 228)), (0.75, (222, 228, 146)), (1, (118, 128, 52))]
        edge, dark = (34, 44, 14), (60, 72, 18)
    t0, t1 = pad, h - pad
    ys = np.clip((np.arange(h) - t0) / max(1, t1 - t0), 0, 1)
    g = np.stack([np.interp(ys, [p_ for p_, _ in stops], [cc[i] for _, cc in stops]) for i in range(3)], 1).astype(np.float32)
    rgbm = np.broadcast_to(g[:, None, :], (h, w, 3)).copy()
    ma = np.asarray(m, np.float32) / 255; ra = np.asarray(rim, np.float32) / 255
    # bevel: the blurred glyph's slope, lit from the top left
    mb = cv2.GaussianBlur(ma, (0, 0), size * k * 0.03)
    gx = cv2.Sobel(mb, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(mb, cv2.CV_32F, 0, 1, ksize=3)
    lit = (0.55 * gx + 0.83 * gy); lit /= max(1e-4, np.abs(lit).max())
    rgbm += np.clip(lit, 0, 1)[..., None] * 120                      # bright upper bevel
    rgbm = rgbm * (1 - np.clip(-lit, 0, 1)[..., None] * 0.55) + np.float32(dark) * np.clip(-lit, 0, 1)[..., None] * 0.55
    # gloss streak across the face
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    band = np.exp(-(((xx * 0.5 + yy) / max(1, h) - 0.36) / 0.05) ** 2)
    rgbm = np.clip(rgbm + band[..., None] * 70 * (mb > 0.6)[..., None], 0, 255)
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = rgbm * ma[..., None] + np.float32(edge) * (1 - ma[..., None])
    out[..., 3] = np.maximum(ma, ra) * 255
    im = Image.fromarray(out.clip(0, 255).astype(np.uint8), 'RGBA').resize((w // k, h // k), Image.LANCZOS)
    return shadowed(im, blur=max(4, int(size * 0.045)), dy=int(size * 0.05), alpha=120)


@effect('ay-orbit-ring', 'the letters of a word orbit your head on a tilted 3D ring, passing behind you and in front')
def fx_ay_orbit_ring(c, e):
    W, H = c.W, c.H
    word = str(e.o.get('text') or 'ТАРГЕТ').upper()
    letters = [ch for ch in word if ch.strip()]
    n = len(letters); look = str(e.o.get('look', 'lime'))
    size = W * float(e.o.get('size', 0.28))
    imgs = cached(e, 'L', lambda: [[(im := _ty_metal_letter(ch, size, look)), im.filter(ImageFilter.GaussianBlur(size * 0.008)),
                                    im.filter(ImageFilter.GaussianBlur(size * 0.022))] for ch in letters])
    star = cached(e, 'st', lambda: _ty_star(W * 0.026, AY['cream'] if look != 'pink' else (255, 236, 238)))
    kin = ease_out(c.lt / 0.4); al = kin * fade(c, e, 0.22)
    Rx = W * float(e.o.get('radius', 0.6)) * (0.82 + 0.18 * kin); Ry = Rx * 0.22
    cx = c.fx; cy = c.fy + c.fw * float(e.o.get('drop', 0.56))
    roll = math.radians(float(e.o.get('tilt', -6)))
    adv = cached(e, 'adv', lambda: [im[0].width * 0.7 for im in imgs])
    dphi = min(math.radians(38), float(np.mean(adv)) * 0.98 / Rx)
    # the spin slows down while the word faces the camera (reads clearly), and speeds up on the way round
    u = c.lt / e.d - 0.55
    sweep = math.radians(float(e.o.get('sweep', 210)))
    ph0 = sweep * (0.42 * u + 2.3 * u ** 3)
    base = math.pi / 2 + (n - 1) / 2 * dphi - ph0
    items = []
    for j in range(n):
        ph = base - j * dphi
        x, y = Rx * math.cos(ph), Ry * math.sin(ph)
        X = cx + x * math.cos(roll) - y * math.sin(roll); Y = cy + x * math.sin(roll) + y * math.cos(roll)
        items.append((math.sin(ph), j, X, Y))
    items.sort()
    for z, j, X, Y in items:
        s = 0.72 + 0.34 * (z + 1) / 2                        # perspective
        lvl = 0 if z > -0.2 else (1 if z > -0.65 else 2)
        im = imgs[j][lvl]
        sq = 0.4 + 0.6 * abs(z) ** 0.55                       # edge-on at the sides of the ring
        wq = max(1, int(im.width * s * sq)); hq = max(1, int(im.height * s))
        imr = im.resize((wq, hq), Image.LANCZOS)
        if z < 0:
            imr = Image.fromarray((np.asarray(imr, np.float32) * np.float32([0.86, 0.86, 0.86, 1])).astype(np.uint8), 'RGBA')
        a = al * (0.7 + 0.3 * (z + 1) / 2)
        if z < 0: place(c, imr, X, Y, 1.0, math.degrees(-roll) * 0.6, a, behind=True)
        else: _ty_front(c, imr, X, Y, a, math.degrees(-roll) * 0.6)
    # faint sparkles riding the ring
    rnd = random.Random(5)
    for i in range(16):
        ph = rnd.uniform(0, 2 * math.pi) - ph0 * 0.9
        x, y = Rx * 1.03 * math.cos(ph), Ry * 1.1 * math.sin(ph) - rnd.uniform(-0.2, 0.5) * size * 0.6
        X = cx + x * math.cos(roll) - y * math.sin(roll); Y = cy + x * math.sin(roll) + y * math.cos(roll)
        tw = max(0.0, math.sin(rnd.uniform(0, 6.3) + c.lt * rnd.uniform(6, 10))) ** 3
        if tw < 0.05: continue
        z = math.sin(ph); sc_ = 0.35 + 0.75 * tw
        st = star.resize((max(1, int(star.width * sc_)),) * 2, Image.BILINEAR)
        if z < 0: place(c, st, X, Y, 1.0, 0, al * tw * 0.8, behind=True)
        else: _ty_front(c, st, X, Y, al * tw * 0.9)


# =====================================================================================================================
# 3. ay-letter-dive
# =====================================================================================================================

@effect('ay-letter-dive', 'a giant serif word on cream paper with your video inside the letters; the camera dives into one letter')
def fx_ay_letter_dive(c, e):
    W, H = c.W, c.H; src = c.img.copy()
    word = str(e.o.get('text') or 'ціна.')
    # lines: split on |; a long single word (> 6 letters) breaks into two lines so the letters stay giant
    if '|' in word: lines = [x for x in word.split('|') if x]
    elif len(word) > 6 and str(e.o.get('lines', 'auto')) != '1':
        h_ = (len(word) + 1) // 2; lines = [word[:h_], word[h_:]]
    else: lines = [word]
    wght = int(e.o.get('weight', 860))
    Gs = cached(e, 'G', lambda: [_ty_glyphs('s', ln, wght) for ln in lines])
    paper = cached(e, 'paper', lambda: ay_paper(W, H, (244, 241, 230), grain=0.007, seed=5))
    sy = float(e.o.get('stretch', 1.85))          # display-condensed: taller letters, the word fills the frame

    def lay():
        size = min(min(W * 0.94 / (G['adv'] / G['upm']) for G in Gs), W * 0.9)
        G0 = Gs[0]; xh = G0['xh'] * size / G0['upm'] * sy
        lead = xh * 1.62
        y_c = H * float(e.o.get('y', 0.5))
        bases = [y_c + xh / 2 + (i - (len(Gs) - 1) / 2) * lead for i in range(len(Gs))]
        P = []
        for G, bs in zip(Gs, bases):
            P += _ty_layout(G, size, (W - G['adv'] * size / G['upm']) / 2, bs, sy)
        idxs = [i for i, cs in enumerate(P) if cs]
        want = int(e.o.get('into', 2)) - 1
        ti = idxs[max(0, min(len(idxs) - 1, want))]
        # the deepest point inside the target letter: there the dive lands
        q = 2; mk = _ty_fill((H // q, W // q), P[ti], 255, 1 / q)
        bm = (mk > 127).astype(np.uint8)
        nl, lab_, st_, _ = cv2.connectedComponentsWithStats(bm)
        if nl > 2: bm = (lab_ == 1 + int(np.argmax(st_[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)   # the body, not a dot
        dt = cv2.distanceTransform(bm, cv2.DIST_L2, 5)
        yy, xx = np.unravel_index(int(np.argmax(dt)), dt.shape)
        allp = np.concatenate([cn for cs in P for cn in cs])
        hgt = allp[:, 1].max() - allp[:, 1].min()
        return P, ti, (xx * q + q / 2, yy * q + q / 2), max(4.0, float(dt.max()) * q), (allp[:, 1].max() + allp[:, 1].min()) / 2, hgt
    P, ti, (px, py), r, wy, whgt = cached(e, 'lay', lay)
    n = len(P)
    t_dive = max(0.55, e.d - float(e.o.get('dive', 0.42)) - 0.1); dur = float(e.o.get('dive', 0.42))
    p = clamp((c.lt - t_dive) / dur)
    if p >= 1:
        return                                                     # her full frame is back
    q = p * p * p * (p * (6 * p - 15) + 10)                        # smootherstep
    Zmax = 1.35 * math.hypot(W, H) / 2 / r
    Z = math.exp(math.log(Zmax) * (p ** 1.6 * (1 - p) + q * p))     # accelerating dive
    Z *= 1 + 0.07 * ease_inout(c.lt / t_dive)                       # a slow push while the word writes itself
    ax, ay = px + (W / 2 - px) * q, py + (H / 2 - py) * q
    # her video inside the letters: slightly enlarged at rest, settling to the real frame as the dive lands
    # at rest her face sits on the word's line, enlarged; it settles to the real frame as the dive lands
    # her face fills the height of the word (eyes to chin visible inside the big letters)
    sv0 = float(e.o.get('zoom', 0) or clamp(whgt / (c.fw * 1.25), 1.0, 1.9)); sv = sv0 + (1.0 - sv0) * q
    tx0, ty0 = W / 2 - c.fx * sv0, wy - c.fy * sv0
    M = np.float32([[sv, 0, tx0 * (1 - q)], [0, sv, ty0 * (1 - q)]])
    vid = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) if q < 0.999 else src
    # letters write in left to right
    step = min(0.09, max(0.05, (t_dive - 0.25) / max(1, n)))
    m = np.zeros((H, W), np.float32)
    for j in range(n):
        if not P[j]: continue
        aj = ease_out((c.lt - 0.04 - j * step) / 0.2)
        if aj <= 0: break
        dy = (1 - aj) * H * 0.025
        cs = [np.stack([ax + (cn[:, 0] - px) * Z, ay + (cn[:, 1] + dy - py) * Z], 1) for cn in P[j]]
        if Z > 3 and j != ti:
            # far-off letters: skip the ones that left the frame
            allp = np.concatenate(cs)
            if allp[:, 0].max() < 0 or allp[:, 0].min() > W or allp[:, 1].max() < 0 or allp[:, 1].min() > H: continue
        mj = _ty_fill((H, W), cs, 255).astype(np.float32) / 255 * aj
        m = np.maximum(m, mj)
    shade = (1 - q)
    bg = paper
    if shade > 0.02:
        sh = cv2.GaussianBlur(np.roll(m, int(H * 0.006), 0), (0, 0), W * 0.008) * 0.16 * shade
        bg = paper * (1 - sh[..., None])
    c.img = bg * (1 - m[..., None]) + vid * m[..., None]
    if c.lt < 0.08:
        kk = ease_out(c.lt / 0.08); c.img = c.img * kk + src * (1 - kk)


# =====================================================================================================================
# 4. ay-sketch-words
# =====================================================================================================================

def _ty_wobble(pts, amp, seed, closed=True):
    """Pencil wobble: shift a polyline along its normals by smooth noise of the arc length."""
    d = np.diff(np.vstack([pts, pts[:1]]) if closed else pts, axis=0)
    seg = np.hypot(d[:, 0], d[:, 1]); s = np.concatenate([[0], np.cumsum(seg)])[:len(pts)]
    nx, ny = -d[:, 1] / np.maximum(seg, 1e-3), d[:, 0] / np.maximum(seg, 1e-3)
    if len(nx) < len(pts): nx, ny = np.append(nx, nx[-1]), np.append(ny, ny[-1])
    rnd = np.random.default_rng(seed); ph = rnd.uniform(0, 6.3, 3)
    w = (np.sin(s / 23 + ph[0]) * 0.55 + np.sin(s / 9.5 + ph[1]) * 0.3 + np.sin(s / 61 + ph[2]) * 0.45) * amp
    return np.stack([pts[:, 0] + nx[:len(pts)] * w, pts[:, 1] + ny[:len(pts)] * w], 1)


def _ty_resample(cn, step):
    """Even spacing along a closed contour (so wobble and partial drawing look natural)."""
    p = np.vstack([cn, cn[:1]]); d = np.hypot(*np.diff(p, axis=0).T); s = np.concatenate([[0], np.cumsum(d)])
    L = s[-1]
    if L < step * 2: return cn, L
    t = np.arange(0, L, step)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], 1), L


@effect('ay-sketch-words', 'ruled notebook paper behind you; a giant outlined word sketches itself in pencil with hatching')
def fx_ay_sketch_words(c, e):
    W, H = c.W, c.H; src = c.img.copy()
    word = str(e.o.get('text') or 'ідея'); label = str(e.o.get('label') or 'скетч')
    col = AY['pink_dk']; k = 2
    G = cached(e, 'G', lambda: _ty_glyphs('s', word, 480))
    paper = cached(e, 'paper', lambda: ay_paper(W, H, (244, 241, 230), grain=0.006, seed=8, lines=int(W * 0.062), line_col=(70, 84, 60), line_a=0.17))

    def lay():
        size = min(W * 0.9 / (G['adv'] / G['upm']), W * 0.62)
        x0 = W * 0.055
        base = H * float(e.o.get('y', 0.29))
        P = _ty_layout(G, size, x0, base)
        allp = np.concatenate([cn for cs in P for cn in cs])
        pad = W * 0.03
        bx0, by0 = max(0, allp[:, 0].min() - pad), max(0, allp[:, 1].min() - pad)
        bx1, by1 = min(W, allp[:, 0].max() + pad), min(H, allp[:, 1].max() + pad)
        bw, bh = int(bx1 - bx0), int(by1 - by0)
        # per letter: resampled contours (2x canvas coords), a glyph mask and its hatching
        let = []
        sp = W * 0.0125 * k; rnd = random.Random(4)
        for j, cs in enumerate(P):
            if not cs: let.append(None); continue
            gm = _ty_fill((bh * k, bw * k), cs, 255, k, bx0, by0)
            # the visible outline = contours of the filled glyph (fonts overlap contours inside a letter)
            fc, _ = cv2.findContours((gm > 127).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
            cc = []
            for f_ in fc:
                if len(f_) < 12: continue
                f_ = f_[:, 0, :].astype(np.float32)
                f_ = np.stack([cv2.GaussianBlur(np.tile(f_[:, i], 3)[None, :], (0, 0), 2.2)[0, len(f_):2 * len(f_)] for i in (0, 1)], 1)
                cc.append(_ty_resample(f_, 3.0 * k))
            hat = np.zeros_like(gm)
            pts = np.concatenate(cs); lx0, lx1 = (pts[:, 0].min() - bx0) * k, (pts[:, 0].max() - bx0) * k
            u = lx0 - bh * k
            while u < lx1 + bh * k:
                j0 = rnd.uniform(-1.5, 1.5) * k
                cv2.line(hat, (int((u + j0) * 16), int(bh * k * 16)), (int((u + bh * k + rnd.uniform(-2, 2) * k) * 16), 0), 255,
                         max(1, int(1.7 * k)), cv2.LINE_AA, 4)
                u += sp * rnd.uniform(0.85, 1.15)
            hat = np.minimum(hat, gm)
            let.append(dict(cc=cc, hat=hat, x0=lx0, x1=lx1))
        return (int(bx0), int(by0), bw, bh), let
    (bx0, by0, bw, bh), let = cached(e, 'lay', lay)
    n = len(let)
    # paper slides in from the left, and out to the right at the end
    t_in, t_out = 0.3, 0.24
    if c.lt < t_in: off = -(1 - ease_out(c.lt / t_in)) * W
    elif c.lt > e.d - t_out: off = ease_inout((c.lt - (e.d - t_out)) / t_out) * W * 1.02
    else: off = 0.0
    # draw the sketch (2x region canvas, ink alpha)
    ink = np.zeros((bh * k, bw * k), np.float32)
    boil = int(c.lt * 8)                                            # the pencil line "boils" 8x a second
    t0 = 0.18; per = max(0.1, min(0.26, (e.d - 0.75) / max(1, n)))
    for j, L in enumerate(let):
        if L is None: continue
        po = clamp((c.lt - t0 - j * per * 0.7) / (per * 1.6))
        if po <= 0: continue
        po = ease_inout(po)
        cv = np.zeros((bh * k, bw * k), np.uint8); cv2b = np.zeros_like(cv)
        for i, (pts, Lc) in enumerate(L['cc']):
            m_ = max(2, int(len(pts) * po))
            a1 = _ty_wobble(pts, 1.5 * k, 31 * j + i + boil * 7)[:m_]
            a2 = _ty_wobble(pts + (1.2 * k, -0.9 * k), 1.9 * k, 97 * j + i + boil * 5)[:m_]
            cv2.polylines(cv, [np.round(a1 * 16).astype(np.int32)], po >= 0.999, 255, max(1, int(2.8 * k)), cv2.LINE_AA, 4)
            cv2.polylines(cv2b, [np.round(a2 * 16).astype(np.int32)], po >= 0.999, 255, max(1, int(1.1 * k)), cv2.LINE_AA, 4)
        a = np.maximum(cv.astype(np.float32) / 255, cv2b.astype(np.float32) / 255 * 0.55)
        # hatching: a diagonal wipe across the letter after the outline is under way
        ph = clamp((c.lt - t0 - j * per * 0.7 - per * 0.6) / (per * 1.5))
        if ph > 0:
            ph = ease_out(ph)
            xs = np.arange(bw * k, dtype=np.float32)[None, :]; ys = np.arange(bh * k, dtype=np.float32)[:, None]
            front = L['x0'] - bh * k * 0.5 + (L['x1'] - L['x0'] + bh * k) * ph
            wipe = np.clip((front - (xs + (bh * k - ys) * 0.5)) / (10 * k), 0, 1)
            a = np.maximum(a, L['hat'].astype(np.float32) / 255 * wipe * 0.62)
        ink = np.maximum(ink, a)
    ink = cv2.resize(ink, (bw, bh), interpolation=cv2.INTER_AREA)
    bg = paper.copy()
    region = bg[by0:by0 + bh, bx0:bx0 + bw]
    colf = np.float32(col) / 255
    region[:] = region * (1 - ink[..., None]) + colf * ink[..., None]
    # the small italic label
    lab = cached(e, 'lab', lambda: ay_np(ay_text(label, W * 0.1, 'i', fill=(78, 86, 66))))
    la = clamp((c.lt - 0.12) / 0.25)
    if la > 0:
        lh, lw_ = lab.shape[:2]; lx, ly = int(W * 0.065), int(by0 - lh * 0.8 + (1 - ease_out(la)) * H * 0.01)
        ly = max(0, ly)
        R_ = bg[ly:ly + lh, lx:lx + lw_]; A_ = lab[:R_.shape[0], :R_.shape[1]]
        R_[:] = R_ * (1 - A_[..., 3:4] * la) + A_[..., :3] * A_[..., 3:4] * la
    if abs(off) < 0.5:
        c.img = bg
    else:
        sh = int(round(off)); out = src.copy()
        if sh < 0:
            out[:, :W + sh] = bg[:, -sh:]; edge = W + sh
            xx = np.arange(W, dtype=np.float32)[None, :]
            d = np.clip(1 - (xx - edge) / (W * 0.06), 0, 1) * (xx >= edge) * 0.32
            out *= (1 - d[..., None])
        else:
            out[:, sh:] = bg[:, :W - sh]; edge = sh
            xx = np.arange(W, dtype=np.float32)[None, :]
            d = np.clip(1 - (edge - xx) / (W * 0.06), 0, 1) * (xx < edge) * 0.32
            out *= (1 - d[..., None])
        c.img = out
    _ty_person(c, src)


# =====================================================================================================================
# 5. ay-post-wall
# =====================================================================================================================

@effect('ay-post-wall', 'a contribution grid of rounded squares fills up day by day, with a day label and a post counter')
def fx_ay_post_wall(c, e):
    W, H = c.W, c.H
    light = str(e.o.get('look', 'dark')) == 'light'
    unit = str(e.o.get('unit') or 'ДЕНЬ').upper(); label = str(e.o.get('label') or 'ПОСТИ').upper()
    try: to = int(float(str(e.o.get('to', 104)).replace(' ', '')))
    except ValueError: to = 104
    days = int(float(e.o.get('days', 365)))
    cols, rows = int(e.o.get('cols', 26)), 7
    N = cols * rows
    pw = W * 0.9; pad = W * 0.045
    pitch = (pw - 2 * pad) / cols; cell = pitch * 0.8
    head = W * 0.1
    ph_ = pad + head + rows * pitch - (pitch - cell) + pad
    kin = ease_out(c.lt / 0.32); al = kin * fade(c, e, 0.22)
    if al <= 0: return
    pcx = W / 2; pcy = H * float(e.o.get('y', 0.04)) + ph_ / 2 + (1 - kin) * -H * 0.02

    def plan():
        rnd = random.Random(21)
        sc = []
        for i in range(N):
            col_, row_ = i // rows, i % rows
            stripe = 0.5 + 0.5 * math.cos((col_ - row_ * 1.3) / 3.2 * math.pi)
            sc.append(rnd.random() * 0.75 + stripe * 0.6)
        posted = min(to, N)
        order = sorted(range(N), key=lambda i: -sc[i])
        lvl = [0] * N
        for r_, i in enumerate(order[:posted]): lvl[i] = 4 if r_ < posted * 0.18 else 3 if r_ < posted * 0.5 else 2 if r_ < posted * 0.8 else 1
        return lvl, posted
    lvl, posted = cached(e, 'plan', plan)
    fill = ease_inout(clamp((c.lt - 0.18) / max(0.3, e.d - 0.62)))
    reach = fill * N
    tsec = (e.d - 0.62) / N                                          # time per cell, for the pop
    # panel
    if light:
        pan = rrect(pw, ph_, W * 0.04, AY['cream'] + (236,))
        pan = shadowed(pan, blur=int(W * 0.02), dy=int(W * 0.01), alpha=70)
    else:
        pan = glass(c, pw, ph_, W * 0.04, pcx, pcy, amt=0.62, tint=(14, 34, 18), dark=0.5, blur=max(10, W // 36))
    k = 2
    lay = Image.new('RGBA', (int(pw * k), int(ph_ * k)), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    if light:
        empty = (46, 125, 62, 34); undone = (46, 125, 62, 12)
        shades = [None, (184, 206, 166), (120, 170, 112), (46, 125, 62), (22, 70, 34)]
        tx, sub = AY['ink'], _TY_INK
    else:
        empty = (30, 50, 30, 255); undone = (243, 244, 236, 14)
        shades = [None, (64, 92, 44), (118, 146, 62), AY['lime'], AY['lime_hi']]
        tx, sub = AY['tx'], AY['lime']
    gx0 = pad; gy0 = pad + head
    rr = cell * 0.24
    for i in range(N):
        col_, row_ = i // rows, i % rows
        x = gx0 + col_ * pitch; y = gy0 + row_ * pitch
        if i < reach:
            age = (reach - i) * tsec
            s = 0.55 + 0.45 * ease_back(clamp(age / 0.16)) if lvl[i] else 1.0
            colr = (shades[lvl[i]] + (255,)) if lvl[i] else empty
        else:
            s = 1.0; colr = undone
        cc = cell * s; ox = (cell - cc) / 2
        d.rounded_rectangle([(x + ox) * k, (y + ox) * k, (x + ox + cc) * k, (y + ox + cc) * k], rr * s * k, fill=colr)
    # labels: day on the left, the counter on the right
    day = int(round(fill * days)); cnt = int(round(to * (sum(1 for i in range(min(N, int(reach))) if lvl[i]) / max(1, posted))))
    if fill >= 0.999: cnt = to
    f1 = ay_font('mm', W * 0.03 * k)
    s1 = f'{unit} {day}'; xx = gx0 * k
    for ch in s1:
        d.text((xx, (pad + head * 0.5) * k), ch, font=f1, fill=tuple(sub) + (255,), anchor='lm'); xx += f1.getlength(ch) + W * 0.006 * k
    s2 = f'→ {days}'
    d.text((xx + W * 0.012 * k, (pad + head * 0.5) * k), s2, font=f1, fill=tuple(tx) + (90,), anchor='lm')
    f2 = ay_font('hx', W * 0.088 * k); f3 = ay_font('mm', W * 0.022 * k)
    lw3 = sum(f3.getlength(ch) + W * 0.005 * k for ch in label)
    xr = (pw - pad) * k; yb = (pad + head * 0.78) * k
    xx = xr - lw3
    for ch in label:
        d.text((xx, yb), ch, font=f3, fill=tuple(sub) + (255,), anchor='ls'); xx += f3.getlength(ch) + W * 0.005 * k
    d.text((xr - lw3 - W * 0.012 * k, yb + W * 0.004 * k), str(cnt), font=f2, fill=tuple(tx) + (255,), anchor='rs')
    lay = lay.resize((int(pw), int(ph_)), Image.LANCZOS)
    off = (pan.width - lay.width) // 2 if light else 0
    pan.alpha_composite(lay, (off, off))
    place(c, pan, pcx, pcy, 1.0, 0, al, behind=True)
