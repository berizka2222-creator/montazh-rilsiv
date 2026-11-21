#!/usr/bin/env python3
"""A reference reel read 2-3 ways: concepts with a 5-second sample on HER video and an honest cost, before the whole reel.
Idea from OpenMontage («2-3 differentiated concepts, cost estimates and a sample before full production»); own code on
style_lab.py's renderer (each reel gets its own lab folder, her style lab stays untouched).

  prep  <reel> <start> <end> --hook "her hook text"      the 5 s the samples are made on (from master.mp4 if the reel is cut,
                                                         else raw.*) -> <reel>/concepts/fragment/
  round <reel> <concepts.json>                           render every concept's sample at 540p, time it, price it
                                                         -> <reel>/concepts/rounds/<id>/<n>.mp4/.jpg + summary.md, upload list
  pick  <reel> <concept id> [--name ref-...] [--mix "captions from b"]
                                                         her pick becomes a style for this reel: ~/reels/styles/<name>.json
                                                         + <reel>/style.txt (build_reel reads it); --mix notes go into STYLE.md

concepts.json (Claude writes it after references/reference.md steps 1-3):
  {"id": "ref-<short>", "reel_seconds": 45, "reference": "<url>",
   "concepts": [{"id": "a", "title": "Темп", "takes": ["швидкі склейки кожні 1.4 с", "зум-удари на акцентах"],
                 "keeps": "її графіка і субтитри як завжди",
                 "style": {<a whole style json, as style_lab directions: motion, captions, brand, layouts, sounds>},
                 "cards": [<build_reel cards in fragment time: the hook + 1-2 graphics that show the concept>],
                 "full": {"graphics_per_min": 10, "behind_seconds": 4, "paid": ["Krea: 2 AI-вставки"], "new_motions": 0}}]}
  2 concepts when the reference is clear, 3 when it can be read more ways; never 3 shades of one idea: each takes a
  DIFFERENT thing from the reference (pace / caption look / structure / graphics / sound). Her colours and fonts always.
Cost per concept: sample render time measured here, the full reel's render estimated from it (final 1080 = 4x the pixels
of the 540 sample), cut-out seconds («за мною», ~13 s per second), graphics count, and anything paid (AI inserts) said plainly."""
import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser()


def lab(reel):
    return Path(reel).expanduser() / "concepts"


def run_lab(reel, *args):
    # samples are throwaway 5 s renders Claude looks at before sending; the full reel still goes through fx_check
    env = {**os.environ, "STYLE_LAB_DIR": str(lab(reel)), "REEL_NO_CHECK": "1"}
    return subprocess.run([sys.executable, str(HERE / "style_lab.py"), *args], env=env, check=True)


def prep(reel, start, end, hook):
    reel = Path(reel).expanduser()
    if not hook: sys.exit("--hook: her hook text (ask her; never invent it)")
    src = reel if (reel / "master.mp4").exists() else next(iter(sorted(reel.glob("raw.*"))), None)
    if not src: sys.exit(f"no master.mp4 or raw.* in {reel}")
    run_lab(reel, "fragment", str(src), str(start), str(end), "--hook", hook)
    print(f"now write {lab(reel) / '<id>.json'} (format in this script's header), then: ref_concepts.py round {reel} <that json>")


def mins(s):
    return f"{s / 60:.0f} хв" if s >= 90 else f"{s:.0f} с"


def round_(reel, path):
    reel = Path(reel).expanduser(); spec = json.load(open(path))
    C = spec["concepts"]
    if not 2 <= len(C) <= 3: sys.exit("2 or 3 concepts")
    rid = spec["id"]; L = lab(reel)
    out_dir = L / "rounds" / rid
    rows, files = [], []
    for c in C:
        one = {"id": rid, "round": 1, "kind": "directions", "title": f"Концепції за референсом",
               "sections": [{"id": "c", "title": "Концепції", "variants": [{"id": c["id"], "title": c["title"],
                             "what": "; ".join(c.get("takes", [])), "style": c["style"], "cards": c.get("cards", [])}]}]}
        tmp = L / f"_{rid}_{c['id']}.json"; json.dump(one, open(tmp, "w"), ensure_ascii=False, indent=1)
        t0 = time.time(); run_lab(reel, "round", str(tmp)); dt = time.time() - t0
        frag = json.load(open(L / "fragment" / "fragment.json"))
        full = c.get("full", {}); secs = float(spec.get("reel_seconds") or 45)
        sample_cut = 13 * sum(max(0, k.get("end", 0) - k.get("start", 0)) for k in c.get("cards", []) if k.get("behind"))
        base = max(5.0, dt - sample_cut)                             # the sample's own cut-out is priced below, not scaled up
        render = base * secs / max(1.0, frag["dur"]) * 4 * 0.6      # 4x pixels; ~0.6: one-off setup in the sample's time
        cut = 13 * float(full.get("behind_seconds", 0))
        rows.append({"id": c["id"], "title": c["title"], "takes": c.get("takes", []), "keeps": c.get("keeps", ""),
                     "sample_s": round(dt), "render_full": round(render + cut), "graphics": round(full.get("graphics_per_min", 0) * secs / 60),
                     "behind_s": full.get("behind_seconds", 0), "paid": full.get("paid", []), "new_motions": full.get("new_motions", 0),
                     "file": str(out_dir / f"c.{c['id']}.mp4"), "poster": str(out_dir / f"c.{c['id']}.jpg")})
        files += [rows[-1]["file"], rows[-1]["poster"]]
        tmp.unlink()
    md = [f"# Концепції за референсом {spec.get('reference', '')}", ""]
    for r in rows:
        md += [f"## {r['id'].upper()}. {r['title']}", "Беремо з референсу: " + "; ".join(r["takes"]), f"Лишається твоє: {r['keeps']}",
               f"Ціна: ~{r['graphics']} графік на рілс" + (f", «за мною» {r['behind_s']} с" if r["behind_s"] else "")
               + (f", нових моушнів {r['new_motions']}" if r["new_motions"] else "")
               + f", фінальний рендер ~{mins(r['render_full'])}; платне: " + (", ".join(r["paid"]) if r["paid"] else "нічого"),
               f"Пробник: {r['file']}", ""]
    (out_dir / "summary.md").write_text("\n".join(md))
    json.dump({"id": rid, "reference": spec.get("reference"), "concepts": rows}, open(out_dir / "concepts.json", "w"), ensure_ascii=False, indent=1)
    json.dump(spec, open(out_dir / "spec.json", "w"), ensure_ascii=False, indent=1)
    print("\n".join(md))
    print("upload (Artifact asset: true, file_paths):"); print("\n".join(files))


def pick(reel, cid, name=None, mix=None):
    reel = Path(reel).expanduser()
    specs = sorted((lab(reel) / "rounds").glob("*/spec.json"), key=lambda p: p.stat().st_mtime)
    if not specs: sys.exit("no concepts round yet")
    spec = json.load(open(specs[-1])); c = next((x for x in spec["concepts"] if x["id"] == cid), None)
    if not c: sys.exit(f"no concept {cid}: " + ", ".join(x["id"] for x in spec["concepts"]))
    name = name or f"{spec['id']}-{cid}"
    st = {"title": f"{c['title']} (за референсом)", "about": "; ".join(c.get("takes", [])), "reference": spec.get("reference"), **c["style"]}
    (HOME / "styles").mkdir(parents=True, exist_ok=True)
    json.dump(st, open(HOME / "styles" / f"{name}.json", "w"), ensure_ascii=False, indent=1)
    (reel / "style.txt").write_text(name)
    note = HOME / "styles" / "STYLE.md"
    with open(note, "a") as f:
        f.write(f"\n- {name}: «{c['title']}» за референсом {spec.get('reference', '')}" + (f" (її правка: {mix})" if mix else "") + "\n")
    print(f"style {name} -> {HOME / 'styles' / (name + '.json')}; {reel / 'style.txt'} = {name}"
          + (f"\napply her mix by hand in that json first: {mix}" if mix else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    if a[0] == "prep": prep(a[1], float(a[2]), float(a[3]), a[a.index("--hook") + 1] if "--hook" in a else None)
    elif a[0] == "round": round_(a[1], a[2])
    elif a[0] == "pick": pick(a[1], a[2], a[a.index("--name") + 1] if "--name" in a else None, a[a.index("--mix") + 1] if "--mix" in a else None)
    else: sys.exit(__doc__)
