"""Збирає автономну сторінку редактора (шрифти, прев'ю стилів, проєкт і прев'ю-відео всередині) — один HTML-файл.
python3 build_artifact.py project.json preview.mp4 out.html [matte.webm]
  preview.mp4 — легка копія відео (540×960), matte.webm — вирізка людини (необов'язково)."""
import base64, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
def b64(p): return base64.b64encode(open(p, 'rb').read()).decode()
MIME = {'.woff2': 'font/woff2', '.woff': 'font/woff', '.ttf': 'font/ttf', '.otf': 'font/otf'}
def inline_urls(css, base):
    """url(шлях) -> data:, якщо файл існує"""
    def sub(m):
        u = m.group(1).strip('\'"')
        if u.startswith('data:'): return m.group(0)
        p = u if os.path.isabs(u) else os.path.join(base, u)
        if not os.path.exists(p): return m.group(0)
        return f'url(data:{MIME.get(os.path.splitext(p)[1], "application/octet-stream")};base64,{b64(p)})'
    return re.sub(r'url\(([^)]+)\)', sub, css)

h = open(os.path.join(HERE, 'editor.html')).read()
h = re.sub(r'<!doctype html>\s*<html lang="uk"><head><meta charset="utf-8">', '', h)
h = h.replace('<title>Монтаж тексту · редактор</title>', '<title>Монтаж тексту на відео</title>\n<meta name="claude:viewport-fit-sides" content="cover">')
brand = os.path.join(HERE, 'brand', 'fonts.css')
bcss = inline_urls(open(brand).read(), os.path.dirname(brand)) if os.path.exists(brand) else ''
h = h.replace('<link rel="stylesheet" href="brand/fonts.css">', '<style>' + bcss + '</style>')
h = re.sub(r'<style id="xfonts">(.*?)</style>', lambda m: '<style>' + inline_urls(m.group(1), HERE) + '</style>', h, flags=re.S)
h = h.replace('<style>\n:root{', '<style>\n:root{color-scheme:dark;', 1)
h = h.replace('</style></head>\n<body>', '''html,body{height:100%}
body{height:100%!important;padding-left:max(0px,env(safe-area-inset-left,0px));padding-right:max(0px,env(safe-area-inset-right,0px))}
@media (max-width:820px){body{grid-template-rows:auto auto auto}main{grid-template-columns:1fr}#stageWrap{height:62vh}#insp{border-left:0;border-top:1px solid var(--line)}footer{height:300px}header{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}body{overflow:auto}}
</style>\n''', 1)
h = h.replace('</body></html>', '')
FL = open(os.path.join(HERE, 'fontlib.js')).read()
FL = re.sub(r'"(fontlib/[^"]+\.woff2)"', lambda m: '"data:font/woff2;base64,' + b64(os.path.join(HERE, m.group(1))) + '"', FL)
h = h.replace('<script src="fontlib.js"></script>', '<script>' + FL + '</script>', 1)
h = h.replace('<script src="thumbs.js"></script>', '<script>' + open(os.path.join(HERE, 'thumbs.js')).read() + '</script>', 1)
assert 'src="fontlib.js"' not in h and 'src="thumbs.js"' not in h

P = json.load(open(sys.argv[1])); P['video'] = 'data:video/mp4;base64,' + b64(sys.argv[2])
if len(sys.argv) > 4: P['matte'] = 'data:video/webm;base64,' + b64(sys.argv[4])
else: P.pop('matte', None)
h = h.replace('<script>\n/* ======== ДАНІ', '<script>window.PROJECT=' + json.dumps(P, ensure_ascii=False) + ';</script>\n<script>\n/* ======== ДАНІ', 1)
assert 'window.PROJECT' in h
open(sys.argv[3], 'w').write(h); print(round(len(h) / 1e6, 2), "MB")
