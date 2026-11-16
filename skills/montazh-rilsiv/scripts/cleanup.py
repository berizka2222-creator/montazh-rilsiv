#!/usr/bin/env python3
"""Tidy a finished reel folder: keep only the raw clip and the final, move everything else to the Trash.

Usage: cleanup.py <reel folder> [--dry-run]

Kept: raw.* (the untouched source), final.mp4, cover.* (cover for Instagram).
Everything else (drafts, master, proxies, logs, page, proj, caches, work folders) goes to the macOS Trash,
so it can still be restored from there. Refuses to run if final.mp4 is missing or not a playable video.
"""
import shutil, subprocess, sys, time
from pathlib import Path

KEEP_PREFIXES = ("raw.", "cover.")
KEEP_NAMES = {"final.mp4"}


def playable(p: Path) -> bool:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=60)
        return out.returncode == 0 and float(out.stdout.strip() or 0) > 1
    except Exception:
        return False


def size(p: Path) -> int:
    if p.is_file() or p.is_symlink():
        return p.lstat().st_size
    return sum(f.lstat().st_size for f in p.rglob("*") if f.is_file())


def to_trash(p: Path, trash: Path):
    dest = trash / p.name
    if dest.exists():
        dest = trash / f"{p.stem}-{time.strftime('%H%M%S')}{p.suffix}"
    shutil.move(str(p), str(dest))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if not args:
        sys.exit(__doc__)
    reel = Path(args[0]).expanduser().resolve()
    final = reel / "final.mp4"
    if not final.exists() or not playable(final):
        sys.exit(f"СТОП: у {reel} немає робочого final.mp4. Нічого не видаляю.")
    if not any(reel.glob("raw.*")):
        print("Увага: сирого raw.* у папці немає, лишиться тільки final.mp4.")

    trash = Path.home() / ".Trash" / f"{reel.name}-чернетки"
    gone, total = [], 0
    for p in sorted(reel.iterdir()):
        if p.name in KEEP_NAMES or p.name.startswith(KEEP_PREFIXES):
            continue
        gone.append(p); total += size(p)

    for p in gone:
        print(("[перевірка] " if dry else "") + "у кошик: " + p.name)
    print(f"{'Звільниться' if dry else 'Звільнено'} ~{total / 1e9:.1f} ГБ. Лишились: "
          + ", ".join(sorted(p.name for p in reel.iterdir() if p not in gone)))
    if dry or not gone:
        return
    trash.mkdir(parents=True, exist_ok=True)
    for p in gone:
        to_trash(p, trash)
    print(f"Чернетки в Кошику: {trash.name} (можна відновити, поки Кошик не очищено).")


if __name__ == "__main__":
    main()
