#!/usr/bin/env python3
"""Check the cut before any render: hear master.mp4 again, re-time captions and cards to it, and list what to fix.
  - re-times every caption word, card and punch-in in edit.json to the words as heard in master.mp4
  - JOIN: the words heard around each join (a clipped, doubled or stray word shows up here)
  - MISSING: speech heard in the cut that has no caption
  - CHECK: caption words that don't match what was heard (misheard words like "донути" for "донести")
Usage: python3 precheck.py <reel-folder>     (after cut.py and once edit.json exists; writes master_transcript.json)
Fix what it lists in edit.json (or the edl + cut.py for a bad join), then render."""
import bisect, difflib, json, os, re, subprocess, sys
from pathlib import Path

reel = Path(sys.argv[1]).expanduser()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pacing import pacing
SPEED = pacing(json.load(open(Path(os.environ.get("REELS_HOME", "~/reels")).expanduser() / "brand.json")))["speed"]
norm = lambda s: re.sub(r"[\W_]", "", s.lower())
# the cut didn't change since the last transcription (cut.py's .master_key, master.mp4 older than the transcript): reuse it
_mk, _mt = reel / ".master_key", reel / "master_transcript.json"
_tk = reel / ".master_transcript_key"
if not (_mt.exists() and _mk.exists() and _tk.exists() and _tk.read_text() == _mk.read_text() and _mt.stat().st_mtime >= (reel / "master.mp4").stat().st_mtime):
    subprocess.run([sys.executable, str(HERE / "transcribe.py"), str(reel / "master.mp4"), str(_mt)], check=True)
    if _mk.exists(): _tk.write_text(_mk.read_text())
else: print("master_transcript.json is up to date (same cut): not transcribing again")
mt = json.load(open(reel / "master_transcript.json"))
ed = json.load(open(reel / "edit.json"))
edl = json.load(open(reel / "edl.json"))
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(reel / "master.mp4")],
                           capture_output=True, text=True).stdout)

# --- re-time: match caption words to heard words in order, interpolate the rest
cw = [w for c in ed["captions"] for w in c["words"]]
A, B = [norm(w["text"]) for w in cw], [norm(w["text"]) for w in mt]
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
m = {blk.a + k: blk.b + k for blk in sm.get_matching_blocks() for k in range(blk.size)}
pairs = sorted((cw[k]["t"], mt[j]["start"]) for k, j in m.items())
if len(pairs) < max(5, len(cw) // 3): sys.exit(f"only {len(pairs)} of {len(cw)} caption words matched the cut: captions and master.mp4 don't belong together")
xs, ys = [p[0] for p in pairs], [p[1] for p in pairs]
def remap(t):
    i = bisect.bisect_left(xs, t)
    if i <= 0: return max(0.0, ys[0] + t - xs[0]) if t > xs[0] else t
    if i >= len(xs): return ys[-1] + t - xs[-1]
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (t - x0) * (y1 - y0) / (x1 - x0) if x1 > x0 else y0
shift = max((abs(mt[j]["start"] - cw[k]["t"]) for k, j in m.items()), default=0)
for k, w in enumerate(cw): w["t"] = round(mt[m[k]]["start"] if k in m else remap(w["t"]), 3)
prev = -1.0
for w in cw:                                               # keep word order strictly increasing
    if w["t"] <= prev: w["t"] = round(prev + 0.05, 3)
    prev = w["t"]
caps = ed["captions"]
for c in caps: c["start"] = c["words"][0]["t"]
for i, c in enumerate(caps):
    nxt = caps[i + 1]["start"] if i + 1 < len(caps) else c["words"][-1]["t"] + 0.6
    c["end"] = round(min(max(c["start"] + 0.12, nxt), dur - 0.05), 3)
for c in ed.get("cards", []):
    if c.get("start", 0) > 0.05: c["start"] = round(remap(c["start"]), 3)
    if c.get("end"): c["end"] = round(min(remap(c["end"]), dur - 0.05), 3)
ed["punch"] = [[round(remap(p[0]), 3), p[1]] if isinstance(p, list) else round(remap(p), 3) for p in ed.get("punch", [])]
json.dump(ed, open(reel / "edit.json", "w"), ensure_ascii=False, indent=1)
print(f"re-timed {len(cw)} caption words ({len(m)} matched to the cut; largest correction {shift:.2f} s), cards and punch-ins")

# --- report
issues = 0
t, joins = 0.0, []
for a, b in edl["keep"][:-1]:
    t += (b - a) / SPEED; joins.append(t)
for jt in joins:
    near = [x["text"] for x in mt if jt - 1.5 < x["start"] < jt + 1.5]
    print(f"JOIN {jt:6.2f}s: {' '.join(near)}")
for op, a1, a2, b1, b2 in sm.get_opcodes():
    heard = " ".join(x["text"] for x in mt[b1:b2]); cap = " ".join(w["text"] for w in cw[a1:a2])
    if op == "insert" and b2 - b1 >= 2:
        issues += 1; print(f"MISSING {mt[b1]['start']:6.2f}s: heard \"{heard}\" with no caption")
    elif op == "replace":
        issues += 1; print(f"CHECK   {mt[b1]['start']:6.2f}s: caption \"{cap}\" / heard \"{heard}\"")
print(f"{issues} caption issue(s) to look at; read every JOIN line for clipped or doubled words")
