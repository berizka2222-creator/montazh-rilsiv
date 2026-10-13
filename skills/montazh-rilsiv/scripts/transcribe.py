#!/usr/bin/env python3
"""Word-timed transcript for a clip: ElevenLabs Scribe when a key is set (tight word timing, keeps "um"/"uh"),
else the free local Whisper via HyperFrames. Writes a flat word list: [{"text","start","end"}, ...].
Usage: python3 transcribe.py <video-or-audio> <out.json>
Key: ELEVENLABS_API_KEY in the environment or in ~/.config/reels/.env (never pasted into chat)."""
import json, os, subprocess, sys, tempfile, urllib.error, urllib.request, uuid
from pathlib import Path

src, out = Path(sys.argv[1]).expanduser(), Path(sys.argv[2]).expanduser()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pacing import lang, asr_args
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
model, words = scribe(k) if k else (None, None)
if words is not None:
    print(f"transcribed with ElevenLabs {model}: {len(words)} words")
else:   # no key, or the key/network failed: the free local route, so an edit never stops on a bad key
    if k: print("falling back to local Whisper - fix ELEVENLABS_API_KEY in ~/.config/reels/.env (it starts with sk_)", file=sys.stderr)
    # Whisper's word times drift on long audio (up to ~1 s by a minute in). So it hears the clip in ~6 s pieces,
    # each split at the quietest moment nearby, and the times are offset back: word timing stays within ~0.2 s.
    import array, math, wave
    d = out.parent / (out.stem + "_whisper"); d.mkdir(exist_ok=True)
    wav = d / "a.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    w = wave.open(str(wav)); sr = w.getframerate(); pcm = array.array("h"); pcm.frombytes(w.readframes(w.getnframes())); dur = len(pcm) / sr
    def lev(t):
        s = pcm[int(t * sr):int(t * sr) + int(sr * 0.01)] or [0]
        return math.sqrt(sum(x * x for x in s) / len(s))
    STEP = float(os.environ.get("REEL_ASR_CHUNK", 6))
    cuts, t = [0.0], STEP - 1
    while t < dur - STEP / 2:
        q = min((lev(t + k * 0.01), t + k * 0.01) for k in range(300))[1]   # quietest 10 ms in the next 3 s
        cuts.append(round(q, 2)); t = q + STEP - 1
    cuts.append(dur)
    words = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        cw, cd = d / f"c{i}.wav", d / f"c{i}"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", str(wav), str(cw)], check=True)
        subprocess.run(["npx", "-y", "hyperframes", "transcribe", str(cw), "-d", str(cd), "--json", *asr_args(BRAND)], capture_output=True, check=True)
        for x in json.load(open(cd / "transcript.json")):
            words.append({"text": x["text"], "start": round(a + x["start"], 3), "end": round(a + min(x["end"], b - a), 3)})
    print(f"transcribed with local Whisper (no ElevenLabs key) in {len(cuts) - 1} pieces: {len(words)} words")
json.dump(words, open(out, "w"))
