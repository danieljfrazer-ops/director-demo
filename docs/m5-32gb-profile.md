# Provisional runtime profile: M5 MacBook Air, 32 GB

This machine is the product constraint. Resolution, duration, concurrency, and
backend choice must bend before the memory limit does.

## Confirmed blocker: stock ComfyUI INT8

The previously selected distilled INT8-ConvRot transformer and encoder are not a
viable stock Apple MPS route. On this exact Mac, PyTorch 2.13.0 exposes MPS but
`torch._int_mm` fails with `aten::_int_mm not currently implemented for MPS`.
Downloading or installing more of that pack cannot solve the missing kernel.

The repository downloader now refuses this profile on macOS. The incompatible INT8
transformer and encoder partials were purged on 15 August 2026. Completed components
and the BF16 VAE partial that remain reusable with strict LTX-2.5 were preserved.

## Candidate video runtimes

1. **Primary local spike — official LTX-2 Python pipeline.** Use the strict LTX-2.5
   distilled BF16 component set with `--offload disk`. Current official source has
   Apple Silicon device selection, per-block disk streaming, and `mps-sdpa>=0.2.0`
   as a platform dependency. That package calls Apple's fused MPSGraph attention
   through a prebuilt zero-copy bridge. This is a credible route, not a benchmark on
   this 32 GB machine.
2. **MVP fallback — smaller local scope.** The approved first MVP is local-only. If the
   primary local runtime fails a required gate, reduce duration, resolution, audio
   scope, or model/profile ambition and record the product limitation. Do not transmit
   project data to a hosted renderer as an MVP fallback.
3. **Rejected on the current stack — ComfyUI INT8-ConvRot video.** Reconsider only
   after a real MPS INT8 kernel lands and the exact probe passes.

ComfyUI remains eligible for lighter image/look-development workflows after its own
measured memory test. Image and video workers must never overlap.

LTX Desktop is supporting evidence only. Its current local Mac backend uses LTX-2.3,
not the required LTX-2.5 weights. Do not use its quality or timing as an LTX-2.5 result.

## Feasibility geometries

The official distilled pipeline is two-stage, so output width and height must be
divisible by 64; frame counts must be `8n + 1`. Use exact values rather than labels
such as “512p, three seconds”:

| Rung | Geometry at 24 fps | Purpose |
|---|---|---|
| A | 448 x 256, 49 frames (~2.04 s) | Prove a decoded I2V result and bounded memory. |
| B | 448 x 256, 73 frames (~3.04 s) | Measure duration scaling. |
| C | 448 x 256, 121 frames (~5.04 s) | Prove the nominal five-second shot. |
| D | 1024 x 576, 121 frames (~5.04 s) | Practical 16:9 local master candidate. |

Measured on 15 August 2026, the 1024 x 576 / 49-frame R1 control completed in 745.50
seconds with 14.49 GB peak child RSS, zero swap delta, and a valid synchronized output.
It was only 19.6% slower than the preceding small-raster run under disk streaming.
This proves the two-second high-resolution rung. The subsequent 1024 x 576 / 121-frame
R2 dialogue run completed in 1,092.06 seconds with 14.80 GB peak child RSS, zero swap
delta, valid synchronized media, and no thermal warning. R2 passes numeric safety and
usability; normal-speed user review confirms significantly less eye and mouth distortion
than the low-resolution baseline. It is the provisional local default, not a claim that
all dialogue faces or camera angles are artifact-free.

The stock strict LTX-2.5 distilled CLI generates synchronized audio and video together;
do not describe its first run as video-only. Score video validity first and record
audio validity separately. Its 2x latent stage is not a cheap post-process: the graph
re-runs the 22B transformer. The high-resolution result is the take requiring approval.

The provisional PoC generation default is now 1024 x 576, 121 frames, 24 fps, BF16
distilled weights, disk offload, and batch size one. It remains user-configurable and is
accepted provisionally after playback review. The delivery profile is
1280 x 720 at 24 fps, upscaled from an approved 1024 x 576 take. A 1920 x 1080 file may be offered later for playback compatibility,
but it is upscaled delivery—not native 1080p detail. Generate ten-second scenes as two
five-second shots or a controlled extension rather than a 241-frame first-pass render.

On 17 August 2026, three real 1024×576 / 49-frame stitched-scene extension runs completed
sequentially in 769–884 seconds. Peak child RSS was 13.77–14.59 GB, absolute swap deltas
ranged from 16.78 MB to 473.04 MB, no thermal warning was recorded, and every output was
conformant H.264/AAC media. First-level and recursive assemblies retained exactly one
shared boundary frame. This confirms the two-second rung as the safe extension and
feasibility-test default; it does not replace the five-second quality default for ordinary
shots. Detailed measurements and limitations remain in the private experiment archive.

## Runtime contract

1. Run one heavy worker at a time; close avoidable memory-heavy applications during
   measurement.
2. Record macOS version, PyTorch/runtime revision, model hashes, geometry, steps,
   attention backend, resident/compressed memory, peak swap, wall time, free disk,
   thermal state, and output validity.
3. The process that owns the model must also own cancellation and teardown. Process
   exit, not Python garbage collection, is the reliable unload boundary.
4. Require at least 100 GiB free before setup: the official component pack is roughly
   66 GiB, with additional environment, cache, logs, and output headroom. Disk offload
   makes storage performance part of inference performance; prefer internal storage
   or a fast APFS Thunderbolt/USB4 NVMe volume.
5. Do not promise 720p delivery until rung D and its upscale pass QC. Do not promise
   native 720p or 1080p on this machine without a separate measured result.

After installation, runtime preflight uses a configurable absolute free-space reserve
(`LTX_MINIMUM_FREE_GIB`, default 20 GiB), not a percentage of total volume capacity.
The measured sequential pipeline streams already-installed weights and produces small
media/provenance files; clip count increases elapsed time and output size but not the
number of simultaneously resident models. The former 15%-of-volume rule incorrectly
blocked a healthy 68.6 GiB-free system solely because its 460 GiB volume implied a
69.1 GiB threshold. Installation still requires the larger setup headroom above.

## Pass, pivot, and stop gates

- **Safety pass:** no macOS out-of-memory termination; peak swap at or below 8 GiB;
  memory returns to within 2 GiB of the pre-run baseline after worker exit.
- **Usability pass:** rung C completes in 30 minutes or less on AC power and produces
  a valid playable clip; rung D is measured separately before becoming the film
  profile. Record subsequent warm-run variation and thermal slowdown.
- **Quality pass:** the clip has no catastrophic identity, anatomy, motion, or decode
  failure when scored against the written shot intent.
- **Pivot:** if rung C cannot meet all three gates within ten focused working days,
  stop optimizing this local runtime path and rescope the MVP to a smaller local
  generation profile or a different local runtime. A hosted render adapter is a future
  product decision only, not the approved MVP fallback.
- **Stop immediately:** sustained swap growth, disk below the reserve, thermal or OS
  instability, or output corruption. Preserve logs and partial outputs for diagnosis.

These thresholds are provisional product choices. Change them explicitly in a dated
benchmark report rather than quietly redefining success.

Use the [Stage 0B runbook](stage-0b-runbook.md) and a private score sheet. The implementation source of truth is the official
[LTX-2 repository](https://github.com/Lightricks/LTX-2). LTX Desktop's
[Darwin runtime policy](https://github.com/Lightricks/LTX-Desktop/blob/main/backend/runtime_config/runtime_policy.py)
is comparative evidence for LTX-2.3 only.
