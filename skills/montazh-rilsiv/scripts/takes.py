#!/usr/bin/env python3
"""Best take of every sentence when she records a line several times («скажу ще раз», false starts, the whole text twice).
Usage: python3 takes.py <reel> [--script script.txt] [--no-face]
  reads  <reel>/transcript.json (transcribe.py: Scribe words), <reel>/facescan.json (facescan.py, optional),
         a script if she has one (--script, or <reel>/script.txt): numbered or plain lines, one sentence or more each
  writes <reel>/takes.json (every attempt, its problems, the pick) and prints the take table in Ukrainian
  prints PROPOSED_CUT: the picked takes as [[srcStart, srcEnd], ...] in script order: put it into proposal.json "proposedCut"
Without a script the sentences come from the recording itself: a phrase that the next minute says again (or finishes)
is an earlier attempt of it. Picks follow ghost-editor's rules (MIT, github.com/kurbaitaev/ghost-editor,
references/take-selection.md; itself after mariagorskikh/talking-head-reel, MIT):
  - a complete attempt beats a partial one; fewer stumbles, fillers and restarts inside it;
  - fewer real look-aways (facescan: head turned, reading, eyes shut), never blinks or quick glances;
  - later over earlier when equal (people warm up);
  - a run of picked sentences that sit back to back in the recording stays one span (one cut instead of four).
She always confirms: the table is a proposal for the «Нарізка» step, never a cut on its own."""
import argparse, difflib, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pacing import pacing, is_filler, lang
import facescan

HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()
LETTERS = "a-zа-яіїєґё0-9'’\\-"
MUTTER = re.compile(r"\b(ще раз|ще разок|заново|спочатку|стоп|again|one more|еще раз|сначала)\b")


def norm(t):
    t = t.lower().replace("ё", "е").replace("’", "'")
    return re.sub(rf"[^{LETTERS}]+", "", t).strip("-'")


def toks(s):
    return [x for x in (norm(w) for w in re.split(r"\s+", s)) if x]


def wsim(a, b):
    """word equality that forgives endings (Ukrainian inflection) and small mishearings"""
    if a == b: return 1.0
    if len(a) >= 4 and len(b) >= 4 and a[:4] == b[:4]: return 0.8
    r = difflib.SequenceMatcher(None, a, b).ratio()
    return r if r >= 0.72 else 0.0


def sw(u, w, mask=None):
    """Smith-Waterman of unit tokens u against spoken tokens w (masked positions never match) -> (score, path)"""
    n, m = len(u), len(w)
    mask = mask or [False] * m
    S = [[0.0 if mask[j] else wsim(u[i], w[j]) for j in range(m)] for i in range(n)]
    H = [[0.0] * (m + 1) for _ in range(n + 1)]; T = [[0] * (m + 1) for _ in range(n + 1)]
    best, bi, bj = 0.0, 0, 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = S[i - 1][j - 1]
            d = H[i - 1][j - 1] + (2.0 * s if s > 0 else -1.0)
            up = H[i - 1][j] - 0.8          # a script word she didn't say
            lf = H[i][j - 1] - 0.6          # an extra spoken word (stumble, repeat, filler)
            v = max(0.0, d, up, lf); H[i][j] = v
            T[i][j] = 0 if v == 0 else (1 if v == d else (2 if v == up else 3))
            if v > best: best, bi, bj = v, i, j
    i, j, path = bi, bj, []
    while i > 0 and j > 0 and T[i][j] != 0:
        t = T[i][j]
        if t == 1: path.append((i - 1, j - 1, S[i - 1][j - 1] > 0)); i -= 1; j -= 1
        elif t == 2: path.append((i - 1, None, False)); i -= 1
        else: path.append((None, j - 1, False)); j -= 1
    return best, path[::-1]


def units_from_script(p):
    U, n = [], 0
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line: continue
        m = re.match(r"(\d+)[.)]\s*(.*)", line)
        n, body = (int(m.group(1)), m.group(2)) if m else (n + 1, line)
        parts = re.split(r"(?<=[.!?…»])\s+(?=[«A-ZА-ЯІЇЄҐ])", body)
        merged = []
        for x in parts:                              # sentences under 4 words go with the next one (lists stay whole)
            if merged and len(toks(merged[-1])) < 4: merged[-1] += " " + x
            else: merged.append(x)
        if len(merged) > 1 and len(toks(merged[-1])) < 4: merged[-2] += " " + merged.pop()
        for k, x in enumerate(merged):
            U.append({"id": f"{n}" + ("" if len(merged) == 1 else "abcdefgh"[k]), "text": x, "toks": toks(x)})
    return U


def phrases(W, gap=0.35):
    """spoken phrases: break at a pause >= gap or after a sentence end; «окей, ще раз» between them is dropped"""
    P, cur = [], []
    for k, w in enumerate(W):
        if cur and (w["start"] - W[k - 1]["end"] >= gap or re.search(r"[.!?…]$", W[k - 1]["text"])):
            P.append(cur); cur = []
        cur.append(k)
    if cur: P.append(cur)
    out = []
    for p in P:                                       # split at a mutter inside a phrase, drop the mutter words
        s = " ".join(W[k]["n"] for k in p)
        m = MUTTER.search(s)
        if not m: out.append(p); continue
        i0 = len(s[:m.start()].split()); i1 = len(s[:m.end()].split())
        while i0 > 0 and W[p[i0 - 1]]["n"] in ("окей", "ок", "так", "ні", "добре", "ok", "okay", "блін"): i0 -= 1
        out += [x for x in (p[:i0], p[i1:]) if x]
    return out


def units_from_recording(W, P, fillers=(), L="uk"):
    """no script: a phrase is an earlier attempt of a later phrase that says most of it again within ~60 s"""
    T = [[W[k]["n"] for k in p if W[k]["n"] and not is_filler(W[k]["text"], fillers, L)] for p in P]
    parent = list(range(len(P)))
    find = lambda x: x if parent[x] == x else find(parent[x])
    for i in range(len(P)):
        if len(T[i]) < 2: continue
        for j in range(i + 1, len(P)):
            if W[P[j][0]]["start"] - W[P[i][-1]]["end"] > 60: break
            if not T[j]: continue
            _, path = sw(T[i], T[j])
            hit = sum(1 for x in path if x[2])
            if hit >= 2 and hit >= 0.6 * len(T[i]):
                parent[find(i)] = find(j); break
    groups = {}
    for i in range(len(P)): groups.setdefault(find(i), []).append(i)
    U = []
    for root, members in sorted(groups.items(), key=lambda g: min(g[1])):
        if len(members) == 1 and len(T[members[0]]) <= 4 and MUTTER.search(" ".join(T[members[0]])):
            continue                                              # «окей, ще раз», «стоп, заново»: not a line
        full = max(members, key=lambda i: (len(T[i]), i))         # the fullest version names the sentence
        U.append({"id": str(len(U) + 1), "text": " ".join(W[k]["text"] for k in P[full]), "toks": T[full], "members": members})
    return U


def inner_restart(ws):
    """a restart inside one attempt («я хочу, я хочу сказати»): (i, k) = the first k words from word i are said twice;
    the first saying (words i..i+k-1) is the one to drop"""
    n = [w["n"] for w in ws]
    for k in (4, 3, 2, 1):
        for i in range(0, min(6, len(n) - 2 * k + 1)):
            if n[i:i + k] == n[i + k:i + 2 * k] and (k > 1 or len(n[i]) > 2):
                return i, k
    return None


def describe(W, j0, j1, unit, fillers, L, face):
    ws = W[j0:j1 + 1]
    _, path = sw(unit["toks"], [w["n"] for w in ws])
    matched = [x for x in path if x[2]]
    n = max(1, len(unit["toks"]))
    ui = [x[0] for x in matched]
    gaps = [round(ws[k + 1]["start"] - ws[k]["end"], 2) for k in range(len(ws) - 1)]
    fil = [w["text"] for w in ws if is_filler(w["text"], fillers, L)]
    extra = [ws[x[1]]["text"] for x in path if x[0] is None and not is_filler(ws[x[1]]["text"], fillers, L)]
    rs = inner_restart(ws)
    a, b = ws[0]["start"], ws[-1]["end"]
    skip = None
    if rs is not None:
        i, k = rs
        if i == 0: a = ws[k]["start"]; j0 += k       # start on the clean repeat
        else: skip = [j0 + i, j0 + i + k - 1]        # words before it stay, the first saying goes
    bad = facescan.badframes(face, a, b) if face else []
    badsec = round(sum(y - x for x, y, _ in bad), 2)
    complete = bool(ui) and len(matched) >= 0.85 * n and min(ui) <= 1 and max(ui) >= n - 2
    score = (0 if complete else 6) + 1.0 * len(fil) + 0.5 * len(extra) + (1.5 if rs is not None else 0) \
        + (1.0 if gaps and max(gaps) > 1.0 else 0) + 2.0 * badsec + 0.5 * (1 - len(matched) / n)
    return {"a": round(a, 2), "b": round(b, 2), "j0": j0, "j1": j1, "skip": skip, "said": " ".join(w["text"] for w in ws),
            "cov": round(len(matched) / n, 2), "complete": complete, "fillers": fil, "extra": extra,
            "restart": rs is not None, "maxgap": max(gaps) if gaps else 0, "face": bad, "face_sec": badsec, "score": round(score, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reel"); ap.add_argument("--script"); ap.add_argument("--no-face", action="store_true")
    A = ap.parse_args()
    reel = Path(A.reel).expanduser()
    brand = json.load(open(HOME / "brand.json")) if (HOME / "brand.json").exists() else {}
    L, fillers = lang(brand), pacing(brand).get("fillers", [])
    raw = json.load(open(reel / "transcript.json"))
    raw = raw.get("words", raw) if isinstance(raw, dict) else raw
    W = [{"text": w["text"].strip(), "start": float(w["start"]), "end": float(w["end"]), "n": norm(w["text"])} for w in raw if w["text"].strip()]
    W = [w for w in W if w["n"] or re.search(r"[.!?…]$", w["text"])]
    face = [] if A.no_face else facescan.load(reel)
    script = A.script or (str(reel / "script.txt") if (reel / "script.txt").exists() else None)
    P = phrases(W)
    out = []
    if script:
        U = units_from_script(script)
        wt = [w["n"] for w in W]
        for u in U:
            mask, found, n = [False] * len(W), [], len(u["toks"])
            while True:
                score, path = sw(u["toks"], wt, mask)
                matched = [x for x in path if x[2]]
                if score < max(3.0, 0.9 * n) or len(matched) < max(2, 0.3 * n): break
                js = [x[1] for x in path if x[1] is not None]
                j0, j1 = min(js), max(js)
                for j in range(j0, j1 + 1): mask[j] = True
                found.append(describe(W, j0, j1, u, fillers, L, face))
            out.append({"id": u["id"], "text": u["text"], "attempts": sorted(found, key=lambda x: x["a"])})
    else:
        for u in units_from_recording(W, P, fillers, L):
            att = [describe(W, P[i][0], P[i][-1], u, fillers, L, face) for i in u["members"]]
            out.append({"id": u["id"], "text": u["text"], "attempts": att})
    # the pick: lowest score, later wins a tie (within 0.5)
    for u in out:
        A_ = u["attempts"]
        if not A_: u["pick"] = None; continue
        lo = min(x["score"] for x in A_)
        u["pick"] = max((k for k, x in enumerate(A_) if x["score"] <= lo + 0.5), key=lambda k: A_[k]["a"])
    # spans in script order; picks that sit back to back in the recording merge into one run
    spans = []
    for u in out:
        if u["pick"] is None: continue
        x = u["attempts"][u["pick"]]
        if spans and spans[-1]["j1"] + 1 >= x["j0"] and 0 <= x["a"] - spans[-1]["b"] < 1.2:
            spans[-1].update(b=x["b"], j1=x["j1"]); spans[-1]["ids"].append(u["id"])
        else:
            spans.append({"a": x["a"], "b": x["b"], "j0": x["j0"], "j1": x["j1"], "ids": [u["id"]]})
        if x.get("skip"):                             # split around a restart's first saying
            s0, s1 = x["skip"]; last = spans[-1]
            spans[-1] = {**last, "b": W[s0 - 1]["end"], "j1": s0 - 1}
            spans.append({"a": W[s1 + 1]["start"], "b": last["b"], "j0": s1 + 1, "j1": last["j1"], "ids": [u["id"]]})
    cut = []
    for s in spans:                                   # breathing room, never into a neighbouring word
        prev_end = W[s["j0"] - 1]["end"] if s["j0"] > 0 else 0.0
        next_start = W[s["j1"] + 1]["start"] if s["j1"] + 1 < len(W) else s["b"] + 0.3
        cut.append([round(max(prev_end + 0.02, s["a"] - 0.12), 2), round(min(next_start - 0.02, s["b"] + 0.25), 2)])
    json.dump({"script": script, "units": out, "proposedCut": cut}, open(reel / "takes.json", "w"), ensure_ascii=False, indent=1)
    multi = sum(1 for u in out if len(u["attempts"]) > 1)
    for u in out:
        if len(u["attempts"]) < 2 and not (u["attempts"] and (u["attempts"][0]["restart"] or u["attempts"][0]["face"])): continue
        print(f"\n[{u['id']}] {u['text'][:110]}")
        for k, x in enumerate(u["attempts"]):
            why = []
            if not x["complete"]: why.append(f"неповний ({int(x['cov'] * 100)}%)")
            if x["restart"]: why.append("почала заново всередині")
            if x["fillers"]: why.append("заповнювачі: " + " ".join(x["fillers"]))
            if x["extra"]: why.append("зайві слова: " + " ".join(x["extra"][:6]))
            if x["maxgap"] > 1.0: why.append(f"пауза {x['maxgap']:.1f} с")
            if x["face"]: why.append("погляд: " + ", ".join(f"{dict(turn='відвернулась', read='дивиться вниз', closed='очі закриті', noface='нема обличчя')[e[2]]} {e[0]:.1f}-{e[1]:.1f}" for e in x["face"][:3]))
            mark = "✅" if k == u["pick"] else "  "
            print(f"  {mark} {x['a']:7.2f}-{x['b']:7.2f}  {x['said'][:80]}" + (f"\n        {'; '.join(why)}" if why else ""))
    print(f"\n{len(out)} речень, {multi} записані кілька разів; обрано {len(cut)} шматків, {sum(b - a for a, b in cut):.1f} с"
          + ("" if face or A.no_face else "  (без перевірки погляду: запусти facescan.py)"))
    print("PROPOSED_CUT: " + json.dumps(cut))


if __name__ == "__main__":
    main()
