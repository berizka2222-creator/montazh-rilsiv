#!/usr/bin/env python3
"""Check an ay-* effect on a test clip, in the person's brand fonts / colours (the same env fx_pass gives the engine).

  .venv/bin/python scripts/ay_check.py ay-banknote                       # stills sheet -> ~/reels/_aytest/out/ay-banknote.jpg
  .venv/bin/python scripts/ay_check.py ay-banknote --opt '{"to": "12 400"}' --start 0.5 --end 3.5 --n 8
  .venv/bin/python scripts/ay_check.py ay-banknote --video                # also renders ~/reels/_aytest/out/ay-banknote.mp4
  --clip <file> to use another talking-head clip, --width 540 for a faster rough look.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VD = HERE.parent
SKILL = VD.parent.parent
sys.path.insert(0, str(SKILL / 'scripts'))
import fx_pass  # noqa: E402  (brand_env / models_env)

ap = argparse.ArgumentParser()
ap.add_argument('fx'); ap.add_argument('--opt', default='{}'); ap.add_argument('--text')
ap.add_argument('--start', type=float, default=0.5); ap.add_argument('--end', type=float, default=3.5)
ap.add_argument('--n', type=int, default=8); ap.add_argument('--times'); ap.add_argument('--width', type=int, default=1080)
ap.add_argument('--clip', default=str(Path('~/reels/_aytest/clip.mp4').expanduser())); ap.add_argument('--video', action='store_true')
ap.add_argument('--out', default=str(Path('~/reels/_aytest/out').expanduser()))
a = ap.parse_args()

out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
py = VD / '.venv' / 'bin' / 'python'
env = {**os.environ, **fx_pass.brand_env(py), **fx_pass.models_env(), 'PYTHONUTF8': '1'}
card = {'fx': a.fx, 'start': a.start, 'end': a.end, **json.loads(a.opt)}
if a.text is not None: card['text'] = a.text
pj = out / f'{a.fx}.plan.json'; json.dump({'effects': [card]}, open(pj, 'w', encoding='utf-8'), ensure_ascii=False)
d = a.end - a.start
times = [float(x) for x in a.times.split(',')] if a.times else [round(a.start + 0.04 + d * (i + 0.5) / a.n * 0.98, 2) for i in range(a.n)]
tmp = out / f'_{a.fx}'; tmp.mkdir(exist_ok=True)
for f in tmp.glob('*.png'): f.unlink()
r = subprocess.run([str(py), str(HERE / 'fx.py'), '--plan', str(pj), a.clip, str(tmp / 's.png'), '--still', ','.join(map(str, times)),
                    '--width', str(a.width)], env=env, capture_output=True, text=True)
if r.returncode: sys.exit(r.stdout[-1500:] + r.stderr[-3000:])
pngs = sorted(tmp.glob('*.png'))
if len(pngs) == 1: pngs[0].rename(tmp / f's_{times[0]:.2f}.png'); pngs = sorted(tmp.glob('*.png'))
# contact sheet: 4 per row, 360 px wide each, with the time under each frame
cols = min(4, len(pngs)); rows = (len(pngs) + cols - 1) // cols
flt = f"scale=360:-1,drawbox=y=ih-28:h=28:w=iw:color=black@0.6:t=fill"
inputs = sum([['-i', str(p)] for p in pngs], [])
lay = '|'.join(f'{(i % cols) * 360}_{(i // cols) * 640}' for i in range(len(pngs)))
fc = ';'.join(f'[{i}:v]scale=360:640[v{i}]' for i in range(len(pngs))) + ';' + ''.join(f'[v{i}]' for i in range(len(pngs))) + \
     f'xstack=inputs={len(pngs)}:layout={lay}:fill=black[o]'
sheet = out / f'{a.fx}.jpg'
if len(pngs) == 1:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(pngs[0]), '-vf', 'scale=540:-1', str(sheet)], check=True)
else:
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', fc, '-map', '[o]', '-q:v', '3', str(sheet)], check=True)
print('sheet', sheet, '| times', times)
if a.video:
    mp4 = out / f'{a.fx}.mp4'
    r = subprocess.run([str(py), str(HERE / 'fx.py'), '--plan', str(pj), a.clip, str(mp4), '--width', str(a.width)], env=env, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stderr[-3000:])
    print('video', mp4)
