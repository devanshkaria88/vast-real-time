"""Generate accident clips from the incident stills with Luma Ray2 on Amazon Bedrock.

Each claim's still, stamped with its OSD clock as in build_media.py, is the end
keyframe of a 5 s clip: Ray2 animates the lead-up and the impact and lands on
the evidence frame. Ray2 is only offered in us-west-2, only through the async
API (one job at a time per account), and writes its video to S3. The result is
stretched back to the still's 1168x784 frame and the OSD box is redrawn with a
clock that ticks up to the claim's incident time.

Output: poodle/media/luma/<claim>.mp4 and manifest.json. Raw Ray2 clips stay in
server/data/luma/ (gitignored) so --process-only can rebuild without paying
again. A 5 s 720p clip costs $7.50. Auth is the AWS default chain
(`aws sso login`); LUMA_S3_URI overrides the output location. Needs ffmpeg:

    uv run --with boto3 --with pillow python server/tools/luma_videos.py PD-0147 PD-0236
    uv run --with boto3 --with pillow python server/tools/luma_videos.py --process-only
"""

from __future__ import annotations

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
from PIL import Image

from build_media import CLIPS, SRC, frame

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "poodle" / "media" / "luma"
RAW = ROOT / "server" / "data" / "luma"
REGION = "us-west-2"
MODEL = "luma.ray-v2:0"
SIZE = (1168, 784)
# Ray2 has no 3:2 option, so the still is squashed to 4:3 for the request and the clip is stretched back.
REQUEST_SIZE = (1024, 768)
SETTINGS = {"aspect_ratio": "4:3", "resolution": "720p", "duration": "5s", "loop": False}
CAMERA = "Fixed elevated CCTV camera, static wide shot, no camera movement, realistic security camera footage."

PROMPTS = {
    "PD-0147": (
        "Suburban London crossroads with traffic lights, overcast daylight. A blue hatchback pulls out of the "
        "side road on the left into the junction. A red hatchback speeds down the main road from the distance, "
        "runs the red light and smashes into the front of the blue car in the middle of the junction. Bonnets "
        "crumple, glass and plastic debris scatter across the tarmac and both cars jolt to a stop nose to nose. "
        "A dark grey car behind brakes and stops."
    ),
    "PD-0188": (
        "Busy London dual carriageway, daylight, traffic flowing in both directions. A white hatchback cuts "
        "across from the outside lane right in front of a black SUV and brakes hard. The SUV cannot stop and "
        "hits the white car's rear corner, spinning it round across the lane line. Debris scatters across the "
        "lane while other cars brake and steer around."
    ),
    "PD-0204": (
        "Suburban roundabout seen from above, daylight. A white hatchback circulates around the roundabout "
        "from the right. A red hatchback approaches from the lower left entry, crosses the give-way line "
        "without stopping and pulls into the white car's path. The white car hits the front of the red car, "
        "plastic debris scatters across the carriageway and both cars stop."
    ),
    "PD-0211": (
        "Busy multi-lane London junction, morning daylight, traffic streaming down the lanes towards the "
        "camera. A blue hatchback drifts right across the lane markings while a silver hatchback swings left "
        "out of its lane beside the traffic island. Their front corners collide, debris sprays across the road "
        "and both cars stop. A white van slows in the next lane; a red double-decker bus waits at the stop."
    ),
    "PD-0219": (
        "London junction in heavy rain before sunrise, dim blue light, wet reflective road. A blue hatchback "
        "drives along the main road with its headlights on. A red hatchback pulls out of the side road on the "
        "right past the GIVE WAY sign without stopping, straight into its path. They collide front to front, "
        "spray and debris scatter across the wet tarmac and both cars stop."
    ),
    "PD-0226": (
        "Quiet London junction at night under street lights. A blue hatchback with its headlights on drives "
        "along the main road from the left. A red hatchback with its headlights on rolls out of the side road "
        "ahead, over the give-way line, into its path. A low-speed bump: the fronts touch, a few fragments drop "
        "onto the road and both cars stop."
    ),
    "PD-0231": (
        "Suburban London main road at a side turning, overcast daylight. A silver estate car slows and turns "
        "right across the road. A blue hatchback overtaking along the centre line at speed slams head-on into "
        "the front of the turning silver car. Both bonnets crumple, steam and debris burst out, and the two "
        "cars come to rest locked together."
    ),
    "PD-0236": (
        "Residential London junction with a zebra crossing, overcast daylight. A blue hatchback drives in from "
        "the left across the zebra crossing. A black saloon turns fast out of the side road on the right "
        "without slowing. The two cars collide front to front; bonnets crumple and a burst of glass and "
        "plastic debris explodes into the air above the crossing."
    ),
}


def keyframe(claim: str) -> str:
    cfg = CLIPS[claim]
    still = frame(Image.open(SRC / f"{cfg[0]}.jpg").convert("RGB"), cfg, 0)
    buf = io.BytesIO()
    still.resize(REQUEST_SIZE, Image.LANCZOS).save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def submit(bedrock, claim: str, s3_uri: str) -> str:
    body = {
        "prompt": f"{CAMERA} {PROMPTS[claim]}",
        **SETTINGS,
        "keyframes": {
            "frame1": {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": keyframe(claim)}},
        },
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


def process(claim: str) -> tuple[str, float]:
    raw = RAW / f"{claim}.mp4"
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=r_frame_rate,nb_read_packets", "-of", "json", str(raw)],
        capture_output=True, text=True, check=True,
    ).stdout)["streams"][0]
    rate, count = probe["r_frame_rate"], int(probe["nb_read_packets"])
    num, den = map(int, rate.split("/"))
    fps = num / den
    w, h = SIZE
    decode = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(raw), "-vf", f"scale={w}:{h}:flags=lanczos",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    encode = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
         "-framerate", rate, "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "26",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(OUT / f"{claim}.mp4")],
        stdin=subprocess.PIPE,
    )
    for i, buf in enumerate(iter(lambda: decode.stdout.read(w * h * 3), b"")):
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
    args = sys.argv[1:]
    process_only = "--process-only" in args
    claims = [a for a in args if a.startswith("PD-")]
    unknown = [c for c in claims if c not in PROMPTS]
    if unknown:
        print("no prompt for", ", ".join(unknown))
        return 2
    if process_only and not claims:
        claims = sorted(p.stem for p in RAW.glob("PD-*.mp4"))
    if not claims:
        print(__doc__)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    if not process_only:
        session = boto3.Session(region_name=REGION)
        bedrock, s3 = session.client("bedrock-runtime"), session.client("s3")
        account = session.client("sts").get_caller_identity()["Account"]
        s3_uri = os.environ.get("LUMA_S3_URI", f"s3://dk-bedrock-video-{account}-{REGION}/poodle").rstrip("/")
    for claim in claims:
        if not process_only:
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
                "settings": {**SETTINGS, "keyframe": "frame1"},
                "invocationArn": arn,
                "output": download(s3, job, claim),
                "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        starts, duration = process(claim)
        manifest.setdefault(claim, {}).update(startsAt=starts, duration=round(duration, 2))
        path.write_text(json.dumps(manifest, indent=1) + "\n")
        print(claim, "ok", f"{duration:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
