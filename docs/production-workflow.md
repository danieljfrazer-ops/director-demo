# Local film-production workflow

This workflow adapts the useful staged-production ideas in Higgsfield's MIT-licensed
`higgsfield-video-explainer` skill without depending on Higgsfield, Gemini, Seed Audio,
or any hosted generation service. The approved MVP is local-only and LTX-2.5 based.

The Higgsfield skill is a procedural reference, not an application backend. Its shared
style key, ordered block IDs, phase barriers, retry-by-block behavior, and immediate
assembly are useful. Its fixed ten-second blocks, cloud job IDs, parallel clip rendering,
non-photoreal restriction, and server-side assembly do not fit this product.

## Authority boundary

The planning LLM may create only the typed `ShotPlan`: creative intent, bibles, shot
breakdown, static anchor intent, motion, audio cues, and continuity facts. It never
chooses model files, memory policy, concurrency, output paths, or recovery behavior.

Deterministic Python compiles that plan into `ProductionManifest` schema version 1.0:

```text
script -> local structured LLM -> validated ShotPlan
       -> deterministic compiler -> ProductionManifest
       -> approved anchors -> one-slot LTX queue -> reviewed takes
       -> normalized timeline -> final film + provenance
```

The local M5/32 GB profile fixes:

- one heavy generation at a time;
- strict LTX-2.5 distilled BF16 with disk offload;
- 1024 x 576 at 24 fps for candidate local masters; lower rasters are explicit
  experiments, not silent draft defaults, because 448 x 256 failed facial review;
- one to five seconds per shot;
- LTX frame counts satisfying `8n + 1`, up to 121 frames;
- no automatic batch or parallel media generation.

For the first MVP, a 2–30 second apparent continuous take may be decomposed into several
2–5 second **render clips**. This is an engine implementation detail, not an editorial
shot boundary. The deterministic planner balances clip lengths, keeps authoritative
reference times where legal, chains approved boundary frames, and assembles to the exact
requested delivery duration. True multi-shot scene breakdown remains post-MVP. The
current resolution and duration defaults were promoted only after the measured hardware
ladder passed; they remain configurable and evidence-bound.

## Local planning model

Ollama and other OpenAI-compatible local servers use the same `ShotPlan` contract. The
compatible provider sends a strict JSON Schema response format, uses temperature zero,
and validates the response again with Pydantic. Invalid output never reaches rendering.

```bash
export DIRECTOR_LLM_PROVIDER=compatible
export DIRECTOR_LLM_BASE_URL=http://127.0.0.1:11434/v1
export DIRECTOR_LLM_API_KEY=local
export DIRECTOR_LLM_MODEL='<evaluated local model>'

director-demo shot-plan-schema > data/project/shot-plan.schema.json
director-demo plan data/project/script.txt --out data/project/shot-plan.json
director-demo compile-production data/project/shot-plan.json \
  --project-root data/project --out data/project/production.json
```

Do not install a planning model while the 66 GiB LTX download or video render is active.
Planning is light compared with video generation, but Ollama must unload its model before
LTX starts (`ollama stop <model>` or an API request with `keep_alive: 0`). A future app
worker will enforce this phase barrier and confirm memory has returned to baseline.

## LTX prompt compilation

The domain preserves static and motion prompts separately. The adapter provides three
deterministic ablations without asking another LLM to rewrite approved facts:

1. `motion_only` — current conservative I2V rule.
2. `style_locked` — motion plus the approved global visual style.
3. `context_locked` — motion plus the exact approved static anchor description.

No compiled prompt may exceed 200 words. The compiler refuses oversized prompts instead
of silently truncating dialogue or continuity. Cross-shot testing will decide which mode
becomes the default; it is not assumed in advance.

## State and recovery

Every shot follows guarded states:

```text
awaiting_anchor -> approved -> queued -> rendering -> rendered -> selected
                                              |             |
                                              v             +-> queued (new take)
                                            failed -> queued
```

Only one shot can be `rendering`. Processes emit append-only JSONL events and artifacts
are validated with `ffprobe`. On restart, the application reconciles the manifest,
events, process exit, input hashes, and output media before retrying; a timeout must not
silently create a duplicate job.

After rendering, the [editorial workflow](editorial-workflow.md) owns immutable take
registration, structured technical/creative review, approved selection, reversible edit
decisions, cut revisions, dependency freshness, normalized delivery, and provenance
snapshots. A rejected generator interval remains a source defect even when an approved
cut safely excludes it.

## Attribution

Workflow ideas were evaluated against Higgsfield AI's `higgsfield-video-explainer`
skill and prompt references, first released 16 July 2026 under the MIT License. No
Higgsfield source text or cloud integration is required at runtime. If substantial
licensed text is copied later, retain its copyright and MIT notice.
