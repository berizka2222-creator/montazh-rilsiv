# Vibha's video effects (vendored)

42 talking-head effects by **Vibha Ramprakash** ([@vibha.in.progress](https://instagram.com/vibha.in.progress)),
from https://github.com/Vibha-Ramprakash/claude-video-effects (commit d675cff), MIT licence: see `LICENSE`.
Fonts keep their SIL OFL / Apache licences (`fonts/*.txt`), models theirs (`models/NOTICE.md`).

Changes made here (the rest is as published):
- `scripts/fx.py` reads `FX_FONTS` and `FX_COLORS` from the environment, so the reel skill draws the effects in the
  person's brand fonts (her fonts have no Cyrillic) and accent colours. Without those variables it behaves as the original.
- `scripts/words.py` is left out: the reel skill has its own word timing (ElevenLabs Scribe).
- `requirements.txt` adds fonttools + brotli (brand fonts shipped as .woff2 are converted to .ttf for Pillow).
The reel skill runs it through `scripts/fx_pass.py` (only the seconds with an effect are processed).
