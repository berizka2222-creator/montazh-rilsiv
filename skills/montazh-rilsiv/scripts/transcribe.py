#!/usr/bin/env python3
"""Word-timed transcript for a clip via ElevenLabs Scribe (tight word timing; verbatim, so "um"/"ем" stay in as words).
Writes a flat word list: [{"text","start","end"}, ...]. There is no local fallback: no key or no network stops here.
Usage: python3 transcribe.py <video-or-audio> <out.json>
Key: ELEVENLABS_API_KEY in the environment or in ~/.config/reels/.env (never pasted into chat)."""
import json, os, subprocess, sys, tempfile, urllib.error, urllib.request, uuid
from pathlib import Path

src, out = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pacing import lang
_bj = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser() / "brand.json"
BRAND = json.load(open(_bj)) if _bj.exists() else {}

def key():
    if os.environ.get("ELEVENLABS_API_KEY"): return os.environ["ELEVENLABS_API_KEY"]
    env = Path("~/.config/reels/.env").expanduser()
    for line in (env.read_text().splitlines() if env.exists() else []):
        if line.startswith("ELEVENLABS_API_KEY="): return line.split("=", 1)[1].strip()

def scribe(k):
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / "a.mp3"   # mono 64 kbps: ~0.5 MB a minute, only the audio leaves the machine
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(audio)], check=True)
        data = audio.read_bytes()
    for model in ("scribe_v2", "scribe_v1"):
        b = uuid.uuid4().hex
        body = b"".join([
            f"--{b}\r\nContent-Disposition: form-data; name=\"model_id\"\r\n\r\n{model}\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"timestamps_granularity\"\r\n\r\nword\r\n".encode(),
            f"--{b}\r\nContent-Disposition: form-data; name=\"tag_audio_events\"\r\n\r\nfalse\r\n".encode(),
            (f"--{b}\r\nContent-Disposition: form-data; name=\"language_code\"\r\n\r\n{lang(BRAND)}\r\n".encode() if lang(BRAND) != "en" else b""),
            f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode(),
            data, f"\r\n--{b}--\r\n".encode()])
        req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body, method="POST",
                                     headers={"xi-api-key": k, "Content-Type": f"multipart/form-data; boundary={b}"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                res = json.load(r)
            return model, [{"text": w["text"], "start": round(w["start"], 3), "end": round(w["end"], 3)}
                           for w in res.get("words", []) if w.get("type") == "word" and w["text"].strip()]
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:200]
            if e.code in (400, 422) and "model" in msg.lower(): continue      # model id not offered: try the older one
            print(f"ElevenLabs error {e.code}: {msg}", file=sys.stderr); return None, None
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"ElevenLabs unreachable: {e}", file=sys.stderr); return None, None
    print("ElevenLabs: no usable Scribe model", file=sys.stderr); return None, None

k = key()
if not k:
    print("NO ELEVENLABS KEY: speech recognition runs on ElevenLabs Scribe. Connect it first (SKILL.md, «Connecting ElevenLabs Scribe»).", file=sys.stderr)
    sys.exit(2)
model, words = scribe(k)
if words is None:
    print("TRANSCRIPTION FAILED: check the key in ~/.config/reels/.env (it starts with sk_), the ElevenLabs balance and the internet, then run again.", file=sys.stderr)
    sys.exit(1)
print(f"transcribed with ElevenLabs {model}: {len(words)} words")
json.dump(words, open(out, "w"))
