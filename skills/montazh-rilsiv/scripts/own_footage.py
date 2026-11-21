#!/usr/bin/env python3
"""Her own videos as B-roll: find a clip for a line in her libraries, with a face check so only she (or nobody) is in it.
Adapted from ghost-editor's own_footage.py (MIT, github.com/kurbaitaev/ghost-editor). Differences: the descriptions come
from macOS Vision on the Mac (no Gemini, no frame leaves the computer), and picks go to <reel>/finds/ like find_media.py,
so they show up on the review page's «Накладення → Знайти».

    own_footage.py me <video-or-photo> [...] [--add]   her face reference, from a clip where only she is in frame
                                                         (any raw.mov of a past reel) -> <REELS_HOME>/me/face_ref.npz + refs.jpg (LOOK: every crop her)
    own_footage.py index [--root DIR ...] [--max N]      scan her libraries -> <REELS_HOME>/me/footage_index.json (incremental, re-run any time)
    own_footage.py find WORD [WORD ...] [--people none|me|any] [--kind photo|video|any] [--min 1.5] [-n 8]
                                                         ranked hits: first her sorted libraries (a folder with library.csv:
                                                         descriptions, tags, mood, who is in frame, place for text),
                                                         then the Vision index of the other roots (English words there)
    own_footage.py check CLIP --in 3.0 --dur 2.0         5 fps over the window: no people / only you / SOMEONE ELSE (exit 1)
    own_footage.py pick <reel> CLIP --in 3.0 --dur 2.5 [--query "coffee"] [--into <request id>]
                                                         checks the window, cuts it (1080 short side, H.264, no sound) into
                                                         <reel>/finds/[<into>/]own-*.mp4 + finds.json; refuses SOMEONE ELSE
    own_footage.py sheet <reel> [-o own-confirm.jpg]     5 frames of every own pick with the face boxes: show her before the render

Catalog libraries: a root with a library.csv (columns path,type,duration,person_in_frame (так/ні/руки/невідомо),description,
tags,mood,place,text_space,use,quality; a library they sorted with Claude) is searched through that table and never re-scanned; the face
check still runs on the window she picks. Other roots: ~/Movies, the Photos library originals when this app may read them (System Settings → Privacy → Full Disk Access),
and folders in <REELS_HOME>/me/roots.json (["~/Desktop/Відео", "/Volumes/GoPro"]). Read only: nothing in them is changed.
iCloud placeholders (not on the Mac) are skipped, never downloaded. Her face embeddings and the index stay in <REELS_HOME>/me/.
Faces: OpenCV YuNet + SFace (models from github.com/opencv/opencv_zoo, MIT / Apache-2.0, cached in ~/.cache/reel-editor/models).
A face of 4 %+ of the frame width is HER when SFace cosine to any reference >= 0.40, else SOMEONE ELSE; smaller = far figure.
Runs in <REELS_HOME>/.venv (numpy + opencv-python-headless); started with another python it re-runs itself there."""
import argparse, hashlib, json, os, re, subprocess, sys, tempfile, urllib.request
from pathlib import Path

HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
VENV = HOME / ".venv" / "bin" / "python"
try:
    import numpy as np
    import cv2
except ImportError:
    if VENV.exists() and Path(sys.prefix).resolve() != (HOME / ".venv").resolve():
        os.execv(str(VENV), [str(VENV), *sys.argv])
    sys.exit(f"needs numpy + opencv: {HOME}/.venv/bin/pip install numpy opencv-python-headless")

HERE = Path(__file__).resolve().parent
ME = HOME / "me"
REF, INDEX = ME / "face_ref.npz", ME / "footage_index.json"
MODELS = Path("~/.cache/reel-editor/models").expanduser()
YUNET = ("face_detection_yunet_2023mar.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx")
SFACE = ("face_recognition_sface_2021dec.onnx", "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx")
PHOTOS = Path("~/Pictures/Photos Library.photoslibrary/originals").expanduser()
ROOTS = [Path("~/Movies").expanduser(), PHOTOS]
VIDEO = re.compile(r"\.(mov|mp4|m4v)$", re.I)
STILL = re.compile(r"\.(jpe?g|png|heic|webp)$", re.I)
SKIP = re.compile(r"(/\.|/Telegram|/CapCut|/renders?/|/proxies|/\.Trash|/TV/|/reels/|/Final Cut|\.fcpbundle|\.lrlibrary)", re.I)
TH, TINY = 0.40, 0.04
VERSION = 1


# ------------------------------------------------------------------ media helpers
def probe(p):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,avg_frame_rate,color_transfer:stream_side_data=rotation:format=duration",
                                   "-of", "json", str(p)], capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]; n, d = (s.get("avg_frame_rate") or "0/1").split("/")
    rot = next((int(x["rotation"]) for x in s.get("side_data_list", []) or [] if "rotation" in x), 0)
    w, h = int(s["width"]), int(s["height"])
    if rot in (90, -90, 270, -270): w, h = h, w
    return {"w": w, "h": h, "fps": float(n) / float(d) if float(d) and float(n) else 30.0,
            "dur": float(j["format"].get("duration", 0) or 0), "hdr": s.get("color_transfer") in ("arib-std-b67", "smpte2084")}


def frames_at(p, times, short=360):
    """BGR frames (upright, short side = short) at the given seconds"""
    out = []
    with tempfile.TemporaryDirectory() as d:
        for k, t in enumerate(times):
            f = f"{d}/{k}.png"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", str(p), "-frames:v", "1",
                            "-vf", f"scale='if(gt(iw,ih),-2,{short})':'if(gt(iw,ih),{short},-2)'", f])
            im = cv2.imread(f)
            if im is not None: out.append((t, im))
    return out


def swift_tool(name):
    src, exe = HERE / f"{name}.swift", Path(f"~/.cache/reel-editor/{name}").expanduser()
    if not exe.exists() or exe.stat().st_mtime < src.stat().st_mtime:
        exe.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["swiftc", "-O", "-o", str(exe), str(src)], check=True, capture_output=True)
    return exe


def tags_of(images):
    """Vision labels for some BGR images -> {label: best confidence}"""
    try: exe = swift_tool("classify")
    except Exception: return {}
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for k, im in enumerate(images):
            paths.append(f"{d}/{k}.jpg"); cv2.imwrite(paths[-1], im)
        out = subprocess.run([str(exe)], input="\n".join(paths) + "\n", capture_output=True, text=True).stdout.split("\n")
    T = {}
    for line in out:
        for x in line.split():
            if ":" in x:
                lab, c = x.rsplit(":", 1); T[lab] = max(T.get(lab, 0), float(c))
    return {k: round(v, 2) for k, v in sorted(T.items(), key=lambda kv: -kv[1])[:16]}


# ------------------------------------------------------------------ faces
def model(nu):
    name, url = nu; p = MODELS / name
    if not p.exists():
        MODELS.mkdir(parents=True, exist_ok=True)
        print(f"downloading {name} (OpenCV model zoo, once) ...", flush=True)
        urllib.request.urlretrieve(url, str(p) + ".part"); os.replace(str(p) + ".part", p)
    return str(p)


class Faces:
    def __init__(self):
        self.rec = cv2.FaceRecognizerSF.create(model(SFACE), ""); self.det = None; self.size = None

    def detect(self, img, thr=0.6):
        h, w = img.shape[:2]
        if self.det is None or self.size != (w, h):
            self.det = cv2.FaceDetectorYN.create(model(YUNET), "", (w, h), thr, 0.3, 50); self.size = (w, h)
        self.det.setScoreThreshold(thr)
        _, fs = self.det.detect(img)
        return [] if fs is None else [f for f in fs if f[2] >= 0.03 * w]

    def feature(self, img, f):
        e = self.rec.feature(self.rec.alignCrop(img, f)).flatten()
        return e / (np.linalg.norm(e) + 1e-9)


_F = None
def faces():
    global _F
    if _F is None: _F = Faces()
    return _F


def load_ref():
    if not REF.exists():
        sys.exit(f"no face reference yet: run `own_footage.py me <a raw.mov of one of her reels>` first ({REF})")
    return np.load(REF)["emb"]


def who(img, ref, thr=0.6):
    """faces in a frame -> [(x, y, w, h, label, cos)], label me / other / tiny"""
    out, w = [], img.shape[1]
    for f in faces().detect(img, thr):
        if f[2] < TINY * w: out.append((*f[:4], "tiny", 0.0)); continue
        cos = float((ref @ faces().feature(img, f)).max())
        out.append((*f[:4], "me" if cos >= TH else "other", cos))
    return out


# ------------------------------------------------------------------ commands
def cmd_me(a):
    ME.mkdir(parents=True, exist_ok=True)
    embs = list(np.load(REF)["emb"]) if a.add and REF.exists() else []
    crops = []
    for src in a.src:
        if STILL.search(src): ims = [cv2.imread(src)]
        else:
            info = probe(src); ims = [im for _, im in frames_at(src, [info["dur"] * (i + .5) / 12 for i in range(12)], 540)]
        for im in ims:
            if im is None: continue
            fs = [f for f in faces().detect(im, 0.85) if f[2] >= 0.09 * im.shape[1]]
            if len(fs) != 1: continue                     # exactly one big face: nobody else sneaks into the reference
            f = fs[0]; embs.append(faces().feature(im, f))
            x, y, w, h = [int(v) for v in f[:4]]
            crops.append(cv2.resize(im[max(0, y):y + h, max(0, x):x + w], (120, 120)))
    if not embs: sys.exit("no single clear face found in these sources")
    E = np.stack(embs); m = E.mean(0) / np.linalg.norm(E.mean(0)); E = E[E @ m >= 0.45]   # drop an outlier (a wrong face)
    np.savez(REF, emb=E)
    if crops: cv2.imwrite(str(ME / "refs.jpg"), np.hstack(crops[:16]))
    print(f"{len(E)} reference embeddings -> {REF}\nLOOK at {ME / 'refs.jpg'}: every crop must be her")


def roots(a):
    if a.root: return [Path(r).expanduser() for r in a.root]
    rj = ME / "roots.json"
    extra = [Path(r).expanduser() for r in json.load(open(rj))] if rj.exists() else []
    return ROOTS + extra


def scan(p, ref):
    info = probe(p)
    if info["dur"] < 1.0: return None
    n = int(min(30, max(2, info["dur"])))
    samples, ims = [], []
    for t, im in frames_at(p, [info["dur"] * (i + .5) / n for i in range(n)]):
        fs = who(im, ref)
        samples.append({"t": round(t, 2), "me": sum(f[4] == "me" for f in fs), "other": sum(f[4] == "other" for f in fs),
                        "tiny": sum(f[4] == "tiny" for f in fs)})
        ims.append(im)
    people = "others" if any(s["other"] for s in samples) else "me" if any(s["me"] for s in samples) else \
        "tiny" if any(s["tiny"] for s in samples) else "none"
    clean, cur, step = [], None, info["dur"] / max(1, n)      # runs with no one else in frame
    for s in samples:
        if s["other"] == 0: cur = [max(0, s["t"] - step / 2), s["t"] + step / 2] if cur is None else [cur[0], s["t"] + step / 2]
        else:
            if cur: clean.append(cur)
            cur = None
    if cur: clean.append(cur)
    six = [ims[int(i * (len(ims) - 1) / 5)] for i in range(6)] if len(ims) >= 6 else ims
    return {**{k: info[k] for k in ("w", "h", "dur", "hdr")}, "fps": round(info["fps"], 2), "people": people,
            "clean": [[round(x, 2), round(min(y, info["dur"]), 2)] for x, y in clean], "tags": tags_of(six[::2]), "_six": six}


def cmd_index(a):
    ref = load_ref()
    idx = json.load(open(INDEX)) if INDEX.exists() else {}
    (ME / "sheets").mkdir(parents=True, exist_ok=True)
    files, cats = [], [r for r in roots(a) if (r / "library.csv").exists()]
    for r in roots(a):
        if not r.is_dir(): print(f"skip {r} (not on this Mac)"); continue
        if (r / "library.csv").exists(): print(f"{r}: sorted library (library.csv), searched through its table, no scan"); continue
        try: next(os.scandir(r), None)
        except PermissionError:
            print(f"skip {r}: macOS blocks it (System Settings → Privacy & Security → Full Disk Access → Claude)"); continue
        for dp, _, fn in os.walk(r):
            if SKIP.search(dp + "/") or any(Path(dp).is_relative_to(c) for c in cats): continue
            files += [os.path.join(dp, f) for f in fn if VIDEO.search(f)]
    done = 0
    for p in sorted(files):
        try: st = os.stat(p)
        except OSError: continue
        if st.st_size < 50_000 or getattr(st, "st_blocks", 1) == 0: continue      # iCloud placeholder: never download
        key = f"{st.st_size}:{int(st.st_mtime)}"
        e = idx.get(p)
        if e and e.get("key") == key and e.get("v") == VERSION: continue
        if a.max and done >= a.max: break
        try: s = scan(p, ref)
        except (subprocess.CalledProcessError, KeyError, ValueError, IndexError) as ex: print(f"skip {p}: {ex}"); continue
        if not s: continue
        six = s.pop("_six"); sh = ME / "sheets" / (hashlib.md5(p.encode()).hexdigest()[:16] + ".jpg")
        if six:
            cv2.imwrite(str(sh), np.hstack([cv2.resize(im, (int(im.shape[1] * 200 / im.shape[0]), 200)) for im in six]), [cv2.IMWRITE_JPEG_QUALITY, 80])
        idx[p] = {"key": key, "v": VERSION, **s, "sheet": str(sh)}
        done += 1
        if done % 10 == 0: json.dump(idx, open(INDEX, "w")); print(f"  {done} scanned", flush=True)
    json.dump(idx, open(INDEX, "w"))
    by = {k: sum(1 for e in idx.values() if e["people"] == k) for k in ("none", "tiny", "me", "others")}
    print(f"{len(idx)} clips indexed ({done} new): no people {by['none']}, far figures {by['tiny']}, only her {by['me']}, "
          f"someone else {by['others']} -> {INDEX}")


def catalogs():
    """rows of every root that carries a library.csv (a library she already sorted and described)"""
    import csv
    out = []
    for r in roots(argparse.Namespace(root=None)):
        f = r / "library.csv"
        if not f.exists(): continue
        for row in csv.DictReader(open(f, encoding="utf-8")):
            p = r / row["path"]
            if p.exists(): out.append({**row, "abs": str(p), "folder": row["path"].split("/")[0]})
    return out


def who_of(e):
    return e.get("person_in_frame") or e.get("in_frame") or ""


def _hit(w, text):
    """Ukrainian-friendly match: the word, or its stem (endings change: гори / гірах / гору)"""
    stem = w[:max(4, len(w) - 2)] if len(w) > 4 else w
    return any(t.startswith(stem) or w in t for t in re.findall(r"[\wʼ'-]+", text.lower()))


def cmd_find(a):
    words = [w.lower() for w in a.words]
    rows = []
    for e in catalogs():
        if a.kind != "any" and e["type"] != a.kind: continue
        who = e.get("person_in_frame") or e.get("in_frame") or ""
        people_folder = bool(re.search(r"(люди|people|події|events)", e["folder"], re.I))
        if a.people == "none" and (who in ("так", "невідомо") or people_folder): continue
        if a.people == "me" and people_folder: continue
        W = {"tags": 3, "description": 2, "mood": 1.5, "place": 1, "folder": 1, "use": 0.5, "colors": 0.5}
        score = sum(max([k for f, k in W.items() if _hit(w, e.get(f, ""))] or [0]) for w in words)
        if not score: continue
        score += {"добре": 0.5, "слабко": -1}.get(e.get("quality"), 0)
        rows.append((score, e))
    if rows: print("== твоя бібліотека")
    for score, e in sorted(rows, key=lambda r: -r[0])[:a.n]:
        print(f"{score:4.1f}  {e['abs']}\n      {e['type']} {e.get('duration') or ''}  людина в кадрі: {who_of(e)}  місце під текст: "
              f"{e.get('text_space')}  якість: {e.get('quality')}\n      {e.get('description')}\n      теги: {e.get('tags')} | настрій: {e.get('mood')}")
    if a.kind == "photo" or not INDEX.exists(): 
        if not rows: print("nothing found: try other words (synonyms, the place, the mood)")
        return
    idx = json.load(open(INDEX)); vrows = []
    for p, e in idx.items():
        if a.people == "none" and e["people"] not in ("none", "tiny"): continue
        if a.people == "me" and e["people"] not in ("none", "tiny", "me"): continue
        tags = e.get("tags", {}); place = (os.path.basename(os.path.dirname(p)) + " " + os.path.basename(p)).lower()
        score = sum(2 * max([c for t, c in tags.items() if w in t.lower()] or [0]) + (0.5 if w in place else 0) for w in words)
        wins = [w for w in e["clean"] if w[1] - w[0] >= a.min]
        if score > 0 and wins: vrows.append((score, p, e, wins))
    if vrows: print("== інші відео (теги Vision, англійською)")
    elif not rows: print("nothing found: try other words (her library: Ukrainian; other videos: English Vision tags)")
    for score, p, e, wins in sorted(vrows, key=lambda r: -r[0])[:a.n]:
        print(f"{score:4.1f}  {p}\n      {e['w']}x{e['h']} {e['fps']:g} fps {e['dur']} s{' HDR' if e['hdr'] else ''}  people: {e['people']}  "
              f"clean: {wins[:3]}\n      tags: {', '.join(list(e.get('tags', {}))[:8])}\n      sheet: {e.get('sheet')}")


def check_window(p, tin, dur, ref):
    hits, ims = [], []
    for t, im in frames_at(p, [tin + k / 5 for k in range(max(1, int(dur * 5)))]):
        ims.append(im)
        hits += [(round(t, 2), f[4], round(f[5], 2), [int(v) for v in f[:4]]) for f in who(im, ref, 0.55)]
    v = "SOMEONE ELSE" if any(x[1] == "other" for x in hits) else "only you" if any(x[1] == "me" for x in hits) else \
        "far figures only" if any(x[1] == "tiny" for x in hits) else "no people"
    return v, hits, ims


def cmd_check(a):
    v, hits, _ = check_window(a.clip, a.tin, a.dur, load_ref())
    print(f"{v}: {os.path.basename(a.clip)} {a.tin:.2f}+{a.dur:.2f} s")
    for t, lab, cos, box in hits:
        if lab == "other": print(f"  {t:.2f} s: a face that is not her (cosine {cos}) at {box}")
    sys.exit(1 if v == "SOMEONE ELSE" else 0)


def pick_still(a, reel):
    im = cv2.imread(a.clip)
    if im is None:                                   # HEIC and friends: let macOS convert
        tmp = Path(tempfile.mkdtemp()) / "still.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", a.clip, "--out", str(tmp)], capture_output=True); im = cv2.imread(str(tmp))
    if im is None: sys.exit(f"can't read {a.clip}")
    k = 1080 / min(im.shape[:2])                     # stills: check at 1080 so a person across the street still has a face
    fs = who(cv2.resize(im, (int(im.shape[1] * k), int(im.shape[0] * k))) if k < 1 else im, load_ref(), 0.55)
    v = "SOMEONE ELSE" if any(f[4] == "other" for f in fs) else "only you" if any(f[4] == "me" for f in fs) else \
        "far figures only" if any(f[4] == "tiny" for f in fs) else "no people"
    if v == "SOMEONE ELSE" and not a.force: sys.exit(f"SOMEONE ELSE in {os.path.basename(a.clip)}: another picture (or --force after she says yes)")
    out_dir = reel / "finds" / a.into if a.into else reel / "finds"; out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"own-{re.sub(r'[^\w-]+', '-', Path(a.clip).stem)[:40]}.jpg"
    k = 1920 / max(im.shape[:2])
    cv2.imwrite(str(out), cv2.resize(im, (int(im.shape[1] * k), int(im.shape[0] * k)), interpolation=cv2.INTER_AREA) if k < 1 else im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    log = out_dir / "finds.json"; found = json.load(open(log)) if log.exists() else []
    found.append({"file": str(out.relative_to(reel)), "kind": "photo", "query": a.query or "", "source": "own", "name": os.path.basename(a.clip),
                  "src": a.clip, "in": 0, "dur": 0, "people": v, "license": "її власне фото"})
    json.dump(found, open(log, "w"), ensure_ascii=False, indent=1)
    print(f"{v} -> {out}")


def cmd_pick(a):
    reel = Path(a.reel).expanduser()
    if STILL.search(a.clip): return pick_still(a, reel)
    if a.dur <= 0 or a.tin + a.dur > probe(a.clip)["dur"] + 0.05: sys.exit("the window runs past the clip's end: check --in / --dur")
    v, hits, _ = check_window(a.clip, a.tin, a.dur, load_ref())
    if v == "SOMEONE ELSE" and not a.force:
        sys.exit(f"SOMEONE ELSE in {os.path.basename(a.clip)} {a.tin:.1f}+{a.dur:.1f} s: pick another window (or --force after she says yes)")
    out_dir = reel / "finds" / a.into if a.into else reel / "finds"; out_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^\w-]+", "-", Path(a.clip).stem)[:40]
    out = out_dir / f"own-{stem}-{a.tin:.1f}.mp4"
    info = probe(a.clip)
    vf = "scale='if(gt(iw,ih),-2,1080)':'if(gt(iw,ih),1080,-2)'" + (",zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable,zscale=t=bt709:m=bt709:r=tv" if info["hdr"] else "")
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a.tin:.3f}", "-t", f"{a.dur:.3f}", "-i", a.clip, "-an",
                        "-vf", vf + ",format=yuv420p", "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(out)])
    if r.returncode and info["hdr"]:        # ffmpeg without zimg: plain conversion, colours may look flat
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a.tin:.3f}", "-t", f"{a.dur:.3f}", "-i", a.clip, "-an",
                        "-vf", "scale='if(gt(iw,ih),-2,1080)':'if(gt(iw,ih),1080,-2)',format=yuv420p", "-c:v", "libx264", "-crf", "16", str(out)], check=True)
    log = out_dir / "finds.json"; found = json.load(open(log)) if log.exists() else []
    found.append({"file": str(out.relative_to(reel)), "kind": "video", "query": a.query or "", "source": "own", "name": os.path.basename(a.clip),
                  "src": a.clip, "in": a.tin, "dur": a.dur, "people": v, "license": "її власне відео"})
    json.dump(found, open(log, "w"), ensure_ascii=False, indent=1)
    print(f"{v} -> {out}")


def cmd_sheet(a):
    reel = Path(a.reel).expanduser(); ref = load_ref()
    picks = [x for f in reel.glob("finds/**/finds.json") for x in json.load(open(f)) if x.get("source") == "own"]
    if not picks: sys.exit("no own-footage picks in finds/ yet")
    rows = []
    for pk in picks:
        if pk.get("kind") == "photo":
            im = cv2.imread(str(reel / pk["file"])); im = cv2.resize(im, (360, int(360 * im.shape[0] / im.shape[1])))
            ims = [im]; v = pk.get("people", "")
        else: v, _, ims = check_window(str(reel / pk["file"]), 0.0, float(pk.get("dur", 2.0)), ref)
        sel = [ims[int(i * (len(ims) - 1) / 4)] for i in range(5)] if len(ims) >= 5 else ims
        tiles = []
        for im in sel:
            im = im.copy()
            for f in who(im, ref, 0.55):
                col = {"me": (0, 200, 0), "other": (0, 0, 255), "tiny": (0, 200, 255)}[f[4]]
                x, y, w, h = [int(q) for q in f[:4]]
                cv2.rectangle(im, (x, y), (x + w, y + h), col, 2)
                cv2.putText(im, {"me": "you", "other": "NOT YOU?", "tiny": "far"}[f[4]], (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1)
            tiles.append(cv2.resize(im, (160, int(160 * im.shape[0] / im.shape[1]))))
        hh = max(t.shape[0] for t in tiles)
        row = np.hstack([cv2.copyMakeBorder(t, 0, hh - t.shape[0], 0, 3, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles])
        if row.shape[1] < 640: row = cv2.copyMakeBorder(row, 0, 0, 0, 640 - row.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255))
        head = np.full((26, row.shape[1], 3), 255, np.uint8)
        cv2.putText(head, f"{pk['name'][:48]}" + ("" if pk.get("kind") == "photo" else f" {float(pk['in']):.1f}+{float(pk['dur']):.1f}s") + f"  {v}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 0, 200) if v == "SOMEONE ELSE" else (30, 30, 30), 1)
        rows.append(np.vstack([head, row])); print(f"  {v:16s} {pk['file']}")
    W = max(r.shape[1] for r in rows)
    out = reel / a.o
    cv2.imwrite(str(out), np.vstack([cv2.copyMakeBorder(r, 0, 6, 0, W - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]))
    print(f"-> {out}: show it to her and wait for her yes before the render")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("me"); p.add_argument("src", nargs="+"); p.add_argument("--add", action="store_true")
    p = sp.add_parser("index"); p.add_argument("--root", action="append"); p.add_argument("--max", type=int)
    p = sp.add_parser("find"); p.add_argument("words", nargs="+"); p.add_argument("--people", choices=["none", "me", "any"], default="me")
    p.add_argument("--kind", choices=["photo", "video", "any"], default="any")
    p.add_argument("--min", type=float, default=1.5); p.add_argument("-n", type=int, default=8)
    p = sp.add_parser("check"); p.add_argument("clip"); p.add_argument("--in", dest="tin", type=float, default=0.0); p.add_argument("--dur", type=float, default=3.0)
    p = sp.add_parser("pick"); p.add_argument("reel"); p.add_argument("clip"); p.add_argument("--in", dest="tin", type=float, default=0.0)
    p.add_argument("--dur", type=float, default=2.5); p.add_argument("--query"); p.add_argument("--into", default=""); p.add_argument("--force", action="store_true")
    p = sp.add_parser("sheet"); p.add_argument("reel"); p.add_argument("-o", default="own-confirm.jpg")
    a = ap.parse_args()
    {"me": cmd_me, "index": cmd_index, "find": cmd_find, "check": cmd_check, "pick": cmd_pick, "sheet": cmd_sheet}[a.cmd](a)


if __name__ == "__main__":
    main()
