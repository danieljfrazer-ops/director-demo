from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, model_validator

from director_demo.runs import sha256_path
from director_demo.schemas import StrictModel


class EditorialError(RuntimeError):
    """Raised when an editorial project or cut violates a durable workflow rule."""


class QualityRating(StrEnum):
    UNKNOWN = "unknown"
    PASS = "pass"
    MINOR = "minor"
    FAIL = "fail"


class TechnicalDecision(StrEnum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"


class CreativeDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    APPROVED_WITH_EDIT = "approved_with_edit"
    REJECTED = "rejected"


class CutState(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    RENDERED = "rendered"
    STALE = "stale"


class DeliveryDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ArtifactRef(StrictModel):
    path: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class QualityReview(StrictModel):
    technical: TechnicalDecision = TechnicalDecision.PENDING
    creative: CreativeDecision = CreativeDecision.PENDING
    eyes: QualityRating = QualityRating.UNKNOWN
    mouth_teeth: QualityRating = QualityRating.UNKNOWN
    identity: QualityRating = QualityRating.UNKNOWN
    anatomy: QualityRating = QualityRating.UNKNOWN
    motion: QualityRating = QualityRating.UNKNOWN
    audio: QualityRating = QualityRating.UNKNOWN
    lip_sync: QualityRating = QualityRating.UNKNOWN
    reviewer: str | None = None
    reviewed_at: str | None = None
    summary: str = ""
    defects: list[str] = Field(default_factory=list)


class ApprovedBoundary(StrictModel):
    boundary_id: str = Field(min_length=1)
    artifact: ArtifactRef
    source_take_id: str = Field(min_length=1)
    source_time_seconds: float = Field(ge=0)
    source_frame: int | None = Field(default=None, ge=0)
    decision: Literal["approved"] = "approved"
    reviewer: str = Field(min_length=1)
    reviewed_at: str
    notes: str = ""


class TakeRecord(StrictModel):
    take_id: str = Field(min_length=1)
    shot_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    created_at: str
    artifact: ArtifactRef
    source_run_record: Path | None = None
    parent_take_id: str | None = None
    conditioning_boundary_id: str | None = None
    retake_reason: str | None = None
    review: QualityReview = Field(default_factory=QualityReview)

    @model_validator(mode="after")
    def validate_lineage(self) -> TakeRecord:
        if self.parent_take_id is not None and not (self.retake_reason or "").strip():
            raise ValueError("a retake with a parent must record its retake reason")
        return self


class EditorialShot(StrictModel):
    shot_id: str = Field(min_length=1)
    number: int = Field(ge=1)
    title: str = Field(min_length=1)
    takes: list[TakeRecord] = Field(min_length=1)
    selected_take_id: str | None = None

    @model_validator(mode="after")
    def validate_takes(self) -> EditorialShot:
        ids = [take.take_id for take in self.takes]
        if len(ids) != len(set(ids)):
            raise ValueError(f"shot {self.shot_id} has duplicate take IDs")
        if any(take.shot_id != self.shot_id for take in self.takes):
            raise ValueError(f"shot {self.shot_id} contains a take owned by another shot")
        if self.selected_take_id is not None:
            try:
                selected = next(
                    take for take in self.takes if take.take_id == self.selected_take_id
                )
            except StopIteration:
                raise ValueError(f"selected take {self.selected_take_id} is not in shot") from None
            if selected.review.technical != TechnicalDecision.PASS:
                raise ValueError("selected take must pass technical review")
            if selected.review.creative not in {
                CreativeDecision.APPROVED,
                CreativeDecision.APPROVED_WITH_EDIT,
            }:
                raise ValueError("selected take must be creatively approved")
        return self


class EditorialProject(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    artifact_root: Path = Path(".")
    source_production_manifest: ArtifactRef | None = None
    boundaries: list[ApprovedBoundary] = Field(default_factory=list)
    shots: list[EditorialShot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_shots(self) -> EditorialProject:
        numbers = [shot.number for shot in self.shots]
        if numbers != sorted(numbers) or len(numbers) != len(set(numbers)):
            raise ValueError("editorial shot numbers must be unique and ordered")
        ids = [shot.shot_id for shot in self.shots]
        if len(ids) != len(set(ids)):
            raise ValueError("editorial shot IDs must be unique")
        all_take_ids = [take.take_id for shot in self.shots for take in shot.takes]
        if len(all_take_ids) != len(set(all_take_ids)):
            raise ValueError("take IDs must be unique across the project")
        takes_by_id = {
            take.take_id: take for shot in self.shots for take in shot.takes
        }
        for take in takes_by_id.values():
            if take.parent_take_id is not None and take.parent_take_id not in takes_by_id:
                raise ValueError(f"parent take is unknown: {take.parent_take_id}")
            if take.parent_take_id == take.take_id:
                raise ValueError(f"take cannot be its own parent: {take.take_id}")
        for take in takes_by_id.values():
            visited = {take.take_id}
            parent_id = take.parent_take_id
            while parent_id is not None:
                if parent_id in visited:
                    raise ValueError(f"take lineage contains a cycle at: {parent_id}")
                visited.add(parent_id)
                parent_id = takes_by_id[parent_id].parent_take_id
        boundary_ids = [boundary.boundary_id for boundary in self.boundaries]
        if len(boundary_ids) != len(set(boundary_ids)):
            raise ValueError("conditioning boundary IDs must be unique")
        for boundary in self.boundaries:
            if boundary.source_take_id not in all_take_ids:
                raise ValueError(
                    f"conditioning boundary source take is unknown: {boundary.source_take_id}"
                )
        for shot in self.shots:
            for take in shot.takes:
                if (
                    take.conditioning_boundary_id is not None
                    and take.conditioning_boundary_id not in boundary_ids
                ):
                    raise ValueError(
                        f"conditioning boundary is unknown: {take.conditioning_boundary_id}"
                    )
        return self


class EditDecision(StrictModel):
    source_in_seconds: float = Field(default=0.0, ge=0)
    source_out_seconds: float | None = Field(default=None, gt=0)
    source_in_frame: int | None = Field(default=None, ge=0)
    source_out_frame_inclusive: int | None = Field(default=None, ge=0)
    fade_in_seconds: float = Field(default=0.0, ge=0)
    fade_out_seconds: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> EditDecision:
        if (
            self.source_out_seconds is not None
            and self.source_out_seconds <= self.source_in_seconds
        ):
            raise ValueError("source out must be later than source in")
        if self.source_in_frame is not None and self.source_in_seconds != 0:
            raise ValueError("source in must use seconds or frames, not both")
        if (
            self.source_out_frame_inclusive is not None
            and self.source_out_seconds is not None
        ):
            raise ValueError("source out must use seconds or frames, not both")
        if (
            self.source_in_frame is not None
            and self.source_out_frame_inclusive is not None
            and self.source_out_frame_inclusive < self.source_in_frame
        ):
            raise ValueError("inclusive source out frame must not precede source in frame")
        return self

    @property
    def changes_source(self) -> bool:
        return any(
            (
                self.source_in_seconds > 0,
                self.source_out_seconds is not None,
                self.source_in_frame is not None,
                self.source_out_frame_inclusive is not None,
                self.fade_in_seconds > 0,
                self.fade_out_seconds > 0,
            )
        )


class TransitionDecision(StrictModel):
    kind: Literal["cut", "dissolve"] = "cut"
    duration_frames: int = Field(default=0, ge=0)
    audio: Literal["cut", "equal_power_crossfade"] = "cut"

    @model_validator(mode="after")
    def validate_transition(self) -> TransitionDecision:
        if self.kind == "cut" and self.duration_frames != 0:
            raise ValueError("a cut transition cannot have overlap frames")
        if self.kind == "cut" and self.audio != "cut":
            raise ValueError("a cut transition cannot crossfade audio")
        if self.kind == "dissolve" and self.duration_frames == 0:
            raise ValueError("a dissolve transition requires overlap frames")
        if self.kind == "dissolve" and self.audio != "equal_power_crossfade":
            raise ValueError("a dissolve requires an equal-power audio crossfade")
        return self


class CutClip(StrictModel):
    clip_id: str = Field(min_length=1)
    shot_id: str = Field(min_length=1)
    take_id: str = Field(min_length=1)
    edit: EditDecision = Field(default_factory=EditDecision)
    transition_to_next: TransitionDecision = Field(default_factory=TransitionDecision)


class DeliveryProfile(StrictModel):
    width: int = Field(default=1024, gt=0, multiple_of=2)
    height: int = Field(default=576, gt=0, multiple_of=2)
    frame_rate: float = Field(default=24.0, gt=0)
    audio_sample_rate: int = Field(default=48_000, gt=0)
    video_codec: Literal["libx264"] = "libx264"
    audio_codec: Literal["aac"] = "aac"
    crf: int = Field(default=18, ge=0, le=51)
    preset: str = "medium"
    resolution_provenance: Literal["native", "normalized", "upscaled"] = "normalized"


class DeliveryReview(StrictModel):
    decision: DeliveryDecision = DeliveryDecision.PENDING
    reviewer: str | None = None
    reviewed_at: str | None = None
    picture: QualityRating = QualityRating.UNKNOWN
    cut_audio: QualityRating = QualityRating.UNKNOWN
    captions: QualityRating = QualityRating.UNKNOWN
    loudness: QualityRating = QualityRating.UNKNOWN
    summary: str = ""


class CutManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str = Field(min_length=1)
    cut_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    state: CutState = CutState.DRAFT
    clips: list[CutClip] = Field(min_length=1)
    delivery: DeliveryProfile = Field(default_factory=DeliveryProfile)
    notes: str = ""

    @model_validator(mode="after")
    def validate_clips(self) -> CutManifest:
        ids = [clip.clip_id for clip in self.clips]
        if len(ids) != len(set(ids)):
            raise ValueError("cut clip IDs must be unique")
        if self.clips[-1].transition_to_next.kind != "cut":
            raise ValueError("the final clip cannot transition to a missing next clip")
        return self


class ResolvedClip(StrictModel):
    clip_id: str
    shot_id: str
    take_id: str
    path: Path
    sha256: str
    conditioning_sha256: str | None = None
    source_duration_seconds: float
    output_duration_seconds: float
    source_in_seconds: float = 0.0
    source_out_seconds: float | None = None
    source_frame_rate: float | None = None
    edit: EditDecision
    transition_to_next: TransitionDecision = Field(default_factory=TransitionDecision)


class AssemblyRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    cut_id: str
    cut_revision: int
    dependency_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["completed"] = "completed"
    created_at: str
    source_project_manifest: ArtifactRef
    source_cut_manifest: ArtifactRef
    clips: list[ResolvedClip]
    output: ArtifactRef
    media: dict[str, Any]
    delivery_review: DeliveryReview = Field(default_factory=DeliveryReview)


class AssemblyFreshness(StrictModel):
    fresh: bool
    provenance_current: bool
    dependency_match: bool
    output_match: bool
    delivery_valid: bool
    delivery_error: str | None = None
    project_manifest_match: bool
    cut_manifest_match: bool
    current_dependency_digest: str


def load_editorial_project(path: Path) -> EditorialProject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EditorialProject.model_validate(_migrate_editorial_project(payload))


def _migrate_editorial_project(payload: dict[str, Any]) -> dict[str, Any]:
    """Read early 1.0 snapshots without rewriting immutable provenance evidence."""

    migrated = copy.deepcopy(payload)
    boundaries = migrated.setdefault("boundaries", [])
    known_boundary_ids = {
        item["boundary_id"] for item in boundaries if "boundary_id" in item
    }
    for shot in migrated.get("shots", []):
        for take in shot.get("takes", []):
            legacy = take.pop("conditioning_boundary", None)
            if legacy is None:
                continue
            boundary_id = legacy["boundary_id"]
            if boundary_id not in known_boundary_ids:
                boundaries.append(legacy)
                known_boundary_ids.add(boundary_id)
            if take.get("conditioning_boundary_id") is None:
                take["conditioning_boundary_id"] = boundary_id
    return migrated


def load_cut_manifest(path: Path) -> CutManifest:
    return CutManifest.model_validate_json(path.read_text(encoding="utf-8"))


def register_take(
    project: EditorialProject,
    shot_id: str,
    take: TakeRecord,
) -> EditorialProject:
    """Append one immutable take without changing selection or prior takes."""

    if any(take.take_id == item.take_id for shot in project.shots for item in shot.takes):
        raise EditorialError(f"take ID already exists: {take.take_id}")
    if take.shot_id != shot_id:
        raise EditorialError("take belongs to a different shot")
    found = False
    shots: list[EditorialShot] = []
    for shot in project.shots:
        if shot.shot_id == shot_id:
            found = True
            shots.append(shot.model_copy(update={"takes": [*shot.takes, take]}))
        else:
            shots.append(shot)
    if not found:
        raise EditorialError(f"unknown shot: {shot_id}")
    return EditorialProject.model_validate(
        project.model_copy(update={"shots": shots}).model_dump(mode="python")
    )


def update_take_review(
    project: EditorialProject,
    shot_id: str,
    take_id: str,
    review: QualityReview,
) -> EditorialProject:
    """Replace review metadata while protecting an already selected take."""

    found = False
    shots: list[EditorialShot] = []
    for shot in project.shots:
        if shot.shot_id != shot_id:
            shots.append(shot)
            continue
        takes: list[TakeRecord] = []
        for take in shot.takes:
            if take.take_id == take_id:
                found = True
                if shot.selected_take_id == take_id and (
                    review.technical != TechnicalDecision.PASS
                    or review.creative
                    not in {CreativeDecision.APPROVED, CreativeDecision.APPROVED_WITH_EDIT}
                ):
                    raise EditorialError(
                        "clear or replace selection before rejecting its selected take"
                    )
                takes.append(take.model_copy(update={"review": review}))
            else:
                takes.append(take)
        shots.append(shot.model_copy(update={"takes": takes}))
    if not found:
        raise EditorialError(f"unknown take: {take_id}")
    return EditorialProject.model_validate(
        project.model_copy(update={"shots": shots}).model_dump(mode="python")
    )


def select_take(
    project: EditorialProject,
    shot_id: str,
    take_id: str | None,
) -> EditorialProject:
    """Select one approved take or explicitly clear a shot's selection."""

    found = False
    shots: list[EditorialShot] = []
    for shot in project.shots:
        if shot.shot_id == shot_id:
            found = True
            shots.append(shot.model_copy(update={"selected_take_id": take_id}))
        else:
            shots.append(shot)
    if not found:
        raise EditorialError(f"unknown shot: {shot_id}")
    return EditorialProject.model_validate(
        project.model_copy(update={"shots": shots}).model_dump(mode="python")
    )


def write_model(model: StrictModel, path: Path) -> Path:
    """Atomically write a versioned domain document."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(model.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def export_editorial_history(
    projects_root: Path,
    outputs_root: Path,
    public_root: Path,
) -> Path:
    """Export validated editorial manifests and hard-linked media for the local UI."""

    media_root = public_root / "editorial-media"
    media_root.mkdir(parents=True, exist_ok=True)
    projects: list[dict[str, Any]] = []
    cuts: list[dict[str, Any]] = []
    assemblies: list[dict[str, Any]] = []
    project_heads: dict[str, Path] = {}
    cut_heads: dict[tuple[str, str, int], Path] = {}

    for manifest_path in sorted(projects_root.rglob("editorial-project.json")):
        project = load_editorial_project(manifest_path)
        item = project.model_dump(mode="json")
        item["manifest_path"] = str(manifest_path.resolve())
        project_heads[project.project_id] = manifest_path
        artifact_root = (manifest_path.parent / project.artifact_root).resolve()
        for shot in item["shots"]:
            for take in shot["takes"]:
                source = _safe_artifact_path(artifact_root, Path(take["artifact"]["path"]))
                take["artifact"]["url"] = _expose_media(
                    source, media_root, f"take-{take['take_id']}"
                )
        projects.append(item)

    for cut_path in sorted(projects_root.rglob("cut-*.json")):
        cut = load_cut_manifest(cut_path)
        item = cut.model_dump(mode="json")
        item["manifest_path"] = str(cut_path.resolve())
        cut_heads[(cut.project_id, cut.cut_id, cut.revision)] = cut_path
        cuts.append(item)

    for record_path in sorted(outputs_root.rglob("*.assembly.json")):
        record = AssemblyRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
        item = record.model_dump(mode="json")
        item["record_path"] = str(record_path.resolve())
        project_path = project_heads.get(
            record.project_id,
            _resolve_record_path(record.source_project_manifest.path),
        )
        cut_path = cut_heads.get(
            (record.project_id, record.cut_id, record.cut_revision),
            _resolve_record_path(record.source_cut_manifest.path),
        )
        item["freshness"] = check_assembly_freshness(
            record, project_path, cut_path
        ).model_dump(mode="json")
        source = record.output.path
        if not source.is_absolute():
            source = (Path.cwd() / source).resolve()
        item["output"]["url"] = _expose_media(
            source, media_root, f"cut-{record.cut_id}-r{record.cut_revision}"
        )
        assemblies.append(item)

    output = public_root / "editorial.json"
    output.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "projects": projects,
                "cuts": cuts,
                "assemblies": assemblies,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def resolve_cut(
    project: EditorialProject,
    cut: CutManifest,
    *,
    project_manifest_path: Path,
    ffprobe_binary: str = "ffprobe",
) -> list[ResolvedClip]:
    """Resolve selected immutable take artifacts and validate every dependency."""

    if project.project_id != cut.project_id:
        raise EditorialError("cut belongs to a different project")
    artifact_root = (project_manifest_path.parent / project.artifact_root).resolve()
    resolved: list[ResolvedClip] = []
    for clip in cut.clips:
        try:
            shot = next(item for item in project.shots if item.shot_id == clip.shot_id)
        except StopIteration:
            raise EditorialError(f"unknown shot in cut: {clip.shot_id}") from None
        if shot.selected_take_id != clip.take_id:
            raise EditorialError(
                f"cut clip {clip.clip_id} does not reference shot {clip.shot_id}'s selected take"
            )
        take = next(item for item in shot.takes if item.take_id == clip.take_id)
        if (
            take.review.creative == CreativeDecision.APPROVED_WITH_EDIT
            and not clip.edit.changes_source
        ):
            raise EditorialError(
                f"take {take.take_id} is approved only with an explicit edit decision"
            )
        source = _safe_artifact_path(artifact_root, take.artifact.path)
        actual_hash = sha256_path(source)
        if actual_hash is None:
            raise EditorialError(f"take artifact is missing: {source}")
        if actual_hash != take.artifact.sha256:
            raise EditorialError(f"take artifact hash changed: {take.take_id}")
        conditioning_hash: str | None = None
        if take.conditioning_boundary_id is not None:
            boundary = next(
                item
                for item in project.boundaries
                if item.boundary_id == take.conditioning_boundary_id
            )
            conditioning_path = _safe_artifact_path(
                artifact_root, boundary.artifact.path
            )
            conditioning_hash = sha256_path(conditioning_path)
            if conditioning_hash is None:
                raise EditorialError(
                    f"conditioning artifact is missing for take {take.take_id}"
                )
            if conditioning_hash != boundary.artifact.sha256:
                raise EditorialError(
                    f"conditioning artifact hash changed for take {take.take_id}"
                )
        media = probe_media(source, ffprobe_binary=ffprobe_binary)
        source_duration = float(media["format"]["duration"])
        streams = media.get("streams", [])
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"), None
        )
        if video_stream is None:
            raise EditorialError(f"clip {clip.clip_id} has no video stream")
        if not any(stream.get("codec_type") == "audio" for stream in streams):
            raise EditorialError(f"clip {clip.clip_id} has no audio stream")
        source_frame_rate = float(
            Fraction(str(video_stream.get("avg_frame_rate", "0/1")))
        )
        if source_frame_rate <= 0:
            raise EditorialError(f"clip {clip.clip_id} has an invalid video frame rate")
        source_in = (
            clip.edit.source_in_frame / source_frame_rate
            if clip.edit.source_in_frame is not None
            else clip.edit.source_in_seconds
        )
        source_out = (
            (clip.edit.source_out_frame_inclusive + 1) / source_frame_rate
            if clip.edit.source_out_frame_inclusive is not None
            else clip.edit.source_out_seconds or source_duration
        )
        if source_out > source_duration + 0.01:
            raise EditorialError(
                f"clip {clip.clip_id} out point exceeds source duration {source_duration:.3f}s"
            )
        if source_out <= source_in:
            raise EditorialError(f"clip {clip.clip_id} has an empty frame/time range")
        output_duration = source_out - source_in
        if clip.edit.fade_in_seconds + clip.edit.fade_out_seconds > output_duration:
            raise EditorialError(f"clip {clip.clip_id} fades exceed edited duration")
        resolved.append(
            ResolvedClip(
                clip_id=clip.clip_id,
                shot_id=clip.shot_id,
                take_id=clip.take_id,
                path=source,
                sha256=actual_hash,
                conditioning_sha256=conditioning_hash,
                source_duration_seconds=source_duration,
                output_duration_seconds=output_duration,
                source_in_seconds=source_in,
                source_out_seconds=source_out,
                source_frame_rate=source_frame_rate,
                edit=clip.edit,
                transition_to_next=clip.transition_to_next,
            )
        )
    for previous, following in zip(resolved, resolved[1:], strict=False):
        transition = previous.transition_to_next
        if transition.kind == "dissolve":
            overlap = transition.duration_frames / cut.delivery.frame_rate
            if overlap >= min(
                previous.output_duration_seconds, following.output_duration_seconds
            ):
                raise EditorialError(
                    f"transition after {previous.clip_id} exceeds an adjacent clip"
                )
    boundaries_by_id = {item.boundary_id: item for item in project.boundaries}
    takes_by_id = {
        take.take_id: take for shot in project.shots for take in shot.takes
    }
    for previous_clip, following_clip in zip(
        cut.clips, cut.clips[1:], strict=False
    ):
        following_take = takes_by_id[following_clip.take_id]
        if following_take.conditioning_boundary_id is None:
            continue
        boundary = boundaries_by_id[following_take.conditioning_boundary_id]
        if boundary.source_frame is None:
            continue
        if boundary.source_take_id != previous_clip.take_id:
            raise EditorialError(
                f"exact boundary before {following_clip.clip_id} belongs to a different take"
            )
        if previous_clip.edit.source_out_frame_inclusive != boundary.source_frame:
            raise EditorialError(
                f"clip {previous_clip.clip_id} must retain exact boundary frame "
                f"{boundary.source_frame} inclusively"
            )
        expected_child_in = (
            1 if previous_clip.transition_to_next.kind == "cut" else 0
        )
        if following_clip.edit.source_in_frame != expected_child_in:
            raise EditorialError(
                f"clip {following_clip.clip_id} must start at frame {expected_child_in} "
                "for its declared exact-boundary transition"
            )
    return resolved


def dependency_digest(cut: CutManifest, clips: list[ResolvedClip]) -> str:
    payload = {
        "schema": "director-demo-cut-dependencies/1",
        "project_id": cut.project_id,
        "cut_id": cut.cut_id,
        "revision": cut.revision,
        "delivery": cut.delivery.model_dump(mode="json"),
        "clips": [
            _dependency_clip_payload(clip)
            for clip in clips
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _dependency_clip_payload(clip: ResolvedClip) -> dict[str, Any]:
    edit: dict[str, Any] = {
        "source_in_seconds": clip.edit.source_in_seconds,
        "source_out_seconds": clip.edit.source_out_seconds,
        "fade_in_seconds": clip.edit.fade_in_seconds,
        "fade_out_seconds": clip.edit.fade_out_seconds,
    }
    if clip.edit.source_in_frame is not None:
        edit["source_in_frame"] = clip.edit.source_in_frame
    if clip.edit.source_out_frame_inclusive is not None:
        edit["source_out_frame_inclusive"] = clip.edit.source_out_frame_inclusive
    payload: dict[str, Any] = {
                "clip_id": clip.clip_id,
                "shot_id": clip.shot_id,
                "take_id": clip.take_id,
                "sha256": clip.sha256,
                "conditioning_sha256": clip.conditioning_sha256,
                "edit": edit,
    }
    if clip.transition_to_next.kind != "cut":
        payload["transition_to_next"] = clip.transition_to_next.model_dump(mode="json")
    return payload


def check_assembly_freshness(
    record: AssemblyRecord,
    project_manifest_path: Path,
    cut_manifest_path: Path,
    *,
    ffprobe_binary: str = "ffprobe",
) -> AssemblyFreshness:
    """Detect stale delivery inputs without modifying or re-rendering the delivery."""

    project = load_editorial_project(project_manifest_path)
    cut = load_cut_manifest(cut_manifest_path)
    clips = resolve_cut(
        project,
        cut,
        project_manifest_path=project_manifest_path,
        ffprobe_binary=ffprobe_binary,
    )
    current_digest = dependency_digest(cut, clips)
    dependency_match = current_digest == record.dependency_digest
    output_match = sha256_path(_resolve_record_path(record.output.path)) == record.output.sha256
    delivery_error: str | None = None
    try:
        _validate_delivery(
            record.media,
            cut.delivery,
            timeline_duration(clips, cut.delivery),
        )
    except EditorialError as exc:
        delivery_error = str(exc)
    delivery_valid = delivery_error is None
    project_match = (
        sha256_path(project_manifest_path) == record.source_project_manifest.sha256
    )
    cut_match = sha256_path(cut_manifest_path) == record.source_cut_manifest.sha256
    return AssemblyFreshness(
        fresh=dependency_match and output_match and delivery_valid,
        provenance_current=project_match and cut_match,
        dependency_match=dependency_match,
        output_match=output_match,
        delivery_valid=delivery_valid,
        delivery_error=delivery_error,
        project_manifest_match=project_match,
        cut_manifest_match=cut_match,
        current_dependency_digest=current_digest,
    )


def assemble_cut(
    project_manifest_path: Path,
    cut_manifest_path: Path,
    output_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
    ffprobe_binary: str = "ffprobe",
) -> AssemblyRecord:
    """Render a reversible editorial cut without modifying any source take."""

    if shutil.which(ffmpeg_binary) is None:
        raise EditorialError(f"FFmpeg binary not found: {ffmpeg_binary}")
    if output_path.exists():
        raise EditorialError(f"refusing to overwrite assembled output: {output_path}")
    project_snapshot = output_path.with_suffix(".project.json")
    cut_snapshot = output_path.with_suffix(".cut.json")
    for snapshot in (project_snapshot, cut_snapshot):
        if snapshot.exists():
            raise EditorialError(f"refusing to overwrite assembly snapshot: {snapshot}")
    project = load_editorial_project(project_manifest_path)
    cut = load_cut_manifest(cut_manifest_path)
    clips = resolve_cut(
        project,
        cut,
        project_manifest_path=project_manifest_path,
        ffprobe_binary=ffprobe_binary,
    )
    digest = dependency_digest(cut, clips)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}.", suffix=output_path.suffix, dir=output_path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    command = build_ffmpeg_command(clips, cut.delivery, temporary, ffmpeg_binary)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise EditorialError(completed.stderr.strip() or "FFmpeg assembly failed")
        media = probe_media(temporary, ffprobe_binary=ffprobe_binary)
        _validate_delivery(media, cut.delivery, timeline_duration(clips, cut.delivery))
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)

    output_hash = sha256_path(output_path)
    _atomic_text_snapshot(project_manifest_path, project_snapshot)
    _atomic_text_snapshot(cut_manifest_path, cut_snapshot)
    project_hash = sha256_path(project_snapshot)
    cut_hash = sha256_path(cut_snapshot)
    if output_hash is None or project_hash is None or cut_hash is None:
        raise EditorialError("assembly provenance hash could not be calculated")
    record = AssemblyRecord(
        project_id=project.project_id,
        cut_id=cut.cut_id,
        cut_revision=cut.revision,
        dependency_digest=digest,
        created_at=datetime.now(UTC).isoformat(),
        source_project_manifest=ArtifactRef(path=project_snapshot, sha256=project_hash),
        source_cut_manifest=ArtifactRef(path=cut_snapshot, sha256=cut_hash),
        clips=clips,
        output=ArtifactRef(path=output_path, sha256=output_hash),
        media=media,
    )
    write_model(record, output_path.with_suffix(".assembly.json"))
    return record


def build_ffmpeg_command(
    clips: list[ResolvedClip],
    profile: DeliveryProfile,
    output_path: Path,
    ffmpeg_binary: str = "ffmpeg",
) -> list[str]:
    if not clips:
        raise EditorialError("cut has no resolved clips")
    command = [ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-y"]
    for clip in clips:
        command.extend(["-i", str(clip.path)])

    filters: list[str] = []
    for index, clip in enumerate(clips):
        start = clip.source_in_seconds
        end = start + clip.output_duration_seconds
        video = (
            f"[{index}:v:0]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS,"
            f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=decrease,"
            f"pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={profile.frame_rate:.6f},format=yuv420p"
        )
        audio = (
            f"[{index}:a:0]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
            f"aresample={profile.audio_sample_rate},"
            f"aformat=sample_rates={profile.audio_sample_rate}:channel_layouts=stereo"
        )
        if clip.edit.fade_in_seconds:
            video += f",fade=t=in:st=0:d={clip.edit.fade_in_seconds:.6f}"
            audio += f",afade=t=in:st=0:d={clip.edit.fade_in_seconds:.6f}"
        if clip.edit.fade_out_seconds:
            fade_start = clip.output_duration_seconds - clip.edit.fade_out_seconds
            video += f",fade=t=out:st={fade_start:.6f}:d={clip.edit.fade_out_seconds:.6f}"
            audio += f",afade=t=out:st={fade_start:.6f}:d={clip.edit.fade_out_seconds:.6f}"
        filters.extend([video + f"[v{index}]", audio + f"[a{index}]"])
    current_video = "v0"
    current_audio = "a0"
    current_duration = clips[0].output_duration_seconds
    for index in range(1, len(clips)):
        transition = clips[index - 1].transition_to_next
        next_video = f"v{index}"
        next_audio = f"a{index}"
        output_video = "outv" if index == len(clips) - 1 else f"vc{index}"
        output_audio = "outa" if index == len(clips) - 1 else f"ac{index}"
        if transition.kind == "cut":
            filters.append(
                f"[{current_video}][{current_audio}]"
                f"[{next_video}][{next_audio}]"
                f"concat=n=2:v=1:a=1[{output_video}][{output_audio}]"
            )
            current_duration += clips[index].output_duration_seconds
        else:
            overlap = transition.duration_frames / profile.frame_rate
            offset = current_duration - overlap
            filters.append(
                f"[{current_video}][{next_video}]"
                f"xfade=transition=fade:duration={overlap:.6f}:offset={offset:.6f}"
                f"[{output_video}]"
            )
            filters.append(
                f"[{current_audio}][{next_audio}]"
                f"acrossfade=d={overlap:.6f}:c1=qsin:c2=qsin[{output_audio}]"
            )
            current_duration += clips[index].output_duration_seconds - overlap
        current_video = output_video
        current_audio = output_audio
    if len(clips) == 1:
        filters.extend(["[v0]null[outv]", "[a0]anull[outa]"])
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            profile.video_codec,
            "-preset",
            profile.preset,
            "-crf",
            str(profile.crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            profile.audio_codec,
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def timeline_duration(clips: list[ResolvedClip], profile: DeliveryProfile) -> float:
    duration = sum(clip.output_duration_seconds for clip in clips)
    for clip in clips[:-1]:
        if clip.transition_to_next.kind == "dissolve":
            duration -= clip.transition_to_next.duration_frames / profile.frame_rate
    return duration


def probe_media(path: Path, *, ffprobe_binary: str = "ffprobe") -> dict[str, Any]:
    if shutil.which(ffprobe_binary) is None:
        raise EditorialError(f"FFprobe binary not found: {ffprobe_binary}")
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
        raise EditorialError(completed.stderr.strip() or f"could not probe {path}")
    return cast(dict[str, Any], json.loads(completed.stdout))


def _safe_artifact_path(root: Path, value: Path) -> Path:
    if value.is_absolute():
        raise EditorialError("artifact paths must be relative to the declared artifact root")
    resolved = (root / value).resolve()
    if not resolved.is_relative_to(root):
        raise EditorialError(f"artifact path escapes declared root: {value}")
    return resolved


def _resolve_record_path(value: Path) -> Path:
    return value if value.is_absolute() else (Path.cwd() / value).resolve()


def _atomic_text_snapshot(source: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    temporary.replace(target)


def _expose_media(source: Path, media_root: Path, stem: str) -> str:
    if not source.is_file():
        raise EditorialError(f"media artifact is missing: {source}")
    safe_stem = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in stem
    )
    digest = sha256_path(source)
    if digest is None:
        raise EditorialError(f"could not hash media artifact: {source}")
    target = media_root / f"{safe_stem}-{digest[:12]}{source.suffix.lower()}"
    if target.exists() and not os.path.samefile(source, target):
        target.unlink()
    if not target.exists():
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    return f"/editorial-media/{target.name}"


def _validate_delivery(media: dict[str, Any], profile: DeliveryProfile, duration: float) -> None:
    streams = media.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if video is None or audio is None:
        raise EditorialError("assembled delivery must contain video and audio")
    if (video.get("width"), video.get("height")) != (profile.width, profile.height):
        raise EditorialError("assembled delivery has an unexpected resolution")
    if video.get("pix_fmt") != "yuv420p":
        raise EditorialError("assembled delivery must use yuv420p pixel format")
    actual_rate = float(Fraction(str(video.get("avg_frame_rate", "0/1"))))
    if abs(actual_rate - profile.frame_rate) > 0.01:
        raise EditorialError("assembled delivery has an unexpected frame rate")
    actual_duration = float(media["format"]["duration"])
    if abs(actual_duration - duration) > max(0.15, 1 / profile.frame_rate * 2):
        raise EditorialError(
            f"assembled duration {actual_duration:.3f}s differs from timeline {duration:.3f}s"
        )
