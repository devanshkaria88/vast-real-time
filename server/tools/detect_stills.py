"""Run YOLO on the frames the claim findings cite.

The frame at each finding's t in the claim's incident clip is detected once; its
boxes go to server/data/detections.json (keyed by claim, each box with its t),
and vehicle, impact and motion findings cite the vehicles and people in their
frame, except findings marked "photo" (phone photos inside a clip, where YOLO
mislabels wrecks). The server only reads the JSON, so the deployed app does not need torch.
Run after build_media.py; on the event VM the live path calls $YOLO_URL instead.

    uv venv /tmp/yolo-venv --python 3.12 && uv pip install --python /tmp/yolo-venv/bin/python ultralytics
    /tmp/yolo-venv/bin/python server/tools/detect_stills.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "poodle"
CLAIMS = ROOT / "server" / "data" / "claims.json"
OUT = ROOT / "server" / "data" / "detections.json"

KEEP = {"car", "truck", "bus", "person", "bicycle", "motorcycle", "traffic light", "stop sign"}
CITED = {"car", "truck", "bus", "motorcycle", "bicycle", "person"}
CITING_KINDS = {"vehicle", "impact", "motion"}


def citable(d: dict) -> bool:
    x, y, w, h = d["box"]
    # A wide box on the bottom edge is the recording car's own bonnet, not a road user.
    bonnet = y > 0.7 and y + h > 0.97 and w > 0.5
    return d["label"] in CITED and d["conf"] >= 0.5 and not bonnet


def signal_state(crop: Image.Image) -> tuple[str, float]:
    """Classify a traffic-light crop by its brightest lit hue. Deterministic, no model."""
    hsv = np.asarray(crop.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    lit = (s > 0.45) & (v > 0.55)
    if lit.sum() < 6:
        return "not_visible", 0.5
    red = (((h < 18) | (h > 340)) & lit).sum()
    amber = ((h >= 18) & (h < 50) & lit).sum()
    green = ((h >= 90) & (h < 180) & lit).sum()
    counts = {"red": red, "amber": amber, "green": green}
    state = max(counts, key=counts.get)
    total = sum(counts.values()) or 1
    return state, round(float(counts[state] / total), 2)


def frame_at(clip: Path, t: float) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "frame.png"
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(clip), "-frames:v", "1", str(out)], check=True)
        return Image.open(out).convert("RGB")


def detect(model: YOLO, img: Image.Image, t: float) -> list[dict]:
    w, h = img.size
    pred = model.predict(img, conf=0.25, verbose=False)[0]
    found = []
    for box, cls, conf in zip(pred.boxes.xyxy.tolist(), pred.boxes.cls.tolist(), pred.boxes.conf.tolist()):
        label = pred.names[int(cls)]
        if label not in KEEP:
            continue
        x1, y1, x2, y2 = box
        det = {
            "label": label,
            "conf": round(float(conf), 3),
            "box": [round(x1 / w, 4), round(y1 / h, 4), round((x2 - x1) / w, 4), round((y2 - y1) / h, 4)],
            "t": t,
        }
        if label == "traffic light":
            det["state"], det["state_conf"] = signal_state(img.crop((int(x1), int(y1), int(x2), int(y2))))
        found.append(det)
    return sorted(found, key=lambda d: -d["conf"])


def main() -> int:
    model = YOLO("yolo11s.pt")
    claims = json.loads(CLAIMS.read_text())
    result: dict[str, dict] = {}
    for claim in claims:
        clip = WEB / claim["footage"]["clip"]
        dets: list[dict] = []
        cited: dict[float, list[int]] = {}
        size = (0, 0)
        for f in claim["findings"]:
            if f["t"] not in cited:
                img = frame_at(clip, f["t"])
                size = img.size
                found = detect(model, img, f["t"])
                cited[f["t"]] = [len(dets) + i for i, d in enumerate(found) if citable(d)][:3]
                dets.extend(found)
            f["det"] = cited[f["t"]] if f["kind"] in CITING_KINDS and not f.get("photo") else []
        result[claim["id"]] = {"width": size[0], "height": size[1], "model": "yolo11s", "detections": dets}
        print(claim["id"], len(dets), "boxes over", len(cited), "frames")
    OUT.write_text(json.dumps(result, indent=1))
    CLAIMS.write_text(json.dumps(claims, indent=1, ensure_ascii=False) + "\n")
    print("wrote", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
