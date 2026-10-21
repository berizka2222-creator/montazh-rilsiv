#!/usr/bin/env python3
"""The tested HyperFrames motion library (references/motion_catalog.json): a menu by moment, ideas per phrase of a reel,
and a log so reels don't keep reusing the same few motions.
  menu [moment]          every ready motion, grouped by the moment it fits («цифра», «список», «CTA», ...)
  ideas <reel>           per phrase of the cut reel (master_transcript.json): 1-3 fitting motions, the ones used in the
                         last reels and in this reel's edit.json pushed down, so each reel gets fresh ones
  log <reel>             record the motions this reel's edit.json uses (run after the final is delivered)
  recent                 what the last reels used
Every entry in the catalog was rendered on a real reel with Ukrainian text in the brand colours and fonts before it was
marked ready. A motion's "card" block is its tested placement (box / scale / tone); copy it, then set start, end and
vars (her words). "replace" motions have English text baked in: the "replace" keys listed in the catalog are the exact
strings to swap for her words."""
import json, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAT = json.load(open(HERE.parent / "references" / "motion_catalog.json"))
READY = [m for m in CAT["motions"] if m.get("status") in ("ready", "replace")]
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
    if any(m["status"] == "brand" for m in READY) and not moment:
        print("\n[бренд] = Remotion-елемент: ~/motion/scripts/render-overlay.sh <Element> '<props>' <reel>/overlays/brand-<Element>-<slug>.webm,"
              "\n          картка {\"type\": \"overlay\", \"brand\": \"<Element>\", \"src\": ..., \"start\": .., \"end\": ..}")
    manual = [m for m in CAT["motions"] if m.get("status") == "manual"]
    if manual and not moment:
        print(f"\n## тільки вручну ({len(manual)}): дрібні у вертикальному кадрі, лише коли людина сама попросить")
        for m in manual: print(f"  {m['name']:26s} {m['ua']}")


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


def ideas(reel):
    reel = Path(reel).expanduser()
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
    for ph in phrases:
        text = " ".join(w["text"] for w in ph)
        moments = [mo for mo, rx in CUES if re.search(rx, text.lower())]
        if not moments: continue
        pool = [m for m in READY if set(m["moments"]) & set(moments)]
        # fresh first: not in this reel, not in the last reels, offered least so far
        order = {mo: k for k, mo in enumerate(moments)}           # the more specific moment (a number before a key phrase) first
        pool.sort(key=lambda m: (m["name"] in used_here, m["name"] in rec, min(order.get(x, 99) for x in m["moments"]),
                                 offered.get(m["name"], 0), m.get("rank", 5)))
        picks = pool[:3]
        for m in picks: offered[m["name"]] = offered.get(m["name"], 0) + 1
        print(f"{ph[0]['start']:6.1f}s  [{', '.join(moments)}]  {text[:90]}")
        for m in picks: print(f"         -> {m['name']}: {m['ua']}" + ("  [render-overlay.sh, картка overlay + \"brand\"]" if m["status"] == "brand" else ""))


def log(reel):
    reel = Path(reel).expanduser()
    names = sorted(card_names(json.load(open(reel / "edit.json"))))
    d = [e for e in log_data() if e["reel"] != reel.name] + [{"reel": reel.name, "at": int(time.time()), "motions": names}]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    json.dump(d[-30:], open(LOG, "w"), ensure_ascii=False, indent=1)
    print(f"logged {len(names)} motions for {reel.name}: {', '.join(names) or '-'}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "menu"
    if cmd == "menu": menu(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "ideas": ideas(sys.argv[2])
    elif cmd == "log": log(sys.argv[2])
    elif cmd == "recent":
        for e in log_data()[-RECENT_REELS:]: print(e["reel"], ", ".join(e["motions"]))
    else: sys.exit(__doc__)
