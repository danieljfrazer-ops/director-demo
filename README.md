# Director Demo

Director Demo is a local-first **AI Film Director**: it turns a synopsis, script,
and optional reference media into an inspectable storyboard, then renders and
assembles a continuous short film.

The product is deliberately not a one-click black box. The storyboard is the
human approval boundary: every shot, prompt, line, reference, continuity rule,
seed, and expected output remains visible and editable before expensive media
generation begins.

## Product principles

- **Local-first and private by default.** Cloud LLMs and render APIs are optional
  adapters, clearly disclosed at the point of use.
- **Continuity is data, not prompt folklore.** Characters, wardrobe, locations,
  props, screen direction, audio identity, and shot-to-shot state are versioned.
- **Reproducible renders.** Every artifact records its inputs, workflow version,
  model/checkpoint, seed, parameters, and parent artifacts.
- **Sequential heavy-model execution.** A single resource-aware render queue
  unloads models between stages on 32 GB Apple Silicon.
- **Review before render.** Users can regenerate or lock individual boards and
  shots without invalidating unrelated approved work.
- **Replaceable engines.** LLM, image, video, audio, and assembly backends sit
  behind adapters; ComfyUI is one engine, not the domain model.

## Repository map

```text
src/director_demo/       Python domain and integration modules
tests/                   Fast unit tests (no model download required)
workflows/               Versioned ComfyUI API workflow templates
docs/                    Product, architecture, roadmap, and backlog
scripts/                 Preflighted local setup utilities
data/                    Runtime projects/assets (ignored)
models/                  Local weights (ignored)
outputs/                 Generated media (ignored)
```

## Quick start

Prerequisites: Python 3.12+, `ffmpeg`, and (for rendering) a separately running
ComfyUI instance.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest
```

Create a shot plan:

```bash
director-demo plan path/to/script.txt --out data/example/shot-plan.json
```

Stitch numbered clips such as `0001.mp4`, `0002.mp4`:

```bash
director-demo stitch outputs/clips outputs/short_film.mp4
```

The model installer intentionally refuses to fill the disk or start without
Hugging Face authentication:

```bash
python scripts/download_ltx25.py --target /path/to/ComfyUI/models
```

The installer selects the official LTX-2.5 distilled INT8-ConvRot transformer
and matching INT8-ConvRot Gemma encoder. It deliberately does not download the
BF16 transformer/encoder or optional prompt-enhancer model.

## Current status

This is the initial technical baseline, not yet a usable end-to-end UI. See the
[architecture review](docs/architecture.md), [roadmap](docs/roadmap.md), and
[backlog](docs/backlog.md) for the agreed build sequence. The fixed target-machine
contract is documented in [the M5/32 GB runtime profile](docs/m5-32gb-profile.md).

This repository is private and currently unlicensed; all rights are reserved.
