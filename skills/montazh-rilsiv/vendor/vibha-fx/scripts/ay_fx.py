# Reel skill: «22 ефекти» from a reference reel (2026-11-13, instagram.com/reel/Dfqx2tSOA_6), rebuilt in the person's brand.
# Not part of Vibha's original: fx.py runs this file at its end (exec), so it shares fx.py's helpers (place, comp, camera,
# face_cam, text_img, rrect, shadowed, glass, cached, ease_*, ramp, fade, pop ...) and registers into the same EFFECTS.
# Names start with "ay-". Each group of effects lives in scripts/ay/*.py and is exec'd here after the shared helpers below.
#
# Default look: deep greens, lime, soft pink, cream (lime and pink follow the brand's colours); Gilroy for headings, Nyght Serif italic for
# accent words, IBM Plex Mono for labels. Every text is Cyrillic-safe.

import glob as _ay_glob

_AY_HOME = os.path.expanduser('~')
_AY_FONTDIR = os.path.join(ROOT, 'fonts')


def _ay_pick(*paths):
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.exists(p): return p
    return None


AY_FONT = {
    # Gilroy (headings, UI). Brand head font first, then the system copies.
    'h': _ay_pick(_FX_FONTS.get('bold', ''), '~/reels/fonts/Gilroy-Bold.ttf', '~/Library/Fonts/Gilroy-Bold.ttf', os.path.join(_AY_FONTDIR, 'Montserrat.ttf')),
    'hx': _ay_pick('~/Library/Fonts/Gilroy-ExtraBold.ttf', '~/Library/Fonts/Gilroy-Black.ttf', '~/reels/fonts/Gilroy-Bold.ttf', os.path.join(_AY_FONTDIR, 'Montserrat.ttf')),
    'hb': _ay_pick('~/Library/Fonts/Gilroy-Black.ttf', '~/Library/Fonts/Gilroy-Heavy.ttf', '~/reels/fonts/Gilroy-Bold.ttf', os.path.join(_AY_FONTDIR, 'Montserrat.ttf')),
    'hm': _ay_pick('~/Library/Fonts/Gilroy-SemiBold.ttf', '~/Library/Fonts/Gilroy-Medium.ttf', '~/reels/fonts/Gilroy-Bold.ttf', os.path.join(_AY_FONTDIR, 'Inter.ttf')),
    'r': _ay_pick('~/Library/Fonts/Gilroy-Regular.ttf', '~/reels/.cache/fxfonts/Gilroy-Regular.ttf', os.path.join(_AY_FONTDIR, 'Inter.ttf')),
    'l': _ay_pick('~/Library/Fonts/Gilroy-Light.ttf', '~/Library/Fonts/Gilroy-Regular.ttf', os.path.join(_AY_FONTDIR, 'Inter.ttf')),
    # Nyght Serif italic: the pink accent words
    'i': _ay_pick(_FX_FONTS.get('serif', ''), '~/reels/fonts/NyghtSerif-RegularItalic.otf', os.path.join(_AY_FONTDIR, 'PlayfairDisplay-Italic.ttf')),
    'il': _ay_pick('~/reels/fonts/NyghtSerif-LightItalic.otf', '~/reels/fonts/NyghtSerif-RegularItalic.otf', os.path.join(_AY_FONTDIR, 'PlayfairDisplay-Italic.ttf')),
    # upright serif with Cyrillic (banknote numbers, newspaper, big words)
    's': os.path.join(_AY_FONTDIR, 'PlayfairDisplay.ttf'),
    'si': os.path.join(_AY_FONTDIR, 'PlayfairDisplay-Italic.ttf'),
    # IBM Plex Mono: labels, numbers, code
    'm': _ay_pick(os.path.join(_AY_FONTDIR, 'IBMPlexMono-Regular.ttf'), os.path.join(_AY_FONTDIR, 'SpaceMono-Bold.ttf')),
    'mm': _ay_pick(os.path.join(_AY_FONTDIR, 'IBMPlexMono-Medium.ttf'), os.path.join(_AY_FONTDIR, 'IBMPlexMono-Regular.ttf')),
    'mb': _ay_pick(os.path.join(_AY_FONTDIR, 'IBMPlexMono-SemiBold.ttf'), os.path.join(_AY_FONTDIR, 'IBMPlexMono-Medium.ttf')),
}
# Playfair is a variable font: weight axis
AY_WGHT = {'s': 500, 'si': 400}

# Palette (default greens; lime / pink come from the brand: FX_COLORS)
AY = dict(
    c0=(4, 8, 4), c1=(7, 12, 7), c2=(11, 18, 10), c3=(16, 24, 13), olive=(40, 48, 28), green=(46, 125, 62),
    lime=(210, 219, 118), lime_hi=(227, 234, 156), pink=(255, 195, 204), pink_dk=(196, 84, 111),
    cream=(241, 240, 231), blush=(251, 228, 231), ink=(20, 26, 14), tx=(243, 244, 236), white=(255, 255, 255),
)
_c = _FX_COLORS
if 'YELLOW' in _c: AY['lime'] = _hx(_c['YELLOW'])
if 'PEACH' in _c: AY['pink'] = _hx(_c['PEACH'])

_ay_fc = {}


def ay_font(kind, size):
    """Brand font by role: h hx hb hm r l (Gilroy), i il (Nyght italic), s si (Playfair), m mm mb (Plex Mono)."""
    k = (kind, int(size))
    if k not in _ay_fc:
        f = ImageFont.truetype(AY_FONT[kind], max(6, int(size)))
        if kind in AY_WGHT:
            try: f.set_variation_by_axes([AY_WGHT[kind]])
            except Exception: pass
        _ay_fc[k] = f
    return _ay_fc[k]


def ay_text(s, size, kind='h', fill=AY['tx'], track=0.0, alpha=255, stroke=0, stroke_fill=None):
    """Tight RGBA image of a line of text. track = extra letter spacing in px."""
    f = ay_font(kind, size)
    if not track:
        bb = f.getbbox(s, stroke_width=stroke); pad = int(size * 0.12) + 2 + stroke
        im = Image.new('RGBA', (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((pad - bb[0], pad - bb[1]), s, font=f, fill=tuple(fill) + (alpha,), stroke_width=stroke,
                                stroke_fill=tuple(stroke_fill or fill) + (alpha,))
        return im
    w = sum(f.getlength(ch) for ch in s) + track * max(0, len(s) - 1)
    asc, desc = f.getmetrics(); pad = int(size * 0.12) + 2
    im = Image.new('RGBA', (int(w) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = pad
    for ch in s:
        d.text((x, pad), ch, font=f, fill=tuple(fill) + (alpha,)); x += f.getlength(ch) + track
    return im


def ay_fit(s, max_w, kind='h', start=200, **kw):
    """Largest size (<= start) at which the line fits max_w."""
    size = int(start)
    while size > 10 and ay_font(kind, size).getlength(s) + kw.get('track', 0) * len(s) > max_w: size = int(size * 0.94)
    return size


def ay_ss(w, h, k=2):
    """Supersampled RGBA canvas: draw at k x, then .resize back with ay_down for clean anti-aliased lines."""
    return Image.new('RGBA', (int(w * k), int(h * k)), (0, 0, 0, 0))


def ay_down(im, w, h): return im.resize((int(w), int(h)), Image.LANCZOS)


def ay_np(im): return np.asarray(im.convert('RGBA'), np.float32) / 255.0


def ay_pil(a):
    """float RGB(A) array 0..1 -> PIL image."""
    a = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(a, 'RGBA' if a.shape[2] == 4 else 'RGB')


def ay_fill(c, color, alpha=1.0, mask=None):
    """Fill the frame with a flat colour (optionally only where mask (H,W) is 1)."""
    col = np.float32(color) / 255
    a = alpha if mask is None else (mask * alpha)[..., None]
    c.img = c.img * (1 - a) + col * a


def ay_person(c, src=None):
    """The person (cut-out) over the current c.img. src = the original frame (float RGB); keep it before you paint the background."""
    if src is None: return
    m = c.m[..., None]
    c.img = c.img * (1 - m) + src * m


def ay_paper(W, H, color=AY['cream'], grain=0.025, seed=3, lines=None, line_col=(0, 0, 0), line_a=0.08):
    """Paper texture (float RGB): flat colour, soft grain, optional ruled lines every `lines` px."""
    rnd = np.random.default_rng(seed)
    n = cv2.resize(rnd.normal(0, 1, (H // 4, W // 4)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    n += rnd.normal(0, 0.6, (H, W)).astype(np.float32)
    base = np.ones((H, W, 3), np.float32) * (np.float32(color) / 255)
    base += n[..., None] * grain
    if lines:
        yy = np.arange(H)[:, None]
        ln = (((yy % int(lines)) < max(1, int(lines * 0.03)))).astype(np.float32)
        base = base * (1 - ln[..., None] * line_a) + np.float32(line_col) / 255 * ln[..., None] * line_a
    return np.clip(base, 0, 1)


def ay_history(c, e, n=24, step=1):
    """Keep the last n frames (and masks / face) of this effect in e.state['hist'] (oldest first). Works in video renders;
    in --still checks only the frames that are rendered get stored, so effects must still look right with a short history."""
    h = e.state.setdefault('hist', [])
    if not h or c.t - h[-1]['t'] >= (step - 0.5) / c.fps:
        h.append({'t': c.t, 'img': c.img.copy(), 'm': c.m.copy(), 'f': (c.fx, c.fy, c.fw)})
        if len(h) > n: del h[0]
    return h


def ay_plate(c, e, key='plate'):
    """A clean background plate (person removed) for this effect: the first frame's background, inpainted where the
    person was, updated with any background the later frames uncover. Float RGB (H, W, 3)."""
    st = e.state
    if key not in st:
        q = 4; sm = cv2.resize(c.img, (c.W // q, c.H // q), interpolation=cv2.INTER_AREA)
        mm = cv2.resize(c.m, (c.W // q, c.H // q), interpolation=cv2.INTER_AREA)
        hole = (cv2.dilate((mm > 0.15).astype(np.uint8), np.ones((9, 9), np.uint8)) * 255).astype(np.uint8)
        fill = cv2.inpaint((sm * 255).astype(np.uint8), hole, 12, cv2.INPAINT_TELEA).astype(np.float32) / 255
        fill = cv2.GaussianBlur(fill, (0, 0), 3)
        fill = cv2.resize(fill, (c.W, c.H), interpolation=cv2.INTER_CUBIC)
        hm = cv2.GaussianBlur(cv2.resize(hole.astype(np.float32) / 255, (c.W, c.H)), (0, 0), 6)[..., None]
        st[key] = c.img * (1 - hm) + fill * hm
        st[key + '_seen'] = 1 - hm[..., 0]
    else:
        bgm = np.clip(1 - c.m * 1.6, 0, 1)
        new = bgm * (1 - st[key + '_seen'])
        if new.max() > 0.05:
            st[key] = st[key] * (1 - new[..., None]) + c.img * new[..., None]
            st[key + '_seen'] = np.maximum(st[key + '_seen'], bgm)
    return st[key]


def ay_warp(c, src, M, size=None, border=cv2.BORDER_CONSTANT):
    """cv2.warpPerspective with a 3x3 matrix, float RGB(A)."""
    W, H = size or (c.W, c.H)
    return cv2.warpPerspective(src, np.float32(M), (int(W), int(H)), flags=cv2.INTER_LINEAR, borderMode=border)


def ay_words(e, key='text', sep='|', default=''):
    v = e.o.get(key)
    if v is None or v == '': v = default
    if isinstance(v, list): return [str(x) for x in v]
    v = str(v)
    return [x.strip() for x in (v.split(sep) if sep in v else [v]) if x.strip()]


def ay_handle(e): return e.o.get('handle') or '@your.handle'


def ay_name(e): return e.o.get('name') or 'Твоє Імʼя'


# the groups of effects
for _ay_f in sorted(_ay_glob.glob(os.path.join(os.path.dirname(os.path.abspath(_rf if '_rf' in globals() else __file__)), 'ay', '*.py'))):
    try:
        exec(compile(open(_ay_f, encoding='utf-8').read(), _ay_f, 'exec'))
    except Exception as _ay_err:   # one broken group must not take the whole engine down
        import traceback as _ay_tb
        print(f'ay_fx: skipped {os.path.basename(_ay_f)}: {_ay_err!r}', file=sys.stderr)
        _ay_tb.print_exc(limit=2)
