#!/usr/bin/env python3
"""Judge every sampled frame of a video with Jev and write a JSONL timeline plus events.

Needs ffmpeg on PATH when --video is used (frames are extracted and scaled to fit Jev's
image limits). With --frames, a directory of PNG/JPEG stills is used as-is.

questions.json layout (keep questions AND thresholds in this one reviewable file):
{
  "model": "jev-1.14.0",                      # optional; --model and JEV_MODEL win
  "thresholds": {"<noul id>": 0.6, ...},      # optional; default --threshold
  "questions": {"<id>": {"type": "noul|choice|score|box", "instructions": "... `frame` ...", ...}},
  "change_questions": {"<id>": {...}}         # optional; only sent with --previous, may mention `previous_frame`
}

Examples:
  jev_video_triage.py --video clip.mp4 --fps 1 --questions q.json --out timeline.jsonl --dry-run
  jev_video_triage.py --frames ./frames --questions q.json --previous --concurrency 4
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jev_call import (JevError, build_request, default_model, image_asset, needs_images_header,  # noqa: E402
                      redacted, resolve_backend, send, summarize)

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


def extract_frames(video: str, out_dir: str, fps: float, max_side: int, max_frames: int | None) -> list[str]:
    """Sample `fps` frames per second with ffmpeg, longest side <= max_side, baseline JPEG."""
    if not shutil.which("ffmpeg"):
        raise JevError("ffmpeg not found on PATH; install it or pass --frames with extracted stills")
    scale = (f"scale=w='if(gt(iw,ih),min(iw,{max_side}),-2)':h='if(gt(iw,ih),-2,min(ih,{max_side}))'")
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video,
           "-vf", f"fps={fps},{scale}", "-q:v", "3"]
    if max_frames:
        cmd += ["-frames:v", str(max_frames)]
    cmd.append(os.path.join(out_dir, "frame_%05d.jpg"))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise JevError(f"ffmpeg failed: {proc.stderr.strip()[:1000]}")
    return list_frames(out_dir)


def list_frames(directory: str) -> list[str]:
    files = sorted(f for f in os.listdir(directory) if os.path.splitext(f)[1].lower() in IMAGE_EXTS)
    if not files:
        raise JevError(f"no PNG/JPEG frames in {directory}")
    return [os.path.join(directory, f) for f in files]


def load_spec(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        spec = json.load(f)
    if "questions" not in spec:            # bare map of questions
        spec = {"questions": spec}
    if not isinstance(spec["questions"], dict) or not spec["questions"]:
        raise JevError("questions.json needs a non-empty `questions` object")
    return spec


def frame_request(model: str, spec: dict[str, Any], frame: str, t: float, previous: str | None) -> dict[str, Any]:
    questions = dict(spec["questions"])
    images = {"frame": frame}
    if previous is not None:
        images["previous_frame"] = previous
        questions.update(spec.get("change_questions", {}))
    state: dict[str, Any] = {"t_seconds": f"{t:.2f}"}
    return build_request(model, state, questions, images)


def judge_frame(idx: int, frame: str, t: float, previous: str | None, model: str, spec: dict[str, Any],
                base: str, key: str, timeout: float) -> dict[str, Any]:
    row: dict[str, Any] = {"i": idx, "t": round(t, 3), "file": os.path.basename(frame)}
    try:
        req = frame_request(model, spec, frame, t, previous)
        resp = send(req, base, key, timeout=timeout)
        row.update({"model": resp.get("model"), "answers": resp.get("answers", {}), "usage": resp.get("usage")})
    except JevError as e:
        row["error"] = str(e)
    return row


def events_from_rows(rows: list[dict[str, Any]], thresholds: dict[str, float], default: float) -> dict[str, list[dict[str, Any]]]:
    """Merge consecutive frames whose Noul >= threshold into [start, end] events per question."""
    events: dict[str, list[dict[str, Any]]] = {}
    noul_ids = sorted({qid for r in rows for qid, a in r.get("answers", {}).items() if a.get("type") == "noul"})
    for qid in noul_ids:
        thr = thresholds.get(qid, default)
        current: dict[str, Any] | None = None
        out: list[dict[str, Any]] = []
        for r in rows:
            a = r.get("answers", {}).get(qid)
            hit = a is not None and a.get("noul", 0.0) >= thr
            if hit:
                p = a["noul"]
                if current is None:
                    current = {"start": r["t"], "end": r["t"], "frames": 1, "max_noul": p}
                else:
                    current["end"] = r["t"]
                    current["frames"] += 1
                    current["max_noul"] = max(current["max_noul"], p)
            elif current is not None:
                out.append(current)
                current = None
        if current is not None:
            out.append(current)
        if out:
            events[qid] = out
    return events


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--video", help="video file; frames are sampled with ffmpeg")
    src.add_argument("--frames", help="directory of PNG/JPEG stills, judged in sorted order")
    p.add_argument("--questions", required=True, help="questions.json (see module docstring)")
    p.add_argument("--out", default="timeline.jsonl", help="JSONL output, one row per frame")
    p.add_argument("--fps", type=float, default=1.0, help="frames per second to sample (also sets t for --frames)")
    p.add_argument("--max-side", type=int, default=1280, help="longest side after scaling (Jev max 1568)")
    p.add_argument("--max-frames", type=int, help="stop after this many frames")
    p.add_argument("--previous", action="store_true", help="also send the previous frame and the change_questions")
    p.add_argument("--model", help="model id (default: --questions model, JEV_MODEL, backend default)")
    p.add_argument("--threshold", type=float, default=0.5, help="default Noul threshold for events")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument("--work-dir", help="where extracted frames go (default: a temp dir that is removed)")
    p.add_argument("--dry-run", action="store_true", help="print the first frame's request (images redacted) and exit")
    args = p.parse_args(argv)

    tmp: str | None = None
    try:
        spec = load_spec(args.questions)
        base, key, backend = resolve_backend()
        model = args.model or os.environ.get("JEV_MODEL") or spec.get("model") or default_model(backend)
        has_box = any(q.get("type") == "box" for q in spec["questions"].values())
        if has_box and backend == "typesafe" and model not in {"jev-1.14.0", "jev-preview"}:
            print(f"warning: box questions need jev-1.14.0 or jev-preview; model is {model}", file=sys.stderr)

        if args.video:
            work = args.work_dir or (tmp := tempfile.mkdtemp(prefix="jev-frames-"))
            os.makedirs(work, exist_ok=True)
            frames = extract_frames(args.video, work, args.fps, args.max_side, args.max_frames)
        else:
            frames = list_frames(args.frames)
            if args.max_frames:
                frames = frames[: args.max_frames]
        times = [i / args.fps for i in range(len(frames))]
        print(f"{len(frames)} frames, backend={backend}, model={model}, previous={args.previous}", file=sys.stderr)

        if args.dry_run:
            prev = frames[0] if args.previous and len(frames) > 1 else None
            idx = 1 if prev else 0
            req = frame_request(model, spec, frames[idx], times[idx], prev)
            print(json.dumps({"backend": backend, "base_url": base,
                              "headers": {"TypeSafe-Danger-Zone-Images": needs_images_header(req)},
                              "frames": len(frames), "request": redacted(req)}, indent=2))
            return 0
        if not key:
            raise JevError("no API key: set TYPESAFE_API_KEY or OPENROUTER_API_KEY (or use --dry-run)")

        jobs = []
        for i, frame in enumerate(frames):
            prev = frames[i - 1] if args.previous and i > 0 else None
            jobs.append((i, frame, times[i], prev))
        rows: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex, open(args.out, "w", encoding="utf-8") as out:
            for row in ex.map(lambda j: judge_frame(*j, model, spec, base, key, args.timeout), jobs):
                rows.append(row)
                out.write(json.dumps(row) + "\n")
                out.flush()
                if "error" in row:
                    print(f"t={row['t']:>7.2f}s  ERROR {row['error'][:160]}", file=sys.stderr)
                else:
                    print(f"t={row['t']:>7.2f}s  " + " | ".join(summarize({'answers': row['answers']})[1:]).replace("  ", " "), file=sys.stderr)

        events = events_from_rows(rows, spec.get("thresholds", {}), args.threshold)
        events_path = os.path.splitext(args.out)[0] + ".events.json"
        with open(events_path, "w", encoding="utf-8") as f:
            json.dump({"model": model, "fps": args.fps, "thresholds": spec.get("thresholds", {}),
                       "default_threshold": args.threshold, "events": events}, f, indent=2)
        errors = sum(1 for r in rows if "error" in r)
        tokens = sum((r.get("usage") or {}).get("input_tokens", 0) for r in rows)
        print(f"\nwrote {args.out} ({len(rows)} rows, {errors} errors, {tokens} input tokens) and {events_path}", file=sys.stderr)
        for qid, evs in events.items():
            spans = ", ".join(f"{e['start']:.0f}-{e['end']:.0f}s (max {e['max_noul']:.2f})" for e in evs)
            print(f"  {qid}: {spans}", file=sys.stderr)
    except JevError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    finally:
        if tmp and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
