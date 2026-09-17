# Lessons learned

This log separates observations from explanations. A plausible cause remains a
hypothesis until a controlled run changes only that variable.

## 2026-09-16 — static recorded showcase

- Four completed H.264/AAC outputs total 17,858,542 bytes and each remains below the
  Cloudflare Pages 25 MiB static-asset limit. This validates a Pages-only portfolio;
  R2 adds no current capability.
- A public demo is safer and more credible when it is a declared read model over an
  explicit media allowlist, rather than a raw export of private run history.
- Automatic draft selection in the existing sidecars is technical workflow state, not
  human creative approval. Public metadata normalizes it to pending human review while
  preserving the recorded source decision.
- Hash-named, byte-identical copies let the deployed site remain self-contained without
  mutating, hard-linking, or depending on ignored local originals.
- Publication rights and code licensing are release gates independent of a successful
  build, valid media, or free hosting allowance.

## 2026-08-17 — LTX Desktop adoption spike

- LTX Desktop 1.2.0 supports local LTX-2.5 MPS generation on the 32 GB M5; the earlier
  repository statement that Desktop only established LTX-2.3 was stale.
- Existing Comfy-aligned LTX-2.5 weights are compatible by filename and content. A
  flat Desktop model layout can reuse them with links rather than another 70 GB copy.
- Local mode depends on at least 15 GB available at backend launch. The same machine
  selected API-only mode at 12 GB and local streaming mode after a clean 15 GB launch.
- The five-second 1024 x 576 smoke render completed in 1,028.63 seconds and passed
  media validation and frame inspection. This is sufficient to adopt Desktop for the
  next private clip-making trial, not evidence that its provenance or continuity
  controls match DirectorDemo.
- For a private tool, extension cost matters more than product differentiation. Prefer
  configuration, interchange, a thin API/sidecar, or an Apache-2.0 fork over rebuilding
  Desktop's editor and model-management surface.

## 2026-08-15 — first native LTX-2.5 take

- The official LTX-2.5 Fast distilled BF16 pipeline can render synchronized video and
  audio on the 32 GB M5 using zero-copy MPS attention and disk offload. The 448 x 256,
  49-frame run completed in 685.24 seconds with 13.49 GB peak RSS and no swap growth.
- The first launch exposed missing Torchvision and a Python build without `_lzma`.
  Rebuilding the isolated runtime with Homebrew Python 3.12 and probing the Gemma 4
  processor in preflight prevents recurrence.
- Audio is a surprisingly strong part of the local result. The user's playback review
  rated it positively, so audio must be preserved as its own quality dimension.
- Eyes and mouth are the first blocking creative defect. The result resembles early
  generative-video facial deformation and cannot be the default product profile.
- This defect did **not** come from an INT8/FP8 quantized execution path. The successful
  command used the unquantized BF16 distilled transformer and BF16 VAEs. Distillation,
  low facial pixel count, speech-driven motion, short dialogue timing, the convolutional
  VAE, and source-anchor framing remain separate hypotheses.
- “It rendered” and “it is usable” are different gates. Runtime feasibility has passed
  rung A; facial quality has failed it.
- Render configuration and human observations must travel with the artifact. Each new
  attempt gets an atomic `.run.json` record in the private local archive. The public
  showcase exposes only allowlisted playback and review metadata.

## Working rules for subsequent experiments

1. Change one meaningful variable per run and retain the same anchor and seed unless
   seed sensitivity is the variable under test.
2. Score eyes, mouth/teeth, identity, motion, audio, and lip synchronization separately.
3. Do not infer model limits from a 448 x 256 dialogue close-up; test a no-dialogue
   control before resolution, then duration, then a materially larger raster.
4. Keep all heavy execution sequential. The browser archive and lightweight tooling may
   remain running, but image, video, and local-LLM model workers must not overlap.
5. A measured default must pass safety, usability, and creative-quality gates. Until
   then, UI values are experiment presets rather than claims of optimality.

## 2026-08-16 — target geometry and first continuity film

- 1024 x 576 / 121 frames / 24 fps is numerically viable: 18m12s, 14.80 GB peak
  child RSS, zero swap delta, no thermal warning, valid synchronized output.
- Disk-streamed model-weight I/O dominates small tests; temporal and resolution scaling
  becomes visible mainly in full-resolution refinement and VAE decode.
- Raising facial pixel count and giving dialogue more time materially improve eyes and
  mouth. Neither fully eliminates later speech-expression/identity drift.
- Repeating the five-second profile at seed 100 changes the exact eye and mouth defects
  without removing the category. Preserve multiple immutable takes and rank them; do
  not silently retry until one looks acceptable or present a single seed as deterministic.
- The shared LTX argument utilities describe audio diffusion skipping, but the pinned
  `ltx_pipelines.distilled` entrypoint rejects `--audio-skip-step`. Do not expose a knob
  based on repository-wide search; validate the exact selected entrypoint's capability.
  The current distilled profile has no supported audio-skip or true video-only mode.
- Last-frame chaining creates a close boundary match but propagates the source frame's
  defects. A boundary frame must be approved as an artifact before downstream work.
- Motion prompts are not precise motion contracts: a “small nod” and “slow pull-out” can
  become a large body exit. Amplitude constraints, first/last-frame controls, review,
  and targeted retakes remain necessary.
- Homogeneous 1024 x 576 / 24 fps H.264/AAC takes concatenate losslessly in under a
  second. Final media still needs its own hash and `ffprobe`; source validity is not
  sufficient evidence for an assembled deliverable.

## 2026-08-16 — reusable editorial slice and retake preflight

- A non-destructive edit is reusable when trim/fade values are data, source takes remain
  immutable, and generic assembly produces a separately validated/hash-addressed
  delivery. The first manifest-driven recovery cut proves this and does not erase the
  rejected source defect.
- Assembly provenance must snapshot the exact manifests consumed. Merely recording a
  mutable head path/hash is insufficient once review metadata or selections change.
- Media freshness and provenance-head freshness differ. Review-only metadata changes do
  not require re-encoding media; selected take, source/boundary hash, edit, revision, or
  delivery changes do.
- Shared repository arguments are not engine capabilities. The pinned distilled
  entrypoint rejected an audio-skip flag before model loading; exact entrypoint help is
  now checked by preflight and the unsupported option is removed.
- Attempt manifests were immutable but retry process logs originally shared one output
  stem. The first rejected-argument log was overwritten by its retry. New logs include
  the run ID so every future failed/successful attempt retains independent diagnostics.
- Conditioning lineage may cross editorial shot boundaries. Parent validation therefore
  belongs at project scope, with missing-parent, self-parent, and cycle rejection, rather
  than assuming every continuation is another take inside the same shot.
- Historical snapshots must remain readable after schema evolution. Early 1.0 snapshots
  embedded their boundary record inside a take; the loader now migrates that shape in
  memory without rewriting the evidence file, and regression coverage preserves it.
- Relative artifact roots are meaningful at the manifest head's location. A byte-exact
  snapshot moved beside a delivery cannot be treated as a new mutable head; review
  export resolves freshness against current heads while retaining the snapshot hash as
  provenance. A future schema revision should record the original manifest base URI.
- A two-second continuation can be more compute-efficient than replacing a longer
  accepted take. T1 removed the known terminal face collapse while retaining immutable
  source material, but still requires normal-speed creative review and comparison with
  the cheaper trim/fade alternative.
- A collection of individually plausible takes is not evidence of a continuous scene.
  User playback rejected both recovery cuts because pose, expression, framing, motion
  velocity, and perceived timing reset at joins. Continuity is a cut-level gate that
  must pass before facial-detail scoring can meaningfully dominate review.
- Conditioning from the nominal next frame is insufficient if the assembler excludes
  that frame. FFmpeg trim out-points are exclusive; a boundary join must explicitly
  retain the exact shared frame or use a declared overlap/transition policy.
- Adjacent-frame similarity is diagnostic, not an approval metric. A join with SSIM
  0.962 still appeared as part of a disjoint sequence because temporal derivatives and
  intent can reset while pixels remain close. Future seam QC must combine exact-frame
  identity, motion/pose trajectory, audio continuity, and normal-speed human review.
- A shared boundary frame should be displayed once in a hard join. Frame-addressed
  inclusive out-points plus a child in-point of frame 1 make this invariant executable;
  overlap transitions instead retain child frame 0 and declare their frame count.
- Quiet generated audio is not necessarily continuous audio. The C1 hard join showed a
  roughly 590x larger decoded sample jump than its equal-power crossfade. Room tone
  should be a continuous finishing track or receive an explicit transition rather than
  being assumed compatible because both clips are quiet.
- Normalizing inputs to `yuv420p` does not guarantee an `xfade` output remains there;
  FFmpeg promoted the first overlap delivery to `yuv444p`. Set the final encoder pixel
  format and validate the delivered stream, retaining the rejected attempt rather than
  overwriting it.
- Adding optional manifest fields must not falsely stale historical media. Dependency
  canonicalization now preserves the legacy hash shape for default hard cuts and adds
  frame/transition fields only when they change output semantics.

## 2026-08-16 — native multi-reference capability

- The pinned `ltx_pipelines.distilled` entrypoint accepts repeated
  `--image PATH FRAME_IDX STRENGTH` arguments. Its two stages both call
  `combined_image_conditionings`: frame zero replaces the opening latent and later
  frames become ordinary keyframe conditioning. This is direct source evidence for
  first/last/interior image control, not yet evidence of creative quality.
- Prompt IDs and image conditioning are different contracts. `@reference-id` is stable
  application metadata; exact frame binding supplies the actual visual constraint. The
  compiled prompt records concise ID/timing bindings without re-describing appearance.
- A global timeline position can map deterministically across sequential clips. A
  reference exactly on a clip boundary belongs on the outgoing last frame, after which
  the existing decoded-boundary chain carries that exact frame into the following clip.
  Assigning both it and the continuation to the next frame zero would create conflicting
  controls and is therefore rejected by the render contract.
- Multiple stills add conditioning work and may introduce incompatible visual demands.
  The UI caps inputs at eight and 50 MiB total; a controlled target-Mac render remains
  required before treating endpoint fidelity or memory cost as accepted evidence.

## 2026-08-16 — PoC artifact retention pass

- Keep original generated takes, run records, approved boundary frames, and accepted or
  rejected comparison media that support documented decisions. Their small footprint is
  worth preserving because manifests and future regression review depend on them.
- Remove derived artifacts when they are reproducible and no longer authoritative. The
  web build/export cache can be regenerated by the documented export/build commands;
  `editorial-recovery-v1` was byte-identical to retained v2, and the initial
  `short_film` assembly was superseded by manifest-driven deliveries.
- Storage cleanup must classify artifacts by provenance role rather than deleting every
  old-looking video. Otherwise a small disk saving silently destroys the evidence used
  to choose continuity, facial-quality, and assembly defaults.

## 2026-08-16 — runtime disk reserve

- A percentage-of-total-volume runtime reserve is not a resource model. On the 460 GiB
  target volume, 15% required 69.1 GiB and rejected a three-clip job with 68.6 GiB free,
  even though the sequential renderer had not started and prior measured runs produced
  only small outputs without proportional scratch growth.
- Setup capacity and steady-state rendering reserve are separate gates. Model download
  still needs roughly 100 GiB of headroom; once installed, the app uses a configurable
  absolute 20 GiB runtime reserve. Sequential clip count affects duration, not peak model
  residency, and must not multiply the reserve.

## 2026-08-17 — non-destructive stitched-scene extension

- An extension must start from the exact final **retained assembly frame**, not the final
  raw frame of the last engine clip. Prior trims, shared-frame removal, and future edits
  can make those different artifacts.
- Extension is immutable assembly lineage, not mutation. The child stores a verified
  parent assembly hash/dependency digest, a hashed endpoint extraction, lineage depth,
  prompt and engine clip plan; the parent remains independently playable.
- The inherited endpoint appears once. A real synthetic FFmpeg integration fixture proves
  a 24-frame parent plus a 49-frame appended clip delivers 72 frames after dropping the
  appended clip's conditioned frame zero.
- File copying is not provenance. The compatibility slice refuses a parent whose video
  hash no longer matches its completed assembly record, then hard-links or copies the
  verified bytes into the child so later child use does not depend on a path outside its
  run folder.
- Deletion must respect lineage. A parent with direct extension children is protected;
  future SQLite reference counting will generalize this to shared assemblies/artifacts.
- The compatibility UI/backend is reusable evidence, not the final branch model. It proves
  endpoint extraction, appended-only rendering, assembly, history, and recursive lineage;
  dependency-driven staleness, future-reference approval, and cross-boundary retakes stay
  explicitly tracked for the full MVP.
- Real target-Mac evidence now validates both first-level and recursive extension at the
  1024×576, 24 fps, 49-frame rung. Frame arithmetic was exactly `parent + child - 1`
  (97+49-1=145, then 145+49-1=193), and endpoint re-extraction matched the stored PNG
  byte-for-byte. Synthetic proof remains useful, but cannot replace this engine-level gate.
- A controlled sibling comparison held parent endpoint, seed, camera, geometry, and runtime
  fixed while changing only the motion prompt. The moderate head turn remained coherent in
  sampled frames and did not increase the measured peak child RSS above 14.59 GB. This is a
  reusable prompt-sensitivity experiment pattern; normal-speed human review remains the
  creative approval boundary.
- Phase-weighted progress is genuine but coarse during high-resolution refinement. Renderer
  log carriage returns may reach the next step before the persisted UI counter updates. This
  is presentation latency, not a stalled render, and should be improved without fabricating
  interpolation.
- Polling run history must reconcile cards by stable job identity and persisted revision;
  replacing the whole container every three seconds resets native video playback, open
  disclosure panels, typed extension prompts, and selected controls. Completed cards now
  retain their DOM nodes indefinitely, while only genuinely changed active jobs are replaced
  and new jobs are inserted without rebuilding prior history.
