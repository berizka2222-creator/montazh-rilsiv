# ay «cam» group: camera / compositing tricks from the reference reel, in the person's brand.
#   ay-clone-row     lagging copies of her fan out to one side in a receding row, then collapse back into her
#   ay-blade-slice   a bright blade sweeps diagonally, the frame is cut along it, the upper part slides and drops back
#   ay-layer-explode the frame tilts into 3D and splits into stacked transparent layers, then folds back flat
#   ay-rack-focus    focus pull: background soft -> focus racks to the background -> back to her
#   ay-blow-away     she breaks into flakes that blow away (Thanos), then they fly back
#   ay-dolly-zoom    vertigo: the background zooms while she keeps her size
# Helpers are prefixed _cam_. Uses fx.py / ay_fx.py helpers (exec'd in the same namespace).

_cam_grid_cache = {}


def _cam_grid(W, H):
    k = (W, H)
    if k not in _cam_grid_cache:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        _cam_grid_cache.clear(); _cam_grid_cache[k] = (xx, yy)
    return _cam_grid_cache[k]


def _cam_smooth(a, b, x):
    """smoothstep from a to b."""
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _cam_pushpull(img, w):
    """Fill where w==0 with a smooth pyramid (push-pull) interpolation of the valid pixels. img HxWx3, w HxW 0..1."""
    pyr = []
    I = img * w[..., None]; Wt = w.astype(np.float32).copy()
    pyr.append((I, Wt))
    while min(Wt.shape[:2]) > 6:
        I = cv2.pyrDown(I); Wt = cv2.pyrDown(Wt); pyr.append((I, Wt))
    I, Wt = pyr[-1]
    cur = I / np.maximum(Wt, 1e-4)[..., None]
    for I, Wt in reversed(pyr[:-1]):
        up = cv2.pyrUp(cur, dstsize=(I.shape[1], I.shape[0]))
        a = np.clip(Wt * 2.2, 0, 1)[..., None]
        cur = (I / np.maximum(Wt, 1e-4)[..., None]) * a + up * (1 - a)
    return np.clip(cur, 0, 1)


def _cam_row_fill(img, hole):
    """Fill the hole row by row: interpolate between the background just left and right of it (walls, furniture lines
    run on), one-sided rows extend their side, empty rows copy from above. Then smoothed so rows do not streak."""
    h, w = hole.shape
    valid = (~hole.astype(bool)).astype(np.float32)
    # boundary colours from a locally averaged background (normalised blur), so one noisy pixel does not streak a row
    num = cv2.GaussianBlur(img * valid[..., None], (0, 0), 2.5); den = cv2.GaussianBlur(valid, (0, 0), 2.5)
    sm = num / np.maximum(den, 1e-4)[..., None]
    idx = np.arange(w)[None, :].repeat(h, 0)
    v = valid > 0.5
    L = np.maximum.accumulate(np.where(v, idx, -1), axis=1)
    R = np.minimum.accumulate(np.where(v, idx, w)[:, ::-1], axis=1)[:, ::-1]
    hasL, hasR = L >= 0, R < w
    off = max(2, w // 90)                                       # sample a little away from the edge (flyaway hair lives there)
    L = np.where(L >= 0, np.maximum(0, L - off), L); R = np.where(R < w, np.minimum(w - 1, R + off), R)
    Lc = np.take_along_axis(sm, np.clip(L, 0, w - 1)[..., None].repeat(3, 2), axis=1)
    Rc = np.take_along_axis(sm, np.clip(R, 0, w - 1)[..., None].repeat(3, 2), axis=1)
    t = np.clip((idx - L) / np.maximum(R - L, 1), 0, 1)[..., None]
    t = t * t * (3 - 2 * t)
    out = np.where((hasL & hasR)[..., None], Lc * (1 - t) + Rc * t, np.where(hasL[..., None], Lc, Rc))
    none = ~(hasL | hasR)
    if none.any():
        for y in range(1, h):
            if none[y].any(): out[y, none[y]] = out[y - 1, none[y]]
    out = np.where(v[..., None], img, out)
    out = cv2.GaussianBlur(out, (0, 0), sigmaX=3, sigmaY=10)
    return np.clip(out, 0, 1).astype(np.float32)


def _cam_radial_fill(img, hole, cx, cy):
    """Fill the hole by pulling the nearest valid pixel along rays from (cx, cy) outward (so a zoom about that point
    reveals the background right next to her edge, stretched, instead of a smear)."""
    h, w = hole.shape
    R = float(np.hypot(max(cx, w - cx), max(cy, h - cy))) + 2
    na, nr = 720, int(R)
    flags = cv2.WARP_POLAR_LINEAR + cv2.INTER_LINEAR + cv2.WARP_FILL_OUTLIERS
    P = cv2.warpPolar(img, (nr, na), (cx, cy), R, flags)
    Ph = cv2.warpPolar(hole.astype(np.float32), (nr, na), (cx, cy), R, flags) > 0.5
    idx = np.where(~Ph, np.arange(nr)[None, :], nr - 1)
    nxt = np.minimum.accumulate(idx[:, ::-1], axis=1)[:, ::-1]          # next valid radius outward
    F = np.take_along_axis(P, nxt[..., None].repeat(3, 2), axis=1)
    F = cv2.GaussianBlur(F, (0, 0), sigmaX=1.0, sigmaY=2.5)            # soften across angles
    out = cv2.warpPolar(F, (w, h), (cx, cy), R, cv2.WARP_POLAR_LINEAR + cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    return np.clip(out, 0, 1)


def _cam_plate(c, e, key='cplate', mode='pp', q=2, grow=0.012):
    """A cleaner background plate than ay_plate: person hole (dilated) filled by push-pull ('pp') or along rays from the
    face ('radial'), soft-blended, with a faint grain so the fill is not plastic. Updates with background the later frames
    uncover. Float RGB (H, W, 3)."""
    st = e.state
    W, H = c.W, c.H
    if key not in st:
        sw, sh = W // q, H // q
        sm = cv2.resize(c.img, (sw, sh), interpolation=cv2.INTER_AREA)
        mm = cv2.resize(c.m, (sw, sh), interpolation=cv2.INTER_AREA)
        r = max(3, int(W * grow / q)) | 1
        hole = cv2.dilate((mm > 0.06).astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        if mode == 'radial':
            fill = _cam_radial_fill(sm, hole, c.fx / q, c.fy / q)
        elif mode == 'row':
            fill = _cam_row_fill(sm, hole)
        else:
            fill = _cam_pushpull(sm, 1 - hole.astype(np.float32))
        fill = cv2.resize(fill, (W, H), interpolation=cv2.INTER_CUBIC)
        hm = cv2.GaussianBlur(cv2.resize(hole.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), W * 0.004)
        hm = np.clip(hm * 1.3, 0, 1)[..., None]
        # grain: the fill gets the same fine texture as the background around it, so it does not read as a smooth blob
        g = cv2.cvtColor(c.img, cv2.COLOR_RGB2GRAY)
        hp = g - cv2.GaussianBlur(g, (0, 0), 2.0)
        sd = float(np.std(hp[hm[..., 0] < 0.05])) if (hm < 0.05).any() else 0.01
        rnd = np.random.default_rng(5)
        nz = cv2.GaussianBlur(rnd.normal(0, 1, (H, W)).astype(np.float32), (0, 0), sigmaX=0.7, sigmaY=1.6)
        nz *= sd / max(1e-4, float(nz.std()))
        fill = fill + nz[..., None]
        st[key] = (c.img * (1 - hm) + fill * hm).astype(np.float32)
        st[key + '_seen'] = 1 - hm[..., 0]
    else:
        # only trust background well clear of her (flyaway hair lives just outside the mask)
        q4 = 4; r = max(2, int(W * grow * 1.5 / q4))
        md = cv2.dilate(cv2.resize(c.m, (W // q4, H // q4), interpolation=cv2.INTER_AREA), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        bgm = np.clip(1 - cv2.resize(cv2.GaussianBlur(md, (0, 0), 2), (W, H), interpolation=cv2.INTER_LINEAR) * 3, 0, 1)
        new = bgm * (1 - st[key + '_seen'])
        if new.max() > 0.05:
            st[key] = st[key] * (1 - new[..., None]) + c.img * new[..., None]
            st[key + '_seen'] = np.maximum(st[key + '_seen'], bgm)
    return st[key]


def _cam_rgba(im):
    return np.asarray(im.convert('RGBA'), np.float32) / 255.0


# ---------------------------------------------------------------- 1. clone row
@effect('ay-clone-row', 'lagging copies of you fan out to one side in a receding row, then collapse back into you')
def fx_ay_clone_row(c, e):
    W, H = c.W, c.H
    n = max(1, min(6, int(e.o.get('n', 4))))
    sd = str(e.o.get('side', 'auto')).lower()
    lag = max(1, int(e.o.get('lag', 3)))                      # frames of delay between copies
    def layout():
        # how far her silhouette reaches on each side at face and shoulder height
        rows = [int(clamp(c.fy, 0, H - 1)), int(clamp(c.fy + c.fw * 1.1, 0, H - 1))]
        ext = {}
        for sgn in (-1, 1):
            best = c.fw * 0.6
            for r in rows:
                xsr = np.where(c.m[r] > 0.5)[0]
                if len(xsr): best = max(best, (c.fx - xsr.min()) if sgn < 0 else (xsr.max() - c.fx))
            ext[sgn] = best
        if sd.startswith('r'): side = 1
        elif sd.startswith('l'): side = -1
        else:   # the side with more free room beyond her silhouette
            side = -1 if (c.fx - ext[-1]) > (W - c.fx - ext[1]) else 1
        step = W * float(e.o.get('gap', 0.12))
        first = max(step, ext[side] * 0.62)                      # first copy clears enough of her to show ~half of itself
        xs = [first + step * sum(0.88 ** i for i in range(j)) for j in range(n)]
        return side, [x / W for x in xs]
    side, xs = cached(e, 'lay', layout)
    hist = ay_history(c, e, n=n * lag + 2)
    src = c.img.copy()
    base = c.img.copy()
    # soft fade of every copy's bottom (a shrunken copy must not end in a hard line)
    vf = cached(e, 'vf', lambda: _cam_smooth(H * 1.0, H * 0.72, np.arange(H, dtype=np.float32)).astype(np.float32)[:, None])
    stagger = min(0.11, e.d * 0.42 / n)
    t_col = e.d - 0.34
    # slot positions: spacing shrinks with depth
    for j in range(n, 0, -1):                                  # farthest first
        t0 = 0.03 + (j - 1) * stagger
        p = ease_out((c.lt - t0) / 0.3)
        p *= 1 - ease_inout((c.lt - (t_col + (n - j) * 0.025)) / 0.26)
        if p <= 0.002: continue
        h = hist[max(0, len(hist) - 1 - j * lag)]
        hfx, hfy, hfw = h['f']
        s = 1 - (1 - 0.8 ** j) * p
        tx = c.fx + side * W * xs[j - 1] * p
        ty = c.fy - H * float(e.o.get("rise", 0.042)) * j * p          # farther copies step up, like a fanned deck
        M = np.float32([[s, 0, tx - s * hfx], [0, s, ty - s * hfy]])
        cm = cv2.warpAffine(h['m'] * vf[:, 0][:, None], M, (W, H), flags=cv2.INTER_LINEAR)
        if cm.max() < 0.02: continue
        ci = cv2.warpAffine(h['img'], M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # contact shadow on what is behind this copy
        q = 4
        sh = cv2.GaussianBlur(cv2.resize(cm, (W // q, H // q), interpolation=cv2.INTER_AREA), (0, 0), W * 0.02 / q)
        sh = cv2.resize(sh, (W, H), interpolation=cv2.INTER_LINEAR)
        sh = np.roll(sh, int(-side * W * 0.018), axis=1)
        base *= (1 - 0.28 * sh * min(1, p * 2))[..., None]
        # deeper = darker, a touch hazier and less saturated
        dk = 1 - 0.08 * j
        lum = (ci @ np.float32([0.299, 0.587, 0.114]))[..., None]
        ci = (lum + (ci - lum) * (1 - 0.08 * j)) * dk
        a = (cm * min(1, p * 2.5) * (1 - 0.05 * j))[..., None]
        base = base * (1 - a) + ci * a
    c.img = base
    ay_person(c, src)


# ---------------------------------------------------------------- 2. blade slice
@effect('ay-blade-slice', 'a bright blade sweeps diagonally and cuts the frame, the upper part slides and drops back')
def fx_ay_blade_slice(c, e):
    W, H = c.W, c.H
    ang = math.radians(float(e.o.get('angle', -17)))        # negative: rising to the right
    slide = float(e.o.get('slide', 0.04))
    tx_, ty_ = math.cos(ang), math.sin(ang)
    nx_, ny_ = -ty_, tx_                                        # normal, points down
    p0 = cached(e, 'p0', lambda: (c.fx, c.fy + c.fw * 0.2))     # through the lower face, fixed for the whole cut
    xx, yy = _cam_grid(W, H)
    rx, ry = xx - p0[0], yy - p0[1]
    dl = rx * nx_ + ry * ny_                                     # signed distance to the line (px)
    u = rx * tx_ + ry * ty_                                      # position along it
    lt, d = c.lt, e.d
    T_sw = min(0.22, d * 0.2)                                    # blade sweep
    t_open, t_close = T_sw * 0.85, d * 0.62
    closef, drop = 1.0, 0.0
    cl = (lt - t_close) / 0.24
    if cl > 0:
        cl = clamp(cl)
        closef = (1 - cl) ** 3
        drop = 0.12 * math.sin((cl - 0.55) / 0.45 * math.pi) if 0.55 < cl < 1 else 0.0   # drops back a touch past flat
    # the cut opens right behind the travelling blade (a wave along the line), closes all at once
    t_u = T_sw * (u / W + 0.75) / 1.6
    x = np.clip((lt - t_u - 0.015) / 0.2, 0, 1)
    op_a = (1 - (1 - x) ** 3) * closef - drop
    op = float(op_a.max()) if lt > 0 else 0.0
    img = c.img
    out = img
    if op > 0.002 or drop > 0:
        s = slide * W * op_a
        wedge = 0.4 + 0.6 * np.clip(0.5 - u / (W * 1.1), 0, 1)
        g = W * float(e.o.get('gap', 0.02)) * op_a * wedge
        mapx = (xx - tx_ * s + nx_ * g).astype(np.float32)
        mapy = (yy - ty_ * s + ny_ * g).astype(np.float32)
        moved = cv2.remap(img, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        upper = np.clip(0.5 - dl, 0, 1)[..., None]
        gapm = np.clip(dl + g + 0.5, 0, 1)[..., None]
        gapc = np.float32(AY['c0']) / 255
        top = moved * (1 - gapm) + gapc * gapm
        out = img * (1 - upper) + top * upper
        # highlights on the two cut edges
        e1 = np.exp(-((dl + g) / 1.5) ** 2) * (upper[..., 0] > 0) * np.clip(np.abs(op_a) * 3, 0, 1)
        e2 = np.exp(-(dl / 1.3) ** 2) * 0.55 * np.clip(np.abs(op_a) * 3, 0, 1)
        hl = np.float32(AY['white']) / 255
        out = out + (e1 * 0.95 + e2)[..., None] * (hl - out)
    # the blade: a bright streak travelling along the line, a scored hairline behind it
    if lt < T_sw + 0.05:
        k = lt / T_sw
        head = (-0.75 + 1.6 * k) * W
        L = W * 0.5
        along = (u - head) / L
        tail = np.clip(1 + along, 0, 1) ** 2 * (along <= 0)
        core = np.exp(-(dl / 1.6) ** 2) * tail
        glow = np.exp(-(dl / 9.0) ** 2) * tail * 0.35
        trace = np.exp(-(dl / 0.9) ** 2) * 0.55 * (u < head) * clamp((T_sw + 0.05 - lt) / 0.08)
        lime = np.float32(AY['lime_hi']) / 255
        out = out + glow[..., None] * (lime - out) + np.clip(core + trace, 0, 1)[..., None] * (1 - out)
    # flash + tiny shake on the cut and on the drop
    for tk, amp in ((t_open, 1.0), (t_close + 0.2, 0.6)):
        q = (lt - tk) / 0.18
        if 0 <= q < 1:
            dec = (1 - q) ** 2 * amp
            out = out + (1 - out) * 0.07 * dec * (tk == t_open)
            jx = math.sin(q * 41 + tk) * W * 0.006 * dec; jy = math.cos(q * 37) * W * 0.004 * dec
            out = cv2.warpAffine(out.astype(np.float32), np.float32([[1, 0, jx], [0, 1, jy]]), (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    c.img = np.clip(out, 0, 1).astype(np.float32)


# ---------------------------------------------------------------- 3. layer explode
def _cam_caption(spec, W):
    """Pills of caption lines; '*word*' = Nyght italic accent (dark pink on cream)."""
    lines = [l for l in spec.split('|') if l.strip()]
    size = int(W * 0.052); k = 2
    ims = []
    for ln in lines:
        parts = []
        for j, chunk in enumerate(ln.split('*')):
            if chunk: parts.append((chunk, 'i' if j % 2 else 'h', AY['pink_dk'] if j % 2 else AY['ink']))
        fs = [ay_font(kd, size * k * (1.3 if kd == 'i' else 1)) for _, kd, _ in parts]
        ws = [f.getlength(t) for (t, _, _), f in zip(parts, fs)]
        padx, pady = size * 0.5 * k, size * 0.28 * k
        Wd = int(sum(ws) + 2 * padx); Hd = int(size * 1.18 * k + 2 * pady)
        im = Image.new('RGBA', (Wd, Hd), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
        dr.rounded_rectangle([0, 0, Wd - 1, Hd - 1], int(size * 0.32 * k), fill=AY['cream'] + (255,))
        x = padx; base = pady + size * 0.92 * k
        for (t, kd, col), f, w_ in zip(parts, fs, ws):
            dr.text((x, base), t, font=f, fill=col + (255,), anchor='ls'); x += w_
        ims.append(im.resize((Wd // k, Hd // k), Image.LANCZOS))
    return ims


def _cam_layer_textures(c, e):
    W, H = c.W, c.H
    # caption plane
    cap = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    pills = _cam_caption(str(e.o.get('caption', 'так збирається|кожен *креатив*')), W)
    y = max(c.fy + c.fw * 1.25, H * 0.6)
    for p in pills:
        p2 = shadowed(p, blur=max(4, W // 120), dy=W // 240, alpha=90)
        cap.alpha_composite(p2, (int(W / 2 - p2.width / 2), int(y - (p2.height - p.height) / 2)))
        y += p.height * 1.12
    return _cam_rgba(cap)


def _cam_label_tex(txt, W):
    im = ay_text(txt, int(W * 0.034), 'mb', fill=AY['lime'], track=W * 0.005)
    return _cam_rgba(im)


@effect('ay-layer-explode', 'the frame tilts into 3D and splits into stacked transparent layers, then folds back flat')
def fx_ay_layer_explode(c, e):
    W, H = c.W, c.H
    src = c.img.copy()
    plate = _cam_plate(c, e, mode='row', grow=0.02)
    cap = cached(e, 'cap', lambda: _cam_layer_textures(c, e))
    labs = cached(e, 'labs', lambda: [_cam_label_tex(t, W) for t in ('01 ФОН', '02 ЛЮДИНА', '03 ТЕКСТ')])
    lt, d = c.lt, e.d
    k = ease_inout(lt / min(0.38, d * 0.36)) * (1 - ease_inout((lt - (d - min(0.34, d * 0.32))) / min(0.34, d * 0.32)))
    capa = clamp(lt / 0.15) * clamp((d - lt) / 0.12)
    # textures: premultiplied RGBA
    m = c.m[..., None]
    person = np.concatenate([src * m, m], 2)
    platet = np.concatenate([plate, np.ones((H, W, 1), np.float32)], 2)
    capt = cap.copy(); capt[..., :3] *= capt[..., 3:4]; capt *= capa
    empty = None
    planes = [(platet, 0), (empty, None), (person, 1), (empty, None), (capt, 2)]
    n = len(planes)
    # camera
    yaw = math.radians(float(e.o.get('yaw', 40))) * k
    pitch = math.radians(-9) * k
    roll = math.radians(-2.5) * k
    D0 = H * 2.4
    D = D0 * (1 + 0.5 * k)
    spread = W * float(e.o.get('spread', 0.3)) * k
    cy_, sy_ = math.cos(yaw), math.sin(yaw); cp, sp = math.cos(pitch), math.sin(pitch); cr, sr = math.cos(roll), math.sin(roll)
    Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]]); Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    R = Rz @ Rx @ Ry
    ox, oy = -W * 0.1 * k, H * 0.035 * k                      # the stack sits a little left of centre
    corners = np.array([[-W / 2, -H / 2], [W / 2, -H / 2], [W / 2, H / 2], [-W / 2, H / 2]], np.float64)
    src_pts = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    # background
    bg = cached(e, 'bg', lambda: (lambda yy, xx: (np.float32(AY['c1']) / 255 + (np.float32(AY['olive']) / 255 - np.float32(AY['c1']) / 255) * 0.35 *
                                                   np.exp(-(((xx - W * 0.5) / (W * 0.7)) ** 2 + ((yy - H * 0.45) / (H * 0.45)) ** 2))[..., None]).astype(np.float32))(*np.mgrid[0:H, 0:W].astype(np.float32)))
    out = bg.copy()
    olay = np.zeros((H, W), np.uint8)
    for i in range(n):
        tex, li = planes[i]
        z = (n - 1 - i - (n - 1) / 2) * spread                 # i=0 (plate) farthest
        P = np.c_[corners, np.full(4, z)] @ R.T
        Z = P[:, 2] + D
        dst = np.float32(np.c_[D0 * P[:, 0] / Z + W / 2 + ox, D0 * P[:, 1] / Z + H / 2 + oy])
        if tex is not None:
            Mh = cv2.getPerspectiveTransform(src_pts, dst)
            wt = cv2.warpPerspective(tex, Mh, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
            if li is not None and k > 0.02:
                lab = labs[li]; lh, lw = lab.shape[:2]
                Ml = cv2.getPerspectiveTransform(np.float32([[0, 0], [lw, 0], [lw, lh], [0, lh]]),
                                                 cv2.perspectiveTransform(np.float32([[[W * 0.045, H * 0.03], [W * 0.045 + lw, H * 0.03],
                                                                                       [W * 0.045 + lw, H * 0.03 + lh], [W * 0.045, H * 0.03 + lh]]]), Mh)[0])
                lab2 = lab.copy(); lab2[..., :3] *= lab2[..., 3:4]
                wl = cv2.warpPerspective(lab2, Ml, (W, H), flags=cv2.INTER_LINEAR) * clamp((k - 0.4) / 0.4)
                wt = wt * (1 - wl[..., 3:4]) + wl
            out = out * (1 - wt[..., 3:4]) + wt[..., :3]
        # outline
        if k > 0.01:
            olay[:] = 0
            cv2.polylines(olay, [np.int32(dst * 16)], True, 255, max(2, W // 420), cv2.LINE_AA, shift=4)
            a = (olay.astype(np.float32) / 255 * min(1, k * 2) * (0.75 if tex is None else 0.55))[..., None]
            out = out * (1 - a) + np.float32(AY['cream']) / 255 * a
    flat = clamp(k * 8)                                         # flat frame = the untouched footage (no plate seams at the edges)
    out = src * (1 - flat) + out * flat if flat < 1 else out
    c.img = np.clip(out, 0, 1).astype(np.float32)
    # the label, top-left
    txt = str(e.o.get('text', 'шари'))
    lab = cached(e, 'lab', lambda: shadowed(ay_text(txt, int(W * 0.13), 'i', fill=AY['pink']), blur=max(6, W // 90), dy=0, alpha=120))
    la = clamp((k - 0.55) / 0.35)
    if la > 0:
        place(c, lab, W * 0.07 + lab.width / 2 - W * 0.02 * (1 - la), H * 0.075 + lab.height / 2, 1, 0, la)


# ---------------------------------------------------------------- 4. rack focus
def _cam_env(u, keys):
    """piecewise ease: keys = [(u0, u1, from, to), ...] in order."""
    v = keys[0][2]
    for a, b, f, t in keys:
        if u >= a: v = f + (t - f) * ease_inout((u - a) / max(1e-6, b - a))
    return v


@effect('ay-rack-focus', 'focus pull: the background goes soft, focus racks to the background and back to you')
def fx_ay_rack_focus(c, e):
    W, H = c.W, c.H
    u = c.lt / e.d
    breath = float(e.o.get('zoom', 0.035))
    face_cam(c, 1 + breath * math.sin(math.pi * clamp(u)) ** 2, c.fy / c.H) if breath else None
    bb = _cam_env(u, [(0.0, 0.22, 0, 1), (0.36, 0.56, 1, 0), (0.7, 0.86, 0, 1), (0.88, 1.0, 1, 0)])   # background blur
    pb = _cam_env(u, [(0.0, 0.36, 0, 0), (0.36, 0.56, 0, 1), (0.7, 0.86, 1, 0)])                      # person blur
    sbg = W * float(e.o.get('blur', 0.018)); sp = W * 0.008
    img = c.img; m = c.m
    q = 4; sw, sh = W // q, H // q
    si = cv2.resize(img, (sw, sh), interpolation=cv2.INTER_AREA)
    smk = cv2.resize(m, (sw, sh), interpolation=cv2.INTER_AREA)
    up = lambda a: cv2.resize(a, (W, H), interpolation=cv2.INTER_LINEAR)
    out = img
    bgw = np.clip(1 - smk * 1.6, 0, 1)
    if bb > 0.003:
        # background blur that never pulls her colours in (normalised convolution), stronger farther from her
        def nblur(s):
            num = cv2.GaussianBlur(si * bgw[..., None], (0, 0), s); den = cv2.GaussianBlur(bgw, (0, 0), s)
            return num / np.maximum(den, 1e-3)[..., None]
        s1 = max(0.6, sbg * bb / q)
        B1, B2 = nblur(s1 * 0.5), nblur(s1)
        dist = cv2.distanceTransform((smk < 0.5).astype(np.uint8), cv2.DIST_L2, 3).astype(np.float32)
        g = np.clip(0.3 + dist / (sw * 0.35), 0, 1)[..., None]
        B = B1 * (1 - g) + B2 * g
        B = B + np.clip(B - 0.7, 0, 1) * 0.35 * bb                  # highlights bloom a little, like a lens
        w = clamp(sbg * bb / (sbg * 0.3))
        Bu = up(B)
        bgl = img * (1 - w) + Bu * w
        out = bgl * (1 - m[..., None]) + img * m[..., None]
    else:
        Bu = None
    if pb > 0.003:
        s2 = max(0.6, sp * pb / q)
        pw = np.clip(smk, 0, 1)
        num = cv2.GaussianBlur(si * pw[..., None], (0, 0), s2); den = cv2.GaussianBlur(pw, (0, 0), s2)
        P = num / np.maximum(den, 1e-3)[..., None]
        a = up(den)
        w = clamp(pb / 0.3)
        under_fill = Bu if Bu is not None else up(cv2.GaussianBlur(si * bgw[..., None], (0, 0), 6) / np.maximum(cv2.GaussianBlur(bgw, (0, 0), 6), 1e-3)[..., None])
        bgonly = out * (1 - m[..., None]) + under_fill * m[..., None]
        soft = bgonly * (1 - a[..., None]) + up(P) * a[..., None]
        out = out * (1 - w) + soft * w
    # a whisper of vignette while the focus moves (sells the lens)
    v = max(bb, pb) * 0.12
    c.img = np.clip(out, 0, 1).astype(np.float32)
    if v > 0.003: vignette(c, v)


# ---------------------------------------------------------------- 5. blow away
def _cam_shards(c, e, side):
    W, H = c.W, c.H
    m = c.m
    ys, xs = np.where(m > 0.5)
    if len(xs) < 50: return None
    x0, x1 = np.percentile(xs, 0.5), np.percentile(xs, 99.5)
    rnd = np.random.default_rng(11)
    # sawtooth front: horizontal teeth of random length and height (rows)
    jag = np.zeros(H, np.float32); y = 0
    while y < H:
        L = int(rnd.uniform(0.012, 0.04) * H); hgt = rnd.uniform(0.02, 0.11)
        jag[y:y + L] = np.linspace(0, 1, max(1, len(jag[y:y + L])), dtype=np.float32) ** 1.4 * hgt
        y += L
    cs = W * float(e.o.get('flake', 0.017))
    gx = np.arange(x0 - cs, x1 + cs, cs); gy = np.arange(0, H, cs)
    cx, cy = np.meshgrid(gx, gy); cx = cx.ravel() + rnd.uniform(-0.3, 0.3, cx.size) * cs; cy = cy.ravel() + rnd.uniform(-0.3, 0.3, cy.size) * cs
    inb = (cx >= 0) & (cx < W) & (cy >= 0) & (cy < H)
    cx, cy = cx[inb], cy[inb]
    keep = m[cy.astype(int), cx.astype(int)] > 0.35
    cx, cy = cx[keep], cy[keep]
    N = len(cx)
    bw = max(1.0, x1 - x0)
    key = ((x1 - cx) / bw if side > 0 else (cx - x0) / bw) + jag[cy.astype(int)] + rnd.uniform(0, 0.03, N)
    # random convex flake: 3-5 points on a jittered circle
    nv = rnd.integers(3, 6, N)
    shapes = []
    for i in range(N):
        a = np.sort(rnd.uniform(0, 2 * math.pi, nv[i])); r = rnd.uniform(0.45, 0.85, nv[i]) * cs
        shapes.append(np.c_[np.cos(a) * r, np.sin(a) * r])
    return dict(cx=cx.astype(np.float32), cy=cy.astype(np.float32), key=key.astype(np.float32), shapes=shapes, jag=jag, x0=x0, x1=x1, bw=bw,
                vx=rnd.uniform(0.18, 0.55, N), vy=rnd.uniform(0.06, 0.28, N), spin=rnd.uniform(-540, 540, N), rot0=rnd.uniform(0, 360, N),
                wob=rnd.uniform(0, 6.28, N), life=rnd.uniform(0.75, 1.15, N), shade=rnd.uniform(-0.12, 0.1, N))


@effect('ay-blow-away', 'you break into flakes that blow away sideways and up, then fly back')
def fx_ay_blow_away(c, e):
    W, H = c.W, c.H
    sweep_from = str(e.o.get('from', 'right')).lower()
    side = 1 if sweep_from.startswith('r') else -1             # the front starts on this side of her
    back = str(e.o.get('back', True)).lower() not in ('false', '0', 'no', 'ні')
    S, L = 0.62, 0.38                                          # virtual time: sweep, flake life (front reaches the end at S)
    plate = _cam_plate(c, e, mode=str(e.o.get('fill', 'row')), grow=0.03)
    sh = cached(e, 'sh', lambda: _cam_shards(c, e, side))
    if sh is None: return
    lt, d = c.lt, e.d
    if back:
        to, tb = d * 0.5, d * 0.62
        if lt < to: v = (lt / to) ** 1.15
        elif lt < tb: v = 1.0
        else: v = 1 - ease_inout((lt - tb) / (d - tb - 0.04))
    else:
        v = (lt / d) ** 1.15
    v = clamp(v, 0, 1.0) * cached(e, 'vmax', lambda: float(np.max(sh['key'] * S + L * sh['life'])) + 0.01)
    front = v / S                                              # key below this has blown away
    xx, yy = _cam_grid(W, H)
    keymap = ((sh['x1'] - xx) / sh['bw'] if side > 0 else (xx - sh['x0']) / sh['bw']) + sh['jag'][:, None]
    gone = np.clip((front - keymap) * sh['bw'] / 2.0 + 0.5, 0, 1) * (front > 0)   # 1 px soft edge
    src = c.img
    q = 4
    md = cv2.dilate(cv2.resize(c.m, (W // q, H // q), interpolation=cv2.INTER_AREA), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * int(W * 0.02 / q) + 1,) * 2))
    md = np.maximum(c.m, cv2.resize(cv2.GaussianBlur(md, (0, 0), W * 0.004), (W, H), interpolation=cv2.INTER_LINEAR))
    pm = md * gone
    out = src * (1 - pm[..., None]) + plate * pm[..., None]
    # flying flakes
    rel = sh['key'] * S                                        # release time of each flake
    f = (v - rel) / (L * sh['life'])
    act = np.where((f > 0) & (f < 1))[0]
    if len(act):
        col_src = cv2.GaussianBlur(src, (0, 0), 2.0)
        colc = np.zeros((H, W, 3), np.uint8); alc = np.zeros((H, W), np.uint8)
        wind = side
        for i in act[np.argsort(-f[act])]:                    # oldest (most faded) first
            fi = f[i]; fe = fi ** 1.35
            px = sh['cx'][i] + wind * sh['vx'][i] * W * fe + math.sin(sh['wob'][i] + fi * 7) * W * 0.008 * fi
            py = sh['cy'][i] - sh['vy'][i] * H * fe - H * 0.04 * fi
            sc = 1 - 0.8 * fi ** 1.2
            al = (1 - fi ** 1.6)
            if sc <= 0.05 or al <= 0.02: continue
            r = math.radians(sh['rot0'][i] + sh['spin'][i] * fi)
            cr, sr = math.cos(r), math.sin(r)
            pts = sh['shapes'][i] @ np.array([[cr, sr], [-sr, cr]]) * sc
            # a tumbling flake catches the light as it turns
            tilt = abs(math.cos(r * 1.7))
            pts[:, 1] *= 0.55 + 0.45 * tilt
            ix, iy = int(sh['cx'][i]), int(sh['cy'][i])
            colv = col_src[min(H - 1, iy), min(W - 1, ix)] * (1 + sh['shade'][i] + 0.18 * (tilt - 0.5))
            colv = np.clip(colv * al, 0, 1)
            poly = np.int32((pts + [px, py]) * 8)
            cv2.fillConvexPoly(colc, poly, tuple(float(x) * 255 for x in colv), cv2.LINE_AA, shift=3)
            cv2.fillConvexPoly(alc, poly, int(al * 255), cv2.LINE_AA, shift=3)
        a = alc.astype(np.float32)[..., None] / 255
        out = out * (1 - a) + colc.astype(np.float32) / 255
    c.img = np.clip(out, 0, 1).astype(np.float32)


# ---------------------------------------------------------------- 6. dolly zoom
@effect('ay-dolly-zoom', 'vertigo: the background zooms while you keep your size')
def fx_ay_dolly_zoom(c, e):
    W, H = c.W, c.H
    amt = float(e.o.get('amount', 0.22))
    back = str(e.o.get('back', True)).lower() not in ('false', '0', 'no', 'ні')
    src = c.img
    plate = _cam_plate(c, e, mode='radial', grow=0.03)
    cx, cy = cached(e, 'ctr', lambda: (c.fx, c.fy))           # zoom centre: her face at the start (steady)
    u = c.lt / e.d
    if back:
        bell = lambda x: ease_inout(x / 0.62) * (1 - ease_inout((x - 0.76) / 0.24))
    else:
        bell = lambda x: ease_inout(x)
    s = 1 + amt * bell(u)
    ds = (1 + amt * bell(u + 1 / (c.fps * e.d))) - s          # per-frame change -> radial motion blur
    def zoom(img, z):
        M = np.float32([[z, 0, cx - z * cx], [0, z, cy - z * cy]])
        return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if abs(ds) > 0.0015:
        taps = 4
        bg = sum(zoom(plate, s * (1 + ds * 1.6 * j / taps)) for j in range(taps)) / taps
    else:
        bg = zoom(plate, s)
    # the background darkens a touch at the peak (tension), she stays as she is
    bg = bg * (1 - 0.1 * (s - 1) / max(1e-3, abs(amt)) * (amt > 0))
    m = c.m[..., None]
    c.img = (bg * (1 - m) + src * m).astype(np.float32)
    k = abs(s - 1) / max(1e-3, abs(amt))
    if k > 0.01: vignette(c, 0.22 * k)
