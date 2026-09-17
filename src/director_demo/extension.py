from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from director_demo.editorial import ArtifactRef
from director_demo.schemas import StrictModel


class ExtensionClipPlan(StrictModel):
    clip_count: int = Field(ge=1, le=6)
    seconds_per_clip: Literal[2, 5]
    frames_per_clip: Literal[49, 121]
    frame_rate: Literal[24] = 24
    seed: int = Field(ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def validate_geometry(self) -> ExtensionClipPlan:
        expected = 49 if self.seconds_per_clip == 2 else 121
        if self.frames_per_clip != expected:
            raise ValueError("extension frame count does not match its clip duration")
        return self


class SceneExtensionManifest(StrictModel):
    """Immutable provenance for an appended-only continuation of one assembly."""

    schema_version: Literal["1.0"] = "1.0"
    extension_id: str = Field(min_length=1)
    parent_job_id: str = Field(min_length=1)
    parent_extension_id: str | None = None
    lineage_depth: int = Field(ge=1)
    created_at: str
    prompt: str = Field(min_length=1)
    parent_assembly: ArtifactRef
    parent_dependency_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    endpoint_frame: ArtifactRef
    endpoint_source_frame: int = Field(ge=0)
    parent_frame_count: int = Field(gt=0)
    parent_frame_rate: float = Field(gt=0)
    plan: ExtensionClipPlan

    @model_validator(mode="after")
    def validate_endpoint(self) -> SceneExtensionManifest:
        if self.endpoint_source_frame != self.parent_frame_count - 1:
            raise ValueError("extension endpoint must be the parent's exact final frame")
        return self


def make_extension_manifest(
    *,
    extension_id: str,
    parent_job_id: str,
    parent_extension_id: str | None,
    lineage_depth: int,
    prompt: str,
    parent_assembly: ArtifactRef,
    parent_dependency_digest: str,
    endpoint_frame: ArtifactRef,
    parent_frame_count: int,
    parent_frame_rate: float,
    clip_count: int,
    seconds_per_clip: Literal[2, 5],
    seed: int,
) -> SceneExtensionManifest:
    frames: Literal[49, 121] = 49 if seconds_per_clip == 2 else 121
    return SceneExtensionManifest(
        extension_id=extension_id,
        parent_job_id=parent_job_id,
        parent_extension_id=parent_extension_id,
        lineage_depth=lineage_depth,
        created_at=datetime.now(UTC).isoformat(),
        prompt=prompt,
        parent_assembly=parent_assembly,
        parent_dependency_digest=parent_dependency_digest,
        endpoint_frame=endpoint_frame,
        endpoint_source_frame=parent_frame_count - 1,
        parent_frame_count=parent_frame_count,
        parent_frame_rate=parent_frame_rate,
        plan=ExtensionClipPlan(
            clip_count=clip_count,
            seconds_per_clip=seconds_per_clip,
            frames_per_clip=frames,
            seed=seed,
        ),
    )


def manifest_path(run_directory: Path) -> Path:
    return run_directory / "extension.json"
