# Director Demo

Director Demo is a local-first proof of concept for making short, image-conditioned
video clips. Each render is immutable, and a completed scene can be extended from its
exact final frame.

This repository has two deliberately separate experiences:

- **Recorded showcase (`web/`)** — a static Cloudflare Pages demonstration at
  [director-demo-73z.pages.dev](https://director-demo-73z.pages.dev). It plays selected
  clips, starting frames, and recorded prompts but cannot run a model.
- **Local clip maker (`src/director_demo/`)** — the Python application that can render
  and extend clips on your own Mac after the LTX runtime, model files, and FFmpeg are
  installed. Cloudflare never renders media.

## Clone and run the recorded showcase

Requires Node.js 22.13 or newer:

```bash
git clone https://github.com/danieljfrazer-ops/director-demo.git
cd director-demo
cd web
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. `npm test` produces the static export in
`web/dist/client`, which is suitable for Cloudflare Pages. The showcase uses only
static assets; it needs no Worker, R2 bucket, database, API key, or hosted model.

The five checked-in videos are recorded reference outputs. Each selected clip includes
its recorded starting frame and generation prompt. Source paths, job records,
timestamps, compiled prompts, and unselected inputs remain private. To exercise the
pipeline, run it locally with your own image inputs and direction text.

## Run the local clip maker

Local rendering is a measured Apple Silicon M5 / 32 GB profile, not a performance or
quality guarantee for every machine. It runs one heavy job at a time. Install Python
3.12+, FFmpeg (including `ffprobe`), and the project environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
ffmpeg -version
ffprobe -version
```

On macOS, use `brew install ffmpeg` if either command is missing. `.env` is optional
for local LTX rendering; it only changes defaults and integration settings. A local
render or extension does **not** require an OpenAI key. The separate optional planning
integration can use an OpenAI-compatible endpoint, and should only be configured after
reviewing what it sends.

Generation requires the pinned LTX runtime and local model files described in the
[local LTX setup and first-render runbook](docs/stage-0b-runbook.md). It installs the
runtime in ignored `.runtime/LTX-2`, downloads gated weights to ignored `models/`, runs
preflight, and makes a small first render.

When `director-demo ltx-preflight` ends with `ready`, launch the local UI from the
repository root with `.venv` active:

```bash
director-demo-app
```

Open `http://127.0.0.1:8765`. Upload your own PNG, JPEG, or WebP image, enter
motion/camera/action/sound direction, choose a short duration and seed, and queue a
local render. When a scene is complete, select **Extend scene from its exact final
frame** to create a linked continuation while preserving the original clip.

Private project assets, generated media, logs, model weights, environment files, and
private publication records are ignored. Put any inputs you want to render under
`data/` or upload them through the local UI.

## Verification

```bash
ruff check .
pytest
cd web
npm run lint
npm test
```

## Publishing

Deploy `web/dist/client` to Cloudflare Pages after the web checks pass. The selected
MP4s are below Pages’ per-file static-asset limit, so R2 is unnecessary. Review
[publication guidance](docs/publication.md), the media-rights checklist, and
[LICENSE](LICENSE) before redistributing code or media.

## Repository map

```text
src/director_demo/       Local Python application and rendering pipeline
tests/                   Fast tests without model downloads
docs/                    Architecture, evidence, and operating notes
scripts/                 Local utilities, including the private showcase packager
data/                    User inputs and runtime projects (ignored)
models/                  Local weights (ignored)
.runtime/                Pinned third-party runtime (ignored)
outputs/                 Generated media and private evidence (ignored)
web/                     Static recorded workflow demonstration
examples/showcase/       Public rights and package documentation
```

Generated media, reference inputs, model weights, and dependencies have separate
licences and usage terms.
