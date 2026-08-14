# Backlog

Priorities: P0 blocks the next milestone; P1 is MVP-critical; P2 is an enhancement.

## P0 — feasibility and foundations

- [ ] Free/attach >=45 GiB storage plus output headroom; authenticate Hugging Face;
  accept LTX-2.5 terms.
- [ ] Benchmark official LTX-2.5 distilled INT8-ConvRot ComfyUI workflow on M5/32 GB
  with recorded memory, swap, thermals, and wall time.
- [ ] Validate text-encoder unload before denoising and VAE unload after output.
- [ ] Capture and pin a golden FLUX-family image workflow on Apple Silicon.
- [ ] Add workflow binding manifests and `/object_info` compatibility validation.
- [ ] Add SQLite project/job/artifact schema and migrations.
- [ ] Add disposable worker process plus one-slot resource governor.
- [ ] Add `ffprobe` validation and normalized assembly profile.

## P1 — usable MVP

- [ ] Asset ingestion: checksum, metadata, proxies, ownership/consent, deletion.
- [ ] React storyboard shell and FastAPI project endpoints.
- [ ] Editable bibles, scene cards, shot cards, references, prompts, and locks.
- [ ] Render queue progress, cancellation, retry, resume, and stale-output detection.
- [ ] Take comparison/approval and dependency-aware invalidation.
- [ ] Dialogue, ambience, music, waveform, captions, and loudness normalization.
- [ ] Golden-script director evals and prompt/schema versioning.
- [ ] Local LLM quality/latency comparison and fully offline path.
- [ ] Export manifest, privacy review, and packaged-app keychain integration.

## P2 — enhancements

- [ ] First/last-frame interpolation and continuous-shot extension.
- [ ] Pose/depth/canny control selection by shot requirement.
- [ ] Automated visual continuity suggestions with human confirmation.
- [ ] Character/style LoRA training workflow with rights metadata.
- [ ] Proxy timeline editor, targeted retakes, and branchable project versions.
- [ ] Storage quota UI, archive/restore, and removable-volume model library.
- [ ] Optional cloud render adapter with explicit privacy/cost preview.
