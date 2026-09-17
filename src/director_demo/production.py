from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from director_demo.schemas import Shot, ShotPlan, StrictModel


class ProductionError(ValueError):
    """Raised when a shot plan cannot safely target the local production profile."""


class LtxPromptMode(StrEnum):
    """Engine prompt ablations; domain prompts remain unchanged."""

    MOTION_ONLY = "motion_only"
    STYLE_LOCKED = "style_locked"
    CONTEXT_LOCKED = "context_locked"


class ProductionPhase(StrEnum):
    STORYBOARD = "storyboard"
    RENDER = "render"
    REVIEW = "review"
    ASSEMBLY = "assembly"
    COMPLETE = "complete"


class ShotProductionState(StrEnum):
    AWAITING_ANCHOR = "awaiting_anchor"
    APPROVED = "approved"
    QUEUED = "queued"
    RENDERING = "rendering"
    RENDERED = "rendered"
    FAILED = "failed"
    SELECTED = "selected"


class LocalM5Profile(StrictModel):
    id: Literal["m5_air_32gb_ltx25"] = "m5_air_32gb_ltx25"
    video_engine: Literal["ltx-2.5-distilled-bf16"] = "ltx-2.5-distilled-bf16"
    heavy_job_slots: Literal[1] = 1
    execution: Literal["strictly_sequential"] = "strictly_sequential"
    offload: Literal["disk"] = "disk"
    width: int = 1024
    height: int = 576
    frame_rate: float = 24.0
    maximum_frames: int = 121
    maximum_shot_seconds: float = 5.0


class ProductionShot(StrictModel):
    shot_id: UUID
    number: int = Field(ge=1)
    scene_id: str
    title: str
    duration_seconds: float
    frames: int
    frame_rate: float
    width: int
    height: int
    seed: int
    prompt_mode: LtxPromptMode
    ltx_prompt: str
    anchor_path: Path
    output_path: Path
    state: ShotProductionState = ShotProductionState.AWAITING_ANCHOR
    predecessor_shot_id: UUID | None = None
    continuity_in: list[str] = Field(default_factory=list)
    continuity_out: list[str] = Field(default_factory=list)


class ProductionManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    title: str
    source_plan_sha256: str
    phase: ProductionPhase = ProductionPhase.STORYBOARD
    profile: LocalM5Profile = Field(default_factory=LocalM5Profile)
    shots: list[ProductionShot]

    @model_validator(mode="after")
    def validate_sequence_and_capacity(self) -> ProductionManifest:
        numbers = [shot.number for shot in self.shots]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("production shots must remain sequential")
        if len({shot.shot_id for shot in self.shots}) != len(self.shots):
            raise ValueError("production shot IDs must be unique")
        if any(shot.frames > self.profile.maximum_frames for shot in self.shots):
            raise ValueError("shot exceeds the local profile frame ceiling")
        return self

    def next_renderable_shot(self) -> ProductionShot | None:
        """Return one approved job only; the M5 profile never exposes a batch."""
        approved = (shot for shot in self.shots if shot.state == ShotProductionState.APPROVED)
        return next(approved, None)

    def transition_shot(
        self, shot_number: int, target: ShotProductionState
    ) -> ProductionManifest:
        """Apply a guarded state transition while enforcing the one-slot invariant."""
        allowed: dict[ShotProductionState, set[ShotProductionState]] = {
            ShotProductionState.AWAITING_ANCHOR: {ShotProductionState.APPROVED},
            ShotProductionState.APPROVED: {ShotProductionState.QUEUED},
            ShotProductionState.QUEUED: {ShotProductionState.RENDERING},
            ShotProductionState.RENDERING: {
                ShotProductionState.RENDERED,
                ShotProductionState.FAILED,
            },
            ShotProductionState.FAILED: {ShotProductionState.QUEUED},
            ShotProductionState.RENDERED: {
                ShotProductionState.SELECTED,
                ShotProductionState.QUEUED,
            },
            ShotProductionState.SELECTED: set(),
        }
        try:
            selected = next(shot for shot in self.shots if shot.number == shot_number)
        except StopIteration:
            raise ProductionError(f"Unknown shot number: {shot_number}") from None
        if target not in allowed[selected.state]:
            raise ProductionError(f"Invalid shot transition: {selected.state} -> {target}")
        if target == ShotProductionState.RENDERING and any(
            shot.state == ShotProductionState.RENDERING for shot in self.shots
        ):
            raise ProductionError("Another heavy render already owns the single M5 slot")
        updated = [
            shot.model_copy(update={"state": target}) if shot.number == shot_number else shot
            for shot in self.shots
        ]
        return self.model_copy(update={"shots": updated})


def legal_frame_count(duration_seconds: float, frame_rate: float = 24.0) -> int:
    """Map editorial duration to the closest positive LTX frame count (8n + 1)."""
    if duration_seconds <= 0 or frame_rate <= 0:
        raise ProductionError("duration and frame rate must be positive")
    interval_count = max(1, round((duration_seconds * frame_rate - 1) / 8))
    return interval_count * 8 + 1


def compile_ltx_prompt(
    shot: Shot,
    global_style: list[str],
    mode: LtxPromptMode = LtxPromptMode.CONTEXT_LOCKED,
    *,
    maximum_words: int = 200,
) -> str:
    """Compile trusted shot fields without asking an LLM to rewrite locked facts."""
    motion = shot.motion_prompt.strip()
    if mode == LtxPromptMode.MOTION_ONLY:
        prompt = motion
    elif mode == LtxPromptMode.STYLE_LOCKED:
        style = ", ".join(item.strip() for item in global_style if item.strip())
        prefix = f"Visual style remains locked to the approved anchor: {style}. " if style else ""
        prompt = prefix + motion
    else:
        prompt = (
            "Maintain the exact subject, wardrobe, environment, lighting, and composition "
            f"shown by the approved anchor: {shot.image_prompt.strip()} "
            f"Motion, camera, and sound unfold as follows: {motion}"
        )

    prompt = re.sub(r"\s+", " ", prompt).strip()
    word_count = len(prompt.split())
    if word_count > maximum_words:
        raise ProductionError(
            f"Shot {shot.number} compiles to {word_count} words; maximum is {maximum_words}. "
            "Shorten the source prompts without silently truncating dialogue or continuity."
        )
    return prompt


def build_production_manifest(
    plan: ShotPlan,
    *,
    project_root: Path,
    prompt_mode: LtxPromptMode = LtxPromptMode.CONTEXT_LOCKED,
    profile: LocalM5Profile | None = None,
) -> ProductionManifest:
    """Deterministically turn creative LLM output into a safe local execution manifest."""
    selected_profile = profile or LocalM5Profile()
    canonical = plan.model_dump_json(exclude_none=True)
    plan_hash = hashlib.sha256(canonical.encode()).hexdigest()
    project_id = f"{_slug(plan.title)}-{plan_hash[:10]}"
    production_shots: list[ProductionShot] = []

    for index, shot in enumerate(plan.shots):
        if shot.duration_seconds > selected_profile.maximum_shot_seconds:
            raise ProductionError(
                f"Shot {shot.number} is {shot.duration_seconds:g}s; the M5/32 GB profile "
                f"requires shots of at most {selected_profile.maximum_shot_seconds:g}s"
            )
        frames = legal_frame_count(shot.duration_seconds, selected_profile.frame_rate)
        if frames > selected_profile.maximum_frames:
            raise ProductionError(f"Shot {shot.number} exceeds the local frame ceiling")
        shot_root = project_root / "shots" / f"{shot.number:04d}"
        production_shots.append(
            ProductionShot(
                shot_id=shot.id,
                number=shot.number,
                scene_id=shot.scene_id,
                title=shot.title,
                duration_seconds=shot.duration_seconds,
                frames=frames,
                frame_rate=selected_profile.frame_rate,
                width=selected_profile.width,
                height=selected_profile.height,
                seed=shot.seed,
                prompt_mode=prompt_mode,
                ltx_prompt=compile_ltx_prompt(shot, plan.global_style, prompt_mode),
                anchor_path=shot_root / "anchor.png",
                output_path=shot_root / "takes" / "take-001.mp4",
                predecessor_shot_id=plan.shots[index - 1].id if index else None,
                continuity_in=shot.continuity_in,
                continuity_out=shot.continuity_out,
            )
        )

    return ProductionManifest(
        project_id=project_id,
        title=plan.title,
        source_plan_sha256=plan_hash,
        profile=selected_profile,
        shots=production_shots,
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48] or "untitled"


def write_manifest(manifest: ProductionManifest, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path
