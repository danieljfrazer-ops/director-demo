from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import resource
import select
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

from director_demo.runs import RunRecord, sha256_path, write_run_record

PINNED_LTX_COMMIT = "fd4ded7f2d88d3da713abcdd4ad41ecc4a9314ca"


class LtxError(RuntimeError):
    """Raised when the native LTX runtime cannot safely render or validate a take."""


class LtxCancelled(LtxError):
    """Raised after a requested render cancellation has stopped the child process."""


@dataclass(frozen=True)
class LtxProgress:
    """A renderer-observed milestone or genuine LTX step counter."""

    phase: str
    message: str
    current: int | None = None
    total: int | None = None


class LtxProgressParser:
    """Turn the pinned runtime's log stream into stable, typed progress events."""

    _step_pattern = re.compile(r"\b(\d+)%\|.*?\|\s*(\d+)/(\d+)\s*")

    def __init__(self, callback: Callable[[LtxProgress], None]):
        self.callback = callback
        self.buffer = ""
        self.denoising_pass = 0
        self.active_phase = "preparing"
        self.last_event: LtxProgress | None = None

    def feed(self, text: str) -> None:
        parts = re.split(r"[\r\n]", self.buffer + text)
        self.buffer = parts.pop()
        for part in parts:
            self._parse_line(part.strip())

    def finish(self) -> None:
        if self.buffer.strip():
            self._parse_line(self.buffer.strip())
        self.buffer = ""

    def _emit(self, event: LtxProgress) -> None:
        if event == self.last_event:
            return
        self.last_event = event
        _notify_progress(self.callback, event)

    def _parse_line(self, line: str) -> None:
        if not line:
            return
        if "Building text encoder" in line:
            self.active_phase = "prompt_encoding"
            self._emit(LtxProgress(self.active_phase, "Loading text encoder"))
            return
        if "Prompt encoding complete" in line:
            self._emit(LtxProgress("prompt_encoding", "Prompt encoding complete"))
            return
        if "Building video encoder + spatial upsampler" in line:
            self.active_phase = "refinement_preparing"
            self._emit(LtxProgress(self.active_phase, "Preparing high-resolution refinement"))
            return
        if "Running denoising loop" in line:
            self.denoising_pass += 1
            self.active_phase = "base_denoise" if self.denoising_pass == 1 else "refinement"
            match = re.search(r"\((\d+) steps", line)
            total = int(match.group(1)) if match else None
            label = (
                "Initial generation"
                if self.denoising_pass == 1
                else "High-resolution refinement"
            )
            self._emit(LtxProgress(self.active_phase, label, 0, total))
            return
        if "Building video decoder" in line:
            self.active_phase = "video_decode"
            self._emit(LtxProgress(self.active_phase, "Decoding video"))
            return
        if "Building audio decoder + vocoder" in line:
            self.active_phase = "audio_decode"
            self._emit(LtxProgress(self.active_phase, "Decoding audio"))
            return
        match = self._step_pattern.search(line)
        if match:
            current, total = int(match.group(2)), int(match.group(3))
            labels = {
                "base_denoise": "Initial generation",
                "refinement": "High-resolution refinement",
                "audio_decode": "Decoding audio",
            }
            label = labels.get(self.active_phase, "Processing")
            self._emit(LtxProgress(self.active_phase, label, current, total))


def _notify_progress(
    callback: Callable[[LtxProgress], None] | None, event: LtxProgress
) -> None:
    if callback is None:
        return
    try:
        callback(event)
    except Exception:
        # Progress reporting must never be able to fail an expensive render.
        return


def _cancellation_requested(callback: Callable[[], bool] | None) -> bool:
    if callback is None:
        return False
    try:
        return callback()
    except Exception:
        return False


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=15)
        return
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


@dataclass(frozen=True)
class LtxModelPaths:
    root: Path

    @property
    def transformer(self) -> Path:
        return self.root / "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors"

    @property
    def text_encoder(self) -> Path:
        return self.root / "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"

    @property
    def video_vae(self) -> Path:
        return self.root / "vae/ltx-2.5-video-vae-conv-bf16.safetensors"

    @property
    def audio_vae(self) -> Path:
        return self.root / "vae/ltx-2.5-audio-vae-bf16.safetensors"

    @property
    def spatial_upscaler(self) -> Path:
        filename = "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
        return self.root / "latent_upscale_models" / filename

    def all(self) -> tuple[Path, ...]:
        return (
            self.transformer,
            self.text_encoder,
            self.video_vae,
            self.audio_vae,
            self.spatial_upscaler,
        )

    def missing(self) -> list[Path]:
        return [path for path in self.all() if not path.is_file()]


@dataclass(frozen=True)
class LtxImageConditioning:
    reference_id: str
    path: Path
    frame_index: int
    strength: float = 1.0

    def validate(self, *, frames: int, require_input: bool = True) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", self.reference_id):
            raise LtxError(f"Invalid reference ID: {self.reference_id!r}")
        if self.frame_index < 0 or self.frame_index >= frames:
            raise LtxError(
                f"Reference @{self.reference_id} frame {self.frame_index} is outside 0–{frames - 1}"
            )
        if not 0.0 < self.strength <= 1.0:
            raise LtxError("Image conditioning strength must be greater than 0 and at most 1")
        if require_input and not self.path.is_file():
            raise LtxError(f"Conditioning image not found: {self.path}")


@dataclass(frozen=True)
class LtxRenderSpec:
    image: Path
    prompt: str
    output: Path
    width: int = 1024
    height: int = 576
    frames: int = 121
    frame_rate: float = 24.0
    seed: int = 42
    offload: str = "disk"
    max_batch_size: int = 1
    image_conditionings: tuple[LtxImageConditioning, ...] = ()
    parent_take_id: str | None = None
    conditioning_boundary_id: str | None = None
    retake_reason: str | None = None

    def validate(self, *, require_input: bool = True) -> None:
        if self.width <= 0 or self.height <= 0 or self.width % 64 or self.height % 64:
            raise LtxError("Two-stage LTX width and height must be positive multiples of 64")
        if self.frames <= 0 or (self.frames - 1) % 8:
            raise LtxError("LTX frame count must satisfy frames = 8n + 1")
        if self.frame_rate <= 0:
            raise LtxError("Frame rate must be positive")
        if not self.prompt.strip():
            raise LtxError("Prompt must not be empty")
        if len(self.prompt.split()) > 200:
            raise LtxError("Prompt must be at most 200 words")
        if self.seed < 0 or self.seed > 2**32 - 1:
            raise LtxError("Seed must fit an unsigned 32-bit integer")
        if self.offload not in {"disk", "cpu", "none"}:
            raise LtxError("Offload must be one of: disk, cpu, none")
        if self.max_batch_size < 1:
            raise LtxError("Maximum batch size must be positive")
        if self.parent_take_id is not None and not (self.retake_reason or "").strip():
            raise LtxError("A retake with a parent take must record a retake reason")
        conditionings = self.resolved_image_conditionings
        for conditioning in conditionings:
            conditioning.validate(frames=self.frames, require_input=require_input)
        frame_indices = [conditioning.frame_index for conditioning in conditionings]
        if len(frame_indices) != len(set(frame_indices)):
            raise LtxError("Only one conditioning image may target each frame")

    @property
    def resolved_image_conditionings(self) -> tuple[LtxImageConditioning, ...]:
        if self.image_conditionings:
            return self.image_conditionings
        return (LtxImageConditioning("start-frame", self.image, 0),)

    def provenance_payload(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "image": str(self.image.resolve()),
            "image_conditionings": [
                {**asdict(item), "path": str(item.path.resolve())}
                for item in self.resolved_image_conditionings
            ],
            "output": str(self.output.resolve()),
        }

    @property
    def job_id(self) -> str:
        payload = self.provenance_payload()
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return digest[:16]


@dataclass(frozen=True)
class LtxPreflight:
    ok: bool
    issues: tuple[str, ...]
    runtime_commit: str | None
    free_disk_gib: float
    mps_backend: str | None
    entrypoint_options: tuple[str, ...]


class JsonlEventLog:
    def __init__(self, path: Path):
        self.path = path

    def append(self, event: str, *, job_id: str, **details: Any) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "job_id": job_id,
            **details,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


class NativeLtxRenderer:
    def __init__(
        self,
        *,
        runtime_root: Path,
        models_root: Path,
        ffprobe_binary: str = "ffprobe",
        minimum_free_gib: float = 20.0,
    ):
        self.runtime_root = runtime_root.resolve()
        self.models = LtxModelPaths(models_root.resolve())
        self.ffprobe_binary = ffprobe_binary
        if minimum_free_gib <= 0:
            raise ValueError("Minimum free disk reserve must be positive")
        self.minimum_free_gib = minimum_free_gib

    @property
    def python_binary(self) -> Path:
        return self.runtime_root / ".venv/bin/python"

    def preflight(self, *, minimum_free_gib: float | None = None) -> LtxPreflight:
        issues: list[str] = []
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            issues.append("This profile requires Apple Silicon macOS")
        if shutil.which(self.ffprobe_binary) is None:
            issues.append(f"Media probe not found: {self.ffprobe_binary}")
        if not (self.runtime_root / "pyproject.toml").is_file():
            issues.append(f"Official LTX runtime not found: {self.runtime_root}")
        if not self.python_binary.is_file():
            issues.append(f"Pinned LTX Python environment not found: {self.python_binary}")

        missing = self.models.missing()
        if missing:
            issues.append("Missing model files: " + ", ".join(str(path) for path in missing))

        disk_target = self.models.root if self.models.root.exists() else self.models.root.parent
        disk_usage = shutil.disk_usage(disk_target)
        free_disk_gib = disk_usage.free / 1024**3
        required_free_gib = (
            self.minimum_free_gib if minimum_free_gib is None else minimum_free_gib
        )
        if required_free_gib <= 0:
            raise ValueError("Minimum free disk reserve must be positive")
        if free_disk_gib < required_free_gib:
            issues.append(
                f"Only {free_disk_gib:.1f} GiB free; require {required_free_gib:.1f} GiB"
            )

        runtime_commit = self._runtime_commit()
        if runtime_commit != PINNED_LTX_COMMIT:
            issues.append(
                f"LTX runtime commit is {runtime_commit or 'unknown'}; expected {PINNED_LTX_COMMIT}"
            )
        mps_backend, mps_issue = self._probe_mps()
        if mps_issue:
            issues.append(mps_issue)
        entrypoint_options, entrypoint_issue = self._probe_entrypoint_options()
        if entrypoint_issue:
            issues.append(entrypoint_issue)
        return LtxPreflight(
            not issues,
            tuple(issues),
            runtime_commit,
            free_disk_gib,
            mps_backend,
            entrypoint_options,
        )

    def command(self, spec: LtxRenderSpec) -> list[str]:
        spec.validate()
        command = [
            str(self.python_binary),
            "-m",
            "ltx_pipelines.distilled",
            "--transformer-path",
            str(self.models.transformer),
            "--text-encoder-path",
            str(self.models.text_encoder),
            "--video-vae-path",
            str(self.models.video_vae),
            "--audio-vae-path",
            str(self.models.audio_vae),
            "--spatial-upsampler-path",
            str(self.models.spatial_upscaler),
            "--offload",
            spec.offload,
            "--max-batch-size",
            str(spec.max_batch_size),
            "--height",
            str(spec.height),
            "--width",
            str(spec.width),
            "--num-frames",
            str(spec.frames),
            "--frame-rate",
            str(spec.frame_rate),
        ]
        for conditioning in spec.resolved_image_conditionings:
            command.extend(
                [
                    "--image",
                    str(conditioning.path.resolve()),
                    str(conditioning.frame_index),
                    str(conditioning.strength),
                ]
            )
        command.extend(
            [
            "--prompt",
            spec.prompt,
            "--seed",
            str(spec.seed),
            "--output-path",
            str(spec.output.resolve()),
            ]
        )
        return command

    def render(
        self,
        spec: LtxRenderSpec,
        *,
        event_log: Path,
        label: str | None = None,
        tags: tuple[str, ...] = (),
        progress_callback: Callable[[LtxProgress], None] | None = None,
        cancel_requested: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        spec.validate()
        preflight = self.preflight()
        if not preflight.ok:
            raise LtxError("Preflight failed:\n- " + "\n- ".join(preflight.issues))
        if spec.output.exists():
            raise LtxError(f"Refusing to overwrite existing output: {spec.output}")

        spec.output.parent.mkdir(parents=True, exist_ok=True)
        log = JsonlEventLog(event_log)
        command = self.command(spec)
        unsupported = sorted(
            {argument for argument in command if argument.startswith("--")}
            - set(preflight.entrypoint_options)
        )
        if unsupported:
            raise LtxError(
                "Pinned distilled entrypoint does not support: " + ", ".join(unsupported)
            )
        started = datetime.now(UTC)
        started_monotonic = time.monotonic()
        swap_before = _swap_used_bytes()
        host_health_before = _host_health_snapshot()
        disk_free_before = shutil.disk_usage(spec.output.parent).free
        run_id = f"{spec.job_id}-{started.strftime('%Y%m%dT%H%M%S%fZ')}"
        sidecar = spec.output.with_name(f"{spec.output.stem}.{run_id}.run.json")
        process_log = _attempt_process_log(spec.output, run_id)
        record = RunRecord(
            run_id=run_id,
            job_id=spec.job_id,
            label=label or spec.output.stem,
            tags=list(dict.fromkeys(tags)),
            status="running",
            started_at=started.isoformat(),
            spec=spec.provenance_payload(),
            engine={
                "name": "LTX-2.5 Fast distilled",
                "pipeline": "ltx_pipelines.distilled",
                "precision": "bf16",
                "quantization": "none",
                "runtime_commit": preflight.runtime_commit,
                "mps_backend": preflight.mps_backend,
                "transformer": self.models.transformer.name,
                "video_vae": self.models.video_vae.name,
            },
            system={
                "platform": platform.platform(),
                "machine": platform.machine(),
                "memory_bytes": os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"),
                "disk_free_bytes_before": disk_free_before,
                "swap_used_bytes_before": swap_before,
                "host_health_before": host_health_before,
            },
            artifacts={
                "image": {"path": str(spec.image), "sha256": sha256_path(spec.image)},
                "images": [
                    {
                        "reference_id": item.reference_id,
                        "path": str(item.path),
                        "frame_index": item.frame_index,
                        "strength": item.strength,
                        "sha256": sha256_path(item.path),
                    }
                    for item in spec.resolved_image_conditionings
                ],
                "video": {"path": str(spec.output), "sha256": None},
                "process_log": str(process_log),
            },
        )
        write_run_record(record, sidecar)
        log.append(
            "render_started",
            job_id=spec.job_id,
            spec=spec.provenance_payload(),
            runtime_commit=preflight.runtime_commit,
            command=command,
        )

        with process_log.open("wb") as output:
            process = subprocess.Popen(
                command,
                cwd=self.runtime_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=self._runtime_environment(),
            )
            parser = LtxProgressParser(progress_callback) if progress_callback else None
            try:
                if process.stdout is None:
                    raise LtxError("Could not capture LTX progress output")
                while True:
                    if _cancellation_requested(cancel_requested):
                        raise LtxCancelled("Render cancelled by user")
                    readable, _, _ = select.select([process.stdout.fileno()], [], [], 0.5)
                    if not readable:
                        continue
                    chunk = os.read(process.stdout.fileno(), 4096)
                    if not chunk:
                        break
                    output.write(chunk)
                    output.flush()
                    if parser:
                        parser.feed(chunk.decode("utf-8", errors="replace"))
                if parser:
                    parser.finish()
                return_code = process.wait()
            except (KeyboardInterrupt, LtxCancelled) as exc:
                _terminate_process_group(process)
                message = (
                    str(exc) if isinstance(exc, LtxCancelled) else "Render cancelled by operator"
                )
                cancelled = record.model_copy(
                    update={
                        "status": "cancelled",
                        "completed_at": datetime.now(UTC).isoformat(),
                        "elapsed_seconds": time.monotonic() - started_monotonic,
                        "performance": {
                            "peak_rss_bytes": _child_peak_rss_bytes(),
                            "host_health_after": _host_health_snapshot(),
                        },
                        "error": {"message": message},
                    }
                )
                write_run_record(cancelled, sidecar)
                log.append("render_cancelled", job_id=spec.job_id, process_log=process_log)
                raise LtxCancelled(message) from None

        if return_code != 0:
            elapsed = time.monotonic() - started_monotonic
            failed = record.model_copy(
                update={
                    "status": "failed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "elapsed_seconds": elapsed,
                    "performance": {
                        "peak_rss_bytes": _child_peak_rss_bytes(),
                        "host_health_after": _host_health_snapshot(),
                    },
                    "error": {"return_code": return_code, "message": "LTX process failed"},
                }
            )
            write_run_record(failed, sidecar)
            log.append(
                "render_failed",
                job_id=spec.job_id,
                return_code=return_code,
                process_log=process_log,
            )
            raise LtxError(f"LTX exited with {return_code}; see {process_log}")

        _notify_progress(progress_callback, LtxProgress("validation", "Validating generated media"))
        metadata = probe_media(spec.output, ffprobe_binary=self.ffprobe_binary)
        validate_media(metadata, spec)
        elapsed = time.monotonic() - started_monotonic
        artifacts = dict(record.artifacts)
        artifacts["video"] = {
            "path": str(spec.output),
            "sha256": sha256_path(spec.output),
            "size_bytes": spec.output.stat().st_size,
        }
        swap_after = _swap_used_bytes()
        completed = record.model_copy(
            update={
                "status": "completed",
                "completed_at": datetime.now(UTC).isoformat(),
                "elapsed_seconds": elapsed,
                "artifacts": artifacts,
                "performance": {
                    "peak_rss_bytes": _child_peak_rss_bytes(),
                    "seconds_per_frame": elapsed / spec.frames,
                    "swap_used_bytes_after": swap_after,
                    "swap_delta_bytes": _optional_delta(swap_after, swap_before),
                    "disk_free_bytes_after": shutil.disk_usage(spec.output.parent).free,
                    "host_health_after": _host_health_snapshot(),
                },
                "media": metadata,
            }
        )
        write_run_record(completed, sidecar)
        log.append(
            "render_completed",
            job_id=spec.job_id,
            output=spec.output,
            media=metadata,
            process_log=process_log,
        )
        return metadata

    def _runtime_commit(self) -> str | None:
        completed = subprocess.run(
            ["git", "-C", str(self.runtime_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip() if completed.returncode == 0 else None

    def _runtime_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        runtime_bin = str(self.python_binary.parent)
        environment["PATH"] = runtime_bin + os.pathsep + environment.get("PATH", "")
        return environment

    def _probe_mps(self) -> tuple[str | None, str | None]:
        if not self.python_binary.is_file():
            return None, None
        probe = """
import json
import torch
import mps_sdpa
from transformers import Gemma4UnifiedProcessor
status = mps_sdpa.backend_status()
q = torch.randn(1, 4, 16, 16, device="mps", dtype=torch.bfloat16)
output = mps_sdpa.sdpa_opt(q, q, q)
torch.mps.synchronize()
print(json.dumps({
    "mps": torch.backends.mps.is_available(),
    "picked": status.get("picked"),
    "available": status.get("available", []),
    "bf16_attention_ok": tuple(output.shape) == tuple(q.shape),
    "gemma_processor_ok": Gemma4UnifiedProcessor.__name__ == "Gemma4UnifiedProcessor",
}))
"""
        try:
            completed = subprocess.run(
                [str(self.python_binary), "-c", probe],
                cwd=self.runtime_root,
                env=self._runtime_environment(),
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return None, "MPS zero-copy attention probe timed out"
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            detail = stderr.splitlines()[-1] if stderr else "unknown"
            return None, f"MPS attention probe failed: {detail}"
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return None, "MPS attention probe returned invalid output"
        picked = str(payload.get("picked"))
        if not payload.get("mps"):
            return picked, "PyTorch MPS is unavailable in the pinned runtime"
        if not payload.get("bf16_attention_ok"):
            return picked, "BF16 MPS attention returned an unexpected result"
        if not payload.get("gemma_processor_ok"):
            return picked, "Gemma 4 processor is unavailable in the pinned runtime"
        if "mpsgraph_zc" not in payload.get("available", []) or picked != "mpsgraph_zc":
            issue = "Zero-copy mpsgraph_zc attention is not active; refusing leak-prone fallback"
            return picked, issue
        return picked, None

    def _probe_entrypoint_options(self) -> tuple[tuple[str, ...], str | None]:
        if not self.python_binary.is_file():
            return (), None
        try:
            completed = subprocess.run(
                [str(self.python_binary), "-m", "ltx_pipelines.distilled", "--help"],
                cwd=self.runtime_root,
                env=self._runtime_environment(),
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return (), "Pinned distilled entrypoint capability probe timed out"
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            return (), (
                "Pinned distilled entrypoint capability probe failed: "
                + (detail[-1] if detail else "unknown")
            )
        options = tuple(sorted(set(re.findall(r"--[a-z0-9][a-z0-9-]*", completed.stdout))))
        required = {
            "--audio-vae-path",
            "--frame-rate",
            "--height",
            "--image",
            "--max-batch-size",
            "--num-frames",
            "--offload",
            "--output-path",
            "--prompt",
            "--seed",
            "--spatial-upsampler-path",
            "--text-encoder-path",
            "--transformer-path",
            "--video-vae-path",
            "--width",
        }
        missing = sorted(required - set(options))
        if missing:
            return options, "Pinned distilled entrypoint is missing: " + ", ".join(missing)
        return options, None


def probe_media(path: Path, *, ffprobe_binary: str = "ffprobe") -> dict[str, Any]:
    if not path.is_file():
        raise LtxError(f"Rendered output not found: {path}")
    completed = subprocess.run(
        [
            ffprobe_binary,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise LtxError(f"ffprobe failed: {completed.stderr.strip()}")
    return cast(dict[str, Any], json.loads(completed.stdout))


def _child_peak_rss_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    return peak if platform.system() == "Darwin" else peak * 1024


def _swap_used_bytes() -> int | None:
    if platform.system() != "Darwin":
        return None
    completed = subprocess.run(
        ["sysctl", "vm.swapusage"], capture_output=True, text=True, check=False
    )
    match = re.search(r"used = ([0-9.]+)([MG])", completed.stdout)
    if completed.returncode != 0 or match is None:
        return None
    scale = 1024**2 if match.group(2) == "M" else 1024**3
    return int(float(match.group(1)) * scale)


def _optional_delta(after: int | None, before: int | None) -> int | None:
    return None if after is None or before is None else after - before


def _attempt_process_log(output: Path, run_id: str) -> Path:
    return output.with_name(f"{output.stem}.{run_id}.render.log")


def _host_health_snapshot() -> dict[str, Any]:
    if platform.system() != "Darwin":
        return {}
    snapshot: dict[str, Any] = {"swap_used_bytes": _swap_used_bytes()}
    memory = subprocess.run(
        ["memory_pressure", "-Q"], capture_output=True, text=True, check=False
    )
    match = re.search(r"System-wide memory free percentage:\s*(\d+)%", memory.stdout)
    if memory.returncode == 0 and match is not None:
        snapshot["memory_free_percent"] = int(match.group(1))
    thermal = subprocess.run(
        ["pmset", "-g", "therm"], capture_output=True, text=True, check=False
    )
    if thermal.returncode == 0:
        snapshot["thermal_status"] = " ".join(thermal.stdout.split())
    vm = subprocess.run(["vm_stat"], capture_output=True, text=True, check=False)
    if vm.returncode == 0:
        page_match = re.search(r"page size of (\d+) bytes", vm.stdout)
        page_size = int(page_match.group(1)) if page_match else 16_384
        names = {
            "Pages free": "free_bytes",
            "Pages active": "active_bytes",
            "Pages inactive": "inactive_bytes",
            "Pages speculative": "speculative_bytes",
            "Pages wired down": "wired_bytes",
            "Pages occupied by compressor": "compressed_bytes",
        }
        for line in vm.stdout.splitlines():
            key, separator, value = line.partition(":")
            if separator and key in names:
                pages = value.strip().rstrip(".")
                if pages.isdigit():
                    snapshot[names[key]] = int(pages) * page_size
    return snapshot


def validate_media(metadata: dict[str, Any], spec: LtxRenderSpec) -> None:
    streams = metadata.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if not videos:
        raise LtxError("Rendered file has no video stream")
    video = videos[0]
    if (video.get("width"), video.get("height")) != (spec.width, spec.height):
        raise LtxError(
            f"Unexpected output size: {video.get('width')}x{video.get('height')}; "
            f"expected {spec.width}x{spec.height}"
        )
    rate_text = video.get("avg_frame_rate") or video.get("r_frame_rate")
    try:
        actual_rate = float(Fraction(str(rate_text)))
    except (ValueError, ZeroDivisionError):
        raise LtxError(f"Invalid output frame rate: {rate_text!r}") from None
    if abs(actual_rate - spec.frame_rate) > 0.01:
        raise LtxError(f"Unexpected output frame rate: {actual_rate}; expected {spec.frame_rate}")
