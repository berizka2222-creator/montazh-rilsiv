"""Рендер проєкту з редактора. Кадр складається в браузері повністю (відео + фони + блюр + картинки + текст),
тому результат збігається з прев'ю.
python3 render.py project.json [назва]"""
import base64, json, os, re, shutil, subprocess, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
pj = os.path.abspath(sys.argv[1]); P = json.load(open(pj))
name = sys.argv[2] if len(sys.argv) > 2 else "montazh"
out = os.path.join(HERE, "out"); os.makedirs(out, exist_ok=True)
work = os.path.join(out, name + "_work"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
FPS = 30
def sh(*a): subprocess.run(a, check=True)
src = P["video"] if os.path.isabs(P["video"]) else os.path.join(os.path.dirname(pj), P["video"])
segs = [s for s in P["segments"] if not s.get("removed")]
dur = sum(s["out"] - s["in"] for s in segs)
has_audio = bool(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                 "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip())

# 1. різання і склейка (H.264 + звук для фіналу)
COVER = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1"
fc, maps = [], ""
for i, s in enumerate(segs):
    fc.append(f"[0:v]trim={s['in']}:{s['out']},setpts=PTS-STARTPTS,{COVER}[v{i}]"); maps += f"[v{i}]"
    if has_audio: fc.append(f"[0:a]atrim={s['in']}:{s['out']},asetpts=PTS-STARTPTS[a{i}]"); maps += f"[a{i}]"
fc.append(f"{maps}concat=n={len(segs)}:v=1:a={1 if has_audio else 0}" + ("[cv][ca]" if has_audio else "[cv]"))
cut = os.path.join(work, "cut.mp4")
cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-filter_complex", ";".join(fc), "-map", "[cv]"]
if has_audio: cmd += ["-map", "[ca]", "-c:a", "aac", "-b:a", "160k"]
sh(*cmd, "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", cut)

# 2. копії для браузера: VP8, кожен кадр ключовий (точний перехід на будь-який кадр)
def to_webm(inp, outp, scale=None):
    vf = ["-vf", scale] if scale else []
    sh("ffmpeg", "-v", "error", "-y", "-i", inp, *vf, "-an", "-c:v", "libvpx", "-g", "1", "-b:v", "12M",
       "-deadline", "realtime", "-cpu-used", "8", outp)
cutw = os.path.join(work, "cut.webm"); to_webm(cut, cutw)
R = dict(P); R["video"] = "file://" + cutw; R["segments"] = [{"in": 0, "out": dur}]
if any(L.get("behind") for L in P["layers"]):   # вирізка людини для шарів «за людиною»
    rng = ",".join(f"{L['start']}-{L['end']}" for L in P["layers"] if L.get("behind"))   # тільки ті секунди, де шар за людиною
    mw = os.path.join(work, "matte.webm"); sh("python3", os.path.join(HERE, "make_matte.py"), cut, mw, "0", rng); R["matte"] = "file://" + mw
R["layers"] = []
for k, L in enumerate(P["layers"]):
    L = dict(L)
    if L.get("kind") == "media" and L.get("mtype") == "video":
        m = re.match(r"data:[^;]+;base64,(.*)", L["src"], re.S)
        raw = os.path.join(work, f"m{k}.bin")
        if m: open(raw, "wb").write(base64.b64decode(m.group(1)))
        else: raw = L["src"] if os.path.isabs(L["src"]) else os.path.join(os.path.dirname(pj), L["src"])
        mw = os.path.join(work, f"m{k}.webm"); to_webm(raw, mw, "scale='min(1080,iw)':-2"); L["src"] = "file://" + mw
    R["layers"].append(L)

# 3. покадрово в браузері
fr = os.path.join(work, "frames"); os.makedirs(fr)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME") or None,
                          args=["--allow-file-access-from-files", "--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 1080, "height": 1920})
    pg.add_init_script("window.PROJECT = " + json.dumps(R) + ";")
    pg.goto("file://" + os.path.join(HERE, os.environ.get("EDITOR","editor.html")) + "?render=1")
    pg.wait_for_function("window.renderReady === true"); pg.evaluate("document.fonts.ready"); pg.wait_for_timeout(500)
    for i in range(int(round(dur * FPS))):
        pg.evaluate(f"renderFrame({i / FPS + 0.001})")
        pg.screenshot(path=os.path.join(fr, f"{i:05d}.jpg"), type="jpeg", quality=95)
    b.close()

# 4. збірка зі звуком
v916 = os.path.join(out, name + "_9x16.mp4")
cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(fr, "%05d.jpg")]
if has_audio: cmd += ["-i", cut, "-map", "0:v", "-map", "1:a", "-c:a", "copy", "-shortest"]
sh(*cmd, "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", v916)
sh("ffmpeg", "-v", "error", "-y", "-i", v916, "-vf", "crop=1080:1350:0:285", "-c:v", "libx264", "-crf", "18",
   "-c:a", "copy", "-movflags", "+faststart", os.path.join(out, name + "_4x5.mp4"))
shutil.rmtree(work)
print("ok", v916, f"{dur:.1f}s")
