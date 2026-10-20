#!/usr/bin/env python3
"""Turn catalog "paste-in" snippets (markup + css + script + a "Timeline integration" comment, no composition of their own)
into mountable HyperFrames compositions, so a `motion` card can use them like any other catalog item.
Usage: python3 wrap_snippets.py [engine/hf/compositions]     rewrites each snippet in place, prints what it did.
Run it after `npx hyperframes add <name>` of a snippet-style item (the add step prints no data-composition-id for them).
Snippets without a timeline-integration recipe are left alone (they are listed as "skip")."""
import re, sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "engine" / "hf" / "compositions"
GSAP = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"

for f in sorted(ROOT.rglob("*.html")):
    t = f.read_text()
    if 'data-composition-id="' in t: continue
    m = re.search(r"Timeline integration:\s*(.*?)-->", t, re.S)
    if not m: print("skip (no timeline recipe):", f.stem); continue
    name = f.stem
    recipe = m.group(1).strip()
    body = t[:m.start()].rsplit("<!--", 1)[0]                     # snippet without the trailing recipe comment
    body = re.sub(r"^\s*<!--.*?-->", "", body, count=1, flags=re.S)  # drop the leading doc comment
    vm = re.search(r"data-composition-variables='(\[.*?\])'", body, re.S)
    vars_attr = f" data-composition-variables='{vm.group(1)}'" if vm else ""
    out = f"""<!doctype html>
<!-- {name}: catalog snippet wrapped by scripts/wrap_snippets.py (timeline from its own integration recipe) -->
<html lang="uk" data-composition-id="{name}" data-composition-duration="4" data-width="1080" data-height="540"{vars_attr}>
  <head><meta charset="UTF-8" /><title>{name}</title></head>
  <body>
    <template>
      <div id="root" data-composition-id="{name}" data-duration="4" data-fps="30">
        <style>
          #root {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }}
          #root > :not(style):not(script) {{ transform: scale(var(--snip-scale, 2)); transform-origin: 50% 50%; }}
        </style>
{body}
        <script src="{GSAP}"></script>
        <script>
          (function () {{
            var tl = gsap.timeline({{ paused: true }});
            var startTime = 0.15;
            {recipe}
            window.__timelines = window.__timelines || {{}};
            window.__timelines["{name}"] = tl;
          }})();
        </script>
      </div>
    </template>
  </body>
</html>
"""
    f.write_text(out)
    print("wrapped:", name)
