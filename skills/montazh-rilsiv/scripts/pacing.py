"""Pacing presets: how hard the edit trims. One place, so cut.py, tighten.py and the review page agree.
brand.json "pacing": "natural" (default) | "tight" | "fast". An explicit brand.json "speed" still wins."""

PRESETS = {
    # pauses longer than pause_min get shortened, leaving `air` seconds either side of the cut
    "natural": {"speed": 1.0, "pause_min": 0.6, "air": 0.15, "fillers": ["um", "uh", "umm", "uhm", "erm", "hmm", "mm"]},
    "tight":   {"speed": 1.1, "pause_min": 0.25, "air": 0.06, "fillers": ["um", "uh", "umm", "uhm", "erm", "er", "ah", "hmm", "mm"]},
    "fast":    {"speed": 1.15, "pause_min": 0.2, "air": 0.05, "fillers": ["um", "uh", "umm", "uhm", "erm", "er", "ah", "hmm", "mm"]},
}

# Fillers per language. Single hesitation sounds only, never real words ("а", "і" are conjunctions in Ukrainian).
LANG_FILLERS = {
    "uk": {"natural": ["е", "ее", "еее", "ем", "емм", "ем-м", "м", "мм", "ммм", "хм", "гм"],
           "tight":   ["е", "ее", "еее", "ем", "емм", "ем-м", "м", "мм", "ммм", "хм", "гм", "ну"],
           "fast":    ["е", "ее", "еее", "ем", "емм", "ем-м", "м", "мм", "ммм", "хм", "гм", "ну"]},
}
# drawn-out hesitations Scribe writes with any number of letters ("еееем", "мммм", "uhhh")
LONG_FILLER = {"uk": r"е+м*|м{2,}|[хг]м+", "en": r"u+[hm]+|e+r+m*|h?m{2,}|a+h+"}

def is_filler(text, fillers, l="en"):
    """True when this transcript word is a hesitation sound to cut. An empty fillers list keeps every filler."""
    import re
    n = re.sub(r"[\W\d_]", "", text.lower())
    return bool(fillers) and (n in fillers or bool(n and re.fullmatch(LONG_FILLER.get(l, LONG_FILLER["en"]), n)))

def lang(brand):
    return (brand.get("language") or "en").lower()

def pacing(brand):
    p = dict(PRESETS.get(brand.get("pacing", "natural"), PRESETS["natural"]))
    if lang(brand) in LANG_FILLERS:
        p["fillers"] = list(LANG_FILLERS[lang(brand)].get(brand.get("pacing", "natural"), LANG_FILLERS[lang(brand)]["natural"]))
    if brand.get("cut_pauses") is False: p["pause_min"] = 999.0   # pauses are cut by hand: never trim them automatically
    if brand.get("speed"): p["speed"] = float(brand["speed"])
    if brand.get("fillers") is not None: p["fillers"] = list(brand["fillers"])   # [] = keep every filler
    return p
