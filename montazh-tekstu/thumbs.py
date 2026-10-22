"""Прев'ю стилів: той самий текст на чорному фоні для кожного стилю -> thumbs.js і thumbs/*.jpg"""
import json, base64, os, io
from playwright.sync_api import sync_playwright
from PIL import Image
HERE=os.path.dirname(os.path.abspath(__file__)); os.makedirs(f"{HERE}/thumbs",exist_ok=True)
L=lambda **k: {"start":0,"end":10,"x":64,"w":952,"color":"#FFFFFF","weight":600,"plate":"none","in":{"type":"fade","dur":.3},"out":{"type":"none","dur":.1},"effect":{"type":"none"},**k}
P={"name":"preview","video":"","segments":[{"in":0,"out":10}],"accent":"#D2DB76","accent2":"#FFC3CC","ghost":"стиль","layers":[
 L(role="title",text="Такий торт _ти спечеш_\nуже після курсу",y=330,size=64,weight=700),
 L(role="sub",text="навіть якщо ніколи не пекла",y=540,size=44),
 L(role="item",text="✓ 5 тортів, які купують знову",y=720,size=38),
 L(role="item",text="✓ Конструктор на *25* смаків",y=800,size=38),
 L(role="num",text="4000+",y=930,size=120,weight=700),
 L(role="price",text="490 грн",y=1180,size=96,weight=700),
 L(role="old",text="~~1 960 грн~~",y=1200,size=56,x=480,w=500),
 L(role="cta",text="Отримати доступ →",y=1360,size=42,weight=700)]}
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=os.environ.get('CHROME') or None,args=["--allow-file-access-from-files"])
    pg=b.new_page(viewport={'width':1080,'height':1920})
    pg.add_init_script("window.PROJECT="+json.dumps(P,ensure_ascii=False)+";")
    pg.goto(f'file://{HERE}/editor.html?render=1'); pg.wait_for_function("window.renderReady===true")
    keys=pg.evaluate("Object.keys(PACKS)"); out={}
    for k in keys:
        pg.evaluate(f"(async k=>{{const p=PACKS[k]; P.accent=p.A||'#D2DB76'; P.accent2=p.B||'#FFC3CC'; await applyPack(k); await document.fonts.ready; applyAt(4);}})('{k}')")
        pg.wait_for_timeout(150)
        png=pg.screenshot(type="png"); im=Image.open(io.BytesIO(png)).convert("RGB").resize((360,640),Image.LANCZOS)
        im.save(f"{HERE}/thumbs/{k}.jpg",quality=82); bio=io.BytesIO(); im.save(bio,"JPEG",quality=72)
        out[k]="data:image/jpeg;base64,"+base64.b64encode(bio.getvalue()).decode()
    b.close()
open(f"{HERE}/thumbs.js","w").write("window.THUMBS="+json.dumps(out)+";\n"); print(len(out),"thumbs")
