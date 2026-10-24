#!/usr/bin/env python3
"""The tested HyperFrames motion library (references/motion_catalog.json): a menu by moment, ideas per phrase of a reel,
and a log so reels don't keep reusing the same few motions.
  menu [moment]          every ready motion, grouped by the moment it fits («цифра», «список», «CTA», ...)
  ideas <reel>           per phrase of the cut reel (master_transcript.json): 1-3 fitting motions, the ones used in the
                         last reels and in this reel's edit.json pushed down, so each reel gets fresh ones
  log <reel>             record the motions this reel's edit.json uses (run after the final is delivered)
  stamp <reel>           «Мої марки»: add every graphic this finished reel kept (motion, brand element, template card,
                         camera move) to <REELS_HOME>/stamps.json with a still from the reel; ideas offers them first
  stamps                 list the collection
  recent                 what the last reels used
Every entry in the catalog was rendered on a real reel with Ukrainian text in the brand colours and fonts before it was
marked ready. A motion's "card" block is its tested placement (box / scale / tone); copy it, then set start, end and
vars (her words). "replace" motions have English text baked in: the "replace" keys listed in the catalog are the exact
strings to swap for her words."""
import json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAT = json.load(open(HERE.parent / "references" / "motion_catalog.json"))
# Statuses (references/motion_catalog.json "about"): ready / replace = checked in a real vertical reel, suggested;
# full_only = works only as a whole-frame takeover, suggested marked «на весь кадр» and below the overlays;
# manual = works but small or niche, only when the person asks; candidate = not checked in the frame yet, never suggested;
# skip = unusable. Brand elements (Remotion, below) are "brand" and suggested like ready ones.
SUGGEST = ("ready", "replace")
READY = [m for m in CAT["motions"] if m.get("status") in SUGGEST]
FULL = [m for m in CAT["motions"] if m.get("status") == "full_only"]
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
# Own motion library (Remotion project, ~/motion/library.json), only when it exists: suggested on equal terms with the catalog,
# as "brand:<Element>". They go in as transparent overlay cards with "brand": "<Element>" (how the log and "used here" see them).
BRAND_LIB = Path(os.environ.get("MOTION_HOME", "~/motion")).expanduser() / "library.json"
if BRAND_LIB.exists():
    for e in json.load(open(BRAND_LIB))["elements"]:
        READY.append({"name": f"brand:{e['element']}", "ua": f"[бренд] {e['ua']}", "moments": e["moments"], "status": "brand",
                      "text_vars": e.get("text_vars", []), "example": e.get("example", {}), "rank": 2})


def card_names(edit):
    """Motion names a reel's edit.json uses: catalog motions and brand elements (overlay cards with "brand")."""
    out = set()
    for c in edit.get("cards", []):
        if c.get("type") == "motion" and c.get("name"): out.add(c["name"])
        elif c.get("type") == "head": out.add(f"head-{c.get('look', 'window')}")   # «подачі голови» count like catalog motions
        elif c.get("type") == "overlay":
            b = c.get("brand") or (re.match(r"brand-([A-Za-z]+)", Path(c.get("src", "")).name) or [None, None])[1]
            if b: out.add(f"brand:{b}")
    return out
LOG = HOME / ".motion_log.json"
RECENT_REELS = 3


def log_data():
    return json.load(open(LOG)) if LOG.exists() else []


def recent_names():
    return {n for e in log_data()[-RECENT_REELS:] for n in e["motions"]}


TR_RULE = "шейдерні переходи (момент «перехід»): дуже активні, максимум 2 на рілс, лише на зміні теми, не на сусідніх склейках, щонайменше 12 с між ними; start = час склейки"


def menu(moment=None):
    by = {}
    for m in READY:
        for mo in m["moments"]:
            by.setdefault(mo, []).append(m)
    rec = recent_names()
    for mo in CAT["moments"]:
        if moment and moment not in mo: continue
        ms = by.get(mo, [])
        if not ms: continue
        print(f"\n## {mo} ({len(ms)})")
        for m in ms:
            flag = "  [був у останніх рілсах]" if m["name"] in rec else ""
            print(f"  {m['name']:26s} {m['ua']}{' · текст через replace' if m['status'] == 'replace' else ''}{flag}")
        if mo == "перехід": print(f"  ! {TR_RULE}")
    if any(m["status"] == "brand" for m in READY) and not moment:
        print("\n[бренд] = Remotion-елемент: ~/motion/scripts/render-overlay.sh <Element> '<props>' <reel>/overlays/brand-<Element>-<slug>.webm,"
              "\n          картка {\"type\": \"overlay\", \"brand\": \"<Element>\", \"src\": ..., \"start\": .., \"end\": ..}")
    full = [m for m in FULL if not moment or any(moment in x for x in m.get("moments", []))]
    if full:
        print(f"\n## на весь кадр ({len(full)}): займають увесь екран на 2-3 с, лише для повноекранних моментів")
        for m in full: print(f"  {m['name']:26s} {m['ua']}")
    st = stamps_data()
    if st and not moment:
        print(f"\n## мої марки ({len(st)}): ефекти з її готових рілсів, пропонувати першими")
        for x in st: print(f"  ★ {x['key']:26s} {x['ua']}  ×{x.get('uses', 1)}")
    manual = [m for m in CAT["motions"] if m.get("status") == "manual"]
    if manual and not moment:
        print(f"\n## тільки вручну ({len(manual)}): лише коли людина сама попросить")
        for m in manual: print(f"  {m['name']:26s} {m['ua']}")
    if not moment:
        n = {k: sum(1 for m in CAT["motions"] if m.get("status") == k) for k in ("candidate", "skip")}
        print(f"\n(ще не перевірені в кадрі: {n['candidate']}, не пропонуються; непридатні: {n['skip']})")


# words in a phrase -> the moment it calls for
CUES = [
    ("цифра", r"\d|відсот|%|тисяч|мільйон|долар|гривень|грн|\$|разів|раза|сто\b|двісті|сорок|тридцят|двадцят|п'ятдесят"),
    ("ріст / падіння", r"зріс|ріст|виріс|більше|впал|знизи|дешевш|дорожч|падає|росте|зменш|збільш"),
    ("список / кроки", r"по-перше|по-друге|перш|друг|трет|крок|етап|пункт|три речі|кілька|список"),
    ("до / після", r"було|стало|до того|після|раніше|тепер|замість"),
    ("питання / ШІ", r"chatgpt|чатгпт|gpt|claude|клод|джеміні|gemini|\bші\b|штучн|нейромереж|промпт"),
    ("повідомлення / чат", r"написал|пише|повідомлен|дірект|директ|direct|лист|заявк|сповіщен|чат|відповіл"),
    ("відгук / доказ", r"відгук|учениц|учень|клієнт|кейс|результат|зірк|рейтинг|довіря"),
    ("проблема / тиск", r"проблем|помилк|злив|хаос|не працю|перегор|стрес|забагато|завал"),
    ("ім'я / хто я", r"мене звати|я —|я таргет|я інна|мій досвід|років досвід|наставни"),
    ("заклик (CTA)", r"пиши|напиши|коментар|підпис|забирай|переходь|запис|посилан|в шапці|директ"),
    ("хук / ключова фраза", r"головне|важливо|секрет|запам'ятай|правило|ніколи|завжди|насправді|уяви|чесно"),
    ("успіх / готово", r"готово|вийшло|запустил|працює|успіх|окупил|продаж|ура"),
    ("картинки / приклади", r"приклад|подивись|ось так|скрін|сайт|сторінк|креатив|банер|відео"),
]


TEXT_ONLY = {"хук / ключова фраза", "цифра", "перехід", "до / після", "успіх / готово"}
TEXT_FX = {"typewriter", "scramble-reveal", "morph-text", "line-by-line-slide", "titlecard-lockup", "titlecard-calm", "tilt-card"}   # text effects tagged with other moments
def is_simple(m):
    """A plain text effect: one word / number / phrase animating over the video, no scene of its own. 2026-10-24: too
    many of these make a reel look basic, so ideas() puts the scenes first and a reel keeps them to a third of its motions."""
    return m.get("name") in TEXT_FX or (m.get("use") == "overlay" and m.get("status") != "brand" and set(m.get("moments", [])) <= TEXT_ONLY)


def ideas(reel):
    reel = Path(reel).expanduser().resolve()
    words = [w for w in json.load(open(reel / "master_transcript.json")) if w["text"].strip()]
    used_here = set()
    if (reel / "edit.json").exists():
        used_here = card_names(json.load(open(reel / "edit.json")))
    rec = recent_names()
    phrases, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 9
        if re.search(r"[.!?]$", w["text"]) or gap > 0.45 or len(cur) >= 14:
            phrases.append(cur); cur = []
    if cur: phrases.append(cur)
    offered = {}
    STAMPS_LIST = sorted(stamps_data(), key=lambda x: -x.get("uses", 1))
    for ph in phrases:
        text = " ".join(w["text"] for w in ph)
        moments = [mo for mo, rx in CUES if re.search(rx, text.lower())] or ["хук / ключова фраза"]   # any line can carry a text effect
        seen = set()
        pool = [m for m in READY + FULL if set(m["moments"]) & set(moments) and not (m["name"] in seen or seen.add(m["name"]))]
        # fresh first: not in this reel, not in the last reels, offered least so far
        order = {mo: k for k, mo in enumerate(moments)}           # the more specific moment (a number before a key phrase) first
        # scenes before plain text effects (is_simple), then fresh first
        pool.sort(key=lambda m: (m["name"] in used_here, m["name"] in rec, is_simple(m), min(order.get(x, 99) for x in m["moments"]),
                                 offered.get(m["name"], 0), -m.get("quality", 3), m.get("rank", 5)))
        rich = [m for m in pool if not is_simple(m)]
        # every phrase also gets scenes from any moment that fits a talking head (UI, chats, carousels, lower thirds, transitions)
        if len(rich) < 3:
            extra = [m for m in READY + FULL if not is_simple(m) and m["name"] not in {x["name"] for x in rich} and m["name"] not in used_here
                     and m.get("use") in ("ui", "full", "transition") and m["name"] not in rec]
            extra.sort(key=lambda m: (offered.get(m["name"], 0), -m.get("quality", 3)))
            rich += extra[:3 - len(rich)]
        picks = rich[:3] + [m for m in pool if is_simple(m)][:1]
        for m in picks: offered[m["name"]] = offered.get(m["name"], 0) + 1
        print(f"{ph[0]['start']:6.1f}s  [{', '.join(moments)}]  {text[:90]}")
        mine = [x for x in STAMPS_LIST if set(x["moments"]) & set(moments) and x["key"].split(":")[-1] not in used_here][:2]
        for x in mine: print(f"         ★ моя марка {x['key']}: {x['ua']}  (з рілса {x['reel']}, налаштування: {json.dumps(x['spec'], ensure_ascii=False)})")
        for m in picks: print(f"         -> {m['name']}: {m['ua']}" + (" [просте]" if is_simple(m) else " [складне]") + (f"  [текст: {', '.join(m['text_vars'])}]" if m.get("text_vars") else "") + (" [інтерфейс, свої кольори]" if m.get("keep_ui") else "") + (" [на весь кадр]" if m.get("status") == "full_only" else "")
                              + ("  [render-overlay.sh, картка overlay + \"brand\"]" if m["status"] == "brand" else ""))


# «Мої марки» (stamps): every graphic a finished reel kept, with a still from that reel and its tested settings.
# Collected after each final (stamp), offered first by ideas, shown on the review page («Ефекти» → «Мої марки»).
STAMPS = HOME / "stamps.json"
TEMPLATE_UA = {"title": "Хук-заголовок", "push": "Фірмова панель на весь кадр", "split": "Екран навпіл", "list": "Список",
               "steps": "Кроки один за одним", "bigtext": "Великі слова", "cta": "Заклик у кінці", "follow": "Картка підписки",
               "card": "Картка", "tag": "Плашка", "block": "Кольоровий блок", "camera": "Рух камери"}
CAMERA_UA = {"in": "наїзд", "out": "від'їзд", "whip": "різкий ривок", "shrink": "кадр у віконці", "shake": "трясіння"}
TEMPLATE_MOMENTS = {"title": ["хук / ключова фраза"], "bigtext": ["хук / ключова фраза"], "push": ["список / кроки", "хук / ключова фраза"],
                    "split": ["список / кроки", "ім'я / хто я"], "list": ["список / кроки"], "steps": ["список / кроки"],
                    "cta": ["заклик (CTA)"], "follow": ["заклик (CTA)", "ім'я / хто я"], "card": ["картинки / приклади"],
                    "tag": ["хук / ключова фраза"], "block": ["хук / ключова фраза"]}
KEEP = ("type", "name", "brand", "move", "layout", "side", "panel", "place", "tone", "behind", "glass", "shape", "scale", "box", "dim", "zoom", "ink", "css")


def stamps_data():
    return json.load(open(STAMPS)) if STAMPS.exists() else []


def stamp_key(c):
    t = c.get("type")
    if t == "motion": return f"motion:{c.get('name')}"
    if t == "overlay": return f"brand:{c['brand']}" if c.get("brand") else None   # their own photos / videos are not stamps
    if t == "camera": return f"camera:{c.get('move', 'in')}"
    v = c.get("layout") or c.get("side")
    return (f"{t}:{v}" if v else t) if t in TEMPLATE_UA else None


def stamp_info(c):
    t, cat = c.get("type"), {m["name"]: m for m in CAT["motions"]}
    if t == "motion": m = cat.get(c.get("name"), {}); return m.get("ua") or c.get("name"), m.get("moments") or []
    if t == "overlay":
        e = next((m for m in READY if m["name"] == f"brand:{c['brand']}"), {}); return e.get("ua") or c["brand"], e.get("moments") or []
    if t == "camera": return f"Рух камери: {CAMERA_UA.get(c.get('move'), c.get('move'))}", ["цифра"] if c.get("move") == "shrink" else ["хук / ключова фраза"]
    return TEMPLATE_UA.get(t, t) + (f" ({c.get('layout')})" if c.get("layout") else ""), TEMPLATE_MOMENTS.get(t, [])


def stamp(reel):
    reel = Path(reel).expanduser().resolve()
    edit = json.load(open(reel / "edit.json")); vid = next((reel / f for f in ("final.mp4", "draft.mp4") if (reel / f).exists()), None)
    data, new = stamps_data(), 0
    (HOME / "stamps").mkdir(parents=True, exist_ok=True)
    for c in edit.get("cards", []):
        k = stamp_key(c)
        if not k or c.get("_capgroups") is not None: continue
        old = next((x for x in data if x["key"] == k), None)
        if old:
            if reel.name not in old.setdefault("reels", [old["reel"]]): old["reels"].append(reel.name); old["uses"] = len(old["reels"]); old["last"] = reel.name
            continue
        ua, moments = stamp_info(c)
        sid = re.sub(r"[^a-z0-9]+", "-", k.lower()).strip("-")
        still = HOME / "stamps" / f"{sid}.jpg"
        if vid and not still.exists():
            a, b = float(c.get("start", 0)), float(c.get("end", c.get("start", 0) + 2))
            t = a + 0.45 if c.get("type") == "camera" else a + min(1.4, (b - a) * 0.6)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(vid), "-frames:v", "1", "-vf", "scale=360:-2", "-q:v", "4", str(still)])
        data.append({"key": k, "id": sid, "ua": ua, "moments": moments, "spec": {x: c[x] for x in KEEP if x in c},
                     "reel": reel.name, "reels": [reel.name], "last": reel.name, "uses": 1, "at": int(time.time()), "still": str(still) if still.exists() else None})
        new += 1
    json.dump(data, open(STAMPS, "w"), ensure_ascii=False, indent=1)
    print(f"stamps: {new} new from {reel.name}, {len(data)} in the collection ({STAMPS})")


def tr_hint(reel):
    """The cut points (edl.json) a shader transition could sit on, with the rule."""
    try:
        t, joins = 0.0, []
        for a, b in json.load(open(reel / "edl.json"))["keep"][:-1]:
            t += b - a; joins.append(f"{t:.1f}")
        print(f"\n{TR_RULE}\n  склейки: {', '.join(joins)} (обери 1-2 там, де починається нова думка)")
    except (OSError, KeyError, ValueError):
        pass


def log(reel):
    reel = Path(reel).expanduser().resolve()
    names = sorted(card_names(json.load(open(reel / "edit.json"))))
    d = [e for e in log_data() if e["reel"] != reel.name] + [{"reel": reel.name, "at": int(time.time()), "motions": names}]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    json.dump(d[-30:], open(LOG, "w"), ensure_ascii=False, indent=1)
    print(f"logged {len(names)} motions for {reel.name}: {', '.join(names) or '-'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "menu"
    if cmd == "menu": menu(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "ideas": ideas(sys.argv[2]); tr_hint(Path(sys.argv[2]).expanduser().resolve())
    elif cmd == "log": log(sys.argv[2])
    elif cmd == "stamp": stamp(sys.argv[2])
    elif cmd == "stamps":
        for x in stamps_data(): print(f"★ {x['key']:26s} {x['ua']}  ×{x.get('uses', 1)}  {x.get('still') or ''}")
    elif cmd == "recent":
        for e in log_data()[-RECENT_REELS:]: print(e["reel"], ", ".join(e["motions"]))
    else: sys.exit(__doc__)
