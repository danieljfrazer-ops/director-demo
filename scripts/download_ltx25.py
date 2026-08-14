#!/usr/bin/env python3
"""Download the official ComfyUI LTX-2.5 distilled INT8-ConvRot pack."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# The selected files occupy about 37 GiB. Leave room for partial downloads,
# metadata, and filesystem overhead. Generated media needs separate headroom.
REQUIRED_FREE_GIB = 45
FILES = [
    "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
    "vae/ltx-2.5-video-vae-bf16.safetensors",
    "vae/ltx-2.5-audio-vae-bf16.safetensors",
    "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="ComfyUI/models directory; the Hugging Face folder layout is preserved.",
    )
    parser.add_argument("--force-low-disk", action="store_true")
    args = parser.parse_args()

    hf = shutil.which("hf")
    if not hf:
        print("Blocked: install huggingface_hub so the `hf` command is available.", file=sys.stderr)
        return 2

    auth = run([hf, "auth", "whoami"])
    if auth.returncode != 0:
        print(
            "Blocked: run `hf auth login` and accept the LTX-2.5 model terms on Hugging Face.",
            file=sys.stderr,
        )
        return 2

    target_parent = args.target.resolve().parent
    target_parent.mkdir(parents=True, exist_ok=True)
    free_gib = shutil.disk_usage(target_parent).free / 1024**3
    if free_gib < REQUIRED_FREE_GIB and not args.force_low_disk:
        print(
            f"Blocked: {free_gib:.1f} GiB free; require {REQUIRED_FREE_GIB} GiB of headroom. "
            "Free disk space or choose a target on another volume.",
            file=sys.stderr,
        )
        return 2

    print("Downloading the ~37 GiB ComfyUI distilled INT8-ConvRot profile:")
    for filename in FILES:
        print(f"  {filename}")
    command = [hf, "download", "Lightricks/LTX-2.5", *FILES, "--local-dir", str(args.target)]
    return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
