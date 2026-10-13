#!/usr/bin/env python3
"""Render queue for a batch of reels: renders run one at a time (each takes the whole machine), in the order they were added,
while the person reviews the next reel on the page.
Usage:
  render_queue.py add <reel> [--final|--capcut] [--preview]   queue a render (--preview = REEL_PREVIEW=1, the 1080p draft)
  render_queue.py run                                         work through the queue, exit when it is empty
                                                              (run it in the background; a second `run` exits at once)
  render_queue.py status                                      what is rendering and what waits
Every finished render appends a line to <queue>/done.log:  <time> DONE|FAIL <reel> <seconds>s
Watch that file to upload each draft as soon as it is ready. Queue folder: $REELS_HOME/.queue (default ~/reels/.queue)."""
import fcntl, json, os, subprocess, sys, time
from pathlib import Path

Q = Path(os.environ.get("REELS_HOME", "~/reels")).expanduser() / ".queue"
JOBS, DONE, LOCK, NOW = Q / "jobs.jsonl", Q / "done.log", Q / "run.lock", Q / "now.json"
RENDER = Path(__file__).resolve().parent / "render.sh"


def jobs():
    return [json.loads(l) for l in JOBS.read_text().splitlines() if l.strip()] if JOBS.exists() else []


def save(js):
    tmp = JOBS.with_suffix(".tmp"); tmp.write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in js)); tmp.replace(JOBS)


def edit(fn):   # read-modify-write the job list under its own lock, so `add` and `run` never clobber each other
    with open(Q / "jobs.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX); js = jobs(); out = fn(js); save(js); return out


def add(reel, flags):
    reel = str(Path(reel).expanduser().resolve())
    if not (Path(reel) / "edit.json").exists(): sys.exit(f"{reel} has no edit.json: import the review and run precheck first")
    job = {"reel": reel, "args": [f for f in flags if f in ("--final", "--capcut")], "preview": "--preview" in flags, "at": time.time()}
    def put(js):
        js[:] = [j for j in js if j["reel"] != reel]   # re-queueing a reel replaces its waiting job (newer decisions win)
        js.append(job); return len(js)
    n = edit(put)
    print(f"queued {Path(reel).name} (#{n} in line)")


def run():
    lk = open(LOCK, "w")
    try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: print("a queue runner is already working; the job will be picked up"); return
    while True:
        job = edit(lambda js: js.pop(0) if js else None)
        if not job: NOW.unlink(missing_ok=True); print("queue empty"); return
        NOW.write_text(json.dumps(job, ensure_ascii=False))
        env = dict(os.environ, **({"REEL_PREVIEW": "1"} if job["preview"] else {}))
        t0 = time.time(); print(f"rendering {Path(job['reel']).name}", flush=True)
        rc = subprocess.run(["bash", str(RENDER), job["reel"], *job["args"]], env=env).returncode
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {'DONE' if rc == 0 else 'FAIL'} {job['reel']} {time.time() - t0:.0f}s"
        with open(DONE, "a") as f: f.write(line + "\n")
        print(line, flush=True)


def status():
    if NOW.exists(): print("rendering:", Path(json.loads(NOW.read_text())["reel"]).name)
    for k, j in enumerate(jobs(), 1): print(f"waiting #{k}:", Path(j["reel"]).name, " ".join(j["args"]) + (" (preview)" if j["preview"] else ""))
    if not NOW.exists() and not jobs(): print("queue empty")


if __name__ == "__main__":
    Q.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "add" and len(sys.argv) > 2: add(sys.argv[2], sys.argv[3:])
    elif cmd == "run": run()
    elif cmd == "status": status()
    else: sys.exit(__doc__)
