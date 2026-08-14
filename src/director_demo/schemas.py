from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShotSize(StrEnum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM = "medium"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    INSERT = "insert"


class AssetReference(StrictModel):
    asset_id: str
    purpose: str
    strength: float = Field(default=1.0, ge=0, le=1)


class DialogueCue(StrictModel):
    character_id: str
    text: str
    delivery: str


class AudioPlan(StrictModel):
    dialogue: list[DialogueCue] = Field(default_factory=list)
    ambience: list[str] = Field(default_factory=list)
    sound_effects: list[str] = Field(default_factory=list)
    music: str | None = None


class Shot(StrictModel):
    id: UUID = Field(default_factory=uuid4)
    number: int = Field(ge=1)
    scene_id: str
    title: str
    duration_seconds: float = Field(default=5, ge=1, le=10)
    shot_size: ShotSize
    dramatic_intent: str
    image_prompt: str = Field(
        description="Static anchor frame: identity, wardrobe, environment, lighting, composition"
    )
    motion_prompt: str = Field(
        description="4-8 present-tense sentences about action, camera, timing, and audio only"
    )
    negative_prompt: str = ""
    references: list[AssetReference] = Field(default_factory=list)
    audio: AudioPlan = Field(default_factory=AudioPlan)
    continuity_in: list[str] = Field(default_factory=list)
    continuity_out: list[str] = Field(default_factory=list)
    transition_out: str = "cut"
    seed: int = Field(ge=0, le=2**32 - 1)


class CharacterBibleEntry(StrictModel):
    id: str
    name: str
    immutable_traits: list[str]
    default_wardrobe: list[str]
    voice_notes: str | None = None


class LocationBibleEntry(StrictModel):
    id: str
    name: str
    immutable_traits: list[str]


class ShotPlan(StrictModel):
    title: str
    logline: str
    aspect_ratio: str = "16:9"
    characters: list[CharacterBibleEntry]
    locations: list[LocationBibleEntry]
    global_style: list[str]
    shots: list[Shot]

    @model_validator(mode="after")
    def validate_sequence(self) -> ShotPlan:
        numbers = [shot.number for shot in self.shots]
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            raise ValueError(f"shot numbers must be sequential: expected {expected}, got {numbers}")
        return self
