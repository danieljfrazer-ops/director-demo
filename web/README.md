# Director Demo web showcase

This static app demonstrates the local clip creation and extension workflow. `/` and
`/studio` render the same recorded demonstration. They play exactly five curated MP4s
and do not connect to a model service, a local machine, or any backend.

## Develop and build

```bash
npm ci
npm run dev
npm run lint
npm test
```

`npm test` writes a static export to `dist/client`. Deploy that directory to
Cloudflare Pages with `web` as the root directory and `npm ci && npm test` as the
build command.

## Privacy boundary

`public/showcase/manifest.json` contains only playback metadata, hashes and sizes,
the five selected prompts and starting frames, safe settings and engine fields, public
lineage, structured review state, rights state, and generic limitations. Source paths,
run IDs, timestamps, sidecars, compiled prompts, unselected inputs, and free-text
reviews are private and never appear in the hosted app. The repository's MIT licence
does not apply to showcase media, starting frames, prompts, model weights, or
third-party dependencies; publication consent is not general reuse permission.

Maintainers who have the ignored original outputs can rebuild the public package with:

```bash
cd ..
python scripts/package_showcase.py --selection outputs/publication/selection.json
pytest tests/test_showcase_package.py
```

The private selection record and originals are intentionally not part of a fresh clone;
the existing public package remains buildable and playable without them.
