"""Build the demo incident clips from the synthetic CCTV stills in `Demo img/`.

Each still becomes a 12 s static-camera clip: the original 2024 clock is covered
by an OSD box and a ticking clock for the claim's incident time is drawn in its
place. Output goes to poodle/media/incidents/<claim>.mp4 plus a poster frame and
a list thumbnail. Needs ffmpeg and Pillow:

    uv run --with pillow python server/tools/build_media.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Demo img"
OUT = ROOT / "poodle" / "media" / "incidents"
FONT = "/System/Library/Fonts/Menlo.ttc"
GREEN = (61, 242, 61)
WHITE = (244, 244, 244)

# claim id: (still, osd box x,y,w,h in source pixels, text x,y, font size, colour, strftime, incident time)
CLIPS = {
    "PD-0147": ("8CCDa", (6, 8, 356, 46), (14, 14), 30, WHITE, "%Y-%m-%d %H:%M:%S", "2026-10-16 17:32:18"),
    "PD-0204": ("0Tq6p", (6, 726, 356, 50), (16, 734), 30, GREEN, "%Y-%m-%d %H:%M:%S", "2026-10-15 16:32:18"),
    "PD-0188": ("uoCkm", (2, 4, 340, 44), (10, 10), 28, GREEN, "%Y-%m-%d %H:%M:%S", "2026-10-16 14:32:18"),
    "PD-0211": ("xp3Rh", (0, 2, 334, 40), (8, 7), 27, GREEN, "%Y-%m-%d %H:%M:%S", "2026-10-17 08:17:32"),
    "PD-0219": ("N6jKP", (8, 14, 412, 48), (18, 22), 28, WHITE, "%d-%m-%Y %a %H:%M:%S", "2026-10-14 07:42:18"),
    "PD-0226": ("vDVdk", (12, 14, 362, 48), (22, 22), 30, GREEN, "%Y-%m-%d %H:%M:%S", "2026-10-13 22:41:32"),
    "PD-0231": ("ulhIn", (20, 26, 410, 48), (30, 34), 30, WHITE, "%Y-%m-%d %H:%M:%S", "2026-10-12 17:42:18"),
    "PD-0236": ("6r6vm", (6, 6, 302, 42), (14, 12), 28, GREEN, "%Y-%m-%d %H:%M:%S", "2026-10-17 12:52:07"),
}

SECONDS = 12
FPS = 15


def frame(still: Image.Image, cfg: tuple, offset: int) -> Image.Image:
    _, (bx, by, bw, bh), (tx, ty), size, colour, fmt, when = cfg
    img = still.copy()
    draw = ImageDraw.Draw(img)
    draw.rectangle((bx, by, bx + bw, by + bh), fill=(0, 0, 0))
    stamp = (datetime.strptime(when, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=offset)).strftime(fmt)
    draw.text((tx, ty), stamp, font=ImageFont.truetype(FONT, size), fill=colour)
    return img


def build(claim: str, cfg: tuple, posters_only: bool) -> None:
    still = Image.open(SRC / f"{cfg[0]}.jpg").convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    first = frame(still, cfg, 0)
    first.save(OUT / f"{claim}.jpg", quality=74)
    thumb = first.copy()
    thumb.thumbnail((320, 320))
    thumb.save(OUT / f"{claim}-thumb.jpg", quality=78)
    if posters_only:
        return
    with tempfile.TemporaryDirectory() as tmp:
        for s in range(SECONDS):
            frame(still, cfg, s).save(Path(tmp) / f"f{s:02d}.png")
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", "1", "-i", str(Path(tmp) / "f%02d.png"),
            "-vf", f"fps={FPS},noise=c0s=4:c0f=t,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-movflags", "+faststart",
            "-an", str(OUT / f"{claim}.mp4"),
        ], check=True)


def main() -> int:
    posters_only = "--posters" in sys.argv
    only = [a for a in sys.argv[1:] if a.startswith("PD-")]
    for claim, cfg in CLIPS.items():
        if only and claim not in only:
            continue
        build(claim, cfg, posters_only)
        print(claim, "ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
