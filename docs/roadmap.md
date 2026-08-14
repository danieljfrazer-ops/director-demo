# Roadmap: proof of concept to full app

Each milestone adds one independently testable capability and has an exit criterion.

## Stage 0 — Feasibility spikes

1. Free at least 80 GiB disk, authenticate Hugging Face, accept the LTX-2.5 license,
   and download the Fast pack with the supplied resumable installer.
2. Benchmark official LTX MPS generation at small resolution/duration, video-only
   first and synchronized audio second. Record RAM, swap, time, and failures.
3. Run one pinned ComfyUI image workflow and one LTX workflow if compatible; compare
   reliability with native LTX execution.

**Exit:** one valid anchor image and one 3-5 second conditioned clip can be reproduced
from recorded inputs on the target Mac without exhausting disk or memory.

## PoC 1 — Text to inspectable plan

Add project folders, the versioned Pydantic shot schema, cloud director adapter,
local-compatible adapter, deterministic fixtures, and JSON import/export.

**Exit:** three representative scripts produce schema-valid plans whose dialogue and
story order pass manual review.

## PoC 2 — One approved shot end to end

Add asset ingestion/probing, a golden image workflow, explicit workflow bindings,
ComfyUI event/history reconciliation, one LTX adapter, provenance, and media QC.

**Exit:** one shot goes script -> board -> approved I2V take with a resumable job log.

## PoC 3 — Tiny continuous film

Add 3-5 shots, character/location bibles, approved anchor boards, sequential resource
governor, take selection, normalized FFmpeg assembly, and a continuity checklist.

**Exit:** a 15-25 second film survives restart/resume and has no unexplained artifact.

## MVP 1 — Glossy storyboard review

Add FastAPI + React: project creation, drag/drop references, script editor, scene/shot
cards, board grid, prompt/reference drawer, lock/regenerate/reorder, cost/time preview,
job progress, cancellation, and compare-takes view.

**Exit:** a non-technical user can approve a cut before any video render starts.

## MVP 2 — Audio and delivery

Add voice consent records, dialogue/ambience/music tracks, waveform/timeline preview,
room-tone transitions, loudness normalization, captions, export presets, and final QC.

**Exit:** selected shots export as a watchable H.264/AAC film with clean edit audio.

## MVP 3 — Local-first hardening

Add local director model evaluation, offline mode, keychain secrets, storage quotas,
model manager, crash recovery, migration tests, telemetry opt-in, and signed packaging.

**Exit:** core planning and rendering work with network disabled after model setup.

## Full app — Creative control and scale

Add first/last keyframes, video extension, pose/depth controls, targeted retakes,
character/style LoRAs, branching versions, timeline trim handles, color pipeline,
proxy media, reusable libraries, project archive/restore, and optional cloud burst.

**Exit:** users can revise one shot or transition without unnecessarily regenerating
the rest of the film, and every export remains reproducible and attributable.
