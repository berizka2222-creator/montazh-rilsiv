#!/usr/bin/env python3
"""Candidates for «врізки під кожну фразу»: splits the cut reel's speech into phrases and finds, in each one,
the brands/services she names (-> real logo from Simple Icons, or a live screenshot of the site) and the numbers
she says (-> stat / count-up). It only PROPOSES: you still pick one insert per phrase and write the cards in edit.json.
Nothing is ever drawn or invented: a brand with no official logo and no screenshot becomes a text tag.

Usage: python3 inserts.py <reel> [--fetch]
  reads  <reel>/master_transcript.json (falls back to transcript.json)
  writes <reel>/inserts.json, prints one line per phrase
  --fetch downloads logos to <reel>/logos/<slug>.svg and screenshots to <reel>/shots/<slug>.png"""
import json, re, subprocess, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SI = "https://cdn.jsdelivr.net/npm/simple-icons@16.35.0/icons/{}.svg"   # pinned: logos never change under a reel

# stem (lowercase; Cyrillic matched by prefix so cases/endings work, Latin by whole word) -> (simple-icons slug or None, label, site for a screenshot or None)
BRANDS = [
    (("zoom", "зум"), "zoom", "Zoom", "https://zoom.us"),
    (("chatgpt", "gpt", "чатgpt", "чатгпт", "гпт", "gpt-шн"), None, "ChatGPT", None),          # no official logo in Simple Icons, chatgpt.com blocks bots
    (("openai",), None, "OpenAI", "https://openai.com"),
    (("claude", "клод"), "claude", "Claude", None),
    (("gemini", "джеміні", "джемені"), "googlegemini", "Gemini", None),
    (("instagram", "інстаграм", "інста", "инстаграм"), "instagram", "Instagram", None),
    (("facebook", "фейсбук", "фб"), "facebook", "Facebook", None),
    (("meta",), "meta", "Meta", None),                                                       # Cyrillic «мета» = «goal»: never matched
    (("ads manager", "адс менеджер", "менеджер реклами", "рекламн кабінет", "кабінет"), "meta", "Ads Manager", None),
    (("піксел", "пиксел", "pixel"), "meta", "Meta Pixel", None),
    (("threads", "тредс", "тредз"), "threads", "Threads", None),
    (("tiktok", "тікток", "тик ток", "тікт"), "tiktok", "TikTok", None),
    (("telegram", "телеграм", "телега", "тг"), "telegram", "Telegram", None),
    (("youtube", "ютуб", "ютюб"), "youtube", "YouTube", None),
    (("whatsapp", "ватсап", "вотсап"), "whatsapp", "WhatsApp", None),
    (("google ads", "гугл адс"), "googleads", "Google Ads", None),
    (("google", "гугл"), "google", "Google", None),
    (("notion", "ноушн", "ноушен"), "notion", "Notion", None),
    (("figma", "фігма", "фигма"), "figma", "Figma", None),
    (("canva", "канва", "канві", "канву"), None, "Canva", "https://www.canva.com"),
    (("capcut", "капкат", "кепкат"), None, "CapCut", "https://www.capcut.com"),
    (("shopify", "шопіфай"), "shopify", "Shopify", None),
]

UNITS = {"нуль": 0, "один": 1, "одна": 1, "одного": 1, "одну": 1, "два": 2, "дві": 2, "двох": 2, "три": 3, "трьох": 3, "чотири": 4, "чотирьох": 4,
         "п'ять": 5, "пять": 5, "п'яти": 5, "шість": 6, "шести": 6, "сім": 7, "семи": 7, "вісім": 8, "восьми": 8, "дев'ять": 9, "дев'яти": 9,
         "десять": 10, "десяти": 10, "одинадцять": 11, "дванадцять": 12, "п'ятнадцять": 15, "двадцять": 20, "двадцяти": 20, "тридцять": 30,
         "тридцяти": 30, "сорок": 40, "сорока": 40, "п'ятдесят": 50, "п'ятдесяти": 50, "шістдесят": 60, "сімдесят": 70, "сімдесяти": 70,
         "семидесяти": 70, "вісімдесят": 80, "дев'яносто": 90, "сто": 100, "ста": 100, "двісті": 200, "двохсот": 200, "триста": 300, "п'ятсот": 500}
SCALE = {"тисяч": 1000, "тисяча": 1000, "тисячі": 1000, "тисячу": 1000, "тис": 1000, "мільйон": 10 ** 6, "мільйони": 10 ** 6, "мільйонів": 10 ** 6}
UNIT_WORDS = ("відсот", "процент", "%", "рок", "рік", "учн", "клієнт", "доллар", "долар", "$", "грн", "гривень", "заявк", "лід", "підписник",
              "хвилин", "годин", "днів", "день", "тижн", "місяц", "разів", "рази", "курс")

def norm(w): return re.sub(r"[^\w'%$-]", "", w.lower().replace("’", "'"))

def phrases(words, gap=0.35, max_len=4.5):
    """Split on punctuation and pauses; long runs split again so every 2-4 s has its own phrase."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        end_p = w["text"].rstrip().endswith((".", "!", "?", ",", ";", ":", "—")) and len(cur) >= 3
        if nxt is None or end_p or nxt["start"] - w["end"] > gap or w["end"] - cur[0]["start"] > max_len:
            out.append(cur); cur = []
    merged = []   # «А це» (0.4 s) is not a phrase of its own: glue anything under 1.2 s to the next one
    for ph in out:
        if merged and merged[-1][-1]["end"] - merged[-1][0]["start"] < 1.2: merged[-1] += ph
        else: merged.append(ph)
    return merged

def find_brands(ph):
    toks = [norm(w["text"]) for w in ph]
    hits, seen = [], set()
    for j, t in enumerate(toks):
        two = f"{t} {toks[j + 1]}" if j + 1 < len(toks) else ""
        for stems, slug, label, site in BRANDS:
            ok = any((two.startswith(s) if " " in s else (t == s if s.isascii() and not s.endswith("-шн") else t.startswith(s))) for s in stems)
            if ok and label not in seen:
                seen.add(label); hits.append({"kind": "logo" if slug else ("shot" if site else "tag"), "label": label, "slug": slug, "site": site, "t": ph[j]["start"]})
                break
    return hits

def find_numbers(ph):
    toks = [norm(w["text"]) for w in ph]
    hits, j = [], 0
    while j < len(toks):
        t, val, k = toks[j], None, j
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(%|\+|k|к)?", t)
        if m:
            val, k = float(m.group(1).replace(",", ".")), j + 1
            if m.group(2) in ("k", "к"): val *= 1000
        elif t in UNITS or t in SCALE:
            val, k = 0, j
            last = 10 ** 9   # «сто сімдесят» = 170, but «два, три» is a list, not 5: add only a smaller order after a bigger one
            while k < len(toks) and (toks[k] in UNITS or toks[k] in SCALE):
                if toks[k] in SCALE: val = (val or 1) * SCALE[toks[k]]; last = SCALE[toks[k]]
                else:
                    u = UNITS[toks[k]]
                    if val and not (u < last and len(str(u)) < len(str(last))): break
                    val += u; last = u
                k += 1
        if val is not None and (val >= 3 or (k < len(toks) and toks[k].startswith(UNIT_WORDS))):   # «один-два» alone is speech, not a stat
            unit = next((toks[x] for x in list(range(k, min(k + 2, len(toks)))) + [j - 1] if x >= 0 and toks[x].startswith(UNIT_WORDS)), "")   # «відсотків двадцять» too
            hits.append({"kind": "stat", "value": int(val) if float(val).is_integer() else val, "unit": unit, "t": ph[j]["start"],
                         "said": " ".join(w["text"] for w in ph[j:k + (1 if unit else 0)])})
            j = max(k, j + 1)
        else:
            j += 1
    return hits

def fetch(reel, cands):
    for c in cands:
        if c["kind"] == "logo":
            p = reel / "logos" / f"{c['slug']}.svg"; p.parent.mkdir(exist_ok=True)
            if not p.exists():
                try: p.write_bytes(urllib.request.urlopen(SI.format(c["slug"]), timeout=20).read())
                except Exception as e: print(f"  logo {c['slug']}: {e}", file=sys.stderr); continue
            c["src"] = str(p.relative_to(reel))
        elif c["kind"] == "shot":
            p = reel / "shots" / f"{c['label'].lower().replace(' ', '-')}.png"; p.parent.mkdir(exist_ok=True)
            if p.exists() or subprocess.run(["bash", str(HERE / "screenshot.sh"), c["site"], str(p)], capture_output=True).returncode == 0:
                c["src"] = str(p.relative_to(reel))
            else:
                c["kind"] = "tag"; c["note"] = "screenshot blocked: text tag instead, or ask her for her own screenshot"

def main():
    reel = Path(sys.argv[1]).expanduser()
    tf = next((p for p in (reel / "master_transcript.json", reel / "transcript.json") if p.exists()), None)
    if not tf: sys.exit("no master_transcript.json / transcript.json in the reel folder")
    words = [w for w in json.load(open(tf)) if w.get("text", "").strip()]
    rows = []
    for ph in phrases(words):
        c = find_brands(ph) + find_numbers(ph)
        rows.append({"start": round(ph[0]["start"], 2), "end": round(ph[-1]["end"], 2), "text": " ".join(w["text"] for w in ph), "candidates": c})
    if "--fetch" in sys.argv:
        fetch(reel, [c for r in rows for c in r["candidates"]])
    json.dump({"source": tf.name, "phrases": rows}, open(reel / "inserts.json", "w"), ensure_ascii=False, indent=1)
    n = sum(1 for r in rows if r["candidates"])
    for r in rows:
        tags = "; ".join(f"{c['kind']}:{c.get('label') or c.get('value')}{(' ' + c['unit']) if c.get('unit') else ''}{' ✓' if c.get('src') else ''}" for c in r["candidates"])
        print(f"{r['start']:6.2f}-{r['end']:6.2f}  {r['text'][:70]:<70}  {tags}")
    print(f"\n{len(rows)} phrases, {n} with a ready logo/screenshot/number; the rest need a text insert (tag/bigtext/list) or nothing. -> {reel / 'inserts.json'}")

if __name__ == "__main__":
    main()
