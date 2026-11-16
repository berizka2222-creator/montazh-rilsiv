#!/usr/bin/env python3
"""Fast final (2026-11-16: a 99 s reel took 40+ min to render and ran an 8 GB Mac out of memory).

The old final made headless Chrome screenshot EVERY frame of the reel with the 1080p video injected as PNG frames:
~3000 frames at 1-2 s each, 40+ min, all the memory of an 8 GB Mac. Here Chrome draws only the graphics, on a
transparent page (no video injection, so static frames are deduplicated), and ffmpeg puts the person's video under them:

  1. proj_ov/  = proj/ with the camera video removed, a transparent background, no <audio>
  2. HyperFrames renders it to overlay.mov (ProRes 4444 with alpha, 1080x1920)
  3. ffmpeg: master.mp4 -> the same punch-in zooms the page did (#cam scale, origin 50% 38%, power3.out, lanczos)
     -> glass cards get their backdrop blur (blur 26px + saturate 1.5 of the video under them, masked by the card)
     -> overlay.mov on top -> the voice + the sound effects -> final.mp4 (one encode of the person's video, on the video chip)

Her video is encoded once from master.mp4 (in the old path it went master -> PNG -> screenshot -> x264), so the
picture is at least as clean. Anything this path can't reproduce exactly (camera moves other than punch-ins, head
layouts, «за мною» cut-outs, blend modes, other backdrop blurs, #bg touched by the timeline) -> exit 2 and render.sh
falls back to the full Chrome render.

Speed (8 GB M1, 99 s reel, 2026-11-16): old full Chrome final 40+ min (and out of memory); this path 76 s after «фінал»,
because render.sh renders the graphics (~2 min) in the background right after each draft, while they watch it.
Same graphics -> overlay.mov is reused (overlay.key = hash of the page), so the final only composes.

Usage: fast_final.py <reel> [--check] [--proj proj_full] [--overlay-only]
  --check          only say whether the fast path applies (exit 0 / 2)
  --overlay-only   render the graphics (overlay.mov) and stop: the draft's background pre-render
"""
import json, os, re, shutil, subprocess, sys, time
from pathlib import Path

reel = Path(sys.argv[1]).expanduser().resolve()
CHECK = "--check" in sys.argv
proj = reel / (sys.argv[sys.argv.index("--proj") + 1] if "--proj" in sys.argv else "proj")
ONLY_OV = "--overlay-only" in sys.argv   # render.sh runs this right after a draft: the final then only composes
html = (proj / "index.html").read_text()
W, H = 1080, 1920
FPS = 30


def no(why):
    print(f"fast final: not for this reel ({why}) -> full Chrome render")
    sys.exit(2)


# ---- 1. can the fast path reproduce this reel exactly? ----------------------------------------------------------
m = re.search(r'<video id="bg"[^>]*src="([^"]+)"[^>]*></video>', html)
if not m: no("no camera video")
SRC = proj / m.group(1)
if not SRC.exists(): no(f"{SRC.name} missing")
if 'data-width="1080"' not in html or 'data-height="1920"' not in html: no("not a 1080x1920 stage")
script = html[html.rfind("<script>"):]
PUNCH = re.compile(r'tl\.to\("#cam",\{scale:([\d.]+),duration:([\d.]+),ease:"power3\.out",overwrite:"auto"\},([\d.]+)\);')
punches = [(float(t), float(z), float(d)) for z, d, t in PUNCH.findall(script)]
if script.count('"#cam"') != len(punches): no("camera moves other than punch-ins")
if re.search(r'"#bg"|#bg\b', script): no("the timeline touches the camera video")
for div in ("headBg",):   # #behind/#subj/#back live inside #cam: the page keeps their zoom and cut-outs itself
    mm = re.search(rf'<div id="{div}">(.*?)</div>', html, re.S)
    if mm and mm.group(1).strip(): no("head layout (a second copy of the video)")
body = html[html.find("<body>"):]
if "mix-blend-mode" in body: no("blend modes need the video under them")
css = html[:html.find("</style>")]
if [x for x in re.findall(r"backdrop-filter:[^;]+", css) if "blur(26px) saturate(1.5)" not in x] or "backdrop-filter" in body:
    no("a backdrop blur this script doesn't know")
dur = float(re.search(r'id="stage"[^>]*data-duration="([\d.]+)"', html).group(1))

# glass cards: the zone id of each .glass element's card -> (start, end, box)
zones = {z["id"]: z for z in json.load(open(reel / "safezones.json"))["items"]} if (reel / "safezones.json").exists() else {}
glass = []
for g in re.finditer(r'class="[^"]*\bglass\b', body):
    ids = re.findall(r'<div id="([a-z]\w*)"', body[:g.start()])
    z = zones.get(ids[-1]) if ids else None
    if not z: no("a glass card without a zone")
    x, y, w, h = z["box"]; P = 40   # room for the pop-in scale and the soft shadow
    x0, y0 = max(0, x - P), max(0, y - P); x1, y1 = min(W, x + w + P), min(H, y + h + P)
    glass.append((z["start"] - 0.05, z["end"] + 0.25, (x0 - x0 % 2, y0 - y0 % 2, (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2)))
if CHECK:
    print(f"fast final: ok ({len(punches)} punch-ins, {len(glass)} glass cards)"); sys.exit(0)

t0 = time.time()
# ---- 2. the graphics alone, on a transparent page -------------------------------------------------------------------
ov = reel / "proj_ov"
shutil.rmtree(ov, ignore_errors=True); ov.mkdir()
for p in proj.iterdir():
    if p.name in ("index.html", SRC.name): continue
    (ov / p.name).symlink_to(p)
page = html.replace(m.group(0), '<div id="bg"></div>')
page = re.sub(r"<audio[^>]*>(</audio>)?", "", page)
page = page.replace("</style>", "html,body,#stage,#scaler,#cam{background:transparent!important}"
                    "#camBg,#headBg{display:none!important}</style>", 1)
(ov / "index.html").write_text(page)
import hashlib
key = hashlib.sha1(page.encode()).hexdigest()[:12]
mov = reel / "overlay.mov"; keyf = reel / "overlay.key"
cached = mov.exists() and keyf.exists() and keyf.read_text().strip() == key
try: cur = int(subprocess.run(["ps", "-o", "nice=", "-p", str(os.getpid())], capture_output=True, text=True).stdout.strip() or 0)
except Exception: cur = 0   # Windows: no ps -o (and no nice: _win.py drops it)
ni = max(0, min(15, 19 - cur))
r = subprocess.CompletedProcess([], 0) if cached else subprocess.run(["nice", "-n", str(ni), "npx", "-y", "hyperframes@0.8.145", "render", str(ov), "--format", "mov",
                    "--resolution", "portrait", "--workers", os.environ.get("REEL_OV_WORKERS", "2"), "--no-low-memory-mode",
                    "-o", str(mov), "--quiet"])
if r.returncode or not mov.exists(): no("the graphics pass failed")
keyf.write_text(key)   # same graphics next time (a re-compose, a new encoder) -> no Chrome at all
t1 = time.time(); print(f"fast final: graphics {t1 - t0:.0f}s" + (" (ready from the draft)" if cached else ""))
if ONLY_OV: shutil.rmtree(ov, ignore_errors=True); sys.exit(0)

# ---- 3. the person's video + zooms + glass blur + graphics + sound -> final.mp4 --------------------------------------------
def zoom_expr():
    z = 1.0
    pieces = []
    for t, zt, d in sorted(punches):
        pieces.append((t, d, z, zt)); z = zt
    expr = f"{z}"                                    # after the last punch
    for t, d, za, zb in reversed(pieces):            # nest from the end: before t -> previous level
        ramp = f"({za}+({zb}-{za})*(1-pow(1-(it-{t})/{d},3)))"
        expr = f"if(lt(it,{t}),{za},if(lt(it,{t + d}),{ramp},{expr}))"
    return expr or "1"

Z = zoom_expr() if punches else "1"
# zoompan, not scale(eval=frame)+crop: crop keeps the first frame's size in its x/y, so a growing frame slid to the
# corner (caught on the 2026-11-16 test: 18 dB against the page's zoom). zoompan matches the page within half a pixel.
f = [f"[0:v]setpts=PTS-STARTPTS,zoompan=z='{Z}':x='(iw-iw/zoom)*0.5':y='(ih-ih/zoom)*0.38':d=1:s={W}x{H}:fps={FPS},"
     f"setpts=PTS-STARTPTS,setsar=1[v0]"]
f.append(f"[1:v]setpts=PTS-STARTPTS,split={len(glass) + 1}" + "".join(f"[o{i}]" for i in range(len(glass) + 1)))
last = "v0"
for i, (a, b, (x, y, w, h)) in enumerate(glass):
    f.append(f"[{last}]split[g{i}a][g{i}b]")
    f.append(f"[g{i}b]crop={w}:{h}:{x}:{y},gblur=sigma=26:steps=3,eq=saturation=1.5,format=yuva420p[bl{i}]")
    f.append(f"[o{i + 1}]crop={w}:{h}:{x}:{y},alphaextract,lut=y='clip(val*255/90,0,255)',format=gray[mk{i}]")
    f.append(f"[bl{i}][mk{i}]alphamerge[blm{i}]")
    f.append(f"[g{i}a][blm{i}]overlay={x}:{y}:enable='between(t,{a:.3f},{b:.3f})'[gv{i}]")
    last = f"gv{i}"
f.append(f"[{last}][o0]overlay=0:0:format=auto,format=yuv420p[v]")

sfx = re.findall(r'<audio id="\w+" src="([^"]+)" data-start="([\d.]+)" data-duration="([\d.]+)"[^>]*data-volume="([\d.]+)"', html)
inputs = ["-i", str(SRC), "-i", str(mov)]
for k, (src, st, du, vol) in enumerate(sfx):
    inputs += ["-i", str(proj / src)]
    f.append(f"[{k + 2}:a]atrim=0:{du},volume={vol},adelay={int(float(st) * 1000)}:all=1[s{k}]")
amix = "[0:a]" + "".join(f"[s{k}]" for k in range(len(sfx)))
f.append(f"{amix}amix=inputs={len(sfx) + 1}:duration=first:normalize=0[a]" if sfx else "[0:a]anull[a]")

def encoder():
    """The computer's video chip when it has one: Mac VideoToolbox, Windows NVIDIA / Intel / AMD (each tried on a tiny
    test clip, since ffmpeg lists encoders the machine can't run). 28 Mbit/s: on a face it can't be told apart from
    x264 CRF 14 (2026-11-16) and encodes ~4x faster. No chip -> x264 veryfast CRF 14 (REEL_ENC=x264 forces it)."""
    want = os.environ.get("REEL_ENC", "auto")
    br = os.environ.get("REEL_HW_BITRATE", "28M")
    hw = {"h264_videotoolbox": ["-b:v", br, "-maxrate", "40M", "-bufsize", "56M"],
          "h264_nvenc": ["-preset", "p5", "-rc", "vbr", "-b:v", br, "-maxrate", "40M", "-bufsize", "56M"],
          "h264_qsv": ["-preset", "medium", "-b:v", br, "-maxrate", "40M", "-bufsize", "56M"],
          "h264_amf": ["-quality", "quality", "-rc", "vbr_peak", "-b:v", br, "-maxrate", "40M", "-bufsize", "56M"]}
    order = (["h264_videotoolbox"] if sys.platform == "darwin" else ["h264_nvenc", "h264_qsv", "h264_amf"]) if want == "auto" else [want]
    for enc in order:
        if enc not in hw: break
        ok = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:d=0.2", "-c:v", enc,
                             *hw[enc], "-f", "null", "-"], capture_output=True).returncode == 0
        if ok:
            print(f"fast final: encoder {enc}"); return ["-c:v", enc, *hw[enc], "-profile:v", "high"]
    print("fast final: encoder libx264 (no video chip ffmpeg can use)")
    return ["-c:v", "libx264", "-preset", os.environ.get("REEL_PRESET", "veryfast"), "-crf", os.environ.get("REEL_CRF", "14"), "-profile:v", "high"]


out = reel / "final.mp4"
cmd = ["nice", "-n", str(ni), "ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(f),
       "-map", "[v]", "-map", "[a]", "-t", f"{dur}", "-r", str(FPS),
       *encoder(),
       "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
       "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", str(out)]
r = subprocess.run(cmd)
if r.returncode or not out.exists(): no("ffmpeg compose failed")
shutil.rmtree(ov, ignore_errors=True)   # overlay.mov stays as the cache (overlay.key)
print(f"fast final: compose {time.time() - t1:.0f}s, total {time.time() - t0:.0f}s -> {out}")
