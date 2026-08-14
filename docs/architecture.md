# Architecture review and refined design

## Executive decision

Keep Python, FFmpeg, LTX-2.5 Fast Distilled, and optional ComfyUI integration—but
replace the linear script with a durable project model, a resumable state machine,
and pluggable generation adapters. On this Mac, validate LTX through its official
MPS-capable runtime before treating ComfyUI as the production LTX backend.

## Red-team findings

### 1. The memory assumption is necessary but insufficient

Sequential image then video loops avoid simultaneous model residency, but unified
memory is shared by macOS, the UI, Python, model weights, latent tensors, and media
buffers. LTX-2.5's official Fast pack is about 66 GiB on disk; the bf16 transformer
alone cannot be fully resident in 32 GB. Apple Silicon therefore needs disk-backed
streaming/offload, low-resolution first passes, aggressive process teardown, and
measured free-memory admission—not merely `del model` or a ComfyUI queue boundary.

**Change:** a resource governor owns the one heavy job slot, checks free RAM/disk,
launches generation in a disposable worker process, and confirms process exit before
the next engine starts. Begin at 512p/short duration, then upscale accepted takes.

### 2. “Local LLM” conflicts with a cloud-only director

The proposal names Claude/OpenAI as the brain but the product promises local LLMs.

**Change:** define a `DirectorProvider` contract. Support a high-quality cloud model
for the first PoC and an OpenAI-compatible local endpoint for offline mode. Store the
provider/model/prompt version with every plan. Compare both against a small golden
script suite before claiming interchangeability.

### 3. A 5-second JSON array is too shallow

A flat array cannot represent character identity, asset ownership, time, geography,
screen direction, approved takes, dependencies, or a change to one upstream board.

**Change:** persist `Project -> Bibles -> Scenes -> Shots -> Takes -> Artifacts`, with
immutable artifact lineage and explicit continuity-in/continuity-out state. Shot
duration is a bounded editorial choice, not always exactly five seconds.

### 4. Continuity cannot come from the last frame alone

Last-frame chaining accumulates drift, freezes poor composition, and makes every
later shot depend on every earlier failure. Hard cuts also rarely want the preceding
clip's last frame as their next composition.

**Change:** use a continuity toolbox selected per cut:

- Canonical character/location reference packs and locked style/seed metadata.
- Approved anchor boards per shot; first/last keyframe conditioning where supported.
- Last-frame or overlap extension only for genuinely continuous camera/action shots.
- Pose/depth/edge controls and reference video for blocking when available.
- Continuity checks on identity, wardrobe, props, screen direction, and audio.

### 5. Prompt rules contain a useful tension

The proposed motion prompt must cover scene/character/audio yet must not re-describe
character/environment in I2V. Repetition fights the conditioning image; omitting who
moves makes action ambiguous.

**Change:** the static prompt owns appearance and setting. The motion prompt may name
the actor and describe changing state, action, camera, timing, dialogue, and sound,
but must not repeat stable visual attributes. Store dialogue and sound as structured
cues, then compile an engine-specific render prompt at execution time.

### 6. ComfyUI JSON injection is brittle

Node IDs and widget positions change; a successful queue event does not itself prove
the intended file exists or is valid. Third-party nodes also add supply-chain and
upgrade risk.

**Change:** version known-good API workflows and separate semantic binding manifests.
Pin ComfyUI/custom-node commits, validate `/object_info`, upload assets explicitly,
listen on `/ws`, reconcile with `/history/{prompt_id}`, then probe output media.
Keep a native LTX adapter so the project is not stranded by a ComfyUI regression.

### 7. Concatenation is not post-production

Stream-copy fails when clips differ in codec, dimensions, FPS, timebase, pixel format,
or audio layout. Generated audio will produce clicks, level jumps, room-tone changes,
and dialogue overlap at edits.

**Change:** validate every take with `ffprobe`; normalize selected takes to a mezzanine
profile; assemble video and audio on an explicit timeline; add room tone, fades,
loudness normalization, subtitles, and final QC. Keep simple concat only for the PoC.

### 8. Automation needs recovery and observability

A loop has no durable resume point, cancellation model, stale-output protection, or
way to explain which prompt/model generated a file.

**Change:** SQLite stores jobs and artifact lineage. Each stage is idempotent and
content-addressed. Events stream to the UI. Failed work retries only when safe; users
can resume from the last valid artifact.

### 9. Reference media introduces product and safety requirements

Voice and likeness inputs require consent/provenance; arbitrary uploads need type,
duration, metadata, and path validation. Lyrics/music can create rights issues.

**Change:** asset ingestion records source, ownership/consent, checksum, media probe,
usage scope, and derived proxies. Secrets stay in the OS keychain; project exports
exclude them. Add visible provenance and a deletion path.

## Proposed component boundaries

```text
React storyboard UI
        |
FastAPI project API + event stream
        |
Project service --- SQLite metadata / content-addressed media store
        |
Durable job state machine --- resource governor --- disposable worker process
        |
  +-----+-------------+--------------+----------------+
  | Director adapter  | Image adapter| Video adapter  | Audio adapter
  | cloud/local LLM   | Comfy/native | LTX native or  | LTX/external
  |                   |              | ComfyUI         |
  +-------------------+--------------+-----------------+
        |
Timeline assembler (ffprobe + FFmpeg) -> QC -> export manifest
```

For a distributable full app, React + TypeScript with FastAPI is a good boundary.
Use a normal browser UI during PoC/MVP; add Tauri or Electron only when packaging,
native file dialogs, keychain access, updates, and process lifecycle justify it.

## Canonical storage model

- SQLite: projects, bibles, scenes, shots, takes, jobs, approvals, parameters.
- Filesystem: original assets and immutable generated artifacts by checksum.
- JSON export: portable project manifest with relative paths and schema version.
- Never store model weights or generated media in Git.

## LTX-2.5 decision on the target Mac

LTX-2.5 Fast remains the preferred video engine, but it is a gated 22B bf16 model.
The target Mac must use MPS streaming/offload and should expect slow generations.
The first spike must benchmark 3-5 second 512p video-only and audio-video cases while
recording peak RAM, swap, wall time, and output validity. A 720p/1080p promise is
accepted-output/upscale territory until measurements prove native generation viable.
