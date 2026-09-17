# GitHub and Cloudflare publication

The public release has two deliberately separate surfaces:

1. GitHub contains the local pipeline, documentation, tests, and the static recorded
   workflow demonstration.
2. Cloudflare Pages serves the exported static demonstration and its five approved
   playback files.

The hosted page never runs a model. Local generation needs Python, the pinned LTX
runtime, FFmpeg, local model weights, filesystem storage, and a resource-aware queue.

## Privacy boundary

The checked-in `web/public/showcase/manifest.json` is a public read model. It contains
playback URLs, file hashes and sizes, media information, the approved original starting
frame and accompanying public prompt for each selected clip, safe settings/engine
fields, public parent lineage, structured review state, rights state, and generic
limitations. It intentionally excludes source paths, job/run IDs, timestamps, sidecars,
reference identifiers, host metrics, and free-text reviews.

The original clips and the private selection record stay under ignored `outputs/`.
Only the five selected public copies, their starting frames, and their accompanying
prompts are published. Contributors can run the pipeline with their own inputs instead.

The package can only be rebuilt by a maintainer who has both original outputs and the
ignored selection record:

```bash
python scripts/package_showcase.py --selection outputs/publication/selection.json
pytest tests/test_showcase_package.py
```

The packager verifies source hashes and size, refuses repository-path escapes and
conflicting copies, and permits only nested public metadata allowlists. A selection may
provide a non-empty `public_prompt` override when the original run prompt must remain
private; the original prompt stays in the ignored run record and is never emitted.

## Cloudflare Pages

Use this configuration:

- Root directory: `web`
- Build command: `npm ci && npm test`
- Build output directory: `dist/client`

The current five MP4s are each below the Pages static-asset limit, so the release uses
Pages only: no R2, Worker, Pages Function, database, or hosted model endpoint.
Re-check Cloudflare’s current limits and pricing before publishing.

## Release gates

Before making the repository or Pages project public:

- confirm that every published asset remains covered by its recorded owner confirmation;
- inspect the full Git diff and a current plus history secret scan;
- run `ruff check .`, `pytest`, `cd web && npm run lint`, and `cd web && npm test`;
- confirm the five public files and starting frames match their expected SHA-256 values; and
- preview the static build and play/seek every video.

Technical validity, creative approval, and delivery approval remain separate. A green
build does not settle human-review gates. The MIT licence applies to software and
documentation only; the showcase media, starting frames, published prompts, model
weights, and third-party dependencies are excluded. Publication consent is not general
permission to reuse those excluded materials.
