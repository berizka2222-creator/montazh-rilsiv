# ay-* «ui» group: interface-style overlays from the 2026-11-13 reference reel, in the person's brand.
#   ay-predict-keys  iOS keyboard (dark green glass) types the text with live predictions
#   ay-voice-note    Instagram DM voice message bubble at the top, waveform fills as it plays
#   ay-comment-drop  "Додай коментар…" input types a word, posts, a reply drops in; the word flashes behind her head
#   ay-liquid-glass  CTA ending: glass pill -> notification, glass IG nav bar with a sliding selector, frosted CTA card
#   ay-index         persistent "У ЦЬОМУ ВІДЕО 03 / 07" panel top-right with a moving highlight pill
#   ay-live-cursor   Figma-like selection box dragged around her by a named cursor, handles + size label + guides
# Helpers are prefixed _ui_. Everything is drawn at 2x and LANCZOS-downsampled for clean edges.

import re as _ui_re

_UI_K = 2
_UI_DEEP = (22, 46, 30)           # deep brand green for buttons / play circle on cream
_UI_PANEL = (17, 33, 21)          # panel tint (between c3 and green)
# Real interfaces keep their native look (2026-11-13): iOS keyboard light grey, Instagram white / blue / red, DM violet, Figma blue
IOS = dict(kb=(209, 212, 219), key=(255, 255, 255), spec=(172, 177, 187), ink=(0, 0, 0), shadow=(137, 139, 145), blue=(0, 122, 255), ph=(142, 142, 147), off=(199, 199, 204))
IG = dict(card=(255, 255, 255), ink=(0, 0, 0), sub=(115, 115, 115), heart=(255, 48, 64), heart_off=(38, 38, 38), blue=(0, 149, 246), avatar=(199, 199, 204), dm=(118, 56, 250), ring=(225, 48, 108))
FIGMA = (13, 153, 255)


def _ui_s(c): return c.W / 1080.0


def _ui_a(col, a=255): return tuple(int(v) for v in col[:3]) + (int(a),)


def _ui_down(im, k=_UI_K):
    return im.resize((max(1, round(im.width / k)), max(1, round(im.height / k))), Image.LANCZOS)


def _ui_spring(x, k=7.0, w=10.0):
    """0 -> 1 with a soft overshoot (damped spring)."""
    if x <= 0: return 0.0
    return 1 - math.exp(-k * x) * math.cos(w * x)


def _ui_sm(x): x = clamp(x); return x * x * x * (x * (x * 6 - 15) + 10)


def _ui_seg(t, a, b): return clamp((t - a) / max(1e-6, b - a))


def _ui_vblur(L, amt):
    """Vertical motion blur of a float RGBA layer (premultiplied so edges stay clean)."""
    k = int(amt)
    if k < 2: return L
    ker = np.zeros((k, 1), np.float32) + 1.0 / k
    pm = L.copy(); pm[..., :3] *= pm[..., 3:4]
    pm = cv2.filter2D(pm, -1, ker, borderType=cv2.BORDER_CONSTANT)
    out = pm.copy(); a = np.maximum(out[..., 3:4], 1e-4); out[..., :3] = np.clip(pm[..., :3] / a, 0, 1)
    return out


def _ui_pad(L, py=0, px=0):
    return np.pad(L, ((py, py), (px, px), (0, 0)))


def _ui_comp(c, L, cx, cy, alpha=1.0, scale=1.0, behind=False, guard=False):
    """Composite a float RGBA layer centred on (cx, cy) with an optional scale."""
    if alpha <= 0.003 or scale <= 0.01: return
    if abs(scale - 1) > 0.004:
        L = cv2.resize(L, (max(1, int(L.shape[1] * scale)), max(1, int(L.shape[0] * scale))), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    comp(c, L, cx - L.shape[1] / 2, cy - L.shape[0] / 2, alpha, behind, guard)


def _ui_shadow_np(L, blur, dy, alpha):
    """Soft drop shadow under a float RGBA layer; returns a bigger layer (same centre)."""
    pad = int(blur * 2 + abs(dy)) + 2
    P = _ui_pad(L, pad, pad)
    a = cv2.GaussianBlur(P[..., 3], (0, 0), blur)
    a = np.roll(a, int(dy), axis=0) * alpha
    out = np.zeros_like(P); out[..., 3] = a
    A = P[..., 3:4]
    out[..., :3] = P[..., :3]
    out[..., 3] = A[..., 0] + a * (1 - A[..., 0])
    out[..., :3] = P[..., :3] * (A / np.maximum(out[..., 3:4], 1e-4))
    return out


def _ui_face(c, e, size, ring=0, ring_col=AY['cream']):
    """Round avatar from her own face (grabbed once), anti-aliased, optional ring. PIL RGBA at size px."""
    size = int(size); k = 3
    def grab():
        r = c.fw * 0.78; x0, y0 = int(max(0, c.fx - r)), int(max(0, c.fy - r * 0.95))
        crop = c.img[y0:int(y0 + 2 * r), x0:int(x0 + 2 * r)]
        return Image.fromarray((np.clip(crop, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
    src = cached(e, '_ui_face', grab)
    key = ('_ui_face_r', size, ring)
    if key in e.state: return e.state[key]
    S = size * k
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    inner = S - 2 * ring * k
    f = src.resize((inner, inner), Image.LANCZOS)
    m = Image.new('L', (inner, inner), 0); ImageDraw.Draw(m).ellipse([0, 0, inner - 1, inner - 1], fill=255); f.putalpha(m)
    if ring:
        ImageDraw.Draw(im).ellipse([0, 0, S - 1, S - 1], fill=_ui_a(ring_col))
    im.alpha_composite(f, (ring * k, ring * k))
    im = im.resize((size, size), Image.LANCZOS)
    e.state[key] = im
    return im


def _ui_runs_layout(runs, max_w, k=1):
    """Word-wrap styled runs [(text, font, fill)] -> lines [[(x, word, font, fill)]] and widths."""
    lines, cur, x = [], [], 0.0
    runs = [(_ui_re.sub(r'(?:(?<=\s)|^)(\w{1,2}) ', '\\1\u00a0', t + ' ').rstrip(' '), f, fill) for t, f, fill in runs]
    for txt, f, fill in runs:
        for wi, w in enumerate(txt.split(' ')):
            if w == '':
                continue
            sp = f.getlength(' ')
            wl = f.getlength(w.replace('\u00a0', ' '))
            lead = sp if (cur and w[:1] not in ',.!?:;)»') else 0
            if cur and x + lead + wl > max_w:
                lines.append(cur); cur, x, lead = [], 0.0, 0
            cur.append((x + lead, w.replace('\u00a0', ' '), f, fill)); x += lead + wl
    if cur: lines.append(cur)
    return lines


# ---------------------------------------------------------------- glass
def _ui_rrect_sdf(xx, yy, cx, cy, hw, hh, r):
    qx = np.abs(xx - cx) - (hw - r); qy = np.abs(yy - cy) - (hh - r)
    ox = np.maximum(qx, 0); oy = np.maximum(qy, 0)
    return np.sqrt(ox * ox + oy * oy) + np.minimum(np.maximum(qx, qy), 0) - r


def _ui_glass(c, cx, cy, w, h, r, src=None, blur=3.0, refr=16.0, zoom=1.0, tint=(255, 255, 255), amt=0.06, bright=1.05,
              rim=0.65, alpha=1.0, shadow=0.16, ca=0.06, glow=0.10, guard=False):
    """Liquid glass: a rounded slab that blurs, brightens and lens-bends the picture behind it, with a specular rim.
    src = picture to refract (default: the current frame). Composites into c.img."""
    w = max(4.0, float(w)); h = max(4.0, float(h)); r = min(r, w / 2, h / 2)
    if alpha <= 0.003: return
    src = c.img if src is None else src
    sh_sig = max(4.0, min(w, h) * 0.08); sh_dy = int(max(3, min(w, h) * 0.05))
    pad = int(max(refr * 1.5, blur * 3, 18, (sh_sig * 2.6 + sh_dy) if shadow > 0 else 0)) + 4
    X0 = int(math.floor(cx - w / 2)) - pad; Y0 = int(math.floor(cy - h / 2)) - pad
    X1 = int(math.ceil(cx + w / 2)) + pad; Y1 = int(math.ceil(cy + h / 2)) + pad
    x0, y0, x1, y1 = max(0, X0), max(0, Y0), min(c.W, X1), min(c.H, Y1)
    if x1 - x0 < 4 or y1 - y0 < 4: return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    d = _ui_rrect_sdf(xx + 0.5, yy + 0.5, cx, cy, w / 2, h / 2, r)
    A = np.clip(0.5 - d, 0, 1)
    # sample window (wider, so the lens can pull pixels from outside the slab)
    sx0, sy0 = max(0, x0 - pad), max(0, y0 - pad); sx1, sy1 = min(c.W, x1 + pad), min(c.H, y1 + pad)
    S = np.ascontiguousarray(src[sy0:sy1, sx0:sx1])
    if blur > 0.4: S = cv2.GaussianBlur(S, (0, 0), blur)
    # lens: near the rim sample towards the centre (bends the background), plus an optional magnification
    ew = max(6.0, min(w, h) * 0.32)
    ds = cv2.GaussianBlur(np.minimum(d, 0), (0, 0), max(1.5, ew * 0.22))    # rounded normals: no seams on the diagonals
    gy, gx = np.gradient(ds)
    gn = np.sqrt(gx * gx + gy * gy) + 1e-6; nx, ny = gx / gn, gy / gn
    g0y, g0x = np.gradient(d); g0n = np.sqrt(g0x * g0x + g0y * g0y) + 1e-6
    depth = np.clip(-d, 0, None)
    f = np.clip(1 - depth / ew, 0, 1) ** 2 * (d < 1)
    mx = cx + (xx - cx) / zoom; my = cy + (yy - cy) / zoom
    out = np.empty((y1 - y0, x1 - x0, 3), np.float32)
    for ch, kk in ((0, 1 + ca), (1, 1.0), (2, 1 - ca)):
        dx = -nx * f * refr * kk; dy = -ny * f * refr * kk
        mapx = (mx + dx - sx0).astype(np.float32); mapy = (my + dy - sy0).astype(np.float32)
        out[..., ch] = cv2.remap(S[..., ch], mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    col = out * bright * (1 - amt) + np.float32(tint) / 255 * amt
    # inner light: brighter towards the rim and towards the top
    inner = np.clip(1 + d / (ew * 0.55), 0, 1) ** 2
    topl = np.clip(1 - (yy - (cy - h / 2)) / max(1.0, h), 0, 1)
    col = col + (inner * glow + topl * glow * 0.45)[..., None]
    # specular rim: thin bright line, strongest where the normal faces top-left / bottom-right
    ring = np.clip(1 - np.abs(d + 1.1) / 1.25, 0, 1)
    spec = 0.35 + 0.65 * np.abs(g0x / g0n * -0.62 + g0y / g0n * -0.78)
    ra = (ring * spec * rim)[..., None]
    col = col * (1 - ra) + ra
    col = np.clip(col, 0, 1)
    dst = c.img[y0:y1, x0:x1]
    if shadow > 0:
        sh = cv2.GaussianBlur(A, (0, 0), sh_sig)
        sh = np.roll(sh, sh_dy, axis=0) * shadow * (1 - A) * alpha
        dst[:] = dst * (1 - sh[..., None])
    a = A * alpha
    if guard:
        e_ = ((xx - c.fx) / (c.fw * 0.95)) ** 2 + ((yy - c.fy) / (c.fw * 1.35)) ** 2
        a = a * (1 - np.clip((1.2 - e_) / 0.3, 0, 1) * c.m[y0:y1, x0:x1])
    a = a[..., None]
    dst[:] = dst * (1 - a) + col * a


def _ui_blur_frame(c, sigma):
    if sigma < 0.3: return
    q = 4 if sigma > 6 else 2
    sm = cv2.resize(c.img, (c.W // q, c.H // q), interpolation=cv2.INTER_AREA)
    sm = cv2.GaussianBlur(sm, (0, 0), sigma / q)
    c.img = cv2.resize(sm, (c.W, c.H), interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------- icons (drawn at 2x)
def _ui_icon(kind, size, col=AY['cream'], sw=None):
    k = 3; S = int(size * k); im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lw = int((sw or size * 0.085) * k); C = _ui_a(col); p = lambda v: v * S
    if kind == 'home':
        pts = [(p(.16), p(.46)), (p(.5), p(.16)), (p(.84), p(.46)), (p(.84), p(.86)), (p(.6), p(.86)), (p(.6), p(.62)),
               (p(.4), p(.62)), (p(.4), p(.86)), (p(.16), p(.86)), (p(.16), p(.46))]
        d.line(pts, fill=C, width=lw, joint='curve')
    elif kind == 'search':
        d.ellipse([p(.16), p(.16), p(.68), p(.68)], outline=C, width=lw)
        d.line([(p(.62), p(.62)), (p(.86), p(.86))], fill=C, width=lw)
    elif kind == 'reels':
        d.rounded_rectangle([p(.14), p(.14), p(.86), p(.86)], int(p(.2)), outline=C, width=lw)
        d.line([(p(.16), p(.36)), (p(.84), p(.36))], fill=C, width=lw)
        d.line([(p(.36), p(.16)), (p(.46), p(.36))], fill=C, width=lw); d.line([(p(.56), p(.16)), (p(.66), p(.36))], fill=C, width=lw)
        d.polygon([(p(.42), p(.48)), (p(.42), p(.74)), (p(.64), p(.61))], fill=C)
    elif kind == 'send':
        pts = [(p(.12), p(.44)), (p(.88), p(.14)), (p(.6), p(.88)), (p(.46), p(.56)), (p(.12), p(.44))]
        d.line(pts, fill=C, width=lw, joint='curve'); d.line([(p(.46), p(.56)), (p(.86), p(.16))], fill=C, width=lw)
    elif kind == 'user':
        d.ellipse([p(.33), p(.12), p(.67), p(.46)], outline=C, width=lw)
        d.arc([p(.16), p(.56), p(.84), p(1.2)], 180, 360, fill=C, width=lw)
    elif kind == 'heart' or kind == 'heart_f':
        pts = []
        for i in range(64):
            t = 2 * math.pi * i / 64
            x = 16 * math.sin(t) ** 3; y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
            pts.append((p(.5 + x / 36), p(.47 - y / 36)))
        if kind == 'heart_f': d.polygon(pts, fill=C)
        else: d.line(pts + [pts[0]], fill=C, width=lw, joint='curve')
    elif kind == 'play':
        d.polygon([(p(.3), p(.18)), (p(.3), p(.82)), (p(.84), p(.5))], fill=C)
    elif kind == 'pause':
        d.rounded_rectangle([p(.26), p(.2), p(.42), p(.8)], int(p(.04)), fill=C); d.rounded_rectangle([p(.58), p(.2), p(.74), p(.8)], int(p(.04)), fill=C)
    elif kind == 'up':
        d.line([(p(.5), p(.82)), (p(.5), p(.2))], fill=C, width=lw); d.line([(p(.24), p(.44)), (p(.5), p(.18)), (p(.76), p(.44))], fill=C, width=lw, joint='curve')
    elif kind == 'shift':
        d.line([(p(.5), p(.14)), (p(.86), p(.52)), (p(.66), p(.52)), (p(.66), p(.84)), (p(.34), p(.84)), (p(.34), p(.52)), (p(.14), p(.52)), (p(.5), p(.14))],
               fill=C, width=lw, joint='curve')
    elif kind == 'back':
        d.line([(p(.36), p(.2)), (p(.9), p(.2)), (p(.9), p(.8)), (p(.36), p(.8)), (p(.08), p(.5)), (p(.36), p(.2))], fill=C, width=lw, joint='curve')
        d.line([(p(.48), p(.36)), (p(.74), p(.64))], fill=C, width=lw); d.line([(p(.74), p(.36)), (p(.48), p(.64))], fill=C, width=lw)
    elif kind == 'person':
        d.ellipse([p(.34), p(.2), p(.66), p(.52)], fill=C); d.pieslice([p(.18), p(.58), p(.82), p(1.2)], 180, 360, fill=C)
    return im.resize((int(size), int(size)), Image.LANCZOS)


# ================================================================ ay-index
def _ui_index_build(c, items, label, foot, pill_kind):
    s = _ui_s(c); K = _UI_K
    fr = ay_font('hm', 23 * s * K); fn = ay_font('mm', 12.5 * s * K); fh = ay_font('mm', 14.5 * s * K); ff = ay_font('h', 23 * s * K)
    pad = 16 * s; numw = 34 * s
    tw = max([fr.getlength(t) / K for t in items] + [ff.getlength(foot) / K, fh.getlength(label) / K + 18 * 3.2 * s + 70 * s])
    pw = int(clamp(tw + 2 * pad + numw + 14 * s, 236 * s, 360 * s))
    rowh = 33 * s; head = 44 * s; footh = 56 * s
    n = len(items)
    ph = int(pad * 0.7 + head + n * rowh + 10 * s + footh)
    PW, PH = pw * K, ph * K
    rows_y = [pad * 0.7 + head + (i + 0.5) * rowh for i in range(n)]
    maxw = (pw - 2 * pad - numw - 10 * s) * K

    def clip_txt(t, f):
        if f.getlength(t) <= maxw: return t
        while len(t) > 2 and f.getlength(t + '…') > maxw: t = t[:-1]
        return t.rstrip() + '…'
    items = [clip_txt(t, fr) for t in items]

    def text_layer(fill_txt, fill_num):
        im = Image.new('RGBA', (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for i, t in enumerate(items):
            y = rows_y[i] * K
            d.text((pad * K + 6 * s * K, y), f'{i + 1:02d}', font=fn, fill=fill_num, anchor='lm')
            d.text((pad * K + numw * K, y + 1 * s * K), t, font=fr, fill=fill_txt, anchor='lm')
        return ay_np(_ui_down(im))
    dim = text_layer(_ui_a(AY['tx'], 112), _ui_a(AY['tx'], 92))
    bright = text_layer(_ui_a(AY['tx'], 255), _ui_a(AY['lime'], 200))
    ink = text_layer(_ui_a(AY['ink'], 255), _ui_a(AY['ink'], 170))
    # chrome: border, header label, divider, footer
    im = Image.new('RGBA', (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([1, 1, PW - 2, PH - 2], int(22 * s * K), outline=_ui_a(AY['cream'], 46), width=max(2, int(1.2 * s * K)))
    # label with letter spacing
    x = pad * K + 6 * s * K; yh = (pad * 0.7 + head * 0.5) * K
    for ch in label:
        d.text((x, yh), ch, font=fh, fill=_ui_a(AY['lime']), anchor='lm'); x += fh.getlength(ch) + 3.2 * s * K
    ydiv = (pad * 0.7 + head + n * rowh + 8 * s) * K
    d.line([(pad * K, ydiv), (PW - pad * K, ydiv)], fill=_ui_a(AY['cream'], 40), width=max(2, int(1 * s * K)))
    chrome = ay_np(_ui_down(im))
    foot_y = (ydiv / K + footh * 0.5 + 2 * s)
    # footer: first word cream, the rest lime; and an inked version for the highlighted state
    def foot_layer(hi):
        im = Image.new('RGBA', (PW, PH), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        parts = foot.split(' ', 1); x = (pad + 6 * s) * K
        if hi:
            fw_ = ff.getlength(foot)
            d.rounded_rectangle([x - 10 * s * K, (foot_y - 19 * s) * K, x + fw_ + 10 * s * K, (foot_y + 19 * s) * K], int(10 * s * K), fill=_ui_a(AY['lime']))
            d.text((x, foot_y * K), foot, font=ff, fill=_ui_a(AY['ink']), anchor='lm')
        else:
            d.text((x, foot_y * K), parts[0], font=ff, fill=_ui_a(AY['tx']), anchor='lm')
            if len(parts) > 1:
                d.text((x + ff.getlength(parts[0] + ' '), foot_y * K), parts[1], font=ff, fill=_ui_a(AY['lime']), anchor='lm')
        return ay_np(_ui_down(im))
    pill_col = AY['lime'] if pill_kind != 'cream' else AY['cream']
    return dict(pw=pw, ph=ph, rows_y=rows_y, rowh=rowh, pad=pad, dim=dim, bright=bright, ink=ink, chrome=chrome,
                foot0=foot_layer(False), foot1=foot_layer(True), pill_col=pill_col, head=head, fh=fh, s=s)


def _ui_index_count(L, now, total, s):
    K = _UI_K; f = ay_font('mb', 14.5 * s * K)
    txt = f'{now:02d} / {total:02d}'
    im = Image.new('RGBA', (L['pw'] * K, int(L['ph'] * K)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((L['pw'] * K - L['pad'] * K - 4 * s * K, (L['pad'] * 0.7 + L['head'] * 0.5) * K), txt, font=f, fill=_ui_a(AY['cream']), anchor='rm')
    return ay_np(_ui_down(im))


@effect('ay-index', 'persistent «У ЦЬОМУ ВІДЕО 03 / 07» panel top-right, numbered list with a moving highlight pill')
def fx_ay_index(c, e):
    items = ay_words(e, default='Оффер|Аудиторія|Креативи|Тексти|Бюджет|Аналітика|Масштаб')
    n = len(items); s = _ui_s(c)
    label = str(e.o.get('label') or 'У ЦЬОМУ ВІДЕО').upper()
    foot = str(e.o.get('foot') or 'Напиши ЕФЕКТИ')
    L = cached(e, 'L', lambda: _ui_index_build(c, items, label, foot, str(e.o.get('pill', 'lime'))))
    total = int(e.o.get('total') or n)
    # which item is current: `at` = list of local switch times (item 1 from at[0] ...) or a fixed `now`
    at = e.o.get('at')
    sw = 0.34
    if at not in (None, ''):
        ts = [float(x) for x in (at if isinstance(at, list) else str(at).replace('|', ',').split(','))]
        k = sum(1 for t in ts if c.lt >= t)
        base = int(e.o.get('now') or 1) - 1
        cur = base + k; prev = cur - 1 if k else cur
        tsw = (c.lt - ts[k - 1]) / sw if k else 1.0
    else:
        cur = int(e.o.get('now') or 1); prev = cur; tsw = 1.0
    cur = int(clamp(cur, 0, n)); prev = int(clamp(prev, 0, n))
    pw, ph = L['pw'], L['ph']
    # placement (top-right), intro / outro
    mx = float(e.o.get('margin', 16)) * s
    x0 = c.W - mx - pw if e.o.get('x') is None else float(e.o['x']) * c.W
    y0 = float(e.o.get('y', 0.11)) * c.H
    tin = 0.38 if str(e.o.get('intro', '1')) not in ('0', 'false', 'False') else 0.0
    tout = 0.28 if str(e.o.get('outro', '1')) not in ('0', 'false', 'False') else 0.0
    pin = ease_out(c.lt / tin) if tin else 1.0
    pout = ease_inout(clamp((e.d - c.lt) / tout)) if tout else 1.0
    a = pin * pout
    if a <= 0.003: return
    x0 += (1 - pin) * 60 * s + (1 - pout) * 30 * s
    # frosted panel body
    _ui_glass(c, x0 + pw / 2, y0 + ph / 2, pw, ph, 22 * s, blur=16, refr=6, tint=_UI_PANEL, amt=0.94, bright=1.0,
              rim=0.25, alpha=a * 0.97, shadow=0.22, ca=0.0, glow=0.03)
    # layer stack (panel-local numpy)
    H_, W_ = L['dim'].shape[:2]
    pill = np.zeros((H_, W_), np.float32)
    rows = L['rows_y']
    if cur >= 1:
        p = ease_inout(tsw)
        ya = rows[prev - 1] if prev >= 1 else rows[cur - 1] - L['rowh']
        yb = rows[cur - 1]
        yc = ya + (yb - ya) * p
        stretch = math.sin(math.pi * clamp(tsw)) * abs(yb - ya) * 0.35 if prev != cur else 0
        hh = L['rowh'] * 0.43 + stretch * 0.5
        pill_a = 1.0 if prev >= 1 or tsw >= 1 else ease_out(tsw)
        yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32)
        sd = _ui_rrect_sdf(xx + 0.5, yy + 0.5, W_ / 2, yc, W_ / 2 - L['pad'] * 0.62, hh, 9 * s)
        pill = np.clip(0.5 - sd, 0, 1) * pill_a
    # bright = past and current rows; crossfade the row that changes state
    row_b = np.zeros((H_, 1), np.float32)
    for i in range(n):
        y_a, y_b = int(rows[i] - L['rowh'] / 2), int(rows[i] + L['rowh'] / 2)
        v = 1.0 if i + 1 <= cur else 0.0
        if i + 1 == cur and prev < cur: v = clamp(tsw * 1.5)
        row_b[max(0, y_a):y_b] = v
    txt = L['dim'] * (1 - row_b[..., None]) + L['bright'] * row_b[..., None]
    lay = np.zeros((H_, W_, 4), np.float32)

    def over(dst, srcL, m=None):
        sa = srcL[..., 3:4] * (1 if m is None else m[..., None])
        dst[..., :3] = srcL[..., :3] * sa + dst[..., :3] * (1 - sa)
        dst[..., 3:4] = sa + dst[..., 3:4] * (1 - sa)
    over(lay, L['chrome'])
    over(lay, txt, 1 - pill)
    pc = np.zeros((H_, W_, 4), np.float32); pc[..., :3] = np.float32(L['pill_col']) / 255; pc[..., 3] = pill
    over(lay, pc)
    over(lay, L['ink'], pill)
    over(lay, cached(e, ('cnt', cur), lambda: _ui_index_count(L, max(cur, 0), total, s)))
    fa = e.o.get('foot_at')
    fh = clamp((c.lt - float(fa)) / 0.25) if fa not in (None, '') else 0.0
    if fh < 1: over(lay, L['foot0'], np.full((H_, W_), 1 - fh, np.float32))
    if fh > 0: over(lay, L['foot1'], np.full((H_, W_), fh, np.float32))
    comp(c, lay, x0, y0, a)


# ================================================================ ay-live-cursor
def _ui_lift(im, r):
    """A soft dark contact shadow under thin lines, so lime reads on light walls."""
    a = im.split()[3]
    sh = Image.new('RGBA', im.size, (8, 14, 8, 0)); sh.putalpha(a.point(lambda v: v * 70 // 255).filter(ImageFilter.GaussianBlur(r)))
    sh.alpha_composite(im)
    return sh


def _ui_cursor_img(size, name, col=FIGMA, ink=(255, 255, 255)):
    k = 3; s = size * k
    ft = ay_font('h', size * 0.62 * k)
    tw = ft.getlength(name)
    W_ = int(s * 0.9 + tw + s * 0.9); H_ = int(s * 1.9)
    im = Image.new('RGBA', (W_, H_), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    o = 4 * k
    pts = [(o, o), (o, o + s * 1.0), (o + s * 0.27, o + s * 0.76), (o + s * 0.47, o + s * 1.18), (o + s * 0.62, o + s * 1.11),
           (o + s * 0.43, o + s * 0.7), (o + s * 0.76, o + s * 0.7)]
    d.polygon(pts, fill=_ui_a(col)); d.line(pts + [pts[0]], fill=_ui_a(ink), width=int(size * 0.075 * k), joint='curve')
    # name tag
    tx, ty = o + s * 0.62, o + s * 1.05
    th = size * 0.95 * k
    d.rounded_rectangle([tx, ty, tx + tw + size * 0.7 * k, ty + th], int(th * 0.32), fill=_ui_a(col))
    d.text((tx + size * 0.35 * k, ty + th / 2 + k), name, font=ft, fill=_ui_a(ink), anchor='lm')
    im = im.resize((W_ // k, H_ // k), Image.LANCZOS)
    return shadowed(im, blur=max(3, int(size * 0.14)), dy=max(2, int(size * 0.08)), alpha=90), 4 + (max(3, int(size * 0.14)) * 2 + max(2, int(size * 0.08)))


@effect('ay-live-cursor', 'Figma-like selection box is dragged around you by a named cursor, then snaps with handles, size label and guides')
def fx_ay_live_cursor(c, e):
    s = _ui_s(c); d_ = e.d; lt = c.lt
    name = str(e.o.get('name') or 'Ти')
    col = FIGMA
    guide_col = (242, 72, 34)
    # box around the head and shoulders (sizes frozen at the first frame, position follows her)
    fw0 = cached(e, 'fw0', lambda: c.fw)
    bw = fw0 * float(e.o.get('bw', 1.6)); top = fw0 * float(e.o.get('top', 1.12)); bot = fw0 * float(e.o.get('bot', 1.3))
    BX0, BY0 = c.fx - bw / 2, c.fy - top
    BX1, BY1 = c.fx + bw / 2, c.fy + bot
    BX0 = max(BX0, 30 * s); BX1 = min(BX1, c.W - 30 * s); BY0 = max(BY0, 60 * s)
    u = lt / d_
    T_FLY, T_PRESS, T_DRAG, T_SNAP = 0.16, 0.22, 0.64, 0.72
    out = fade(c, e, 0.22)
    # drag corner path: from the anchor, overshoot past the target, settle
    pd = _ui_seg(u, T_PRESS, T_DRAG)
    ee = _ui_spring(pd * 1.15, 4.6, 7.0)
    wob = math.sin(lt * 11.0) * (1 - pd) * 14 * s
    cxp = BX0 + (BX1 - BX0) * ee + wob
    cyp = BY0 + (BY1 - BY0) * (ee * 0.92 + 0.08 * _ui_sm(pd)) + math.cos(lt * 9.0) * (1 - pd) * 10 * s
    snapped = u >= T_DRAG
    if snapped: cxp, cyp = BX1, BY1
    # cursor position
    if u < T_FLY:
        q = ease_out(u / T_FLY)
        sx, sy = c.W * 1.04, BY0 - 160 * s
        curx, cury = sx + (BX0 - sx) * q, sy + (BY0 - sy) * q
    elif u < T_PRESS:
        curx, cury = BX0, BY0
    elif not snapped:
        curx, cury = cxp, cyp
    else:
        q = ease_out(_ui_seg(u, T_DRAG, 0.9))
        curx, cury = BX1 + 26 * s * q, BY1 + 30 * s * q
    # ---- draw lines/handles on a 2x supersampled region
    K = 2
    gx0, gy0 = int(min(BX0, curx) - 60 * s), int(min(BY0, cury) - 90 * s)
    gx1, gy1 = int(max(BX1, cxp, curx) + 60 * s), int(max(BY1, cyp, cury) + 110 * s)
    gx0, gy0 = max(0, gx0), max(0, gy0); gx1, gy1 = min(c.W, gx1), min(c.H, gy1)
    show_box = u >= T_PRESS
    e.state['_chip'] = None
    if show_box and gx1 > gx0 and gy1 > gy0:
        im = Image.new('RGBA', ((gx1 - gx0) * K, (gy1 - gy0) * K), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        P = lambda x, y: ((x - gx0) * K, (y - gy0) * K)
        x0_, y0_ = BX0, BY0; x1_, y1_ = (cxp, cyp)
        lw = max(2, int(2.0 * s * K))
        ca = 255
        d.rectangle([P(min(x0_, x1_), min(y0_, y1_)), P(max(x0_, x1_), max(y0_, y1_))], outline=_ui_a(col, ca), width=lw)
        # faint fill so the selection reads as a layer
        ov = Image.new('RGBA', im.size, (0, 0, 0, 0))
        ImageDraw.Draw(ov).rectangle([P(min(x0_, x1_), min(y0_, y1_)), P(max(x0_, x1_), max(y0_, y1_))], fill=_ui_a(col, 16))
        im = Image.alpha_composite(ov, im); d = ImageDraw.Draw(im)
        # anchor ring (pressed at the start)
        pr = pop(c, T_FLY * d_, 0.25)
        rr = 13 * s * K * pr
        if rr > 1:
            ax, ay_ = P(x0_, y0_)
            d.ellipse([ax - rr, ay_ - rr, ax + rr, ay_ + rr], outline=_ui_a(AY['cream'], 255), width=max(2, int(2 * s * K)))
        if snapped:
            hp = _ui_seg(u, T_DRAG, T_SNAP)
            for k_, (hx, hy) in enumerate([(x0_, y0_), ((x0_ + x1_) / 2, y0_), (x1_, y0_), (x1_, (y0_ + y1_) / 2), (x1_, y1_),
                                           ((x0_ + x1_) / 2, y1_), (x0_, y1_), (x0_, (y0_ + y1_) / 2)]):
                q = ease_back(clamp(hp * 1.6 - k_ * 0.07))
                hs = 8.5 * s * K * q
                if hs < 0.5: continue
                X, Y = P(hx, hy)
                d.rectangle([X - hs, Y - hs, X + hs, Y + hs], fill=_ui_a(AY['cream']), outline=_ui_a(col), width=max(2, int(2 * s * K)))
        # size chip under the box (Figma-style), live while dragging
        bwp, bhp = abs(x1_ - x0_), abs(y1_ - y0_)
        if bwp > 30 * s:
            sc = 1080.0 / c.W
            dims = e.o.get('dims') or f'{int(round(bwp * sc))} × {int(round(bhp * sc))}'
            fm = ay_font('mb', 21 * s * K)
            tw = fm.getlength(dims); th = 36 * s * K
            mxp = (min(x0_, x1_) + max(x0_, x1_)) / 2; myp = max(y0_, y1_) + 16 * s
            X, Y = P(mxp, myp)
            imc = Image.new('RGBA', im.size, (0, 0, 0, 0)); dc = ImageDraw.Draw(imc)
            dc.rounded_rectangle([X - tw / 2 - 10 * s * K, Y, X + tw / 2 + 10 * s * K, Y + th], int(6 * s * K), fill=_ui_a(col))
            dc.text((X, Y + th / 2 + 1), dims, font=fm, fill=_ui_a((255, 255, 255)), anchor='mm')
        else: imc = None
        L = ay_np(_ui_down(_ui_lift(im, 2.2 * s * K), K))
        comp(c, L, gx0, gy0, out, guard=not snapped)
        if imc is not None:
            e.state['_chip'] = (ay_np(_ui_down(_ui_lift(imc, 2.2 * s * K), K)), gx0, gy0, out * clamp((bhp / (BY1 - BY0) - 0.78) / 0.2))
    # guides (after snap): pink vertical through the centre, horizontal along the top edge
    if snapped:
        g = ease_out(_ui_seg(u, T_DRAG + 0.02, T_SNAP + 0.06)) * out
        lw = max(1, int(round(1.6 * s)))
        L = np.zeros((c.H, lw + 2, 4), np.float32); L[..., :3] = np.float32(guide_col) / 255
        L[:, 1:1 + lw, 3] = 0.9
        grow = g
        ymid = (BY0 + BY1) / 2; hh = c.H * grow
        ys0, ys1 = int(max(0, ymid - hh / 2)), int(min(c.H, ymid + hh / 2))
        if ys1 > ys0:
            comp(c, L[ys0:ys1], (BX0 + BX1) / 2 - lw / 2 - 1, ys0, g, guard=True)
        Lh = np.zeros((lw + 2, c.W, 4), np.float32); Lh[..., :3] = np.float32(guide_col) / 255
        xmid = (BX0 + BX1) / 2; ww = c.W * grow
        xs0, xs1 = int(max(0, xmid - ww / 2)), int(min(c.W, xmid + ww / 2))
        Lh[1:1 + lw, xs0:xs1, 3] = 0.75
        comp(c, Lh, 0, BY0 - lw / 2 - 1, g, guard=True)
    if e.state.get('_chip'):
        Lc, gx_, gy_, ca_ = e.state['_chip']
        comp(c, Lc, gx_, gy_, ca_)
    # cursor on top
    cs = 42 * s
    cim, off = cached(e, ('cur', int(cs)), lambda: _ui_cursor_img(cs, name, col))
    press = 0.86 if (T_FLY <= u < T_PRESS + 0.03) else 1.0
    ca = out * clamp(u / 0.05)
    L = ay_np(cim)
    if press != 1.0:
        L = cv2.resize(L, (int(L.shape[1] * press), int(L.shape[0] * press)), interpolation=cv2.INTER_AREA)
    comp(c, L, curx - off * press, cury - off * press, ca)


# ================================================================ ay-voice-note
def _ui_wave(n, seed=5):
    rnd = np.random.default_rng(seed)
    x = np.linspace(0, 1, n)
    env = 0.35 + 0.65 * np.clip(np.sin(x * math.pi * 1.0) ** 0.6, 0, 1)
    syl = 0.55 + 0.45 * np.abs(np.sin(x * 23.0 + rnd.uniform(0, 3))) * np.abs(np.sin(x * 7.3 + 1.0))
    h = env * syl * (0.7 + 0.3 * rnd.random(n))
    h[rnd.random(n) < 0.12] *= 0.45
    return np.clip(h / h.max(), 0.14, 1.0)


@effect('ay-voice-note', 'Instagram DM voice message slides in at the top: play, waveform fills as it plays, 0:00 → 0:03, avatar, caption chip')
def fx_ay_voice_note(c, e):
    s0 = _ui_s(c); s = s0 * float(e.o.get('scale', 1.35)); lt = c.lt; d_ = e.d; K = _UI_K
    cap = str(e.o.get('text') or 'Голосове')
    secs = int(float(e.o.get('secs', 3)))
    pw, ph = 640 * s, 110 * s
    av = 70 * s; gap = 14 * s
    total_w = pw + gap + av
    xc = e.o.get('x')
    if xc is None: x0 = (c.W - total_w) / 2                     # centred, ~80% of the width
    else: x0 = float(xc) * c.W - total_w / 2
    yc = float(e.o.get('y', 0.095)) * c.H
    # timeline
    T_IN = min(0.38, d_ * 0.3); T_PLAY = T_IN + 0.08; T_END = d_ - 0.32
    pin = _ui_spring(lt / (T_IN * 1.6), 6.0, 9.0)
    pout = ease_inout(clamp((d_ - lt) / 0.26))
    a = clamp(lt / (T_IN * 0.6)) * pout
    if a <= 0.003: return
    dy = -(1 - pin) * 170 * s - (1 - pout) * 50 * s
    prog = clamp((lt - T_PLAY) / max(0.2, T_END - T_PLAY))
    playing = T_PLAY <= lt < T_END
    # --- pill at 2x
    W2, H2 = int(pw * K), int(ph * K)
    im = Image.new('RGBA', (W2, H2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W2 - 1, H2 - 1], H2 // 2, fill=_ui_a(IG['dm']))
    pc = 82 * s * K; px0 = (ph * K - pc) / 2
    tap = 1 - 0.1 * math.sin(math.pi * clamp((lt - T_IN + 0.05) / 0.16))
    pcs = pc * tap; pcx, pcy = px0 + pc / 2, H2 / 2
    d.ellipse([pcx - pcs / 2, pcy - pcs / 2, pcx + pcs / 2, pcy + pcs / 2], fill=_ui_a((255, 255, 255)))
    ic = _ui_icon('pause' if playing else 'play', pcs * 0.42, IG['dm'])
    im.alpha_composite(ic, (int(pcx - ic.width / 2 + (0 if playing else pcs * 0.03)), int(pcy - ic.height / 2)))
    # waveform
    wx0 = px0 + pc + 26 * s * K; wx1 = W2 - (176 * s * K)
    n = int((wx1 - wx0) / (10 * s * K)); bw = 5.2 * s * K; step = (wx1 - wx0) / n
    hs = cached(e, ('wave', n), lambda: _ui_wave(n))
    grow = clamp((lt - T_IN * 0.4) / 0.4)
    head = prog * n
    for i in range(n):
        g = ease_out(clamp(grow * 1.8 - i / n * 0.8))
        live = 1.0
        if playing:
            dist = abs(i - head)
            if dist < 4: live = 1 + 0.32 * (1 - dist / 4) * math.sin(lt * 31 + i * 1.7)
        bh = max(bw, hs[i] * 62 * s * K * g * live)
        x = wx0 + i * step
        fill_f = clamp(head - i)
        mixk = 0.26 + 0.74 * clamp(fill_f)
        base = _ui_a((255, 255, 255), int(110 + 145 * clamp(fill_f)))
        d.rounded_rectangle([x, H2 / 2 - bh / 2, x + bw, H2 / 2 + bh / 2], int(bw / 2), fill=base)
    # timer
    tsec = min(secs, int(prog * secs + 1e-6)) if lt >= T_PLAY else 0
    ft = ay_font('hm', 31 * s * K)
    d.text((W2 - 104 * s * K, H2 / 2 + 1), f'0:{tsec:02d}', font=ft, fill=_ui_a((255, 255, 255)), anchor='rm')
    # send circle
    sc = 62 * s * K; scx = W2 - px0 - sc / 2
    d.ellipse([scx - sc / 2, H2 / 2 - sc / 2, scx + sc / 2, H2 / 2 + sc / 2], fill=_ui_a(IG['dm']))
    up = _ui_icon('up', sc * 0.5, IG['dm'], sw=sc * 0.5 * 0.11)
    im.alpha_composite(up, (int(scx - up.width / 2), int(H2 / 2 - up.height / 2)))
    pill = (_ui_shadow_np(ay_np(_ui_down(im)), 14 * s, 8 * s, 0.32))
    _ui_comp(c, pill, x0 + pw / 2, yc + dy, a)
    # avatar
    face = ay_np(_ui_face(c, e, av, ring=int(3 * s)))
    ap = _ui_spring((lt - 0.08) / (T_IN * 1.6), 6.0, 9.0)
    _ui_comp(c, face, x0 + pw + gap + av / 2, yc + dy, a * clamp((lt - 0.08) / 0.15), scale=0.6 + 0.4 * ap)
    # caption chip
    chip = cached(e, 'chip', lambda: (_ui_shadow_np(ay_np(_ui_chip(cap, 30 * s, (255, 255, 255), (0, 0, 0))), 8 * s, 4 * s, 0.25)))
    cp = _ui_spring((lt - T_IN * 0.8) / 0.55, 6.5, 10.0)
    _ui_comp(c, chip, x0 + pw * 0.66, yc + dy + ph / 2 + 40 * s, a * clamp((lt - T_IN * 0.8) / 0.15), scale=0.7 + 0.3 * cp)


def _ui_chip(s_, size, bg, fg, kind='h'):
    K = 3; f = ay_font(kind, size * K)
    tw = f.getlength(s_); h = size * 1.55 * K; pw = tw + size * 1.0 * K
    im = Image.new('RGBA', (int(pw), int(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], int(h * 0.3), fill=_ui_a(bg))
    d.text((im.width / 2, im.height / 2 + K), s_, font=f, fill=_ui_a(fg), anchor='mm')
    return im.resize((int(pw / K), int(h / K)), Image.LANCZOS)


# ================================================================ ay-comment-drop
def _ui_avatar_you(size):
    K = 3; S = int(size * K); im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, S - 1, S - 1], fill=_ui_a(IG['avatar']))
    ic = _ui_icon('person', size * 0.56 * K, AY['cream'])
    im.alpha_composite(ic, ((S - ic.width) // 2, int(S * 0.2)))
    return im.resize((int(size), int(size)), Image.LANCZOS)


def _ui_comment_card(c, e, w, user, when, runs_spec, likes, liked, heart_pop, avatar, s, text_size=33):
    """Posted comment card (2x drawn). runs_spec = [(text, kind, color)]. Returns PIL RGBA at 1x."""
    K = _UI_K
    fu = ay_font('h', 25 * s * K); fw_ = ay_font('r', 25 * s * K)
    runs = [(t, ay_font(k, text_size * s * K), col) for t, k, col in runs_spec]
    padx, pady = 22 * s * K, 22 * s * K; avs = 60 * s * K
    tx0 = padx + avs + 18 * s * K
    maxw = w * K - tx0 - 92 * s * K
    lines = _ui_runs_layout(runs, maxw)
    if len(lines) > 1:                     # balance the lines (no lonely last word)
        lo_ = maxw * 0.4; hi_ = maxw
        for _ in range(14):
            mid_ = (lo_ + hi_) / 2
            if len(_ui_runs_layout(runs, mid_)) > len(lines): lo_ = mid_
            else: hi_ = mid_
        lines = _ui_runs_layout(runs, hi_ + 1)
    lh = text_size * 1.18 * s * K
    h = pady * 2 + 32 * s * K + lh * len(lines)
    im = Image.new('RGBA', (int(w * K), int(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], int(30 * s * K), fill=_ui_a(IG['card']))
    im.alpha_composite(avatar.resize((int(avs), int(avs)), Image.LANCZOS), (int(padx), int(pady)))
    y = pady + 14 * s * K
    d.text((tx0, y), user, font=fu, fill=_ui_a(AY['ink']), anchor='lm')
    d.text((tx0 + fu.getlength(user), y), f' · {when}', font=fw_, fill=_ui_a(AY['ink'], 120), anchor='lm')
    y += 18 * s * K + lh * 0.55
    for ln in lines:
        for x, wtxt, f, col in ln:
            d.text((tx0 + x, y), wtxt, font=f, fill=_ui_a(col), anchor='lm')
        y += lh
    # heart + count
    hs = 34 * s * K * (1 + 0.35 * math.sin(math.pi * clamp(heart_pop)))
    hk = 'heart_f' if liked else 'heart'
    hcol = IG['heart'] if liked else IG['heart_off']
    hi = _ui_icon(hk, hs, hcol, sw=hs * 0.09)
    hx = im.width - padx - 34 * s * K / 2 - 4 * s * K
    im.alpha_composite(hi, (int(hx - hi.width / 2), int(pady + 18 * s * K - hi.height / 2)))
    if likes not in (None, ''):
        d.text((hx, pady + 58 * s * K), str(likes), font=ay_font('hm', 23 * s * K), fill=_ui_a(AY['ink'], 150), anchor='mm')
    return _ui_down(im)


def _ui_input_bar(c, e, w, h, typed, caret_on, post_state, avatar, s, placeholder):
    K = _UI_K
    im = Image.new('RGBA', (int(w * K), int(h * K)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], int(h * 0.32 * K), fill=_ui_a(IG['card']))
    avs = 60 * s * K; ax = 20 * s * K
    im.alpha_composite(avatar.resize((int(avs), int(avs)), Image.LANCZOS), (int(ax), int((im.height - avs) / 2)))
    tx = ax + avs + 20 * s * K; cy = im.height / 2
    if typed:
        f = ay_font('hx', 36 * s * K)
        d.text((tx, cy + 2 * s * K), typed, font=f, fill=_ui_a(IG['ink']), anchor='lm'); cx_ = tx + f.getlength(typed) + 4 * s * K
    else:
        f = ay_font('r', 31 * s * K)
        d.text((tx, cy + 2 * s * K), placeholder, font=f, fill=_ui_a(AY['ink'], 110), anchor='lm'); cx_ = tx - 2 * s * K
    if caret_on:
        d.rounded_rectangle([cx_, cy - 22 * s * K, cx_ + 3 * s * K, cy + 22 * s * K], int(1.5 * s * K), fill=_ui_a(IG['avatar']))
    # post button: disabled -> active -> pressed
    fb = ay_font('h', 25 * s * K); lab = 'Опублікувати'
    bw = fb.getlength(lab) + 34 * s * K; bh = 54 * s * K
    sc = post_state.get('scale', 1.0)
    bx1 = im.width - 16 * s * K; bx0 = bx1 - bw
    bcx, bcy = (bx0 + bx1) / 2, cy
    bw2, bh2 = bw * sc / 2, bh * sc / 2
    act = post_state.get('active', 0.0)
    bg = IG['card']   # Instagram: «Опублікувати» is blue text, no pill
    d.rounded_rectangle([bcx - bw2, bcy - bh2, bcx + bw2, bcy + bh2], int(bh2), fill=_ui_a(bg))
    tc = IG['blue']
    d.text((bcx, bcy + 1), lab, font=ay_font('h', 25 * s * K * sc), fill=_ui_a(tc, 110 + 145 * act), anchor='mm')
    return _ui_down(im)


@effect('ay-comment-drop', '«Додай коментар…» input slides in, the word types in, posts as a comment card, a reply from «ти» drops under it; the word flashes big behind your head')
def fx_ay_comment_drop(c, e):
    s0 = _ui_s(c); s = s0 * float(e.o.get('scale', 1.3)); lt = c.lt; d_ = e.d; u = lt / d_
    word = str(e.o.get('text') or 'ЕФЕКТИ')
    comment = e.o.get('comment') or 'Напиши {w}, і я надішлю тобі все'
    likes = e.o.get('likes', 12)
    user = str(e.o.get('user') or ay_handle(e).lstrip('@'))
    you = str(e.o.get('you') or 'ти')
    w = 880 * s0
    xc = e.o.get('x')
    x0 = (c.W - w) / 2 if xc is None else float(xc) * c.W - w / 2
    y_top = float(e.o.get('y', 0.06)) * c.H
    avatar = _ui_face(c, e, 60 * s)
    # timeline (fractions of the duration, tuned for ~2.4 s)
    T_IN, T_TY0, T_TY1, T_TAP, T_MORPH, T_REP, T_HEART = 0.11, 0.17, 0.47, 0.52, 0.62, 0.70, 0.82
    out = ease_inout(clamp((d_ - lt) / 0.25))
    # ---- big word behind the head
    if e.o.get('big', True) not in (False, 0, '0', 'false'):
        bin_ = _ui_seg(u, 0.03, 0.15); bout = _ui_seg(u, 0.50, 0.60)
        if bin_ > 0 and bout < 1:
            def mk_big():
                sz = ay_fit(word, c.W * 0.84, 'hb', 260 * s)
                return ay_np(ay_text(word, sz, 'hb', fill=(16, 30, 20)))
            B = cached(e, 'big', mk_big)
            head_top = c.fy - c.fw * 1.0
            bar_bot = y_top + 104 * s + 26 * s
            cy = max(head_top - B.shape[0] * 0.08, bar_bot + B.shape[0] / 2)
            q = ease_out(bin_)
            vel = (1 - q) * 70 * s + bout * 50 * s
            L = _ui_vblur(_ui_pad(B, int(vel) + 2), vel)
            _ui_comp(c, L, c.fx, cy - (1 - q) * 120 * s - bout * 40 * s, (clamp(bin_ * 2)) * (1 - ease_inout(bout)), behind=True)
    # ---- input bar -> card
    pin = _ui_spring(u / T_IN / 1.5, 6.0, 9.0)
    a_in = clamp(u / (T_IN * 0.6)) * out
    if a_in <= 0.003: return
    dy_in = -(1 - pin) * 160 * s - (1 - out) * 50 * s
    n_typed = int(round(len(word) * _ui_seg(u, T_TY0, T_TY1))) if u >= T_TY0 else 0
    typed = word[:n_typed]
    caret = (int(lt * 2.6) % 2 == 0) or (T_TY0 <= u < T_TY1)
    tap = _ui_seg(u, T_TAP - 0.03, T_TAP + 0.04)
    post = {'active': clamp(n_typed / 1.0) if n_typed else 0.0, 'scale': 1 - 0.12 * math.sin(math.pi * tap)}
    morph = _ui_seg(u, T_TAP + 0.02, T_MORPH)
    m = ease_inout(morph)
    bar_h = 104 * s
    # comment runs: {w} -> bold green word
    runs = []
    parts = comment.split('{w}')
    for i, p_ in enumerate(parts):
        if p_.strip(): runs.append((p_.strip(), 'hm', AY['ink']))
        if i < len(parts) - 1: runs.append((word, 'hb', IG['ink']))
    card1 = cached(e, 'card1', lambda: ay_np(_ui_comment_card(c, e, w, user, 'зараз', runs, likes, True, 0, avatar, s, text_size=31)))
    ch1 = card1.shape[0]
    cur_h = bar_h + (ch1 - bar_h) * m
    ycen = y_top + cur_h / 2 + dy_in
    if m < 1:
        bar = ay_np(_ui_input_bar(c, e, w, bar_h, typed, caret and u < T_TAP, post, avatar, s, str(e.o.get('placeholder') or 'Додай коментар…')))
        # stretch the cream slab while morphing (simple: scale vertically, fade the content)
        if m > 0:
            slab = cached(e, ('slab', int(cur_h)), lambda: ay_np(_ui_slab(w, cur_h, 30 * s, IG['card'])))
            _ui_comp(c, (_ui_shadow_np(slab, 14 * s, 8 * s, 0.25)), x0 + w / 2, ycen, a_in)
            comp(c, bar, x0, y_top + dy_in, a_in * (1 - clamp(m * 2.2)))
        else:
            _ui_comp(c, (_ui_shadow_np(bar, 14 * s, 8 * s, 0.25)), x0 + w / 2, ycen, a_in)
    if m > 0:
        sh1 = cached(e, 'card1s', lambda: (_ui_shadow_np(card1, 14 * s, 8 * s, 0.25)))
        k_ = clamp((m - 0.45) / 0.55)
        if m >= 1: _ui_comp(c, sh1, x0 + w / 2, ycen, a_in)
        else:
            hh_ = int(cur_h); Lc = card1[:hh_].copy()
            slab_a = _ui_slab_np(card1.shape[1], hh_, 30 * s)
            hm_ = min(Lc.shape[0], slab_a.shape[0])
            Lc = Lc[:hm_]; Lc[..., 3] *= slab_a[:hm_]
            comp(c, Lc, x0, y_top + dy_in, a_in * k_)
    # ---- reply card from «ти»
    rp = _ui_seg(u, T_REP, T_REP + 0.12)
    if rp > 0:
        hp = _ui_seg(u, T_HEART, T_HEART + 0.08)
        liked = hp > 0
        rw = w - 96 * s
        key = ('card2', liked, int(hp * 8))
        card2 = cached(e, key, lambda: (_ui_shadow_np(ay_np(_ui_comment_card(c, e, rw, you, 'зараз', [(word, 'hb', IG['ink'])],
                                                                                 1 if liked else '', liked, hp, _ui_avatar_you(60 * s), s)), 12 * s, 7 * s, 0.25)))
        q = _ui_spring(rp * 0.9, 6.0, 9.0)
        cy2 = y_top + ch1 + 16 * s + card2.shape[0] / 2 - 26 * s + dy_in
        _ui_comp(c, card2, x0 + 96 * s + rw / 2, cy2 - (1 - q) * 70 * s, a_in * clamp(rp * 3), scale=0.92 + 0.08 * q)


def _ui_slab_np(w, h, r):
    yy, xx = np.mgrid[0:int(h), 0:int(w)].astype(np.float32)
    return np.clip(0.5 - _ui_rrect_sdf(xx + 0.5, yy + 0.5, int(w) / 2, int(h) / 2, int(w) / 2, int(h) / 2, r), 0, 1)


def _ui_slab(w, h, r, col):
    K = _UI_K; im = Image.new('RGBA', (int(w * K), int(h * K)), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, im.width - 1, im.height - 1], int(r * K), fill=_ui_a(col))
    return _ui_down(im)


# ================================================================ ay-predict-keys
_UI_VOCAB = ('таргет таргетолог таргетинг реклама рекламу рекламі рекламний креатив креативи креативів клієнти клієнтів клієнт ліди лідів '
             'запуск запускаю запустити заявки заявок бюджет бюджету аудиторія аудиторію аналітика аналітику наставництво налаштування '
             'налаштуй оффер продажі продаж піксель кампанія кампанію конверсії вартість ціна тест тестую тести рілс рілси сторіз воронка '
             'масштаб масштабую результат результати робота працює без для як що це вже ще все мені тобі твій твою твої свій свою '
             'нові нових новий більше менше дешевше швидше сьогодні зараз завжди Meta Instagram').split()
_UI_VOCAB_EN = ('the you your what with this that ads ad meta campaign creative creatives clients leads budget audience launch '
                'test results reels story funnel scale more less today now always keys key keep predict').split()


def _ui_kb_rows(cyr):
    if cyr:
        return ['йцукенгшщзхї', 'фівапролджє', 'ячсмитьбю']
    return ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']


def _ui_kb_geom(KW, s, cyr):
    """Key rectangles (1x, keyboard-local) for the letter rows and the bottom row."""
    rows = _ui_kb_rows(cyr)
    pad = 20 * s; gap = 8 * s
    top = pad + 92 * s + 14 * s + 62 * s + 12 * s        # input bar + suggestions
    kh = 74 * s; vg = 11 * s
    nmax = max(len(rows[0]), 10)
    kw = (KW - 2 * pad - (nmax - 1) * gap) / nmax
    keys = {}
    y = top
    for ri, row in enumerate(rows):
        if ri < 2:
            tw = len(row) * kw + (len(row) - 1) * gap; x = (KW - tw) / 2
            for ch in row: keys[ch] = (x, y, kw, kh); x += kw + gap
        else:
            sw_ = kw * 1.35
            keys['⇧'] = (pad, y, sw_, kh); keys['⌫'] = (KW - pad - sw_, y, sw_, kh)
            inner0 = pad + sw_ + gap * 1.6; inner1 = KW - pad - sw_ - gap * 1.6
            kw3 = min(kw, (inner1 - inner0 - (len(row) - 1) * gap) / len(row))
            tw = len(row) * kw3 + (len(row) - 1) * gap; x = (KW - tw) / 2
            for ch in row: keys[ch] = (x, y, kw3, kh); x += kw3 + gap
        y += kh + vg
    # bottom row
    w123 = kw * 1.55; wret = kw * 2.4; wdot = kw
    keys['123'] = (pad, y, w123, kh)
    keys['ret'] = (KW - pad - wret, y, wret, kh)
    keys['.'] = (KW - pad - wret - gap - wdot, y, wdot, kh)
    keys[','] = (pad + w123 + gap, y, wdot, kh)
    sx0 = pad + w123 + gap + wdot + gap; sx1 = KW - pad - wret - gap - wdot - gap
    keys[' '] = (sx0, y, sx1 - sx0, kh)
    KH = y + kh + pad
    return keys, KH, kw


def _ui_kb_base(KW, s, cyr, upper):
    keys, KH, kw = _ui_kb_geom(KW, s, cyr)
    K = _UI_K
    im = Image.new('RGBA', (int(KW * K), int(KH * K)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    fk = ay_font('hm', 34 * s * K); fs = ay_font('hm', 25 * s * K)
    special = IOS['spec']
    for k_, (x, y, w, h) in keys.items():
        X0, Y0, X1, Y1 = x * K, y * K, (x + w) * K, (y + h) * K
        r = int(12 * s * K)
        spec = k_ in ('⇧', '⌫', '123')
        ret = k_ == 'ret'
        bg = special if spec else (IOS['blue'] if ret else IOS['key'])
        d.rounded_rectangle([X0, Y0 + 3 * s * K, X1, Y1 + 3 * s * K], r, fill=IOS['shadow'] + (255,))   # key shadow
        d.rounded_rectangle([X0, Y0, X1, Y1], r, fill=_ui_a(bg))
        cx_, cy_ = (X0 + X1) / 2, (Y0 + Y1) / 2
        if k_ == '⇧' or k_ == '⌫':
            ic = _ui_icon('shift' if k_ == '⇧' else 'back', 30 * s * K, IOS['ink'], sw=2.6 * s * K)
            if k_ == '⇧' and upper:
                ic = _ui_icon('shift', 30 * s * K, IOS['ink'], sw=2.6 * s * K)
            im.alpha_composite(ic, (int(cx_ - ic.width / 2), int(cy_ - ic.height / 2)))
        elif k_ == '123':
            d.text((cx_, cy_), '123', font=fs, fill=_ui_a(IOS['ink']), anchor='mm')
        elif k_ == 'ret':
            d.text((cx_, cy_), 'готово' if cyr else 'return', font=fs, fill=_ui_a((255, 255, 255)), anchor='mm')
        elif k_ == ' ':
            d.text((cx_, cy_), 'пробіл' if cyr else 'space', font=fs, fill=_ui_a(IOS['ink']), anchor='mm')
        else:
            d.text((cx_, cy_ - 2 * s * K), k_.upper() if upper else k_, font=fk, fill=_ui_a(AY['ink']), anchor='mm')
    return ay_np(_ui_down(im)), keys, KH


def _ui_kb_plan(text, cyr):
    """Typing script: list of steps (kind, payload). kinds: 'ch' (press a key), 'pick' (suggestion fills the word)."""
    steps = []
    words = text.split(' ')
    for wi, w in enumerate(words):
        last = wi == len(words) - 1
        if len(w) <= 3 or not any(ch.isalpha() for ch in w):
            for ch in w: steps.append(('ch', ch))
            if not last: steps.append(('ch', ' '))
        else:
            k = max(2, min(len(w) - 1, int(math.ceil(len(w) * 0.5))))
            for ch in w[:k]: steps.append(('ch', ch))
            steps.append(('pick', w + ('' if last else ' ')))
    return steps


def _ui_kb_suggest(text_now, target_words, cyr, picking):
    vocab = _UI_VOCAB if cyr else _UI_VOCAB_EN
    parts = text_now.split(' ')
    partial = parts[-1]
    wi = len(parts) - 1
    tw = target_words[wi] if wi < len(target_words) else ''
    if partial == '':
        nxt = tw
        pool = [v for v in vocab if v.lower() != nxt.lower()]
        seed = sum(map(ord, text_now)) % max(1, len(pool))
        a, b = pool[seed % len(pool)], pool[(seed * 7 + 3) % len(pool)]
        if not text_now: return [a, nxt or b, b], -1
        if not nxt: return [',', '.', '!'], -1
        return [a, nxt, b], -1
    lo = partial.lower()
    cands = [v for v in vocab if v.lower().startswith(lo) and v.lower() != tw.lower()]
    mid = tw if len(partial) >= 2 and tw.lower().startswith(lo) else (cands[0] if cands else tw)
    right = next((v for v in cands if v != mid), None) or (vocab[(len(text_now) * 5) % len(vocab)])
    left = f'«{partial}»'
    if partial[:1].isupper():
        mid = mid[:1].upper() + mid[1:]; right = right[:1].upper() + right[1:]
    return [left, mid, right], (1 if picking else -1)


@effect('ay-predict-keys', 'iOS keyboard (dark green glass) under your chin types the text letter by letter with live predictions, keys light up, lime send')
def fx_ay_predict_keys(c, e):
    s = _ui_s(c); lt = c.lt; d_ = e.d; K = _UI_K
    text = str(e.o.get('text') or 'Запускаю рекламу без зливу бюджету')
    cyr = bool(_ui_re.search('[а-яіїєґА-ЯІЇЄҐ]', text))
    KW = c.W * float(e.o.get('width', 0.86))
    # base keyboards (lower/upper), cached
    base_lo = cached(e, 'kb_lo', lambda: _ui_kb_base(KW, s, cyr, False))
    base_up = cached(e, 'kb_up', lambda: _ui_kb_base(KW, s, cyr, True))
    keys, KH = base_lo[1], base_lo[2]
    # timeline
    T_IN = 0.32; T_OUT = 0.3
    t0, t1 = T_IN + 0.06, d_ - T_OUT - 0.32
    steps = cached(e, 'steps', lambda: _ui_kb_plan(text, cyr))
    weights = [1.0 if k_ == 'ch' else 2.2 for k_, _ in steps]
    tot = sum(weights)
    times = []; acc = 0.0
    for wgt in weights: times.append(t0 + (t1 - t0) * acc / tot); acc += wgt
    # current state
    typed = ''; press_key = None; press_t = -9; pick_t = -9; picking = False
    for (kind, p_), ts in zip(steps, times):
        if lt < ts:
            if kind == 'pick' and lt >= ts - 0.16 * (t1 - t0) / tot * 2.2:
                picking = True
            break
        if kind == 'ch':
            typed += p_; press_key = p_; press_t = ts
        else:
            parts = typed.split(' '); parts[-1] = ''
            typed = ' '.join(parts) + p_; pick_t = ts; press_key = None
    target_words = text.split(' ')
    sent = lt >= t1 + 0.12
    # placement: under the chin, frozen at the first frame
    def place_y():
        chin = c.fy + c.fw * 0.78
        return clamp(chin + 40 * s, c.H * 0.52, c.H - KH - 90 * s)
    ky = cached(e, 'ky', place_y)
    kx = (c.W - KW) / 2 if e.o.get('x') is None else float(e.o['x']) * c.W - KW / 2
    pin = ease_out(clamp(lt / T_IN)); pout = ease_inout(clamp((d_ - lt) / T_OUT))
    a = clamp(lt / (T_IN * 0.7)) * pout
    if a <= 0.003: return
    oy = (1 - pin) * 150 * s + (1 - pout) * 120 * s
    vel = (1 - pin) * 60 * s + (1 - pout) * 40 * s
    # glass body (dark green frosted)
    _ui_glass(c, kx + KW / 2, ky + oy + KH / 2, KW, KH, 44 * s, blur=18, refr=12, tint=IOS['kb'], amt=0.97, bright=1.0,
              rim=0.35, alpha=a, shadow=0.3, ca=0.0, glow=0.04)
    upper = typed == '' or typed.endswith('. ')
    layer = (base_up if upper else base_lo)[0].copy()
    # overlay: input bar, suggestions, pressed key, preview balloon
    im = Image.new('RGBA', (int(KW * K), int(KH * K)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pad = 20 * s
    ib = (pad * K, pad * K, (KW - pad) * K, (pad + 92 * s) * K)
    d.rounded_rectangle(ib, int(46 * s * K), fill=(255, 255, 255, 255), outline=_ui_a(IOS['spec'], 160), width=max(2, int(1.2 * s * K)))
    fi = ay_font('hm', 38 * s * K)
    words_now = typed.split(' ')
    tx0 = ib[0] + 32 * s * K; cy_ = (ib[1] + ib[3]) / 2 + 2 * s * K
    maxw = ib[2] - ib[0] - 140 * s * K
    full_w = fi.getlength(typed)
    shift_x = max(0.0, full_w - maxw)
    # typed text in its own strip, clipped to the field (scrolls left when long, soft fade at the left edge)
    tl = Image.new('RGBA', (int(maxw + 8 * s * K), int(ib[3] - ib[1])), (0, 0, 0, 0)); dt = ImageDraw.Draw(tl)
    x = -shift_x; ty = cy_ - ib[1]
    accent_last = len([w for w in words_now if w]) >= 2 or (len(target_words) >= 2 and len(words_now) >= 2)
    for i, w in enumerate(words_now):
        col = IOS['ink']
        if w: dt.text((x, ty), w, font=fi, fill=_ui_a(col), anchor='lm')
        x += fi.getlength(w + ' ')
    if shift_x > 0:
        fm_ = Image.linear_gradient('L').rotate(90, expand=True).resize((int(40 * s * K), tl.height))
        a_ = tl.split()[3]; a_.paste(Image.composite(a_.crop((0, 0, fm_.width, tl.height)), Image.new('L', fm_.size, 0), fm_), (0, 0))
        tl.putalpha(a_)
    im.alpha_composite(tl, (int(tx0), int(ib[1])))
    if not typed:
        d.text((tx0, cy_), str(e.o.get('placeholder') or ('Повідомлення' if cyr else 'Message')), font=fi, fill=_ui_a(IOS['ph']), anchor='lm')
    caret_x = tx0 - shift_x + full_w + 3 * s * K
    if (int(lt * 2.5) % 2 == 0) or (t0 <= lt <= t1):
        d.rounded_rectangle([caret_x, cy_ - 24 * s * K, caret_x + 3.2 * s * K, cy_ + 24 * s * K], int(1.6 * s * K), fill=_ui_a(IOS['blue']))
    # send button
    sb = 64 * s * K * (1 + 0.18 * math.sin(math.pi * clamp((lt - t1 - 0.04) / 0.22)))
    sbx, sby = ib[2] - 14 * s * K - 64 * s * K / 2, (ib[1] + ib[3]) / 2
    d.ellipse([sbx - sb / 2, sby - sb / 2, sbx + sb / 2, sby + sb / 2], fill=_ui_a(IOS['blue'] if typed else IOS['off']))
    up = _ui_icon('up', sb * 0.5, (255, 255, 255), sw=sb * 0.5 * 0.12)
    im.alpha_composite(up, (int(sbx - up.width / 2), int(sby - up.height / 2)))
    # suggestions
    sugg, hi = _ui_kb_suggest(typed, target_words, cyr, picking)
    sy0 = ib[3] + 14 * s * K; sh = 62 * s * K
    cw = (KW - 2 * pad) * K / 3
    fsg = ay_font('hm', 29 * s * K); fsgb = ay_font('h', 29 * s * K)
    for i, sg in enumerate(sugg):
        cx0 = pad * K + i * cw
        if i > 0: d.line([(cx0, sy0 + sh * 0.25), (cx0, sy0 + sh * 0.75)], fill=_ui_a(IOS['ink'], 40), width=max(2, int(1.2 * s * K)))
        if i == hi:
            d.rounded_rectangle([cx0 + 8 * s * K, sy0 + 4 * s * K, cx0 + cw - 8 * s * K, sy0 + sh - 4 * s * K], int(14 * s * K), fill=_ui_a(IOS['key']))
        f = fsgb if i == 1 else fsg
        t = sg
        while f.getlength(t) > cw - 24 * s * K and len(t) > 3: t = t[:-2] + '…' if not t.endswith('…') else t[:-2] + '…'
        d.text((cx0 + cw / 2, sy0 + sh / 2 + 1), t, font=f, fill=_ui_a(IOS['ink'], 255 if (i == 1 or i == hi) else 200), anchor='mm')
    # pressed key + balloon
    pk_age = lt - press_t
    if press_key is not None and pk_age < 0.16:
        kk = press_key.lower() if press_key.lower() in keys else (' ' if press_key == ' ' else None)
        if kk in keys:
            x_, y_, w_, h_ = keys[kk]
            fl = 1 - pk_age / 0.16
            X0, Y0, X1, Y1 = x_ * K, y_ * K, (x_ + w_) * K, (y_ + h_) * K
            if kk == ' ':
                d.rounded_rectangle([X0, Y0, X1, Y1], int(12 * s * K), fill=_ui_a(IOS['spec'], int(255 * fl)))
                d.text(((X0 + X1) / 2, (Y0 + Y1) / 2), 'пробіл' if cyr else 'space', font=ay_font('hm', 25 * s * K), fill=_ui_a(IOS['ink'], int(255 * fl)), anchor='mm')
            else:
                # iOS key popup: a white balloon grown out of the pressed key, letter enlarged
                pa = int(255 * min(1.0, fl * 1.8))
                pop_ = Image.new('RGBA', im.size, (0, 0, 0, 0)); dp = ImageDraw.Draw(pop_)
                bw_, bh_ = w_ * 1.5 * K, h_ * 1.25 * K
                bx = (X0 + X1) / 2; by1 = Y0 + 6 * s * K; by0 = by1 - bh_
                bxa = clamp(bx - bw_ / 2, 4, im.width - 4 - bw_)
                col_ = _ui_a(IOS['key'])
                dp.rounded_rectangle([bxa, by0, bxa + bw_, by1 + 10 * s * K], int(18 * s * K), fill=col_)
                dp.rectangle([X0, by1 - 4 * s * K, X1, Y1 - 12 * s * K], fill=col_)
                dp.rounded_rectangle([X0, Y0, X1, Y1], int(12 * s * K), fill=col_)
                dp.text((bxa + bw_ / 2, (by0 + by1) / 2), press_key, font=ay_font('hm', 56 * s * K), fill=_ui_a(AY['ink']), anchor='mm')
                sh_ = Image.new('RGBA', im.size, (4, 10, 6, 0)); sh_.putalpha(pop_.split()[3].point(lambda v: v * 120 // 255).filter(ImageFilter.GaussianBlur(6 * s * K)))
                sh_.alpha_composite(pop_)
                if pa < 255: sh_.putalpha(sh_.split()[3].point(lambda v: v * pa // 255))
                im.alpha_composite(sh_)
    ov = ay_np(_ui_down(im))
    sa = ov[..., 3:4]
    layer[..., :3] = ov[..., :3] * sa + layer[..., :3] * (1 - sa)
    layer[..., 3:4] = sa + layer[..., 3:4] * (1 - sa)
    if vel > 2:
        layer = _ui_vblur(_ui_pad(layer, int(vel) + 2), vel)
        comp(c, layer, kx, ky + oy - int(vel) - 2, a)
    else:
        comp(c, layer, kx, ky + oy, a)


# ================================================================ ay-liquid-glass
@effect('ay-liquid-glass', 'CTA ending: glass pill drops and morphs into a DM notification, a glass Instagram nav bar with a sliding selector, then a frosted CTA card')
def fx_ay_liquid_glass(c, e):
    s = _ui_s(c); lt = c.lt; d_ = e.d; u = lt / d_; K = _UI_K
    word = str(e.o.get('text') or 'ЕФЕКТИ')
    note = str(e.o.get('note') or f'{ay_handle(e)} надіслала тобі всі ефекти')
    label = str(e.o.get('label') or 'ВСІ ЕФЕКТИ З ВІДЕО').upper()
    top_line = str(e.o.get('top') or 'Напиши')
    sub = str(e.o.get('sub') or 'і я надішлю тобі все')
    out = ease_inout(clamp((d_ - lt) / 0.2)) if str(e.o.get('outro', '0')) not in ('0', 'false') else 1.0
    # ---- 1. background blur + slight dim (from ~0.40)
    bl = ease_inout(_ui_seg(u, 0.40, 0.54)) * out
    if bl > 0:
        _ui_blur_frame(c, 26 * s * bl)
        c.img = c.img * (1 - 0.18 * bl)
    # ---- 2. notification: pill drops, morphs wide, content, then lifts away
    nw0, nh0 = 230 * s, 66 * s
    nw1, nh1 = 980 * s, 168 * s
    ncx = c.W / 2; ny1 = 70 * s + nh1 / 2
    p_drop = _ui_spring(_ui_seg(u, 0.0, 0.11), 5.5, 8.0)
    p_morph = _ui_seg(u, 0.075, 0.20)
    mw = _ui_spring(p_morph * 1.1, 6.0, 9.0); mh = _ui_spring(clamp(p_morph * 1.3 - 0.15), 6.5, 10.0)
    p_away = ease_inout(_ui_seg(u, 0.43, 0.51))
    nw = nw0 + (nw1 - nw0) * mw; nh = nh0 + (nh1 - nh0) * mh
    nw = nw * (1 - 0.6 * p_away); nh = nh * (1 - 0.4 * p_away)
    ncy = -nh0 + (ny1 + nh0) * p_drop - p_away * 210 * s
    na = clamp(u / 0.03) * (1 - p_away)
    if na > 0.003:
        _ui_glass(c, ncx, ncy, nw, nh, min(nh / 2, 52 * s), blur=10, refr=22, tint=(28, 40, 26), amt=0.42, bright=0.95,
                  rim=0.75, alpha=na, shadow=0.22, ca=0.08, glow=0.10)
        ca_ = _ui_seg(u, 0.16, 0.22) * (1 - p_away)
        if ca_ > 0:
            def mk_note():
                W2, H2 = int(nw1 * K), int(nh1 * K)
                im = Image.new('RGBA', (W2, H2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
                av = 96 * s * K
                f = _ui_face(c, e, int(av), ring=int(4 * s * K), ring_col=IG['ring'])
                im.alpha_composite(f, (int(36 * s * K), int((H2 - av) / 2)))
                tx = 36 * s * K + av + 26 * s * K
                fu = ay_font('h', 31 * s * K); fn = ay_font('hm', 30 * s * K)
                d.text((tx, H2 / 2 - 22 * s * K), ay_handle(e).lstrip('@'), font=fu, fill=_ui_a(AY['tx']), anchor='lm')
                d.text((W2 - 40 * s * K, H2 / 2 - 22 * s * K), 'ЗАРАЗ', font=ay_font('mm', 20 * s * K), fill=_ui_a(AY['tx'], 150), anchor='rm')
                msg = note.replace(ay_handle(e) + ' ', '') if note.startswith(ay_handle(e)) else note
                maxw = W2 - tx - 40 * s * K
                while fn.getlength(msg) > maxw and len(msg) > 4: msg = msg[:-2] + '…'
                d.text((tx, H2 / 2 + 24 * s * K), msg, font=fn, fill=_ui_a((255, 255, 255), 225), anchor='lm')
                return ay_np(_ui_down(im))
            NL = cached(e, 'note', mk_note)
            _ui_comp(c, NL, ncx, ncy + (1 - ease_out(ca_)) * 10 * s, ca_ * na, scale=min(1.0, nw / nw1))
    # ---- 3. nav bar with the liquid selector
    bw1, bh1 = 820 * s, 132 * s
    bcx, bcy = c.W / 2, c.H - float(e.o.get('nav_bottom', 64)) * s - bh1 / 2
    p_b = _ui_spring(_ui_seg(u, 0.02, 0.12), 6.0, 9.0)
    p_bm = _ui_seg(u, 0.07, 0.19)
    bw = 150 * s + (bw1 - 150 * s) * _ui_spring(p_bm * 1.1, 6.0, 9.0); bh = 60 * s + (bh1 - 60 * s) * _ui_spring(clamp(p_bm * 1.3 - 0.1), 6.5, 10.0)
    ba = clamp(_ui_seg(u, 0.02, 0.06)) * out
    if ba > 0.003:
        sc_ = 0.55 + 0.45 * p_b
        _ui_glass(c, bcx, bcy + (1 - p_b) * 60 * s, bw * sc_, bh * sc_, bh * sc_ / 2, blur=2.6, refr=26, tint=(14, 24, 14), amt=0.22,
                  bright=1.0, rim=0.8, alpha=ba, shadow=0.2, ca=0.10, glow=0.12)
        ia = _ui_seg(u, 0.15, 0.21) * out
        kinds = ['home', 'search', 'reels', 'send', 'user']
        xs = [bcx - bw1 / 2 + bw1 * (i + 0.5) / 5 for i in range(5)]
        if ia > 0:
            for i, k_ in enumerate(kinds):
                ic = cached(e, ('ic', k_), lambda k_=k_: ay_np(_ui_icon(k_, 50 * s, AY['cream'], sw=50 * s * 0.085)))
                _ui_comp(c, ic, xs[i], bcy, ia * ba, scale=0.85 + 0.15 * ease_out(ia))
            # selector blob: home -> search -> reels -> send (stretching while it moves)
            stops = [0.21, 0.27, 0.33, 0.39]
            target = int(e.o.get('nav', 3))
            path = [0, 1, 2, 3] if target >= 3 else list(range(target + 1))
            pos = float(path[0]); vel = 0.0
            for j in range(1, len(path)):
                q = _ui_seg(u, stops[j - 1] + 0.012, stops[j])
                if q > 0:
                    eq = ease_inout(q); pos = path[j - 1] + (path[j] - path[j - 1]) * eq
                    vel = math.sin(math.pi * q)
            bx = xs[0] + (xs[1] - xs[0]) * pos
            selw = 132 * s * (1 + 0.55 * vel); selh = 92 * s * (1 - 0.12 * vel)
            _ui_glass(c, bx, bcy, selw, selh, selh / 2, blur=0.8, refr=7, zoom=1.12, tint=(255, 255, 255), amt=0.24, bright=1.15,
                      rim=0.95, alpha=ia * ba, shadow=0.12, ca=0.12, glow=0.16)
    # ---- 4. CTA card grows from a small glass tile over the (blurred) face
    p_card = _ui_seg(u, 0.44, 0.60)
    if p_card > 0:
        cw1, ch1 = 900 * s, 640 * s
        ccx, ccy1 = c.W / 2, c.H * float(e.o.get('y', 0.47))
        q = _ui_spring(p_card * 1.05, 5.0, 7.5)
        fx0, fy0 = c.fx, c.fy
        cw = 200 * s + (cw1 - 200 * s) * q; ch = 150 * s + (ch1 - 150 * s) * _ui_spring(clamp(p_card * 1.15 - 0.05), 5.5, 8.0)
        ccx_ = fx0 + (ccx - fx0) * clamp(q); ccy = fy0 + (ccy1 - fy0) * clamp(q)
        _ui_glass(c, ccx_, ccy, cw, ch, min(56 * s, ch / 2), blur=10, refr=34, zoom=1.04, tint=(30, 44, 28), amt=0.30, bright=1.0,
                  rim=0.85, alpha=clamp(p_card * 4) * out, shadow=0.26, ca=0.10, glow=0.12)
        ta = _ui_seg(u, 0.55, 0.68)
        if ta > 0:
            def mk_lines():
                fl = ay_font('mm', 22 * s);
                L1 = ay_np(_ui_t(label, 25 * s, 'mm', AY['lime'], track=6 * s))
                L2 = ay_np(_ui_t(top_line, 74 * s, 'h', AY['tx']))
                size = ay_fit(word, cw1 * 0.84, 'hb', 210 * s)
                L3 = ay_np(_ui_grad_text(word, size, 'hb', AY['cream'], AY['lime']))
                L4 = ay_np(_ui_t(sub, 50 * s, 'hm', AY['tx']))
                return [L1, L2, L3, L4]
            Ls = cached(e, 'cta', mk_lines)
            hs_ = [Lx.shape[0] for Lx in Ls]
            gaps = [10 * s, -6 * s, 0 * s]
            tot = sum(hs_) + sum(gaps)
            y = ccy - tot / 2
            for j, Lx in enumerate(Ls):
                qj = ease_out(clamp(ta * 1.8 - j * 0.22))
                if qj > 0:
                    _ui_comp(c, (_ui_shadow_np(Lx, 10 * s, 4 * s, 0.25)) if j >= 1 else Lx, ccx_, y + hs_[j] / 2 + (1 - qj) * 26 * s,
                             qj * out, scale=0.96 + 0.04 * qj)
                y += hs_[j] + (gaps[j] if j < len(gaps) else 0)


def _ui_t(s_, size, kind='h', fill=AY['tx'], track=0.0):
    im = ay_text(s_, size * _UI_K, kind, fill, track * _UI_K)
    return _ui_down(im)


def _ui_grad_text(s_, size, kind, c_top, c_bot):
    im = ay_text(s_, size * _UI_K, kind, (255, 255, 255))
    a = np.asarray(im, np.float32) / 255
    h = a.shape[0]; t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    col = np.float32(c_top) / 255 * (1 - t) + np.float32(c_bot) / 255 * t
    a[..., :3] = col
    return _ui_down(ay_pil(a))
