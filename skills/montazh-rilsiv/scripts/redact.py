#!/usr/bin/env python3
"""Hide client data in a screen recording or a clip: blur / pixelate boxes, found on screen or given by hand.
Idea and filters from ffmpeg-skill's redact.py (MIT, github.com/kajisho5/ffmpeg-skill); added here: several boxes,
each only for the seconds it is on screen, and finding them by reading the screen (macOS Vision OCR, on the Mac).

  find:   python3 redact.py find <video> [--words "Квітка" "Glamour Studio" ...] [--no-auto] [--step 0.5]
          reads the screen every --step s and lists what it would hide -> <video>.redact.json + a contact sheet
          <video>.redact.jpg (red boxes): LOOK at it, remove false hits / add misses in the json, then apply.
          Auto patterns (on by default): e-mails, phone numbers, ad account / pixel / business IDs (act_…, 6+ digits),
          sums of money (12 500 ₴, $1,200, 3 400 грн), card-like numbers, @handles that aren't hers (brand.json "handle"
          is kept). --words: client names, ad set / campaign names, anything else she names (case- and ending-tolerant).
  apply:  python3 redact.py apply <video> <out.mp4> [--json <video>.redact.json] [--mode blur|pixelate]
  box:    python3 redact.py apply <video> <out.mp4> --box x,y,w,h[,from,to] [--box ...]   (pixels of the source frame;
          from/to in seconds, whole clip when left out)
Boxes are padded by 6 px and held 0.3 s longer on each side, so a scroll between two reads stays covered.
Never hide by guessing: an item the sheet doesn't show covered is not covered. Audio and the rest of the frame stay as they are."""
import argparse, json, os, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()

AUTO = [
    ("email", r"[\w.+-]+@[\w-]+\.[\w.]+"),
    ("phone", r"(?:\+?\d[\d\s().-]{8,}\d)"),
    ("account id", r"\b(?:act_)?\d{6,}\b"),
    ("money", r"(?:[$€£₴]\s?\d[\d\s.,]*\d|\d[\d\s.,]*\d\s?(?:₴|грн|uah|\$|usd|€|eur|zł|pln))"),
    ("handle", r"@[A-Za-z0-9_.]{3,}"),
]


def swift_tool(name):
    src, exe = HERE / f"{name}.swift", Path(f"~/.cache/reel-editor/{name}").expanduser()
    if not exe.exists() or exe.stat().st_mtime < src.stat().st_mtime:
        exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", "-o", str(exe), str(src)], check=True, capture_output=True)
    return exe


def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:stream_side_data=rotation:format=duration", "-of", "json", str(p)],
                                  capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]; w, h = int(s["width"]), int(s["height"])
    rot = next((int(x["rotation"]) for x in s.get("side_data_list", []) or [] if "rotation" in x), 0)
    if rot in (90, -90, 270, -270): w, h = h, w
    return w, h, float(j["format"]["duration"])


def ocr(video, step):
    """[(t, [(line_text, line_box, [(word, box), ...]), ...]), ...] with boxes in 0..1"""
    exe = swift_tool("ocr")
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{step}", "-q:v", "2", f"{d}/f%05d.jpg"], check=True)
        frames = sorted(Path(d).glob("f*.jpg"))
        out = subprocess.run([str(exe)], input="\n".join(map(str, frames)) + "\n", capture_output=True, text=True, check=True).stdout
    res, cur = [], None
    for line in out.split("\n"):
        if line.startswith("#"):
            cur = (int(line[1:]) * step + step / 2, []); res.append(cur); continue
        if "\t" not in line or cur is None: continue
        geo, text = line.split("\t", 1)
        if geo.startswith("  ~ "):
            if cur[1]: cur[1][-1][2].append((text, [float(v) for v in geo[4:].split()]))
        else:
            cur[1].append((text, [float(v) for v in geo.split()], []))
    return res


def union(boxes):
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def span_box(text, lbox, words, a, b):
    """box of characters a..b of a line: the words that overlap it, else a proportional slice of the line"""
    pos, hits = 0, []
    for w, box in words:
        k = text.find(w, pos)
        if k < 0: continue
        pos = k + len(w)
        if k < b and pos > a: hits.append(box)
    if hits: return union(hits)
    n = max(1, len(text)); return [lbox[0] + lbox[2] * a / n, lbox[1], lbox[2] * (b - a) / n, lbox[3]]


def word_rx(w):
    """a word she names, tolerant of case and Ukrainian endings (Квітка / Квітки / квітці)"""
    parts = [re.escape(p[:max(4, len(p) - 2)]) + r"\w*" if len(p) > 4 else re.escape(p) for p in w.split()]
    return re.compile(r"\s+".join(parts), re.I)


def cmd_find(a):
    video = Path(a.video).expanduser()
    W, H, dur = probe(video)
    brand = json.load(open(HOME / "brand.json")) if (HOME / "brand.json").exists() else {}
    keep = {h.lower().lstrip("@") for h in ([brand.get("handle")] if isinstance(brand.get("handle"), str) else brand.get("handle") or []) if h}
    pats = [] if a.no_auto else [(k, re.compile(p, re.I)) for k, p in AUTO]
    pats += [(f"«{w}»", word_rx(w)) for w in (a.words or [])]
    hits = []
    for t, lines in ocr(video, a.step):
        for text, lbox, words in lines:
            for kind, rx in pats:
                for m in rx.finditer(text):
                    s = m.group(0).strip()
                    if kind == "handle" and s.lower().lstrip("@") in keep: continue
                    if kind == "phone" and len(re.sub(r"\D", "", s)) < 9: continue
                    if kind == "account id" and re.fullmatch(r"20\d\d", s): continue
                    hits.append({"t": t, "kind": kind, "text": s, "box": span_box(text, lbox, words, m.start(), m.end())})
    # one item per thing on screen: same kind + text + nearby box across consecutive reads -> one timed box
    items = []
    for h in sorted(hits, key=lambda h: h["t"]):
        px = [round(h["box"][0] * W), round(h["box"][1] * H), round(h["box"][2] * W), round(h["box"][3] * H)]
        for it in items:
            if it["kind"] == h["kind"] and it["text"] == h["text"] and h["t"] - it["to"] <= a.step * 1.5 \
                    and abs(it["box"][0] - px[0]) < 40 and abs(it["box"][1] - px[1]) < 40:
                it["to"] = h["t"]; it["box"] = [min(it["box"][0], px[0]), min(it["box"][1], px[1]),
                                                  max(it["box"][0] + it["box"][2], px[0] + px[2]) - min(it["box"][0], px[0]),
                                                  max(it["box"][1] + it["box"][3], px[1] + px[3]) - min(it["box"][1], px[1])]
                break
        else:
            items.append({"kind": h["kind"], "text": h["text"], "from": h["t"], "to": h["t"], "box": px})
    for it in items:
        it["from"] = round(max(0.0, it["from"] - a.step / 2 - 0.3), 2); it["to"] = round(min(dur, it["to"] + a.step / 2 + 0.3), 2)
    out = Path(str(video) + ".redact.json")
    json.dump({"video": str(video), "size": [W, H], "items": items}, open(out, "w"), ensure_ascii=False, indent=1)
    for it in items:
        print(f"  {it['from']:6.1f}-{it['to']:6.1f}s  {it['kind']:10s} {it['text'][:40]:40s} {it['box']}")
    print(f"{len(items)} items -> {out}")
    sheet(video, items, W, H, dur, Path(str(video) + ".redact.jpg"))


def sheet(video, items, W, H, dur, out):
    """up to 6 frames where items are on screen, boxes drawn in red"""
    ts = sorted({round((it["from"] + it["to"]) / 2, 1) for it in items})[:6] or [dur / 2]
    with tempfile.TemporaryDirectory() as d:
        tiles = []
        for k, t in enumerate(ts):
            boxes = [it["box"] for it in items if it["from"] <= t <= it["to"]]
            draw = ",".join(f"drawbox=x={b[0] - 6}:y={b[1] - 6}:w={b[2] + 12}:h={b[3] + 12}:color=red@0.9:t=4" for b in boxes) or "null"
            f = f"{d}/t{k}.jpg"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                            "-vf", f"{draw},scale=-2:720", f], check=True)
            tiles.append(f)
        if len(tiles) == 1: subprocess.run(["cp", tiles[0], str(out)])
        else:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *sum([["-i", f] for f in tiles], []),
                            "-filter_complex", "".join(f"[{i}]" for i in range(len(tiles))) + f"hstack={len(tiles)}", str(out)], check=True)
    print(f"LOOK at {out}: every red box must cover the whole item, and nothing she wants seen")


def cmd_apply(a):
    video = Path(a.video).expanduser(); W, H, dur = probe(video)
    items = []
    if a.box:
        for s in a.box:
            v = [float(x) for x in s.split(",")]
            items.append({"box": [int(x) for x in v[:4]], "from": v[4] if len(v) > 4 else 0, "to": v[5] if len(v) > 5 else dur})
    else:
        j = Path(a.json) if a.json else Path(str(video) + ".redact.json")
        items = json.load(open(j))["items"]
    if not items: sys.exit("nothing to hide")
    chain, last = [], "[0:v]"
    for i, it in enumerate(items):
        x, y, w, h = it["box"]; p = 6
        x, y = max(0, x - p), max(0, y - p); w, h = min(W - x, w + 2 * p), min(H - y, h + 2 * p)
        w, h = max(8, w // 2 * 2), max(8, h // 2 * 2)
        en = f"between(t,{it['from']:.2f},{it['to']:.2f})"
        if a.mode == "pixelate":
            k = max(4, min(w, h) // 6)
            fx = f"scale=max(2\\,iw/{k}):max(2\\,ih/{k}):flags=neighbor,scale={w}:{h}:flags=neighbor"
        else:
            r = max(4, min(w, h) // 3)
            fx = f"boxblur={min(r, w // 2 - 1)}:2:{max(1, min(r, w // 2 - 1) // 2)}:2"
        chain.append(f"{last}split[b{i}][s{i}];[s{i}]crop={w}:{h}:{x}:{y},{fx}[r{i}];[b{i}][r{i}]overlay={x}:{y}:enable='{en}'[v{i}]")
        last = f"[v{i}]"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video), "-filter_complex", ";".join(chain), "-map", last,
                    "-map", "0:a?", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    str(Path(a.out).expanduser())], check=True)
    print(f"{len(items)} boxes hidden -> {a.out}  (LOOK at a frame where each one is on screen)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("find"); p.add_argument("video"); p.add_argument("--words", nargs="*"); p.add_argument("--no-auto", action="store_true")
    p.add_argument("--step", type=float, default=0.5)
    p = sp.add_parser("apply"); p.add_argument("video"); p.add_argument("out"); p.add_argument("--json"); p.add_argument("--box", action="append")
    p.add_argument("--mode", choices=["blur", "pixelate"], default="blur")
    a = ap.parse_args()
    {"find": cmd_find, "apply": cmd_apply}[a.cmd](a)


if __name__ == "__main__":
    main()
