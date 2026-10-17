# Jev / TypeSafe System One API reference (verified 17 Oct 2026)

Source of truth: https://docs.typesafe.ai/api.md , https://docs.typesafe.ai/models.md ,
https://docs.typesafe.ai/images.md , https://docs.typesafe.ai/primitives/box.md ,
https://docs.typesafe.ai/sdk/python.md , https://docs.typesafe.ai/sdk/javascript.md .
Re-read them before relying on a version-dependent detail.

## Endpoint and headers

- `POST https://api.typesafe.ai/v1/systemone`
- `Authorization: Bearer <TYPESAFE_API_KEY>`
- `Content-Type: application/json` (or `multipart/form-data` for image file parts)
- Optional `Content-Encoding: gzip | x-gzip | zstd` (one layer; zstd window <= 8 MiB)
- Experimental, opt-in per request:
  - `TypeSafe-Danger-Zone-Images: true` - required for any request with an image or a `box` question
  - `TypeSafe-Danger-Zone-Long-Context: true` - raises limits to 262k tokens (slower, less accurate)
- `GET /v1/models` lists the aliases the account can use. Versioned ids work even if unlisted.

## Models and aliases

| Model | Meaning (as of 15 Oct 2026) |
| --- | --- |
| `jev-1.14.0` | Newest release, available from 14 Oct 2026. Only model that answers `box`. |
| `jev-1.13.0` | Previous release. Still available; >= 60 days notice before deprecation. |
| `jev-latest` | Most recent stable; SDK default. Pointed to `jev-1.13.0`; moves to 1.14.0 about 21 Oct 2026. |
| `jev-preview` | Most recent release, stable or not. Points to `jev-1.14.0`. |

Pricing: $0.042 per million input tokens ($42 per billion); output tokens free; images
and long context billed at the same per-token rate (they add input tokens).
Latency: TypeSafe quotes 70-500 ms end to end, most near 100 ms from the US West Coast.
Input: text (string, object, array) and PNG/JPEG stills with the images header. No audio or video.
Language: English primary; other languages supported with lower accuracy (1.14 improves this).
Rate limits: per organisation, tokens and requests per second; see the developer console; `429` on excess.
Data: TypeSafe states it does not train on customer requests; zero data retention for enterprise.

## Request body

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `model` | string | yes | alias or versioned id |
| `state` | string, object or array | yes | what every question is judged against; reference nested fields in questions with backticks: `` `order.charges[0].amount` `` |
| `questions` | map<id, Question> | yes | ids are for your code and are not sent to the model: put the full meaning in `instructions` |
| `assets` | map<reference, Asset> | no | images; see Images below |

Every question has `type` and `instructions` (string, object or array). `criteria` is
required for `choice` and `score`, optional for `noul`, absent for `box`.

### noul (probability that a statement is true)

```json
{"type": "noul", "instructions": "Is the ticket about billing?",
 "criteria": {"true": "the customer asks about a charge, invoice or refund", "false": "anything else"}}
```
Answer: `{"type": "noul", "noul": 0.95}`. No `confidence` field. 0.5 means cannot tell.
For a confidence-style number use `|2p - 1|`.

### choice (one option from a closed set, max 255 options)

```json
{"type": "choice", "instructions": "What action is the user requesting?",
 "criteria": {"check_balance": "Check the balance of an account",
              "approve_transfer": "Approve the pending transfer request",
              "other": "Something else"}}
```
Answer: `{"type": "choice", "choice": "approve_transfer", "probabilities": {...sum to 1},
"confidence": 0.82}`. `confidence = (p_max - 1/n) / (1 - 1/n)`. Option descriptions may be
`null`, strings, objects or arrays. Option order can bias 1.13; reorder to check stability.

### score (position on 2-10 ordered, described levels)

```json
{"type": "score", "instructions": "How urgent is this ticket?",
 "criteria": ["can wait", "this week", "today"]}
```
Answer: `{"type": "score", "score": 1.4, "legend": {"0": "can wait", ...},
"probabilities": {"0": 0.1, "1": 0.4, "2": 0.5}, "confidence": 0.6}`.
`score` is the probability-weighted mean of level indexes; use it for ranking and
thresholds, never as a magnitude. Levels must describe concrete situations.

### box (experimental; where one target is in an image; needs `jev-1.14.0` or `jev-preview`)

```json
{"type": "box", "instructions": "the person nearest the crane in `frame`"}
```
Answer: `{"type": "box", "box": {"top": 0.25, "bottom": 0.82, "left": 0.44, "right": 0.84},
"confidence": 0.92}`. Edges are fractions from the top-left corner: `left`/`right` of width,
`top`/`bottom` of height. Pixels = fraction x width or height. A Box always returns a box,
even when the target is absent: pair it with a presence Noul and ignore the box when the
Noul is low. One target per Box question; describe the one you want. Crop first for small
targets; check edges with per-edge Nouls on the crop ("Does the X continue past the left edge?").

## Response body

```json
{"model": "jev-1.14.0", "answers": {"<id>": {...}}, "usage": {"input_tokens": 296, "output_tokens": 20}}
```

## Limits

- Default context: 64k tokens per request (state + all questions); 32k for state + any one question.
  No limit on the number of questions while both hold. Long-context header: 262k for both.
- Body: 32 MiB max (compressed and decompressed). UTF-8 JSON without BOM. Nesting <= 64 levels.
  Finite numbers only; send ids and exact large quantities as strings.
- Choice: max 255 options. Score: 2-10 levels.

## Errors

| Status | Meaning |
| --- | --- |
| 400 | malformed request; `max_tokens_exceeded`; image sent without the images header; image or asset rejected |
| 401 | missing or invalid key |
| 413 | body or image over a size limit |
| 415 | unsupported or doubled `Content-Encoding` |
| 422 | validation failure (names the field) |
| 429 | rate limit: retry with exponential backoff |
| 529 | overloaded: retry after a short delay |

The SDKs retry 429/529 automatically.

## Images (experimental)

Each image appears once in top-level `assets`, keyed by a reference string. Write the
reference anywhere in `state`, `instructions` or `criteria`; the API substitutes the image.

Asset fields: `type` (optional, must be `"image"`), `format` (`png` | `jpg` | `jpeg`, required
with `data_base64`), `data_base64` (standard base64, `=` padding, no whitespace, no `data:` prefix)
or `part` (name of a multipart file part). If both are set, `part` wins.

Reference rules: every asset must be referenced (else 400); references match as plain text,
whole values first, then left to right without overlap, so use a UUID per image per request;
each use adds another copy of the image's tokens; object keys (option names, question ids)
are not replaced; answers echo the reference text, not the image; a reference is <= 1,024
bytes, all references together <= 65,536 bytes.

Limits: PNG or JPEG still images (animated PNG rejected); 16 MiB per file; 280-1568 px per
side; 78,400-2,458,624 total pixels; 32 MiB request body; 32 MiB for all images after
processing; 32 MiB for the expanded request. Out-of-range images are rejected, never resized.
One bad image fails the whole request.

Prepare: rotate pixels upright (EXIF is stripped and not applied), longest side <= 1568,
baseline 8-bit JPEG quality ~90, export video frames as stills, convert GIF/WebP/HEIC.
Pillow: `ImageOps.exif_transpose(img).thumbnail((1568, 1568))` then `convert("RGB").save(..., "JPEG", quality=90)`.

Multipart (recommended; base64 adds a third to size): first part named `request` holds the
JSON (`application/json`); each image is its own file part whose name the asset's `part`
names; part content types `image/png`, `image/jpeg`, `image/jpg`, `application/octet-stream` or none.

```bash
curl https://api.typesafe.ai/v1/systemone \
  -H "Authorization: Bearer $TYPESAFE_API_KEY" \
  -H "TypeSafe-Danger-Zone-Images: true" \
  -F 'request={"model":"jev-preview","state":{"photo":"6e1d0b7c-kitchen"},
       "assets":{"6e1d0b7c-kitchen":{"type":"image","part":"kitchen-photo"}},
       "questions":{"mug_visible":{"type":"noul","instructions":"Is there a coffee mug in `photo`?"},
                    "mug":{"type":"box","instructions":"the coffee mug in `photo`"}}};type=application/json' \
  -F 'kitchen-photo=@kitchen.jpg;type=image/jpeg'
```

Image placement patterns: compare against a known picture (known picture in `instructions`,
photo in `state`); define Choice options by example pictures (`criteria`); "what changed"
(previous frame or short history in `state`); look closer only when needed (small copy
first, then crop); search a large image by tiles as Choice options; find where with Box.

## Python SDK (`typesafe-sdk` 0.7.5, 14 Oct 2026, Python >= 3.10)

```bash
pip install typesafe-sdk            # extras: [http2], [pil] (Pillow images), [zstd]
```

```python
from pathlib import Path
from typesafe_sdk import Box, Choice, Image, Noul, Score, TypeSafeClient, RetryPolicy

client = TypeSafeClient(
    model="jev-1.14.0",                         # or TYPESAFE_DEFAULT_MODEL; default jev-latest
    headers={"TypeSafe-Danger-Zone-Images": "true"},   # client-wide; or extra_headers per call
    timeout=10.0,                               # seconds per HTTP operation
    # api_key=..., base_url=... (TYPESAFE_API_KEY / TYPESAFE_BASE_URL), retry=RetryPolicy(...)
)
frame = Image(Path("frame_00042.jpg"))          # or Image(bytes), Image.from_base64(s), Image.from_pil(pil_img)

resp = client.system_one(
    state={"frame": frame, "site": "crane bay"},
    questions={
        "person_present": Noul(instructions="Is there a person in `frame`?"),
        "ppe": Choice(instructions="What head protection does the nearest person in `frame` wear?",
                      criteria={"helmet": "a hard hat", "none": "no head protection", "unclear": "cannot see the head"}),
        "risk": Score(instructions="How risky is the scene in `frame`?",
                      criteria=["routine", "worth a supervisor's look", "stop work now"]),
        "person": Box(instructions="the person nearest the camera in `frame`"),
    },
    model="jev-preview",                        # per-call override; Box needs 1.14
    extra_headers={"TypeSafe-Danger-Zone-Images": "true"},
    # assets={"<ref>": Image(...)} to choose your own reference strings
)
resp.nouls["person_present"].noul
resp.choices["ppe"].choice, resp.choices["ppe"].confidence, resp.choices["ppe"].probabilities
resp.scores["risk"].score, resp.scores["risk"].legend
resp.boxes["person"].box, resp.boxes["person"].confidence
resp.model, resp.usage.input_tokens
```

`AsyncTypeSafeClient` has the same surface with `await`. `with client.attach_assets(img):`
lets plain strings reference an image. `client.models.list()` lists aliases.
Errors: `typesafe_sdk` exceptions for API errors, rate limits, connection failures, timeouts.
Env: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL`, `TYPESAFE_LOG_LEVEL`.

## JavaScript / TypeScript SDK (`@typesafe-ai/sdk` 0.7.x, Node >= 22)

```bash
npm install @typesafe-ai/sdk
```

```ts
import { openAsBlob } from "node:fs";
import { box, choice, image, noul, score, TypeSafeClient, withAssets } from "@typesafe-ai/sdk";

const client = new TypeSafeClient({
  defaultModel: "jev-1.14.0",                       // or TYPESAFE_DEFAULT_MODEL; default jev-latest
  defaultHeaders: { "TypeSafe-Danger-Zone-Images": "true" },
  timeout: 10000,                                   // ms per attempt
  // apiKey, baseURL (TYPESAFE_API_KEY / TYPESAFE_BASE_URL), retry, compression: false
});
const frame = image(await openAsBlob("frame_00042.jpg"));   // or Image.fromBase64(text)

const { answers, model, usage } = await client.systemOne(
  {
    state: { frame, site: "crane bay" },
    questions: {
      personPresent: noul("Is there a person in `frame`?"),
      ppe: choice("What head protection does the nearest person in `frame` wear?",
                  { helmet: "a hard hat", none: "no head protection", unclear: "cannot see the head" }),
      risk: score("How risky is the scene in `frame`?", ["routine", "worth a supervisor's look", "stop work now"]),
      person: box(withAssets`the person nearest the camera in ${frame}`),
    },
    model: "jev-preview",
  },
  { headers: { "TypeSafe-Danger-Zone-Images": "true" }, timeout: 15000 },
);
answers.personPresent.noul; answers.ppe.choice; answers.ppe.confidence; answers.risk.score;
answers.person.box.top; // confidence may be null when the API does not report one
```

`withAssets` tagged templates embed images in text; an image in an untagged template throws
before sending. `assets: {"<ref>": image(...)}` lets plain strings reference images.
Requests with images go as `multipart/form-data`. Bodies >= 1 KiB are zstd-compressed on
Node >= 22.15. Never use the SDK in a browser (`dangerouslyAllowBrowser` exposes the key).

## Vercel AI SDK route

`npm install ai @ai-sdk/typesafe-ai`; `typeSafeAi.evaluationModel('jev-latest')` with
`experimental_evaluate`. The yes/no type is `boolean` with a `probability` field; confidence
arrives in `result.providerMetadata.typesafe.confidence` keyed by question id. Gateway model id `typesafe-ai/jev`.

## OpenRouter route (no TypeSafe account needed)

- Decisions API: `POST https://openrouter.ai/api/alpha/decisions` (alpha; may move).
- System One passthrough: `POST https://openrouter.ai/api/v1/systemone`; point the TypeSafe SDK
  at base URL `https://openrouter.ai/api` with an OpenRouter key.
- Model ids: `typesafe/jev-1.14` (current), `typesafe/jev-1.13`, `~typesafe/jev-latest`.
- Images: the Decisions API accepts `state` arrays mixing text and `{"type": "image_url",
  "image_url": {"url": "data:image/png;base64,..."}}`; Box needs jev-1.14 (1.13 returns 400).
  Every response includes `usage.cost`. Image support through the passthrough is unverified here.
- Any image request and any text request over ~32k bytes uses long-context mode on OpenRouter.

## jev-use library (Node, MIT)

`npm i jev-use`: `new Jev()` resolves the backend from `TYPESAFE_API_KEY`, `OPENROUTER_API_KEY`,
`AI_GATEWAY_API_KEY` or `JEV_BACKEND=mock`; `jev.judge(state, {id: check(...)|pick(...)|rate(...)})`
returns `{answers, verdicts}` where every verdict is `{answer, confidence, confidenceFrom,
escalate, reason?, hint?, distribution?, legend?}`; `jev.gate(state, {tool, input})` returns
`{decision: allow|deny|escalate}`; `route({producesContent, enumerable})` says whether a step
is Jev-shaped. See `references/agent-system.md`.
