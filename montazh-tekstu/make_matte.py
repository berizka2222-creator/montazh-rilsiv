"""Вирізає людину з відео: на виході webm (VP9) з прозорістю — тільки людина, решта прозора.
python3 make_matte.py in.mp4 out.webm [ширина_виходу] [проміжки "1.2-3.4,7-8"]
Людину вирізає тільки в заданих проміжках (з запасом 0.2 с), решта кадрів — повністю прозорі й рахуються миттєво."""
import subprocess, sys, json, numpy as np
from PIL import Image, ImageFilter
from rembg import new_session, remove
inp, outp = sys.argv[1], sys.argv[2]
W0 = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "0" else 0
RNG = [tuple(map(float, r.split("-"))) for r in sys.argv[4].split(",")] if len(sys.argv) > 4 and sys.argv[4] else None
pr = json.loads(subprocess.run(["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,r_frame_rate","-of","json",inp],capture_output=True,text=True).stdout)["streams"][0]
w, h = pr["width"], pr["height"]
if W0: h = round(h * W0 / w / 2) * 2; w = W0
num, den = map(int, pr["r_frame_rate"].split("/")); fps = num / den
sess = new_session("u2net_human_seg")
dec = subprocess.Popen(["ffmpeg","-v","error","-i",inp,"-vf",f"scale={w}:{h}","-f","rawvideo","-pix_fmt","rgb24","-"],stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgba","-s",f"{w}x{h}","-r",f"{fps}","-i","-",
    "-c:v","libvpx-vp9","-pix_fmt","yuva420p","-auto-alt-ref","0","-g","1","-b:v","6M","-deadline","realtime","-cpu-used","8",outp],stdin=subprocess.PIPE)
prev = None; n = 0; sw = 320; sh = round(h * sw / w)
while True:
    buf = dec.stdout.read(w * h * 3)
    if len(buf) < w * h * 3: break
    t = n / fps
    if RNG and not any(a - .2 <= t <= b + .2 for a, b in RNG):
        enc.stdin.write(bytes(w * h * 4)); n += 1; prev = None; continue
    fr = Image.frombuffer("RGB", (w, h), buf)
    m = remove(fr.resize((sw, sh)), session=sess, only_mask=True)          # маска людини
    m = np.asarray(m, dtype=np.float32) / 255
    if prev is not None: m = 0.6 * m + 0.4 * prev                          # прибирає мерехтіння
    prev = m
    mk = Image.fromarray((np.clip((m - .25) / .5, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.5))
    rgba = fr.convert("RGBA"); rgba.putalpha(mk)
    enc.stdin.write(rgba.tobytes()); n += 1
enc.stdin.close(); enc.wait(); print("matte", n, "frames", outp)
