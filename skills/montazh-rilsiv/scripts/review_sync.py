#!/usr/bin/env python3
"""Bridge between a reel folder and the Reel Review page.
  export <reel> <proposal.json> <out-dir>   build reel.json (the page's data) + assets to upload
  import <reel> <review.json>               turn the person's decisions into edl.json + edit.json for cut.py/render.sh
  overlays <reel> <review.json>             list the overlays they placed (round 1), so Claude's graphics go around them
The cut timeline is computed by review/core.js (run with node), the same file the page uses, so review and render agree.

proposal.json (Claude writes this per reel):
  {"title", "proposedCut": [[srcStart, srcEnd], ...] (kept lines), "accentWords": ["claude", ...],
   "cards": [{"id","type","kind","what","anchor":"word","after":srcSec,"end_anchor"?,"place":[x,y,w,h], "sfx":{"name","db"}, ...build_reel fields}]}"""
import json, os, re, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pacing import pacing, is_filler, lang, pairs_forward

HERE = Path(__file__).resolve().parent
CORE = HERE.parent / "review" / "core.js"
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
norm = lambda s: re.sub(r"[\W_]", "", s.lower())

def _rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def _theme(brand):
    """Review page colours from the brand: dark brands get a dark page, light brands a light one.
    brand.json "page" (optional) overrides any token, e.g. their website look: {"bg", "surface", "accent", "on-accent",
    "pink", "grid", "glow1", "glow2", "label"}; "label" is the small line above the page title."""
    t = _theme_base(brand); t.update(brand.get("page") or {}); return t

def _theme_base(brand):
    c = brand.get("colors", {}); main = c.get("main", "#141414"); pop = c.get("pop", "#ED84B0")
    light = c.get("light", "#FFFFFF"); soft = c.get("soft", pop); deep = c.get("deep")
    r, g, b = _rgb(main); dark = (0.299 * r + 0.587 * g + 0.114 * b) < 128
    pr, pg, pb = _rgb(pop); rgba = lambda a: f"rgba({pr},{pg},{pb},{a})"
    if dark:
        lr, lg, lb = _rgb(light); ink = lambda a: f"rgba({lr},{lg},{lb},{a})"
        return {"scheme": "dark", "bg": main, "surface": deep or ink(.06), "ink": light, "muted": ink(.62),
                "line": ink(.16), "pink": pop, "pink-soft": rgba(.12), "now": rgba(.22), "glow": rgba(.28),
                "cut-bg": pop, "cut-fg": main, "auto": ink(.45), "keep": soft, "on-accent": main}
    return {"scheme": "light", "bg": light, "surface": "#FFFFFF", "ink": main, "muted": "rgba(0,0,0,.55)",
            "line": rgba(.25), "pink": pop, "pink-soft": rgba(.10), "now": rgba(.18), "glow": rgba(.25),
            "cut-bg": main, "cut-fg": light, "on-accent": main}

def raw_clip(reel):   # the raw clip's name keeps its extension (raw.mov from an iPhone, raw.mp4 from Android)
    return next(iter(sorted(reel.glob("raw.*"))), reel / "raw.mov")


def node(reel_json, decisions):
    # data goes in on stdin: long clips would overflow the command-line length limit
    js = f"""const C=require({json.dumps(str(CORE))});const I=JSON.parse(require("fs").readFileSync(0,"utf8"));const R=I.r,D=I.d;
const P=C.plan(R,D);process.stdout.write(JSON.stringify({{spans:P.spans,cutDur:P.cutDur,pauses:P.pauses,
captions:C.capsAround(R,D,C.captions(R,D,P),C.graphics(R,D,P)),graphics:C.graphics(R,D,P),hash:C.hash(D),grade:C.gradeFilter(D.grade,"__CUBE__"),cube:C.isNeutral(D.grade)?"":C.gradeCube(D.grade)}}));"""
    return json.loads(subprocess.run(["node", "-e", js], input=json.dumps({"r": reel_json, "d": decisions}),
                                     capture_output=True, text=True, check=True).stdout)

def export(reel, proposal, out):
    out.mkdir(parents=True, exist_ok=True)
    brand = json.load(open(HOME / "brand.json"))
    src = [w for w in json.load(open(reel / "transcript.json")) if w["text"].strip()]
    words = [{"text": w["text"], "s": round(w["start"], 3), "e": round(w["end"], 3)} for w in src]
    # Transcript word times run back to back, hiding pauses. Measure real silences in the cleaned voice (threshold just
    # above this clip's noise floor) and pull word edges back to them, so pauses show up as gaps the review can trim.
    import array, math, wave
    wf = wave.open(str(reel / "voice.wav")); sr = wf.getframerate(); pcm = array.array("h"); pcm.frombytes(wf.readframes(wf.getnframes()))
    hop = int(sr * 0.05)
    lev = sorted(20 * math.log10(max(1.0, math.sqrt(sum(x * x for x in pcm[i:i + hop:4]) / (hop / 4))) / 32768) for i in range(0, len(pcm) - hop, hop))
    thresh = min(lev[len(lev) // 10] + 5, -20)
    sd = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(reel / "voice.wav"), "-af", f"silencedetect=noise={thresh:.1f}dB:d=0.15", "-f", "null", "-"],
                        capture_output=True, text=True).stderr
    sil = list(zip(map(float, re.findall(r"silence_start: ([\d.]+)", sd)), map(float, re.findall(r"silence_end: ([\d.]+)", sd))))
    for a, b in sil:
        for w in words:
            if w["s"] < a < w["e"] and a - w["s"] > 0.08: w["e"] = round(a, 3)
            elif a <= w["s"] < b and w["e"] - b > 0.08: w["s"] = round(b, 3)
    # fillers ("um", "ем"): Scribe writes them as words, so mark those; fillers.json adds any that aren't words yet
    fl = pacing(brand)["fillers"]
    for w in words:
        if is_filler(w["text"], fl, lang(brand)): w["filler"] = True
    fj = reel / "fillers.json"
    if fj.exists():
        for t in json.load(open(fj))["transcription"]:
            txt = t["text"].strip()
            if is_filler(txt, fl, lang(brand)):
                s, e = t["offsets"]["from"] / 1000, t["offsets"]["to"] / 1000
                if any(w.get("filler") and abs(w["s"] - s) < 0.1 for w in words): continue   # already a word in the transcript
                if not any(w["s"] < e - 0.05 and w["e"] > s + 0.05 for w in words):
                    words.append({"text": txt.strip(",.").lower(), "s": round(s, 3), "e": round(max(e, s + 0.25), 3), "filler": True})
                else:   # the recogniser folded the um into a neighbouring word: split it off so cutting it removes its audio
                    e = round(max(e, s + 0.25), 3)
                    for w in words:
                        if w["s"] < e - 0.05 and w["e"] > s + 0.05 and not w.get("filler"):
                            if w["s"] >= s - 0.05: w["s"] = round(min(e, w["e"] - 0.05), 3)   # starts with the um: start after it
                            elif w["e"] <= e + 0.05: w["e"] = round(s, 3)  # word ends with the um: end before it
                    words.append({"text": txt.strip(",.").lower() or "um", "s": round(s, 3), "e": e, "filler": True})
        words.sort(key=lambda w: w["s"])
    keep = proposal["proposedCut"]
    proposed_cut = [i for i, w in enumerate(words) if not w.get("filler") and
                    not any(a <= (w["s"] + w["e"]) / 2 <= b for a, b in keep)]
    # pauses Claude keeps on purpose: after a question or exclamation, or longer than 0.8 s after a sentence end
    keep_pauses = [i for i in range(len(words) - 1) if re.search(r"[?!]$", words[i]["text"]) or
                   (re.search(r"[.]$", words[i]["text"]) and words[i + 1]["s"] - words[i]["e"] > 0.8)]
    acc = set(proposal.get("accentWords", []))
    mode = brand.get("captions", {}).get("mode", "phrase")
    caps, cur = [], []
    for i, w in enumerate(words):
        if w.get("filler"): continue
        cur.append(i)
        nxt = next((j for j in range(i + 1, len(words)) if not words[j].get("filler")), None)
        if mode == "word" and len(cur) == 1 and nxt and pairs_forward(w["text"], words[nxt]["text"], words[nxt]["s"] - w["e"], brand): continue
        if mode == "word" or len(cur) >= 3 or re.search(r"[.,!?;:]$", w["text"]) or (nxt and words[nxt]["s"] - w["e"] > 0.35):
            caps.append({"w": cur, "acc": [k for k in cur if norm(words[k]["text"]) in acc]}); cur = []
    if cur: caps.append({"w": cur, "acc": [k for k in cur if norm(words[k]["text"]) in acc]})
    board = []
    for c in proposal["cards"]:
        hits = [i for i, w in enumerate(words) if norm(w["text"]) == norm(c["anchor"]) and w["s"] >= c.get("after", 0)]
        if not hits: print("warning: anchor not found:", c["id"], c["anchor"]); continue
        g = {k: v for k, v in c.items() if k not in ("anchor", "after", "end_anchor")}
        g["w0"] = hits[0]
        if c.get("end_anchor"):
            e = [i for i, w in enumerate(words) if norm(w["text"]) == norm(c["end_anchor"]) and i >= hits[0]]
            if e: g["w1"] = e[0]
        board.append(g)
    reel_json = {"title": proposal["title"], "srcDur": float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                 "format=duration", "-of", "csv=p=0", str(raw_clip(reel))], capture_output=True, text=True).stdout),
                 "theme": _theme(brand), "handle": brand.get("handle", ""), "speed": pacing(brand)["speed"], "pacing": pacing(brand), "words": words, "proposedCut": proposed_cut, "keepPauses": keep_pauses,
                 "captions": caps, "board": board,
                 "style": {"capSize": brand["captions"].get("size", 104), "capY": brand["captions"].get("y", 1250),
                           "mode": mode, "editorial": brand["captions"].get("style") == "editorial",
                           "cap": brand["colors"].get("caption", "#FFFFFF"), "acc": brand["colors"].get("caption_accent", "#FF7DB8"), "acc2": brand["colors"].get("caption_accent_2"),
                           "main": brand["colors"]["main"], "case": brand["captions"].get("case", "lower")},
                 "grade": brand.get("grade"), "look": brand.get("text_look"), "titleColor": brand.get("title_color", brand["colors"]["main"]), "titleY": brand.get("title_y", 360),
                 **({"face": json.load(open(reel / "face.json"))["box"]} if (reel / "face.json").exists() else {}),
                 "fontChoices": {**(brand.get("caption_fonts") or {}), "names": {r: (brand.get("fonts", {}).get(r) or {}).get("family", "") for r in ("body", "accent")}}}   # face: scripts/face_box.py; fontChoices: the design system's other caption fonts
    P = node(reel_json, {"cut": proposed_cut})
    print(f"{len(words)} words ({sum(1 for w in words if w.get('filler'))} fillers), {len(caps)} captions, {len(board)} graphics, "
          f"proposed cut {P['cutDur']:.1f}s, {len(P['pauses'])} pauses ({len(keep_pauses)} kept on purpose)")
    json.dump(reel_json, open(out / "reel.json", "w"))
    return reel_json

def _overlap(a, b):   # two graphics clash when they share screen time AND screen area (full-screen ones clash with everything)
    if a["start"] >= b["end"] or b["start"] >= a["end"]: return False
    (ax, ay, aw, ah), (bx, by, bw, bh) = a.get("place") or [0, 0, 1080, 1920], b.get("place") or [0, 0, 1080, 1920]
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah

def list_overlays(reel, review):
    """Round 1 of the review: they place their own photos/videos first. This prints each one in cut time and source
    time (with the word it hangs on), so the graphics plan in proposal.json can leave those moments and areas free."""
    reel_json = json.load(open(reel / "review_reel.json"))
    d = json.load(open(review)) if Path(review).exists() else {}
    d = {"restoredFillers": [], "restoredPauses": [], "trimmedPauses": [], "board": {}, "sfxOff": {}, "overlays": [], **d}
    if d.get("cut") is None: d["cut"] = reel_json["proposedCut"]
    if d.get("captions") is None: d["captions"] = reel_json["captions"]
    P = node(reel_json, d)
    W = reel_json["words"]
    mine = [g for g in P["graphics"] if g.get("user") and not g.get("gone") and g["state"] != "d"]
    for g in mine:
        w = W[g["w0"]]
        print(f"OVERLAY {g['id']}: cut {g['start']:.1f}-{g['end']:.1f}s, from word \"{w['text']}\" (source {w['s']:.1f}s), "
              f"box {g.get('place')}, {g.get('mode')}/{g.get('effect')}, {g.get('what', '')}")
    for g in P["graphics"]:
        if g.get("user") or g.get("gone") or g["state"] == "d": continue
        for o in mine:
            if _overlap(g, o): print(f"CONFLICT: {g['id']} ({g.get('kind')}) overlaps their overlay {o['id']} at cut {max(g['start'], o['start']):.1f}s: move or drop it")
    print(f"{len(mine)} overlay(s) placed")

def do_import(reel, review):
    reel_json = json.load(open(reel / "review_reel.json"))
    d = json.load(open(review)) if Path(review).exists() else {}
    # same defaults as the page's blank() + decisions(), so the build's fingerprint matches what the page computes
    d = {"restoredFillers": [], "restoredPauses": [], "trimmedPauses": [], "board": {}, "sfxOff": {}, "overlays": [], **d}
    if d.get("cut") is None: d["cut"] = reel_json["proposedCut"]          # [] is a real decision ("cut nothing"), not "unset"
    if d.get("captions") is None: d["captions"] = reel_json["captions"]
    P = node(reel_json, d)
    if P.get("grade"):   # her colour grade from the page: the tone curve goes to <reel>/grade.cube, the chain into edl.json
        (reel / "grade.cube").write_text(P["cube"]); P["grade"] = P["grade"].replace("__CUBE__", str((reel / "grade.cube").resolve()))
    clean = d.get("voiceClean") is not False
    if not clean: print("VOICE: keep the original sound, no clean-up (the final loudness is still levelled)")
    if P.get("grade"): print("GRADE (set on the page, goes into edl.json, cut.py applies it):", d.get("grade"))
    json.dump({"source": raw_clip(reel).name, "audio": "voice.wav" if clean else raw_clip(reel).name, "keep": [[round(a, 3), round(b, 3)] for a, b in P["spans"]],
               **({"grade": P["grade"]} if P.get("grade") else {})},
              open(reel / "edl.json", "w"))
    caps = [{"start": round(c["start"], 3), "end": round(c["end"], 3), **({"y": c["y"]} if c.get("y") is not None else {}),
             "words": [{"text": re.sub(r"[.,!?;:]+$", "", w["text"]), "t": round(w["t"], 3), "accent": w["accent"]} for w in c["words"]]}
            for c in P["captions"] if not c.get("gone")]
    cards, changes, overlays = [], [], []
    for g in P["graphics"]:
        if g.get("gone") or g["state"] == "d": continue
        note = ((d.get("board") or {}).get(g["id"]) or {}).get("note")
        if g["state"] == "c": changes.append(f"{g['id']} @ cut {g['start']:.1f}s: {note or '(no note)'}")
        spec = {k: v for k, v in g.items() if k not in ("id", "kind", "what", "w0", "w1", "state", "place", "moved", "gone", "own", "shifted", "capsAside")}
        if g.get("capsAside"): spec["quiet"] = True   # captions step aside while this card shows (no room for both)
        if g.get("shifted") and g.get("type") in ("motion", "custom") and not g.get("user"):
            pass   # catalog motions keep their tested placement (band / split / full, see build_reel); the page only shifts their preview box
        elif g.get("shifted"):   # core.js moved it off the face / captions: the render uses the new spot
            if g.get("type") in ("card", "tag", "title", "bigtext", "cta"):
                spec["y"] = g["place"][1]
                if g.get("zoom"): spec["x"] = g["place"][0]   # shrunk to fit above the head (behind the person)
            elif g.get("type") in ("motion", "custom", "shot", "image"): spec["box" if g["type"] in ("motion", "custom") else "y"] = g["place"] if g["type"] in ("motion", "custom") else g["place"][1]
        spec.update(start=round(g["start"], 3), end=round(g["end"], 3), id=g["id"])
        if (d.get("sfxSwap") or {}).get(g["id"]) and isinstance(spec.get("sfx"), dict): spec["sfx"] = {**spec["sfx"], "name": d["sfxSwap"][g["id"]]}
        if g["id"] in (d.get("sfxOff") or {}) and d["sfxOff"][g["id"]]: spec["sfx"] = False
        if g.get("type") == "overlay":   # uploaded on the page: Claude downloads the asset into <reel>/overlays/ before rendering
            spec = {k: v for k, v in spec.items() if k not in ("imgUrl", "user", "media")}
            spec["src"] = f"overlays/{g['assetId']}"
            have = list((reel / "overlays").glob(g["assetId"] + ".*")) if (reel / "overlays").exists() else []
            overlays.append(f"{g['id']} @ cut {g['start']:.1f}-{g['end']:.1f}s, {g['mode']}, {g.get('what', '')}: "
                            + ("file ready" if have else f"DOWNLOAD asset {g['assetId']} into {reel / 'overlays'}"))
        cards.append(spec)
    punch, last = [], -9.0   # punch-ins on sentence starts in the cut, at most every ~6 s (emphasis, not every line)
    for c in caps:
        if c["start"] - last > 6: punch.append(c["start"]); last = c["start"]
    extra = {}
    cy = d.get("capY") if d.get("capY") is not None else (reel_json.get("style") or {}).get("capY")
    if cy is not None and cy != json.load(open(HOME / "brand.json")).get("captions", {}).get("y", 1250): extra["caption_y"] = cy   # this reel's own caption height
    if d.get("capSize") is not None: extra["caption_size"] = d["capSize"]   # the caption size she picked for this reel
    page_look = {k: v for k, v in (d.get("look") or {}).items() if k in ("cap", "hook", "txt") and v}   # text look from «Субтитри» / the hook block / «Накладення» text (only what she changed)
    base_look = json.load(open(HOME / "brand.json")).get("text_look") or {}                      # her saved default («Робити так у всіх наступних рілсах»)
    look = {k: {**base_look.get(k, {}), **page_look.get(k, {}), **({"acc": {**base_look.get(k, {}).get("acc", {}), **page_look.get(k, {}).get("acc", {})}} if k == "cap" else {}),
                **({"l2": {**base_look.get(k, {}).get("l2", {}), **page_look.get(k, {}).get("l2", {})}} if k == "hook" else {})} for k in set(base_look) | set(page_look)}
    if look:
        extra["text_look"] = look; print("TEXT LOOK:", json.dumps(look, ensure_ascii=False))
        if page_look and (d.get("look") or {}).get("keep"):   # becomes the brand default (reel.json "look" on the next reels)
            bp = HOME / "brand.json"; bj = json.load(open(bp)); bj["text_look"] = look
            json.dump(bj, open(bp, "w"), ensure_ascii=False, indent=2); print("TEXT LOOK saved to brand.json for the next reels")
    if d.get("speedMul"): extra["motion_mul"] = d["speedMul"]; print("MOTION SPEED for this reel: x" + str(d["speedMul"]))   # «Повільніше / Швидше» on «Графіка»
    st = d.get("style")   # the editing style she picked on «Графіка» (~/reels/styles/<name>.json); "brand" = brand.json only
    if st:
        (reel / "style.txt").write_text("" if st == "brand" else st)
        if st != "brand": extra["style"] = st
        print("STYLE:", "brand only" if st == "brand" else st)
    if d.get("capFont"):   # caption fonts she picked (Google Fonts with Ukrainian letters): downloaded once into ~/reels/fonts/google
        import urllib.request
        out = {}
        for role, f in d["capFont"].items():
            if not f or not (f.get("gf") or f.get("brandFile")): continue
            dst = HOME / "fonts" / f["brandFile"] if f.get("brandFile") else HOME / "fonts" / "google" / (re.sub(r"\W+", "-", f["gf"]).strip("-") + ".ttf")
            if not dst.exists() and f.get("gf"):
                dst.parent.mkdir(parents=True, exist_ok=True)
                css = urllib.request.urlopen(f"https://fonts.googleapis.com/css2?family={f['gf']}&display=swap").read().decode()
                urllib.request.urlretrieve(re.search(r"url\((https://[^)]+\.ttf)\)", css).group(1), dst)
            out[role] = {"family": f["family"], "file": str(dst), "weight": f.get("weight", 400), "style": f.get("style", "normal")}
            print(f"CAPTION FONT ({role}): {f['family']} -> {dst.name}")
        if out: extra["caption_fonts"] = out
    json.dump({"captions": caps, "punch": punch, "cards": cards, "hash": P["hash"], **extra}, open(reel / "edit.json", "w"), indent=1)
    print(f"cut {P['cutDur']:.1f}s from {len(P['spans'])} spans; {len(caps)} captions; {len(cards)} graphics; hash {P['hash']}")
    for c in changes: print("CHANGE REQUESTED:", c)
    for o in overlays: print("OVERLAY:", o)
    for n in d.get("cutNotes") or []:   # notes she left on the cut video at step 2 (cut seconds): fix the cut before the draft
        print(f"CUT NOTE @ cut {n['t']:.1f}s: {n['text']}")
    if (d.get("hook") or "").strip(): print("HOOK (their text, use as is):", d["hook"].strip())
    if ((d.get("cta") or {}).get("text") or "").strip(): print("CTA (their text):", d["cta"]["text"].strip())
    users = [g for g in P["graphics"] if g.get("user") and not g.get("gone") and g["state"] != "d"]
    for g in P["graphics"]:
        if not g.get("user") and not g.get("gone") and g["state"] != "d":
            for o in users:
                if _overlap(g, o): print(f"CONFLICT: {g['id']} ({g.get('kind')}) overlaps their overlay {o['id']} at cut {max(g['start'], o['start']):.1f}s: move or drop it before rendering")
    W = reel_json["words"]
    for e in sorted(d.get("effects") or [], key=lambda e: e.get("at", 0)):   # effects they asked for on the page («Ефекти»)
        w = W[e["w0"]] if 0 <= e.get("w0", -1) < len(W) else {"text": "?", "s": 0}
        files = "; ".join(f"{f['name']} -> DOWNLOAD asset {f['id']} into {reel / 'effects'}" for f in e.get("files") or [])
        print(f"EFFECT REQUESTED @ cut {e.get('at', 0):.1f}s for {e.get('dur', 3)}s, from word \"{w['text']}\" (source {w['s']:.1f}s): {e['text']}"
              + (f" | files: {files}" if files else ""))
    for k, n in (d.get("notes") or {}).items():
        if n.strip(): print(f"NOTE ({k}):", n.strip())
    for k, files in (d.get("refs") or {}).items():   # reference pictures/videos she attached to a section's note
        for f in files or []:
            have = list((reel / "refs").glob(f["id"] + ".*")) if (reel / "refs").exists() else []
            print(f"REFERENCE ({k}): {f.get('name')} -> " + ("file ready" if have else f"DOWNLOAD asset {f['id']} into {reel / 'refs'}"))
    if (d.get("brandRequest") or "").strip(): print("BRAND CHANGE REQUESTED (only apply if confirmed):", d["brandRequest"].strip())
    for r in d.get("revisions") or []: print(f"REVISION @ cut {r['t']:.1f}s:", r["text"])

if __name__ == "__main__":
    cmd, reel = sys.argv[1], Path(sys.argv[2]).expanduser()
    if cmd == "export":
        r = export(reel, json.load(open(sys.argv[3])), Path(sys.argv[4]))
        json.dump(r, open(reel / "review_reel.json", "w"))
    elif cmd == "import": do_import(reel, sys.argv[3])
    elif cmd == "overlays": list_overlays(reel, sys.argv[3])
    else: sys.exit(__doc__)
