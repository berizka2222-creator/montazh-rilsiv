#!/usr/bin/env python3
"""Give the finished reel a public HTTPS link that Instagram can fetch, for one hour.

  publish_ig.py <final.mp4> [cover.jpg]   -> prints {"video_url", "cover_url"?, "expires": "1h"}

Instagram's publishing API (Meta connector, publish_instagram_media) only takes a public URL, and the review page's files are
private. The reel is about to be public on Instagram anyway, so it goes to litterbox.catbox.moe for 1 hour (the file deletes
itself), and nothing has to be set up. Only after she pressed «Опублікувати в Instagram» and confirmed the account and
caption in chat. Then: get_instagram_accounts -> publish_instagram_media(media_type="REELS", video_url, caption, cover_url,
share_to_feed=true, skip_if_recently_published=true) -> write the permalink to builds/latest "published"."""
import json, subprocess, sys
from pathlib import Path

HOST = "https://litterbox.catbox.moe/resources/internals/api.php"

def up(path):
    p = Path(path).expanduser()
    if not p.exists(): sys.exit(f"no file: {p}")
    if p.stat().st_size > 1_000_000_000: sys.exit("file over 1 GB")
    r = subprocess.run(["curl", "-sS", "-m", "600", "-F", "reqtype=fileupload", "-F", "time=1h", "-F", f"fileToUpload=@{p}", HOST],
                       capture_output=True, text=True)
    url = r.stdout.strip()
    if r.returncode or not url.startswith("https://"): sys.exit(f"upload failed: {r.stderr.strip() or url}")
    return url

if len(sys.argv) < 2: sys.exit(__doc__)
out = {"video_url": up(sys.argv[1]), "expires": "1h"}
if len(sys.argv) > 2: out["cover_url"] = up(sys.argv[2])
print(json.dumps(out))
