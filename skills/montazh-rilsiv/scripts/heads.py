"""Head layouts («подачі голови»): the person's own video becomes the graphic. For the length of one phrase the frame
shrinks into a shape on a brand background (window, circle, cloud, soft edges, polaroid, ...) and their key words, photos
or a picture gather around it. build_reel.py draws a card {"type": "head", "look": "<look>", ...} with build().

Card fields (edit.json):
  look    window | circle | cloud | soft | polaroid | bigword | top | collage | pile | around | picture
  words   ["вчилася", "знання", ...] or [{"text", "t"?, "role"?: "head"|"body"|"accent"}]: their own words, 1-4 of them.
          Each appears the moment they say it (matched in master_transcript.json); "t" (cut seconds) forces a time.
  bg      main | deep | pop | soft | light | "#hex" (default per look below)
  images  ["a.jpg", ...]  their photos: collage (2-4), pile (3-6), picture (1), polaroid (1-3, the background changes per word)
  word    bigword: the one huge word (default: the last of "words")
  brackets  false: no [ ] around the words in cloud / top / around
Every look keeps the face in its window, takes over the whole frame for its seconds (captions step aside, the card carries
the words) and hands the frame back at its end. Tested placements: references/motions.md «Подачі голови»."""
import json, re

W, H = 1080, 1920
LOOKS = {   # default background, short Ukrainian name (the review page and motions.py show it)
    "window":   ("light", "Вікно, слова стовпчиком різними шрифтами"),
    "circle":   ("pop",   "Коло на кольорі в крапку, слова зверху"),
    "cloud":    ("soft",  "Хмаринка, слова в [дужках] навколо"),
    "soft":     ("main",  "М'які розмиті краї, велике слово зверху"),
    "polaroid": ("duo",   "Поляроїд над фоном, що міняється на кожному слові"),
    "bigword":  ("pop",   "Величезне розмите слово фокусується над маленьким вікном"),
    "top":      ("light", "Голова зверху, слова падають на низ"),
    "collage":  ("light", "Колаж: ти одна з нумерованих фото"),
    "pile":     ("light", "Купка чорно-білих фото, ти зверху"),
    "around":   (None,    "Повний кадр, слова в [дужках] навколо голови"),
    "picture":  ("light", "Картинка над тобою і підпис-пігулка під нею"),
}
NEEDS_IMAGES = {"collage": 2, "pile": 3, "picture": 1}


def _lum(hexc):
    h = hexc.lstrip("#")
    if len(h) == 3: h = "".join(x * 2 for x in h)
    try: r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError: return 1.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def cloud_svg():
    import math
    bumps = "".join(f'<circle cx="{430 + 330 * math.cos(2 * math.pi * i / 14):.0f}" cy="{400 + 300 * math.sin(2 * math.pi * i / 14):.0f}" '
                    f'r="{92 + 14 * (i % 2)}"/>' for i in range(14))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 860 800" preserveAspectRatio="none"><g fill="#fff">'
            f'<ellipse cx="430" cy="400" rx="335" ry="305"/>{bumps}</g></svg>')


SOFT_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="none">'
            '<filter id="f" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4"/></filter>'
            '<rect x="9" y="7" width="82" height="86" rx="10" fill="#fff" filter="url(#f)"/></svg>')


def _norm(s):
    return re.sub(r"[^\w]", "", s.lower())


def time_words(items, a, b, transcript):
    """[(text, t, role)] - each word at the moment it is said inside a..b (prefix match, so «знання» finds «знаннями»)."""
    ws = [w for w in transcript if a - 0.25 <= w["start"] < b and w.get("text", "").strip()]
    out, k = [], 0
    for j, it in enumerate(items):
        it = {"text": it} if isinstance(it, str) else dict(it)
        t = it.get("t")
        if t is None:
            key = _norm(it["text"].split()[0])[:max(3, min(5, len(_norm(it["text"].split()[0])) - 1))] if it["text"].split() else ""
            for m in range(k, len(ws)):
                if key and _norm(ws[m]["text"]).startswith(key): t, k = ws[m]["start"], m + 1; break
        if t is None: t = a + 0.25 + (b - a - 0.6) * j / max(1, len(items))   # not said here: spread evenly
        out.append((it["text"], max(a, min(t, b - 0.3)), it.get("role")))
    return out


def build(c, a, b, cid, X):
    """X: the build_reel context - js, front, headbg lists, sfx(), font(), fit(), img(), esc(), zone(), quiet, colours, face,
    transcript, files dict (name -> text) written into the project."""
    look = c.get("look", "window")
    if look not in LOOKS: print(f"head: unknown look '{look}', using window"); look = "window"
    imgs = [p for p in (X["img"](s) for s in c.get("images", [])) if p]
    if look in NEEDS_IMAGES and len(imgs) < NEEDS_IMAGES[look]:
        print(f"head '{look}' at {a:.1f}s needs {NEEDS_IMAGES[look]}+ of their photos (\"images\"), has {len(imgs)}: drawn as window")
        look = "window"
    js, front, bgl, esc, font = X["js"], X["front"], X["headbg"], X["esc"], X["font"]
    MAIN, POP, SOFT, DEEP, LIGHT = X["MAIN"], X["POP"], X["SOFT"], X["DEEP"], X["LIGHT"]
    q = X["q"]
    FX, FY = X["face_c"]
    bgname = c.get("bg") or LOOKS[look][0]
    BG = {"main": MAIN, "deep": DEEP, "pop": POP, "soft": SOFT, "light": "#FAFAF7" if LIGHT.upper() == "#FFFFFF" else LIGHT}.get(bgname, bgname)
    dark = bool(BG) and BG.startswith("#") and _lum(BG) < 0.45
    INK = LIGHT if dark else MAIN
    HL = SOFT if BG == POP else POP                       # highlight box colour that differs from the background
    words = time_words(c.get("words", []), a, b, X["transcript"])
    brk = (lambda s: f"[{s}]") if c.get("brackets", True) else (lambda s: s)
    n = [0]

    # ---- the background layer for this card (behind the camera window)
    bid = f"{cid}bg"
    if look == "around": bid = None
    elif bgname == "duo":
        bgl.append(f'<div id="{bid}" class="hbg"><div class="hduo" id="{cid}duo"></div><div class="htint" id="{cid}tint"></div><div class="hdots"></div></div>')
    else:
        dots = ";background-image:radial-gradient(circle, rgba(13,26,15,.16) 4px, transparent 5px);background-size:46px 46px" if look == "circle" else ""
        bgl.append(f'<div id="{bid}" class="hbg" style="background-color:{BG}{dots}"></div>')
    if bid: js.append(f'tl.set("#{bid}",{{autoAlpha:1}},{q(a)});tl.set("#{bid}",{{autoAlpha:0}},{q(b)});')

    def frame(t, box, s, fy=0.40, radius="0px", border="0px solid transparent", rot=0, mask="none", shadow="none", pop=True, bottom=None):
        x, y, w, h = box
        vw, vh = W * s, H * s
        left = min(0, max(w - vw, w / 2 - FX * s)); top = min(0, max(h - vh, h * fy - FY * s))
        js.append(f'tl.set("#cam",{{left:{x},top:{y},width:{w},height:{h},borderRadius:"{radius}",border:"{border}",rotation:{rot},'
                  f'boxShadow:"{shadow}",maskImage:"{mask}",webkitMaskImage:"{mask}",scale:1,y:0,x:0}},{q(t)});'
                  f'tl.set("#cam > video",{{left:{left:.0f},top:{top:.0f},width:{vw:.0f},height:{vh:.0f}}},{q(t)});')
        if bottom: js.append(f'tl.set("#cam",{{borderBottomWidth:{bottom}}},{q(t)});')
        if pop: js.append(f'tl.fromTo("#cam",{{scale:.86}},{{scale:1,duration:.45,ease:"back.out(1.7)",immediateRender:false}},{q(t)});')

    def word(html, t, end, x, y, style, anim="up", center=False):
        n[0] += 1; wid = f"{cid}w{n[0]}"
        pos = "transform:translateX(-50%);text-align:center;" if center else ""
        front.append(f'<div id="{wid}" class="hw" style="left:{x:.0f}px;top:{y:.0f}px;{pos}{style}">{html}</div>')
        js.append(f'tl.set("#{wid}",{{autoAlpha:1}},{q(t)});tl.set("#{wid}",{{autoAlpha:0}},{q(end)});')
        if anim == "up": js.append(f'tl.fromTo("#{wid}",{{y:50,opacity:0}},{{y:0,opacity:1,duration:.4,ease:"power3.out",immediateRender:false}},{q(t)});')
        elif anim == "pop": js.append(f'tl.fromTo("#{wid}",{{scale:.4,opacity:0}},{{scale:1,opacity:1,duration:.35,ease:"back.out(2.2)",immediateRender:false}},{q(t)});')
        elif anim == "drop": js.append(f'tl.fromTo("#{wid}",{{y:-140,opacity:0}},{{y:0,opacity:1,duration:.55,ease:"bounce.out",immediateRender:false}},{q(t)});')
        return wid

    def photo(src, t, x, y, w, h, rot=0, style="", label=None):
        n[0] += 1; pid = f"{cid}p{n[0]}"
        lab = f'<span class="hnum" style="{font("body", 34)};color:{INK}">({label})</span>' if label else ""
        bgl.append(f'<div id="{pid}" class="hph" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;transform:rotate({rot}deg);{style}"><img src="{src}">{lab}</div>')
        js.append(f'tl.set("#{pid}",{{autoAlpha:1}},{q(t)});tl.set("#{pid}",{{autoAlpha:0}},{q(b)});'
                  f'tl.fromTo("#{pid}",{{scale:.5,opacity:0}},{{scale:1,opacity:1,duration:.35,ease:"back.out(1.8)",immediateRender:false}},{q(t)});')

    def px_for(text, want, role="head"): return X["fit"](re.sub(r"<[^>]+>", "", text), want, role=role)
    def width(text, px, role="head"): return X["width"](re.sub(r"<[^>]+>", "", text), px, role)
    def slot_x(x, text, px, role): return max(60, min(x, 1020 - width(text, px, role)))
    def take(k):
        if len(words) > k: print(f"head '{look}' at {a:.1f}s shows {k} words, dropped: {', '.join(w[0] for w in words[k:])}")
        return words[:k]
    SH = "0 30px 70px rgba(13,26,15,.22)"
    snd = {"window": "swish", "circle": "pop_pluck", "cloud": "whoosh_soft", "soft": None, "polaroid": "swish", "bigword": "whoosh_soft",
           "top": "slide", "collage": "pop_pluck", "pile": "swish", "around": "whoosh_soft", "picture": "pop_pluck"}[look]
    if snd: X["sfx"](snd, a - 0.05, -14)

    if look == "window":
        frame(a, (230, 820, 620, 860), 0.66, radius="46px", shadow=SH)
        for j, (t, tt, role) in enumerate(take(3)):
            role = role or ("head", "accent", "body")[j]
            px = px_for(t, (128, 116, 110)[j], role)
            if role == "accent": html = f'<span style="background:{HL};color:{MAIN};padding:0 24px 8px;border-radius:18px">{esc(t)}</span>'
            else: html = esc(t)
            word(html, tt, b, (540, 600, 470)[j], (300, 450, 600)[j], f"{font(role, px)};color:{INK};letter-spacing:-.04em;white-space:nowrap", center=True,
                 anim="pop" if j == 2 else "up")

    elif look == "circle":
        frame(a, (190, 820, 700, 700), 0.82, fy=0.44, radius="50%", border=f"12px solid {MAIN}")
        ws = take(3)
        for j, (t, tt, role) in enumerate(ws):
            last = j == len(ws) - 1 and len(ws) > 1
            role = role or ("accent", "head", "head")[j]
            if last:
                px = px_for(t, 84, role)
                word(f'<span style="background:{MAIN};color:{HL};padding:4px 30px 12px;border-radius:60px">{esc(t)}</span>', tt, b, 540, (290, 420, 590)[j],
                     f"{font(role, px)};letter-spacing:-.02em;white-space:nowrap", anim="pop", center=True)
            else:
                px = px_for(t, (104, 124, 124)[j], role)
                word(esc(t), tt, b, 540, (290, 420, 590)[j], f"{font(role, px)};color:{INK};letter-spacing:-.04em;white-space:nowrap", center=True)

    elif look == "cloud":
        X["files"]["img/head_cloud.svg"] = cloud_svg()
        frame(a, (110, 700, 860, 800), 0.86, fy=0.46, mask="url(img/head_cloud.svg)")
        slots = [(110, 290), (700, 400), (150, 520), (620, 1500)]
        for j, (t, tt, role) in enumerate(take(4)):
            role = role or ("body", "body", "accent", "body")[j]
            px = px_for(brk(t), 76, role)
            word(esc(brk(t)), tt, b, slot_x(slots[j][0], brk(t), px, role), slots[j][1], f"{font(role, px)};color:{INK};letter-spacing:-.02em;white-space:nowrap")

    elif look == "soft":
        X["files"]["img/head_soft.svg"] = SOFT_SVG
        frame(a, (130, 760, 820, 1040), 0.9, fy=0.42, mask="url(img/head_soft.svg)", pop=False)
        js.append(f'tl.fromTo("#cam",{{opacity:0,scale:1.06}},{{opacity:1,scale:1,duration:.6,ease:"power2.out",immediateRender:false}},{q(a)});'
                  f'tl.set("#cam",{{opacity:1}},{q(b)});')
        ws = take(3)
        big = max(range(len(ws)), key=lambda j: (len(ws[j][0]) <= 6, -len(ws[j][0]))) if ws else -1   # the shortest word (a number) goes big
        y = 300
        for j, (t, tt, role) in enumerate(ws):
            if j == big:
                px = px_for(t, 260, "head")
                word(esc(t), tt, b, 540, y, f"{font('head', px)};color:{SOFT if dark else MAIN};letter-spacing:-.05em;white-space:nowrap", anim="pop", center=True)
                y += px * 1.05
            else:
                role = role or ("accent" if j == 0 else "body"); px = px_for(t, 92 if j == 0 else 58, role)
                word(esc(t), tt, b, 540, y, f"{font(role, px)};color:{INK};opacity:.9;white-space:nowrap", center=True)
                y += px * 1.25

    elif look == "polaroid":
        frame(a, (262, 640, 556, 700), 0.72, fy=0.42, radius="6px", border="22px solid #fff", rot=-4, shadow="0 40px 80px rgba(0,0,0,.45)", bottom=150)
        ws = take(4)
        label, rest = (ws[0], ws[1:]) if len(ws) > 1 else (None, ws)
        if label:
            word(f'<span style="background:#fff;color:{MAIN};padding:6px 26px 12px;border-radius:14px">{esc(label[0])}</span>', a, b, 540, 330,
                 f"{font('head', px_for(label[0], 70))};letter-spacing:-.03em;white-space:nowrap", anim="none", center=True)
        cols = [MAIN, POP, SOFT]
        for j, (t, tt, role) in enumerate(rest):
            end = rest[j + 1][1] - 0.06 if j + 1 < len(rest) else b
            word(esc(t), tt, end, 540, 1218, f"{font(role or 'accent', px_for(t, 92, role or 'accent'))};color:{MAIN};transform:translateX(-50%) rotate(-4deg);white-space:nowrap",
                 anim="pop", center=True)
        changes = [a] + [tt for _, tt, _ in rest[1:]] if rest else [a]
        for j, t in enumerate(changes):
            if bgname == "duo":
                src = imgs[j % len(imgs)] if imgs else None
                if src: js.append(f'tl.set("#{cid}duo",{{backgroundImage:"url({src})",backgroundSize:"cover",backgroundPosition:"center"}},{q(t)});')
                else: X["need_duo"](); js.append(f'tl.set("#headDuoVid",{{left:{(-300, -900, -200)[j % 3]},top:{(-500, -1300, -1700)[j % 3]}}},{q(t)});')
                js.append(f'tl.set("#{cid}tint",{{backgroundColor:"{cols[j % 3]}"}},{q(t)});')
                js.append(f'tl.fromTo("#{cid}duo",{{scale:1.08}},{{scale:1,duration:.9,ease:"power2.out",immediateRender:false}},{q(t)});')
        if bgname == "duo" and not imgs:
            js.append(f'tl.set("#headDuoWrap",{{autoAlpha:1}},{q(a)});tl.set("#headDuoWrap",{{autoAlpha:0}},{q(b)});')

    elif look == "bigword":
        frame(a, (290, 820, 500, 660), 0.6, fy=0.42, radius="22px", shadow="0 30px 60px rgba(13,26,15,.3)")
        text = c.get("word") or (words[-1][0] if words else "")
        tt = next((w[1] for w in words if w[0] == text), words[-1][1] if words else a + 0.6)
        px = px_for(text.upper(), 250)
        wid = word(esc(text.upper()), a + 0.1, b, 540, 330, f"{font('head', px)};color:{INK};letter-spacing:-.05em;white-space:nowrap", anim="none", center=True)
        js.append(f'tl.fromTo("#{wid}",{{filter:"blur(34px)",scale:1.25,opacity:0}},{{filter:"blur(12px)",scale:1,opacity:.85,duration:.6,ease:"power2.out",immediateRender:false}},{q(a + 0.1)});'
                  f'tl.to("#{wid}",{{filter:"blur(0px)",opacity:1,duration:.35,ease:"power2.out"}},{q(max(tt, a + 0.75))});')

    elif look == "top":
        frame(a, (0, 0, W, 1020), 1.0, fy=0.62, pop=False)
        js.append(f'tl.fromTo("#cam",{{y:-120}},{{y:0,duration:.5,ease:"power3.out",immediateRender:false}},{q(a)});')
        slots = [(140, 1110), (500, 1230), (170, 1360), (560, 1480)]
        for j, (t, tt, role) in enumerate(take(4)):
            role = role or "body"; px = px_for(brk(t), 76, role)
            col = f"color:{POP if _lum(POP) < 0.6 else MAIN}" if j == 1 else f"color:{INK}"
            word(esc(brk(t)), tt, b, slot_x(slots[j][0], brk(t), px, role), slots[j][1], f"{font(role, px)};{col};letter-spacing:-.02em;white-space:nowrap", anim="drop")

    elif look == "collage":
        TILE = "box-shadow:0 14px 34px rgba(0,0,0,.14)"
        spots = [(70, 250, 290, 370), (395, 290, 270, 340), (700, 230, 310, 390), (680, 1060, 330, 420)]
        for j, src in enumerate(imgs[:4]):
            num = j + 1 if j < 3 else 5
            photo(src, a + 0.08 * j, *spots[j], style=TILE, label=num)
        frame(a + 0.24, (70, 700, 560, 720), 0.62, fy=0.42, shadow="0 14px 34px rgba(0,0,0,.18)")
        word("(4)", a + 0.24, b, 642, 700, f"{font('body', 34)};color:{INK}", anim="none")
        lines = [t for t, _, _ in take(2)]
        if lines:
            px = min(px_for(x, 74) for x in lines)
            word("<br>".join(esc(x) for x in lines), words[0][1], b, 668, 820, f"{font('head', min(px, 74))};color:{INK};letter-spacing:-.03em;line-height:.95")

    elif look == "pile":
        BW = "filter:grayscale(1) contrast(1.1);border:10px solid #fff;box-shadow:0 18px 40px rgba(0,0,0,.25)"
        spots = [(90, 330, -9), (640, 300, 7), (60, 900, 6), (660, 930, -6), (360, 230, 3), (380, 1080, -4)]
        for j, src in enumerate(imgs[:6]):
            photo(src, a + 0.07 * j, spots[j][0], spots[j][1], 360, 470, rot=spots[j][2], style=BW)
        frame(a + 0.45, (290, 520, 500, 700), 0.6, fy=0.42, border="12px solid #fff", rot=3, shadow="0 34px 70px rgba(0,0,0,.35)")
        ws = take(2)
        if ws:
            text = " ".join(t for t, _, _ in ws); px = px_for(text, 84)
            word(f'<span style="background:{HL};padding:4px 28px 12px;border-radius:20px">{esc(text)}</span>', ws[0][1], b, 540, 1450,
                 f"{font('head', px)};color:{MAIN};letter-spacing:-.04em;white-space:nowrap", anim="pop", center=True)

    elif look == "around":
        frame(a, (0, 0, W, H), 1.0, pop=False)
        js.append(f'tl.set("#cam > video",{{left:0,top:0,width:{W},height:{H}}},{q(a)});'
                  f'tl.fromTo("#cam",{{scale:1.12}},{{scale:1,duration:.5,ease:"power3.out",immediateRender:false}},{q(a)});')
        F = X["face"] or [304, 537, 462, 617]
        slots = [(110, max(230, F[1] - 210)), (600, max(330, F[1] - 100)), (110, min(1450, F[1] + F[3] + 150))]
        ws = take(3)
        for j, (t, tt, role) in enumerate(ws):
            role = role or "body"; px = px_for(brk(t), 78, role)
            if j == len(ws) - 1 and len(ws) > 1:
                html = f'<span style="background:{MAIN};color:{SOFT};padding:2px 26px 10px;border-radius:50px">{esc(brk(t))}</span>'
                st = f"{font(role, px)};letter-spacing:-.02em;white-space:nowrap"
            else:
                html = esc(brk(t)); st = f"{font(role, px)};color:#fff;letter-spacing:-.02em;white-space:nowrap;text-shadow:0 2px 14px rgba(0,0,0,.45)"
            word(html, tt, b, slot_x(slots[j][0], brk(t), px, role), slots[j][1], st, anim="pop" if j == len(ws) - 1 else "up")

    elif look == "picture":
        X["files"]["img/head_soft.svg"] = SOFT_SVG
        photo(imgs[0], a, 190, 230, 700, 460, style="-webkit-mask-image:url(img/head_soft.svg);mask-image:url(img/head_soft.svg);-webkit-mask-size:100% 100%;mask-size:100% 100%")
        frame(a, (190, 860, 700, 620), 0.62, fy=0.45, mask="url(img/head_soft.svg)")
        ws = take(3)
        for j, (t, tt, role) in enumerate(ws):
            end = ws[j + 1][1] - 0.04 if j + 1 < len(ws) else b
            px = px_for(t, 46)
            word(esc(t), a if j == 0 else tt, end, 540, 730, f"{font('head', px)};color:{MAIN};background:{HL};padding:10px 30px 14px;border-radius:60px;white-space:nowrap",
                 anim="pop", center=True)

    # hand the frame back
    js.append(f'tl.set("#cam",{{left:0,top:0,width:{W},height:{H},borderRadius:0,border:"0px solid transparent",rotation:0,boxShadow:"none",'
              f'maskImage:"none",webkitMaskImage:"none",scale:1,x:0,y:0,opacity:1}},{q(b)});'
              f'tl.set("#cam > video",{{left:0,top:0,width:{W},height:{H}}},{q(b)});')
    X["quiet"].append((a, b))
    X["zone"](cid, "подача голови", a, b, (0, 0, W, H), True, True)
