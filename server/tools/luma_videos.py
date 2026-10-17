"""Generate CCTV accident clips from the incident stills with Luma Ray2 on Amazon Bedrock.

A CCTV camera never moves, so both ends of each 5 s clip are pinned to the
still's framing. The start keyframe is the claim's still with the crashed cars
and their debris erased (Stability Erase Object, masked from the YOLO boxes of
the claim's vehicles); the end keyframe is the still itself, stamped with its
OSD clock as in build_media.py. Ray2 only has to drive the cars in and crash
them. The clip is stretched back to the still's 1168x784 frame, dropped to
15 fps with sensor grain, and the OSD box is redrawn with a clock that ticks up
to the claim's incident time.

Ray2 is only offered in us-west-2, only through the async API (one job at a
time per account), and writes its video to S3. A 5 s 720p clip costs $7.50, an
erased start frame $0.07. Auth is the AWS default chain (`aws sso login`);
LUMA_S3_URI overrides the output location. Needs ffmpeg.

Output: poodle/media/luma/<claim>.mp4 and manifest.json. Start frames and raw
Ray2 clips stay in server/data/luma/ (gitignored); delete a start frame to
erase it again. --plates-only builds the start frames to check before paying for
video; --process-only rebuilds the clips from the raw downloads; --trim cuts
seconds off the start where Ray2 pops a car into view (kept in the manifest).

    uv run --with boto3 --with pillow python server/tools/luma_videos.py --plates-only PD-0147
    uv run --with boto3 --with pillow python server/tools/luma_videos.py PD-0147 PD-0219
    uv run --with boto3 --with pillow python server/tools/luma_videos.py --process-only PD-0147 --trim 0.5
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw

from build_media import CLIPS, SRC, frame

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "server" / "data"
OUT = ROOT / "poodle" / "media" / "luma"
RAW = DATA / "luma"
REGION = "us-west-2"
MODEL = "luma.ray-v2:0"
ERASE = "us.stability.stable-image-erase-object-v1:0"
SIZE = (1168, 784)
# Ray2 has no 3:2 option, so the keyframes are squashed to 4:3 for the request and the clip is stretched back.
REQUEST_SIZE = (1024, 768)
SETTINGS = {"aspect_ratio": "4:3", "resolution": "720p", "duration": "5s", "loop": False}
CAMERA = (
    "Real CCTV traffic camera recording: grainy surveillance video from a fixed camera on a pole, locked-off "
    "static shot, the camera never moves, pans or zooms. Ordinary real-time traffic speed, no slow motion, no cuts."
)

# Ray2 does best with a plain sequence of events. Timing words ("for the first two seconds") and "drives in from
# the edge of the frame" made it spawn cars, debris and spray early in most takes.
PROMPTS = {
    "PD-0147": (
        "Overcast suburban London crossroads. The main-road traffic lights stay red the whole time and a dark grey "
        "car waits at them. A blue hatchback drives out of the side road on the left and crosses the junction on "
        "its green light. A red hatchback comes down the main road from the distance, goes past the waiting grey "
        "car, runs the red light and crashes into the front of the blue car in the middle of the junction. Glass "
        "and plastic scatter and both cars stop nose to nose."
    ),
    "PD-0188": (
        "Daylight on a busy London dual carriageway, steady traffic. A black SUV drives in the inside lane. A white "
        "hatchback in the outside lane suddenly swerves across in front of it without signalling and brakes hard "
        "for no reason. The SUV cannot stop and hits the white car's rear corner, spinning it round across the "
        "lane line. Other cars brake and steer around."
    ),
    "PD-0204": (
        "Daylight at a suburban roundabout. A white hatchback drives round the roundabout from the right. A red "
        "hatchback comes up to the entry at the lower left and, without giving way to traffic from the right, "
        "drives straight over the give-way line onto the roundabout and into the white car's path. The white car "
        "hits the red car's front corner, debris scatters and both cars stop."
    ),
    "PD-0211": (
        "Morning peak at a busy multi-lane London junction, traffic flowing down the lanes towards the camera. A "
        "blue hatchback drifts right across the lane markings without signalling as a silver hatchback swings left "
        "out of its lane beside the traffic island. Their front corners collide, debris sprays and both cars stop. "
        "A white van slows in the next lane; a red double-decker bus waits at the stop."
    ),
    "PD-0219": (
        "Heavy rain before sunrise at a London junction, dim light, wet reflective road. A blue hatchback with its "
        "headlights on drives along the main road. A red hatchback comes out of the side road on the right, "
        "ignores the GIVE WAY sign and pulls straight out without stopping, into the blue car's path. They collide "
        "front to front, spray and debris scatter on the wet road and both cars stop."
    ),
    "PD-0226": (
        "Night at a quiet London junction under street lights, dry road. A blue hatchback with its headlights on "
        "drives along the main road from the left. A red hatchback with its headlights on comes out of the side "
        "road at the top and rolls straight over the give-way lines without stopping, into the blue car's path. A "
        "low-speed bump: the fronts touch, a few fragments fall and both cars stop."
    ),
    "PD-0231": (
        "Overcast suburban London main road at a side turning. A silver estate car slows and turns right across "
        "the road. A blue hatchback overtakes along the centre line at speed and hits the turning silver car "
        "head-on. Both fronts crumple, steam and debris burst out and the two cars stop locked together."
    ),
    "PD-0236": (
        "Overcast residential London junction with a zebra crossing. A blue hatchback drives in from the left "
        "across the zebra crossing. A black saloon pulls fast out of the side road on the right over the give-way "
        "lines without stopping. The two cars collide front to front and a burst of glass and plastic debris flies "
        "into the air above the crossing."
    ),
}


def still(claim: str) -> Image.Image:
    cfg = CLIPS[claim]
    return frame(Image.open(SRC / f"{cfg[0]}.jpg").convert("RGB"), cfg, 0)


def b64(img: Image.Image, fmt: str = "JPEG") -> str:
    buf = io.BytesIO()
    img.save(buf, fmt, **({"quality": 92} if fmt == "JPEG" else {}))
    return base64.b64encode(buf.getvalue()).decode()


def keyframe(img: Image.Image) -> dict:
    data = b64(img.resize(REQUEST_SIZE, Image.LANCZOS))
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def crash_mask(claim: str) -> Image.Image:
    row = next(c for c in json.loads((DATA / "claims.json").read_text()) if c["id"] == claim)
    dets = json.loads((DATA / "detections.json").read_text())[CLIPS[claim][0]]["detections"]
    cars = [dets[i]["box"] for f in row["findings"] if f["kind"] == "vehicle" for i in f["det"]]
    x0, y0 = min(b[0] for b in cars), min(b[1] for b in cars)
    x1, y1 = max(b[0] + b[2] for b in cars), max(b[1] + b[3] for b in cars)
    bw, bh = x1 - x0, y1 - y0
    w, h = SIZE
    mask = Image.new("L", SIZE, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle(((x0 - 0.08 * bw) * w, (y0 - 0.06 * bh) * h, (x1 + 0.08 * bw) * w, (y1 + 0.1 * bh) * h), fill=255)
    # Debris, shadows and headlight pools spread out below the impact.
    draw.ellipse(((x0 - 0.3 * bw) * w, (y0 + 0.4 * bh) * h, (x1 + 0.4 * bw) * w, (y1 + 0.9 * bh) * h), fill=255)
    return mask


def clean_plate(bedrock, claim: str) -> Image.Image:
    path = RAW / f"{claim}-start.png"
    if not path.exists():
        body = {"image": b64(still(claim), "PNG"), "mask": b64(crash_mask(claim), "PNG"), "grow_mask": 15, "output_format": "png"}
        out = json.loads(bedrock.invoke_model(modelId=ERASE, body=json.dumps(body))["body"].read())
        if out["finish_reasons"][0]:
            raise RuntimeError(f"{claim}: erase refused: {out['finish_reasons'][0]}")
        path.write_bytes(base64.b64decode(out["images"][0]))
    return Image.open(path).convert("RGB")


def submit(bedrock, claim: str, s3_uri: str) -> str:
    body = {
        "prompt": f"{CAMERA} {PROMPTS[claim]}",
        **SETTINGS,
        "keyframes": {"frame0": keyframe(clean_plate(bedrock, claim)), "frame1": keyframe(still(claim))},
    }
    for _ in range(20):
        try:
            return bedrock.start_async_invoke(
                modelId=MODEL,
                modelInput=body,
                outputDataConfig={"s3OutputDataConfig": {"s3Uri": f"{s3_uri}/{claim}"}},
                tags=[{"key": "project", "value": "poodle"}, {"key": "claim", "value": claim}],
            )["invocationArn"]
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("ThrottlingException", "ServiceQuotaExceededException"):
                raise
            print(claim, "waiting for the running Ray2 job to finish")
            time.sleep(30)
    raise RuntimeError(f"{claim}: Ray2 stayed busy for 10 minutes")


def wait(bedrock, claim: str, arn: str) -> dict:
    started = time.monotonic()
    while True:
        job = bedrock.get_async_invoke(invocationArn=arn)
        if job["status"] != "InProgress":
            return job
        print(f"{claim} generating, {time.monotonic() - started:.0f}s")
        time.sleep(20)


def download(s3, job: dict, claim: str) -> str:
    uri = job["outputDataConfig"]["s3OutputDataConfig"]["s3Uri"]
    bucket, _, prefix = uri.removeprefix("s3://").partition("/")
    invocation = job["invocationArn"].rsplit("/", 1)[-1]
    listing = s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
    key = next((o["Key"] for o in listing if invocation in o["Key"] and o["Key"].endswith(".mp4")), None)
    if key is None:
        raise RuntimeError(f"{claim}: no video for {invocation} under {uri}")
    s3.download_file(bucket, key, str(RAW / f"{claim}.mp4"))
    return f"s3://{bucket}/{key}"


def process(claim: str, trim: float) -> tuple[str, float]:
    raw = RAW / f"{claim}.mp4"
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=r_frame_rate,nb_read_packets", "-of", "json", str(raw)],
        capture_output=True, text=True, check=True,
    ).stdout)["streams"][0]
    rate, count = probe["r_frame_rate"], int(probe["nb_read_packets"])
    num, den = map(int, rate.split("/"))
    fps = num / den
    skip = round(trim * fps)
    count -= skip
    w, h = SIZE
    decode = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(raw), "-vf", f"scale={w}:{h}:flags=lanczos",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    encode = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
         "-framerate", rate, "-i", "-", "-vf", "fps=15,noise=c0s=4:c0f=t", "-c:v", "libx264", "-preset", "slow",
         "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(OUT / f"{claim}.mp4")],
        stdin=subprocess.PIPE,
    )
    frames = iter(lambda: decode.stdout.read(w * h * 3), b"")
    for _ in range(skip):
        next(frames)
    for i, buf in enumerate(frames):
        # The still is the last frame, so the clock reads the incident time for the final second.
        offset = math.floor((i - count) / fps) + 1
        encode.stdin.write(frame(Image.frombytes("RGB", SIZE, buf), CLIPS[claim], offset).tobytes())
    encode.stdin.close()
    if decode.wait() or encode.wait():
        raise RuntimeError(f"{claim}: ffmpeg failed")
    incident = datetime.strptime(CLIPS[claim][-1], "%Y-%m-%d %H:%M:%S")
    starts = incident + timedelta(seconds=math.floor(-count / fps) + 1)
    return starts.isoformat(), count / fps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("claims", nargs="*", metavar="PD-XXXX")
    parser.add_argument("--plates-only", action="store_true", help="build the erased start frames and stop")
    parser.add_argument("--process-only", action="store_true", help="rebuild clips from the raw downloads")
    parser.add_argument("--trim", type=float, help="seconds to cut from the start, e.g. where a car pops in")
    args = parser.parse_args()
    unknown = [c for c in args.claims if c not in PROMPTS]
    if unknown:
        parser.error("no prompt for " + ", ".join(unknown))
    claims = args.claims or (sorted(p.stem for p in RAW.glob("PD-????.mp4")) if args.process_only else [])
    if not claims:
        parser.print_help()
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    if not args.process_only:
        session = boto3.Session(region_name=REGION)
        bedrock, s3 = session.client("bedrock-runtime"), session.client("s3")
    if args.plates_only:
        for claim in claims:
            clean_plate(bedrock, claim)
            print(claim, "start frame", (RAW / f"{claim}-start.png").relative_to(ROOT))
        return 0
    if not args.process_only:
        account = session.client("sts").get_caller_identity()["Account"]
        s3_uri = os.environ.get("LUMA_S3_URI", f"s3://dk-bedrock-video-{account}-{REGION}/poodle").rstrip("/")
    path = OUT / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    for claim in claims:
        if not args.process_only:
            arn = submit(bedrock, claim, s3_uri)
            print(claim, "submitted", arn)
            job = wait(bedrock, claim, arn)
            if job["status"] != "Completed":
                print(claim, "failed:", job.get("failureMessage", job["status"]))
                continue
            manifest[claim] = {
                "clip": f"media/luma/{claim}.mp4",
                "still": CLIPS[claim][0],
                "model": MODEL,
                "region": REGION,
                "prompt": f"{CAMERA} {PROMPTS[claim]}",
                "settings": {**SETTINGS, "frame0": "still with the crashed cars erased", "frame1": "still"},
                "invocationArn": arn,
                "output": download(s3, job, claim),
                "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        entry = manifest.setdefault(claim, {})
        if args.trim is not None:
            entry["trim"] = args.trim
        starts, duration = process(claim, entry.get("trim", 0))
        entry.update(startsAt=starts, duration=round(duration, 2))
        path.write_text(json.dumps(manifest, indent=1) + "\n")
        print(claim, "ok", f"{duration:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
