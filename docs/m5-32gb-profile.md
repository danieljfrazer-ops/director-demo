# Fixed runtime profile: M5 MacBook Air, 32 GB

This hardware is a product constraint, not an optional deployment target. Features
must degrade resolution, duration, or throughput before they exceed its memory.

## Selected LTX-2.5 files

The correct profile is both **step-distilled** and **weight-quantized**:

| Component | Official file | Approx. disk size |
|---|---|---:|
| Video/audio transformer | `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | 20.03 GiB |
| Gemma 4 encoder + projection | `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | 14.32 GiB |
| Diffusion video VAE | `ltx-2.5-video-vae-bf16.safetensors` | 1.37 GiB |
| Audio VAE | `ltx-2.5-audio-vae-bf16.safetensors` | 0.34 GiB |
| 2x latent spatial upscaler | `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | 0.93 GiB |

Total: approximately **37 GiB**, before ComfyUI, Python, generated media, and caches.
Keep at least 45 GiB free for installation and substantially more for project media.

Do not use either `*-bf16` transformer or encoder. Distillation alone reduces steps;
the BF16 distilled transformer is the same approximately 39.13 GiB as the BF16 dev
transformer. Do not use the NVFP4 transformer: it targets NVIDIA FP4 execution and is
not the Apple MPS profile. The INT8-ConvRot files are explicitly ComfyUI-only.

The optional `gemma4_e2b_it_bf16.safetensors` prompt enhancer is omitted. The app's
director already produces detailed prompts, saving another approximately 9.57 GiB of
disk and avoiding another large model lifecycle.

## Runtime contract

1. Only one heavy generation job may execute.
2. Produce text embeddings, then unload/offload Gemma before loading/denoising LTX.
3. Unload the transformer before high-memory VAE decode or the next image model.
4. Start feasibility tests at 512p, 24 fps, and 3 seconds. Increase one dimension at
   a time. Generate low and apply the included 2x latent upscaler for accepted takes.
5. Video-only is the first gate. Synchronized audio is a separate gate because MPS
   audio-VAE paths have historically had different failure modes.
6. Record free RAM, peak resident memory, swap, wall time, output resolution/FPS,
   and thermal throttling for every benchmark.
7. If memory pressure becomes critical, cancel cleanly; do not let macOS enter an
   unbounded swap-thrash state.

## ComfyUI baseline

- Use current ComfyUI with its native LTX-2.5 T2V/I2V/FLF2V templates.
- Use the standard `UNETLoader` with `weight_dtype=default`; quantization metadata is
  carried by the checkpoint.
- Do not use `--highvram` or `--gpu-only`.
- Test ComfyUI defaults first. Add aggressive offload settings only when telemetry
  demonstrates a need; flags change as DynamicVRAM evolves.
- Pin the exact ComfyUI release and exported API workflow after the first successful
  M5 run.

## Acceptance ladder

1. 512p, 3-second I2V, video only.
2. 512p, 5-second I2V, video only.
3. 512p, 5-second I2V with synchronized audio.
4. 720p-equivalent output through latent upscaling.
5. Longer duration or higher native resolution only if the preceding measurement has
   safe memory and thermal headroom.
