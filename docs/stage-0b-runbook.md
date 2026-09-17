# Local LTX-2.5 setup and first render

This runbook installs the native LTX runtime used by Director Demo's local clip maker. It is for Apple Silicon macOS and the measured M5 / 32 GB profile—not a promise that every Mac will have the same speed, quality, or memory behaviour. Run one heavy LTX job at a time.

The app uses Lightricks' official Python implementation, not ComfyUI or the hosted showcase. The runtime is pinned to `fd4ded7f2d88d3da713abcdd4ad41ecc4a9314ca`; the model is `Lightricks/LTX-2.5` Fast distilled BF16 with disk offload. The model download is approximately 66 GiB. Start with **at least 100 GiB free** for model files, the Hugging Face cache, the isolated runtime, outputs, and working headroom.

## Before you start

Install FFmpeg and `uv`:

```bash
brew install ffmpeg uv
```

You also need a Hugging Face account that has accepted the gated LTX-2.5 terms. Install and authenticate the Hugging Face CLI. It prompts interactively: never paste a token into this repository or commit it.

```bash
uv tool install 'huggingface_hub[cli]'
hf auth login
```

Confirm access before downloading:

- [LTX-2.5 model access](https://huggingface.co/Lightricks/LTX-2.5)
- [Official LTX-2 runtime](https://github.com/Lightricks/LTX-2)

Create the Director Demo application environment as described in the [README](../README.md) before using `director-demo` or `director-demo-app`. The LTX runtime gets its own environment and must never be installed into Director Demo's `.venv`.

## 1. Pin the isolated runtime

Start at the root of a clone. Save its absolute path *before* entering the LTX repository; every project path below is derived from that saved value.

```bash
DIRECTOR_PROJECT_ROOT="$(pwd -P)"
DIRECTOR_RUNTIME_ROOT="$DIRECTOR_PROJECT_ROOT/.runtime"
mkdir -p "$DIRECTOR_RUNTIME_ROOT"
(
  cd "$DIRECTOR_RUNTIME_ROOT"
  git clone https://github.com/Lightricks/LTX-2.git LTX-2
  cd LTX-2
  git checkout fd4ded7f2d88d3da713abcdd4ad41ecc4a9314ca
  uv venv --python /opt/homebrew/bin/python3.12 .venv --clear
  .venv/bin/python -m ensurepip --upgrade
  .venv/bin/python -m pip install \
    'torch==2.13.0' 'torchaudio==2.11.0' 'torchvision==0.28.0'
  .venv/bin/python -m pip install -e packages/ltx-core -e packages/ltx-pipelines
)
```

The parenthesised block returns you to the Director Demo root. Do not derive the project root after changing into `.runtime/LTX-2`: `git rev-parse --show-toplevel` there identifies the third-party runtime, not Director Demo.

## 2. Download the required model components

Use the project's model directory. The app's default `LTX_MODELS_ROOT=models` and preflight expect this exact layout.

```bash
DIRECTOR_PROJECT_ROOT="$(pwd -P)"
DIRECTOR_MODEL_ROOT="$DIRECTOR_PROJECT_ROOT/models"
mkdir -p "$DIRECTOR_MODEL_ROOT"
hf download Lightricks/LTX-2.5 \
  diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors \
  text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
  vae/ltx-2.5-video-vae-conv-bf16.safetensors \
  vae/ltx-2.5-audio-vae-bf16.safetensors \
  latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
  --local-dir "$DIRECTOR_MODEL_ROOT"
find "$DIRECTOR_MODEL_ROOT" -type f -name '*.safetensors' \
  -exec shasum -a 256 {} + | sort -k2 > "$DIRECTOR_MODEL_ROOT/SHA256SUMS"
```

The required paths are:

```text
models/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors
models/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors
models/vae/ltx-2.5-video-vae-conv-bf16.safetensors
models/vae/ltx-2.5-audio-vae-bf16.safetensors
models/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors
```

Weights, hashes, authentication caches, and `.runtime/` are local setup artefacts. Do not commit them.

## 3. Preflight the actual application configuration

Return to the Director Demo root, activate its application environment, then check the pinned runtime, model paths, FFprobe, disk reserve, MPS, and entrypoint options:

```bash
DIRECTOR_PROJECT_ROOT="$(pwd -P)"
cd "$DIRECTOR_PROJECT_ROOT"
source .venv/bin/activate
director-demo ltx-preflight
```

Success ends with `ready`. Do not render until it does. Preflight requires Apple MPS and the zero-copy `mpsgraph_zc` attention backend rather than accepting a memory-leaking fallback.

## 4. Make a two-second first render

Put your own source image and plain-text direction file in ignored `data/`. Begin with restrained motion, a stable camera, and simple sound intent.

```bash
mkdir -p data/my-project outputs/my-project
# Copy your image to data/my-project/anchor.png and write direction.txt there.
director-demo render-ltx \
  data/my-project/anchor.png \
  data/my-project/direction.txt \
  outputs/my-project/first-2-seconds.mp4 \
  --width 448 --height 256 --frames 49 --fps 24 --seed 42
```

At 24 fps, 49 frames is the legal LTX two-second starting rung (`8n + 1`). The command refuses to overwrite an existing output and writes a run sidecar and process log beside the MP4. Validate it with:

```bash
ffprobe -v error -show_format -show_streams outputs/my-project/first-2-seconds.mp4
```

If it passes, increase progressively: 73 and then 121 frames at 448×256, before trying the application default of 1024×576 at 121 frames. The measured five-second default can take about 18 minutes per clip on the target Mac; timing and creative quality vary by machine and prompt.

## 5. Use the local UI and extend a scene

With preflight still reporting ready:

```bash
director-demo-app
```

Visit `http://127.0.0.1:8765`. Upload one to eight PNG, JPEG, or WebP references, set their timeline positions, write direction that may refer to an image ID such as `@start-frame`, choose duration and seed, then queue the generation. Results live in ignored `outputs/app-jobs/`.

When a stitched scene is complete, open **Extend scene from its exact final frame**, enter continuation direction, and queue it. The parent assembly remains immutable; the child begins from the parent's retained endpoint and records lineage. Local rendering and extension do **not** require an OpenAI key. The optional planning integration is separate and may use an OpenAI-compatible local or remote service.

## Common failures

| Symptom | What to check |
|---|---|
| `hf download` is denied | Accept the LTX-2.5 gated terms, run `hf auth login` again, then retry. |
| `ffprobe` missing | Install FFmpeg and confirm `ffprobe -version` is on `PATH`. |
| Runtime or Python environment missing | Re-run step 1 from the Director Demo root; `LTX_RUNTIME_ROOT` defaults to `.runtime/LTX-2`. |
| Model files missing | Re-run step 2 without changing `--local-dir`; files must be under the listed `models/` paths. |
| MPS/preflight fails | Confirm Apple Silicon macOS, the pinned runtime commit, and runtime dependencies. Do not force a fallback backend. |
| Disk is low or swap grows | Stop the render, free space, and return to the 49-frame rung. Do not run concurrent model jobs. |
| Output already exists | Choose a new output filename; takes are intentionally immutable. |
| Render fails after preflight | Read the adjacent process log and run sidecar; preserve them for diagnosis instead of overwriting the attempt. |

The hosted [recorded showcase](https://director-demo-73z.pages.dev) is independent of this setup: it is static playback only and cannot access your local runtime or files.
