"""Build the incident clips from the real dashcam videos in poodle/media/raw/.

Each claim's footage.raw becomes a 720p, muted, fast-start clip at
poodle/media/incidents/<claim>.mp4, with a poster frame at footage.posterAt and
a list thumbnail. Needs ffmpeg and Pillow:

    uv run --with pillow python server/tools/build_media.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "poodle"
CLAIMS = ROOT / "server" / "data" / "claims.json"


def build(claim: dict) -> None:
    f = claim["footage"]
    clip = WEB / f["clip"]
    clip.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", str(WEB / f["raw"]), "-vf", "scale=1280:-2",
        "-c:v", "libx264", "-preset", "medium", "-crf", "30", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-an", str(clip),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{f['posterAt']:.3f}", "-i", str(clip),
        "-frames:v", "1", "-q:v", "4", str(WEB / f["poster"]),
    ], check=True)
    thumb = Image.open(WEB / f["poster"])
    thumb.thumbnail((320, 320))
    thumb.save(WEB / f["thumb"], quality=78)


def main() -> int:
    only = [a for a in sys.argv[1:] if a.startswith("PD-")]
    for claim in json.loads(CLAIMS.read_text()):
        if only and claim["id"] not in only:
            continue
        build(claim)
        print(claim["id"], "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
