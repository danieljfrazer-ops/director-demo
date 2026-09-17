# Architecture: evidence before infrastructure

## Status and executive decision

This is both a target design and a record of the working vertical slice. The repository
now has a typed director/shot-plan path, an unwired ComfyUI adapter, a simple FFmpeg
stitcher, a native LTX-2.5 renderer, durable run provenance, and a read-only local run
archive. Multiple image-conditioned takes and a three-clip film have rendered locally.
User review confirms that the measured 1024 x 576 profile materially improves facial
quality; the chained outro also proves that unapproved boundary defects and uncontrolled
motion propagate into a cut.

Keep Python, FFmpeg, typed project data, and LTX-2.5 Fast Distilled as the desired
video model. Make the **video runtime provisional**:

- The stock ComfyUI INT8-ConvRot route is rejected on the M5 because its required
  integer matrix operation is absent from MPS.
- The working primary local path is Lightricks' official LTX-2 Python pipeline using
  strict LTX-2.5 BF16 weights, fused MPS attention, and disk streaming. It remains
  evidence-bound and replaceable rather than permanent.
- The first MVP is local-only; there is no cloud LTX or planning fallback. A failed local
  capability blocks the relevant workflow and produces evidence for a later decision.
- ComfyUI remains a possible image adapter and future video adapter, not the domain
  model or an assumed production dependency.

The [red-team disposition](redteam-disposition.md) records the evidence and corrections.
LTX Desktop can run the selected LTX family locally on the target M5 through MPS
streaming. Treat Desktop as the provisional private generation/editor UI and this repository as a
comparison, provenance, and automation layer until actual use exposes a missing need.

## Public showcase boundary

The portfolio deployment is a separate, static read model—not the local execution
application. An explicit, versioned allowlist selects immutable completed outputs;
generic packaging verifies their source hashes, copies bytes without transcoding, and
emits privacy-filtered provenance for a static browser. The hosted interface never
claims to run LTX, approve creative work, or provide a production database.

Cloudflare Pages is the chosen initial delivery target because all selected files are
below its 25 MiB static-asset limit. The measured package does not justify R2, Workers,
Pages Functions, D1, or a browser-to-localhost bridge. Original runs and raw sidecars
remain ignored local evidence. See [publication.md](publication.md).

## Build the smallest truthful vertical slice

Before React, FastAPI, SQLite, or a general scheduler, build only:

```text
script -> typed shot plan -> approved anchor -> one video adapter
       -> validated take -> normalized FFmpeg output
                |
                +-> append-only JSONL events + hash-named artifacts
```

One CLI command should exercise one hand-pinned, manually proven engine configuration.
The project folder is the recovery boundary. Each event records input hashes, engine
and model revision, seed/parameters, status, artifact hash, and error. Re-running
skips a valid matching artifact and never silently reuses an output after an input
changes.

The typed [local production workflow](production-workflow.md) now separates creative
LLM output from deterministic M5 scheduling. `ProductionManifest` fixes the single heavy
job slot, disk offload, legal LTX frame geometry, conventional artifact paths, prompt
compilation mode, and guarded shot states. An agent skill may drive this contract later,
but Markdown instructions are never the durable source of production truth.

This vertical slice answers the real unknowns: whether the model runs, whether two
shots preserve identity, how long it takes, and whether the result is worth watching.

Every new slice also obeys [product and engineering governance](governance.md): it must
be reusable in the intended application or produce decision-quality evidence. Current
PoC media are immutable fixtures; film-specific repairs never enter generic code.

Every native render attempt writes an atomic, versioned `.run.json` sidecar before the
heavy process starts and updates that same attempt record on success or failure. The
private record owns exact direction/configuration, engine precision and quantization
state, revisions, input/output hashes, elapsed time, media probe, and human review.
Those sidecars remain local evidence; the public recorded showcase receives only the
explicitly allowlisted, privacy-filtered fields described in `publication.md`.

## Domain model

A flat list of five-second prompts is insufficient. Preserve these concepts in typed
JSON now, without prematurely normalizing them into database tables:

```text
Project
  Bibles (character, wardrobe, location, prop, style, voice)
  Scenes
    Shots
      continuity-in / continuity-out
      static image intent
      motion/camera intent
      structured dialogue and sound cues
      references and approvals
      Takes
        immutable input/provenance record
        generated Artifacts
```

Shot duration is an editorial choice constrained by the selected engine. Stable
appearance and setting belong to the image prompt/reference pack. For I2V, motion
text may name the actor and describe changing state, action, timing, camera, dialogue,
and sound, but must not repeat stable visual attributes.

## Continuity strategy

Do not chain every last frame. Select the least fragile control per edit:

- Canonical character/location reference packs and locked style metadata.
- Approved anchor boards for every hard cut.
- First/last keyframes or short overlap extension only for genuinely continuous action.
- Pose, depth, edge, or reference-video controls where the chosen engine supports them.
- A scored checklist for face/body identity, wardrobe, props, location, screen
  direction, lighting intent, and voice.

Stage 0.5 measures this before application infrastructure. Automated continuity
scoring can later assist reviewers; it does not replace a human creative gate.

The first measured last-frame chain confirms that boundary conditioning is effective
and that defects propagate through dependencies. Therefore a chained take depends on an
explicitly approved boundary-frame artifact, not merely an approved parent video. A
retake invalidates downstream chains by hash; it must never silently retain children
conditioned from an obsolete or rejected expression.

The local adapter now models uploaded stills as typed timeline references with a stable,
editable ID, immutable file/hash, strength, and global percentage. It deterministically
maps the percentage onto a clip and exact pixel-frame index, including first/last-frame
interpolation and interior keyframes. At an exact multi-clip boundary, the reference is
applied to the outgoing final frame; the decoded frame then becomes the next clip's
frame-zero continuation. This avoids two competing conditionings on one frame. IDs such
as `@start-frame` are application metadata compiled into prompt timing; visual control
comes from native repeated `--image PATH FRAME_IDX STRENGTH` conditioning, not from an
assumption that the model intrinsically resolves arbitrary IDs.

## Engine adapter contract

The domain layer supplies semantic inputs and expects immutable artifact/provenance
outputs. An adapter owns engine-specific prompt compilation, geometry constraints,
model hashes, progress, cancellation, teardown, and output discovery.

For any adapter to be considered operational it must pass:

1. A capability/preflight check against the exact installed runtime revision.
2. A live queue-to-file integration test using a pinned configuration.
3. Timeout, cancellation, process-exit, and restart/reconciliation tests.
4. Media validation with `ffprobe`, not merely a successful queue event.
5. Memory return-to-baseline measurement on the target Mac.

If ComfyUI is used, bind semantic fields through a versioned manifest rather than
hard-coded widget positions; pin ComfyUI/custom-node commits; validate `/object_info`;
upload assets explicitly; reconcile WebSocket events with `/history/{prompt_id}`;
and accept only loopback URLs by default. Because a separately launched ComfyUI owns
its models, the app cannot promise unload semantics unless it also supervises that
process or successfully calls and verifies its interrupt/free controls.

## Assembly is a timeline, not concat

The existing concatenator is adequate only for homogeneous PoC clips. Production
assembly must probe and normalize codec, dimensions, frame rate, timebase, pixel
format, and audio layout before placing media on an explicit timeline. Dialogue,
ambience, music, room tone, fades, captions, and loudness are separate tracks. The
final file and each delivered upscale receive their own QC and approval.

The first production-shaped timeline slice now exists as `EditorialProject`,
`CutManifest`, and `AssemblyRecord`. It keeps takes immutable, separates technical from
creative approval, requires an explicit edit for conditionally approved takes, verifies
take/boundary hashes, applies reversible second- or frame-addressed trims/fades and
declared cut/dissolve transitions, normalizes media, and snapshots the exact manifests
beside every delivery. Exact-boundary joins must retain the declared source frame
inclusively and either remove the child's duplicate first frame or declare an overlap;
the resolver rejects off-by-one joins. A dependency digest distinguishes media staleness
from review-only metadata changes. See [editorial workflow](editorial-workflow.md).

## Privacy, rights, and trust boundaries

The legacy OpenAI bootstrap provider sends the script to a third party. It is excluded
from the MVP and must stay clearly labelled if retained for historical CLI compatibility.
The MVP UI exposes only evaluated local adapters and must pass a network-disabled test
before it claims private/offline operation.

Every uploaded voice, likeness, image, video, sound effect, and music asset records
source, ownership/consent, allowed use, checksum, and deletion state. Generated media
records model/workflow licence and provenance. Secrets stay outside project exports
and move from `.env` to the OS keychain before multi-user distribution.

External render and model servers are untrusted unless explicitly configured. Local
engines bind to loopback, inputs and returned paths are validated, downloads are
streamed with limits, and arbitrary custom-node code is pinned and reviewed.

## Approved single-shot MVP architecture

The user has explicitly authorized the narrower single-shot MVP. Its immutable take
history, range retakes, approvals, dependency invalidation, restart recovery, and
queryable history now justify:

```text
React storyboard UI
        |
FastAPI project API + event stream
        |
Project service --- SQLite metadata / immutable artifact store
        |
Durable state machine --- one-slot resource governor --- supervised workers
        |
Director | Image | Video | Audio adapters -> timeline assembler -> QC/export
```

SQLite is adopted from observed JSONL query/recovery needs and the approved revision
graph, not an imagined enterprise schema. A normal browser UI comes before a desktop
shell. Tauri/Electron, signing, updates, telemetry, LoRA training, multiple scenes, and
cloud burst remain out of scope and require separate evidence and user demand.

Scene extension is assembly lineage, not in-place concatenation: the exact retained final
frame and continuity-out state of a selected assembly seed appended clip slots in a new
branch. Parent selection/edit changes stale descendants by dependency digest; recursive
extensions never rewrite their ancestors.

The normative product and implementation contracts are the
[MVP specification](mvp-single-shot-spec.md),
[technical design](mvp-single-shot-technical-design.md), and
[implementation plan](mvp-single-shot-implementation-plan.md). The
[MVP red-team disposition](mvp-single-shot-redteam-disposition.md) records the independent
product, M5 architecture, and integrity challenges and their resolution. Re-evaluate model/runtime
choices at every milestone because this ecosystem changes faster than the product layer.
