# Product brief

## Governing constraint

Prototype refinement is never an objective. Every retained change must become a
configurable/tested capability of the intended application or produce decision-quality
evidence that changes architecture, defaults, quality gates, or roadmap. Generated media
are immutable fixtures; repairs are reversible data and generic workflow behavior.

## Problem

Turning a story into generated video is currently a fragile sequence of prompt
writing, asset hunting, model swapping, manual naming, and editing. The greatest
failure is not single-shot beauty; it is loss of identity, state, intent, and audio
continuity across an editable sequence.

## Product promise

Director Demo translates source material and user-owned references into a visual,
editable production plan. Once approved, it executes the plan sequentially through
measured local engines, preserves provenance, exposes failures clearly, and assembles
the accepted takes into a film. The first MVP is fully local and has no cloud fallback.

The approved first product slice is a single apparently continuous 2–30 second scene.
Engine constraints may require several internal render clips, but those are replaceable
clip slots rather than separate editorial shots. A selected stitched scene can be
extended non-destructively in further 2–30 second increments from its exact retained
final frame, so its accumulated duration may grow while every parent assembly remains
immutable. See the
[MVP product specification](mvp-single-shot-spec.md).

## Primary user journey

1. Create a project and import synopsis/script plus optional image, video, voice,
   SFX, and music references.
2. Review the extracted cast, locations, props, rights/consent notes, and style bible.
3. Generate a shot plan and low-cost storyboard.
4. Edit, reorder, lock, or regenerate boards and prompts; approve a cut.
5. Render draft clips sequentially, compare takes, and approve selections.
6. Render/fix audio, transitions, subtitles, color, and loudness.
7. Export the film plus a reproducibility manifest.

## Non-goals for the first MVP

- Feature-length projects, multi-user cloud collaboration, training foundation
  models, a full nonlinear editor, or guaranteed actor likeness.
- Any use of a person's voice or likeness without recorded consent is prohibited,
  not merely deferred.
- Native 720p/1080p generation as the default on a 32 GB Mac. The PoC target is
  1024 x 576 at 24 fps, delivered at 1280 x 720 after a separate approved upscale.
- Multiple scenes, a full screenplay workflow, a nonlinear editor, and cloud inference.
