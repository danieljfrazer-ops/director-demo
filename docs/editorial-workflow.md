# Manifest-driven editorial workflow

## Purpose and carry-over

This slice proves a reusable application capability, not a repair script for the first
film. It represents immutable takes, structured review, explicit selection, reversible
edit decisions, approved conditioning boundaries, cut revisions, normalized assembly,
dependency freshness, and exact delivery provenance as versioned JSON.

The CLI and local review UI consume the same contract. A later API/SQLite layer may
index it, but must not redefine its semantics.

## Documents

### Editorial project

An `EditorialProject` owns ordered shots and immutable takes. Each take records its
artifact hash, source run, optional parent/reason, optional approved conditioning
boundary, and separate technical/creative review. A selected take must technically pass
and be either `approved` or `approved_with_edit`.

`approved_with_edit` is intentionally strict: a cut cannot use that take without an
explicit trim or fade. This prevents a UI selection from silently ignoring a known
source defect.

### Cut manifest

A `CutManifest` owns ordered selected-take references plus reversible source in/out and
fade decisions. Delivery resolution, frame rate, codecs, quality settings, and whether
the resolution is native/normalized/upscaled are explicit data.

Edits may address boundaries in seconds or by integer frame. Frame-addressed out-points
are explicitly inclusive, removing FFmpeg's otherwise easy-to-miss exclusive-end
ambiguity. A continuation can retain the exact source boundary frame and start its child
at frame 1 so the shared frame appears once. Each clip also declares its transition to
the next: a hard cut or a frame-counted dissolve with equal-power audio crossfade.

Changing a selected take, source hash, conditioning-boundary hash, edit decision, cut
revision, or delivery profile changes the dependency digest. Review prose may change
without forcing a media render; the assembly record reports that provenance metadata is
newer while correctly distinguishing media freshness.

### Assembly record

The generic FFmpeg assembler:

1. resolves project-relative paths inside the declared artifact root;
2. verifies take and conditioning-boundary hashes;
3. probes video and audio before work;
4. applies time- or frame-addressed trims, fades, and declared overlap transitions
   without changing source files;
5. normalizes video, audio, dimensions, frame rate, pixel format, and sample rate;
6. refuses to overwrite any output;
7. validates the completed delivery with `ffprobe`;
8. hashes the output and every dependency; and
9. snapshots the exact project and cut manifests beside the delivery.

The snapshots are the historical authority. A mutable project “head” can evolve without
destroying the ability to reproduce which bytes produced an older delivery.

## Commands

```bash
director-demo editorial-schemas
director-demo validate-cut data/my-project/editorial-project.json \
  data/my-project/cut.json
director-demo assemble-cut data/my-project/editorial-project.json \
  data/my-project/cut.json \
  outputs/my-project/cuts/recovery.mp4
director-demo check-assembly data/my-project/editorial-project.json \
  data/my-project/cut.json \
  outputs/my-project/cuts/recovery.assembly.json
director-demo export-editorial
```

The local app’s review surface shows selected takes,
structured quality dimensions, retained source defects, conditioning provenance, exact
edit decisions, cut revision, delivery, and dependency state. It is currently read-only;
future write actions must persist through atomic domain operations, not browser-only
state.

The domain already exposes atomic operations that a future API/UI will call:

```bash
director-demo register-take PROJECT.json SHOT_ID TAKE.json
director-demo review-take PROJECT.json SHOT_ID TAKE_ID REVIEW.json
director-demo select-take PROJECT.json SHOT_ID [TAKE_ID]
```

Registration never changes selection. A take cannot be selected until technical and
creative approval pass, and a selected take cannot be rejected until selection is
explicitly cleared or replaced. These are domain invariants rather than UI conventions.

## First integration evidence

The existing three-shot film was imported only as fixture data. Its source clips and
hashes were not changed. Shot 3 is `approved_with_edit` because its uncontrolled turn
causes a small oblique-face collapse near the end.

Cut revision 2 stores an out-point of 2.55 seconds and a 0.30-second fade on that take.
The generic assembler produced a 9.67-second 1024 x 576 / 24 fps H.264/AAC delivery,
SHA-256 `47ed5e92d2fcd7bc9567754a9c35b61c9be664ab991ddb5a62729c691b2d6720`.
Its dependency digest is
`acd5112d49b48ae0c58f40f3040de85f977629a29edf6dfb67bcad09f6547fe1`.
Both media and provenance freshness pass against the current manifests.

This is evidence that editorial recovery is technically reusable. It does not erase or
reclassify the original generator defect, which remains visible in the source review.

The second integration path conditions a new two-second continuation on the approved
2.00-second boundary of shot 3. It is modeled as shot 4 with cross-shot parent lineage,
not as an overwrite or an unexplained replacement. Cut revision 3 retains the original
through that boundary and then appends the continuation with a 0.30-second terminal
fade. The generic assembler produced an 11.125-second 1024 x 576 / 24 fps H.264/AAC
review delivery, SHA-256
`fb0759d6d64a9cb746c0297d2ddf493793a250067c37f8aaeaecdea506221f75`.
Its dependency digest is
`98a78b0cd3f2b20748a695f32d1938a87404e84fb8ea7e89c4e939824cb96338`;
media and provenance freshness both pass.

Early project snapshots used an embedded conditioning-boundary shape. The current
loader migrates those documents only in memory and leaves their bytes/hashes unchanged.
This is a compatibility rule: immutable evidence is never rewritten to imitate a newer
schema.
