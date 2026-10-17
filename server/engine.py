"""Coverage decision and footage Q&A for Poodle.

Three layers, as in docs/IDEA.md:
- code owns hard rules, dates, arithmetic and the decision table (this file);
- Jev supplies typed judgments (peril, exclusion, fault band, ...). Without a key the
  seeded answers in data/claims.json stand in and the record says so;
- an LLM only writes prose (Q&A answers when W&B Inference is configured).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data"
WEB = ROOT / "poodle"

THRESHOLDS = {"floor": 0.5, "reject": 0.9}
UK_BOX = (49.8, 60.9, -8.7, 1.8)  # lat min, lat max, lon min, lon max

COVER_LABEL = {
    "comprehensive": "Comprehensive",
    "third_party_fire_theft": "Third party, fire and theft",
    "third_party_only": "Third party only",
}
FAULT_LABEL = {
    "not_at_fault": "Not at fault",
    "shared_fault": "Shared fault",
    "mostly_at_fault": "Mostly at fault",
    "fully_at_fault": "Fully at fault",
    "cannot_determine": "Cannot determine",
}
OUTCOME_LABEL = {"accept": "Accept", "partial": "Accept, partial", "reject": "Reject", "refer": "Refer to handler"}


def load_json(name: str):
    return json.loads((DATA / name).read_text())


def noul_conf(p: float) -> float:
    return round(abs(2 * p - 1), 2)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def money(v: float | int | None) -> str:
    return "—" if v is None else f"£{v:,.0f}"


# ---------------------------------------------------------------- hard rules (code)

def hard_checks(claim: dict, policy: dict) -> list[dict]:
    when = datetime.fromisoformat(claim["incidentAt"]).date()
    start, end = date.fromisoformat(policy["start"]), date.fromisoformat(policy["end"])
    lat_ok = UK_BOX[0] <= claim["lat"] <= UK_BOX[1] and UK_BOX[2] <= claim["lon"] <= UK_BOX[3]
    named = claim["driver"] in policy["namedDrivers"]
    return [
        {"id": "in_force", "label": "Policy in force on the incident date", "pass": start <= when <= end,
         "detail": f"{policy['start']} to {policy['end']}"},
        {"id": "vehicle", "label": "Vehicle matches the schedule", "pass": claim["vehicleReg"] == policy["vehicle"]["reg"],
         "detail": claim["vehicleReg"]},
        {"id": "driver", "label": "Driver named on the schedule", "pass": named,
         "detail": claim["driver"] if named else f"{claim['driver']} is not named", "clause": None if named else "E1"},
        {"id": "territory", "label": "Incident inside the territory", "pass": lat_ok,
         "detail": f"{claim['lat']:.4f}, {claim['lon']:.4f}", "clause": None if lat_ok else "E6"},
    ]


# ---------------------------------------------------------------- decision table (code)

def decide(claim: dict, policy: dict, jev: dict, jev_mode: str) -> dict:
    checks = hard_checks(claim, policy)
    excess = policy["excess"]["compulsory"] + policy["excess"]["voluntary"]
    estimate = claim.get("estimate")
    cover = policy["cover"]
    fault = jev["fault_band"]["level"]
    covers_p = jev["section_covers_peril"]["noul"]
    evidence_p = jev["evidence_sufficient"]["noul"]
    key_conf = {
        "peril": jev["peril"]["confidence"],
        "section_covers_peril": noul_conf(covers_p),
        "exclusion": jev["exclusion"]["confidence"],
        "fault_band": jev["fault_band"]["confidence"],
        "evidence_sufficient": noul_conf(evidence_p),
        "fraud_risk": jev["fraud_risk"]["confidence"],
    }
    low = [k for k, v in key_conf.items() if v < THRESHOLDS["floor"]]
    reasons: list[dict] = []
    covered: list[dict] = []
    not_covered: list[dict] = []
    branch = ""

    failed = [c for c in checks if not c["pass"]]
    if failed:
        outcome, branch = "reject", "hard_rule_failed"
        for c in failed:
            reasons.append({"text": f"{c['label']}: failed ({c['detail']}).", "cite": c.get("clause")})
        not_covered.append({"name": "Damage to your car", "detail": "Hard-rule check failed, see reasons.", "cite": failed[0].get("clause")})
        covered.append({"name": "Liability to others", "detail": "The third party's claim is still handled under the law.", "cite": "S2"})
    elif evidence_p < 0.5 or fault == "cannot_determine" or jev["fraud_risk"]["level"] == "high" or low:
        outcome, branch = "refer", "uncertain"
        if jev["fraud_risk"]["level"] == "high":
            reasons.append({"text": "Fraud-risk signals are high. A person reviews this; it is not an accusation.", "cite": None})
        if evidence_p < 0.5:
            reasons.append({"text": "Not enough evidence to decide cover yet.", "cite": None})
        if fault == "cannot_determine":
            reasons.append({"text": "Fault cannot be determined from the footage.", "cite": None})
        for k in low:
            reasons.append({"text": f"`{k}` is below the {THRESHOLDS['floor']} confidence floor ({key_conf[k]:.2f}).", "cite": None})
    elif jev["exclusion"]["choice"] != "none" and jev["exclusion"]["confidence"] >= THRESHOLDS["reject"]:
        outcome, branch = "reject", "exclusion"
        clause = jev["exclusion"]["choice"]
        reasons.append({"text": "An exclusion applies.", "cite": clause})
        not_covered.append({"name": "Damage to your car", "detail": "Excluded by the policy wording.", "cite": clause})
    elif covers_p < 0.5 and noul_conf(covers_p) >= THRESHOLDS["reject"]:
        outcome, branch = "reject", "section_not_covered"
        reasons.append({"text": f"{COVER_LABEL[cover]} cover does not include damage to your own car.", "cite": "S1"})
        if fault in ("mostly_at_fault", "fully_at_fault"):
            reasons.append({"text": f"The footage puts the policyholder {FAULT_LABEL[fault].lower()}.", "cite": (claim.get("rules") or [None])[0]})
        not_covered.append({"name": "Damage to your car", "detail": f"Section 1 is not part of {COVER_LABEL[cover].lower()} cover.", "cite": "S1"})
        covered.append({"name": "Liability to others", "detail": "The third party's repairs are handled under Section 2.", "cite": "S2"})
    else:
        branch = "covered"
        covered.append({"name": "Damage to your car", "detail": f"Repair estimate {money(estimate)}, less the {money(excess)} excess.", "cite": "S1"})
        if fault == "not_at_fault":
            covered.append({"name": "Excess recovered", "detail": "Not-at-fault claim: the excess is recovered from the other insurer.", "cite": "S1"})
        if fault == "not_at_fault" or "protected_ncd" in policy["addOns"]:
            covered.append({"name": "No-claims discount kept", "detail": "Not at fault or protected." if fault == "not_at_fault" else "Protected NCD is on the schedule.", "cite": "S6"})
        else:
            not_covered.append({"name": "No-claims discount", "detail": "Reduced at renewal unless costs are recovered.", "cite": "S6"})
        # A benefit counts only when the facts qualify for it (Jev noul >= 0.5).
        for addon, clause, name, key in (("courtesy_car", "B1", "Courtesy car", "benefit_courtesy_car"),
                                          ("legal_expenses", "B2", "Legal expenses", "benefit_legal_expenses")):
            if jev[key]["noul"] < 0.5:
                continue
            if addon in policy["addOns"]:
                covered.append({"name": name, "detail": "Add-on applies to this claim.", "cite": clause})
            else:
                not_covered.append({"name": name, "detail": "That add-on is not on the schedule.", "cite": clause})
        partial = bool(not_covered) or fault == "shared_fault"
        under_limit = estimate is not None and estimate <= policy["autoSettle"]
        rule = (claim.get("rules") or [None])[0]
        if fault == "not_at_fault":
            reasons.append({"text": "The footage puts the other driver at fault.", "cite": rule})
        if partial:
            outcome = "partial"
            if fault == "shared_fault":
                reasons.append({"text": "Shared fault: 50% of costs recovered from the other insurer.", "cite": rule})
            missing = [x["name"].lower() for x in not_covered]
            reasons.append({"text": "Your own repair is covered under Section 1." + (f" Not included: {', '.join(missing)}." if missing else ""), "cite": None})
        elif under_limit and jev["fraud_risk"]["level"] == "low":
            outcome = "accept"
            reasons.append({"text": f"Covered, no exclusion, low fraud risk, estimate under the {money(policy['autoSettle'])} auto-settle limit.", "cite": None})
        else:
            outcome = "accept"
            reasons.append({"text": "Covered. Above the auto-settle limit, so a handler confirms.", "cite": None})

    limit = policy["vehicle"]["value"]
    payable = None
    recovery = None
    if outcome in ("accept", "partial") and estimate is not None:
        payable = max(0, min(estimate, limit) - excess)
        if fault == "not_at_fault":
            recovery = estimate
        elif fault == "shared_fault":
            recovery = round(estimate * 0.5)
    straight_through = outcome == "accept" and estimate is not None and estimate <= policy["autoSettle"]
    return {
        "outcome": outcome,
        "label": OUTCOME_LABEL[outcome],
        "needsReview": not straight_through,
        "straightThrough": straight_through,
        "reasons": reasons,
        "covered": covered,
        "notCovered": not_covered,
        "checks": checks,
        "settlement": {"estimate": estimate, "limit": limit, "excess": excess, "payable": payable, "recovery": recovery},
        "fault": {"level": fault, "label": FAULT_LABEL[fault], "confidence": jev["fault_band"]["confidence"]},
        "record": {
            "decider": "Jev typed answers + code decision table",
            "model": "jev-1.14.0",
            "mode": jev_mode,
            "thresholds": THRESHOLDS,
            "keyConfidence": key_conf,
            "branch": branch,
            "answers": jev,
        },
    }


# ---------------------------------------------------------------- footage Q&A (replay)

INTENTS = [
    (r"\b(light|signal|red|green|amber)\b", ("signal",)),
    (r"\b(indicat|blinker|signall)", ("signal",)),
    (r"\b(impact|hit|collid|crash|contact|where)\b", ("impact",)),
    (r"\b(weather|rain|wet|dark|night|light(ing)?|visib)", ("weather", "light", "road")),
    (r"\b(speed|fast|mph|brak|stop(ped)?)\b", ("motion",)),
    (r"\b(give.?way|junction|roundabout|lane|road|marking|sign)\b", ("road",)),
    (r"\b(car|vehicle|van|bus|who|colour|color)\b", ("vehicle",)),
]


def answer(claim: dict, question: str) -> dict:
    q = question.lower()
    findings = claim["findings"]
    hits: list[dict] = []
    for pattern, ks in INTENTS:  # the first intent with matching findings wins
        if re.search(pattern, q):
            hits = [f for f in findings if f["kind"] in ks]
            if hits:
                break
    if re.search(r"\b(speed|mph|fast)\b", q) and not any(f["kind"] == "motion" for f in hits):
        return {"answer": "Not visible. Speed needs GPS, telematics or a second camera; this clip cannot show it.",
                "grounded": False, "citations": []}
    if re.search(r"\bindicat", q):
        ind = [f for f in findings if "indicator" in f["text"].lower()]
        if not ind or ind[0]["conf"] < 0.5:
            return {"answer": "Not visible. Indicators cannot be seen in this footage after the impact.",
                    "grounded": False, "citations": [{"finding": ind[0]["id"]}] if ind else []}
    if not hits:
        return {"answer": "Not visible in this footage. Try asking about the signals, the point of impact, the vehicles or the road.",
                "grounded": False, "citations": []}
    hits.sort(key=lambda f: -f["conf"])
    top = [f for f in hits if f["conf"] >= 0.5][:2] or hits[:1]
    weak = all(f["conf"] < 0.5 for f in top)
    text = " ".join(f["text"] for f in top)
    if weak:
        text = f"Unclear. {text}"
    return {"answer": text, "grounded": not weak, "citations": [{"finding": f["id"]} for f in top]}
