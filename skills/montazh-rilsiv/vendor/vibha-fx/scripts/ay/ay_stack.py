# ay-head-stack: paper labels drop one by one and stack up on top of her head (a list of things, «все це на мені»).
# text = "слово::підпис|слово::підпис|..." (підпис optional, small italic). Up to ~7 labels.

def _ay_label(word, sub, size, bg, fg, subfg):
    k = 2; f1 = ay_font('hx', size * k); f2 = ay_font('i', size * 0.62 * k)
    w1 = f1.getlength(word); w2 = f2.getlength(sub) if sub else 0
    padx, pady = size * 0.42 * k, size * 0.26 * k; gap = size * 0.22 * k if sub else 0
    asc = f1.getmetrics()[0]
    W = int(w1 + gap + w2 + 2 * padx); H = int(size * 1.0 * k + 2 * pady)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, W - 1, H - 1], int(size * 0.12 * k), fill=tuple(bg) + (255,))
    # paper fibres: a faint darker edge at the bottom
    d.rounded_rectangle([0, H - int(size * 0.07 * k), W - 1, H - 1], int(size * 0.1 * k), fill=tuple(int(v * 0.9) for v in bg) + (255,))
    base = pady + size * 0.82 * k
    d.text((padx, base), word, font=f1, fill=tuple(fg) + (255,), anchor='ls')
    if sub: d.text((padx + w1 + gap, base), sub, font=f2, fill=tuple(subfg) + (255,), anchor='ls')
    im = im.resize((W // k, H // k), Image.LANCZOS)
    return shadowed(im, blur=max(4, int(size * 0.18)), dy=int(size * 0.12), alpha=110)


@effect('ay-head-stack', 'labels drop one by one and stack up on top of your head')
def fx_ay_head_stack(c, e):
    items = [(p.split('::') + [''])[:2] for p in ay_words(e, default='таргет::meta|креативи::рілс|аналітика::звіт|воронка::ліди|оффер::ціна')]
    n = len(items); W, H = c.W, c.H
    size = W * float(e.o.get('size', 0.06))
    looks = [(AY['cream'], AY['ink'], AY['pink_dk']), (AY['lime'], AY['ink'], AY['olive']), (AY['pink'], AY['ink'], AY['pink_dk'])]
    labels = cached(e, 'lab', lambda: [_ay_label(w, s, size, *looks[(j if e.o.get('colors', 'mix') == 'mix' else 0) % 3]) for j, (w, s) in enumerate(items)])
    every = float(e.o.get('every', min(0.32, max(0.16, (e.d - 0.6) / max(1, n)))))
    out = fade(c, e, 0.22)
    rnd = random.Random(7)
    rots = cached(e, 'rot', lambda: [rnd.uniform(-5.5, 5.5) for _ in range(n)])
    offs = cached(e, 'off', lambda: [rnd.uniform(-0.09, 0.09) for _ in range(n)])
    top = c.fy - c.fw * 0.95          # the crown of the head
    y = top
    for j, lab in enumerate(labels):
        t0 = 0.08 + j * every
        if c.lt < t0: break
        p = (c.lt - t0) / 0.34
        fall = 1 - ease_out(clamp(p))                    # drops from above
        sq = math.sin(clamp(p) * math.pi) * 0.06 if p < 1 else 0   # a little squash on landing
        cy = y - lab.height * 0.36
        x = c.fx + offs[j] * W
        place(c, lab, x, cy - fall * H * 0.35, 1 + sq, rots[j] * (0.4 + 0.6 * ease_out(clamp(p))), out * clamp(p * 4))
        y -= lab.height * 0.62
