"""Застосовує стиль до проєкту без відкриття редактора (той самий код, що й кнопка «Стиль ролика»).
python3 apply_pack.py project.json назва_стилю out.json [акцент] [другий_колір]
Назви стилів: python3 apply_pack.py --list"""
import json, os, sys
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None, args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1080, "height": 1920})
    if sys.argv[1] == "--list":
        pg.add_init_script("window.PROJECT={video:'',segments:[{in:0,out:1}],layers:[]};")
        pg.goto(f"file://{HERE}/editor.html?render=1"); pg.wait_for_function("window.renderReady===true")
        for k, n, d in pg.evaluate("Object.entries(PACKS).map(([k,p])=>[k,p.name,p.desc])"): print(f"{k:10} {n} — {d}")
        sys.exit()
    P = json.load(open(sys.argv[1])); key = sys.argv[2]
    pg.add_init_script("window.PROJECT=" + json.dumps({**P, "video": ""}, ensure_ascii=False) + ";")
    pg.goto(f"file://{HERE}/editor.html?render=1"); pg.wait_for_function("window.renderReady===true")
    A = sys.argv[4] if len(sys.argv) > 4 else None; B = sys.argv[5] if len(sys.argv) > 5 else None
    out = pg.evaluate("""async ([k,A,B])=>{ const p=PACKS[k]; P.accent=A||p.A||P.accent||'#D2DB76'; P.accent2=B||p.B||P.accent2||'#FFC3CC';
        await applyPack(k); await document.fonts.ready; return P; }""", [key, A, B])
    b.close()
out["video"] = P["video"]
json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1); print("ok", key, sys.argv[3])
