import json
from pathlib import Path
from uuid import UUID

import pytest
from typer.testing import CliRunner

from director_demo.cli import app
from director_demo.production import (
    LtxPromptMode,
    ProductionError,
    ShotProductionState,
    build_production_manifest,
    compile_ltx_prompt,
    legal_frame_count,
)
from director_demo.schemas import ShotPlan


def sample_plan(*, duration: float = 5.0) -> ShotPlan:
    return ShotPlan.model_validate(
        {
            "title": "The Quiet Signal",
            "logline": "A technician notices a signal.",
            "characters": [
                {
                    "id": "mara",
                    "name": "Mara",
                    "immutable_traits": ["short dark hair"],
                    "default_wardrobe": ["olive sweater"],
                }
            ],
            "locations": [
                {
                    "id": "studio",
                    "name": "Studio",
                    "immutable_traits": ["warm gray wall"],
                }
            ],
            "global_style": ["natural cinematic realism", "soft window light"],
            "shots": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "number": 1,
                    "scene_id": "scene-1",
                    "title": "Signal",
                    "duration_seconds": duration,
                    "shot_size": "medium",
                    "dramatic_intent": "Mara notices the signal.",
                    "image_prompt": (
                        "Mara in her olive sweater, centered in the warm gray studio, "
                        "soft window light from camera left."
                    ),
                    "motion_prompt": (
                        "Mara blinks and slowly turns toward the sound. The camera pushes in. "
                        "A quiet electronic pulse repeats."
                    ),
                    "audio": {"dialogue": [], "ambience": [], "sound_effects": []},
                    "continuity_in": ["Mara faces camera"],
                    "continuity_out": ["Mara faces screen right"],
                    "seed": 42,
                }
            ],
        }
    )


@pytest.mark.parametrize(
    ("duration", "expected"),
    [(1.0, 25), (2.0, 49), (3.0, 73), (4.0, 97), (5.0, 121)],
)
def test_duration_maps_to_ltx_legal_frames(duration: float, expected: int) -> None:
    assert legal_frame_count(duration) == expected


def test_manifest_enforces_single_slot_and_sequential_paths(tmp_path: Path) -> None:
    manifest = build_production_manifest(sample_plan(), project_root=tmp_path)

    assert manifest.profile.heavy_job_slots == 1
    assert manifest.profile.execution == "strictly_sequential"
    assert manifest.profile.offload == "disk"
    assert (manifest.profile.width, manifest.profile.height) == (1024, 576)
    assert manifest.shots[0].frames == 121
    assert manifest.shots[0].anchor_path == tmp_path / "shots/0001/anchor.png"
    assert manifest.next_renderable_shot() is None

    approved = manifest.shots[0].model_copy(update={"state": ShotProductionState.APPROVED})
    ready_manifest = manifest.model_copy(update={"shots": [approved]})
    assert ready_manifest.next_renderable_shot() == approved


def test_local_profile_rejects_shot_over_five_seconds(tmp_path: Path) -> None:
    with pytest.raises(ProductionError, match="at most 5s"):
        build_production_manifest(sample_plan(duration=5.1), project_root=tmp_path)


def test_state_machine_enforces_one_heavy_render_slot(tmp_path: Path) -> None:
    plan = sample_plan()
    second = plan.shots[0].model_copy(
        update={
            "id": UUID("00000000-0000-0000-0000-000000000002"),
            "number": 2,
            "title": "Reaction",
        }
    )
    manifest = build_production_manifest(
        plan.model_copy(update={"shots": [plan.shots[0], second]}),
        project_root=tmp_path,
    )
    for number in (1, 2):
        manifest = manifest.transition_shot(number, ShotProductionState.APPROVED)
        manifest = manifest.transition_shot(number, ShotProductionState.QUEUED)
    manifest = manifest.transition_shot(1, ShotProductionState.RENDERING)

    with pytest.raises(ProductionError, match="single M5 slot"):
        manifest.transition_shot(2, ShotProductionState.RENDERING)

    manifest = manifest.transition_shot(1, ShotProductionState.RENDERED)
    manifest = manifest.transition_shot(2, ShotProductionState.RENDERING)
    assert manifest.shots[1].state == ShotProductionState.RENDERING


def test_state_machine_rejects_skipped_transition(tmp_path: Path) -> None:
    manifest = build_production_manifest(sample_plan(), project_root=tmp_path)
    with pytest.raises(ProductionError, match="Invalid shot transition"):
        manifest.transition_shot(1, ShotProductionState.RENDERING)


def test_prompt_modes_are_deterministic() -> None:
    plan = sample_plan()
    shot = plan.shots[0]

    motion = compile_ltx_prompt(shot, plan.global_style, LtxPromptMode.MOTION_ONLY)
    style = compile_ltx_prompt(shot, plan.global_style, LtxPromptMode.STYLE_LOCKED)
    context = compile_ltx_prompt(shot, plan.global_style, LtxPromptMode.CONTEXT_LOCKED)

    assert motion == shot.motion_prompt
    assert "natural cinematic realism" in style
    assert shot.image_prompt in context
    assert context.endswith(shot.motion_prompt)


def test_prompt_compiler_refuses_silent_truncation() -> None:
    plan = sample_plan()
    verbose = plan.shots[0].model_copy(update={"motion_prompt": "motion " * 201})
    with pytest.raises(ProductionError, match="maximum is 200"):
        compile_ltx_prompt(verbose, plan.global_style)


def test_compile_production_cli_writes_valid_manifest(tmp_path: Path) -> None:
    shot_plan = tmp_path / "shot-plan.json"
    output = tmp_path / "production.json"
    project_root = tmp_path / "project"
    shot_plan.write_text(sample_plan().model_dump_json(indent=2), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "compile-production",
            str(shot_plan),
            "--project-root",
            str(project_root),
            "--out",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["profile"]["id"] == "m5_air_32gb_ltx25"
    assert payload["shots"][0]["frames"] == 121


def test_shot_plan_schema_cli_exposes_strict_contract() -> None:
    result = CliRunner().invoke(app, ["shot-plan-schema"])
    assert result.exit_code == 0
    schema = json.loads(result.stdout)
    assert schema["additionalProperties"] is False
    assert "shots" in schema["properties"]
