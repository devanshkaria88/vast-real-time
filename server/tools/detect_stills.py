"""Precompute YOLO detections for the demo incident stills.

Runs once on a laptop with ultralytics installed; the server only reads the JSON,
so the deployed app does not need torch. On the event VM the live path calls
$YOLO_URL instead.

    uv venv /tmp/yolo-venv --python 3.12 && uv pip install --python /tmp/yolo-venv/bin/python ultralytics
    /tmp/yolo-venv/bin/python server/tools/detect_stills.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "Demo img"
OUT = ROOT / "server" / "data" / "detections.json"

KEEP = {"car", "truck", "bus", "person", "bicycle", "motorcycle", "traffic light", "stop sign"}


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


def main() -> int:
    model = YOLO("yolo11s.pt")
    result: dict[str, dict] = {}
    for path in sorted(SRC.glob("*.jpg")):
        img = Image.open(path).convert("RGB")
        w, h = img.size
        pred = model.predict(img, conf=0.25, verbose=False)[0]
        dets = []
        for box, cls, conf in zip(pred.boxes.xyxy.tolist(), pred.boxes.cls.tolist(), pred.boxes.conf.tolist()):
            label = pred.names[int(cls)]
            if label not in KEEP:
                continue
            x1, y1, x2, y2 = box
            det = {
                "label": label,
                "conf": round(float(conf), 3),
                "box": [round(x1 / w, 4), round(y1 / h, 4), round((x2 - x1) / w, 4), round((y2 - y1) / h, 4)],
            }
            if label == "traffic light":
                state, sconf = signal_state(img.crop((int(x1), int(y1), int(x2), int(y2))))
                det["state"] = state
                det["state_conf"] = sconf
            dets.append(det)
        dets.sort(key=lambda d: -d["conf"])
        result[path.stem] = {"width": w, "height": h, "model": "yolo11s", "detections": dets}
        print(path.name, len(dets), [d["label"] for d in dets][:12])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    print("wrote", OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
