"""9 эффектов для говорящей головы (вертикальное видео 1080×1920).

    python fx9.py plan.json                 рендер: исходник + эффекты → output из плана (звук исходника сохраняется)
    python fx9.py plan.json --sheet         контакт-лист: по 3 кадра каждого эффекта → <output>_sheet.jpg (проверить до рендера)
    python fx9.py plan.json --only dust     рендерить только эти эффекты (через запятую), остальное как есть
    python fx9.py --list                    список эффектов и их настроек

plan.json:
    {"input": "talk.mp4", "output": "talk_fx.mp4",
     "effects": [{"fx": "dust", "t0": 3.4, "t1": 4.9},
                 {"fx": "droste", "t0": 8.0, "t1": 9.2, "to": [1040, 600]}]}

Время t0/t1 — секунды ИСХОДНИКА. Исходник любого размера приводится к 1080×1920, 30 к/с (обрезка по центру).
Зависимости: pip install numpy opencv-python-headless pillow "rembg[cpu]"   + ffmpeg в PATH.
Необязательно (лучше LiDAR): pip install torch transformers — тогда глубина считается нейросетью Depth Anything V2.
"""
import json
import math
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
VF = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=rgb24'

# ─────────────────────────────── плавности ───────────────────────────────


def cl(x, a=0., b=1.):
    return max(a, min(b, x))


def eo(x):                       # быстрый старт, мягкая посадка
    x = cl(x); return 1 - (1 - x) ** 3


def eio(x):                      # мягко с двух сторон
    x = cl(x); return x * x * (3 - 2 * x)


def env(u, d, a=.3, b=.35):      # 0→1 за a с, держит, 1→0 за последние b с
    return eo(u / a) * eio((d - u) / b)


def spring(t, w=14., z=.55):     # пружина с перелётом
    if t <= 0:
        return 0.
    return 1 - math.exp(-z * w * t) * math.cos(w * math.sqrt(1 - z * z) * t)

# ─────────────────────────────── шрифт (Mac / Windows / Linux) ───────────────────────────────


FONT_FILES = ['/System/Library/Fonts/HelveticaNeue.ttc', '/System/Library/Fonts/Supplemental/Arial.ttf', '/Library/Fonts/Arial.ttf',
              'C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/segoeui.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
_fonts = {}


FONT_OVERRIDE = {}          # plan.json "font": "path.ttf" (the brand font)


def font(size):
    if size not in _fonts:
        p = FONT_OVERRIDE.get('font') or next((f for f in FONT_FILES if os.path.exists(f)), None)
        _fonts[size] = ImageFont.truetype(p, size) if p else ImageFont.load_default(size=size)
    return _fonts[size]

# ─────────────────────────────── человек: маска (rembg) ───────────────────────────────


class Person:
    """маска человека rembg на 640 px, сглажена по времени (без «призраков» фона)"""

    def __init__(self, model='u2net_human_seg', work=640):
        self.model, self.work, self.session = model, work, None
        self.prev, self.prev_i = None, -10
        self.cache = {}

    def raw(self, rgb):
        if self.session is None:
            from rembg import new_session
            self.session = new_session(self.model)
        from rembg import remove
        s = self.work / max(W, H)
        small = Image.fromarray(rgb).resize((int(W * s), int(H * s)), Image.BILINEAR)
        m = np.asarray(remove(small, session=self.session, only_mask=True), np.float32) / 255.
        m = np.clip((m - .35) / .3, 0, 1)
        return m * m * (3 - 2 * m)

    def mask(self, rgb, i):
        if i in self.cache:
            return self.cache[i]
        m = self.raw(rgb)
        if self.prev is not None and i - self.prev_i == 1:
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
            m = np.minimum(m, cv2.dilate(self.prev, k))
            m = .3 * np.minimum(self.prev, cv2.dilate(m, np.ones((5, 5), np.uint8))) + .7 * m
        self.prev, self.prev_i = m, i
        out = cv2.GaussianBlur(np.clip(cv2.resize(m, (W, H), interpolation=cv2.INTER_CUBIC), 0, 1), (0, 0), 1.4)
        self.cache = {i: out}
        return out


def face_c(m):
    """центр лица по маске: середина головы чуть ниже макушки"""
    rows = np.where(m.max(1) > .5)[0]
    if not len(rows):
        return W / 2, H * .45
    top = int(rows[0])
    xs = np.where(m[min(top + 140, H - 1)] > .5)[0]
    return (float(xs.mean()) if len(xs) else W / 2), float(top + 150)


def head_top(m):
    rows = np.where(m.max(1) > .5)[0]
    return int(rows[0]) if len(rows) else int(H * .3)

# ─────────────────────────────── чистый фон без человека ───────────────────────────────


class Plate:
    """фон без человека: медиана кадров по пикселям, где человека нет (камера стоит); дыры — inpaint.
    Нужен эффектам «пыль» и «стоп-кадр», считается один раз и кешируется рядом с output."""

    def __init__(self, src, out, person):
        self.src, self.path, self.person, self.img = src, os.path.splitext(out)[0] + '_plate.png', person, None

    def get(self):
        if self.img is not None:
            return self.img
        if os.path.exists(self.path):
            self.img = np.asarray(Image.open(self.path).convert('RGB')).astype(np.float32)
            return self.img
        print('[fx9] считаю чистый фон (один раз)…', flush=True)
        dur = probe_dur(self.src)
        n = int(min(24, max(8, dur / .8)))
        hw, hh = W // 2, H // 2
        stack = []
        for k in range(n):
            fr = grab(self.src, dur * (k + .5) / n)
            if fr is None:
                continue
            m = self.person.raw(fr)
            m = cv2.dilate(cv2.resize(m, (hw, hh)), np.ones((21, 21), np.uint8))
            small = cv2.resize(fr, (hw, hh), interpolation=cv2.INTER_AREA).astype(np.float32)
            small[m > .05] = np.nan
            stack.append(small)
        med = np.nanmedian(np.stack(stack), axis=0)
        hole = np.isnan(med[..., 0])
        med = np.nan_to_num(med).astype(np.uint8)
        fill = cv2.inpaint(med, hole.astype(np.uint8) * 255, 9, cv2.INPAINT_TELEA)
        fill = cv2.GaussianBlur(fill, (0, 0), 4)
        med[hole] = fill[hole]
        img = cv2.resize(med, (W, H), interpolation=cv2.INTER_CUBIC)
        Image.fromarray(img).save(self.path)
        self.img = img.astype(np.float32)
        return self.img


def behind(f, m, plate, grow=21):
    """кадр, где человек заменён фоном: живой фон там, где его видно, чистый фон — только под человеком"""
    md = cv2.GaussianBlur(cv2.dilate(m, np.ones((grow, grow), np.uint8)), (0, 0), 6)[..., None]
    return f * (1 - md) + plate * md

# ─────────────────────────────── глубина для LiDAR ───────────────────────────────


_DEPTH = {}


def depth(rgb, m, size):
    """0..1, 1 = близко. Depth Anything V2 (если стоят torch + transformers), иначе по силуэту и высоте кадра"""
    if 'pipe' not in _DEPTH:
        try:
            from transformers import pipeline
            _DEPTH['pipe'] = pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Small-hf')
        except Exception:
            _DEPTH['pipe'] = None
            print('[fx9] LiDAR: нет transformers — глубина по силуэту (pip install torch transformers — будет объёмнее)')
    if _DEPTH['pipe'] is not None:
        d = np.asarray(_DEPTH['pipe'](Image.fromarray(rgb).resize((W // 2, H // 2)))['depth'], np.float32)
        lo, hi = np.percentile(d, 1), np.percentile(d, 99.5)
        d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
        return cv2.resize(d, size, interpolation=cv2.INTER_CUBIC)
    # без нейросети: фон — ровная дальняя плоскость (чуть ближе к низу кадра), человек выступает вперёд объёмом
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None].repeat(W, 1)
    body = cv2.GaussianBlur(m, (0, 0), 18)
    d = .12 + .12 * yy + .62 * body + .1 * cv2.GaussianBlur(body, (0, 0), 60)
    return cv2.resize(np.clip(d, 0, 1), size, interpolation=cv2.INTER_AREA)


def remap_scale(img, s, cx, cy):
    M = np.float32([[s, 0, cx - s * cx], [0, s, cy - s * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ═══════════════════════════════ 9 эффектов: fn(f, m, u, d, o, st, ctx) ═══════════════════════════════
# f — кадр float32, m — маска человека 0..1, u — секунды от начала эффекта, d — длительность окна,
# o — настройки из plan.json, st — состояние эффекта между кадрами, ctx — фон, буфер прошлых кадров.


def fx_dust(f, m, u, d, o, st, ctx):
    """человек рассыпается тёплой пылью (ветер вправо-вверх) и собирается обратно"""
    bg = behind(f, m, ctx['plate']())
    if 'th' not in st:
        rng = np.random.default_rng(3)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        n = cv2.resize(rng.random((H // 24, W // 24)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
        th = .55 * n + .15 * (xx / W) + .25 * (1 - xx / W)
        st['th'] = (th - th.min()) / (th.max() - th.min())
        st['jit'] = rng.random((H, W)).astype(np.float32)
    a1, a2 = d * .55, d * .35
    p = (eio(u / a1) if u < d - a2 else eio((d - u) / a2)) * 1.15
    th, jit = st['th'], st['jit']
    gone = np.clip((p - th) / .12, 0, 1)
    e = eio(min(u, d - u) / .4)
    soft = cv2.GaussianBlur(bg, (0, 0), 9)
    bgu = bg * (1 - e) + soft * e                                  # фон в лёгком расфокусе на время эффекта
    mg = (m * gone)[..., None]
    base = f * (1 - mg) + bgu * mg
    base = base * (1 - (1 - m[..., None]) * e) + bgu * (1 - m[..., None]) * e
    ys, xs = np.nonzero((m[::2, ::2] > .5) & (gone[::2, ::2] > 0))
    ys, xs = ys * 2, xs * 2
    if len(xs):
        j = jit[ys, xs]
        age = (p - th[ys, xs]).clip(0) * d
        dx = (420 + 520 * j) * age ** 1.3 + 40 * np.sin(ys * .02 + j * 6) * age
        dy = -(160 + 260 * (1 - j)) * age ** 1.2 + 30 * np.cos(xs * .03 + j * 5) * age
        nx = (xs + dx).astype(np.int32); ny = (ys + dy).astype(np.int32)
        ok = (nx >= 0) & (nx < W - 2) & (ny >= 0) & (ny < H - 2)
        ag = age[ok].clip(0, 1)
        warm = np.array(o.get('color', [255, 214, 160]), np.float32)
        col = (f[ys[ok], xs[ok]] * .35 + warm * .65) * (1 + .25 * (1 - ag[:, None]))
        al = (1 - age[ok] / 1.1).clip(0, 1) * (.55 + .45 * j[ok])
        nx, ny = nx[ok], ny[ok]
        layer = np.zeros((H, W, 3), np.float32); wa = np.zeros((H, W), np.float32)
        for oy in (0, 1):
            for ox in (0, 1):
                np.add.at(layer, (ny + oy, nx + ox), col * al[:, None])
                np.add.at(wa, (ny + oy, nx + ox), al)
        A = np.clip(wa, 0, 1)[..., None]
        base = base * (1 - A) + layer / np.maximum(wa, 1e-3)[..., None] * A
    return base


def fx_lidar(f, m, u, d, o, st, ctx):
    """кадр становится облаком точек по глубине и поворачивается в 3D, по нему бежит линия сканера"""
    k = 5
    fr = np.clip(f, 0, 255).astype(np.uint8)
    dd = depth(fr, m, (W // k, H // k))
    if 'dc' in st:
        dd = .5 * st['dc'] + .5 * dd
    st['dc'] = dd
    small = cv2.resize(fr, (W // k, H // k), interpolation=cv2.INTER_AREA).astype(np.float32)
    ms = cv2.resize(m, (W // k, H // k))
    yy, xx = np.mgrid[0:H // k, 0:W // k].astype(np.float32)
    X = xx * k - W / 2; Y = yy * k - H / 2
    Z = (1 - dd) * 2200 + 900 - ms * 120
    e = env(u, d, .45, .45)
    h = d * .5
    ang = math.radians(o.get('angle', 38)) * (eio(u / h) if u < h else eio((d - u) / h))
    ca, sa = math.cos(ang), math.sin(ang)
    piv = 1500.
    Zc = Z - piv
    X2 = X * ca + Zc * sa
    Z2 = -X * sa + Zc * ca + piv
    pz = Z2.clip(200) / Z.clip(1)                                  # при угле 0 точки ложатся ровно на кадр
    px = X2 / pz + W / 2
    py = (Y - 140 * math.sin(ang)) / pz + H / 2
    canvas = np.empty((H, W, 3), np.float32); canvas[:] = (10, 12, 16)
    order = np.argsort(-Z2.ravel())
    pxr, pyr = px.ravel()[order].astype(np.int32), py.ravel()[order].astype(np.int32)
    col = np.clip(small.reshape(-1, 3)[order] * (1.7 + .8 * dd.ravel()[order][:, None]) + 35, 0, 255)
    ok = (pxr > 1) & (pxr < W - 3) & (pyr > 1) & (pyr < H - 3)
    pxr, pyr, col = pxr[ok], pyr[ok], col[ok]
    for oy in (0, 1, 2):
        for ox in (0, 1, 2):
            canvas[pyr + oy, pxr + ox] = col
    canvas = canvas + cv2.GaussianBlur(canvas, (0, 0), 6) * .35
    sy = int((u / d) * 1.6 * H) % (H + 200) - 100
    band = np.exp(-((np.arange(H) - sy) / 18.) ** 2)[:, None, None]
    canvas = canvas + band * np.array([60, 120, 255], np.float32) * .35 * e
    mix = eio(u / .32) * eio((d - u) / .32)
    return f * (1 - mix) + canvas * mix


def fx_clones(f, m, u, d, o, st, ctx):
    """из-за спины на пружине выезжают 4 копии с отставанием по времени и уходят обратно"""
    out = f.copy()
    cx, cy = face_c(m)
    k = spring(u - .02) * eio((d - u) / .38)
    for side, lag, sc, ofs in ((-1, 6, .88, 300), (1, 12, .88, 300), (-1, 12, .74, 520), (1, 6, .74, 520)):
        fp, mp = ctx['past'](lag)
        kk = k if sc > .8 else spring(u - .12) * eio((d - u) / .38)
        if kk <= .01:
            continue
        s = 1 - (1 - sc) * kk
        M = np.float32([[s, 0, cx - s * cx + side * ofs * kk], [0, s, H - s * H]])
        F = cv2.warpAffine(fp, M, (W, H), borderMode=cv2.BORDER_REFLECT)
        A = cv2.warpAffine(mp, M, (W, H)) * (1 - m) * (.92 if sc > .8 else .8)
        F = F * .9 + np.array([200, 215, 235], np.float32) * .1         # копия чуть прохладнее, как отражение
        out = out * (1 - cv2.GaussianBlur(A, (0, 0), 30)[..., None] * .25)
        out = out * (1 - A[..., None]) + F * A[..., None]
    return out


def fx_droste(f, m, u, d, o, st, ctx):
    """кадр в рамке сбоку от головы, внутри снова кадр…; камера влетает внутрь и бесшовно возвращается"""
    if 'P' not in st:
        cx, _ = face_c(m)
        st['P'] = np.float32(o.get('to') or [min(W - 40, cx + 440), max(420, head_top(m) - 100)])
        r = 70
        mk = np.zeros((H, W), np.float32)
        cv2.rectangle(mk, (r, 0), (W - r, H), 1, -1); cv2.rectangle(mk, (0, r), (W, H - r), 1, -1)
        for (px, py) in ((r, r), (W - r, r), (r, H - r), (W - r, H - r)):
            cv2.circle(mk, (px, py), r, 1, -1)
        st['card'] = cv2.GaussianBlur(mk, (0, 0), 1.2)
        st['rim'] = cv2.GaussianBlur(cv2.dilate(mk, np.ones((49, 49), np.uint8)), (0, 0), 1.2)
    P, z = st['P'], o.get('scale', .3)
    t_in, t_out = .4, .38
    if u < t_in:
        a, p = spring(u, 12, .6), 0.
    elif u < d - t_out:
        a, p = 1., eio((u - t_in) / (d - t_out - t_in))
    else:
        a, p = eio((d - u) / t_out), 0.                     # после влёта кадр самоподобен: тот же вид при масштабе 1
    Z, ze = (1 / z) ** p, z * max(a, 1e-3)
    out, n = None, 0
    while True:
        sc = (ze ** n) * Z
        if sc < .015 or n > 12:
            break
        M = np.float32([[sc, 0, P[0] - sc * P[0]], [0, sc, P[1] - sc * P[1]]])
        img = cv2.warpAffine(f, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        if n == 0:
            out = img
        else:
            card = cv2.warpAffine(st['card'], M, (W, H)); rim = cv2.warpAffine(st['rim'], M, (W, H))
            shs = cv2.GaussianBlur(np.roll(cv2.resize(rim, (W // 4, H // 4), interpolation=cv2.INTER_AREA), max(1, int(6 * sc)), 0),
                                   (0, 0), 3 + 10 * sc)
            out = out * (1 - cv2.resize(shs, (W, H))[..., None] * .5)
            out = out * (1 - rim[..., None]) + 252 * rim[..., None]
            out = out * (1 - card[..., None]) + img * card[..., None]
        n += 1
    return out


def fx_blueprint(f, m, u, d, o, st, ctx):
    """линия сканера превращает кадр в синий чертёж: сетка, контуры, размерные линии у головы"""
    fr = np.clip(f, 0, 255).astype(np.uint8)
    g = cv2.bilateralFilter(cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY), 9, 40, 9)
    ed = cv2.Canny(g, 40, 110).astype(np.float32) / 255
    pe = cv2.dilate(cv2.Canny((m * 255).astype(np.uint8), 60, 160).astype(np.float32) / 255, np.ones((5, 5), np.uint8))
    ed = np.clip(cv2.GaussianBlur(ed, (0, 0), .7) * 1.4 + cv2.GaussianBlur(pe, (0, 0), 1) * 1.2, 0, 1)
    if 'grid' not in st:
        gr = np.zeros((H, W), np.float32)
        gr[::60, :] = .22; gr[:, ::60] = .22
        gr[::12, :] = np.maximum(gr[::12, :], .07); gr[:, ::12] = np.maximum(gr[:, ::12], .07)
        st['grid'] = gr
    blue = np.array(o.get('color', [28, 78, 196]), np.float32)
    bp = blue * (1 - st['grid'][..., None]) + 235 * st['grid'][..., None]
    bp = bp * (1 - .25 * m[..., None]) + (blue + 10) * .25 * m[..., None]
    bp = bp * (1 - ed[..., None]) + np.array([245, 248, 255], np.float32) * ed[..., None]
    img = Image.fromarray(bp.clip(0, 255).astype(np.uint8)); dr = ImageDraw.Draw(img)
    cx, cy = face_c(m)
    top, hw, c = head_top(m), 170, (245, 248, 255)
    dr.line([(cx - hw, top - 40), (cx + hw, top - 40)], fill=c, width=3)
    for x in (cx - hw, cx + hw):
        dr.line([(x, top - 58), (x, top - 22)], fill=c, width=3)
    dr.text((cx, top - 74), o.get('width_label', '340 мм'), font=font(34), fill=c, anchor='ms')
    dr.line([(cx + hw + 60, top), (cx + hw + 60, top + 320)], fill=c, width=3)
    for y in (top, top + 320):
        dr.line([(cx + hw + 42, y), (cx + hw + 78, y)], fill=c, width=3)
    dr.text((cx + hw + 92, top + 172), o.get('height_label', 'H 230'), font=font(30), fill=c, anchor='lm')
    dr.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=c, width=3)
    dr.line([(cx - 30, cy), (cx + 30, cy)], fill=c, width=2); dr.line([(cx, cy - 30), (cx, cy + 30)], fill=c, width=2)
    if o.get('stamp', 'АРКУШ 01 · М 1:10'):
        dr.text((120, 1600), o.get('stamp', 'АРКУШ 01 · М 1:10'), font=font(30), fill=c)
    bp = np.asarray(img).astype(np.float32)
    a, b = d * .42, d * .32
    ly = (eio(u / a) if u < d - b else eio((d - u) / b)) * (H + 40) - 20
    yy = np.arange(H, dtype=np.float32)[:, None]
    above = np.clip((ly - yy) / 6, 0, 1)
    out = f * (1 - above[..., None]) + bp * above[..., None]
    return out + np.exp(-((yy - ly) / 10) ** 2)[..., None] * np.array([140, 190, 255], np.float32) * .9


def fx_freeze(f, m, u, d, o, st, ctx):
    """время замирает: человек вырезан с белой кромкой, фон обесцвечен и размыт, камера проезжает с параллаксом"""
    if 'f0' not in st:
        st['f0'], st['m0'], st['c'] = f.copy(), m.copy(), face_c(m)
        st['bg'] = behind(f, m, ctx['plate']())
    f0, m0, bg = st['f0'], st['m0'], st['bg']
    cx, cy = st['c']
    e, k = env(u, d, .5, .3), eio(u / d)
    sb, sp = 1 + .05 * e, 1 + .16 * e
    dxb, dxp = -40 * e * (k - .5) * 2, 70 * e * (k - .5) * 2
    gray = bg.mean(2, keepdims=True)
    bgs = cv2.GaussianBlur((bg * (1 - .55 * e) + gray * .55 * e) * (1 - .12 * e) + 255 * .12 * e, (0, 0), 1 + 7 * e)
    Mb = np.float32([[sb, 0, cx - sb * cx + dxb], [0, sb, cy - sb * cy]])
    Mp = np.float32([[sp, 0, cx - sp * cx + dxp], [0, sp, cy - sp * cy + 30 * e]])
    B = cv2.warpAffine(bgs, Mb, (W, H), borderMode=cv2.BORDER_REFLECT)
    P = cv2.warpAffine(f0, Mp, (W, H), borderMode=cv2.BORDER_REFLECT)
    A = cv2.warpAffine(m0, Mp, (W, H))
    B = B * (1 - cv2.GaussianBlur(A, (0, 0), 22)[..., None] * .35 * e)
    out = B * (1 - A[..., None]) + P * A[..., None]
    edge = np.clip(cv2.dilate(A, np.ones((9, 9), np.uint8)) - A, 0, 1) * e
    out = out * (1 - edge[..., None]) + 255 * edge[..., None]
    back = eio((u - (d - .3)) / .3)
    return out * (1 - back) + f * back


def fx_circle(f, m, u, d, o, st, ctx):
    """кадр на пружине сжимается в круглую карточку на светлом фоне (тень, свечение цветом видео) и возвращается"""
    if 'c' not in st:
        st['c'] = face_c(m)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        st['xx'], st['yy'] = xx, yy
    cx, cy = st['c']; cy += 40
    b = .38
    k = spring(u, 13, .62) if u < d - b else eio((d - u) / b)
    R = 1250 + (o.get('radius', 360) - 1250) * k
    img = remap_scale(f, 1 - .3 * k, cx, cy)
    dist = np.sqrt((st['xx'] - cx) ** 2 + (st['yy'] - cy) ** 2)
    inside = np.clip(R - dist + .8, 0, 1.6) / 1.6
    ring = np.clip(1 - np.abs(dist - R - 6) / 6, 0, 1) * min(1, k * 3)
    glow_col = f[max(0, int(cy) - 200):int(cy) + 200, max(0, int(cx) - 200):int(cx) + 200].reshape(-1, 3).mean(0)
    halo = np.exp(-np.clip(dist - R, 0, None) / 90) * (dist > R) * .55 * k
    shadow = np.exp(-np.clip(dist - R - 10, 0, None) / 40) * (dist > R) * .25 * k
    bg = np.empty((H, W, 3), np.float32); bg[:] = o.get('bg', [244, 241, 236])
    bg = (bg * (1 - halo[..., None]) + glow_col * halo[..., None]) * (1 - shadow[..., None])
    out = bg * (1 - inside[..., None]) + img * inside[..., None]
    return out * (1 - ring[..., None]) + 255 * ring[..., None]


def fx_slice(f, m, u, d, o, st, ctx):
    """кадр режется на полосы, они разъезжаются в разные стороны со смазом и собираются («по полочкам»)"""
    n = int(o.get('bands', 7))
    out = np.empty_like(f); out[:] = o.get('bg', [246, 244, 240])
    hs = H / n
    for i in range(n):
        y0, y1 = int(i * hs), int((i + 1) * hs)
        k = eio((u - i * .045) / .38) * eio((d - u - (n - 1 - i) * .03) / .34)
        off = (1 if i % 2 else -1) * k * (180 + 40 * (i % 3))
        band = f[y0:y1]
        vel = abs(off - st.get(i, off)); st[i] = off
        if vel > 4:
            band = cv2.blur(band, (int(min(vel, 60)) | 1, 1))
        row = np.empty_like(band); row[:] = out[y0:y1]
        sh = int(round(off))
        xa, xb = max(0, sh), min(W, W + sh)
        row[:, xa:xb] = band[:, xa - sh:xb - sh]
        g = int(10 * k) // 2
        if g:
            row[:g] = out[y0:y0 + g]; row[-g:] = out[y1 - g:y1]
        out[y0:y1] = row
    return out


def fx_wave(f, m, u, d, o, st, ctx):
    """от лица расходится кольцо искажения с лёгкой хроматикой и микротолчком камеры"""
    if 'c' not in st:
        st['c'] = face_c(m)
        st['yy'], st['xx'] = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = st['c']
    dx, dy = st['xx'] - cx, st['yy'] - cy
    rr = np.sqrt(dx * dx + dy * dy) + 1e-3
    disp = np.zeros_like(rr)
    for delay, amp in ((0, o.get('amp', 34)), (.16, o.get('amp', 34) * .6)):
        t = u - delay
        if t <= 0:
            continue
        x = (rr - eo(t / .9) * 1900) / 70
        disp += amp * (1 - cl(t / .95)) ** 1.4 * np.sin(x * 2.2) * np.exp(-x * x)
    mx = (st['xx'] - dx / rr * disp).astype(np.float32)
    my = (st['yy'] - dy / rr * disp).astype(np.float32)
    out = cv2.remap(f, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    k = np.clip(np.abs(disp) / 30, 0, 1)
    r = cv2.remap(f[..., 0], mx + dx / rr * 4 * k, my + dy / rr * 4 * k, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out[..., 0] = out[..., 0] * (1 - k) + r * k
    out = out + (k * 30)[..., None]
    return remap_scale(out, 1 + .025 * math.sin(math.pi * cl(u / .35)), cx, cy)


FX = {'dust': fx_dust, 'lidar': fx_lidar, 'clones': fx_clones, 'droste': fx_droste, 'blueprint': fx_blueprint,
      'freeze': fx_freeze, 'circle': fx_circle, 'slice': fx_slice, 'wave': fx_wave}
HELP = {
    'dust': 'рассыпается в пыль и собирается. color: [255,214,160] (цвет пыли)',
    'lidar': 'облако точек по глубине, поворот в 3D, линия сканера. angle: 38 (градусы поворота)',
    'clones': '4 копии с отставанием по времени выезжают из-за спины',
    'droste': 'бесконечный кадр: рамки внутри рамок, влёт внутрь. to: [x, y] — куда уходят рамки (по умолчанию сбоку от головы), scale: 0.3',
    'blueprint': 'синий чертёж по линии сканера. width_label: "340 мм", height_label: "H 230", stamp: "ЛИСТ 01 · М 1:10" ("" — без штампа), color: [28,78,196]',
    'freeze': 'стоп-кадр 2.5D: человек вырезан с белой кромкой, фон размыт, проезд камеры',
    'circle': 'кадр сжимается в круглую карточку на светлом фоне. radius: 360, bg: [244,241,236]',
    'slice': 'полосы разъезжаются и собираются («по полочкам»). bands: 7, bg: [246,244,240]',
    'wave': 'ударная волна от лица. amp: 34 (сила искажения)',
}
NEED_MASK = set(FX) - {'slice'}

# ─────────────────────────────── рендер ───────────────────────────────


def probe_dur(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).strip())


def grab(path, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t):.3f}', '-i', path, '-frames:v', '1', '-vf', VF,
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3) if len(raw) == W * H * 3 else None


def prepare(plan, base):
    if plan.get('font'): FONT_OVERRIDE['font'] = plan['font']
    rel = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    plan['input'] = rel(plan['input'])
    plan['output'] = rel(plan.get('output', os.path.splitext(plan['input'])[0] + '_fx.mp4'))
    for e in plan['effects']:
        assert e['fx'] in FX, f"нет эффекта «{e['fx']}». Есть: {', '.join(FX)}"
        assert e['t1'] > e['t0'], f"{e['fx']}: t1 должно быть больше t0"
    plan['effects'].sort(key=lambda e: e['t0'])
    return plan


class Engine:
    def __init__(self, plan, only=None):
        self.plan, self.only = plan, only
        self.person = Person(plan.get('mask_model', 'u2net_human_seg'))
        self.plate_ = Plate(plan['input'], plan['output'], self.person)
        self.state = {}
        self.hist = []                                   # прошлые кадры (для клонов): (i, кадр)

    def active(self, t):
        return next((e for e in self.plan['effects'] if e['t0'] <= t < e['t1'] and (not self.only or e['fx'] in self.only)), None)

    def frame(self, fr, i):
        t = i / FPS
        self.hist.append((i, fr))
        if len(self.hist) > 14:
            self.hist.pop(0)
        e = self.active(t)
        if e is None:
            return fr
        f = fr.astype(np.float32)
        m = self.person.mask(fr, i) if e['fx'] in NEED_MASK else np.zeros((H, W), np.float32)
        st = self.state.setdefault(id(e), {})
        pm = {}

        def past(lag):
            j = max(0, len(self.hist) - 1 - lag)
            k, img = self.hist[j]
            if k not in pm:
                pm[k] = self.person.raw(img)
                pm[k] = cv2.GaussianBlur(cv2.resize(pm[k], (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), 1.4)
            return img.astype(np.float32), pm[k]
        ctx = dict(plate=self.plate_.get, past=past)
        out = FX[e['fx']](f, m, t - e['t0'], e['t1'] - e['t0'], e, st, ctx)
        return np.clip(out + .5, 0, 255).astype(np.uint8)


def render(plan, only=None):
    src, dst = plan['input'], plan['output']
    eng = Engine(plan, only)
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-vf', VF, '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-i', src, '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', dst],
                           stdin=subprocess.PIPE)
    n, sz, total = 0, W * H * 3, int(probe_dur(src) * FPS)
    while True:
        buf = dec.stdout.read(sz)
        if len(buf) < sz:
            break
        enc.stdin.write(eng.frame(np.frombuffer(buf, np.uint8).reshape(H, W, 3), n).tobytes())
        n += 1
        if n % 30 == 0:
            print(f'\r[fx9] {n}/{total} кадров', end='', flush=True)
    enc.stdin.close(); enc.wait(); dec.wait()
    print(f'\n[fx9] готово: {dst}')
    return dst


def sheet(plan, only=None):
    """по 3 кадра каждого эффекта — быстрый просмотр до полного рендера"""
    eng = Engine(plan, only)
    effects = [e for e in plan['effects'] if not only or e['fx'] in only]
    tw, th = 216, 384
    im = Image.new('RGB', (3 * tw + 32, len(effects) * (th + 40) + 8), (24, 24, 26))
    dr = ImageDraw.Draw(im)
    for r, e in enumerate(effects):
        d = e['t1'] - e['t0']
        for c, k in enumerate((.25, .5, .8)):
            i0 = int(round((e['t0']) * FPS))
            i = int(round((e['t0'] + d * k) * FPS))
            eng.state.pop(id(e), None); eng.hist.clear(); eng.person.prev = None
            for j in (i0, i):                                          # первый кадр окна — для стоп-кадра и состояния
                fr = grab(plan['input'], j / FPS)
                if fr is None:
                    continue
                out = eng.frame(fr, j)
            x, y = 8 + c * (tw + 8), 8 + r * (th + 40)
            im.paste(Image.fromarray(out).resize((tw, th), Image.LANCZOS), (x, y + 32))
            dr.text((x, y + 4), f"{e['fx']}  {i / FPS:.2f}s", fill=(255, 214, 90), font=font(20))
    p = os.path.splitext(plan['output'])[0] + '_sheet.jpg'
    im.save(p, quality=88)
    print(f'[fx9] контакт-лист: {p}')
    return p


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__); return
    if argv[0] == '--list':
        for k, v in HELP.items():
            print(f'  {k:10} {v}')
        return
    path = argv[0]
    plan = prepare(json.load(open(path, encoding='utf-8')), os.path.dirname(os.path.abspath(path)))
    only = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
    (sheet if '--sheet' in argv else render)(plan, only)


if __name__ == '__main__':
    main(sys.argv[1:])
