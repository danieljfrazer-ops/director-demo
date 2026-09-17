# ruff: noqa: E501

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import queue
import re
import shutil
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import unquote, urlparse

from director_demo.config import Settings
from director_demo.editorial import (
    ApprovedBoundary,
    ArtifactRef,
    CreativeDecision,
    CutClip,
    CutManifest,
    EditDecision,
    EditorialProject,
    EditorialShot,
    QualityReview,
    TakeRecord,
    TechnicalDecision,
    assemble_cut,
    write_model,
)
from director_demo.extension import make_extension_manifest, manifest_path
from director_demo.ltx import (
    LtxCancelled,
    LtxImageConditioning,
    LtxProgress,
    LtxRenderSpec,
    NativeLtxRenderer,
)
from director_demo.runs import sha256_path

HOST = "127.0.0.1"
PORT = 8765
MAX_REQUEST_BYTES = 80 * 1024 * 1024
MAX_REFERENCE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_REFERENCE_BYTES = 50 * 1024 * 1024
MAX_REFERENCES = 8
ALLOWED_IMAGES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
APP_ROOT = Path.cwd().resolve()
JOBS_ROOT = APP_ROOT / "outputs/app-jobs"
JOB_QUEUE: queue.Queue[str] = queue.Queue()
CANCEL_EVENTS: dict[str, threading.Event] = {}
CANCEL_LOCK = threading.Lock()


@dataclass(frozen=True)
class ReferenceUpload:
    reference_id: str
    image: bytes
    extension: str
    position_percent: float
    original_name: str


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _job_path(job_id: str) -> Path:
    if not job_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in job_id):
        raise ValueError("invalid job ID")
    return JOBS_ROOT / job_id


def _read_job(job_id: str) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((_job_path(job_id) / "job.json").read_text(encoding="utf-8")),
    )


def _job_for_api(job_id: str) -> dict[str, Any]:
    """Return persisted job data plus its current, display-only local folder path."""
    job = _read_job(job_id)
    job["folder_path"] = str(_job_path(job_id).resolve())
    return job


def _update_job(job_id: str, **changes: Any) -> dict[str, Any]:
    job = _read_job(job_id)
    job.update(changes)
    job["updated_at"] = datetime.now(UTC).isoformat()
    _atomic_json(_job_path(job_id) / "job.json", job)
    return job


def _cancel_event(job_id: str) -> threading.Event:
    with CANCEL_LOCK:
        return CANCEL_EVENTS.setdefault(job_id, threading.Event())


def _decode_reference(item: dict[str, Any], index: int) -> ReferenceUpload:
    reference_id = str(item.get("id", "")).strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", reference_id):
        raise ValueError(
            f"Reference {index + 1} ID must start with a letter and use only a-z, 0-9, _ or -"
        )
    mime = str(item.get("image_type", ""))
    if mime not in ALLOWED_IMAGES:
        raise ValueError(f"Reference @{reference_id} must be PNG, JPEG, or WebP")
    encoded = str(item.get("image_data", ""))
    if "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        image = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise ValueError(f"Reference @{reference_id} is not valid base64") from exc
    if not image or len(image) > MAX_REFERENCE_BYTES:
        raise ValueError(f"Reference @{reference_id} must be between 1 byte and 25 MiB")
    try:
        position = float(item.get("position_percent", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Reference @{reference_id} timeline position is invalid") from exc
    if position < 0 or position > 100:
        raise ValueError(f"Reference @{reference_id} position must be between 0 and 100%")
    return ReferenceUpload(
        reference_id=reference_id,
        image=image,
        extension=ALLOWED_IMAGES[mime],
        position_percent=position,
        original_name=Path(str(item.get("name", f"reference-{index + 1}"))).name,
    )


def _validate_request(
    payload: dict[str, Any],
) -> tuple[str, list[ReferenceUpload], int, int, int]:
    prompt, clips, duration, seed = _validate_generation_settings(payload)
    raw_references = payload.get("images")
    if raw_references is None and payload.get("image_data"):
        raw_references = [
            {
                "id": "start-frame",
                "image_type": payload.get("image_type"),
                "image_data": payload.get("image_data"),
                "position_percent": 0,
                "name": "legacy-reference",
            }
        ]
    references = _validate_reference_records(raw_references, require_start=True)
    frames = 121 if duration == 5 else 49
    global_frames = [
        round(item.position_percent / 100 * clips * (frames - 1)) for item in references
    ]
    if len(global_frames) != len(set(global_frames)):
        raise ValueError("Reference positions resolve to the same generated frame")
    return prompt, references, clips, duration, seed


def _validate_generation_settings(payload: dict[str, Any]) -> tuple[str, int, int, int]:
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt or len(prompt.split()) > 170:
        raise ValueError("Motion prompt must contain 1–170 words")
    clips = int(payload.get("clips", 1))
    duration = int(payload.get("duration", 5))
    seed = int(payload.get("seed", 42))
    if clips not in {1, 2, 3}:
        raise ValueError("Clip count must be 1, 2, or 3")
    if duration not in {2, 5}:
        raise ValueError("Clip duration must be 2 or 5 seconds")
    if seed < 0 or seed > 2**32 - 1:
        raise ValueError("Seed is outside the supported range")
    return prompt, clips, duration, seed


def _validate_reference_records(
    raw_references: Any, *, require_start: bool, maximum: int = MAX_REFERENCES
) -> list[ReferenceUpload]:
    if not isinstance(raw_references, list) or not 1 <= len(raw_references) <= maximum:
        raise ValueError(f"Upload between 1 and {maximum} reference images")
    references = [
        _decode_reference(cast(dict[str, Any], item), index)
        for index, item in enumerate(raw_references)
        if isinstance(item, dict)
    ]
    if len(references) != len(raw_references):
        raise ValueError("Every reference must be an image record")
    ids = [item.reference_id for item in references]
    if len(ids) != len(set(ids)):
        raise ValueError("Reference IDs must be unique")
    if sum(len(item.image) for item in references) > MAX_TOTAL_REFERENCE_BYTES:
        raise ValueError("Reference images must total no more than 50 MiB")
    if require_start and not any(item.position_percent == 0 for item in references):
        raise ValueError("At least one reference must target the 0% start frame")
    return references


def create_job(payload: dict[str, Any]) -> dict[str, Any]:
    prompt, references, clips, duration, seed = _validate_request(payload)
    job_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    directory = _job_path(job_id)
    directory.mkdir(parents=True)
    references_directory = directory / "references"
    references_directory.mkdir()
    stored_references: list[dict[str, Any]] = []
    for item in references:
        reference = references_directory / f"{item.reference_id}{item.extension}"
        reference.write_bytes(item.image)
        stored_references.append(
            {
                "id": item.reference_id,
                "file": str(reference.relative_to(directory)),
                "original_name": item.original_name,
                "position_percent": item.position_percent,
                "strength": 1.0,
                "sha256": sha256_path(reference),
            }
        )
    start_reference = min(stored_references, key=lambda item: float(item["position_percent"]))
    now = datetime.now(UTC).isoformat()
    job = {
        "job_id": job_id,
        "status": "queued",
        "stage": "Waiting for the sequential renderer",
        "created_at": now,
        "updated_at": now,
        "prompt": prompt,
        "reference": start_reference["file"],
        "references": stored_references,
        "clips": clips,
        "duration_seconds": duration,
        "seed": seed,
        "settings": {
            "width": 1024,
            "height": 576,
            "frame_rate": 24,
            "frames_per_clip": 121 if duration == 5 else 49,
            "offload": "disk",
            "max_batch_size": 1,
            "join": "exact shared-frame hard cut",
        },
        "completed_clips": 0,
        "compiled_prompts": {},
        "progress": {
            "overall_percent": 0.0,
            "clip_percent": 0.0,
            "clip_index": None,
            "phase": "queued",
            "message": "Waiting for the sequential renderer",
            "step_current": None,
            "step_total": None,
        },
        "final_video": None,
        "error": None,
    }
    _atomic_json(directory / "job.json", job)
    _cancel_event(job_id)
    JOB_QUEUE.put(job_id)
    return _job_for_api(job_id)


def _link_or_copy(source: Path, destination: Path) -> None:
    try:
        destination.hardlink_to(source)
    except OSError:
        shutil.copy2(source, destination)


def _video_frame_details(source: Path, ffprobe_binary: str) -> tuple[int, float]:
    completed = subprocess.run(
        [
            ffprobe_binary,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames,avg_frame_rate",
            "-of",
            "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Could not inspect parent video")
    try:
        stream = json.loads(completed.stdout)["streams"][0]
        frame_count = int(stream["nb_read_frames"])
        frame_rate = float(Fraction(str(stream["avg_frame_rate"])))
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError) as exc:
        raise RuntimeError("Parent video does not expose an exact decoded frame count") from exc
    if frame_count <= 0 or frame_rate <= 0:
        raise RuntimeError("Parent video has invalid frame geometry")
    return frame_count, frame_rate


def _validate_parent_assembly(parent_job_id: str, parent_video: Path) -> tuple[str, str]:
    record_path = parent_video.with_suffix(".assembly.json")
    if not record_path.is_file():
        raise ValueError("Parent scene is missing its immutable assembly provenance")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        expected_hash = str(record["output"]["sha256"])
        dependency_digest = str(record["dependency_digest"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Parent assembly provenance is invalid") from exc
    actual_hash = sha256_path(parent_video)
    if record.get("status") != "completed" or record.get("project_id") != parent_job_id:
        raise ValueError("Parent assembly provenance does not identify this completed scene")
    if actual_hash != expected_hash:
        raise ValueError("Parent stitched video has changed since assembly validation")
    if not re.fullmatch(r"[0-9a-f]{64}", dependency_digest):
        raise ValueError("Parent assembly dependency digest is invalid")
    return expected_hash, dependency_digest


def create_extension_job(parent_job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Queue an appended-only child using the parent's exact assembled final frame."""

    parent = _read_job(parent_job_id)
    if parent.get("status") != "completed" or not parent.get("final_video"):
        raise ValueError("Only a completed stitched scene can be extended")
    prompt, clips, duration, seed = _validate_generation_settings(payload)
    raw_uploads = payload.get("images", [])
    if raw_uploads is None:
        raw_uploads = []
    uploads = (
        _validate_reference_records(raw_uploads, require_start=False, maximum=MAX_REFERENCES - 1)
        if raw_uploads
        else []
    )
    if any(item.position_percent <= 0 for item in uploads):
        raise ValueError("Extension references must target a position after the inherited 0% frame")
    if any(item.reference_id == "extension-start" for item in uploads):
        raise ValueError("Reference ID extension-start is reserved for the parent endpoint")

    parent_directory = _job_path(parent_job_id).resolve()
    parent_video = (parent_directory / str(parent["final_video"])).resolve()
    try:
        parent_video.relative_to(parent_directory)
    except ValueError as exc:
        raise ValueError("Parent video path is outside its run folder") from exc
    if not parent_video.is_file():
        raise FileNotFoundError("Parent stitched video is missing")
    validated_parent_hash, parent_dependency_digest = _validate_parent_assembly(
        parent_job_id, parent_video
    )

    settings = Settings()
    job_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    directory = _job_path(job_id)
    directory.mkdir(parents=True)
    try:
        references_directory = directory / "references"
        references_directory.mkdir()
        parent_copy = directory / "parent-assembly.mp4"
        _link_or_copy(parent_video, parent_copy)
        parent_frames, parent_fps = _video_frame_details(parent_copy, settings.ffprobe_binary)
        endpoint = references_directory / "extension-start.png"
        _extract_frame(parent_copy, parent_frames - 1, endpoint, settings.ffmpeg_binary)

        stored_references: list[dict[str, Any]] = [
            {
                "id": "extension-start",
                "file": str(endpoint.relative_to(directory)),
                "original_name": f"final frame of {parent_job_id}",
                "position_percent": 0.0,
                "strength": 1.0,
                "sha256": sha256_path(endpoint),
                "role": "inherited_assembly_endpoint",
            }
        ]
        for item in uploads:
            reference = references_directory / f"{item.reference_id}{item.extension}"
            reference.write_bytes(item.image)
            stored_references.append(
                {
                    "id": item.reference_id,
                    "file": str(reference.relative_to(directory)),
                    "original_name": item.original_name,
                    "position_percent": item.position_percent,
                    "strength": 1.0,
                    "sha256": sha256_path(reference),
                    "role": "extension_timeline_reference",
                }
            )
        frames = 121 if duration == 5 else 49
        global_frames = [
            round(float(item["position_percent"]) / 100 * clips * (frames - 1))
            for item in stored_references
        ]
        if len(global_frames) != len(set(global_frames)):
            raise ValueError("Extension reference positions resolve to the same generated frame")

        parent_hash = sha256_path(parent_copy)
        endpoint_hash = sha256_path(endpoint)
        if parent_hash is None or endpoint_hash is None:
            raise RuntimeError("Could not hash extension inputs")
        if parent_hash != validated_parent_hash:
            raise RuntimeError("Parent assembly copy changed during extension preparation")
        parent_extension = parent.get("extension") or {}
        manifest = make_extension_manifest(
            extension_id=job_id,
            parent_job_id=parent_job_id,
            parent_extension_id=cast(str | None, parent_extension.get("extension_id")),
            lineage_depth=int(parent_extension.get("lineage_depth", 0)) + 1,
            prompt=prompt,
            parent_assembly=ArtifactRef(path=Path(parent_copy.name), sha256=parent_hash),
            parent_dependency_digest=parent_dependency_digest,
            endpoint_frame=ArtifactRef(
                path=Path(endpoint.relative_to(directory)), sha256=endpoint_hash
            ),
            parent_frame_count=parent_frames,
            parent_frame_rate=parent_fps,
            clip_count=clips,
            seconds_per_clip=cast(Literal[2, 5], duration),
            seed=seed,
        )
        write_model(manifest, manifest_path(directory))
        now = datetime.now(UTC).isoformat()
        job = {
            "job_id": job_id,
            "job_type": "scene_extension",
            "status": "queued",
            "stage": "Waiting to extend stitched scene",
            "created_at": now,
            "updated_at": now,
            "prompt": prompt,
            "reference": stored_references[0]["file"],
            "references": stored_references,
            "clips": clips,
            "duration_seconds": duration,
            "seed": seed,
            "parent_job_id": parent_job_id,
            "extension": manifest.model_dump(mode="json"),
            "settings": {
                "width": 1024,
                "height": 576,
                "frame_rate": 24,
                "frames_per_clip": frames,
                "offload": "disk",
                "max_batch_size": 1,
                "join": "exact shared-frame hard cut",
            },
            "completed_clips": 0,
            "compiled_prompts": {},
            "progress": {
                "overall_percent": 0.0,
                "clip_percent": 0.0,
                "clip_index": None,
                "phase": "queued",
                "message": "Waiting to extend stitched scene",
                "step_current": None,
                "step_total": None,
            },
            "final_video": None,
            "error": None,
        }
        _atomic_json(directory / "job.json", job)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    _cancel_event(job_id)
    JOB_QUEUE.put(job_id)
    return _job_for_api(job_id)


def import_completed_assembly(
    source_video: Path,
    source_assembly_record: Path,
    *,
    title: str,
    prompt_summary: str,
) -> dict[str, Any]:
    """Import a validated historical assembly without modifying its source evidence."""

    source_video = source_video.resolve()
    source_assembly_record = source_assembly_record.resolve()
    if not source_video.is_file() or not source_assembly_record.is_file():
        raise FileNotFoundError("Historical video and assembly record are both required")
    try:
        source_record = json.loads(source_assembly_record.read_text(encoding="utf-8"))
        expected_hash = str(source_record["output"]["sha256"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Historical assembly record is invalid") from exc
    actual_hash = sha256_path(source_video)
    if source_record.get("status") != "completed" or actual_hash != expected_hash:
        raise ValueError("Historical assembly is incomplete or its video hash changed")
    source_record_hash = sha256_path(source_assembly_record)
    if actual_hash is None or source_record_hash is None:
        raise RuntimeError("Could not hash historical assembly evidence")

    settings = Settings()
    frame_count, frame_rate = _video_frame_details(source_video, settings.ffprobe_binary)
    job_id = datetime.now(UTC).strftime("import-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    directory = _job_path(job_id)
    directory.mkdir(parents=True)
    try:
        imported_video = directory / "final-video.mp4"
        _link_or_copy(source_video, imported_video)
        imported_source_record = directory / "source-assembly.json"
        _link_or_copy(source_assembly_record, imported_source_record)
        dependency_digest = hashlib.sha256(
            (
                "director-demo-imported-assembly/1\n"
                + source_record_hash
                + "\n"
                + actual_hash
            ).encode()
        ).hexdigest()
        _atomic_json(
            directory / "final-video.assembly.json",
            {
                "schema_version": "imported-1.0",
                "project_id": job_id,
                "status": "completed",
                "dependency_digest": dependency_digest,
                "output": {"path": "final-video.mp4", "sha256": actual_hash},
                "source_assembly_record": {
                    "path": "source-assembly.json",
                    "sha256": source_record_hash,
                },
            },
        )
        now = datetime.now(UTC).isoformat()
        clip_count = max(1, len(source_record.get("clips") or []))
        job = {
            "job_id": job_id,
            "job_type": "imported_assembly",
            "status": "completed",
            "stage": "Imported immutable assembly",
            "created_at": now,
            "updated_at": now,
            "completed_at": now,
            "title": title,
            "prompt": prompt_summary,
            "references": [],
            "clips": clip_count,
            "duration_seconds": round(frame_count / frame_rate, 3),
            "seed": 0,
            "settings": {
                "width": 1024,
                "height": 576,
                "frame_rate": frame_rate,
                "frames_per_clip": None,
                "offload": "historical import",
                "max_batch_size": 1,
                "join": "preserved from source assembly",
            },
            "completed_clips": clip_count,
            "compiled_prompts": {},
            "progress": {
                "overall_percent": 100.0,
                "phase": "completed",
                "message": "Imported immutable assembly",
            },
            "final_video": "final-video.mp4",
            "error": None,
            "imported_from": {
                "video": str(source_video),
                "assembly_record": str(source_assembly_record),
                "source_record_sha256": source_record_hash,
            },
        }
        _atomic_json(directory / "job.json", job)
    except Exception:
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return _job_for_api(job_id)


def open_job_folder(job_id: str) -> None:
    directory = _job_path(job_id)
    if directory.is_symlink() or directory.parent.resolve() != JOBS_ROOT.resolve():
        raise ValueError("invalid job directory")
    if not (directory / "job.json").is_file():
        raise FileNotFoundError("job not found")
    completed = subprocess.run(
        ["open", str(directory.resolve())], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "Could not open the job folder")


def delete_job(job_id: str) -> None:
    directory = _job_path(job_id)
    if directory.is_symlink() or directory.parent.resolve() != JOBS_ROOT.resolve():
        raise ValueError("invalid job directory")
    job = _read_job(job_id)
    if job.get("status") in {"queued", "running", "cancelling"}:
        raise ValueError("A queued or running job cannot be deleted")
    children = []
    for candidate in JOBS_ROOT.glob("*/job.json"):
        if candidate.parent.name == job_id:
            continue
        try:
            child = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if child.get("parent_job_id") == job_id:
            children.append(str(child.get("job_id", candidate.parent.name)))
    if children:
        raise ValueError(
            "This run is an immutable parent of extension run(s): " + ", ".join(sorted(children))
        )
    shutil.rmtree(directory)


def cancel_job(job_id: str) -> dict[str, Any]:
    job = _read_job(job_id)
    status = str(job.get("status"))
    if status == "queued":
        _cancel_event(job_id).set()
        progress = dict(job.get("progress") or {})
        progress.update({"phase": "cancelled", "message": "Cancelled before rendering"})
        return _update_job(
            job_id,
            status="cancelled",
            stage="Cancelled before rendering",
            progress=progress,
            completed_at=datetime.now(UTC).isoformat(),
        )
    if status in {"running", "cancelling"}:
        _cancel_event(job_id).set()
        progress = dict(job.get("progress") or {})
        progress.update({"phase": "cancelling", "message": "Stopping renderer safely"})
        return _update_job(
            job_id,
            status="cancelling",
            stage="Cancelling generation…",
            progress=progress,
        )
    raise ValueError("Only a queued or running job can be cancelled")


def _parse_byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    if not header:
        return None
    if size <= 0 or not header.startswith("bytes=") or "," in header:
        raise ValueError("unsupported byte range")
    value = header[6:].strip()
    if "-" not in value:
        raise ValueError("invalid byte range")
    start_text, end_text = value.split("-", 1)
    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            raise ValueError("invalid byte range")
        start = max(0, size - suffix)
        return start, size - 1
    start = int(start_text)
    end = int(end_text) if end_text else size - 1
    if start < 0 or start >= size or end < start:
        raise ValueError("byte range outside file")
    return start, min(end, size - 1)


def _extract_frame(source: Path, frame: int, output: Path, ffmpeg_binary: str) -> None:
    completed = subprocess.run(
        [
            ffmpeg_binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-fps_mode",
            "vfr",
            "-frames:v",
            "1",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not output.is_file():
        raise RuntimeError(completed.stderr.strip() or "Could not extract boundary frame")


def _progress_payload(event: LtxProgress, clip_index: int, clip_count: int) -> dict[str, Any]:
    ratio = 0.0
    if event.current is not None and event.total:
        ratio = min(1.0, max(0.0, event.current / event.total))
    if event.phase == "prompt_encoding":
        clip_fraction = 0.03
    elif event.phase == "base_denoise":
        clip_fraction = 0.05 + 0.50 * ratio
    elif event.phase == "refinement_preparing":
        clip_fraction = 0.56
    elif event.phase == "refinement":
        clip_fraction = 0.58 + 0.32 * ratio
    elif event.phase == "video_decode":
        clip_fraction = 0.92
    elif event.phase == "audio_decode":
        clip_fraction = 0.96 + 0.02 * ratio
    elif event.phase == "validation":
        clip_fraction = 0.99
    else:
        clip_fraction = 0.01
    overall = ((clip_index - 1 + clip_fraction) / clip_count) * 98.0
    return {
        "overall_percent": round(overall, 1),
        "clip_percent": round(clip_fraction * 100.0, 1),
        "clip_index": clip_index,
        "phase": event.phase,
        "message": event.message,
        "step_current": event.current,
        "step_total": event.total,
    }


def _job_references(job: dict[str, Any]) -> list[dict[str, Any]]:
    references = job.get("references")
    if isinstance(references, list) and references:
        return cast(list[dict[str, Any]], references)
    return [
        {
            "id": "start-frame",
            "file": str(job["reference"]),
            "position_percent": 0.0,
            "strength": 1.0,
        }
    ]


def _reference_clip_frame(
    position_percent: float, *, clips: int, frames_per_clip: int
) -> tuple[int, int]:
    span = frames_per_clip - 1
    global_frame = round(position_percent / 100 * clips * span)
    if global_frame > 0 and global_frame % span == 0:
        return global_frame // span - 1, span
    return min(global_frame // span, clips - 1), global_frame % span


def _clip_conditionings(
    job: dict[str, Any], directory: Path, clip_index: int, boundary: Path | None
) -> tuple[LtxImageConditioning, ...]:
    clips = int(job["clips"])
    frames = int(job["settings"]["frames_per_clip"])
    conditionings: list[LtxImageConditioning] = []
    if boundary is not None:
        conditionings.append(
            LtxImageConditioning(
                reference_id=f"continuity-{clip_index + 1}",
                path=boundary,
                frame_index=0,
            )
        )
    for reference in _job_references(job):
        target_clip, target_frame = _reference_clip_frame(
            float(reference["position_percent"]), clips=clips, frames_per_clip=frames
        )
        if target_clip != clip_index:
            continue
        conditionings.append(
            LtxImageConditioning(
                reference_id=str(reference["id"]),
                path=directory / str(reference["file"]),
                frame_index=target_frame,
                strength=float(reference.get("strength", 1.0)),
            )
        )
    if not conditionings:
        raise RuntimeError(f"Clip {clip_index + 1} has no image conditioning")
    return tuple(sorted(conditionings, key=lambda item: item.frame_index))


def _compile_reference_prompt(job: dict[str, Any]) -> str:
    bindings = ", ".join(
        f"@{reference['id']}={float(reference['position_percent']):g}%"
        for reference in _job_references(job)
    )
    return f"Reference timing: {bindings}. {job['prompt']}"


def _assemble_job(job_id: str, clip_paths: list[Path], boundaries: list[Path]) -> Path:
    job = _read_job(job_id)
    directory = _job_path(job_id)
    frames = int(job["settings"]["frames_per_clip"])
    fps = float(job["settings"]["frame_rate"])
    approved_boundaries: list[ApprovedBoundary] = []
    shots: list[EditorialShot] = []
    cut_clips: list[CutClip] = []
    previous_take_id: str | None = None
    extension = cast(dict[str, Any], job.get("extension") or {})
    if extension:
        parent_path = directory / str(extension["parent_assembly"]["path"])
        parent_take_id = "parent-assembly-take"
        parent_shot_id = "parent-assembly"
        parent_frames = int(extension["parent_frame_count"])
        parent_fps = float(extension["parent_frame_rate"])
        parent_take = TakeRecord(
            take_id=parent_take_id,
            shot_id=parent_shot_id,
            label=f"Immutable parent assembly {job['parent_job_id']}",
            created_at=str(job["created_at"]),
            artifact=ArtifactRef(path=Path(parent_path.name), sha256=sha256_path(parent_path) or ""),
            source_run_record=Path("extension.json"),
            review=QualityReview(
                technical=TechnicalDecision.PASS,
                creative=CreativeDecision.APPROVED,
                reviewer="Inherited selected stitched assembly",
                reviewed_at=str(job["created_at"]),
                summary="Immutable prefix selected by the user for scene extension.",
            ),
        )
        shots.append(
            EditorialShot(
                shot_id=parent_shot_id,
                number=1,
                title="Inherited stitched scene",
                takes=[parent_take],
                selected_take_id=parent_take_id,
            )
        )
        cut_clips.append(
            CutClip(
                clip_id="clip-parent-assembly",
                shot_id=parent_shot_id,
                take_id=parent_take_id,
                edit=EditDecision(source_out_frame_inclusive=parent_frames - 1),
            )
        )
        endpoint_path = directory / str(extension["endpoint_frame"]["path"])
        approved_boundaries.append(
            ApprovedBoundary(
                boundary_id="boundary-extension-start",
                artifact=ArtifactRef(
                    path=Path(endpoint_path.relative_to(directory)),
                    sha256=sha256_path(endpoint_path) or "",
                ),
                source_take_id=parent_take_id,
                source_time_seconds=(parent_frames - 1) / parent_fps,
                source_frame=parent_frames - 1,
                reviewer="Exact retained assembly endpoint extraction",
                reviewed_at=str(job["created_at"]),
                notes="Exact decoded final retained frame seeds the appended scene branch.",
            )
        )
        previous_take_id = parent_take_id

    shot_number_offset = 1 if extension else 0
    for index, clip_path in enumerate(clip_paths):
        shot_id = f"shot-{index + 1:04d}"
        take_id = f"{shot_id}-take-001"
        boundary_id: str | None
        if extension and index == 0:
            boundary_id = "boundary-extension-start"
        else:
            boundary_id = f"boundary-after-{index:04d}" if index else None
        take = TakeRecord(
            take_id=take_id,
            shot_id=shot_id,
            label=f"Generated clip {index + 1}",
            created_at=datetime.now(UTC).isoformat(),
            artifact=ArtifactRef(path=Path(clip_path.name), sha256=sha256_path(clip_path) or ""),
            parent_take_id=previous_take_id,
            conditioning_boundary_id=boundary_id,
            retake_reason=(
                "Extend the selected stitched assembly from its exact retained final frame."
                if extension and index == 0
                else "Continue the preceding exact boundary frame."
                if index
                else None
            ),
            review=QualityReview(
                technical=TechnicalDecision.PASS,
                creative=CreativeDecision.APPROVED,
                reviewer="Local app automatic draft selection",
                reviewed_at=datetime.now(UTC).isoformat(),
                summary="Technically selected for draft assembly; human creative review remains required.",
            ),
        )
        shots.append(
            EditorialShot(
                shot_id=shot_id,
                number=index + 1 + shot_number_offset,
                title=f"Generated clip {index + 1}",
                takes=[take],
                selected_take_id=take_id,
            )
        )
        if index:
            boundary_path = boundaries[index - 1]
            approved_boundaries.append(
                ApprovedBoundary(
                    boundary_id=boundary_id or "",
                    artifact=ArtifactRef(
                        path=Path(boundary_path.name), sha256=sha256_path(boundary_path) or ""
                    ),
                    source_take_id=f"shot-{index:04d}-take-001",
                    source_time_seconds=(frames - 1) / fps,
                    source_frame=frames - 1,
                    reviewer="Local app exact-frame extraction",
                    reviewed_at=datetime.now(UTC).isoformat(),
                    notes="Exact decoded final frame used for the next continuation.",
                )
            )
        edit = EditDecision(
            source_in_frame=1 if previous_take_id is not None else None,
            source_out_frame_inclusive=frames - 1,
        )
        cut_clips.append(
            CutClip(clip_id=f"clip-{index + 1:04d}", shot_id=shot_id, take_id=take_id, edit=edit)
        )
        previous_take_id = take_id
    project = EditorialProject(
        project_id=job_id,
        title=f"Local generation {job_id}",
        artifact_root=Path("."),
        boundaries=approved_boundaries,
        shots=shots,
    )
    cut = CutManifest(
        project_id=job_id,
        cut_id="automatic-hard-join",
        revision=1,
        clips=cut_clips,
        notes="Automatic draft using exact shared-frame hard joins; human review required.",
    )
    project_path = write_model(project, directory / "editorial-project.json")
    cut_path = write_model(cut, directory / "cut.json")
    output = directory / "final-video.mp4"
    assemble_cut(project_path, cut_path, output)
    return output


def process_job(job_id: str) -> None:
    settings = Settings()
    directory = _job_path(job_id)
    cancel_event = _cancel_event(job_id)
    existing = _read_job(job_id)
    if existing.get("status") == "cancelled" or cancel_event.is_set():
        return
    job = _update_job(job_id, status="running", stage="Preflight")
    renderer = NativeLtxRenderer(
        runtime_root=settings.ltx_runtime_root,
        models_root=settings.ltx_models_root,
        ffprobe_binary=settings.ffprobe_binary,
        minimum_free_gib=settings.ltx_minimum_free_gib,
    )
    clip_paths: list[Path] = []
    boundaries: list[Path] = []
    frames = int(job["settings"]["frames_per_clip"])
    boundary: Path | None = None
    is_extension = bool(job.get("extension"))
    try:
        for index in range(int(job["clips"])):
            clip_number = index + 1
            _update_job(
                job_id,
                stage=f"Preparing clip {clip_number} of {job['clips']}",
                completed_clips=index,
                progress={
                    "overall_percent": round((index / int(job["clips"])) * 98.0, 1),
                    "clip_percent": 0.0,
                    "clip_index": clip_number,
                    "phase": "preparing",
                    "message": "Starting renderer",
                    "step_current": None,
                    "step_total": None,
                },
            )
            output = directory / f"clip-{index + 1:04d}.mp4"
            prompt = _compile_reference_prompt(job)
            if index or is_extension:
                prompt = (
                    "The action continues directly from the conditioning frame without a pose, "
                    "expression, framing, camera, or audio reset. " + prompt
                )
            conditionings = _clip_conditionings(job, directory, index, boundary)
            latest_job = _read_job(job_id)
            compiled_prompts = dict(latest_job.get("compiled_prompts") or {})
            compiled_prompts[str(clip_number)] = prompt
            _update_job(job_id, compiled_prompts=compiled_prompts)

            def report_progress(event: LtxProgress, *, current_clip: int = clip_number) -> None:
                if cancel_event.is_set():
                    return
                _update_job(
                    job_id,
                    stage=f"Clip {current_clip} of {job['clips']}: {event.message}",
                    progress=_progress_payload(event, current_clip, int(job["clips"])),
                )

            renderer.render(
                LtxRenderSpec(
                    image=conditionings[0].path,
                    prompt=prompt,
                    output=output,
                    width=1024,
                    height=576,
                    frames=frames,
                    frame_rate=24.0,
                    seed=int(job["seed"]),
                    offload="disk",
                    max_batch_size=1,
                    image_conditionings=conditionings,
                    parent_take_id=(
                        "parent-assembly-take"
                        if is_extension and index == 0
                        else f"shot-{index:04d}-take-001"
                        if index
                        else None
                    ),
                    conditioning_boundary_id=(
                        "boundary-extension-start"
                        if is_extension and index == 0
                        else f"boundary-after-{index:04d}"
                        if index
                        else None
                    ),
                    retake_reason=(
                        "Extend the selected stitched assembly from its exact retained final frame."
                        if is_extension and index == 0
                        else "Continue the preceding exact boundary frame."
                        if index
                        else None
                    ),
                ),
                event_log=directory / "events.jsonl",
                label=f"Local app clip {index + 1}",
                tags=("local-app", "exact-hard-join"),
                progress_callback=report_progress,
                cancel_requested=cancel_event.is_set,
            )
            clip_paths.append(output)
            _update_job(
                job_id,
                stage=(
                    f"Extracting continuation frame after clip {clip_number}"
                    if index < int(job["clips"]) - 1
                    else "Preparing final assembly"
                ),
                completed_clips=clip_number,
                progress={
                    "overall_percent": round((clip_number / int(job["clips"])) * 98.0, 1),
                    "clip_percent": 100.0,
                    "clip_index": clip_number,
                    "phase": "clip_complete",
                    "message": "Clip rendered and validated",
                    "step_current": None,
                    "step_total": None,
                },
            )
            if index < int(job["clips"]) - 1:
                boundary = directory / f"boundary-after-{index + 1:04d}.png"
                _extract_frame(output, frames - 1, boundary, settings.ffmpeg_binary)
                boundaries.append(boundary)
        _update_job(
            job_id,
            stage="Assembling exact-frame hard joins",
            completed_clips=len(clip_paths),
            progress={
                "overall_percent": 99.0,
                "clip_percent": 100.0,
                "clip_index": len(clip_paths),
                "phase": "assembly",
                "message": "Assembling final video",
                "step_current": None,
                "step_total": None,
            },
        )
        final_video = _assemble_job(job_id, clip_paths, boundaries)
        _update_job(
            job_id,
            status="completed",
            stage="Ready to review",
            final_video=final_video.name,
            completed_at=datetime.now(UTC).isoformat(),
            progress={
                "overall_percent": 100.0,
                "clip_percent": 100.0,
                "clip_index": len(clip_paths),
                "phase": "completed",
                "message": "Ready to review",
                "step_current": None,
                "step_total": None,
            },
        )
    except LtxCancelled:
        latest = _read_job(job_id)
        cancelled_progress = dict(latest.get("progress") or {})
        cancelled_progress.update({"phase": "cancelled", "message": "Generation cancelled"})
        _update_job(
            job_id,
            status="cancelled",
            stage="Generation cancelled",
            progress=cancelled_progress,
            completed_at=datetime.now(UTC).isoformat(),
            error=None,
        )
    except Exception as exc:
        latest = _read_job(job_id)
        failed_progress = dict(latest.get("progress") or {})
        failed_progress.update({"phase": "failed", "message": "Generation failed"})
        _update_job(
            job_id,
            status="failed",
            stage="Failed",
            error=f"{type(exc).__name__}: {exc}",
            completed_at=datetime.now(UTC).isoformat(),
            progress=failed_progress,
        )


def worker() -> None:
    while True:
        job_id = JOB_QUEUE.get()
        try:
            process_job(job_id)
        finally:
            with CANCEL_LOCK:
                CANCEL_EVENTS.pop(job_id, None)
            JOB_QUEUE.task_done()


def list_jobs() -> list[dict[str, Any]]:
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    jobs = []
    for path in JOBS_ROOT.glob("*/job.json"):
        try:
            jobs.append(_job_for_api(path.parent.name))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    queued = sorted(
        (job for job in jobs if job.get("status") == "queued"),
        key=lambda item: str(item.get("created_at", "")),
    )
    for position, job in enumerate(queued, start=1):
        job["queue_position"] = position
    return sorted(jobs, key=lambda item: str(item.get("created_at", "")), reverse=True)


HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>DirectorDemo Local</title><style>
:root{color-scheme:dark;--bg:#101412;--card:#19201d;--line:#34423b;--ink:#f4f3eb;--muted:#aab5ae;--accent:#b8df4e;--danger:#ff897d}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,#26332c,var(--bg) 42%);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui}main{max-width:1050px;margin:auto;padding:38px 22px}h1{font-size:clamp(36px,7vw,74px);line-height:.95;margin:12px 0}h1 em{color:var(--accent);font-style:normal}.intro{max-width:680px;color:var(--muted)}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:32px}.card{background:#19201ddd;border:1px solid var(--line);border-radius:20px;padding:22px;box-shadow:0 20px 70px #0005}label{display:block;margin:14px 0 6px;color:var(--muted)}textarea,input,select,button{width:100%;border:1px solid var(--line);border-radius:10px;padding:12px;background:#0d110f;color:var(--ink)}textarea{min-height:150px;resize:vertical}button{margin-top:18px;background:var(--accent);color:#111;font-weight:800;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.defaults{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.defaults small{display:block;color:var(--muted)}.reference-row{display:grid;grid-template-columns:1.4fr .8fr;gap:8px;margin-top:8px}.reference-row label{margin:0}.reference-file{grid-column:1/-1;color:var(--muted);font-size:12px;overflow-wrap:anywhere}.job{border-top:1px solid var(--line);padding:18px 0}.job:first-child{border:0}.state{color:var(--accent);font-weight:700}.progress-meta{display:flex;justify-content:space-between;gap:8px;color:var(--muted);font-size:12px}.error{color:var(--danger)}.folder{color:var(--muted);font:12px/1.4 ui-monospace,SFMono-Regular,monospace;overflow-wrap:anywhere;margin:10px 0}.actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.actions button{margin-top:4px;background:#27322d;color:var(--ink)}.actions .delete{border-color:#81443f;color:var(--danger)}.extension{margin:14px 0;padding:12px;border:1px solid var(--line);border-radius:12px;background:#111713}.extension summary{cursor:pointer;color:var(--accent);font-weight:800}.extension textarea{min-height:90px}video{width:100%;border-radius:12px;background:#000;margin-top:12px}a{color:var(--accent)}progress{width:100%}@media(max-width:760px){.grid{grid-template-columns:1fr}.defaults,.reference-row{grid-template-columns:1fr}}</style></head><body><main><p>LOCAL · ONE HEAVY WORKER · M5 32 GB PROFILE</p><h1>DirectorDemo<br><em>clip maker</em></h1><p class="intro">Upload one or more timeline references and describe motion, camera, action and sound. Editable IDs such as @start-frame bind prompt language to exact conditioned frames. Multiple clips continue from each exact final frame and use the user-approved hard join. Completed stitched scenes can be extended non-destructively from their exact retained final frame.</p><div class="grid"><section class="card"><h2>New video</h2><form id="form"><label>Reference images (1–8)</label><input id="image" type="file" accept="image/png,image/jpeg,image/webp" multiple required><div id="reference-editor"></div><p class="intro">The first and last selected files default to 0% and 100%. Edit each ID or timeline position, then reference it in the prompt as <code>@id</code>.</p><label>Motion / camera / audio prompt</label><textarea id="prompt" required placeholder="Between @start-frame and @end-frame, the subject smiles, raises one arm, and lifts into the sky..."></textarea><div class="defaults"><label>Clips<select id="clips"><option>1</option><option>2</option><option>3</option></select></label><label>Seconds each<select id="duration"><option value="5">5 · quality default</option><option value="2">2 · faster test</option></select></label><label>Seed<input id="seed" type="number" value="42" min="0"></label></div><p class="intro">Defaults: 1024×576, 24 fps, BF16 distilled, disk offload, batch 1, exact shared-frame hard joins. Five seconds takes roughly 18 minutes per clip on this Mac.</p><button>Queue generation</button><p id="message"></p></form></section><section class="card"><h2>Runs</h2><div id="jobs">Loading…</div></section></div></main><script>
const jobs=document.querySelector('#jobs'),message=document.querySelector('#message');
const escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const imageInput=document.querySelector('#image'),referenceEditor=document.querySelector('#reference-editor');
const slug=(name,index)=>{let value=name.replace(/[.][^.]+$/,'').toLowerCase().replace(/[^a-z0-9_-]+/g,'-').replace(/^-+|-+$/g,'').slice(0,32);if(!/^[a-z]/.test(value))value=`ref-${value||index+1}`;return value.slice(0,32)};
imageInput.addEventListener('change',()=>{const files=[...imageInput.files],used=new Set();referenceEditor.innerHTML=files.map((file,index)=>{let id=slug(file.name,index),suffix=2;while(used.has(id)){id=`${slug(file.name,index).slice(0,29)}-${suffix++}`}used.add(id);const position=files.length===1?0:Math.round(index*100/(files.length-1));return `<div class="reference-row" data-index="${index}"><div class="reference-file">${escapeHtml(file.name)}</div><label>Reference ID<input class="reference-id" value="${escapeHtml(id)}" maxlength="32" pattern="[a-z][a-z0-9_-]{0,31}" required></label><label>Timeline %<input class="reference-position" type="number" min="0" max="100" step="0.1" value="${position}" required></label></div>`}).join('')});
const readFile=file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(new Error(`Could not read ${file.name}`));reader.readAsDataURL(file)});
const progressFor=j=>{if(j.progress)return j.progress;if(j.status==='completed')return {overall_percent:100,message:'Ready to review'};return {overall_percent:Math.round(100*(j.completed_clips||0)/j.clips),message:j.stage}};
const jobRenderKey=j=>JSON.stringify([j.status,j.stage,j.updated_at,j.queue_position,j.completed_clips,j.final_video,j.error]);
const jobHtml=j=>{
    const active=['queued','running','cancelling'].includes(j.status),p=progressFor(j);
    const step=p.step_total!=null?`Step ${p.step_current||0} of ${p.step_total}`:(j.status==='queued'&&j.queue_position?`Queue position ${j.queue_position}`:'');
    const progress=active?`<progress max="100" value="${p.overall_percent||0}"></progress><div class="progress-meta"><span>${Number(p.overall_percent||0).toFixed(1)}% overall</span><span>${escapeHtml(step)}</span></div>`:'';
    const actions=active?`<button type="button" data-action="open" data-job="${j.job_id}">Open folder</button><button type="button" class="delete" data-action="cancel" data-job="${j.job_id}" ${j.status==='cancelling'?'disabled':''}>${j.status==='cancelling'?'Cancelling…':'Cancel generation'}</button>`:`<button type="button" data-action="open" data-job="${j.job_id}">Open folder</button><button type="button" class="delete" data-action="delete" data-job="${j.job_id}">Delete run</button>`;
    const references=(j.references||[{id:'start-frame',position_percent:0}]).map(r=>`@${escapeHtml(r.id)} · ${Number(r.position_percent).toFixed(1)}%`).join(' · ');
    const lineage=j.parent_job_id?`<p class="intro">Extends <strong>${escapeHtml(j.parent_job_id)}</strong> · generation ${Number(j.extension?.lineage_depth||1)}</p>`:'';
    const extension=j.status==='completed'&&j.final_video?`<details class="extension"><summary>Extend scene from its exact final frame</summary><label>Continuation direction<textarea class="extension-prompt" placeholder="The action continues without resetting pose, camera or ambience…"></textarea></label><div class="defaults"><label>Clips<select class="extension-clips"><option>1</option><option>2</option><option>3</option></select></label><label>Seconds each<select class="extension-duration"><option value="5">5 · quality</option><option value="2">2 · test</option></select></label><label>Variation seed<input class="extension-seed" type="number" value="${Number(j.seed||42)+1}" min="0"></label></div><button type="button" data-action="extend" data-job="${j.job_id}">Queue extension</button><p class="intro">The selected stitched video stays immutable. Its exact retained final frame becomes the new 0% guide.</p></details>`:'';
    return `<article class="job"><strong>${escapeHtml(j.job_id)}</strong><div class="state">${escapeHtml(j.stage)}</div>${lineage}${progress}<small>${j.settings.width}×${j.settings.height} · ${j.settings.frame_rate} fps · ${j.duration_seconds}s × ${j.clips}</small><p class="intro">References: ${references}</p>${j.error?`<p class="error">${escapeHtml(j.error)}</p>`:''}${j.final_video?`<video controls preload="metadata" playsinline src="/media/${j.job_id}/${j.final_video}"></video><p><a href="/media/${j.job_id}/${j.final_video}" download>Download final MP4</a></p>`:''}${extension}<p class="folder"><strong>Saved files:</strong><br>${escapeHtml(j.folder_path)}</p><div class="actions">${actions}</div></article>`;
};
const buildJob=(j,key)=>{const template=document.createElement('template');template.innerHTML=jobHtml(j).trim();const node=template.content.firstElementChild;node.dataset.jobId=j.job_id;node.dataset.renderKey=key;return node};
let refreshing=false;
async function refresh(){
  if(refreshing)return;
  refreshing=true;
  try{
    const data=await fetch('/api/jobs',{cache:'no-store'}).then(r=>r.json());
    if(!data.length){if(jobs.textContent!=='No jobs yet.')jobs.textContent='No jobs yet.';return}
    const existing=new Map([...jobs.querySelectorAll('article.job[data-job-id]')].map(node=>[node.dataset.jobId,node]));
    if(!existing.size)jobs.textContent='';
    let cursor=jobs.firstElementChild;
    for(const j of data){
      const key=jobRenderKey(j),old=existing.get(j.job_id);
      let node=old;
      if(!node||node.dataset.renderKey!==key){
        node=buildJob(j,key);
        if(old){if(cursor===old)cursor=node;old.replaceWith(node)}
      }
      if(node!==cursor)jobs.insertBefore(node,cursor);
      cursor=node.nextElementSibling;
      existing.delete(j.job_id);
    }
    for(const node of existing.values())node.remove();
  }finally{refreshing=false}
}
setInterval(refresh,3000);refresh();
jobs.addEventListener('click',async e=>{
  const button=e.target.closest('button[data-action]');if(!button||button.disabled)return;
  const id=button.dataset.job,action=button.dataset.action;
  if(action==='delete'&&!confirm(`Delete run ${id} and every unshared file in its folder? Parent runs with extensions remain protected.`))return;
  if(action==='cancel'&&!confirm(`Cancel generation ${id}? Validated completed clips will remain.`))return;
  button.disabled=true;
  try{
    if(action==='extend'){
      const panel=button.closest('.extension'),prompt=panel.querySelector('.extension-prompt').value.trim();
      if(!prompt)throw new Error('Describe how the scene should continue.');
      const body={prompt,clips:Number(panel.querySelector('.extension-clips').value),duration:Number(panel.querySelector('.extension-duration').value),seed:Number(panel.querySelector('.extension-seed').value)};
      const response=await fetch(`/api/jobs/${encodeURIComponent(id)}/extend`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
      const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not queue extension');
      message.textContent=`Queued extension ${result.job_id} from ${id}.`;
    }else{
      const suffix=action==='open'?'open-folder':action==='cancel'?'cancel':'',method=action==='delete'?'DELETE':'POST';
      const response=await fetch(`/api/jobs/${encodeURIComponent(id)}/${suffix}`,{method});const result=await response.json();
      if(!response.ok)throw new Error(result.error||'Action failed');
      message.textContent=action==='open'?'Opened run folder in Finder.':action==='cancel'?'Cancellation requested.':'Run and its files deleted.';
    }
    await refresh();
  }catch(error){message.textContent=error.message;button.disabled=false}
});
document.querySelector('#form').addEventListener('submit',async e=>{e.preventDefault();message.textContent='Uploading references…';try{const files=[...imageInput.files],rows=[...referenceEditor.querySelectorAll('.reference-row')];const images=await Promise.all(rows.map(async row=>{const file=files[Number(row.dataset.index)];return {id:row.querySelector('.reference-id').value.trim().toLowerCase(),position_percent:Number(row.querySelector('.reference-position').value),name:file.name,image_type:file.type,image_data:await readFile(file)}}));const body={prompt:document.querySelector('#prompt').value,images,clips:Number(document.querySelector('#clips').value),duration:Number(document.querySelector('#duration').value),seed:Number(document.querySelector('#seed').value)};const response=await fetch('/api/jobs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const result=await response.json();message.textContent=response.ok?'Queued '+result.job_id:(result.error||'Could not queue');refresh()}catch(error){message.textContent=error.message}});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_media(self, *, send_body: bool) -> None:
        parts = [unquote(part) for part in urlparse(self.path).path.split("/") if part]
        if len(parts) != 3 or parts[0] != "media":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            root = _job_path(parts[1]).resolve()
            source = (root / parts[2]).resolve()
            source.relative_to(root)
        except (ValueError, OSError):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not source.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        size = source.stat().st_size
        try:
            requested = _parse_byte_range(self.headers.get("Range"), size)
        except (ValueError, TypeError):
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        start, end = requested if requested else (0, size - 1)
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if requested else HTTPStatus.OK)
        self.send_header(
            "Content-Type", mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        )
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Disposition", f'inline; filename="{source.name}"')
        if requested:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if not send_body:
            return
        try:
            with source.open("rb") as stream:
                stream.seek(start)
                remaining = length
                while remaining:
                    chunk = stream.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # Browsers routinely abandon one range when seeking to another.
            return

    def do_HEAD(self) -> None:
        if urlparse(self.path).path.startswith("/media/"):
            self._serve_media(send_body=False)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/health":
            self._json({"ok": True})
            return
        if parsed.path == "/api/jobs":
            self._json(list_jobs())
            return
        if parsed.path.startswith("/media/"):
            self._serve_media(send_body=True)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed_path = urlparse(self.path).path
        parts = [unquote(part) for part in parsed_path.split("/") if part]
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "extend":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise ValueError("Request is empty or too large")
                payload = json.loads(self.rfile.read(length))
                self._json(create_extension_job(parts[2], payload), HTTPStatus.ACCEPTED)
            except FileNotFoundError as exc:
                self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, TypeError, json.JSONDecodeError, RuntimeError, OSError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "open-folder":
            try:
                open_job_folder(parts[2])
                self._json({"ok": True})
            except FileNotFoundError as exc:
                self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, RuntimeError, OSError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cancel":
            try:
                self._json(cancel_job(parts[2]), HTTPStatus.ACCEPTED)
            except FileNotFoundError as exc:
                self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
            except (ValueError, OSError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
            return
        if parsed_path != "/api/jobs":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("Request is empty or too large")
            payload = json.loads(self.rfile.read(length))
            self._json(create_job(payload), HTTPStatus.ACCEPTED)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:
        parts = [unquote(part) for part in urlparse(self.path).path.split("/") if part]
        if len(parts) != 3 or parts[:2] != ["api", "jobs"]:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            delete_job(parts[2])
            self._json({"ok": True})
        except FileNotFoundError as exc:
            self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (ValueError, OSError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.CONFLICT)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[local-app] {self.address_string()} {format % args}")


def main() -> None:
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    for job in list_jobs():
        if job.get("status") in {"queued", "running", "cancelling"}:
            _update_job(str(job["job_id"]), status="interrupted", stage="Restart required", error="App stopped before completion; create a new job.")
    threading.Thread(target=worker, daemon=True, name="director-render-worker").start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"DirectorDemo local app: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
