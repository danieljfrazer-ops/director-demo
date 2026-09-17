# Backlog

The historical P0/P1/P2 and MVP-S sections retain PoC and design evidence. The later
LTX Desktop adoption decision supersedes custom application delivery: use Desktop for
private clip-making and resume an item below only when actual use proves a gap that
configuration, interchange, a thin sidecar/API integration, or a narrow fork cannot
satisfy.

## PUB — portfolio publication

- [x] **PUB-001 — Immutable showcase package.** Select four completed outputs through a
  versioned allowlist; verify source/destination hashes; copy without transcoding; emit
  sanitized provenance; keep local originals and raw sidecars ignored.
- [x] **PUB-002 — Static recorded studio.** Play the real clips, expose safe
  configuration and extension lineage, and keep the creation/extension controls as a
  clearly disabled workflow demonstration.
- [x] **PUB-003 — Zero-backend build.** Produce a static `web/dist/client` export whose
  selected assets are individually below the Pages 25 MiB limit; require no R2,
  Worker, Function, database, API key, or model endpoint.
- [ ] **PUB-004 — Publication rights.** Confirm the publication/reuse basis for each
  generated video and conditioning reference; keep all unapproved clips out of the
  initial selection.
- [ ] **PUB-005 — Public release.** Choose a code licence, review the coherent Git diff,
  push to GitHub, connect Cloudflare Pages, and smoke-test playback and byte-range
  seeking at the deployed URL.
- [ ] **PUB-006 — Recorded-demo accessibility debt.** Add captions and perform a
  keyboard/screen-reader review before representing the showcase as delivery-ready.

## MVP-S — local single-shot scene director

- [x] **MVP-S00 — LTX Desktop adoption gate.** LTX Desktop completed a local M5 smoke
  render and is the provisional primary generation/editor UI.

- [ ] **MVP-S00A — LTX product-feasibility gate.** Prove start/end interpolation,
  moderate-motion chaining, fixed-boundary middle replacement, source continuation,
  recursive stitched-assembly extension, generated audio seam, and six-clip
  thermal/resource stability before application work.
- [ ] **MVP-S00B — Local helper-adapter bakeoffs.** Select measured local prompt optimizer,
  storyboard, segmentation, and target-style anchor adapters; verify licences, offline
  operation, peak memory, latency, and teardown before LTX.
- [ ] **MVP-S01 — Durable revision core.** Add typed projects/revisions, SQLite
  migrations, immutable content-addressed artifacts, dependency digests, approvals,
  events, selections, assemblies, and import-only legacy history compatibility.
- [ ] **MVP-S02 — Local service and queue.** Add loopback FastAPI, SSE replay, range
  media, idempotent mutations, a durable one-heavy-slot queue, supervised cancellation,
  restart reconciliation, path confinement, and safe run-scoped deletion.
- [ ] **MVP-S03 — Scene and references.** Add 2–30 second scene setup, measured defaults,
  multiple tagged/timed frames, named multi-reference characters, authoritative
  background, rights/consent, source-video final-frame extraction, and locked source.
- [ ] **MVP-S04 — Deterministic clip plan.** Balance 2–5 second render slots, enforce
  legal LTX frames, align authoritative references where safe, explain boundaries, and
  trim assembly to exact requested generated duration.
- [ ] **MVP-S05 — Local prompt approval.** Optimize locally by default; expose editable
  master intent, continuity contract, all per-slot prompts, plan rationale, manual
  fallback, immutable revisions, and approval/staleness rules.
- [ ] **MVP-S06 — Storyboards and target anchors.** Generate low-cost B&W proposals for
  missing beats; support feedback versions, replacement, approval, justified skip;
  prepare character/background composites and approve target-style conditioning frames.
- [ ] **MVP-S07 — Progressive generation.** Render LTX clips sequentially with genuine
  hierarchical progress, playable validated partials, cancellation, recovery, approved
  boundary chaining, exact shared-frame joins, source prepend, normalized audio/video,
  immutable assembly, and QC.
- [ ] **MVP-S08 — Contiguous retakes.** Select generated-only contiguous slots, review
  feedback-derived prompts, keep/change seed, apply incoming/outgoing constraints,
  preserve unchanged hashes, promote alternatives, reassemble, compare, and roll back.
- [ ] **MVP-S08B — Stitched-scene extension.** Extend any selected assembly from its
  exact retained final decoded frame; plan/render only appended slots; preserve the parent
  as an immutable prefix; assemble one shared frame; support recursive extension,
  comparison/rollback, cross-boundary retakes, and descendant staleness.
- [x] **MVP-S08B-a — Legacy-compatible extension vertical slice.** Add immutable
  `extension.json` lineage, validated parent assembly hash/digest, exact endpoint
  extraction, appended-only queueing, parent-prefix assembly, recursive run-card action,
  parent deletion protection, and synthetic FFmpeg frame-count proof. This proves the
  reusable execution seam; SQLite branching/staleness and storyboard approval remain in
  MVP-S08B.
- [x] **MVP-S08B-b — Real M5 recursive-extension feasibility spike.** Run a first-level
  extension, recursively extend its assembled result, and compare a prompt-only moderate
  motion sibling at 1024×576/24 fps/49 frames. Exact endpoint hashes, frame arithmetic,
  media conformance, seams, and resource envelopes pass; normal-speed human creative
  approval remains open; retain detailed evidence privately.
- [ ] **MVP-S09 — MVP acceptance.** Pass 2/6/17/30-second, source continuation,
  multi-reference/background, restart/cancel, retake/rollback, byte-range playback,
  network-denied, M5 resource, accessibility, and normal-speed human quality tests.

Detailed requirements and exit criteria live in the
[MVP specification](mvp-single-shot-spec.md),
[technical design](mvp-single-shot-technical-design.md), and
[implementation plan](mvp-single-shot-implementation-plan.md). The independent review
and accepted changes are recorded in the
[MVP red-team disposition](mvp-single-shot-redteam-disposition.md).

## P0 — feasibility and creative risk

- [x] Authenticate Hugging Face and verify gated LTX-2.5 access.
- [x] Probe stock INT8-ConvRot on target MPS; record the `aten::_int_mm` blocker.
- [x] Purge incompatible INT8 partials; preserve reusable LTX-2.5 components.
- [x] Provide at least 100 GiB free on the fast internal model volume.
- [x] Install `uv` 0.12.5 through Homebrew.
- [x] Complete strict LTX-2.5 component download and verify hashes.
- [x] Pin the official runtime and install its isolated macOS environment.
- [x] Verify PyTorch 2.13 MPS and zero-copy `mpsgraph_zc` attention.
- [x] Add native render CLI, disk-offload command compilation, JSONL events,
  process-group cancellation, and `ffprobe` validation.
- [ ] Pin official LTX-2 source and benchmark strict LTX-2.5 BF16 disk streaming
  against rungs A–D in the Stage 0B runbook.
- [ ] Record the local video-engine ADR and explicit no-cloud MVP boundary.
- [x] Prove one anchor-image workflow and worker-process teardown on Apple Silicon.
- [ ] Run the ten-pair cross-shot identity spike; achieve at least 7/10.
- [x] Prove one last-frame-chained take and record boundary continuity, inherited-defect,
  and motion-overshoot risks.
- [ ] Verify model and reference-asset licences for intended demo/distribution use.
- [ ] Define likeness, voice, music, and reference-media consent/provenance records.
- [ ] **QUALITY GATE:** eliminate or materially reduce eye, mouth, and teeth deformation
  in dialogue/portrait shots. Rung A failed with unquantized BF16 distilled weights, so
  do not mislabel this as a quantization defect. Run the no-dialogue, timing, resolution,
  VAE, framing, and seed ablations in a private experiment record; retain a future larger-model or
  future larger-local-model escape hatch if the local distilled ceiling remains
  unacceptable; the MVP has no cloud fallback.
  **Current disposition:** material reduction is confirmed by user playback at
  1024 x 576 / 121f / 24fps; keep the issue open for oblique/small faces, aggressive
  motion, dialogue extremes, and automated take selection.

## P1 — demonstrable short film

- [x] Add a `director-demo render-ltx` vertical slice for one pinned engine path.
- [ ] Add rights-aware checksummed ingestion for arbitrary user-supplied source assets;
  editorial artifacts already have confined paths, hashes, and media probes.
- [x] Add project-root-confined editorial artifact resolution, take/boundary hash
  verification, and pre/post-assembly media probing.
- [x] Persist an atomic, versioned run sidecar with exact prompt/config, engine revision,
  input/output hashes, timing, peak RSS, media probe, status, and review fields.
- [x] Make process logs immutable per run ID; retain the first overwritten retry-log
  incident as a documented provenance defect.
- [x] Add a generated local run index and filterable browser contact sheet with playable
  native/fullscreen video, prompts, configuration, provenance, performance, and notes.
- [ ] Add WebVTT captions/transcripts to generated dialogue clips and the archive player.
- [ ] Add hash-named outputs, conservative stale-output detection, retry, and resume.
- [ ] Pin runtime/node revisions and validate engine capabilities before queueing.
- [ ] Add cancellation/teardown owned by the model worker and verify memory recovery.
- [x] Add manifest-driven normalized FFmpeg assembly with reversible trims/fades,
  immutable outputs, final validation, dependency digests, and exact manifest snapshots.
- [x] Prove homogeneous stream-copy assembly and normalized manifest-driven assembly,
  including a heterogeneous-resolution/frame-rate/sample-rate normalization fixture.
- [ ] Add and evaluate the local director provider; remove cloud bootstrap from the MVP
  path and prove it with outbound networking disabled.
- [x] Add strict local-LLM JSON Schema output and deterministic M5 production manifests.
- [x] Add one-slot shot states and LTX prompt-compilation ablations inspired by the
  MIT-licensed Higgsfield explainer workflow.
- [ ] Generate the 3–5 shot film, score its defect budget, and run the taste gate.
- [x] Generate and technically validate a 10.15-second three-clip continuity micro-film;
  human defect scoring and the taste gate remain open.
- [x] Retake the chained outro from an approved neutral boundary with constrained
  low-amplitude motion; reject any take whose face becomes too small/oblique, and
  compare it with an editorial trim of the current ending. T1 is technically accepted
  and provisionally passes frame review; normal-speed user approval remains open.
- [x] Produce the generic editorial-trim comparison without modifying the source; the
  targeted retake is running as a lineage/boundary experiment rather than film polish.
- [x] Probe audio diffusion skipping: the pinned distilled entrypoint rejects the shared
  flag, so it is not exposed. Revisit only with an exact compatible engine revision;
  the current path has no true video-only generation switch.
- [ ] Publish the measured demo findings and go/no-go recommendation.
- [ ] Add an explicit original-manifest base URI in the next editorial schema revision;
  retain in-memory migration for early embedded-boundary snapshots and never rewrite
  historical evidence merely to fit a current schema.
- [ ] **CONTINUITY GATE:** prove a deliberately designed two-clip scene reads as one
  uninterrupted action at normal speed. Use the exact retained boundary frame, preserve
  pose/expression/framing and camera/motion velocity, manage continuous audio separately,
  and compare a hard shared-frame join with a short overlap transition. The current
  9–11 second fixture cuts fail this gate despite improved facial integrity.
- [x] Execute the bounded exact-frame seam render and produce hard-join and six-frame
  overlap variants. Technical diagnostics materially improve; user normal-speed verdict
  selects the exact hard join and rejects the dissolve's phase-shift/motion-blur effect.
- [x] Add a minimal local generation UI with reference-image upload, motion prompt,
  1–3 sequential clips, measured M5 defaults, exact-frame continuation, hard-join draft
  assembly, progress/history, playback/download, and a double-click restart launcher.
- [x] Add reusable multi-reference timeline input: 1–8 immutable uploaded images,
  editable unique IDs, exact global positions, native repeated LTX image conditioning,
  deterministic cross-clip mapping, hashes, compiled prompts, and run-card provenance.
- [ ] Run a controlled first/last-frame interpolation taste test at the measured M5
  profile. Compare one 5-second clip with a two-clip continuation, score endpoint
  fidelity, motion plausibility, identity drift, seam continuity, memory, and runtime,
  and retain the result before promoting multi-reference defaults.
- [ ] Make edit-boundary semantics frame-addressed rather than relying only on decimal
  exclusive out-points; validate that the conditioning frame is exactly the final
  retained source frame and reject off-by-one joins.
- [ ] Add seam QC that reports adjacent-frame difference, pose/framing displacement,
  optical-flow direction/magnitude discontinuity, and audio level/phase discontinuity;
  keep normal-speed human review as the creative authority.
- [x] Enforce final `yuv420p` after FFmpeg transitions and reject incompatible delivery
  pixel formats; retain the first promoted `yuv444p` overlap as rejected evidence.

## P2 — only if the demo earns it

- [x] Build the first read-only run-history slice; keep storyboard authoring conditional.
- [x] Add a read-only manifest-backed editorial review slice showing selections,
  structured QC, retained defects, edit decisions, lineage, delivery, and freshness.
- [x] Add atomic domain operations for take registration, structured review, approved
  selection, and explicit selection clearing; future UI writes must call these rules.
- [ ] Add SQLite once observed JSONL query/recovery needs justify a schema.
- [ ] Add editable bibles, locks, dependency-aware invalidation, and take comparison.
- [ ] Add dialogue/ambience/music timeline, captions, and loudness normalization.
- [ ] Add keychain secrets, storage quotas, offline evaluation, and packaging.
- [ ] Evaluate first/last-frame, pose/depth, extension, and targeted retake controls.
- [ ] Consider LoRA training only with a measured hardware route and rights metadata.
- [ ] Re-evaluate cloud burst, archive/restore, proxies, and a color pipeline from use.

## P2 UI feature backlog — requirements captured by the interface studies

These are product requirements, not claims about the current implementation. The
three interactive mock-ups in `web/` use this common list as their design brief.

### Projects, source material, and production setup

- [ ] **UI-001 — Project library.** Create, duplicate, archive, restore, search, sort,
  and switch between film projects; show stage, last activity, completion, storage,
  queued work, warnings, and the current approved cut without opening each project.
- [ ] **UI-002 — Guided project creation.** Import a synopsis, treatment, screenplay,
  Fountain/Final Draft text, or paste a prompt; choose aspect ratio and intent; save
  incomplete setup as a draft; never transmit source material without disclosure.
- [ ] **UI-003 — Reference-media workspace.** Add images, video, voice, music, and SFX
  by upload or safe local path; preview, label, group, replace, checksum, and remove
  assets; record purpose, strength, source, ownership, consent, allowed use, and
  deletion state for every asset.
- [ ] **UI-004 — Editable production bibles.** Review and edit extracted characters,
  wardrobe, voices, locations, props, style, palette, and continuity rules; attach
  canonical references and distinguish locked traits from shot-local direction.
- [ ] **UI-005 — Versioned pipeline profile per project.** Configure planning, anchor
  image, video, audio, upscale, and assembly adapters; expose only supported engine
  capabilities and legal geometry; show privacy, licence, cost, quality, time, memory,
  and storage implications before saving a versioned profile.
- [ ] **UI-006 — Safe defaults and preflight.** Validate runtime/model revisions,
  available disk and memory, reference rights, frame geometry, prompt limits, output
  paths, and server trust before queueing; distinguish errors, blockers, and advice.

### Story plan and storyboard editing

- [ ] **UI-007 — Script-to-plan review.** Present synopsis, script, extracted story
  entities, scenes, and proposed shots side by side; show source-line traceability and
  let the user accept, reject, merge, split, or regenerate a proposal.
- [ ] **UI-008 — Complete editable shot record.** Edit title, dramatic intent, shot
  size, duration, static anchor prompt, motion/camera prompt, negative prompt, seed,
  dialogue, ambience, SFX, music, transition, references, and continuity in/out.
- [ ] **UI-009 — Visual storyboard desk.** View boards as grid, filmstrip, list, scene,
  or timeline; filter by scene, state, warning, cast, location, or approval; retain
  starting images, prompts, expected outputs, and provenance together.
- [ ] **UI-010 — Direct manipulation.** Reorder shots, move between scenes, duplicate,
  split, merge, insert, delete with recovery, and change duration; show ripple effects
  on numbering, cut length, audio cues, transitions, and downstream artifacts.
- [ ] **UI-011 — Anchor generation and comparison.** Generate or import starting
  images per shot; compare takes at matched zoom, inspect metadata, select, approve,
  lock, annotate, reject, and regenerate without invalidating unrelated approved work.
- [ ] **UI-012 — Dependency-aware changes.** Preview exactly which anchors, video
  takes, audio, assemblies, and exports become stale before committing a bible, prompt,
  reference, duration, or configuration change; offer retain, invalidate, or branch.
- [ ] **UI-013 — Continuity review.** Show previous/current/next frames and scored
  identity, wardrobe, prop, location, lighting, eyeline, screen-direction, action, and
  voice checks; allow human overrides with notes rather than hiding score uncertainty.
- [ ] **UI-014 — Storyboard versions and approvals.** Save named snapshots, diff any
  two versions, branch alternatives, record approval notes, and restore without losing
  immutable artifact history.

### Generation, retries, and queue control

- [ ] **UI-015 — Flexible render scope.** Generate all eligible shots, a selected
  subset, one scene, one shot, missing shots, stale shots, failed shots, or one at a
  time; clearly state what is excluded and why before queueing.
- [ ] **UI-016 — Resource-aware render queue.** Show queued, preparing, rendering,
  validating, review, failed, cancelled, and blocked jobs; enforce the one-heavy-model
  slot, support reorder/pause/cancel/resume, expose measured ETA, and verify teardown.
- [x] **UI-016a — Genuine local render progress.** Parse the pinned LTX runtime's
  two real denoising counters into typed, persisted progress; aggregate progress across
  sequential clips, validation, and assembly; expose queue position. Retain polling as
  the simple local transport. Measured ETA and stall detection remain in UI-016 rather
  than presenting speculative feedback.
- [x] **UI-016b — Scoped cancellation and seekable playback.** Allow confirmed
  cancellation of one queued or active local generation, retain its run folder, hide
  progress after every terminal outcome, and serve MP4 HEAD/range requests correctly.
  Reorder, pause/resume, measured ETA, and stall detection remain in UI-016.
- [ ] **UI-017 — Immutable retries.** Retry failed or unsatisfactory work with the same
  inputs or adjusted prompt, seed, duration, references, prompt compilation, or engine
  parameters; always create a new take with parentage and preserve prior takes.
- [ ] **UI-018 — Failure recovery.** Translate engine errors into actionable guidance,
  preserve diagnostics, reconcile after restart, avoid duplicate jobs, and offer safe
  retry from the last validated boundary.
- [ ] **UI-019 — Render notifications and attention inbox.** Surface completions,
  failures, expiring consent, stale approvals, continuity warnings, and storage pressure;
  provide a single review-next action without requiring constant monitoring.

### Review, assembly, and delivery

- [ ] **UI-020 — Take player and comparison.** Preview available clips with frame-step,
  loop, speed, mute, waveform, timecode, full-screen, A/B, side-by-side, and onion-skin
  comparison; show generated inputs and provenance without covering the picture.
- [ ] **UI-021 — Take selection and QC.** Rate, annotate, reject, approve, and choose a
  take per shot; record structured defects and confirm technical validation separately
  from creative approval.
- [ ] **UI-022 — Assembly workspace.** Build a working cut from selected takes; reorder,
  trim within validated limits, set transitions, add handles, replace a take in place,
  and expose gaps or stale media before stitching.
- [ ] **UI-023 — Audio and finishing timeline.** Place dialogue, ambience, room tone,
  SFX, music, captions, fades, and transition audio on separate tracks; preview mixes,
  normalize loudness, and surface missing or unlicensed assets.
- [ ] **UI-024 — Stitching and cut versions.** Queue normalized FFmpeg assembly, show
  progress and validation, retain named cut versions, compare cuts, and prevent an old
  job from silently overwriting a newer edit.
- [ ] **UI-025 — Preview proxies and offline review.** Generate lightweight proxies and
  contact sheets without implying draft proxies are validated masters; allow review
  while the heavy engine is unloaded.
- [ ] **UI-026 — Download and export centre.** Download an individual scene/take,
  selected scenes, a stitched cut, all cuts, stills, subtitles, audio stems, prompts,
  project archive, and reproducibility manifest; show size, format, checksum, licence,
  and validation state; use resumable archives for large packages.
- [ ] **UI-027 — Delivery presets and final QC.** Configure draft, review, and delivery
  outputs; probe codec, dimensions, frame rate, timebase, pixel format, audio layout,
  captions, and loudness; require explicit approval before marking a master delivered.

### Trust, accessibility, and operational quality

- [ ] **UI-028 — Provenance everywhere.** From any board, take, or export, inspect input
  hashes, parent artifacts, workflow/model revisions, seed, parameters, timestamps,
  engine location, licence, consent, and validation result; export the same record.
- [ ] **UI-029 — Honest local/cloud state.** Persistent, unambiguous indicators show
  whether each stage is local or remote, what will leave the device, estimated cost,
  and whether explicit consent is still valid; never label the OpenAI bootstrap local.
- [ ] **UI-030 — Recoverable destructive actions.** Confirm exact affected artifacts,
  prefer archive/trash, offer undo where possible, and never hide downstream impact.
- [ ] **UI-031 — Accessible production UI.** Full keyboard operation, visible focus,
  semantic labels, screen-reader status announcements, non-colour state cues, scalable
  typography, reduced motion, captions, and a high-contrast mode.
- [ ] **UI-032 — Responsive and long-running resilience.** Support desktop production
  first, useful tablet review, lost connections, app restart, background jobs, stale
  tabs, and very large projects without losing edits or presenting phantom progress.
- [ ] **UI-033 — Audit-ready event history.** Filter and export append-only project,
  configuration, generation, approval, assembly, download, and deletion events while
  keeping secrets and irrelevant personal data out of logs and project exports.

## Phased UI feature backlog — research/red-team refresh 2026-08-16

This phased plan supersedes the flat UI study list for delivery sequencing while
keeping the requirement IDs above as traceable source requirements. It is informed
by the interface red-team and comparable-product research recorded in
`docs/ui-redteam-research-2026-08-16.md`.

### Phase 0 — Foundational shell and trustworthy mock state

- [x] **UI-P0-001 — Navigable project library.** Show multiple film projects with
  status, progress, shots, takes, warnings, and direct entry to boards, generation,
  exports, and attention items.
- [x] **UI-P0-002 — Project-specific storyboards.** Keep each project’s images,
  shots, prompts, states, references, and pipeline profile separate rather than
  reusing one global shot list.
- [x] **UI-P0-003 — Production-stage navigation.** Provide a durable in-project
  workbench across Plan, Boards, Generate, Takes, Cut, and Delivery.
- [x] **UI-P0-004 — Local-first status surface.** Show the local engine profile,
  one-heavy-model-slot constraint, queue count, and privacy state in persistent
  navigation.
- [x] **UI-P0-005 — Mock-fixture provenance.** Use immutable mock storyboards and
  images as fixtures for interaction review, not as implied generated outputs.
- [ ] **UI-P0-006 — Accessibility baseline.** Add automated checks for keyboard
  reachability, focus order, reduced motion, semantic labels, and non-color-only
  state indicators.

### Phase 1 — Story planning, references, and storyboard editing

- [x] **UI-P1-001 — Story/source planning tab.** Expose synopsis, script excerpt,
  extracted cast/locations/style, and traceable production bibles.
- [x] **UI-P1-002 — Reference rights ledger.** Display reference purpose, type,
  strength, source, and consent/licence status before render actions.
- [x] **UI-P1-003 — Complete shot editor mock.** Edit static image prompt, motion
  prompt, negative prompt, duration, seed, reference links, and continuity notes.
- [x] **UI-P1-004 — Storyboard view modes.** Demonstrate card, filmstrip, list,
  and timeline mode affordances even while only the card view is fully mocked.
- [x] **UI-P1-005 — Dependency impact preview.** Show what prompt, reference, and
  configuration changes would stale before saving.
- [ ] **UI-P1-006 — Direct manipulation.** Implement real reorder, duplicate,
  split, merge, delete-with-recovery, scene reassignment, and numbering ripple.
- [ ] **UI-P1-007 — Storyboard version diff.** Compare board snapshots by changed
  prompt, anchor, reference, duration, approval, and downstream stale state.

### Phase 2 — Generation scope, preflight, and retry control

- [x] **UI-P2-001 — Flexible render scopes.** Demonstrate all eligible, selected
  subset, current shot, failed, missing video, and stale-only queue choices.
- [x] **UI-P2-002 — Preflight summary.** Surface runtime, privacy, rights, geometry,
  storage, and excluded-shot checks before queueing.
- [x] **UI-P2-003 — Resource-aware queue mock.** Show rendering, queued, blocked,
  cancel, pause-after-current, and one-slot sequencing.
- [x] **UI-P2-004 — Immutable retry composer.** Retry with parentage, seed/prompt
  overrides, retry reason, and inherited anchor/reference context.
- [ ] **UI-P2-005 — Real queued job records.** Persist queue jobs with status,
  retry lineage, stale invalidation, crash recovery, and duplicate prevention.
- [ ] **UI-P2-006 — Actionable engine errors.** Translate failures into safe retry,
  boundary recovery, configuration, or rights/remediation actions.
- [ ] **UI-P2-007 — Attention inbox.** Turn render completions, failures, consent
  expiry, stale approvals, and storage pressure into a single review-next list.

### Phase 3 — Take review, QC, and approval

- [x] **UI-P3-001 — Take review workspace.** Show generated preview, frame controls,
  scene download, take tabs, A/B affordance, scores, notes, defects, and approval.
- [x] **UI-P3-002 — Provenance sidecar mock.** Surface seed, engine, parent anchor,
  validation state, and local execution in the take review panel.
- [ ] **UI-P3-003 — Frame-accurate annotations.** Add comments and defect marks on
  specific frames, with resolved/unresolved state and exportable review history.
- [ ] **UI-P3-004 — Take comparison modes.** Add real side-by-side, onion-skin,
  loop range, speed, mute, waveform, and frame-step comparison.
- [ ] **UI-P3-005 — Separate approval gates.** Persist technical validation,
  creative approval, selected-take approval, and delivery approval separately.
- [ ] **UI-P3-006 — Captions and transcript review.** Add WebVTT/SRT preview,
  dialogue sync checks, speaker labels, and caption export state.

### Phase 4 — Assembly, stitching, and delivery

- [x] **UI-P4-001 — Assembly timeline mock.** Show selected takes on video/audio
  lanes, cut versions, stale impact, gap check, and stitch action.
- [x] **UI-P4-002 — Delivery center mock.** Show scene downloads, stitched cut,
  reproducibility bundle, complete archive, checksums/manifests, and final QC.
- [ ] **UI-P4-003 — Real cut editing.** Implement trim handles, ripple changes,
  transition controls, take replacement, cut branching, and stale cut invalidation.
- [ ] **UI-P4-004 — Stitching job lifecycle.** Queue FFmpeg assemblies, validate
  outputs, retain named cut versions, and prevent older jobs from overwriting newer
  edit decisions.
- [ ] **UI-P4-005 — Export packaging.** Generate resumable archives for individual
  scenes, selected scenes, cuts, storyboards, stills, captions, audio stems,
  prompts, manifests, and complete projects.
- [ ] **UI-P4-006 — Delivery presets and final QC.** Validate codec, dimensions,
  frame rate, timebase, pixel format, audio layout, captions, loudness, license,
  and approval state before marking a master delivered.

### Phase 5 — Advanced production and collaboration

- [ ] **UI-P5-001 — Reusable workflow templates.** Model generation as configurable
  reusable workflows with per-node run/retry controls, inspired by node-based
  creative workflow tools.
- [ ] **UI-P5-002 — Collaboration and review links.** Add permissioned review links,
  internal/client comment separation, expiry, download controls, and watermarked
  review surfaces.
- [ ] **UI-P5-003 — Production tracking layer.** Add tasks, owners, due dates,
  review status, approvals, assets, shots, versions, notes, and schedule/reporting
  views for larger productions.
- [ ] **UI-P5-004 — External editor handoff.** Export/import XML/EDL, storyboard
  PDFs, animatics, and handoff packages for NLE or storyboard-tool review.
- [ ] **UI-P5-005 — Cloud-burst adapter governance.** Add explicit cloud consent,
  cost estimate, transmission disclosure, adapter capability checks, and local/cloud
  provenance per artifact.
- [ ] **UI-P5-006 — Operational resilience.** Handle large projects, stale tabs,
  app restart, offline review, storage quotas, archive/restore, and background-job
  reconciliation without losing edits.

### Phase 6 — Specialized, extensible, and delivery-grade workflows

- [ ] **UI-P6-001 — Guided workflow library.** Build Simple mode from curated,
  versioned pipeline forms with declared capabilities, dependencies, preview media,
  licences, supported models, and safe measured defaults.
- [ ] **UI-P6-002 — Expert graph mode.** Inspect and edit the executable graph,
  publish reusable subgraphs, choose exposed production parameters, and migrate
  workflow revisions through explicit diffs without mutating historical takes.
- [ ] **UI-P6-003 — Non-destructive anchor repair.** Add layers, masks, regional
  prompts, inpaint/outpaint, paintover, and repair revisions whose lineage remains
  inspectable from every downstream take.
- [ ] **UI-P6-004 — Advanced comparison and automated QC.** Support synchronized
  A/B, wipe, onion-skin, reference overlays, config diffs, codec/frame/duration checks,
  and advisory model scores that never silently replace human approvals.
- [ ] **UI-P6-005 — OTIO conform and portable archive.** Import/export timelines,
  conform newer approved takes through a previewable change list, relink missing
  media by stable ID/hash, and verify portable project packages.
- [ ] **UI-P6-006 — Content-addressed assets and model manager.** Deduplicate media,
  pin model/runtime hashes, disclose licences and disk use, diagnose missing
  dependencies, and audit whether a historical take is reproducible.
- [ ] **UI-P6-007 — Temporal and audiovisual direction.** Generate or repair frame
  ranges, first/last-frame transitions and extensions; direct dialogue, ambience,
  music, stems, lip sync, captions, loudness, and audio provenance.
- [ ] **UI-P6-008 — Colour and rendition pipeline.** Add OCIO display transforms,
  SDR/HDR masters, alternate aspect ratios, social crops, localization, captions,
  watermarks, and independent approval per rendition.
- [ ] **UI-P6-009 — Signed provenance.** Emit and validate C2PA Content Credentials
  covering reference ingredients, AI/ML inputs, composed scenes, editorial repairs,
  cut assembly, and delivery transformations.
- [ ] **UI-P6-010 — Distributed execution and adapter SDK.** Route equivalent frozen
  jobs to local, remote, or cloud workers with privacy/cost disclosure; support
  generator, QC, exporter, asset-resolver, and NLE adapters through a stable API.
- [ ] **UI-P6-011 — Production-scale collaboration.** Add roles, assignments,
  deadlines, presence, locks, conflict-safe edits, private/client notes, approval
  audit trails, expiring review links, and watermarked review media.
- [ ] **UI-P6-012 — 3D previs and continuity intelligence.** Add blocking, lenses,
  camera paths, eyelines, screen direction, reusable sets/characters, and explainable
  continuity suggestions with explicit human override.
