#!/usr/bin/env python3
"""Style lab: the person's own editing style, built in rounds of rendered variants they rate (Залишити / Можливо / Прибрати).
Round 1 = 9 whole-look directions on one 5-second fragment of their own video; later rounds go element by element
(captions, hook, lists, numbers, split, transitions, cta, sounds, motion), one change per variant, same words.
Output: ~/reels/styles/<name>.json (read by build_reel.py) + ~/reels/styles/STYLE.md (Затверджено / Можливо / Відхилено).

  fragment <reel-folder | clip> <start> <end> [--hook "line / line"]   cut the 5 s the rounds are made on (-> styles/_lab/fragment)
  round <round.json>                    render every variant at 540p (-> styles/_lab/rounds/<id>/: <sec>.<var>.mp4/.jpg, page.json)
  directions [--id ID] [--only a,b]     write round 1 from the 9 direction archetypes, in their brand (then run `round`)
  element <style> <element> [--id ID]   write the round.json for one element of a style from the catalogue (then run `round`)
  page <round-dir> <uploads.json>       page.json + uploaded urls ({file name: url}) -> doc.json for ArtifactData set style/round
  votes <round-dir> <votes.json>        print her verdicts (the page's style/votes doc) in plain words
  apply <round-dir> <votes.json>        write the verdicts into styles/*.json and STYLE.md
  list                                  the styles on this account

round.json: {"id", "round", "kind": "directions"|"elements", "style"?: base style name (elements), "title", "lede"?,
  "cards"?: [...], "sections": [{"id", "title", "what", "cards"?, "variants": [{"id", "title", "what", "style": {..}, "cards"?}]}]}
  cards are build_reel cards in fragment time; a variant's own cards win over its section's, those over the round's.
  directions: "style" is the whole look; elements: "style" is a patch on the base style (one change)."""
import json, os, re, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
STYLES = HOME / "styles"
LAB = STYLES / "_lab"
FRAG = LAB / "fragment"
ROUNDS = LAB / "rounds"
ELEMENT_UA = {"direction": "напрям", "captions": "субтитри", "hook": "хук", "lists": "списки", "numbers": "цифри",
              "split": "розбивки екрану", "transitions": "переходи", "cta": "CTA", "sounds": "звуки", "motion": "швидкість руху"}


def merge(a, b, union=False):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict): out[k] = merge(out[k], v, union)
        elif union and isinstance(v, list) and isinstance(out.get(k), list): out[k] = out[k] + [x for x in v if x not in out[k]]
        else: out[k] = v
    return out


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# ---- fragment -----------------------------------------------------------------------------------------------------
def fragment(src, start, end, hook=None):
    """A short piece of their own video with its words: from a reel folder (master.mp4 + master_transcript.json + face.json)
    or from a raw clip (transcribed with scripts/transcribe.py, face found with face_box.py)."""
    src = Path(src).expanduser()
    if FRAG.exists(): shutil.rmtree(FRAG)
    FRAG.mkdir(parents=True)
    clip = src / "master.mp4" if src.is_dir() else src
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(clip),
        "-vf", "scale=540:960:force_original_aspect_ratio=increase,crop=540:960", "-r", "30", "-c:v", "libx264", "-crf", "18",
        "-preset", "veryfast", "-g", "15", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(FRAG / "master.mp4")])
    if src.is_dir() and (src / "master_transcript.json").exists():
        words = [{**w, "start": round(w["start"] - start, 3), "end": round(w["end"] - start, 3)}
                 for w in json.load(open(src / "master_transcript.json")) if w["start"] >= start - 0.05 and w["start"] < end - 0.1 and w["end"] <= end + 0.2]
        json.dump(words, open(FRAG / "master_transcript.json", "w"), ensure_ascii=False, indent=1)
        if (src / "face.json").exists(): shutil.copy(src / "face.json", FRAG / "face.json")
    else:
        sh([sys.executable, str(HERE / "transcribe.py"), str(FRAG / "master.mp4"), str(FRAG / "master_transcript.json")])
        subprocess.run([sys.executable, str(HERE / "face_box.py"), str(FRAG)])   # macOS only; without it graphics aren't moved off the face
    words = json.load(open(FRAG / "master_transcript.json"))
    info = {"src": str(src), "start": start, "end": end, "dur": round(end - start, 2), "hook": hook,
            "text": " ".join(w["text"] for w in words),
            "graphic": None, "transition_at": None, "number": None, "cta": None, "accents": []}
    json.dump(info, open(FRAG / "fragment.json", "w"), ensure_ascii=False, indent=1)
    print(f"fragment: {FRAG} ({info['dur']} s): {info['text']}")
    print("fill fragment.json: hook (their text, never invented), graphic {start,end,title?,rows,row_times} on spoken words,"
          " transition_at, accents (words), number/cta if the fragment has them")


def captions(words, brand, accents):
    """Captions for the fragment in the brand's mode: one word (short words paired with the next) or 2-3 word phrases."""
    mode, pair = brand.get("captions", {}).get("mode", "word"), brand.get("captions", {}).get("pair_short", 0)
    acc = {re.sub(r"\W", "", a.lower()) for a in accents}
    out, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        nxt = words[k + 1] if k + 1 < len(words) else None
        short = len(re.sub(r"\W", "", w["text"])) <= pair and nxt is not None and len(cur) == 1
        brk = mode == "word" and not short or mode != "word" and (len(cur) >= 3 or re.search(r"[.,!?;:]$", w["text"]))
        if brk or nxt is None or nxt["start"] - w["end"] > 0.35:
            out.append({"start": cur[0]["start"], "end": nxt["start"] if nxt else w["end"] + 0.3,
                        "words": [{"text": x["text"].strip(".,!?;:"), "t": x["start"], "accent": re.sub(r"\W", "", x["text"].lower()) in acc} for x in cur]})
            cur = []
    return out


def render_variant(vdir, style, cards, frag):
    for f in ("master.mp4", "master_transcript.json", "face.json"):
        if (FRAG / f).exists() and not (vdir / f).exists(): os.symlink(FRAG / f, vdir / f)
    json.dump(style, open(vdir / "style.json", "w"), ensure_ascii=False, indent=1)
    brand = merge(json.load(open(HOME / "brand.json")), style.get("brand", {}))
    words = json.load(open(FRAG / "master_transcript.json"))
    edit = {"style": str(vdir / "style.json"), "captions": captions(words, brand, frag.get("accents", [])), "punch": [], "cards": cards}
    json.dump(edit, open(vdir / "edit.json", "w"), ensure_ascii=False, indent=1)
    env = {**os.environ, "REEL_DRAFT": "1", "REEL_WORKERS": os.environ.get("REEL_WORKERS", "1")}
    r = subprocess.run(["bash", str(HERE / "render.sh"), str(vdir)], env=env, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith(("style:", "safe zone:", "warning", "variety:")): print("   ", line)
    if r.returncode or not (vdir / "draft.mp4").exists():
        print((r.stdout + r.stderr)[-1500:]); raise SystemExit(f"render failed: {vdir}")


def run_round(path):
    spec = json.load(open(path))
    frag = json.load(open(FRAG / "fragment.json"))
    base = json.load(open(STYLES / f"{spec['style']}.json")) if spec.get("style") else {}
    out = ROUNDS / spec["id"]; out.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, out / "round.json")
    page = {k: spec.get(k) for k in ("id", "round", "kind", "style", "title", "lede")}
    page["sections"] = []
    for sec in spec["sections"]:
        ps = {"id": sec["id"], "title": sec["title"], "what": sec.get("what", ""), "variants": []}
        for var in sec["variants"]:
            vid = f"{sec['id']}.{var['id']}"
            style = var.get("style", {}) if spec.get("kind") == "directions" else merge(base, var.get("style", {}))
            cards = var.get("cards") or sec.get("cards") or spec.get("cards") or []
            vdir = out / vid
            if vdir.exists(): shutil.rmtree(vdir)
            vdir.mkdir()
            print(f"render {vid}: {var['title']}")
            render_variant(vdir, {"title": var["title"], **style}, json.loads(json.dumps(cards)), frag)
            shutil.copy(vdir / "draft.mp4", out / f"{vid}.mp4")
            sh(["ffmpeg", "-v", "error", "-y", "-ss", str(min(2.5, frag["dur"] / 2)), "-i", str(vdir / "draft.mp4"), "-frames:v", "1",
                "-vf", "scale=270:480", "-q:v", "4", str(out / f"{vid}.jpg")])
            shutil.rmtree(vdir / "proj", ignore_errors=True)
            ps["variants"].append({"id": vid, "title": var["title"], "what": var.get("what", ""), "file": f"{vid}.mp4", "poster": f"{vid}.jpg"})
        page["sections"].append(ps)
    json.dump(page, open(out / "page.json", "w"), ensure_ascii=False, indent=1)
    files = [str(out / f"{v['id']}{x}") for s in page["sections"] for v in s["variants"] for x in (".mp4", ".jpg")]
    print(f"round {spec['id']}: {sum(len(s['variants']) for s in page['sections'])} variants -> {out}")
    print("upload (Artifact asset: true, file_paths):"); print("\n".join(files))


def page_doc(rdir, uploads):
    rdir = Path(rdir).expanduser(); up = json.load(open(uploads))
    doc = json.load(open(rdir / "page.json"))
    brand = json.load(open(HOME / "brand.json"))
    for s in doc["sections"]:
        for v in s["variants"]:
            v["url"], v["posterUrl"] = up[v.pop("file")], up.get(v.pop("poster"))
    doc["handle"] = brand.get("handle")
    sys.path.insert(0, str(HERE)); from review_sync import _theme
    doc["theme"] = _theme(brand)   # the page takes their colours even before any reel is loaded
    from datetime import datetime, timezone
    doc["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(doc, open(rdir / "doc.json", "w"), ensure_ascii=False, indent=1)
    print(f"{rdir / 'doc.json'}: ArtifactData set style/round (file_path), then delete style/votes of the previous round")


# ---- verdicts -----------------------------------------------------------------------------------------------------
V_UA = {"keep": "Залишити", "maybe": "Можливо", "drop": "Прибрати"}


def read_votes(rdir, votes):
    rdir = Path(rdir).expanduser()
    page, spec = json.load(open(rdir / "page.json")), json.load(open(rdir / "round.json"))
    vt = json.load(open(votes)); vt = vt.get("data", vt)
    if vt.get("round") not in (None, page["id"]): sys.exit(f"these votes are for round {vt.get('round')}, not {page['id']}")
    V = vt.get("verdicts", {})
    var = {f"{s['id']}.{v['id']}": (s, v) for s in spec["sections"] for v in s["variants"]}
    return page, spec, V, var, vt


def show_votes(rdir, votes):
    page, spec, V, var, vt = read_votes(rdir, votes)
    for s in page["sections"]:
        print(f"{s['title']}:")
        for v in s["variants"]:
            x = V.get(v["id"], {})
            print(f"  {V_UA.get(x.get('v'), 'без оцінки'):10} {v['title']}" + (f"  · {x['note']}" if x.get("note") else ""))
    if vt.get("note"): print(f"Загальна нотатка: {vt['note']}")
    for r in vt.get("refs", []):   # links: yt-dlp them; files: Artifact read with path = id
        print(f"Референс ({r['kind']}): {r['url']}" + (f"  asset {r['id']} ({r.get('name', '')})" if r.get("id") else ""))


def apply(rdir, votes):
    page, spec, V, var, vt = read_votes(rdir, votes)
    STYLES.mkdir(exist_ok=True)
    n = spec.get("round", 1)
    if spec.get("kind") == "directions":
        keeps = [k for k in var if V.get(k, {}).get("v") == "keep"]
        rej = [{"element": "напрям", "what": var[k][1]["title"] + (": " + var[k][1].get("what", "") if var[k][1].get("what") else ""),
                "why": V[k].get("note", ""), "round": n} for k in var if V.get(k, {}).get("v") == "drop"]
        maybe = [{"element": "напрям", "what": var[k][1]["title"], "note": V[k].get("note", ""), "round": n, "style": var[k][1].get("style", {})}
                 for k in var if V.get(k, {}).get("v") == "maybe"]
        for k in keeps:
            sec, v = var[k]
            name = v.get("name") or v["id"]
            st = {**v.get("style", {}), "name": name, "title": v["title"], "what": v.get("what", ""),
                  "locked": [{"element": "напрям", "what": v["title"], "note": V[k].get("note", ""), "round": n}],
                  "maybe": [], "rejected": list(rej)}
            json.dump(st, open(STYLES / f"{name}.json", "w"), ensure_ascii=False, indent=1)
            print(f"style {name}: {v['title']} -> {STYLES / (name + '.json')}")
        state = {"round": n, "maybe": maybe, "rejected": rej}
        json.dump(state, open(LAB / "directions.json", "w"), ensure_ascii=False, indent=1)
        if not keeps: print("no direction kept: next round = the «Можливо» ones fixed by her notes (styles/_lab/directions.json), plus new ones")
    else:
        name = spec["style"]; p = STYLES / f"{name}.json"; st = json.load(open(p))
        for k, (sec, v) in var.items():
            x = V.get(k, {}); el = ELEMENT_UA.get(sec.get("element", sec["id"]), sec["title"])
            patch, note = v.get("style", {}), x.get("note", "")
            st["maybe"] = [m for m in st.get("maybe", []) if m.get("patch") != patch]
            if x.get("v") == "keep":
                st = merge(st, patch, union=True)
                st.setdefault("locked", []).append({"element": el, "what": v["title"], "note": note, "round": n, "patch": patch})
            elif x.get("v") == "drop":
                st.setdefault("rejected", []).append({"element": el, "what": v["title"], "why": note, "round": n, "patch": patch})
                for t in patch.get("_deny", []): st.setdefault("layouts", {}).setdefault("deny", []).append(t)
            elif x.get("v") == "maybe":
                st.setdefault("maybe", []).append({"element": el, "what": v["title"], "note": note, "round": n, "patch": patch})
        for key in ("list", "camera"):   # a look she dropped never stays allowed
            lay = st.get("layouts", {})
            if key in lay:
                gone = {x for r in st.get("rejected", []) for x in r.get("patch", {}).get("layouts", {}).get(key, [])}
                lay[key] = [x for x in lay[key] if x not in gone] or lay[key]
        st.pop("_deny", None)
        json.dump(st, open(p, "w"), ensure_ascii=False, indent=1)
        print(f"style {name} updated")
    write_md()


def describe(st):
    b, lay, cap, snd = st.get("brand", {}), st.get("layouts", {}), st.get("captions", {}), st.get("sounds", {})
    out = [f"- Швидкість руху: x{st.get('motion', {}).get('speed', 1)}",
           f"- Субтитри: поява «{cap.get('anim', 'pop')}», акцент «{cap.get('accent', 'color')}»"
           + (f", розмір {b['captions']['size']}" if b.get("captions", {}).get("size") else ""),
           f"- Хук: {'скляна панель' if b.get('title_glass') else 'без панелі'}" + (f", колір {b['title_color']}" if b.get("title_color") else "")]
    if lay.get("list"): out.append(f"- Списки: {', '.join(lay['list'])}")
    if lay.get("camera"): out.append(f"- Рухи камери: {', '.join(lay['camera'])}")
    for k in ("number", "split", "transition"):
        if lay.get(k): out.append(f"- {ELEMENT_UA.get(k, k)}: {', '.join(lay[k])}")
    if lay.get("deny"): out.append(f"- Не використовувати: {', '.join(sorted(set(lay['deny'])))}")
    if snd.get("events"): out.append("- Звуки: " + ", ".join(f"{e} = {s or 'тиша'}" for e, s in snd["events"].items()))
    return out


def write_md():
    styles = sorted(p for p in STYLES.glob("*.json"))
    brand = json.load(open(HOME / "brand.json"))
    L = ["# Стилі монтажу", "",
         f"Стиль за замовчуванням: {brand.get('style') or ('`' + styles[0].stem + '`' if len(styles) == 1 else 'питати перед кожним монтажем')}.",
         "Файли для скриптів: `~/reels/styles/<назва>.json`. Цей файл переписується після кожного раунду.", ""]
    for p in styles:
        st = json.load(open(p))
        L += [f"## {st.get('title', p.stem)} (`{p.stem}`)", ""] + ([st["what"], ""] if st.get("what") else []) + describe(st) + [""]
        L += ["### Затверджено"] + [f"- раунд {x['round']} · {x['element']}: {x['what']}" + (f" ({x['note']})" if x.get("note") else "") for x in st.get("locked", [])] + [""]
        if st.get("maybe"):
            L += ["### Можливо, доопрацювати"] + [f"- раунд {x['round']} · {x['element']}: {x['what']}" + (f": {x['note']}" if x.get("note") else "") for x in st["maybe"]] + [""]
        L += ["### Відхилено"] + ([f"- раунд {x['round']} · {x['element']}: {x['what'].rstrip('.')}" + (f". Причина: {x['why']}" if x.get("why") else "") for x in st.get("rejected", [])] or ["- поки нічого"]) + [""]
    dj = LAB / "directions.json"   # directions still open from round 1 («Можливо»): shown until a later round settles them
    if dj.exists() and json.load(open(dj)).get("maybe"):
        L += ["## Напрями на доопрацювання", ""] + [f"- {x['what']}" + (f": {x['note']}" if x.get("note") else "") for x in json.load(open(dj))["maybe"]] + [""]
    (STYLES / "STYLE.md").write_text("\n".join(L))
    print(f"{STYLES / 'STYLE.md'}")


# ---- round 1: nine direction archetypes, each recoloured and re-fonted from their own brand ----------------------------
def _fonts(brand):
    """Their display fonts: brand head/accent plus any extra files in brand.json "caption_fonts" (their design system)."""
    F = brand.get("fonts", {})
    extra = [f for f in (brand.get("caption_fonts", {}).get("body", []) + brand.get("caption_fonts", {}).get("accent", [])) if f.get("file")]
    seen, out = set(), []
    for f in extra:
        p = (HOME / "fonts" / f["file"])
        if p.exists() and f["file"] not in seen and "Gilroy" not in f["file"]:
            seen.add(f["file"]); out.append({"family": f["label"].split()[0], "file": str(p), "weight": f.get("weight", 400), "style": f.get("style", "normal")})
    return F.get("head"), F.get("accent"), out


def _sticker():
    for d in ("elements_clean", "elements"):
        pngs = sorted((HOME / "assets" / d).glob("*.png")) if (HOME / "assets" / d).exists() else []
        pngs = [x for x in pngs if not x.stem.startswith(("logo", "_"))]
        if pngs: return f"{d}/{pngs[min(2, len(pngs) - 1)].name}"
    return None


def directions(rid=None, only=None):
    """Round 1 for anyone: 9 looks (calm, editorial, scrapbook, chrome, magazine, notes, kinetic, quiet, split) on their
    fragment, in their colours and fonts. Edit the json after (swap a direction for one from their references) before `round`."""
    brand = json.load(open(HOME / "brand.json")); frag = json.load(open(FRAG / "fragment.json"))
    C = brand["colors"]; MAIN, POP, LIGHT = C["main"], C["pop"], C.get("light", "#FFFFFF"); SOFT = C.get("soft", POP)
    if not frag.get("hook"): sys.exit("fragment.json has no hook: ask them for their hook text (never invent it)")
    g = frag.get("graphic") or {}; rows, rt = g.get("rows", []), g.get("row_times")
    if not rows: sys.exit("fragment.json graphic.rows is empty: put the spoken words there")
    dur, T = frag["dur"], frag.get("transition_at") or round(frag["dur"] * 0.45, 2)
    gs, ge, ttl = g.get("start", round(dur * 0.6, 2)), g.get("end", dur), g.get("title", "")
    head, accent, extra = _fonts(brand)
    disp1 = extra[0] if extra else head                    # a second display face from their system, if they have one
    disp2 = extra[1] if len(extra) > 1 else disp1
    serif = {**accent, "weight": accent.get("weight", 400)} if accent and accent.get("file") else head
    stk = _sticker()
    hook = lambda **k: {"type": "title", "text": frag["hook"], "y": 1165, "size": 72, "start": 0, "end": min(2.2, dur * 0.45), **k}
    lst = lambda lay: {"type": "list", "layout": lay, "title": ttl, "rows": rows, "row_times": rt, "start": gs, "end": ge}
    words = " / ".join(rows[:2])
    A = [
     ("calm", "Спокійний преміум", "Повільний рух, субтитри проявляються з розмиття, хук і список на матовому склі, плавний наїзд камери, м'які звуки.",
      {"motion": {"speed": 0.8}, "captions": {"anim": "blur", "accent": "color"}, "brand": {"title_glass": True, "glass": True, "cta_glass": True},
       "layouts": {"list": ["card", "notes"], "camera": ["in", "out"]},
       "sounds": {"events": {"transition": "whoosh_soft", "row": "hit_soft", "title": "ding_glass", "accent": "chime", "hit": "hit_soft"}}},
      [hook(size=70), {"type": "camera", "move": "in", "scale": 1.12, "start": T, "end": dur}, lst("card")]),
     ("editorial", "Яскравий редакційний", "Швидко і різко: слова-акценти великі на плашці, хук кольором без панелі, різкий зум, панель наїжджає на кадр, удари.",
      {"motion": {"speed": 1.3}, "captions": {"anim": "slam", "accent": "box"},
       "brand": {"title_glass": False, "title_color": SOFT, "glass": False, "cta_glass": False, "cta_bg": SOFT, "captions": {"style": "editorial"}},
       "layouts": {"list": ["drop", "stack"], "camera": ["whip", "shake"]},
       "sounds": {"events": {"transition": "whoosh_fast", "row": "pop", "title": "snap", "hit": "hit_punch", "accent": "hit_punch"}}},
      [hook(size=76), {"type": "camera", "move": "whip", "start": T, "end": T + 0.8}, {"type": "push", "text": words, "color": SOFT, "y": 640, "start": gs, "end": ge}]),
     ("scrapbook", "Живий скрапбук", "Звичайний темп, субтитри виринають знизу з підкресленням акценту, кадр відʼїжджає, пункти-картки летять стосом, клацання й дзвіночки.",
      {"motion": {"speed": 1.0}, "captions": {"anim": "rise", "accent": "underline"},
       "brand": {"title_glass": False, "title_color": LIGHT, "glass": False, "cta_glass": False, "cta_bg": POP},
       "layouts": {"list": ["stack", "notes"], "camera": ["out", "shake"]},
       "sounds": {"events": {"transition": "swish", "row": "pop_pluck", "title": "page_turn", "accent": "ding", "hit": "pop_drop"}}},
      [hook(size=74), {"type": "camera", "move": "out", "start": T, "end": T + 0.9}, lst("stack")]),
     ("chrome", "Хромовий люкс", "Повільно й дорого: заголовки акцентним шрифтом, твій елемент, великі слова з'являються над головою.",
      {"motion": {"speed": 0.85}, "captions": {"anim": "blur", "accent": "color"},
       "brand": {"title_glass": False, "title_color": LIGHT, "fonts": {"head": serif}},
       "layouts": {"list": ["card", "notes"], "camera": ["in"]},
       "sounds": {"events": {"transition": "whoosh_air", "row": "ding_glass", "title": "chime", "accent": "chime", "hit": "hit_soft"}}},
      [hook(size=84), {"type": "camera", "move": "in", "scale": 1.1, "start": T, "end": dur}]
      + ([{"type": "sticker", "src": stk, "x": 820, "y": 430, "size": 190, "start": gs, "end": ge}] if stk else [])
      + [{"type": "bigtext", "text": rows[-1], "behind": True, "y": 240, "color": POP, "start": rt[-1] if rt else gs, "end": ge}]),
     ("magazine", "Журнальна обкладинка", "Інший шрифт з твоєї системи, субтитри фразами внизу на плашці, кадр стискається у вікно, над ним великі слова.",
      {"motion": {"speed": 1.0}, "captions": {"anim": "rise", "accent": "box"},
       "brand": {"title_glass": False, "title_color": SOFT, "captions": {"mode": "phrase", "size": 70, "y": 1300},
                 "colors": {"caption_accent": SOFT, "caption_accent_2": SOFT}, "fonts": {"head": disp1}},
       "layouts": {"list": ["drop", "stack"], "camera": ["shrink", "out"]},
       "sounds": {"events": {"transition": "page_turn", "row": "shutter", "title": "page_turn", "hit": "shutter"}}},
      [hook(), {"type": "camera", "move": "shrink", "text": words, "start": gs, "end": ge}]),
     ("notes", "Нотатки з телефона", "Живо, як UGC: дрібні субтитри фразами з підкресленням, лист нотаток з галочками, поштовх кадру, клацання.",
      {"motion": {"speed": 1.1}, "captions": {"anim": "pop", "accent": "underline"},
       "brand": {"title_glass": False, "title_color": LIGHT, "captions": {"mode": "phrase", "size": 64}},
       "layouts": {"list": ["notes", "stack"], "camera": ["shake", "out"]},
       "sounds": {"events": {"transition": "swipe", "row": "tap", "title": "click", "hit": "mouse_click", "typing": "typing"}}},
      [hook(size=64), lst("notes"), {"type": "camera", "move": "shake", "start": rt[-1] if rt else ge - 1}]),
     ("kinetic", "Кінетична типографіка", "Дуже швидко: великі субтитри вдаряють, хук кольором акценту, різкий зум, кольорова панель з великими словами на весь екран.",
      {"motion": {"speed": 1.5}, "captions": {"anim": "slam", "accent": "color"},
       "brand": {"title_glass": False, "title_color": POP, "captions": {"size": 110, "style": "editorial"}, "fonts": {"head": disp2}},
       "layouts": {"list": ["drop"], "camera": ["whip", "shake"]},
       "sounds": {"events": {"transition": "whoosh_fast", "row": "hit_punch", "title": "boom", "hit": "hit_punch", "accent": "hit_punch"}}},
      [hook(size=80), {"type": "camera", "move": "whip", "start": T, "end": T + 0.7}, {"type": "push", "text": words, "color": POP, "y": 640, "start": gs, "end": ge}]),
     ("quiet", "Тиша й повітря", "Мінімум: маленькі субтитри внизу, невеликий хук без панелі, камера не рухається, одна скляна пігулка, без звуків.",
      {"motion": {"speed": 0.9}, "captions": {"anim": "rise", "accent": "color"},
       "brand": {"title_glass": False, "title_color": LIGHT, "title_max_px": 80, "captions": {"size": 62, "y": 1360}},
       "layouts": {"list": ["card"], "camera": ["in"]}, "sounds": {"level": "none"}},
      [hook(size=56), {"type": "tag", "text": rows[-1], "glass": True, "y": 300, "start": rt[-1] if rt else gs, "end": ge}]),
     ("split", "Екран навпіл", "Екран ділиться: панель зі списком зверху, ти знизу; відʼїзд кадру, м'які звуки.",
      {"motion": {"speed": 1.0}, "captions": {"anim": "pop", "accent": "color"}, "brand": {"title_glass": True},
       "layouts": {"list": ["card", "drop"], "camera": ["out", "in"]},
       "sounds": {"events": {"transition": "whoosh_soft", "row": "pop", "title": "snap"}}},
      [hook(), {"type": "camera", "move": "out", "start": T, "end": T + 0.8}, {"type": "split", "title": ttl or rows[0], "rows": rows, "row_times": rt, "start": gs, "end": ge}]),
    ]
    if only: A = [a for a in A if a[0] in only]
    rid = rid or f"{(brand.get('handle') or 'style').lstrip('@')}-r1"
    spec = {"id": rid, "round": 1, "kind": "directions", "title": "Раунд 1 · напрями",
            "lede": f"{len(A)} напрямів на тих самих 5 секундах твого відео, усі в твоїх кольорах і шрифтах. Можна залишити кілька: кожен стане окремим стилем.",
            "sections": [{"id": "dir", "title": "Напрями", "what": "Субтитри, хук, одна графіка, один перехід і звуки разом.",
                          "variants": [{"id": i, "name": i, "title": t, "what": w, "style": st, "cards": cards} for i, t, w, st, cards in A]}]}
    LAB.mkdir(parents=True, exist_ok=True)
    out = LAB / f"{rid}.json"; json.dump(spec, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"{out}: {len(A)} directions. Swap any for one built from their references, then: python3 {Path(__file__).name} round {out}")


# ---- element rounds: one change per variant, same words ------------------------------------------------------------
def element_round(name, element, rid=None):
    st = json.load(open(STYLES / f"{name}.json"))
    frag = json.load(open(FRAG / "fragment.json"))
    brand = merge(json.load(open(HOME / "brand.json")), st.get("brand", {}))
    C = brand["colors"]; g = frag.get("graphic") or {}
    dur, hook = frag["dur"], frag.get("hook")
    T = frag.get("transition_at") or round(dur * 0.45, 2)
    gs, ge = g.get("start", round(dur * 0.55, 2)), g.get("end", dur)
    rows, rt = g.get("rows", []), g.get("row_times")
    hook_card = [{"type": "title", "text": hook, "start": 0, "end": min(2.0, dur * 0.4)}] if hook else []
    rejected = [r.get("patch") for r in st.get("rejected", [])]
    cap, lay, snd = st.get("captions", {}), st.get("layouts", {}), st.get("sounds", {})
    V = []   # (id, title, what, patch, cards)
    if element == "captions":
        cards = []
        for a in ("pop", "rise", "blur", "slam"):
            if a != cap.get("anim", "pop"): V.append((a, f"Поява: {a}", "як слово з'являється", {"captions": {"anim": a}}, cards))
        for a in ("color", "box", "underline"):
            if a != cap.get("accent", "color"): V.append(("acc-" + a, f"Акцент: {a}", "як виглядає слово-акцент", {"captions": {"accent": a}}, cards))
        size = brand.get("captions", {}).get("size", 84)
        V.append(("bigger", f"Більші: {int(size * 1.2)}", "розмір", {"brand": {"captions": {"size": int(size * 1.2)}}}, cards))
    elif element == "hook":
        if not hook: sys.exit("fragment.json has no hook: ask them for the hook text first")
        V += [("glass", "Скляна панель", "хук на матовому склі", {"brand": {"title_glass": True}}, hook_card),
              ("bare", "Без панелі", "білі великі слова", {"brand": {"title_glass": False, "title_color": C.get("light", "#FFFFFF")}}, hook_card),
              ("pop", "Кольором акценту", "слова в кольорі акценту", {"brand": {"title_glass": False, "title_color": C["pop"]}}, hook_card),
              ("high", "Високо над головою", "хук у верхній третині", {"brand": {"title_y": 300}}, hook_card)]
    elif element == "lists":
        if not rows: sys.exit("fragment.json graphic.rows is empty: put the spoken items there")
        for l, t in (("drop", "Пункти падають"), ("notes", "Нотатки айфона"), ("stack", "Картки стосом"), ("card", "Картка")):
            V.append((l, t, "той самий список", {"layouts": {"list": [l]}},
                      [{"type": "list", "layout": l, "title": g.get("title", ""), "rows": rows, "row_times": rt, "start": gs, "end": ge}]))
    elif element == "numbers":
        n = frag.get("number")
        if not n: sys.exit("fragment.json has no number (a figure they say): pick a fragment with one or skip numbers")
        V += [("count", "Лічильник", "цифра рахує до значення", {"layouts": {"number": ["count"]}},
               [{"type": "motion", "name": "count-up", "vars": {"start": 0, "end": n["value"], "suffix": n.get("suffix", ""), "accent": C["pop"]},
                 "box": [240, 1170, 600, 315], "start": n["t"], "end": min(dur, n["t"] + 2.5)}]),
              ("big", "Велика цифра", "на весь кадр", {"layouts": {"number": ["big"]}},
               [{"type": "bigtext", "text": n["text"], "start": n["t"], "end": min(dur, n["t"] + 2.2)}]),
              ("behind", "Цифра за тобою", "за головою", {"layouts": {"number": ["behind"]}},
               [{"type": "bigtext", "text": n["text"], "behind": True, "y": 300, "start": n["t"], "end": min(dur, n["t"] + 2.2)}]),
              ("shrink", "Кадр у вікно", "кадр зменшується, цифра зверху", {"layouts": {"number": ["shrink"]}},
               [{"type": "camera", "move": "shrink", "text": n["text"], "start": n["t"], "end": min(dur, n["t"] + 2.5)}])]
    elif element == "split":
        if not rows: sys.exit("fragment.json graphic.rows is empty")
        title = g.get("title") or rows[0]
        V += [("split-top", "Екран навпіл", "панель зверху, ти знизу", {"layouts": {"split": ["top"]}},
               [{"type": "split", "title": title, "rows": rows, "row_times": rt, "start": gs, "end": ge}]),
              ("split-left", "Навпіл збоку", "панель ліворуч", {"layouts": {"split": ["left"]}},
               [{"type": "split", "side": "left", "title": title, "rows": rows, "row_times": rt, "start": gs, "end": ge}]),
              ("push", "Наїзд кадру", "панель виштовхує кадр", {"layouts": {"split": ["push"]}, "_deny": ["push"]},
               [{"type": "push", "text": " / ".join(rows[:2]), "start": gs, "end": ge}]),
              ("steps", "Панелі-кроки", "панелі наїжджають", {"layouts": {"split": ["steps"]}, "_deny": ["steps"]},
               [{"type": "steps", "items": rows, "row_times": rt, "start": gs, "end": ge}])]
    elif element == "transitions":
        for m, t in (("out", "Відʼїзд"), ("in", "Повільний наїзд"), ("whip", "Різкий зум"), ("shrink", "Кадр у вікно"), ("shake", "Поштовх")):
            V.append((m, t, "перехід на тих самих словах", {"layouts": {"camera": [m]}}, hook_card + [{"type": "camera", "move": m, "start": T, "end": min(dur, T + 1.4)}]))
    elif element == "cta":
        cta = frag.get("cta")
        if not cta: sys.exit("fragment.json has no cta: ask them for their CTA words")
        card = [{"type": "cta", "text": cta, "start": max(0, dur - 2.6), "end": dur}]
        V += [("glass", "Скло", "матова скляна пігулка", {"brand": {"cta_glass": True}}, card),
              ("light", "Біла пігулка", "суцільна світла", {"brand": {"cta_glass": False, "cta_bg": C.get("light", "#FFFFFF")}}, card),
              ("pop", "Кольором акценту", "пігулка в кольорі акценту", {"brand": {"cta_glass": False, "cta_bg": C["pop"]}}, card),
              ("big", "Більша", "крупніший текст", {"brand": {"cta_px": int(brand.get("cta_px", 78) * 1.25)}}, card)]
    elif element == "sounds":
        cards = hook_card + [{"type": "camera", "move": (lay.get("camera") or ["out"])[0], "start": T, "end": min(dur, T + 1.2)}]
        if rows: cards.append({"type": "list", "layout": (lay.get("list") or ["drop"])[0], "title": g.get("title", ""), "rows": rows, "row_times": rt, "start": gs, "end": ge})
        for sid, t, ev in (("soft", "М'які", {"transition": "whoosh_soft", "row": "hit_soft", "title": "chime"}),
                           ("click", "Клацання", {"transition": "swish", "row": "click", "title": "snap"}),
                           ("punch", "Удари", {"transition": "whoosh_fast", "row": "pop", "title": "hit_punch"}),
                           ("air", "Повітря", {"transition": "whoosh_air", "row": "pop_pluck", "title": "ding_glass"}),
                           ("quiet", "Без звуків", None)):
            V.append((sid, t, "кожен звук на своїй появі", {"sounds": {"events": ev}} if ev else {"sounds": {"level": "none"}}, cards))
    elif element == "motion":
        cards = hook_card + [{"type": "camera", "move": (lay.get("camera") or ["out"])[0], "start": T, "end": min(dur, T + 1.2)}]
        if rows: cards.append({"type": "list", "layout": (lay.get("list") or ["drop"])[0], "title": g.get("title", ""), "rows": rows, "row_times": rt, "start": gs, "end": ge})
        for sp, t in ((0.75, "Повільніше"), (1.0, "Як є"), (1.3, "Швидше"), (1.6, "Дуже швидко")):
            if sp != st.get("motion", {}).get("speed", 1): V.append((f"x{sp}", t, f"швидкість руху x{sp}", {"motion": {"speed": sp}}, cards))
    else:
        sys.exit(f"unknown element {element}: " + ", ".join(k for k in ELEMENT_UA if k != "direction"))
    V = [v for v in V if v[3] not in rejected][:5]
    rnd = max([x.get("round", 1) for x in st.get("locked", []) + st.get("rejected", [])] + [1]) + 1
    rid = rid or f"{name}-r{rnd}-{element}"
    spec = {"id": rid, "round": rnd, "kind": "elements", "style": name,
            "title": f"Раунд {rnd} · {ELEMENT_UA[element]}", "lede": "У кожному варіанті змінено одну річ, слова ті самі.",
            "sections": [{"id": element, "element": element, "title": ELEMENT_UA[element].capitalize(), "what": "",
                          "variants": [{"id": i, "title": t, "what": w, "style": p, "cards": c} for i, t, w, p, c in V]}]}
    LAB.mkdir(parents=True, exist_ok=True)
    out = LAB / f"{rid}.json"; json.dump(spec, open(out, "w"), ensure_ascii=False, indent=1)
    print(f"{out}: {len(V)} variants. Next: python3 {Path(__file__).name} round {out}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    cmd = a[0]
    if cmd == "fragment":
        hook = a[a.index("--hook") + 1] if "--hook" in a else None
        fragment(a[1], float(a[2]), float(a[3]), hook)
    elif cmd == "round": run_round(Path(a[1]).expanduser())
    elif cmd == "directions": directions(a[a.index("--id") + 1] if "--id" in a else None, a[a.index("--only") + 1].split(",") if "--only" in a else None)
    elif cmd == "element": element_round(a[1], a[2], a[a.index("--id") + 1] if "--id" in a else None)
    elif cmd == "page": page_doc(a[1], a[2])
    elif cmd == "votes": show_votes(a[1], a[2])
    elif cmd == "apply": apply(a[1], a[2])
    elif cmd == "list":
        for p in sorted(STYLES.glob("*.json")):
            st = json.load(open(p)); print(f"{p.stem}: {st.get('title', '')}")
    else: sys.exit(__doc__)
