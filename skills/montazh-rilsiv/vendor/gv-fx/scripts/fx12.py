"""12 эффектов для говорящей головы (Reels 1080×1920) — скилл Алексея Гвоздарева (@alexgvozdarev).

    python fx12.py plan.json                 рендер: исходник + эффекты → output из плана (звук исходника сохраняется)
    python fx12.py plan.json --sheet         контакт-лист: по 3 кадра каждого эффекта → <output>_sheet.jpg (проверить до рендера)
    python fx12.py plan.json --only orbit    рендерить только эти эффекты (через запятую), остальное как есть
    python fx12.py --list                    список эффектов и их настроек

plan.json:
    {"input": "talk.mp4", "output": "talk_fx.mp4",
     "effects": [{"fx": "orbit", "t0": 2.8, "t1": 3.6},
                 {"fx": "ransom", "t0": 8.1, "t1": 9.2, "lines": ["БУКВЫ", "ВЫРЕЗКИ"]}]}

Время t0/t1 — секунды ИСХОДНИКА. Исходник любого размера приводится к 1080×1920, 30 к/с (обрезка по центру).
Зависимости: pip install numpy opencv-python pillow "rembg[cpu]"   + ffmpeg в PATH.
"""
import json
import math
import os
import random
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
YEL = (255, 214, 90)
CREAM = (243, 238, 229)
FIGMA = (24, 160, 251)
PURPLE = (151, 71, 255)

# ─────────────────────────────── плавности ───────────────────────────────


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def eo(x):                      # быстрый старт, мягкая посадка
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ei(x):                      # мягкий старт, разгон
    x = clamp(x)
    return x ** 3


def eio(x):                     # мягко с обеих сторон
    x = clamp(x)
    return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2


def spring(t, w=13.0, z=.62):
    """пружина: 0 → 1 с перелётом. w — жёсткость (быстрее), z — затухание (меньше = сильнее перелёт)"""
    if t <= 0:
        return 0.0
    wd = w * math.sqrt(1 - z * z)
    return 1 - math.exp(-z * w * t) * (math.cos(wd * t) + z * w / wd * math.sin(wd * t))


def back_env(u, d, rel=.3):
    """1 внутри эффекта и плавно → 0 за последние rel с: эффект сам отдаёт кадр обратно, без рывка"""
    return 1 - eio((u - (d - rel)) / rel)


def lerp(a, b, u):
    return a + (b - a) * u

# ─────────────────────────────── шрифты (Mac / Windows / Linux) ───────────────────────────────


FONT_DIRS = ['/System/Library/Fonts/Supplemental', '/System/Library/Fonts', '/Library/Fonts', os.path.expanduser('~/Library/Fonts'),
             'C:/Windows/Fonts', os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts'),
             '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype/msttcorefonts', '/usr/share/fonts/truetype/liberation']
FONT_NAMES = {      # все с кириллицей
    'display': ['Arial Black.ttf', 'ariblk.ttf', 'Impact.ttf', 'impact.ttf', 'Arial Bold.ttf', 'arialbd.ttf', 'DejaVuSans-Bold.ttf'],
    'medium': ['HelveticaNeue.ttc:1', 'Arial Bold.ttf', 'arialbd.ttf', 'segoeuib.ttf', 'DejaVuSans-Bold.ttf'],
    'regular': ['HelveticaNeue.ttc', 'Arial.ttf', 'arial.ttf', 'segoeui.ttf', 'DejaVuSans.ttf'],
    'italic': ['Georgia Italic.ttf', 'georgiai.ttf', 'Times New Roman Italic.ttf', 'timesi.ttf', 'DejaVuSerif-Italic.ttf'],
    'r1': ['Georgia Bold.ttf', 'georgiab.ttf', 'DejaVuSerif-Bold.ttf'],
    'r2': ['Impact.ttf', 'impact.ttf', 'Arial Black.ttf', 'ariblk.ttf', 'DejaVuSans-Bold.ttf'],
    'r3': ['Arial Black.ttf', 'ariblk.ttf', 'DejaVuSans-Bold.ttf'],
    'r4': ['Courier New Bold.ttf', 'courbd.ttf', 'DejaVuSansMono-Bold.ttf'],
    'r5': ['Times New Roman Bold.ttf', 'timesbd.ttf', 'DejaVuSerif-Bold.ttf'],
}
FONT_OVERRIDE = {}          # plan.json "fonts": {"display": "/путь/к/шрифту.ttf"}
_fonts = {}


def _find(kind):
    if kind in FONT_OVERRIDE:
        p, _, i = FONT_OVERRIDE[kind].partition(':')
        return p, int(i or 0)
    for name in FONT_NAMES[kind]:
        n, _, i = name.partition(':')
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return p, int(i or 0)
    return None, 0


def font(kind, size):
    key = (kind, int(size))
    if key not in _fonts:
        p, i = _find(kind)
        if p is None:
            print(f'[fx12] нет шрифта для «{kind}» — укажите "fonts": {{"{kind}": "путь.ttf"}} в plan.json', file=sys.stderr)
            _fonts[key] = ImageFont.load_default(size=int(size))
        else:
            _fonts[key] = ImageFont.truetype(p, max(4, int(size)), index=i)
    return _fonts[key]

# ─────────────────────────────── человек и лицо ───────────────────────────────


class Person:
    """маска человека (rembg) + рамка лица (OpenCV), сглажено по времени, считается только на кадрах с эффектами"""

    def __init__(self, model='u2net_human_seg', work=640):
        self.model, self.work = model, work
        self.session = None
        self.prev_m = self.prev_f = None
        self.prev_i = -10
        self.cascade = None                           # детектор лиц Haar есть только в OpenCV 4; в 5 — лицо по силуэту
        if hasattr(cv2, 'CascadeClassifier') and hasattr(cv2, 'data'):
            c = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
            self.cascade = None if c.empty() else c   # OpenCV 5 ships without the xml: face by silhouette then

    def mask(self, rgb, i):
        if self.session is None:
            from rembg import new_session
            self.session = new_session(self.model)
        from rembg import remove
        s = self.work / max(W, H)
        small = Image.fromarray(rgb).resize((int(W * s), int(H * s)), Image.BILINEAR)
        m = np.asarray(remove(small, session=self.session, only_mask=True), np.float32) / 255.
        m = np.clip((m - .35) / .3, 0, 1)             # чёткая маска: полупрозрачные пятна фона → 0 (иначе «призраки»)
        m = m * m * (3 - 2 * m)
        if self.prev_m is not None and i - self.prev_i == 1:
            # модель иногда на кадр «хватает» предмет за спиной (торшер, кресло): новая область маски может
            # появиться только рядом с прошлой (≈45 px за кадр), одиночные вспышки фона отсекаются
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
            m = np.minimum(m, cv2.dilate(self.prev_m, k))
            prev = np.minimum(self.prev_m, cv2.dilate(m, np.ones((5, 5), np.uint8)))   # ушедший кусок фона не тянется «призраком»
            m = .3 * prev + .7 * m                    # спокойные края между кадрами
        self.prev_m, self.prev_i = m, i
        m = cv2.resize(m, (W, H), interpolation=cv2.INTER_CUBIC)
        return cv2.GaussianBlur(np.clip(m, 0, 1), (0, 0), 1.4)

    def face(self, rgb, m=None):
        """(cx, cy, ширина лица) в пикселях кадра"""
        fs = ()
        if self.cascade is not None:
            g = cv2.cvtColor(cv2.resize(rgb, (360, 640)), cv2.COLOR_RGB2GRAY)
            fs = self.cascade.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
        if len(fs):
            x, y, w, h = max(fs, key=lambda r: r[2] * r[3])
            f = np.array([(x + w / 2) * 3, (y + h / 2) * 3, w * 3], np.float32)
        elif m is not None and (m > .5).any():         # лицо по силуэту: макушка + ширина головы над плечами
            f = self.head_from_mask(m)
        elif self.prev_f is not None:
            f = self.prev_f
        else:
            f = np.array([W / 2, H * .36, 320], np.float32)
        if self.prev_f is not None:
            f = .7 * self.prev_f + .3 * f                # без дрожи рамки
        self.prev_f = f
        return float(f[0]), float(f[1]), float(f[2])

    @staticmethod
    def head_from_mask(m):
        mk = m > .5
        rows = np.where(mk.any(1))[0]
        top = int(rows[0])
        span = range(top, min(H, top + 700), 4)
        wid = np.array([mk[y].sum() for y in span], np.float32)
        head = float(np.median(wid[20:65])) if len(wid) > 65 else float(wid.max())   # 80–260 px ниже макушки
        head = clamp(head, 140, 700)
        ys = [y for y in span if top + 60 <= y <= top + 1.2 * head]
        cxs = [np.where(mk[y])[0].mean() for y in ys if mk[y].any()]
        cx = float(np.median(cxs)) if cxs else W / 2
        return np.array([cx, top + .62 * 1.3 * head, .85 * head], np.float32)

# ─────────────────────────────── общие помощники ───────────────────────────────


def warp_scale(arr, s, cx, cy):
    m = np.float32([[s, 0, (1 - s) * cx], [0, s, (1 - s) * cy]])
    return cv2.warpAffine(arr, m, (arr.shape[1], arr.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def radial(arr, cx, cy, s0, s1, n=None):
    """зум-смаз: среднее копий кадра в масштабах s0..s1 вокруг (cx, cy), мягкий «гауссов затвор» без ступенек"""
    if n is None:
        n = int(clamp(abs(math.log(s1 / s0)) * 1100 / 1.5, 1, 40))
    if n <= 1:
        return warp_scale(arr, s0, cx, cy).astype(np.float32)
    acc = np.zeros(arr.shape, np.float32)
    ss = np.exp(np.linspace(math.log(s0), math.log(s1), n))
    w = np.exp(-.5 * (np.linspace(-.5, .5, n) / .3) ** 2)
    w /= w.sum()
    for s, k in zip(ss, w):
        acc += warp_scale(arr, s, cx, cy).astype(np.float32) * k
    return acc


def over(base, rgba, x=0, y=0):
    """наложить RGBA (numpy) на float-кадр в точке x, y"""
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(base.shape[1], x + w), min(base.shape[0], y + h)
    if x0 >= x1 or y0 >= y1:
        return base
    sub = rgba[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    a = sub[..., 3:4] / 255.
    base[y0:y1, x0:x1] = base[y0:y1, x0:x1] * (1 - a) + sub[..., :3] * a
    return base


def under_person(base, rgba, m):
    """слой ЗА человеком: рисуется на фоне, человек остаётся спереди"""
    a = rgba[..., 3:4].astype(np.float32) / 255. * (1 - m[..., None])
    return base * (1 - a) + rgba[..., :3].astype(np.float32) * a


def shadow_of(rgba, blur=14, off=(0, 10), a=.45):
    al = cv2.GaussianBlur(rgba[..., 3].astype(np.float32) * a, (0, 0), blur)
    sh = np.zeros_like(rgba)
    sh[..., 3] = np.clip(np.roll(np.roll(al, off[1], 0), off[0], 1), 0, 255)
    return sh


def soft_shadow(lay, r=16, a=.5, dy=6):
    al = lay.getchannel('A').filter(ImageFilter.GaussianBlur(r)).point(lambda v: int(v * a))
    sh = Image.new('RGBA', lay.size, (0, 0, 0, 0))
    sh.putalpha(al)
    out = Image.new('RGBA', lay.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, dy))
    out.alpha_composite(lay)
    return out


def rounded_mask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    return np.asarray(m, np.float32) / 255.

# ═══════════════════════════════ 12 ЭФФЕКТОВ ═══════════════════════════════
# каждый: fn(fr, ctx, u, d, o) → float-кадр.  fr — RGB uint8, u — секунды от начала эффекта, d — длительность,
# o — настройки из plan.json, ctx — {'t', 'i', 'mask'(), 'face'()} (маска считается только когда её просят)


# 01 ── ОРБИТА: карточки роликов крутятся вокруг человека (за ним и перед ним)
_thumbs = {}


def _thumb_set(paths):
    key = tuple(paths)
    if key not in _thumbs:
        res = []
        for p in paths:
            im = Image.open(p).convert('RGB')
            im = im.resize((216, int(216 * im.height / im.width)), Image.LANCZOS).crop((0, 0, 216, 384)) if im.height / im.width >= 384 / 216 \
                else im.resize((int(384 * im.width / im.height), 384), Image.LANCZOS)
            if im.size != (216, 384):
                x = (im.width - 216) // 2
                im = im.crop((x, 0, x + 216, 384))
            a = np.dstack([np.asarray(im), (rounded_mask(216, 384, 20) * 255).astype(np.uint8)])
            b = Image.fromarray(a)
            ImageDraw.Draw(b).rounded_rectangle((0, 0, 215, 383), 20, outline=(255, 255, 255, 200), width=3)
            res.append(np.asarray(b))
        _thumbs[key] = res
    return _thumbs[key]


def _orbit_layers(u, d, face, ths):
    fx, fy, fs = face
    cx, cy = W / 2, fy + fs * 2.0                         # уровень груди: передние карточки проходят под лицом
    SC = .5
    n = len(ths)
    ang0 = 1.6 * u + 1.4 * (1 - math.exp(-u * 3.5))      # быстрый старт, дальше ровное вращение
    grow = eo(u / .3)
    out_k = ei((u - (d - .28)) / .28)
    R = 430 * grow + 520 * out_k                          # на выходе разлетаются
    w2, h2 = int(W * SC), int(H * SC)
    back = np.zeros((h2, w2, 4), np.float32)
    front = np.zeros((h2, w2, 4), np.float32)
    items = sorted((math.cos(ang0 + 2 * math.pi * i / n), ang0 + 2 * math.pi * i / n, i) for i in range(n))
    src = np.float32([[0, 0], [216, 0], [216, 384], [0, 384]])
    for z, th, i in items:                                 # дальние раньше, ближние поверх
        x = cx + R * math.sin(th)
        y = cy - 70 * z
        sc = (.85 + .45 * (z + 1) / 2) * (.3 + .7 * grow)
        hw = 108 * sc * max(.12, abs(math.cos(th)))
        hh = 192 * sc
        tilt = .16 * math.sin(th)
        q = np.float32([[x - hw, y - hh * (1 - tilt)], [x + hw, y - hh * (1 + tilt)], [x + hw, y + hh * (1 + tilt)], [x - hw, y + hh * (1 - tilt)]])
        if math.cos(th) < 0:
            q = q[[1, 0, 3, 2]]
        M = cv2.getPerspectiveTransform(src, q * SC)
        im = ths[i].astype(np.float32).copy()
        im[..., :3] *= .55 + .45 * (z + 1) / 2             # дальние темнее
        im[..., 3] *= (1 - out_k)
        lay = cv2.warpPerspective(im, M, (w2, h2), flags=cv2.INTER_LINEAR)
        tgt = front if z >= 0 else back
        a = lay[..., 3:4] / 255.
        tgt[..., :3] = tgt[..., :3] * (1 - a) + lay[..., :3] * a
        tgt[..., 3:4] = tgt[..., 3:4] + (255 - tgt[..., 3:4]) * a
    return back, front


def fx_orbit(fr, ctx, u, d, o):
    ths = _thumb_set(o['images'])[:7]
    face = ctx['face']()
    bs, fs_ = [], []
    for off in np.linspace(-.5, .5, 5) / FPS:             # 5 копий = смаз движения карусели
        b, f = _orbit_layers(u + off, d, face, ths)
        bs.append(b)
        fs_.append(f)
    b = cv2.resize(sum(bs) / 5, (W, H))
    f = cv2.resize(sum(fs_) / 5, (W, H))
    out = fr.astype(np.float32)
    m = ctx['mask']()
    ab = b[..., 3:4] / 255. * (1 - m[..., None])            # задние — за человеком
    out = out * (1 - ab) + b[..., :3] / np.maximum(b[..., 3:4] / 255., 1e-3) * ab
    af = f[..., 3:4] / 255.
    return out * (1 - af) + f[..., :3] / np.maximum(af, 1e-3) * af


# 02 ── ВЕРТИГО: долли-зум — человек того же размера, фон наезжает, кадр холоднее
def _plate_bg(frame, m):
    """фон без человека (дыра заполнена inpaint), резкость вне дыры сохраняется"""
    sm = cv2.resize(frame, (270, 480), interpolation=cv2.INTER_AREA)
    mk = (cv2.resize(m, (270, 480)) > .25).astype(np.uint8) * 255
    mk = cv2.dilate(mk, np.ones((9, 9), np.uint8))
    pl = cv2.GaussianBlur(cv2.inpaint(sm, mk, 9, cv2.INPAINT_TELEA), (0, 0), 2.5)
    pl = cv2.resize(pl, (W, H), interpolation=cv2.INTER_CUBIC)
    hole = cv2.GaussianBlur(cv2.resize(mk, (W, H)).astype(np.float32) / 255, (0, 0), 6)[..., None]
    return (frame.astype(np.float32) * (1 - hole) + pl.astype(np.float32) * hole).astype(np.uint8)


def fx_vertigo(fr, ctx, u, d, o):
    fx, fy, fs = ctx['face']()
    m = ctx['mask']()
    amt = o.get('amount', .42)
    k = lambda uu: 1 + amt * eio(uu / 1.0) * back_env(uu, d, .35)
    bg = _plate_bg(fr, m)
    span = 2.5 / FPS
    bgz = radial(bg, fx, fy, k(u - span / 2), k(u + span / 2))
    mm = cv2.GaussianBlur(m, (0, 0), 1.2)[..., None]
    out = bgz * (1 - mm) + fr.astype(np.float32) * mm
    g = eio(u / .8) * back_env(u, d, .35)
    out *= np.array([1 - .06 * g, 1, 1 + .08 * g], np.float32)       # холоднее
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - .28 * g * np.clip(((xx - W / 2) / (W * .62)) ** 2 + ((yy - H / 2) / (H * .62)) ** 2, 0, 1)
    return out * vig[..., None].astype(np.float32)


# 03 ── ЗУМ КАМЕРЫ: интерфейс камеры (REC, уголки на лице, шкала 1.00→1.30×) + наезд с зум-смазом
def _push(u):
    """медленный разгон → быстрый наезд → мягкая посадка (как живой зум)"""
    u = clamp(u)
    return .18 * (u / .55) ** 2 if u < .55 else .18 + .82 * eo((u - .55) / .45)


def fx_camzoom(fr, ctx, u, d, o):
    fx, fy, fs = ctx['face']()
    amt = o.get('amount', .30)
    z = lambda uu: 1 + amt * _push((uu + .25) / .95) * back_env(uu, d, .35)
    span = 3 / FPS
    out = radial(fr, fx, fy, z(u - span / 2), z(u + span / 2))
    zz = z(u)
    a = eo(u / .15) * back_env(u, d, .2)
    ui = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ui)
    bw, bh = fs * .62 * zz, fs * .74 * zz
    x0, y0, x1, y1 = fx - bw, fy - bh, fx + bw, fy + bh
    L, c = 40, (255, 255, 255, int(235 * a))
    for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):   # уголки фокуса на лице
        dr.line((px, py, px + sx * L, py), fill=c, width=4)
        dr.line((px, py, px, py + sy * L), fill=c, width=4)
    yb = o.get('ui_y', 1500)
    if int(ctx['t'] * 2) % 2 == 0:                                     # мигающая точка REC
        dr.ellipse((96, yb + 4, 118, yb + 26), fill=(255, 59, 48, int(255 * a)))
    f = font('medium', 26)
    t = ctx['t']
    dr.text((130, yb), f'REC  00:00:{int(t) % 60:02d}:{int(t * FPS) % FPS:02d}', font=f, fill=(255, 255, 255, int(230 * a)))
    rx0, rx1, ry = 470, 860, yb + 15
    for i in range(41):                                                # шкала зума
        x = rx0 + (rx1 - rx0) * i / 40
        h = 16 if i % 10 == 0 else 8
        dr.line((x, ry - h / 2, x, ry + h / 2), fill=(255, 255, 255, int(150 * a)), width=2)
    mx = rx0 + (rx1 - rx0) * clamp((zz - 1) / .4)
    dr.polygon(((mx, ry - 14), (mx - 8, ry - 26), (mx + 8, ry - 26)), fill=YEL + (int(255 * a),))
    dr.text((880, yb), f'{zz:.2f}×', font=f, fill=YEL + (int(255 * a),))
    for (px, py, sx, sy) in ((60, 300, 1, 1), (W - 60, 300, -1, 1), (60, 1640, 1, -1), (W - 60, 1640, -1, -1)):   # рамка видоискателя
        dr.line((px, py, px + sx * 60, py), fill=(255, 255, 255, int(120 * a)), width=3)
        dr.line((px, py, px, py + sy * 60), fill=(255, 255, 255, int(120 * a)), width=3)
    return over(out, np.asarray(ui))


# 04 ── КИПЯЩИЙ КОНТУР: рисованный дрожащий контур вокруг человека + каракули и искры
def _contour_pts(m, grow, step=7):
    mk = (m > .5).astype(np.uint8)
    sm = cv2.resize(mk, (W // 2, H // 2), interpolation=cv2.INTER_NEAREST)
    if grow:
        sm = cv2.dilate(sm, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
    cs, _ = cv2.findContours(sm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return np.zeros((0, 2))
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(np.float32) * 2
    c = c[::max(1, step // 2)]
    c = c[(c[:, 1] < H - 30) & (c[:, 0] > 8) & (c[:, 0] < W - 8)]
    if not len(c):
        return c
    return np.roll(c, -int(np.argmin(c[:, 1])), 0)                       # рисуем от макушки


def _boil(pts, seed, amp):
    rnd = np.random.default_rng(seed)
    n = len(pts)
    if n < 4:
        return pts
    ctrl = rnd.normal(0, amp, (n // 10 + 2, 2))
    xi = np.linspace(0, len(ctrl) - 1, n)
    return pts + np.stack([np.interp(xi, np.arange(len(ctrl)), ctrl[:, j]) for j in (0, 1)], 1)


def _runs(pts, maxjump=40):
    runs, cur = [], [pts[0]] if len(pts) else []
    for a, b in zip(pts[:-1], pts[1:]):
        if np.hypot(*(b - a)) > maxjump:
            runs.append(cur)
            cur = [b]
        else:
            cur.append(b)
    if cur:
        runs.append(cur)
    return runs


def fx_doodle(fr, ctx, u, d, o):
    m = ctx['mask']()
    out = fr.astype(np.float32)
    seed = ctx['i'] // 2                                                   # перерисовка раз в 2 кадра = «кипение»
    reveal = eo(u / .38)
    fade = 1 - eo((u - (d - .18)) / .18)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    for grow, amp, col, wdt, dash in ((22, 3.5, (255, 255, 255), 7, None), (50, 6, YEL, 5, 70)):
        pts = _contour_pts(m, grow)
        if len(pts) < 10:
            continue
        pts = _boil(pts, seed * 7 + grow, amp)[:int(len(pts) * reveal)]
        for run in _runs(pts):
            if len(run) < 2:
                continue
            if dash:
                for i in range(0, len(run) - 1, dash // 4):
                    seg = run[i:i + dash // 7]
                    if (i // (dash // 4)) % 2 == 0 and len(seg) > 1:
                        dr.line([tuple(p) for p in seg], fill=col + (int(255 * fade),), width=wdt, joint='curve')
            else:
                dr.line([tuple(p) for p in run], fill=col + (int(255 * fade),), width=wdt, joint='curve')
    fx, fy, fs = ctx['face']()
    rnd = random.Random(seed)
    cols = [(255, 160, 200), (140, 200, 255), YEL, (255, 255, 255)]
    spots = [(fx - fs * 1.15, fy - fs * .9), (fx + fs * 1.2, fy - fs * .7), (fx - fs * 1.35, fy + fs * .9), (fx + fs * 1.4, fy + fs * 1.1)]
    for i, (sx, sy) in enumerate(spots):                                  # спирали и искры появляются по очереди
        if reveal < (i + 1) / 5:
            continue
        c = cols[i % 4] + (int(255 * fade),)
        if i % 2 == 0:
            ps = []
            for k in range(26):
                a = k / 25 * 4 * math.pi
                r = 10 + k * 1.6
                ps.append((sx + r * math.cos(a) + rnd.uniform(-2, 2), sy + r * .7 * math.sin(a) + rnd.uniform(-2, 2)))
            dr.line(ps, fill=c, width=5, joint='curve')
        else:
            for k in range(6):
                a = k / 6 * 2 * math.pi + rnd.uniform(-.15, .15)
                r0, r1 = 16 + rnd.uniform(-3, 3), 42 + rnd.uniform(-5, 5)
                dr.line((sx + r0 * math.cos(a), sy + r0 * math.sin(a), sx + r1 * math.cos(a), sy + r1 * math.sin(a)), fill=c, width=5)
    return over(out, np.asarray(lay))


# 05 ── ВЫХОД ИЗ РАМКИ: кадр сжимается в пост Instagram, голова вылезает за верх рамки, осколки
def _heart(dr, x, y, s, col):
    dr.ellipse((x - s, y - s * .6, x, y + s * .4), outline=col, width=3)
    dr.ellipse((x, y - s * .6, x + s, y + s * .4), outline=col, width=3)
    dr.line((x - s * .95, y + .05 * s, x, y + s * 1.05), fill=col, width=3)
    dr.line((x + s * .95, y + .05 * s, x, y + s * 1.05), fill=col, width=3)


def fx_framebreak(fr, ctx, u, d, o):
    fx, fy, fs = ctx['face']()
    m = ctx['mask']()
    S1 = .70
    cw, ch = int(W * S1), 700
    cx0 = (W - cw) // 2
    card_top = o.get('card_top', 790)
    oy1 = card_top - S1 * fy                                               # верх поста режет лицо по линии носа
    k = eio(u / .32) * back_env(u, d, .3)
    s = 1 + (S1 - 1) * k
    ox, oy = cx0 * k, oy1 * k
    bg = cv2.GaussianBlur(cv2.resize(fr, (W // 4, H // 4)), (0, 0), 6)
    bg = cv2.resize(bg, (W, H)).astype(np.float32) * (1 - .62 * k)
    A = np.float32([[s, 0, ox], [0, s, oy]])
    sc = cv2.warpAffine(fr, A, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    msc = cv2.warpAffine(m, A, (W, H), flags=cv2.INTER_LINEAR)
    x0, x1 = cx0 * k, W - cx0 * k
    y0, y1 = card_top * k, H + (card_top + ch - H) * k
    r = int(30 * k)
    clip = Image.new('L', (W, H), 0)
    ImageDraw.Draw(clip).rounded_rectangle((x0, y0, x1, y1), r, fill=255)
    cm = np.asarray(clip, np.float32)[..., None] / 255.
    out = bg * (1 - cm) + sc.astype(np.float32) * cm
    ui = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(ui)
    if k > .6:                                                             # интерфейс поста: лайк, коммент, ник, «Подписаться»
        a = int(255 * clamp((k - .6) / .4))
        dr.rounded_rectangle((x0, y0, x1, y1), r, outline=(255, 255, 255, a // 4), width=2)
        ix = x1 - 52
        _heart(dr, ix, y1 - 250, 15, (255, 255, 255, a))
        dr.ellipse((ix - 15, y1 - 195, ix + 15, y1 - 165), outline=(255, 255, 255, a), width=3)
        dr.polygon(((ix - 16, y1 - 128), (ix + 16, y1 - 140), (ix + 2, y1 - 110)), outline=(255, 255, 255, a), width=3)
        dr.ellipse((x0 + 26, y1 - 72, x0 + 70, y1 - 28), fill=(220, 220, 225, a))
        hf = font('medium', 26)
        handle = o.get('handle', 'your_name')
        dr.text((x0 + 84, y1 - 64), handle, font=hf, fill=(255, 255, 255, a))
        bx = x0 + 84 + hf.getlength(handle) + 18
        dr.rounded_rectangle((bx, y1 - 66, bx + 150, y1 - 30), 10, outline=(255, 255, 255, a), width=2)
        dr.text((bx + 14, y1 - 62), o.get('button', 'Стежити'), font=font('regular', 22), fill=(255, 255, 255, a))
    out = over(out, np.asarray(ui))
    if u >= .34 and k > .5:                                                # голова вылезает над верхом поста
        above = np.zeros((H, W), np.float32)
        above[:int(y0) + 2] = 1
        above = cv2.GaussianBlur(above, (0, 0), 1.5)
        mh = cv2.GaussianBlur(msc, (0, 0), 1.0) * above
        pop = 1 + .04 * math.exp(-(u - .34) * 14)                          # толчок при проломе
        scp = sc
        if pop > 1.002:
            mh = warp_scale(mh, pop, W / 2, y0)
            scp = warp_scale(sc, pop, W / 2, y0)
        out = out * (1 - mh[..., None]) + scp.astype(np.float32) * mh[..., None]
        p = u - .34
        if p < .75:                                                        # осколки рамки разлетаются по параболе
            rnd = random.Random(11)
            sl = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            ds = ImageDraw.Draw(sl)
            for i in range(18):
                sx = rnd.uniform(x0 + 30, x1 - 30)
                sy = y0 + rnd.uniform(-10, 10)
                vx = (sx - W / 2) * rnd.uniform(1.2, 2.6)
                vy = -rnd.uniform(500, 1100)
                px, py = sx + vx * p, sy + vy * p + 1400 * p * p
                sz = rnd.uniform(14, 40)
                a0 = rnd.uniform(0, 6.28) + p * rnd.uniform(-9, 9)
                pts = [(px + sz * math.cos(a0 + j * 2.2 + rnd.uniform(-.4, .4)), py + sz * .8 * math.sin(a0 + j * 2.2)) for j in range(3)]
                al = int(230 * (1 - p / .75))
                ds.polygon(pts, fill=(235, 240, 245, al // 3), outline=(255, 255, 255, al))
            out = over(out, np.asarray(sl.filter(ImageFilter.GaussianBlur(.8))))
        if p < .1:                                                         # вспышка по линии пролома
            fl = np.zeros((H, W), np.float32)
            cv2.line(fl, (int(x0), int(y0)), (int(x1), int(y0)), 1.0, 6)
            out = out + (cv2.GaussianBlur(fl, (0, 0), 10) * 3 * (1 - p / .1))[..., None] * 255
    return out


# 06 ── БУКВЫ-ВЫРЕЗКИ: тетрадный фон, человек вырезан с белой кромкой, буквы из журналов по одной
_paper = [None]


def _paper_bg():
    if _paper[0] is None:
        im = Image.new('RGB', (W, H), (243, 239, 229))
        d = ImageDraw.Draw(im)
        for x in range(0, W, 46):
            d.line((x, 0, x, H), fill=(196, 214, 228), width=2)
        for y in range(0, H, 46):
            d.line((0, y, W, y), fill=(196, 214, 228), width=2)
        rnd = random.Random(2)
        top = [(x, 760 + rnd.uniform(-14, 14) + x * .06) for x in range(-20, W + 40, 26)]
        bot = [(x, 980 + rnd.uniform(-14, 14) + x * .06) for x in range(W + 40, -40, -26)]
        d.polygon(top + bot, fill=(250, 222, 92))                         # полоса скотча-маркера
        pts = [(x + rnd.uniform(-10, 10), y + rnd.uniform(-10, 10)) for x, y in [(-20, 1380), (420, 1340), (460, 1700), (-20, 1760)]]
        d.polygon(pts, fill=(196, 160, 112))                              # обрывок крафта
        arr = np.asarray(im).astype(np.float32)
        noise = np.random.default_rng(1).normal(0, 6, (H // 2, W // 2)).astype(np.float32)
        _paper[0] = np.clip(arr + cv2.resize(cv2.GaussianBlur(noise, (0, 0), 1.2), (W, H))[..., None], 0, 255)
    return _paper[0]


RANSOM = [((244, 240, 230), (20, 20, 20), 'r1'), ((255, 214, 90), (20, 20, 20), 'r2'), ((22, 22, 24), (255, 255, 255), 'r3'),
          ((40, 70, 190), (255, 255, 255), 'r4'), ((255, 255, 255), (220, 40, 40), 'r5'), ((236, 226, 205), (30, 30, 30), 'r2')]
_chips = {}


def _chip(ch, i):
    k = (ch, i)
    if k not in _chips:
        rnd = random.Random(i * 31 + ord(ch))
        bg, fg, fk = RANSOM[(i * 5 + ord(ch)) % len(RANSOM)]
        f = font(fk, rnd.choice([118, 130, 142]))
        l, t, r, b = f.getbbox(ch)
        pw, ph = r - l + rnd.randint(22, 36), b - t + rnd.randint(22, 36)
        im = Image.new('RGBA', (pw + 20, ph + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pts = [(10 + rnd.uniform(-4, 4), 10 + rnd.uniform(-4, 4)), (10 + pw + rnd.uniform(-4, 4), 10 + rnd.uniform(-4, 4)),
               (10 + pw + rnd.uniform(-4, 4), 10 + ph + rnd.uniform(-4, 4)), (10 + rnd.uniform(-4, 4), 10 + ph + rnd.uniform(-4, 4))]
        d.polygon(pts, fill=bg + (255,))
        d.text((10 + (pw - (r - l)) / 2 - l, 10 + (ph - (b - t)) / 2 - t), ch, font=f, fill=fg + (255,))
        _chips[k] = np.asarray(im.rotate(rnd.uniform(-9, 9), Image.BICUBIC, expand=True))
    return _chips[k]


def fx_ransom(fr, ctx, u, d, o):
    m = ctx['mask']()
    out = _paper_bg().copy()
    mk = (m > .5).astype(np.uint8)
    border = cv2.GaussianBlur(cv2.dilate(mk, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))).astype(np.float32), (0, 0), 1.2)
    sh = cv2.GaussianBlur(np.roll(np.roll(border, 14, 0), 8, 1), (0, 0), 10)[..., None] * .35
    out = out * (1 - sh)
    out = out * (1 - border[..., None]) + 255 * border[..., None]         # белая кромка «вырезано ножницами»
    mm = cv2.GaussianBlur(m, (0, 0), 1.0)[..., None]
    out = out * (1 - mm) + fr.astype(np.float32) * mm
    rnd = random.Random(int(ctx['t'] * 12))                                # стоп-моушн дрожь 12 к/с
    lines = o.get('lines', ['ТВІЙ', 'ТЕКСТ'])
    ys = o.get('ys', [420, 590])                                           # строки над головой (не на лице!)
    n_on = int((u - .12) / o.get('step', .05))                             # пауза между буквами
    k = 0
    for li, word in enumerate(lines):
        chips = [_chip(c, j + li * 10) for j, c in enumerate(word) if c != ' ']
        tw = sum(c.shape[1] - 18 for c in chips)
        x = W / 2 - tw / 2
        for c in chips:
            if k < n_on:
                jx, jy = rnd.randint(-3, 3), rnd.randint(-3, 3)
                over(out, shadow_of(c, 6, (3, 6), .45), int(x + jx), int(ys[li] - c.shape[0] / 2 + jy))
                over(out, c, int(x + jx), int(ys[li] - c.shape[0] / 2 + jy))
            x += c.shape[1] - 18
            k += 1
    if u > d - .22:                                                        # выход: рваный край уезжает вверх
        p = eio((u - (d - .22)) / .22)
        edge = H - p * (H + 120)
        ctrl = np.random.default_rng(4).normal(0, 18, W // 30 + 2)
        ey = edge + np.interp(np.arange(W), np.arange(len(ctrl)) * 30, ctrl)
        yy = np.arange(H)[:, None]
        below = (yy > ey[None, :]).astype(np.float32)[..., None]
        fringe = ((yy > ey[None, :] - 16) & (yy <= ey[None, :])).astype(np.float32)[..., None]
        out = out * (1 - below) + fr.astype(np.float32) * below
        out = out * (1 - fringe) + 248 * fringe
    return out


# 07 ── ЖИДКОЕ СТЕКЛО: стеклянная линза едет по кадру (по субтитрам), увеличивает и преломляет под собой
def _liquid(img, box, alpha=1.0, mag=1.9, rim=1.0, tint=.06, shadow=.25):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    if w < 6 or h < 6 or alpha < .02:
        return img
    pad = int(h * .6) + 4
    X0c, Y0c = max(0, int(x0) - pad), max(0, int(y0) - pad)
    X1c, Y1c = min(W, int(math.ceil(x1)) + pad), min(H, int(math.ceil(y1)) + pad)
    reg = img[Y0c:Y1c, X0c:X1c].astype(np.float32)
    H_, W_ = reg.shape[:2]
    yy, xx = np.mgrid[0:H_, 0:W_].astype(np.float32)
    cx, cy = (x0 + x1) / 2 - X0c, (y0 + y1) / 2 - Y0c
    b = h / 2
    a_ = max(0., w / 2 - b)
    px = np.clip(xx - cx, -a_, a_)
    dx, dy = xx - cx - px, yy - cy
    dd = np.sqrt(dx ** 2 + dy ** 2) / b                                    # 0 в центре, 1 на кромке
    inside = dd < 1
    s = 1 / mag + (1.45 - 1 / mag) * np.clip(dd, 0, 1) ** 3.2             # к краю берём пиксели дальше = преломление
    out = reg.copy()
    for ci, ds in enumerate((.035, 0, -.035)):                            # лёгкая хроматика по краю
        ss = s * (1 + ds * np.clip(dd, 0, 1) ** 3)
        mx = (cx + px + dx * ss).astype(np.float32)
        my = (cy + dy * ss).astype(np.float32)
        out[..., ci] = cv2.remap(reg[..., ci], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = out * (1 - tint) + 255 * tint
    edge = np.clip((dd - .78) / .22, 0, 1) ** 2
    light = np.clip(-(dy / b) * .8 - (dx / max(b, 1)) * .2, 0, 1)
    out += (edge * (60 + 150 * light) * rim)[..., None]                     # блик сверху-слева
    out -= (np.clip((dd - .55) / .45, 0, 1) ** 3 * np.clip(dy / b, 0, 1) * 35)[..., None]
    ring = np.exp(-((dd - .985) / .022) ** 2) * (.5 + .5 * light)
    out = out * (1 - ring[..., None] * .55 * rim) + 255 * ring[..., None] * .55 * rim
    aa = np.clip((1 - dd) * b * 1.2, 0, 1) * alpha
    res = reg * (1 - aa[..., None]) + np.clip(out, 0, 255) * aa[..., None]
    if shadow:
        sh = np.clip(1 - np.sqrt((xx - cx - px) ** 2 + (dy - b * .35) ** 2) / (b * 1.25), 0, 1) ** 2
        res = res * (1 - (sh * (1 - inside) * shadow * alpha)[..., None] * .6)
    img[Y0c:Y1c, X0c:X1c] = res
    return img


def fx_lens(fr, ctx, u, d, o):
    p0, p1 = o.get('from', [250, 1290]), o.get('to', [830, 1290])
    r, mag = o.get('r', 140), o.get('mag', 1.9)
    k = eio(u / d)
    a = eo(u / .2) * (1 - eo((u - (d - .2)) / .2))
    x, y = lerp(p0[0], p1[0], k), lerp(p0[1], p1[1], k) - 26 * math.sin(math.pi * k)   # лёгкая дуга
    rr = r * lerp(.6, 1, a)
    return _liquid(fr.astype(np.float32), (x - rr, y - rr, x + rr, y + rr), a, mag)


# 08 ── ЗУМ С БЛЮРОМ: плавный наезд «как оператор» с радиальным смазом движения, в конце мягкий отъезд
def fx_zoomblur(fr, ctx, u, d, o):
    fx, fy, fs = ctx['face']()
    amt = o.get('amount', .18)
    z = lambda uu: 1 + amt * _push(uu / max(.3, min(.85, d * .6))) * back_env(uu, d, min(.4, d * .35))
    span = o.get('blur', 3) / FPS
    return radial(fr, fx, fy * .9 + H / 2 * .1, z(u - span / 2), z(u + span / 2))


# 09 ── ВЫДЕЛЕНИЕ КАК В FIGMA: слово в рамке выделения, рамку тянут курсором с именем, потом слово растягивают
def _letters_layer(parts, size, cx, base, u, step=.022, dur=.34):
    """слово из частей [(текст, вид)], буквы входят из размытия с лёгким масштабом. → (RGBA, рамка)"""
    chars = []
    for txt, kind in parts:
        for ch in txt:
            chars.append((ch, kind))
    widths = [font(k, size).getlength(c) for c, k in chars]
    w = sum(widths)
    x = cx - w / 2
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for i, ((ch, kind), cw) in enumerate(zip(chars, widths)):
        p = eo((u - i * step) / dur)
        if p > 0:
            f = font(kind, size * (1.1 - .1 * p))
            im = Image.new('RGBA', (int(cw * 1.4) + 60, int(size * 1.6)), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((30, int(size * 1.6) - 30), ch, font=f, fill=(255, 255, 255, int(255 * p)), anchor='ls')
            if p < 1:
                im = im.filter(ImageFilter.GaussianBlur(8 * (1 - p)))
            lay.alpha_composite(im, (int(x - 30), int(base - size * 1.6 + 30)))
        x += cw
    box = (cx - w / 2 - 18, base - size * .74 - 18, cx + w / 2 + 18, base + size * .24 + 18)
    return lay, box


def _cursor(dr, x, y, name, col, a=1.0):
    s = 1.25
    pts = [(0, 0), (0, 30), (8, 23), (14, 37), (20, 34), (14, 21), (24, 21)]
    P = [(x + px * s, y + py * s) for px, py in pts]
    dr.polygon(P, fill=col + (int(255 * a),))
    dr.line(P + [P[0]], fill=(255, 255, 255, int(255 * a)), width=3)
    f = font('medium', 30)
    tw = f.getlength(name)
    bx, by = x + 26 * s, y + 34 * s
    dr.rounded_rectangle((bx, by, bx + tw + 26, by + 44), radius=10, fill=col + (int(255 * a),))
    dr.text((bx + 13, by + 22), name, font=f, fill=(255, 255, 255, int(255 * a)), anchor='lm')


def fx_figma(fr, ctx, u, d, o):
    word = o.get('word', 'виділення')
    it = o.get('italic', [4, 5])                                           # какие буквы курсивной антиквой: [с, до)
    parts = [(word[:it[0]], 'display'), (word[it[0]:it[1]], 'italic'), (word[it[1]:], 'display')]
    parts = [p for p in parts if p[0]]
    base = o.get('y', 1352)
    tg = o.get('grow_at', d * .55)                                          # когда тянут маркер и слово растёт
    g = 1 + (o.get('grow', 1.28) - 1) * eio((u - tg) / .45)
    fw = sum(font(k, 120).getlength(t) for t, k in parts)                  # ширина слова при 120 px
    size = min(120 * g, 120 * o.get('maxw', 820) / max(1, fw))             # вместе с ростом не шире maxw: курсору нужно место справа
    lay, box = _letters_layer(parts, size, W / 2, base, u)
    dr = ImageDraw.Draw(lay)
    fa = 1 - eio((u - (d - .25)) / .25)
    k = eio(u / .55)                                                       # рамку тянут из левого нижнего угла
    x0, y0, x1, y1 = box
    bx1, by0 = x0 + (x1 - x0) * k, y1 - (y1 - y0) * k
    col = FIGMA + (int(255 * fa),)
    dr.rectangle((x0, by0, bx1, y1), outline=col, width=3)
    for hx, hy in ((x0, by0), (bx1, by0), (x0, y1), (bx1, y1)):           # маркеры по углам
        dr.rectangle((hx - 9, hy - 9, hx + 9, hy + 9), fill=(255, 255, 255, int(255 * fa)), outline=col, width=3)
    if k > .9:                                                             # бирка размера как в Figma
        tag = f'{int(x1 - x0)} × {int(y1 - y0)}'
        f = font('medium', 26)
        tw = f.getlength(tag)
        dr.rounded_rectangle(((x0 + x1) / 2 - tw / 2 - 12, y1 + 14, (x0 + x1) / 2 + tw / 2 + 12, y1 + 52), 8, fill=col)
        dr.text(((x0 + x1) / 2, y1 + 33), tag, font=f, fill=(255, 255, 255, int(255 * fa)), anchor='mm')
    if u < tg:
        cx_, cy_ = bx1, by0
    else:
        p = eio((u - tg) / .2)
        cx_, cy_ = x1 + 2 * p, y0 + (y1 - 4 - y0) * p
    _cursor(dr, cx_, cy_, o.get('name', 'Ти'), PURPLE, a=clamp((u + .1) / .15) * fa)
    under = o.get('under', [])                                             # мелкая строка под рамкой по словам: [[сек от начала, "слово"], …]
    if under:
        f = font('medium', 42)
        sp = f.getlength(' ')
        ws = [f.getlength(w) for _, w in under]
        x = W / 2 - (sum(ws) + sp * (len(ws) - 1)) / 2
        for (tw_, w), ww in zip(under, ws):
            p = eo((u - tw_) / .25) * fa
            if p > 0:
                dr.text((x, base + 120 + 20 * (1 - p)), w, font=f, fill=CREAM + (int(255 * p),))
            x += ww + sp
    return over(fr.astype(np.float32), np.asarray(soft_shadow(lay, 16, .5)))


# 10 ── ЦИФРА ЗА ГОЛОВОЙ: огромная полупрозрачная цифра (контур) за человеком, всплывает из размытия
def fx_bignum(fr, ctx, u, d, o):
    m = ctx['mask']()
    s = str(o.get('text', '10'))
    style = o.get('style', 'outline')
    size = o.get('size', 900)
    f = font('display', size)
    l, t_, r, b = f.getbbox(s)
    pad = 40
    im = Image.new('RGBA', (r - l + pad * 2, b - t_ + pad * 2), CREAM + (0,))
    dd = ImageDraw.Draw(im)
    if style == 'outline':
        dd.text((pad - l, pad - t_), s, font=f, fill=CREAM + (16,), stroke_width=4, stroke_fill=CREAM + (140,))
    else:
        dd.text((pad - l, pad - t_), s, font=f, fill=CREAM + (52,))
    p = eo(u / .5)
    q = eio((u - (d - .35)) / .35)
    a = p * (1 - q)
    sc = 1.12 - .12 * p                                                    # въезжает из 112 %
    drift = -24 * clamp(u / max(.1, d)) - 120 * q                          # медленно всплывает, уходит вверх
    im2 = im.resize((max(2, int(im.width * sc)), max(2, int(im.height * sc))), Image.BICUBIC)
    bl = 18 * (1 - p) + 14 * q
    if bl > .4:
        im2 = im2.filter(ImageFilter.GaussianBlur(bl))
    if a < 1:
        im2.putalpha(im2.getchannel('A').point(lambda v: int(v * a)))
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    L.alpha_composite(im2, (int(W / 2 - im2.width / 2), int(o.get('y', 760) - im2.height / 2 + drift)))
    return under_person(fr.astype(np.float32), np.asarray(L), m)


# 11 ── МЕМ-МАЯТНИК: маленькая карточка-мем выезжает ИЗ-ЗА головы на пружине и качается на булавке
_meme = {}


def fx_meme(fr, ctx, u, d, o):
    m = ctx['mask']()
    path = o['image']
    w = o.get('w', 260)
    if path not in _meme:
        im = Image.open(path).convert('RGBA')
        _meme[path] = im.resize((w, int(im.height * w / im.width)), Image.LANCZOS)
    pic = _meme[path]
    k = spring(u, 10, .62)                                                 # выезд с лёгким перелётом
    q = eio((u - (d - .35)) / .35)                                         # уезжает обратно за голову
    sway = 6 * math.sin(2 * math.pi * u / 2.6) * clamp(u / .5)
    swing = o.get('rot', -6) * k + 10 * math.exp(-2.4 * u) * math.sin(7.0 * u) + sway
    b = 10
    card = Image.new('RGBA', (pic.width + 2 * b, pic.height + 2 * b), (255, 255, 255, 255))
    card.paste(pic, (b, b), pic)
    mk = Image.new('L', card.size, 0)
    ImageDraw.Draw(mk).rounded_rectangle((0, 0, card.width - 1, card.height - 1), 16, fill=255)
    card.putalpha(mk)
    pad = 60
    big = Image.new('RGBA', (card.width + 2 * pad, card.height + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(card, (pad, pad))
    px, py = big.width / 2, pad + 6
    dr = ImageDraw.Draw(big)                                               # булавка
    dr.ellipse((px - 13, py - 13, px + 13, py + 13), fill=(225, 60, 60, 255), outline=(255, 255, 255, 255), width=3)
    dr.ellipse((px - 5, py - 8, px + 1, py - 2), fill=(255, 255, 255, 200))
    rot = big.rotate(swing, Image.BICUBIC, center=(px, py))
    a = clamp(u / .12) * (1 - clamp((q - .6) / .4))
    if a < 1:
        rot.putalpha(rot.getchannel('A').point(lambda v: int(v * a)))
    sh = Image.new('RGBA', rot.size, (0, 0, 0, 0))
    sh.putalpha(rot.getchannel('A').point(lambda v: int(v * .4)))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    fx, fy, fs = ctx['face']()
    src = o.get('from', [fx, fy + fs * .3])                                # откуда: из-за головы
    cx, cy = o.get('to', [830, 640])                                       # куда: точка булавки
    mm = k * (1 - q)
    x = int(src[0] + (cx - src[0]) * mm - px)
    y = int(src[1] + (cy - src[1]) * mm - py)
    Lb = Image.new('RGBA', (W + 2000, H + 2000), (0, 0, 0, 0))             # с запасом: карточка может быть за краем
    Lb.alpha_composite(sh, (x + 5 + 1000, y + 14 + 1000))
    Lb.alpha_composite(rot, (x + 1000, y + 1000))
    L = Lb.crop((1000, 1000, 1000 + W, 1000 + H))
    return under_person(fr.astype(np.float32), np.asarray(L), m)


# 12 ── ПРУЖИННЫЙ ИНТЕРФЕЙС: стеклянная пилюля → раскрывается в карточку с тумблерами → схлопывается
def fx_spring(fr, ctx, u, d, o):
    rows = o.get('rows', ['пружина', 'переліт', 'інерція'])
    title = o.get('title', 'Spring UI')
    cy = o.get('y', 1330)
    tm = d * o.get('open_at', .24) if o.get('open_at', .24) < 1 else o['open_at']
    tb = d - o.get('close_at', .42)
    pill, cardsz = (320, 92), (660, 120 + 95 * len(rows))
    k_in = spring(u, 14.8, .54)
    k_m = spring(u - tm, 13.5, .55)
    k_b = spring(u - tb, 15.5, .6)
    k_out = eio((u - (d - .22)) / .22)
    mm = k_m * (1 - k_b) if u >= tb else k_m
    w = lerp(pill[0], cardsz[0], mm) * k_in * (1 - k_out)
    h = lerp(pill[1], cardsz[1], mm) * k_in * (1 - k_out)
    if w < 8 or h < 8:
        return fr.astype(np.float32)
    img = Image.fromarray(fr).convert('RGBA')
    cx = W / 2
    x0, y0, x1, y1 = int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)
    r = int(min(h / 2, lerp(46, 42, mm)))
    mask = Image.new('L', (W, H))
    ImageDraw.Draw(mask).rounded_rectangle((x0, y0, x1, y1), r, fill=255)
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * .35)))
    img.alpha_composite(sh, (0, 10))
    pad = 40
    bx = (max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad))
    glass = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    glass.paste(img.crop(bx).filter(ImageFilter.GaussianBlur(20)), bx[:2])  # матовое стекло: размытый фон
    glass = Image.alpha_composite(glass, Image.new('RGBA', (W, H), (255, 255, 255, 52)))
    glass.putalpha(mask)
    img.alpha_composite(glass)
    ImageDraw.Draw(img).rounded_rectangle((x0, y0, x1, y1), r, outline=(255, 255, 255, 120), width=2)
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(L)
    a_pill = clamp(1 - mm * 2.2) * (1 - k_out)
    if a_pill > 0:
        dr.text((cx, cy), title, font=font('medium', 38), fill=(255, 255, 255, int(255 * a_pill)), anchor='mm')
    if mm > .35:
        f = font('medium', 40)
        for i, s in enumerate(rows):
            k = spring(u - tm - .12 - i * .09, 16, .5) * (1 - clamp((u - tb + .05) / .18))
            if k <= 0:
                continue
            ry = y0 + 70 + i * 95 + (1 - k) * 46
            al = int(255 * clamp(k * 1.6) * (1 - k_out))
            dr.text((x0 + 120, ry), s, font=f, fill=(255, 255, 255, al), anchor='lm')
            on = spring(u - tm - .25 - i * .09, 18, .55)                   # тумблеры включаются по очереди
            tx = x1 - 140
            dr.rounded_rectangle((tx, ry - 24, tx + 84, ry + 24), 24, fill=(52, 199, 89, int(al * clamp(on))) if on > .05 else (255, 255, 255, int(al * .25)))
            kx = tx + 24 + 36 * clamp(on)
            dr.ellipse((kx - 20, ry - 20, kx + 20, ry + 20), fill=(255, 255, 255, al))
            dr.ellipse((x0 + 58, ry - 9, x0 + 76, ry + 9), fill=(255, 255, 255, al))
    img.alpha_composite(L)
    return np.asarray(img.convert('RGB')).astype(np.float32)


FX = {'orbit': fx_orbit, 'vertigo': fx_vertigo, 'camzoom': fx_camzoom, 'doodle': fx_doodle, 'framebreak': fx_framebreak,
      'ransom': fx_ransom, 'lens': fx_lens, 'zoomblur': fx_zoomblur, 'figma': fx_figma, 'bignum': fx_bignum, 'meme': fx_meme,
      'spring': fx_spring}
HELP = {
    'orbit': 'карточки роликов вокруг человека. images: [пути картинок] (по умолчанию — 7 кадров из самого видео)',
    'vertigo': 'долли-зум: фон наезжает, человек на месте. amount: 0.42',
    'camzoom': 'интерфейс камеры REC + наезд на лицо. amount: 0.30, ui_y: 1500',
    'doodle': 'кипящий рисованный контур + каракули',
    'framebreak': 'кадр → пост Instagram, голова вылезает. handle: "ник", button: "Подписаться", card_top: 790',
    'ransom': 'тетрадный фон + буквы-вырезки. lines: ["СЛОВО", "СЛОВО"], ys: [420, 590], step: 0.05',
    'lens': 'линза жидкого стекла едет. from: [250,1290], to: [830,1290], r: 140, mag: 1.9',
    'zoomblur': 'плавный наезд с радиальным смазом. amount: 0.18, blur: 3',
    'figma': 'слово в рамке Figma + курсор. word, italic: [4,5], name: "Ты", grow_at: сек, grow: 1.28, under: [[сек,"слово"],…], y: 1352',
    'bignum': 'цифра за головой. text: "10", style: outline|fill, size: 900, y: 760',
    'meme': 'мем-маятник из-за головы. image: путь (обязательно), to: [830,640], w: 260',
    'spring': 'пилюля → карточка с тумблерами. title, rows: [3 строки], y: 1330, open_at: 0.24, close_at: 0.42',
}
NEED_MASK = {'orbit', 'vertigo', 'camzoom', 'doodle', 'framebreak', 'ransom', 'zoomblur', 'bignum', 'meme'}

# ─────────────────────────────── рендер ───────────────────────────────

VF = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=rgb24'


def probe_dur(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).strip())


def grab(path, t):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{max(0, t):.3f}', '-i', path, '-frames:v', '1', '-vf', VF,
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3) if len(raw) == W * H * 3 else None


def prepare(plan, base):
    """пути, кадры для орбиты по умолчанию, шрифты"""
    FONT_OVERRIDE.update(plan.get('fonts', {}))
    rel = lambda p: p if os.path.isabs(p) else os.path.join(base, p)
    plan['input'] = rel(plan['input'])
    plan['output'] = rel(plan.get('output', os.path.splitext(plan['input'])[0] + '_fx.mp4'))
    dur = probe_dur(plan['input'])
    for e in plan['effects']:
        assert e['fx'] in FX, f"нет эффекта «{e['fx']}». Есть: {', '.join(FX)}"
        assert e['t1'] > e['t0'], f"{e['fx']}: t1 должно быть больше t0"
        if e['fx'] == 'meme':
            assert e.get('image'), 'meme: нужен "image": путь к картинке мема'
            e['image'] = rel(e['image'])
        if e['fx'] == 'orbit':
            if e.get('images'):
                e['images'] = [rel(p) for p in e['images']]
            else:                                                          # 7 кадров из самого видео
                d = os.path.join(os.path.dirname(plan['output']), '.fx12_thumbs')
                os.makedirs(d, exist_ok=True)
                e['images'] = []
                for k in range(7):
                    p = os.path.join(d, f'{k}.jpg')
                    if not os.path.exists(p):
                        fr = grab(plan['input'], dur * (k + .5) / 7)
                        if fr is not None:
                            Image.fromarray(fr).save(p, quality=90)
                    if os.path.exists(p):
                        e['images'].append(p)
    plan['effects'].sort(key=lambda e: e['t0'])
    return plan


def render_frame(fr, i, plan, person, only=None):
    t = i / FPS
    e = next((e for e in plan['effects'] if e['t0'] <= t < e['t1'] and (not only or e['fx'] in only)), None)
    if e is None:
        return fr
    cache = {}

    def mask():
        if 'm' not in cache:
            cache['m'] = person.mask(fr, i)
        return cache['m']

    def face():
        if 'f' not in cache:
            cache['f'] = person.face(fr, cache.get('m'))
        return cache['f']
    if e['fx'] in NEED_MASK:
        mask()
    ctx = dict(t=t, i=i, mask=mask, face=face)
    out = FX[e['fx']](fr, ctx, t - e['t0'], e['t1'] - e['t0'], e)
    return np.clip(out + .5, 0, 255).astype(np.uint8)


def render(plan, only=None):
    src, dst = plan['input'], plan['output']
    person = Person(plan.get('mask_model', 'u2net_human_seg'))
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-vf', VF, '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-i', src, '-map', '0:v', '-map', '1:a?', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
                            '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', dst],
                           stdin=subprocess.PIPE)
    n, sz = 0, W * H * 3
    total = int(probe_dur(src) * FPS)
    while True:
        buf = dec.stdout.read(sz)
        if len(buf) < sz:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        enc.stdin.write(render_frame(fr, n, plan, person, only).tobytes())
        n += 1
        if n % 30 == 0:
            print(f'\r[fx12] {n}/{total} кадров', end='', flush=True)
    enc.stdin.close()
    enc.wait()
    dec.wait()
    print(f'\n[fx12] готово: {dst}')
    return dst


def sheet(plan, only=None):
    """по 3 кадра каждого эффекта (начало, середина, конец) — быстрый просмотр до полного рендера"""
    person = Person(plan.get('mask_model', 'u2net_human_seg'))
    effects = [e for e in plan['effects'] if not only or e['fx'] in only]
    tw, th = 216, 384
    cols = 3
    im = Image.new('RGB', (cols * tw + (cols + 1) * 8, len(effects) * (th + 40) + 8), (24, 24, 26))
    dr = ImageDraw.Draw(im)
    for r, e in enumerate(effects):
        d = e['t1'] - e['t0']
        for c, k in enumerate((.2, .5, .85)):
            i = int(round((e['t0'] + d * k) * FPS))
            fr = grab(plan['input'], i / FPS)
            if fr is None:
                continue
            person.prev_m = person.prev_f = None
            out = render_frame(fr, i, plan, person)
            x, y = 8 + c * (tw + 8), 8 + r * (th + 40)
            im.paste(Image.fromarray(out).resize((tw, th), Image.LANCZOS), (x, y + 32))
            dr.text((x, y + 4), f"{e['fx']}  {i / FPS:.2f}s", fill=(255, 214, 90), font=font('medium', 20))
    p = os.path.splitext(plan['output'])[0] + '_sheet.jpg'
    im.save(p, quality=88)
    print(f'[fx12] контакт-лист: {p}')
    return p


def main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return
    if argv[0] == '--list':
        for k, v in HELP.items():
            print(f'  {k:11} {v}')
        return
    path = argv[0]
    plan = prepare(json.load(open(path, encoding='utf-8')), os.path.dirname(os.path.abspath(path)))
    only = set(argv[argv.index('--only') + 1].split(',')) if '--only' in argv else None
    if '--sheet' in argv:
        sheet(plan, only)
    else:
        render(plan, only)


if __name__ == '__main__':
    main(sys.argv[1:])
