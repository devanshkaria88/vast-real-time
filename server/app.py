"""Poodle backend: serves the desk and its API on :8080.

    uv run --with-requirements server/requirements.txt uvicorn server.app:app --port 8080
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import services, tfl
from .engine import COVER_LABEL, DATA, WEB, answer, decide, load_json, money, sha256

CLAIMS: list[dict] = load_json("claims.json")
POLICY_DATA = load_json("policies.json")
POLICIES, WORDING, RULES = POLICY_DATA["policies"], POLICY_DATA["wording"], POLICY_DATA["rules"]
DETECTIONS = load_json("detections.json")
STATE_FILE = DATA / "state.json"
FRAMES = DATA / "frames"
STATE: dict = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
JEV_LIVE: dict[str, dict] = {}
HASHES: dict[str, list[dict]] = {}
http: httpx.AsyncClient


def save_state() -> None:
    STATE_FILE.write_text(json.dumps(STATE, indent=1))


def media(path: str) -> str:
    """Media can live outside the code bundle (deploy limit is 1 MiB): set POODLE_MEDIA_BASE to a bucket URL."""
    base = services.env("POODLE_MEDIA_BASE")
    return f"{base.rstrip('/')}/{path.removeprefix('media/')}" if base else path


def custody(claim: dict) -> list[dict]:
    if claim["id"] in HASHES:
        return HASHES[claim["id"]]
    reported = datetime.fromisoformat(claim["reportedAt"])
    f = claim["footage"]
    items = []
    for i, (label, rel) in enumerate((("Original still", f"../Demo img/{f['still']}.jpg"),
                                       ("Incident clip", f["clip"]), ("Poster frame", f["poster"]))):
        path = (WEB / rel).resolve()
        if path.exists():
            items.append({"file": path.name, "label": label, "bytes": path.stat().st_size, "sha256": sha256(path),
                          "source": f["source"], "loggedAt": (reported + timedelta(seconds=3 + i)).isoformat(),
                          "by": "Ingest agent"})
    HASHES[claim["id"]] = items
    return items


def find(claim_id: str) -> dict:
    for c in CLAIMS:
        if c["id"] == claim_id:
            return c
    raise HTTPException(404, f"No claim {claim_id}")


def jev_mode(claim_id: str) -> str:
    return "live" if claim_id in JEV_LIVE else "seeded"


def evaluate(claim: dict) -> dict:
    policy = POLICIES[claim["policyId"]]
    return decide(claim, policy, JEV_LIVE.get(claim["id"], claim["jev"]), jev_mode(claim["id"]))


def default_status(claim: dict, decision: dict) -> str:
    if claim["channel"] == "Camera alert":
        return "triage"
    return "ready" if decision["straightThrough"] else "review"


def summary(claim: dict) -> dict:
    d = evaluate(claim)
    s = STATE.get(claim["id"], {})
    return {
        "id": claim["id"], "title": claim["title"], "place": claim["place"], "area": claim["area"],
        "incidentAt": claim["incidentAt"], "reportedAt": claim["reportedAt"], "channel": claim["channel"],
        "status": s.get("status") or default_status(claim, d), "outcome": d["outcome"], "label": d["label"],
        "fraud": claim["jev"]["fraud_risk"]["level"] == "high", "estimate": claim.get("estimate"),
        "payable": d["settlement"]["payable"], "assignee": s.get("assignee") or claim["assignee"],
        "thumb": media(claim["footage"]["thumb"]), "camera": claim["footage"]["camera"],
        "fault": d["fault"]["label"], "lat": claim["lat"], "lon": claim["lon"],
    }


def activity(claim: dict, decision: dict) -> list[dict]:
    t0 = datetime.fromisoformat(claim["reportedAt"])
    dets = DETECTIONS[claim["footage"]["still"]]["detections"]
    counts = Counter(d["label"] for d in dets)
    verdicts = Counter(c["verdict"] for c in claim["statement"]["claims"])
    vehicles = counts["car"] + counts["truck"] + counts["bus"]
    log = [
        (0, "Poodle", f"Opened the claim from {claim['channel'].lower()}."),
        (3, "Ingest agent", f"Hashed {len(custody(claim))} files with SHA-256 and logged custody."),
        (8, "Perception agent", f"YOLO11s found {vehicles} vehicles" + (f" and {counts['traffic light']} signal heads." if counts["traffic light"] else ".")),
        (11, "Context agent", f"Placed the incident at {claim['place']} and linked the nearest TfL cameras."),
    ]
    if claim["statement"]["claims"]:
        log.append((14, "Statement agent", f"Checked the statement: {verdicts['supported']} supported, "
                                          f"{verdicts['contradicted']} contradicted, {verdicts['unverifiable']} unverifiable."))
    log.append((16, "Coverage agent", f"Recommended {decision['label'].lower()} ({decision['record']['mode']} Jev answers)."))
    out = [{"at": (t0 + timedelta(seconds=s)).isoformat(), "actor": a, "text": t} for s, a, t in log]
    out.extend(STATE.get(claim["id"], {}).get("activity", []))
    return out


def full(claim: dict) -> dict:
    d = evaluate(claim)
    policy = POLICIES[claim["policyId"]]
    det = DETECTIONS[claim["footage"]["still"]]
    cites = {k: {**WORDING[k], "kind": "clause"} for k in WORDING} | {k: {**RULES[k], "kind": "rule"} for k in RULES}
    f = claim["footage"]
    return {
        **claim,
        **summary(claim),
        "footage": {**f, "clip": media(f["clip"]), "poster": media(f["poster"]), "thumb": media(f["thumb"])},
        "policy": {**policy, "id": claim["policyId"], "coverLabel": COVER_LABEL[policy["cover"]],
                   "excessTotal": policy["excess"]["compulsory"] + policy["excess"]["voluntary"]},
        "decision": d,
        "detections": det,
        "evidence": custody(claim),
        "attachments": STATE.get(claim["id"], {}).get("attachments", []),
        "activity": activity(claim, d),
        "citations": cites,
    }


@asynccontextmanager
async def lifespan(_: FastAPI):
    global http
    http = httpx.AsyncClient(headers={"User-Agent": "poodle-claims-desk/1.0"})
    FRAMES.mkdir(exist_ok=True)
    try:
        await tfl.cameras(http)
    except Exception as exc:
        print("TfL warm-up failed:", exc)
    for c in CLAIMS:
        custody(c)
    yield
    await http.aclose()


app = FastAPI(title="Poodle", lifespan=lifespan)


@app.get("/api/health")
async def health():
    await tfl.cameras(http)
    svc = services.services_status(tfl.status())
    return {"ok": True, "mode": "live" if all(s["status"] == "live" for s in svc) else "replay", "services": svc}


@app.get("/api/claims")
async def list_claims():
    return [summary(c) for c in CLAIMS]


@app.get("/api/claims/{claim_id}")
async def get_claim(claim_id: str):
    claim = find(claim_id)
    if claim_id not in JEV_LIVE:
        try:
            live = await services.jev_decide(http, claim, POLICIES[claim["policyId"]], WORDING)
            if live:
                JEV_LIVE[claim_id] = live
        except Exception as exc:
            print("Jev call failed, using seeded answers:", exc)
    return full(claim)


class Ask(BaseModel):
    question: str


@app.post("/api/claims/{claim_id}/ask")
async def ask(claim_id: str, body: Ask):
    claim = find(claim_id)
    started = time.perf_counter()
    result, source = None, "Rule-based (replay)"
    try:
        result = await services.llm_answer(http, claim, body.question)
        if result:
            source = "W&B Inference"
    except Exception as exc:
        print("LLM answer failed, using replay:", exc)
    if not result:
        result = answer(claim, body.question)
    by_id = {f["id"]: f for f in claim["findings"]}
    result["citations"] = [{**by_id[c["finding"]]} for c in result["citations"] if c.get("finding") in by_id]
    result.update(source=source, ms=round((time.perf_counter() - started) * 1000), question=body.question)
    services.record_event({"claim": claim_id, "kind": "question", "question": body.question, "answer": result["answer"]})
    return result


class Action(BaseModel):
    action: str
    by: str = "You"
    note: str | None = None


@app.post("/api/claims/{claim_id}/action")
async def act(claim_id: str, body: Action):
    claim = find(claim_id)
    s = STATE.setdefault(claim_id, {})
    label = evaluate(claim)["label"].lower()
    if body.action == "approve":
        s["status"] = "done"
        text = f"Confirmed the recommendation: {label}."
    elif body.action == "refer":
        s["status"] = "review"
        s["assignee"] = "SIU team"
        text = "Referred to the special investigations unit."
    elif body.action == "assign":
        s["assignee"] = body.by
        text = f"Assigned to {body.by}."
    elif body.action == "reopen":
        s.pop("status", None)
        text = "Reopened the claim."
    else:
        raise HTTPException(400, f"Unknown action {body.action}")
    s.setdefault("activity", []).append({"at": datetime.now().isoformat(timespec="seconds"), "actor": body.by, "text": text})
    save_state()
    services.record_event({"claim": claim_id, "kind": body.action, "by": body.by})
    return full(claim)


async def fetch_frame(cam: dict) -> tuple[bytes, str, str | None]:
    r = await http.get(cam["image"], params={"t": int(time.time())}, timeout=15)
    r.raise_for_status()
    return r.content, hashlib.sha256(r.content).hexdigest(), r.headers.get("last-modified")


async def cam_by_id(cam_id: str) -> dict:
    for c in await tfl.cameras(http):
        if c["id"] == cam_id:
            return c
    raise HTTPException(404, f"No camera {cam_id}")


@app.get("/api/cams")
async def cams(near: str | None = None, n: int = 6, q: str | None = None):
    all_cams = await tfl.cameras(http)
    if near:
        lat, lon = (float(x) for x in near.split(","))
        return tfl.nearest(all_cams, lat, lon, n)
    if q:
        ql = q.lower()
        return [c for c in all_cams if ql in c["name"].lower() or ql in c["view"].lower()][:n]
    return all_cams


@app.post("/api/cams/{cam_id}/scan")
async def scan(cam_id: str):
    cam = await cam_by_id(cam_id)
    frame, digest, modified = await fetch_frame(cam)
    result = await services.detect(http, frame)
    counts = Counter(d["label"] for d in result["detections"])
    taken = parsedate_to_datetime(modified).astimezone().isoformat(timespec="seconds") if modified else None
    return {"cam": cam, "frame": "data:image/jpeg;base64," + base64.b64encode(frame).decode(), "sha256": digest,
            "fetchedAt": datetime.now().isoformat(timespec="seconds"), "takenAt": taken, "counts": counts, **result}


class Attach(BaseModel):
    camId: str


@app.post("/api/claims/{claim_id}/attach")
async def attach(claim_id: str, body: Attach):
    claim = find(claim_id)
    cam = await cam_by_id(body.camId)
    frame, digest, _ = await fetch_frame(cam)
    name = f"{claim_id}-{cam['id']}-{int(time.time())}.jpg"
    (FRAMES / name).write_bytes(frame)
    item = {"file": name, "label": f"TfL JamCam {cam['name']}", "camId": cam["id"], "bytes": len(frame), "sha256": digest,
            "source": "TfL JamCams (Powered by TfL Open Data)", "loggedAt": datetime.now().isoformat(timespec="seconds"),
            "by": "You", "distance": round(tfl.distance_m(claim["lat"], claim["lon"], cam["lat"], cam["lon"]))}
    s = STATE.setdefault(claim_id, {})
    s.setdefault("attachments", []).append(item)
    s.setdefault("activity", []).append({"at": item["loggedAt"], "actor": "You",
                                         "text": f"Attached a live frame from {cam['name']} ({item['distance']} m away)."})
    save_state()
    services.record_event({"claim": claim_id, "kind": "attach", "cam": cam["id"], "sha256": digest})
    return full(claim)


@app.get("/api/claims/{claim_id}/pack", response_class=HTMLResponse)
async def pack(claim_id: str):
    c = full(find(claim_id))
    d = c["decision"]
    e = html.escape

    def cite(key):
        return f' <span class="cite">{e(c["citations"][key]["title"])}</span>' if key and key in c["citations"] else ""

    rows = "".join(f"<tr><td>{e(x['label'])}</td><td>{e(x['file'])}</td><td><code>{x['sha256']}</code></td>"
                   f"<td>{e(x['loggedAt'])}</td><td>{e(x['by'])}</td></tr>" for x in c["evidence"] + c["attachments"])
    findings = "".join(f"<li>{e(f['text'])} <span class='muted'>{e(f['source'])}, {f['conf']:.2f}</span></li>" for f in c["findings"])
    stmt = "".join(f"<li><b>{e(s['verdict'])}</b>: {e(s['text'])}</li>" for s in c["statement"]["claims"]) or "<li>No statement yet.</li>"
    cov = "".join(f"<li>Covered: {e(x['name'])}. {e(x['detail'])}{cite(x.get('cite'))}</li>" for x in d["covered"])
    cov += "".join(f"<li>Not covered: {e(x['name'])}. {e(x['detail'])}{cite(x.get('cite'))}</li>" for x in d["notCovered"])
    reasons = "".join(f"<li>{e(r['text'])}{cite(r.get('cite'))}</li>" for r in d["reasons"])
    checks = "".join(f"<li>{'Pass' if x['pass'] else 'Fail'}: {e(x['label'])} ({e(x['detail'])})</li>" for x in d["checks"])
    st = d["settlement"]
    poster = c["footage"]["poster"]
    poster = poster if poster.startswith("http") else f"/{poster}"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Evidence pack {e(c['id'])}</title>
<style>body{{font:14px/1.5 Inter,system-ui,sans-serif;color:#1b1c1f;max-width:900px;margin:40px auto;padding:0 24px}}
h1{{font-size:22px;margin:0}}h2{{font-size:15px;margin:28px 0 8px;border-bottom:1px solid #e4e4e7;padding-bottom:6px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border-bottom:1px solid #eee;padding:6px 8px;text-align:left;vertical-align:top}}
code{{font:11px ui-monospace,Menlo,monospace;word-break:break-all}}.muted{{color:#6b6f76}}.cite{{color:#5e6ad2;font-size:12px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;background:#f1f1f4;font-weight:600}}img{{max-width:100%;border-radius:6px}}</style></head><body>
<p class="muted">Poodle evidence pack · generated {datetime.now():%d %b %Y %H:%M} · demo footage, synthetic policy</p>
<h1>{e(c['id'])}: {e(c['title'])}</h1>
<p>{e(c['place'])}, {e(c['area'])} · incident {e(c['incidentAt'].replace('T', ' '))} · policy {e(c['policy']['id'])} ({e(c['policy']['coverLabel'])})</p>
<p><span class="badge">{e(d['label'])}</span> · {e(d['fault']['label'])} · payable {money(st['payable'])} · excess {money(st['excess'])}</p>
<img src="{e(poster)}" alt="Incident frame from {e(c['footage']['camera'])}">
<h2>Why</h2><ul>{reasons}</ul><h2>Coverage</h2><ul>{cov or '<li>Held for a handler.</li>'}</ul>
<h2>Hard-rule checks</h2><ul>{checks}</ul><h2>What the footage shows</h2><ul>{findings}</ul>
<h2>Statement check</h2><p class="muted">{e(c['statement']['text'] or '')}</p><ul>{stmt}</ul>
<h2>Chain of custody</h2><table><tr><th>Item</th><th>File</th><th>SHA-256</th><th>Logged</th><th>By</th></tr>{rows}</table>
<h2>Decision record</h2><pre><code>{e(json.dumps(d['record'], indent=2))}</code></pre></body></html>"""


@app.get("/api/claims/{claim_id}/pack.json")
async def pack_json(claim_id: str):
    return JSONResponse(full(find(claim_id)))


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
