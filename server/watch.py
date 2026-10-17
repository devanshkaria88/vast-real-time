"""Background incident scanner: every live TfL JamCam, judged by Jev, kept as a library.

The app starts it when a Jev key is set (POODLE_WATCH=off turns it off):

- poll each camera's still with a conditional GET; S3 answers 304 until TfL publishes
  a new frame, which happens every 5 to 8 minutes per camera;
- send each new frame to Jev once, with every question below batched in one request;
- code turns the typed answers into incidents: opened by one flagged frame, confirmed
  by a second, cleared after two quiet frames or 30 minutes without a frame.

Runtime data lives in data/library/ (gitignored) and is served at /library/:
  observations-<date>.jsonl  one row per judged frame: the data mine
  incidents.json             the incident library
  frames/, clips/            incident stills and the camera's 10 s clips, with SHA-256
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import random
import time
import uuid
from collections import Counter, OrderedDict, deque
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from . import services, tfl

LIBRARY = Path(services.env("POODLE_LIBRARY_DIR") or Path(__file__).resolve().parent / "data" / "library")
USD_PER_TOKEN = 0.042 / 1_000_000

# ---------------------------------------------------------------- questions and thresholds
# One reviewable place for what Jev is asked about each frame and how code acts on it.
# Thresholds are starting points from a probe on crash stills and live frames; calibrate
# them on the review labels the desk collects.

QUESTIONS = {
    "usable": {
        "type": "noul", "instructions": "Can the road and the vehicles on it be seen in `frame`?",
        "criteria": {"true": "the carriageway is visible clearly enough to judge what is happening on it",
                     "false": "the frame is blank, grey, a 'camera unavailable' card, pointing at a wall or the sky, "
                              "too dark to see the road, or the lens is covered by rain, glare or dirt"}},
    "incident": {
        "type": "noul", "instructions": "Does `frame` show a road incident happening now?",
        "criteria": {"true": "a collision, a damaged, overturned or burning vehicle, a vehicle stopped across a live lane "
                             "or at an odd angle, emergency services working on the road, debris or a fallen object on "
                             "the carriageway, flooding, or a person lying in the road",
                     "false": "ordinary traffic, including queues, parked cars, buses at stops, vehicles waiting at lights, "
                              "roadworks behind barriers, and vehicles stopped at the kerb"}},
    "kind": {
        "type": "choice", "instructions": "What is the main thing happening on the road in `frame`?",
        "criteria": {
            "collision": "a crash: vehicles in contact, a damaged or overturned vehicle, or wreckage",
            "breakdown": "one vehicle stopped in a live lane with hazard lights, a raised bonnet or a tow truck",
            "emergency_response": "police, ambulance or fire vehicles stopped on the road at a scene",
            "obstruction": "debris, a fallen tree, a spilled load or another object blocking the carriageway",
            "flooding": "standing water covering part of the carriageway",
            "fire_or_smoke": "flames or smoke from a vehicle or the roadside",
            "person_in_road": "a person lying, standing or walking in a live traffic lane away from a crossing",
            "roadworks": "planned works: cones, barriers, works vehicles or a lane closed for maintenance",
            "congestion": "slow or stationary queues with no visible cause",
            "normal": "traffic moving normally, or an empty road",
            "unclear": "the frame is too dark, blurred, obstructed or blank to tell",
            "other": "something else unusual on the road"}},
    "severity": {
        "type": "score", "instructions": "How urgently should a traffic control room operator look at `frame`?",
        "criteria": ["nothing to act on: normal traffic",
                     "worth noting: a stopped vehicle, a queue or works that is not blocking traffic",
                     "act now: a lane is blocked by a collision, breakdown, obstruction or emergency scene",
                     "major: a serious crash, a fire, an overturned vehicle, people hurt, or the road is closed"]},
    "emergency_vehicle": {"type": "noul", "instructions": "Is a police car, ambulance or fire engine visible in `frame`?"},
    "damaged_vehicle": {
        "type": "noul",
        "instructions": "Is a vehicle in `frame` visibly damaged, overturned, on fire, or facing against the flow of traffic?"},
    "lane_blocked": {
        "type": "noul",
        "instructions": "Is a traffic lane in `frame` blocked by a stopped vehicle, debris, people or emergency services, "
                        "so that traffic has to go around it?",
        "criteria": {"true": "a lane is obstructed by something that is not part of normal traffic",
                     "false": "vehicles waiting at lights or in a queue, parked in bays, or at a bus stop; or no lane is blocked"}},
    "people_in_road": {
        "type": "noul", "instructions": "Are people standing or walking in a traffic lane in `frame`, away from a pedestrian crossing?"},
    "traffic": {
        "type": "score", "instructions": "How much traffic is on the road in `frame`?",
        "criteria": ["empty road", "light traffic with large gaps", "busy, vehicles close together",
                     "nose-to-tail queue filling the lanes"]},
    "surface": {
        "type": "choice", "instructions": "What is the condition of the road surface in `frame`?",
        "criteria": {"dry": "dry road", "wet": "wet road, puddles or reflections on the surface",
                     "snow_or_ice": "snow or ice on the road", "unclear": "cannot see the surface"}},
    "light": {
        "type": "choice", "instructions": "What is the lighting in `frame`?",
        "criteria": {"daylight": "daylight", "dusk": "dusk or dawn", "night_lit": "night with street lights",
                     "dark": "night without useful light"}},
    "where": {"type": "box",
              "instructions": "the collision, damaged vehicle, stopped vehicle, obstruction or emergency scene in `frame`"},
}

THRESHOLDS = {
    "usable": 0.5,  # below: the view cannot be judged, so the frame neither extends nor clears an incident
    "open": 0.7,    # `incident` needed to open an incident, or to count towards confirming one
    "keep": 0.5,    # `incident` that keeps an open incident alive
    "box": 0.3,     # weakest box confidence worth drawing
}
INCIDENT_KINDS = {"collision", "breakdown", "emergency_response", "obstruction", "flooding", "fire_or_smoke",
                  "person_in_road", "other"}
CONFIRM_FRAMES = 2       # flagged frames that confirm an incident
CLEAR_FRAMES = 2         # quiet frames in a row that clear it
STALE_SECONDS = 30 * 60  # an open incident with no frame for this long is cleared
MAX_FRAMES = 12          # stills kept per incident
MAX_CLIPS = 3            # 10 s clips kept per incident
POLL_IDLE = 60           # seconds between checks while a camera's still is unchanged
POLL_AFTER_NEW = 210     # TfL refreshes each camera every 5 to 8 minutes
FETCH_CONCURRENCY = 12
CENTRE = (51.5073, -0.1276)  # Charing Cross: POODLE_WATCH_LIMIT keeps the cameras nearest to it


def flagged(o: dict) -> bool:
    return o["usable"] >= THRESHOLDS["usable"] and o["incident"] >= THRESHOLDS["open"] and o["kind"] in INCIDENT_KINDS


def compact(a: dict) -> dict:
    """The typed answers for one frame, flattened into an observation row."""
    r = lambda x: round(float(x), 3)  # noqa: E731
    return {
        "usable": r(a["usable"]["noul"]), "incident": r(a["incident"]["noul"]),
        "kind": a["kind"]["choice"], "kindConf": r(a["kind"]["confidence"]),
        "severity": r(a["severity"]["score"]),
        "emergency": r(a["emergency_vehicle"]["noul"]), "damaged": r(a["damaged_vehicle"]["noul"]),
        "blocked": r(a["lane_blocked"]["noul"]), "people": r(a["people_in_road"]["noul"]),
        "traffic": r(a["traffic"]["score"]), "surface": a["surface"]["choice"], "light": a["light"]["choice"],
    }


# ---------------------------------------------------------------- helpers

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def http_time(value: str | None) -> str | None:
    try:
        return parsedate_to_datetime(value).astimezone().isoformat(timespec="seconds") if value else None
    except (TypeError, ValueError):
        return None


def age_s(iso: str | None) -> float:
    return time.time() - datetime.fromisoformat(iso).timestamp() if iso else 0.0


def image_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 <= len(data):
        if data[i] != 0xFF:
            return None
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


def jev_format(data: bytes) -> str | None:
    """'jpg' or 'png' when Jev accepts the still as sent (it rejects, never resizes, out-of-range images)."""
    size = image_size(data)
    if not size:
        return None
    w, h = size
    if not (280 <= w <= 1568 and 280 <= h <= 1568 and 78_400 <= w * h <= 2_458_624):
        return None
    return "png" if data[:4] == b"\x89PNG" else "jpg"


# ---------------------------------------------------------------- library on disk

class Library:
    def __init__(self, root: Path):
        self.root = root
        self.frames = root / "frames"
        self.clips = root / "clips"
        self.frames.mkdir(parents=True, exist_ok=True)
        self.clips.mkdir(parents=True, exist_ok=True)
        self.file = root / "incidents.json"
        self.incidents: dict[str, dict] = json.loads(self.file.read_text()) if self.file.exists() else {}
        self.version = 0
        if not self.file.exists():
            self.save()

    def save(self) -> None:
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.incidents, indent=1))
        tmp.replace(self.file)
        self.version += 1

    def new_id(self) -> str:
        prefix = f"INC-{datetime.now():%y%m%d}-"
        return f"{prefix}{1 + sum(k.startswith(prefix) for k in self.incidents):03d}"

    def observations(self, day: date) -> Path:
        return self.root / f"observations-{day.isoformat()}.jsonl"

    def observe(self, row: dict) -> None:
        with self.observations(date.today()).open("a") as f:
            f.write(json.dumps(row) + "\n")

    def usage(self, day: date) -> tuple[int, int]:
        """(frames judged, input tokens) on `day`, read back from its observation file."""
        path = self.observations(day)
        frames = tokens = 0
        if path.exists():
            with path.open() as f:
                for line in f:
                    try:
                        tokens += int(json.loads(line).get("tok") or 0)
                        frames += 1
                    except (ValueError, AttributeError):
                        continue
        return frames, tokens


# ---------------------------------------------------------------- scanner

class Watcher:
    def __init__(self, root: Path = LIBRARY):
        self.library = Library(root)
        self.settings = root / "watch.json"
        self.paused = bool(json.loads(self.settings.read_text()).get("paused")) if self.settings.exists() else False
        self.http: httpx.AsyncClient | None = None
        self.queue: asyncio.Queue | None = None
        self.tasks: list[asyncio.Task] = []
        self.background: set[asyncio.Task] = set()
        self.cams: dict[str, dict] = {}       # camera id -> poll and tracking state
        self.shas: dict[str, set[str]] = {}   # sha -> cameras showing that exact still (shared placeholder cards)
        self.recent: deque[dict] = deque(maxlen=48)
        self.shown: OrderedDict[str, bytes] = OrderedDict()  # frames a status response advertised, kept until the desk loads them
        self.judged_at: deque[float] = deque(maxlen=5000)
        self.counts: Counter = Counter()
        self.errors = 0
        self.backoff_until = 0.0
        self.last_error: dict | None = None
        self.started_at: str | None = None
        self.watching = 0
        self.day = date.today()
        self.day_frames, self.day_tokens = self.library.usage(self.day)
        self.cam_file = root / "cams.json"  # last judged still per camera, so a restart skips unchanged frames
        if self.cam_file.exists():
            for cam_id, saved in json.loads(self.cam_file.read_text()).items():
                st = self._cam(cam_id)
                st["etag"], st["sha"] = saved.get("etag"), saved.get("sha")
                if st["sha"]:
                    self.shas.setdefault(st["sha"], set()).add(cam_id)
        for inc in self.library.incidents.values():
            if inc["status"] == "open":
                self._cam(inc["cam"]["id"])["open"] = inc["id"]
        self._close_stale()

    # ------------------------------------------------------------ lifecycle

    def enabled(self) -> tuple[bool, str | None]:
        if (services.env("POODLE_WATCH") or "on").lower() in ("0", "off", "false", "no"):
            return False, "Turned off with POODLE_WATCH=off."
        if not services.jev_target():
            return False, "Needs a Jev key: set TYPESAFE_API_KEY or OPENROUTER_API_KEY in .env, then restart."
        return True, None

    def start(self, http: httpx.AsyncClient) -> None:
        if self.tasks or not self.enabled()[0]:
            return
        self.http = http
        self.queue = asyncio.Queue(maxsize=48)
        self.started_at = now_iso()
        workers = int(services.env("POODLE_WATCH_CONCURRENCY") or 6)
        self.tasks = [asyncio.create_task(self._scheduler())]
        self.tasks += [asyncio.create_task(self._judge_worker()) for _ in range(workers)]
        print(f"watch: scanning TfL cameras with {workers} Jev workers")

    async def stop(self) -> None:
        for t in [*self.tasks, *self.background]:
            t.cancel()
        await asyncio.gather(*self.tasks, *self.background, return_exceptions=True)
        self.tasks = []
        self.cam_file.write_text(json.dumps({i: {"etag": s["etag"], "sha": s["sha"]} for i, s in self.cams.items()
                                             if s["etag"] and not s["inflight"]}))

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        self.backoff_until = 0.0
        self.settings.write_text(json.dumps({"paused": paused}))

    def budget(self) -> float:
        try:
            return float(services.env("POODLE_WATCH_DAILY_USD") or 0)
        except ValueError:
            return 0.0

    def cost_today(self) -> float:
        return self.day_tokens * USD_PER_TOKEN

    def _blocked(self) -> str | None:
        if self.paused:
            return "paused"
        if self.budget() and self.cost_today() >= self.budget():
            return "budget"
        if time.time() < self.backoff_until:
            return "backoff"
        return None

    def _roll_day(self) -> None:
        if date.today() != self.day:
            self.day, self.day_frames, self.day_tokens = date.today(), 0, 0

    # ------------------------------------------------------------ polling

    def _cam(self, cam_id: str) -> dict:
        return self.cams.setdefault(cam_id, {"etag": None, "sha": None, "next": 0.0, "inflight": False,
                                             "open": None, "quiet": 0})

    @staticmethod
    def _later(seconds: float) -> float:
        return time.time() + seconds + random.uniform(-0.15, 0.15) * seconds

    def _select(self, cams: list[dict]) -> list[dict]:
        live = [c for c in cams if c["available"]]
        limit = int(services.env("POODLE_WATCH_LIMIT") or 0)
        if limit:
            live = sorted(live, key=lambda c: tfl.distance_m(*CENTRE, c["lat"], c["lon"]))[:limit]
        return live

    async def _scheduler(self) -> None:
        sem = asyncio.Semaphore(FETCH_CONCURRENCY)
        while True:
            try:
                self._roll_day()
                self._close_stale()
                if not self._blocked():
                    cams = self._select(await tfl.cameras(self.http))
                    self.watching = len(cams)
                    now = time.time()
                    due = [c for c in cams if not self._cam(c["id"])["inflight"] and self._cam(c["id"])["next"] <= now]
                    await asyncio.gather(*(self._poll(c, sem) for c in due))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = {"at": now_iso(), "text": f"Scheduler: {exc}"[:200]}
            await asyncio.sleep(3)

    def _own(self, cam_id: str, st: dict, sha: str) -> None:
        old = self.shas.get(st["sha"])
        if old is not None:
            old.discard(cam_id)
            if not old:
                del self.shas[st["sha"]]
        self.shas.setdefault(sha, set()).add(cam_id)
        st["sha"] = sha

    async def _poll(self, cam: dict, sem: asyncio.Semaphore) -> None:
        st = self._cam(cam["id"])
        async with sem:
            try:
                r = await self.http.get(cam["image"], headers={"If-None-Match": st["etag"]} if st["etag"] else None,
                                        timeout=15)
            except httpx.HTTPError:
                self.counts["fetchErrors"] += 1
                st["next"] = self._later(POLL_IDLE * 2)
                return
        self.counts["polls"] += 1
        if r.status_code != 200:
            st["next"] = self._later(POLL_IDLE if r.status_code == 304 else POLL_IDLE * 2)
            return
        st["etag"] = r.headers.get("etag")
        st["next"] = self._later(POLL_AFTER_NEW)
        frame = r.content
        sha = hashlib.sha256(frame).hexdigest()
        if sha == st["sha"]:
            self.counts["unchanged"] += 1
            return
        self._own(cam["id"], st, sha)
        fmt = jev_format(frame)
        if len(self.shas[sha]) > 1 or not fmt:
            self.counts["skipped"] += 1
            return
        self.counts["newFrames"] += 1
        st["inflight"] = True
        await self.queue.put((cam, frame, sha, fmt, r.headers.get("last-modified")))

    # ------------------------------------------------------------ judging

    async def _judge(self, frame: bytes, fmt: str) -> dict:
        base, key, model = services.jev_target()
        box_ok = "1.14" in model or "preview" in model
        questions = {k: q for k, q in QUESTIONS.items() if box_ok or q["type"] != "box"}
        ref = f"frame-{uuid.uuid4()}"
        body = {"model": model, "state": {"frame": ref}, "questions": questions,
                "assets": {ref: {"type": "image", "format": fmt, "data_base64": base64.b64encode(frame).decode()}}}
        started = time.perf_counter()
        r = await self.http.post(f"{base.rstrip('/')}/v1/systemone", json=body, timeout=30,
                                 headers={"Authorization": f"Bearer {key}", "TypeSafe-Danger-Zone-Images": "true"})
        r.raise_for_status()
        out = r.json()
        out["ms"] = round((time.perf_counter() - started) * 1000)
        return out

    async def _judge_worker(self) -> None:
        while True:
            cam, frame, sha, fmt, modified = await self.queue.get()
            st = self._cam(cam["id"])
            try:
                while self._blocked():
                    await asyncio.sleep(5)
                resp = await self._judge(frame, fmt)
                self.errors = 0
                self._record(cam, frame, sha, modified, resp)
            except asyncio.CancelledError:
                st["sha"] = st["etag"] = None  # never judged: fetch it again after a restart
                raise
            except Exception as exc:
                self._failed(exc)
                st["sha"] = st["etag"] = None  # fetch and judge this camera again on its next poll
                st["next"] = self._later(POLL_IDLE)
            finally:
                st["inflight"] = False
                self.queue.task_done()

    def _failed(self, exc: Exception) -> None:
        self.errors += 1
        self.counts["jevErrors"] += 1
        code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        text = f"Jev HTTP {code}: {exc.response.text[:160]}" if code else f"{type(exc).__name__}: {exc}"[:200]
        self.last_error = {"at": now_iso(), "text": text}
        if code in (429, 529) or self.errors >= 3:
            self.backoff_until = time.time() + min(300, 5 * 2 ** min(self.errors, 6))
        print("watch:", text)

    def _record(self, cam: dict, frame: bytes, sha: str, modified: str | None, resp: dict) -> None:
        self._roll_day()
        a = resp["answers"]
        o = compact(a)
        tokens = int((resp.get("usage") or {}).get("input_tokens") or 0)
        self.day_frames += 1
        self.day_tokens += tokens
        self.counts["judged"] += 1
        self.judged_at.append(time.time())
        judged = now_iso()
        taken = http_time(modified) or judged
        inc_id = self._track(cam, frame, sha, taken, judged, o, a, resp.get("model"))
        self.library.observe({"at": judged, "cam": cam["id"], "name": cam["name"], "sha": sha[:16], "taken": taken,
                              "model": resp.get("model"), "tok": tokens, "ms": resp.get("ms"), **o, "inc": inc_id})
        self.recent.appendleft({"cam": cam["id"], "name": cam["name"], "at": judged, "taken": taken, "sha": sha[:16],
                                "usable": o["usable"], "incident": o["incident"], "kind": o["kind"],
                                "severity": o["severity"], "inc": inc_id, "frame": frame})

    # ------------------------------------------------------------ incidents

    def _track(self, cam: dict, frame: bytes, sha: str, taken: str, judged: str, o: dict, a: dict,
               model: str | None) -> str | None:
        st = self._cam(cam["id"])
        inc = self.library.incidents.get(st["open"] or "")
        if inc is not None and inc["status"] != "open":
            inc = None
        hit = flagged(o)
        entry = {"takenAt": taken, "judgedAt": judged, "sha256": sha, **o,
                 "kinds": dict(sorted(a["kind"]["probabilities"].items(), key=lambda kv: -kv[1])[:4])}
        if "where" in a:
            entry["box"], entry["boxConf"] = a["where"]["box"], a["where"].get("confidence")
        if inc is None:
            if not hit:
                return None
            inc = self._open(cam, model)
            st["open"], st["quiet"] = inc["id"], 0
            self._extend(inc, entry, frame, hit)
            self._spawn(self._save_clip(inc, cam))
            self._event("incident_opened", inc)
            self.library.save()
            return inc["id"]
        if o["usable"] < THRESHOLDS["usable"]:
            return None
        if o["incident"] >= THRESHOLDS["keep"]:
            st["quiet"] = 0
            was_confirmed = inc["confirmed"]
            self._extend(inc, entry, frame, hit)
            if inc["confirmed"] and not was_confirmed:
                self._spawn(self._save_clip(inc, cam))
                self._event("incident_confirmed", inc)
            self.library.save()
            return inc["id"]
        st["quiet"] += 1
        if st["quiet"] >= CLEAR_FRAMES:
            self._store(entry, frame, f"{inc['id']}-after.jpg")
            inc["after"] = entry
            st["open"] = None
            self._close(inc, "Two quiet frames in a row", taken)
        return None

    def _open(self, cam: dict, model: str | None) -> dict:
        inc = {"id": self.library.new_id(), "status": "open", "confirmed": False,
               "cam": {k: cam.get(k) for k in ("id", "name", "view", "lat", "lon", "image", "video")},
               "openedAt": None, "confirmedAt": None, "lastSeenAt": None, "clearedAt": None, "clearReason": None,
               "kind": None, "kindConf": None, "peak": 0.0, "peakFrame": 0, "severity": 0.0, "conditions": {},
               "seen": 0, "flagged": 0, "frames": [], "after": None, "clips": [], "review": None, "model": model}
        self.library.incidents[inc["id"]] = inc
        return inc

    def _store(self, entry: dict, frame: bytes, name: str) -> None:
        (self.library.frames / name).write_bytes(frame)
        entry["file"] = name

    def _extend(self, inc: dict, entry: dict, frame: bytes, hit: bool) -> None:
        inc["seen"] += 1
        inc["flagged"] += int(hit)
        stored = len(inc["frames"]) < MAX_FRAMES
        if stored:
            self._store(entry, frame, f"{inc['id']}-{len(inc['frames']) + 1:02d}.jpg")
            inc["frames"].append(entry)
        inc["openedAt"] = inc["openedAt"] or entry["takenAt"]
        inc["lastSeenAt"] = entry["takenAt"]
        if entry["incident"] > inc["peak"] or inc["kind"] is None:
            inc["peak"], inc["kind"], inc["kindConf"] = entry["incident"], entry["kind"], entry["kindConf"]
            if stored:
                inc["peakFrame"] = len(inc["frames"]) - 1
        inc["severity"] = max(inc["severity"], entry["severity"])
        inc["conditions"] = {k: entry[k] for k in ("surface", "light", "traffic")}
        if not inc["confirmed"] and inc["flagged"] >= CONFIRM_FRAMES:
            inc["confirmed"], inc["confirmedAt"] = True, entry["takenAt"]

    def _close(self, inc: dict, reason: str, at: str | None) -> None:
        inc["status"], inc["clearedAt"], inc["clearReason"] = "cleared", at or now_iso(), reason
        self._event("incident_cleared", inc)
        self.library.save()

    def _close_stale(self) -> None:
        for inc in self.library.incidents.values():
            if inc["status"] == "open" and age_s(inc["lastSeenAt"]) > STALE_SECONDS:
                self._cam(inc["cam"]["id"])["open"] = None
                self._close(inc, "No new frame for 30 minutes", inc["lastSeenAt"])

    async def _save_clip(self, inc: dict, cam: dict) -> None:
        if not cam.get("video") or len(inc["clips"]) >= MAX_CLIPS:
            return
        try:
            r = await self.http.get(cam["video"], timeout=30)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"watch: clip for {inc['id']} failed:", exc)
            return
        sha = hashlib.sha256(r.content).hexdigest()
        if any(c["sha256"] == sha for c in inc["clips"]):
            return
        name = f"{inc['id']}-{len(inc['clips']) + 1}.mp4"
        (self.library.clips / name).write_bytes(r.content)
        inc["clips"].append({"file": name, "sha256": sha, "bytes": len(r.content),
                             "takenAt": http_time(r.headers.get("last-modified")), "savedAt": now_iso()})
        self.library.save()

    def _spawn(self, coro) -> None:
        if self.http is None:  # not running (tests): nothing to fetch with
            coro.close()
            return
        task = asyncio.create_task(coro)
        self.background.add(task)
        task.add_done_callback(self.background.discard)

    def _event(self, kind: str, inc: dict) -> None:
        event = {"kind": kind, "incident": inc["id"], "cam": inc["cam"]["id"], "camName": inc["cam"]["name"],
                 "incidentKind": inc["kind"], "peak": inc["peak"], "severity": inc["severity"]}
        if self.http is None:
            services.record_event(event)
        else:
            self._spawn(asyncio.to_thread(services.record_event, event))

    # ------------------------------------------------------------ API views

    def review(self, inc_id: str, label: str | None, by: str) -> dict | None:
        inc = self.library.incidents.get(inc_id)
        if inc is None:
            return None
        inc["review"] = {"label": label, "by": by, "at": now_iso()} if label else None
        self._event("incident_reviewed", inc)
        self.library.save()
        return inc

    @staticmethod
    def summary(inc: dict) -> dict:
        thumb = inc["frames"][inc["peakFrame"]]["file"] if inc["frames"] else None
        keys = ("id", "status", "confirmed", "kind", "kindConf", "peak", "severity", "openedAt", "lastSeenAt",
                "clearedAt", "seen", "review", "conditions")
        return {**{k: inc.get(k) for k in keys}, "thumb": thumb, "frames": len(inc["frames"]), "clips": len(inc["clips"]),
                "cam": {k: inc["cam"].get(k) for k in ("id", "name", "view", "lat", "lon")}}

    def incidents(self) -> dict:
        items = sorted(self.library.incidents.values(), key=lambda i: i["openedAt"] or "", reverse=True)
        return {"items": [self.summary(i) for i in items], "version": self.library.version}

    def recent_frame(self, sha: str) -> bytes | None:
        return self.shown.get(sha) or next((r["frame"] for r in self.recent if r["sha"] == sha), None)

    @staticmethod
    def rules() -> dict:
        return {"thresholds": THRESHOLDS, "kinds": sorted(INCIDENT_KINDS), "confirmFrames": CONFIRM_FRAMES,
                "clearFrames": CLEAR_FRAMES, "staleMinutes": STALE_SECONDS // 60}

    def status(self) -> dict:
        ok, reason = self.enabled()
        blocked = self._blocked() if ok else None
        state = "off" if not ok else blocked or ("scanning" if self.tasks else "starting")
        if blocked == "paused":
            reason = "Paused from the desk."
        elif blocked == "budget":
            reason = f"Daily budget of ${self.budget():.2f} reached. Scanning resumes tomorrow."
        elif blocked == "backoff":
            reason = f"Jev is not answering. Retrying in {round(self.backoff_until - time.time())} s."
        now = time.time()
        incs = self.library.incidents.values()
        target = services.jev_target()
        latest = list(self.recent)[:8]
        for r in latest:
            self.shown[r["sha"]] = r["frame"]
            self.shown.move_to_end(r["sha"])
        while len(self.shown) > 64:
            self.shown.popitem(last=False)
        return {
            "state": state, "reason": reason, "model": target[2] if target else None,
            "startedAt": self.started_at, "watching": self.watching,
            "perMinute": round(sum(1 for t in self.judged_at if now - t < 300) / 5, 1),
            "judgedToday": self.day_frames, "tokensToday": self.day_tokens, "costToday": round(self.cost_today(), 4),
            "budget": self.budget() or None, "counts": dict(self.counts), "queue": self.queue.qsize() if self.queue else 0,
            "open": sum(i["status"] == "open" for i in incs), "incidents": len(self.library.incidents),
            "confirmed": sum(bool(i["confirmed"]) for i in incs), "version": self.library.version,
            "lastError": self.last_error, "rules": self.rules(),
            "recent": [{k: v for k, v in r.items() if k != "frame"} for r in latest],
        }


watcher = Watcher()
