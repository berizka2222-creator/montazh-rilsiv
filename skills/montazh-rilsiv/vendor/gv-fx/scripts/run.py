#!/usr/bin/env python3
"""Effects from two talking-head packs (fx12.py: Алексей Гвоздарев, 12 effects; fx9.py: «9 эффектов», part 2) behind the same
call as vibha-fx/scripts/fx.py, so fx_pass.py can use them like any other fx card:

  run.py --plan plan.json in.mp4 out.mp4 --width 540

plan.json: {"effects": [{"fx": "gv-figma", "start": 0.4, "end": 2.1, "text"?: "...", ...options}]}
  gv-<name>  -> fx12.py  (orbit vertigo camzoom doodle framebreak ransom lens zoomblur figma bignum meme spring)
  e9-<name>  -> fx9.py   (dust lidar clones droste blueprint freeze circle slice wave)
Both packs draw at 1080x1920, 30 fps; the result is scaled to --width. «text» is turned into each effect's own field
(ransom lines, figma word, bignum text, spring rows), «images» (a folder) into a list of pictures, "#RRGGBB" into [r, g, b].
Fonts come from FX_FONTS (the brand's head / body / accent, set by fx_pass.py)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENG = {"gv": HERE / "fx12.py", "e9": HERE / "fx9.py"}
PICS = (".jpg", ".jpeg", ".png", ".webp")
# rembg keeps its model in ~/.u2net; onnxruntime can't open it under a non-Latin profile (C:\\Users\\Інна...)
if "U2NET_HOME" not in os.environ and not str(Path.home()).isascii():
    os.environ["U2NET_HOME"] = str((Path(os.environ.get("PUBLIC", "C:/Users/Public")) if os.name == "nt" else Path(tempfile.gettempdir())) / "montazh-rilsiv" / "u2net")


def rgb(v):
    if isinstance(v, str) and v.startswith("#") and len(v) == 7: return [int(v[i:i + 2], 16) for i in (1, 3, 5)]
    return v


def split(t): return [x.strip() for x in str(t).split("|") if x.strip()]


def pics(v):
    if isinstance(v, list): return v
    p = Path(str(v))
    return sorted(str(f) for f in p.iterdir() if f.suffix.lower() in PICS) if p.is_dir() else [str(p)]


def effect(d):
    eng, _, name = d["fx"].partition("-")
    e = {k: rgb(v) for k, v in d.items() if k not in ("fx", "start", "end", "text", "words", "images")}
    e.update(fx=name, t0=float(d["start"]), t1=float(d["end"]))
    t = d.get("text")
    if t:
        if name == "ransom": e.setdefault("lines", split(t))
        elif name == "figma": e.setdefault("word", str(t).replace("|", " "))
        elif name == "spring": e.setdefault("rows", split(t))
        elif name in ("bignum",): e.setdefault("text", str(t))
        elif name == "framebreak": e.setdefault("handle", str(t).lstrip("@"))
    if "handle" in e: e["handle"] = str(e["handle"]).lstrip("@")
    if name == "orbit" and d.get("images") and "images" not in d.get("opt", {}):
        e.setdefault("images", pics(d["images"])[:7])
    if name == "meme":
        img = e.get("image") or (pics(d["images"])[0] if d.get("images") else None)
        if not img: sys.exit("gv-meme: потрібна картинка мему (opt.image)")
        e["image"] = img
    for k in ("rows", "lines"):
        if isinstance(e.get(k), str): e[k] = split(e[k])
    return eng, e


def main(a):
    plan = json.load(open(a[a.index("--plan") + 1], encoding="utf-8"))
    rest = [x for i, x in enumerate(a) if x not in ("--plan", "--width") and a[i - 1] not in ("--plan", "--width")]
    src, dst = rest[0], rest[1]
    width = int(a[a.index("--width") + 1]) if "--width" in a else 1080
    fonts = json.loads(os.environ.get("FX_FONTS") or "{}")
    tmp = Path(tempfile.mkdtemp(prefix="gvfx_"))
    by = {}
    for d in plan["effects"]:
        eng, e = effect(d)
        if eng not in ENG: sys.exit(f"невідомий ефект {d['fx']}")
        by.setdefault(eng, []).append(e)
    cur = src
    for k, (eng, effs) in enumerate(by.items()):
        out = tmp / f"step{k}.mp4"
        p = {"input": str(cur), "output": str(out), "effects": effs}
        if eng == "gv" and fonts:
            p["fonts"] = {kk: fonts[v] for kk, v in (("display", "bold"), ("medium", "bold"), ("regular", "ui"), ("italic", "serif")) if fonts.get(v)}
        if eng == "e9" and fonts.get("ui"): p["font"] = fonts["ui"]
        pj = tmp / f"step{k}.json"; json.dump(p, open(pj, "w", encoding="utf-8"), ensure_ascii=False)
        r = subprocess.run([sys.executable, str(ENG[eng]), str(pj)])
        if r.returncode or not out.exists(): sys.exit(f"{ENG[eng].name} failed")
        cur = out
    h = width * 16 // 9 // 2 * 2
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(cur), "-vf", f"scale={width}:{h}", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "14", "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)], check=True)
    for f in tmp.iterdir(): f.unlink()
    tmp.rmdir()


if __name__ == "__main__":
    main(sys.argv[1:])
