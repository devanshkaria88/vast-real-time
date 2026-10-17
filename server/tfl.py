"""TfL JamCams: the live London traffic camera feed.

List: https://api.tfl.gov.uk/Place/Type/JamCam (CORS open, ~890 cameras).
Each camera has a JPEG still (refreshed every 5-8 min) and a ~10 s MP4 clip on S3.
Licence: show images uncropped and credit "Powered by TfL Open Data".
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import httpx

API = "https://api.tfl.gov.uk/Place/Type/JamCam"
SNAPSHOT = Path(__file__).resolve().parent / "data" / "jamcams-snapshot.json"
TTL = 120

_cache: dict = {"at": 0.0, "cams": [], "ok": False, "error": None}


def _parse(raw: list) -> list[dict]:
    cams = []
    for c in raw:
        props = {p["key"]: p for p in c.get("additionalProperties", [])}
        image = props.get("imageUrl", {}).get("value")
        if not image:
            continue
        cams.append({
            "id": c["id"].replace("JamCams_", ""),
            "name": c["commonName"],
            "view": (props.get("view", {}).get("value") or "").replace("\\/", "/"),
            "lat": c["lat"],
            "lon": c["lon"],
            "image": image,
            "video": props.get("videoUrl", {}).get("value"),
            "available": props.get("available", {}).get("value") == "true",
            "modified": props.get("imageUrl", {}).get("modified"),
        })
    return cams


async def cameras(client: httpx.AsyncClient) -> list[dict]:
    if _cache["cams"] and time.time() - _cache["at"] < TTL:
        return _cache["cams"]
    params = {"app_key": os.environ["TFL_APP_KEY"]} if os.environ.get("TFL_APP_KEY") else None
    try:
        r = await client.get(API, params=params, timeout=20)
        r.raise_for_status()
        cams = _parse(r.json())
        _cache.update(at=time.time(), cams=cams, ok=True, error=None)
        SNAPSHOT.write_text(json.dumps(cams))
    except Exception as exc:  # network down: fall back to the last snapshot
        _cache.update(ok=False, error=str(exc)[:200], at=time.time())
        if not _cache["cams"] and SNAPSHOT.exists():
            _cache["cams"] = json.loads(SNAPSHOT.read_text())
    return _cache["cams"]


def status() -> dict:
    live = sum(1 for c in _cache["cams"] if c["available"])
    return {"ok": _cache["ok"], "count": live, "error": _cache["error"], "fetchedAt": _cache["at"]}


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest(cams: list[dict], lat: float, lon: float, n: int = 6) -> list[dict]:
    ranked = sorted(
        ({**c, "distance": round(distance_m(lat, lon, c["lat"], c["lon"]))} for c in cams if c["available"]),
        key=lambda c: c["distance"],
    )
    return ranked[:n]
