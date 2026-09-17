# Roadmap: evidence-led single-shot MVP

The immediate goal is now to make private local clips with LTX Desktop and test whether
any custom DirectorDemo layer is still needed. It supersedes the earlier decision to
build a separate single-shot application MVP: freeze overlapping application work while
real clip-making tests whether provenance, continuity, or automation gaps justify a
thin sidecar or narrow Apache-2.0 fork.

Every milestone is also subject to [product and engineering governance](governance.md):
work must become a configurable/tested full-app capability or produce consequential
decision evidence. A prototype film is an integration fixture, never a polishing goal.

## Portfolio publication slice

- [x] Select a small, rights-tracked recorded package from immutable completed runs.
- [x] Add deterministic hash verification, privacy-filtered provenance, and static
  playback with explicit technical/creative/delivery review boundaries.
- [x] Validate a Cloudflare Pages-only build with no runtime backend or R2 dependency.
- [ ] Confirm rights for every selected video and conditioning reference.
- [ ] Choose and add the code licence, then complete GitHub and `pages.dev` release
  smoke tests described in [publication.md](publication.md).

## Stage 0A — runtime triage (complete)

- Confirm Hugging Face access and available storage.
- Probe the proposed ComfyUI INT8-ConvRot execution primitive on the target Mac.
- Preserve evidence and stop incompatible downloads.

**Result:** failed by design. PyTorch 2.13.0 MPS does not implement `aten::_int_mm`.
The stock ComfyUI INT8 route is rejected, without rejecting LTX-2.5 itself.

## Stage 0B — choose a render engine

1. Follow the [Stage 0B runbook](stage-0b-runbook.md) against a pinned official
   LTX-2 revision and the strict LTX-2.5 BF16 distilled component set.
2. Run its MPS fused-attention and disk-streaming path through rungs A–C in the
   [M5 profile](m5-32gb-profile.md), then test the 1024 x 576 rung D.
3. Capture a repeatable benchmark report including hashes, RAM, swap, time, thermals,
   disk, and output validity.
4. The former cloud-fallback proposal is rejected for the approved MVP. If a required
   local gate fails, record the blocker and reconsider local model/profile scope rather
   than transmitting project data.
5. Separately prove one lightweight anchor-image workflow and full worker teardown.
6. Treat facial integrity as an independent exit gate: complete the controlled
   no-dialogue, timing, and resolution ablations before selecting a default profile.

**Exit:** one conditioned 1024 x 576, 121-frame, 24 fps clip passes the numeric safety,
usability, facial-integrity, and quality gates. The chosen engine and fallback are
recorded in an ADR. R2 has passed numeric safety and usability at the target geometry;
normal-speed user review confirms materially less eye and mouth distortion, so it is
the provisional local default. Rung A remains a documented low-resolution failure;
speech-face defects remain tracked rather than declared eliminated.

## Stage 0.5 — continuity spike

Hand-write two shots of one character in one location. Build a small canonical
reference pack, generate two anchor boards and clips, and repeat for ten independently
seeded pairs. Score face, body, wardrobe, props, location, and screen direction using
the same checklist each time.

**Exit:** the character is recognizably the same in at least 7 of 10 pairs, with zero
unexplained wardrobe or character substitutions in passing pairs. Otherwise redesign
the reference/conditioning approach before building planning infrastructure.

## PoC 1 — inspectable plan

Use the existing typed shot plan and director CLI on three representative scripts.
Add a real local-compatible provider and permit manual JSON edits. The legacy OpenAI
bootstrap is excluded from the MVP and must remain clearly labelled if retained for
historical CLI compatibility. Static prompts own appearance and setting; motion prompts contain
only changing state, action, camera, timing, dialogue, and sound.

**Exit:** all three plans render through the selected PoC pipeline without emergency
prompt edits after approval; any pre-render edits are counted and reported.

## PoC 2 — one approved shot end to end

Add a minimal `render` command, one hand-pinned engine workflow/configuration, asset
checksums, explicit semantic bindings, `ffprobe` validation, hash-named artifacts,
and one append-only JSONL event log. Do not add SQLite or a web UI yet.

**Exit:** script -> board -> approval -> I2V take -> validated artifact works from a
fresh project folder, and an interrupted run resumes without duplicating a valid take.

## PoC 3 — tiny continuous film

Create 3–5 shots and 2–3 takes per shot. Use character/location bibles, approved
anchors, an explicit continuity checklist, and normalized FFmpeg assembly. Record
manual interventions instead of hiding them behind automation claims.

**Exit:** a 15–25 second H.264 film has zero identity substitutions, zero unexplained
wardrobe/location breaks, at most one non-story-breaking motion artifact, and no
invalid media or broken cut audio. A cold reviewer—not the author—scores the checklist.

**Current evidence:** a 10.15-second three-clip technical micro-film now exists and
passes codec/audio/final-file validation. Its R2-to-outro boundary uses real last-frame
conditioning and is visually close. User playback confirms much better eye/mouth
quality overall, but the outro overshoots into a body turn/exit and its small oblique
face collapses near the ending. Reject/trim that take and render a constrained outro
before the cold-viewer taste gate.

The manifest-driven editorial slice produces two independently reviewable strategies
without changing source takes. The 9.67-second recovery cut proves reversible trim/fade
recovery. A second 11.125-second review cut retains shot 3 through its approved 2.00-second
boundary and appends a lineage-linked 49-frame constrained continuation. The continuation
completed in 11m59s at 14.31 GB peak RSS; its first frame scores 0.992690 SSIM against
the boundary and frame review shows no terminal side-profile collapse. User normal-speed
playback is still required before creative approval. PoC 3 remains open because it is
shorter than 15 seconds, has only one take for most shots, has not passed the ten-pair
identity spike, and has not passed a cold-viewer taste gate.

Normal-speed user review rejects both cuts as a flowing scene. Multiple joins visibly
reset the woman's pose, expression, framing, and motion, which dominates attention before
facial-detail assessment. The lack of newly noticed eye/mouth distortion is encouraging
but does not rescue the film-level result. Before the ten-pair identity study or a longer
film, run a bounded two-clip adjacency spike designed as one continuous action. Its exit
gate is perceptual continuity at normal speed, not merely a close boundary frame.

That bounded C1 experiment is now technically complete. One new 49-frame child was
conditioned on the exact final decoded frame of its parent. A 4.04-second hard join and
3.83-second six-frame dissolve/audio-crossfade variant both pass delivery and freshness
checks. The actual displayed hard seam scores 0.967636 SSIM, with motion windows 0.489
before and 0.414 after; the overlap reduces the independent-room-tone sample jump by
roughly 590x. These measurements justify user review, not gate closure.

## Demo taste gate and definition of done

Show the film without explanation to at least three people who did not build it. Ask:

1. How many recurring characters did you see?
2. Did any cut make the character, place, or story hard to follow?
3. Would you voluntarily watch another 60 seconds in this style?

The demo passes when at least two of three identify the intended recurring characters,
report no story-breaking cut, and answer yes to question 3. Publish a short findings
report with render times, continuity hit rate, interventions, defects, and recommendation.

**DirectorDemo is complete at this point.** A failed taste gate triggers a creative
workflow/conditioning redesign, not UI work.

## Approved first MVP — local single-shot scene director

This implementation is paused behind the LTX Desktop adoption checkpoint. Resume only
for an observed private-workflow gap that configuration, editor interchange, a thin
sidecar/API integration, or a narrow fork cannot satisfy.

Deliver in the staged order defined by the
[implementation plan](mvp-single-shot-implementation-plan.md):

1. Select and measure the local prompt, storyboard, segmentation, and anchor adapters.
2. Add the durable revision/provenance model, SQLite, artifact store, one-slot queue,
   FastAPI/SSE service, and backwards-compatible history import.
3. Add scene setup, multi-role references, character/background preparation, source
   continuation, and deterministic 2–30 second clip planning.
4. Add local prompt optimization, visible approval, storyboards, and target-style
   conditioning approval.
5. Add progressive LTX rendering, exact-boundary assembly, source prepend, truthful
   progress/cancellation/restart, and calibrated preflight.
6. Add contiguous generated-range retakes, immutable alternatives, promotion,
   reassembly, comparison, and rollback.
7. Add recursive non-destructive scene extension from the exact retained endpoint of a
   selected stitched assembly, with appended-only generation and dependency staleness.
8. Pass network-denied, target-Mac, recovery, security, accessibility, and normal-speed
   creative quality gates.

The [product specification](mvp-single-shot-spec.md) and
[technical design](mvp-single-shot-technical-design.md) are normative. Multiple scenes,
a nonlinear editor, and cloud adapters remain post-MVP. Before each model investment,
re-evaluate current local runtimes rather than preserving an obsolete backend choice.
