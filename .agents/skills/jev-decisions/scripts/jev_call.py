#!/usr/bin/env python3
"""One TypeSafe System One (Jev) call from the command line, stdlib only.

Backend resolution (first match wins):
  TYPESAFE_API_KEY   -> https://api.typesafe.ai          models: jev-1.14.0, jev-1.13.0, jev-latest, jev-preview
  OPENROUTER_API_KEY -> https://openrouter.ai/api        models: typesafe/jev-1.14, typesafe/jev-1.13
Override the base URL with JEV_BASE_URL and the model with JEV_MODEL or --model.

Examples:
  jev_call.py --state-text "Help! My payouts have been failing for 3 days." \
      --questions '{"urgent": {"type": "noul", "instructions": "Does the message convey urgency?"}}'
  jev_call.py --image frame=frame.jpg --questions questions.json --dry-run
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

DIRECT_BASE = "https://api.typesafe.ai"
OPENROUTER_BASE = "https://openrouter.ai/api"
IMAGES_HEADER = "TypeSafe-Danger-Zone-Images"
LONG_CONTEXT_HEADER = "TypeSafe-Danger-Zone-Long-Context"
DEFAULT_MODEL = {"typesafe": "jev-1.14.0", "openrouter": "typesafe/jev-1.14", "none": "jev-1.14.0"}


class JevError(Exception):
    """A request could not be built or the API refused it."""


def resolve_backend() -> tuple[str, str | None, str]:
    """Return (base_url, api_key, backend_name) from the environment."""
    base = os.environ.get("JEV_BASE_URL")
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return base or DIRECT_BASE, key, "typesafe"
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return base or OPENROUTER_BASE, key, "openrouter"
    return base or DIRECT_BASE, None, "none"


def default_model(backend: str) -> str:
    return os.environ.get("JEV_MODEL") or DEFAULT_MODEL.get(backend, "jev-1.14.0")


def image_asset(path: str) -> tuple[str, dict[str, str]]:
    """Read a PNG or JPEG file and return (reference, asset entry) for the `assets` map."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        fmt = "png"
    elif data[:3] == b"\xff\xd8\xff":
        fmt = "jpg"
    else:
        raise JevError(f"{path}: not a PNG or JPEG file (Jev accepts only those, as stills)")
    if len(data) > 16 * 1024 * 1024:
        raise JevError(f"{path}: over the 16 MiB per-image limit")
    ref = f"img-{uuid.uuid4()}"
    return ref, {"type": "image", "format": fmt, "data_base64": base64.b64encode(data).decode("ascii")}


def build_request(model: str, state: Any, questions: dict[str, Any], images: dict[str, str] | None = None) -> dict[str, Any]:
    """Assemble a System One request. `images` maps a state field name to an image path;
    the field receives the image's reference and the image goes into `assets`."""
    if not isinstance(questions, dict) or not questions:
        raise JevError("questions must be a non-empty object keyed by question id")
    for qid, q in questions.items():
        if not isinstance(q, dict) or q.get("type") not in {"noul", "choice", "score", "box"}:
            raise JevError(f"question {qid!r}: type must be noul, choice, score or box")
        if q["type"] in {"choice", "score"} and "criteria" not in q:
            raise JevError(f"question {qid!r}: {q['type']} needs criteria")
    assets: dict[str, Any] = {}
    if images:
        if state is None:
            state = {}
        if not isinstance(state, dict):
            raise JevError("--image needs an object state so the reference can be stored under a field name")
        for name, path in images.items():
            ref, asset = image_asset(path)
            assets[ref] = asset
            state[name] = ref
    if state is None:
        raise JevError("state is required")
    req: dict[str, Any] = {"model": model, "state": state, "questions": questions}
    if assets:
        req["assets"] = assets
    return req


def needs_images_header(req: dict[str, Any]) -> bool:
    return bool(req.get("assets")) or any(q.get("type") == "box" for q in req["questions"].values())


def send(req: dict[str, Any], base_url: str, api_key: str, *, long_context: bool = False,
         timeout: float = 30.0, max_retries: int = 4) -> dict[str, Any]:
    """POST the request; retry 429/529 and connection errors with exponential backoff."""
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    if needs_images_header(req):
        headers[IMAGES_HEADER] = "true"
    if long_context:
        headers[LONG_CONTEXT_HEADER] = "true"
    body = json.dumps(req).encode("utf-8")
    url = base_url.rstrip("/") + "/v1/systemone"
    delay = 1.0
    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 529) and attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise JevError(f"HTTP {e.code} from {url}: {text[:2000]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise JevError(f"could not reach {url}: {e}") from None
    raise JevError("unreachable")


def redacted(req: dict[str, Any]) -> dict[str, Any]:
    """Copy of the request with base64 image data replaced by its size, for logs and dry runs."""
    out = copy.deepcopy(req)
    for asset in out.get("assets", {}).values():
        if "data_base64" in asset:
            asset["data_base64"] = f"<{len(asset['data_base64'])} base64 chars>"
    return out


def box_to_pixels(box: dict[str, float], width: int, height: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) in pixels for a Box answer."""
    return (round(box["left"] * width), round(box["top"] * height),
            round(box["right"] * width), round(box["bottom"] * height))


def summarize(resp: dict[str, Any]) -> list[str]:
    lines = [f"model={resp.get('model')} usage={resp.get('usage')}"]
    for qid, a in resp.get("answers", {}).items():
        t = a.get("type")
        if t == "noul":
            lines.append(f"  {qid}: noul={a['noul']:.2f}")
        elif t == "choice":
            lines.append(f"  {qid}: choice={a['choice']} confidence={a.get('confidence', 0):.2f} probabilities={_fmt(a.get('probabilities', {}))}")
        elif t == "score":
            lines.append(f"  {qid}: score={a['score']:.2f} confidence={a.get('confidence', 0):.2f} probabilities={_fmt(a.get('probabilities', {}))}")
        elif t == "box":
            b = a["box"]
            conf = a.get("confidence")
            conf_s = f"{conf:.2f}" if isinstance(conf, (int, float)) else "n/a"
            lines.append(f"  {qid}: box top={b['top']:.3f} bottom={b['bottom']:.3f} left={b['left']:.3f} right={b['right']:.3f} confidence={conf_s}")
        else:
            lines.append(f"  {qid}: {a}")
    return lines


def _fmt(probs: dict[str, float]) -> str:
    return "{" + ", ".join(f"{k}: {v:.2f}" for k, v in probs.items()) + "}"


def load_json_arg(value: str) -> Any:
    """Parse inline JSON, or read a JSON file when the value is an existing path."""
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise JevError(f"not JSON and not a file: {value[:80]!r} ({e})") from None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_mutually_exclusive_group()
    s.add_argument("--state-json", help="inline JSON or path to a JSON file for `state`")
    s.add_argument("--state-text", help="plain string state")
    p.add_argument("--questions", required=True, help="inline JSON or path; a map of id -> question, or an object with a `questions` key")
    p.add_argument("--image", action="append", default=[], metavar="NAME=PATH",
                   help="attach an image under state field NAME (repeatable); adds the images header")
    p.add_argument("--model", help="model id (default: JEV_MODEL, else the backend's default)")
    p.add_argument("--long-context", action="store_true", help="send the long-context danger-zone header")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--dry-run", action="store_true", help="print the request (images redacted) and exit without sending")
    args = p.parse_args(argv)

    try:
        questions = load_json_arg(args.questions)
        if isinstance(questions, dict) and "questions" in questions and all(
                not (isinstance(v, dict) and "type" in v) for k, v in questions.items() if k != "questions"):
            questions = questions["questions"]
        state: Any = None
        if args.state_json is not None:
            state = load_json_arg(args.state_json)
        elif args.state_text is not None:
            state = args.state_text
        images: dict[str, str] = {}
        for item in args.image:
            if "=" not in item:
                raise JevError(f"--image expects NAME=PATH, got {item!r}")
            name, path = item.split("=", 1)
            images[name] = path
        base, key, backend = resolve_backend()
        model = args.model or default_model(backend)
        req = build_request(model, state, questions, images)
        if args.dry_run:
            print(json.dumps({"backend": backend, "base_url": base, "headers": {
                IMAGES_HEADER: needs_images_header(req), LONG_CONTEXT_HEADER: args.long_context},
                "request": redacted(req)}, indent=2))
            return 0
        if not key:
            raise JevError("no API key: set TYPESAFE_API_KEY or OPENROUTER_API_KEY (or use --dry-run)")
        resp = send(req, base, key, long_context=args.long_context, timeout=args.timeout)
    except JevError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(resp, indent=2))
    print("\n".join(summarize(resp)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
