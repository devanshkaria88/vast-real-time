"""Sponsor-stack adapters. Each switches on from env vars; without them Poodle runs
in replay mode and reports that in /api/health.

Unverified against the event stack (no credentials on the build laptop): the YOLO,
Cosmos, W&B Inference, Jev and VastDB request shapes follow docs/hack-plan.md and the
jev-decisions skill. Check them on the team VM before the demo.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EVENTS = Path(__file__).resolve().parent / "data" / "events.jsonl"


def load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines into the environment. Variables already set win, blank values are skipped."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip().strip("\"'")
        if key and value and key not in os.environ:
            os.environ[key] = value


load_dotenv(ROOT / ".env")


def env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


# ---------------------------------------------------------------- detector

_local_model = None


def _local_yolo_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False


LOCAL_YOLO = _local_yolo_available()


def _local_detect(image: bytes) -> list[dict]:
    global _local_model
    import io

    from PIL import Image
    from ultralytics import YOLO

    if _local_model is None:
        _local_model = YOLO(env("POODLE_YOLO_WEIGHTS") or "yolo11s.pt")
    img = Image.open(io.BytesIO(image)).convert("RGB")
    w, h = img.size
    pred = _local_model.predict(img, conf=0.25, verbose=False)[0]
    out = []
    for box, cls, conf in zip(pred.boxes.xyxy.tolist(), pred.boxes.cls.tolist(), pred.boxes.conf.tolist()):
        x1, y1, x2, y2 = box
        out.append({"label": pred.names[int(cls)], "conf": round(float(conf), 3),
                    "box": [round(x1 / w, 4), round(y1 / h, 4), round((x2 - x1) / w, 4), round((y2 - y1) / h, 4)]})
    return out


async def detect(client: httpx.AsyncClient, image: bytes) -> dict:
    started = time.perf_counter()
    url = env("YOLO_URL")
    if url:
        headers = {"Authorization": f"Bearer {env('YOLO_TOKEN')}"} if env("YOLO_TOKEN") else {}
        r = await client.post(f"{url.rstrip('/')}/v1/infer", headers=headers, timeout=20,
                              json={"image_base64": base64.b64encode(image).decode()})
        r.raise_for_status()
        body = r.json()
        dets = body.get("detections") or body.get("predictions") or []
        return {"source": "YOLO (event stack)", "ms": round((time.perf_counter() - started) * 1000), "detections": dets}
    if LOCAL_YOLO:
        dets = await asyncio.to_thread(_local_detect, image)
        return {"source": "YOLO11s (local)", "ms": round((time.perf_counter() - started) * 1000), "detections": dets}
    return {"source": None, "ms": 0, "detections": [], "error": "No detector connected. Set YOLO_URL or install ultralytics."}


# ---------------------------------------------------------------- Cosmos Reason (video Q&A)

_cosmos_model: str | None = None


async def _cosmos_model_id(client: httpx.AsyncClient, url: str, headers: dict) -> str:
    global _cosmos_model
    if env("COSMOS_MODEL"):
        return env("COSMOS_MODEL")
    if _cosmos_model is None:
        r = await client.get(f"{url}/v1/models", headers=headers, timeout=10)
        r.raise_for_status()
        _cosmos_model = r.json()["data"][0]["id"]
    return _cosmos_model


async def cosmos_answer(client: httpx.AsyncClient, claim: dict, question: str) -> dict | None:
    url = env("COSMOS3_REASON_URL")
    clip = ROOT / "poodle" / claim["footage"]["clip"]
    if not url or not clip.exists():
        return None
    url = url.rstrip("/")
    headers = {"Authorization": f"Bearer {env('COSMOS_TOKEN')}"} if env("COSMOS_TOKEN") else {}
    prompt = (
        "This is dashcam footage of a road collision, reviewed for an insurance claim. Answer the adjuster's question "
        "from what is visible only. If it cannot be seen, say it is not visible. "
        'Reply as <think>your reasoning</think><answer>{"answer": "<= 2 sentences", "grounded": true|false}</answer>.\n'
        f"Question: {question}"
    )
    video = base64.b64encode(clip.read_bytes()).decode()
    r = await client.post(f"{url}/v1/chat/completions", headers=headers, timeout=60, json={
        "model": await _cosmos_model_id(client, url, headers),
        "messages": [{"role": "user", "content": [
            {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{video}"}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": 400, "temperature": 0,
    })
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]
    if "<answer>" in text:
        text = text.split("<answer>", 1)[1].split("</answer>", 1)[0].strip()
    try:
        body = json.loads(text)
        answer, grounded = body.get("answer", ""), bool(body.get("grounded"))
    except json.JSONDecodeError:
        answer, grounded = text, not text.lower().startswith("not visible")
    return {"answer": answer, "grounded": grounded, "citations": []}


# ---------------------------------------------------------------- W&B Inference (LLM prose)

async def llm_answer(client: httpx.AsyncClient, claim: dict, question: str) -> dict | None:
    key = env("WANDB_API_KEY")
    if not key:
        return None
    findings = [{"id": f["id"], "text": f["text"], "conf": f["conf"]} for f in claim["findings"]]
    prompt = (
        "You answer an insurance adjuster's question about incident footage using ONLY these findings. "
        "If the findings cannot answer it, say it is not visible. Reply as JSON: "
        '{"answer": "<= 2 sentences", "citations": ["finding ids"], "grounded": true|false}.\n'
        f"Findings: {json.dumps(findings)}\nQuestion: {question}"
    )
    headers = {"Authorization": f"Bearer {key}"}
    if env("WANDB_PROJECT"):
        headers["OpenAI-Project"] = env("WANDB_PROJECT")
    r = await client.post("https://api.inference.wandb.ai/v1/chat/completions", headers=headers, timeout=30, json={
        "model": env("POODLE_LLM_MODEL") or "meta-llama/Llama-3.3-70B-Instruct",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 220, "temperature": 0,
        "response_format": {"type": "json_object"},
    })
    r.raise_for_status()
    body = json.loads(r.json()["choices"][0]["message"]["content"])
    return {"answer": body.get("answer", ""), "grounded": bool(body.get("grounded")),
            "citations": [{"finding": c} for c in body.get("citations", [])]}


# ---------------------------------------------------------------- Jev (typed coverage answers)

FAULT_OPTIONS = {
    "not_at_fault": "the policyholder did nothing to cause the collision",
    "shared_fault": "both drivers contributed",
    "mostly_at_fault": "the policyholder caused most of it",
    "fully_at_fault": "the policyholder caused it",
    "cannot_determine": "the facts do not show who caused it",
}


def jev_questions(policy: dict, wording: dict) -> dict:
    exclusions = {k: v["text"] for k, v in wording.items() if k.startswith("E")}
    exclusions["none"] = "no exclusion applies"
    return {
        "peril": {"type": "choice", "instructions": "What happened in `facts`?", "criteria": {
            "collision_with_vehicle": "a collision with another vehicle", "collision_with_object": "hit an object",
            "collision_with_pedestrian_or_cyclist": "hit a person on foot or a cyclist", "theft": "theft",
            "vandalism": "vandalism", "fire": "fire", "weather": "weather damage", "glass_only": "glass only", "other": "something else"}},
        "section_covers_peril": {"type": "noul", "instructions": "Does Section 1 in `policy` cover damage to the policyholder's own car for this incident under `policy.cover`?"},
        "exclusion": {"type": "choice", "instructions": "Which exclusion in `policy` do `facts` trigger?", "criteria": exclusions},
        "fault_band": {"type": "choice", "instructions": "How much did the policyholder contribute to the collision in `facts`?", "criteria": FAULT_OPTIONS},
        "benefit_courtesy_car": {"type": "noul", "instructions": "Would the policyholder need a courtesy car while their car is repaired, given `facts`?"},
        "benefit_legal_expenses": {"type": "noul", "instructions": "Do `facts` give the policyholder uninsured losses to recover from another driver?"},
        "severity": {"type": "score", "instructions": "How badly damaged is the policyholder's car in `facts`?",
                     "criteria": ["cosmetic scuffs", "repairable damage", "major structural damage", "likely write-off"]},
        "evidence_sufficient": {"type": "noul", "instructions": "Do `facts` contain enough evidence to decide cover without asking for more?"},
        "fraud_risk": {"type": "score", "instructions": "How strongly do `facts` match staged-collision patterns?",
                       "criteria": ["no staged-collision signs", "some signs worth a look", "strong staged-collision signs"]},
    }


def jev_target() -> tuple[str, str, str] | None:
    """(base URL, key, model) for Jev, or None when no key is set."""
    key = env("TYPESAFE_API_KEY") or env("OPENROUTER_API_KEY")
    if not key:
        return None
    direct = bool(env("TYPESAFE_API_KEY"))
    base = env("JEV_BASE_URL") or ("https://api.typesafe.ai" if direct else "https://openrouter.ai/api")
    model = env("JEV_MODEL") or ("jev-1.14.0" if direct else "typesafe/jev-1.14")
    return base, key, model


async def jev_decide(client: httpx.AsyncClient, claim: dict, policy: dict, wording: dict) -> dict | None:
    target = jev_target()
    if not target:
        return None
    base, key, model = target
    state = {
        "facts": {"findings": [f["text"] for f in claim["findings"]], "statement": claim["statement"]["text"],
                  "driver": claim["driver"], "estimate": claim.get("estimate")},
        "policy": {"cover": policy["cover"], "addOns": policy["addOns"],
                   "wording": {k: v["text"] for k, v in wording.items()}},
    }
    r = await client.post(f"{base}/v1/systemone", headers={"Authorization": f"Bearer {key}"}, timeout=15,
                          json={"model": model, "state": state, "questions": jev_questions(policy, wording)})
    r.raise_for_status()
    a = r.json()["answers"]
    sev = ["cosmetic", "repairable", "major", "write_off"]
    fraud = ["low", "medium", "high"]
    return {
        "peril": {"choice": a["peril"]["choice"], "confidence": a["peril"]["confidence"]},
        "section_covers_peril": {"noul": a["section_covers_peril"]["noul"]},
        "exclusion": {"choice": a["exclusion"]["choice"], "confidence": a["exclusion"]["confidence"]},
        "fault_band": {"level": a["fault_band"]["choice"], "confidence": a["fault_band"]["confidence"]},
        "benefit_courtesy_car": {"noul": a["benefit_courtesy_car"]["noul"]},
        "benefit_legal_expenses": {"noul": a["benefit_legal_expenses"]["noul"]},
        "severity": {"level": sev[min(3, round(a["severity"]["score"]))], "confidence": a["severity"]["confidence"]},
        "evidence_sufficient": {"noul": a["evidence_sufficient"]["noul"]},
        "fraud_risk": {"level": fraud[min(2, round(a["fraud_risk"]["score"]))], "confidence": a["fraud_risk"]["confidence"]},
    }


# ---------------------------------------------------------------- event sink (local file, VastDB when configured)

def record_event(event: dict) -> None:
    event = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **event}
    with EVENTS.open("a") as f:
        f.write(json.dumps(event) + "\n")
    if env("VASTDB_ENDPOINT"):
        try:
            _vastdb_insert(event)
        except Exception as exc:  # keep the desk working if the store is down
            print("vastdb insert failed:", exc)


def _vastdb_insert(event: dict) -> None:
    import pyarrow as pa
    import vastdb

    session = vastdb.connect(endpoint=env("VASTDB_ENDPOINT"), access=env("VASTDB_ACCESS_KEY"), secret=env("VASTDB_SECRET_KEY"))
    columns = pa.schema([("at", pa.string()), ("claim", pa.string()), ("kind", pa.string()), ("payload", pa.string())])
    with session.transaction() as tx:
        bucket = tx.bucket(env("VASTDB_BUCKET") or "poodle")
        schema = bucket.schema("poodle", fail_if_missing=False) or bucket.create_schema("poodle")
        table = schema.table("events", fail_if_missing=False) or schema.create_table("events", columns)
        table.insert(pa.table({"at": [event["at"]], "claim": [event.get("claim", "")], "kind": [event.get("kind", "")],
                               "payload": [json.dumps(event)]}))


def services_status(tfl_status: dict) -> list[dict]:
    def s(id_, name, role, live, live_text, fallback):
        return {"id": id_, "name": name, "role": role, "status": "live" if live else "replay", "detail": live_text if live else fallback}

    yolo_live = bool(env("YOLO_URL")) or LOCAL_YOLO
    try:
        import vastdb  # noqa: F401
        vastdb_sdk = True
    except Exception:
        vastdb_sdk = False
    vastdb_fallback = "SDK not installed (pip install vastdb pyarrow)" if env("VASTDB_ENDPOINT") else "Local event log"
    return [
        s("tfl", "TfL JamCams", "Live London cameras", tfl_status["ok"], f"{tfl_status['count']} live", "Snapshot (feed unreachable)"),
        s("yolo", "YOLO11", "Detection on frames", yolo_live, "Event stack" if env("YOLO_URL") else "Local yolo11s", "Precomputed boxes"),
        s("cosmos", "Cosmos Reason", "Video reasoning", bool(env("COSMOS3_REASON_URL")), "Event stack", "Recorded findings"),
        s("jev", "TypeSafe Jev", "Typed coverage answers", bool(env("TYPESAFE_API_KEY") or env("OPENROUTER_API_KEY")), "jev-1.14.0", "Seeded answers"),
        s("llm", "W&B Inference", "Answers in plain English", bool(env("WANDB_API_KEY")), env("POODLE_LLM_MODEL") or "Llama 3.3 70B", "Rule-based answers"),
        s("vastdb", "VastDB", "Evidence and events store", bool(env("VASTDB_ENDPOINT")) and vastdb_sdk, "Writing events", vastdb_fallback),
    ]
