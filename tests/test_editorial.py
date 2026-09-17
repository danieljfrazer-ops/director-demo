import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from director_demo.cli import app
from director_demo.editorial import (
    CreativeDecision,
    CutClip,
    CutManifest,
    EditDecision,
    EditorialError,
    EditorialProject,
    QualityReview,
    TakeRecord,
    TechnicalDecision,
    TransitionDecision,
    assemble_cut,
    check_assembly_freshness,
    dependency_digest,
    load_editorial_project,
    register_take,
    resolve_cut,
    select_take,
    update_take_review,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_payload(artifact: Path, *, creative: str = "approved") -> dict[str, object]:
    return {
        "project_id": "project-1",
        "title": "Reusable editorial fixture",
        "artifact_root": ".",
        "shots": [
            {
                "shot_id": "shot-1",
                "number": 1,
                "title": "Opening",
                "selected_take_id": "take-1",
                "takes": [
                    {
                        "take_id": "take-1",
                        "shot_id": "shot-1",
                        "label": "First take",
                        "created_at": "2026-08-16T00:00:00+00:00",
                        "artifact": {"path": artifact.name, "sha256": sha256(artifact)},
                        "review": {
                            "technical": "pass",
                            "creative": creative,
                        },
                    }
                ],
            }
        ],
    }


def make_cut(*, edit: EditDecision | None = None) -> CutManifest:
    return CutManifest(
        project_id="project-1",
        cut_id="cut-1",
        revision=1,
        clips=[
            CutClip(
                clip_id="clip-1",
                shot_id="shot-1",
                take_id="take-1",
                edit=edit or EditDecision(),
            )
        ],
    )


def generate_fixture_video(
    path: Path,
    *,
    duration: float = 1.0,
    size: str = "320x192",
    frame_rate: int = 24,
    sample_rate: int = 48_000,
) -> None:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate={frame_rate}:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate={sample_rate}:duration={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_selected_take_requires_both_technical_and_creative_approval(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    artifact.write_bytes(b"fixture")

    with pytest.raises(ValidationError, match="creatively approved"):
        EditorialProject.model_validate(project_payload(artifact, creative="rejected"))


def test_approved_with_edit_take_requires_an_explicit_edit(tmp_path: Path) -> None:
    if shutil.which("ffprobe") is None:
        pytest.skip("ffprobe is required")
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project = EditorialProject.model_validate(
        project_payload(artifact, creative="approved_with_edit")
    )

    with pytest.raises(EditorialError, match="approved only with an explicit edit"):
        resolve_cut(project, make_cut(), project_manifest_path=tmp_path / "project.json")


def test_resolve_cut_rejects_changed_take_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project = EditorialProject.model_validate(project_payload(artifact))
    artifact.write_bytes(b"changed after approval")

    with pytest.raises(EditorialError, match="artifact hash changed"):
        resolve_cut(project, make_cut(), project_manifest_path=tmp_path / "project.json")


def test_dependency_digest_changes_with_non_destructive_edit(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project = EditorialProject.model_validate(project_payload(artifact))
    first = make_cut(edit=EditDecision(source_out_seconds=0.8))
    second = first.model_copy(
        update={
            "revision": 2,
            "clips": [
                first.clips[0].model_copy(
                    update={"edit": EditDecision(source_out_seconds=0.7)}
                )
            ],
        }
    )
    first_resolved = resolve_cut(
        project, first, project_manifest_path=tmp_path / "project.json"
    )
    second_resolved = resolve_cut(
        project, second, project_manifest_path=tmp_path / "project.json"
    )

    assert dependency_digest(first, first_resolved) != dependency_digest(
        second, second_resolved
    )


def test_frame_addressed_edit_resolves_inclusive_boundary(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact, duration=1.0, frame_rate=24)
    project = EditorialProject.model_validate(project_payload(artifact))
    cut = make_cut(
        edit=EditDecision(source_in_frame=1, source_out_frame_inclusive=23)
    )

    clip = resolve_cut(
        project, cut, project_manifest_path=tmp_path / "project.json"
    )[0]

    assert clip.source_in_seconds == pytest.approx(1 / 24)
    assert clip.source_out_seconds == pytest.approx(1.0)
    assert clip.output_duration_seconds == pytest.approx(23 / 24)


def test_edit_rejects_mixed_time_and_frame_addressing() -> None:
    with pytest.raises(ValidationError, match="seconds or frames"):
        EditDecision(source_in_seconds=0.1, source_in_frame=1)


def test_dependency_digest_changes_with_transition_policy(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project = EditorialProject.model_validate(project_payload(artifact))
    cut = make_cut()
    resolved = resolve_cut(
        project, cut, project_manifest_path=tmp_path / "project.json"
    )
    changed = resolved[0].model_copy(
        update={
            "transition_to_next": TransitionDecision(
                kind="dissolve",
                duration_frames=4,
                audio="equal_power_crossfade",
            )
        }
    )

    assert dependency_digest(cut, resolved) != dependency_digest(cut, [changed])


def test_manifest_assembly_applies_trim_fade_and_writes_provenance(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are required")
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project_path = tmp_path / "project.json"
    cut_path = tmp_path / "cut.json"
    output = tmp_path / "assembled.mp4"
    project = EditorialProject.model_validate(project_payload(artifact))
    cut = make_cut(
        edit=EditDecision(
            source_in_seconds=0.1,
            source_out_seconds=0.8,
            fade_in_seconds=0.1,
            fade_out_seconds=0.1,
        )
    )
    project_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    cut_path.write_text(cut.model_dump_json(indent=2), encoding="utf-8")

    record = assemble_cut(project_path, cut_path, output)

    assert output.is_file()
    assert output.with_suffix(".assembly.json").is_file()
    assert output.with_suffix(".project.json").read_text() == project_path.read_text()
    assert output.with_suffix(".cut.json").read_text() == cut_path.read_text()
    assert record.output.sha256 == sha256(output)
    assert record.clips[0].output_duration_seconds == pytest.approx(0.7)
    assert record.delivery_review.decision == "pending"
    video = next(stream for stream in record.media["streams"] if stream["codec_type"] == "video")
    assert (video["width"], video["height"]) == (1024, 576)


def test_assembly_refuses_to_overwrite_output(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    cut = tmp_path / "cut.json"
    output = tmp_path / "assembled.mp4"
    output.write_bytes(b"existing")
    with pytest.raises(EditorialError, match="refusing to overwrite"):
        assemble_cut(project, cut, output)


def test_assembly_freshness_detects_changed_cut_manifest(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are required")
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project_path = tmp_path / "project.json"
    cut_path = tmp_path / "cut.json"
    output = tmp_path / "assembled.mp4"
    project = EditorialProject.model_validate(project_payload(artifact))
    cut = make_cut(edit=EditDecision(source_out_seconds=0.8))
    project_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    cut_path.write_text(cut.model_dump_json(indent=2), encoding="utf-8")
    record = assemble_cut(project_path, cut_path, output)
    assert check_assembly_freshness(record, project_path, cut_path).fresh

    changed_cut = cut.model_copy(
        update={
            "revision": 2,
            "clips": [
                cut.clips[0].model_copy(
                    update={"edit": EditDecision(source_out_seconds=0.7)}
                )
            ],
        }
    )
    cut_path.write_text(changed_cut.model_dump_json(indent=2), encoding="utf-8")
    freshness = check_assembly_freshness(record, project_path, cut_path)
    assert not freshness.fresh
    assert not freshness.dependency_match
    assert not freshness.cut_manifest_match
    assert freshness.output_match


def test_assembly_freshness_rejects_nonconforming_delivery_metadata(
    tmp_path: Path,
) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are required")
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project_path = tmp_path / "project.json"
    cut_path = tmp_path / "cut.json"
    output = tmp_path / "assembled.mp4"
    project = EditorialProject.model_validate(project_payload(artifact))
    cut = make_cut()
    project_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    cut_path.write_text(cut.model_dump_json(indent=2), encoding="utf-8")
    record = assemble_cut(project_path, cut_path, output)
    media = json.loads(json.dumps(record.media))
    video = next(stream for stream in media["streams"] if stream["codec_type"] == "video")
    video["pix_fmt"] = "yuv444p"
    invalid = record.model_copy(update={"media": media})

    freshness = check_assembly_freshness(invalid, project_path, cut_path)

    assert not freshness.fresh
    assert not freshness.delivery_valid
    assert freshness.delivery_error == "assembled delivery must use yuv420p pixel format"


def test_assembly_normalizes_heterogeneous_inputs(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are required")
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    generate_fixture_video(first, size="320x192", frame_rate=24, sample_rate=48_000)
    generate_fixture_video(second, size="640x360", frame_rate=30, sample_rate=44_100)
    payload = project_payload(first)
    second_shot = json.loads(json.dumps(payload["shots"][0]))  # type: ignore[index]
    second_shot.update(
        {
            "shot_id": "shot-2",
            "number": 2,
            "title": "Second",
            "selected_take_id": "take-2",
        }
    )
    second_take = second_shot["takes"][0]
    second_take.update(
        {
            "take_id": "take-2",
            "shot_id": "shot-2",
            "artifact": {"path": second.name, "sha256": sha256(second)},
        }
    )
    payload["shots"].append(second_shot)  # type: ignore[union-attr]
    project = EditorialProject.model_validate(payload)
    cut = CutManifest(
        project_id="project-1",
        cut_id="heterogeneous-cut",
        revision=1,
        clips=[
            CutClip(clip_id="clip-1", shot_id="shot-1", take_id="take-1"),
            CutClip(clip_id="clip-2", shot_id="shot-2", take_id="take-2"),
        ],
    )
    project_path = tmp_path / "project.json"
    cut_path = tmp_path / "cut.json"
    output = tmp_path / "normalized.mp4"
    project_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    cut_path.write_text(cut.model_dump_json(indent=2), encoding="utf-8")

    record = assemble_cut(project_path, cut_path, output)

    video = next(stream for stream in record.media["streams"] if stream["codec_type"] == "video")
    audio = next(stream for stream in record.media["streams"] if stream["codec_type"] == "audio")
    assert (video["width"], video["height"], video["avg_frame_rate"]) == (
        1024,
        576,
        "24/1",
    )
    assert audio["sample_rate"] == "48000"


def test_assembly_applies_video_and_audio_overlap_transition(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are required")
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    generate_fixture_video(first)
    generate_fixture_video(second)
    payload = project_payload(first)
    second_shot = json.loads(json.dumps(payload["shots"][0]))  # type: ignore[index]
    second_shot.update(
        {
            "shot_id": "shot-2",
            "number": 2,
            "title": "Second",
            "selected_take_id": "take-2",
        }
    )
    second_take = second_shot["takes"][0]
    second_take.update(
        {
            "take_id": "take-2",
            "shot_id": "shot-2",
            "artifact": {"path": second.name, "sha256": sha256(second)},
        }
    )
    payload["shots"].append(second_shot)  # type: ignore[union-attr]
    project = EditorialProject.model_validate(payload)
    cut = CutManifest(
        project_id="project-1",
        cut_id="dissolve-cut",
        revision=1,
        clips=[
            CutClip(
                clip_id="clip-1",
                shot_id="shot-1",
                take_id="take-1",
                transition_to_next=TransitionDecision(
                    kind="dissolve",
                    duration_frames=6,
                    audio="equal_power_crossfade",
                ),
            ),
            CutClip(clip_id="clip-2", shot_id="shot-2", take_id="take-2"),
        ],
    )
    project_path = tmp_path / "project.json"
    cut_path = tmp_path / "cut.json"
    output = tmp_path / "dissolve.mp4"
    project_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    cut_path.write_text(cut.model_dump_json(indent=2), encoding="utf-8")

    record = assemble_cut(project_path, cut_path, output)

    assert float(record.media["format"]["duration"]) == pytest.approx(1.75, abs=0.08)
    assert record.clips[0].transition_to_next.duration_frames == 6
    video = next(stream for stream in record.media["streams"] if stream["codec_type"] == "video")
    assert video["pix_fmt"] == "yuv420p"


def test_review_metadata_change_does_not_stale_media_dependencies(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg tools are required")
    artifact = tmp_path / "take.mp4"
    generate_fixture_video(artifact)
    project_path = tmp_path / "project.json"
    cut_path = tmp_path / "cut.json"
    output = tmp_path / "assembled.mp4"
    project = EditorialProject.model_validate(project_payload(artifact))
    cut = make_cut(edit=EditDecision(source_out_seconds=0.8))
    project_path.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    cut_path.write_text(cut.model_dump_json(indent=2), encoding="utf-8")
    record = assemble_cut(project_path, cut_path, output)

    changed_project = project.model_copy(update={"title": "Review metadata changed"})
    project_path.write_text(changed_project.model_dump_json(indent=2), encoding="utf-8")
    freshness = check_assembly_freshness(record, project_path, cut_path)
    assert freshness.fresh
    assert not freshness.provenance_current
    assert freshness.dependency_match


def test_editorial_schema_cli_exposes_all_contracts() -> None:
    result = CliRunner().invoke(app, ["editorial-schemas"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert set(payload) == {"editorial_project", "cut_manifest", "assembly_record"}
    assert payload["editorial_project"]["additionalProperties"] is False


def test_review_enums_remain_explicit() -> None:
    assert TechnicalDecision.PASS.value == "pass"
    assert CreativeDecision.APPROVED_WITH_EDIT.value == "approved_with_edit"


def test_register_review_and_select_take_workflow(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    project = EditorialProject.model_validate(project_payload(first))
    pending = TakeRecord.model_validate(
        {
            "take_id": "take-2",
            "shot_id": "shot-1",
            "label": "Retake",
            "created_at": "2026-08-16T01:00:00+00:00",
            "artifact": {"path": second.name, "sha256": sha256(second)},
            "parent_take_id": "take-1",
            "retake_reason": "Correct motion overshoot.",
        }
    )
    project = register_take(project, "shot-1", pending)
    assert project.shots[0].selected_take_id == "take-1"
    approved = QualityReview(
        technical="pass",
        creative="approved",
        reviewer="tester",
        summary="Retake accepted.",
    )
    project = update_take_review(project, "shot-1", "take-2", approved)
    project = select_take(project, "shot-1", "take-2")
    assert project.shots[0].selected_take_id == "take-2"
    assert len(project.shots[0].takes) == 2


def test_selected_take_cannot_be_rejected_without_reselection(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    artifact.write_bytes(b"fixture")
    project = EditorialProject.model_validate(project_payload(artifact))
    with pytest.raises(EditorialError, match="clear or replace selection"):
        update_take_review(
            project,
            "shot-1",
            "take-1",
            QualityReview(technical="pass", creative="rejected"),
        )


def test_retake_parent_requires_reason(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    artifact.write_bytes(b"fixture")
    payload = project_payload(artifact)
    shot = payload["shots"][0]  # type: ignore[index]
    take = shot["takes"][0]  # type: ignore[index]
    take["parent_take_id"] = "take-0"
    with pytest.raises(ValidationError, match="retake reason"):
        EditorialProject.model_validate(payload)


def test_retake_lineage_may_cross_shots(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    artifact.write_bytes(b"fixture")
    payload = project_payload(artifact)
    payload["shots"].append(  # type: ignore[union-attr]
        {
            "shot_id": "shot-2",
            "number": 2,
            "title": "Boundary-conditioned continuation",
            "takes": [
                {
                    "take_id": "take-2",
                    "shot_id": "shot-2",
                    "label": "Continuation",
                    "created_at": "2026-08-16T01:00:00+00:00",
                    "artifact": {"path": artifact.name, "sha256": sha256(artifact)},
                    "parent_take_id": "take-1",
                    "retake_reason": "Extend from an approved boundary.",
                }
            ],
        }
    )

    project = EditorialProject.model_validate(payload)

    assert project.shots[1].takes[0].parent_take_id == "take-1"


def test_retake_lineage_rejects_cycles(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    artifact.write_bytes(b"fixture")
    payload = project_payload(artifact)
    first_take = payload["shots"][0]["takes"][0]  # type: ignore[index]
    first_take["parent_take_id"] = "take-2"
    first_take["retake_reason"] = "Invalid cycle fixture."
    payload["shots"].append(  # type: ignore[union-attr]
        {
            "shot_id": "shot-2",
            "number": 2,
            "title": "Continuation",
            "takes": [
                {
                    "take_id": "take-2",
                    "shot_id": "shot-2",
                    "label": "Continuation",
                    "created_at": "2026-08-16T01:00:00+00:00",
                    "artifact": {"path": artifact.name, "sha256": sha256(artifact)},
                    "parent_take_id": "take-1",
                    "retake_reason": "Invalid cycle fixture.",
                }
            ],
        }
    )

    with pytest.raises(ValidationError, match="lineage contains a cycle"):
        EditorialProject.model_validate(payload)


def test_load_migrates_embedded_boundary_without_rewriting_snapshot(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "take.mp4"
    boundary = tmp_path / "boundary.png"
    artifact.write_bytes(b"fixture")
    boundary.write_bytes(b"approved boundary")
    payload = project_payload(artifact)
    take = payload["shots"][0]["takes"][0]  # type: ignore[index]
    take["conditioning_boundary"] = {
        "boundary_id": "legacy-boundary",
        "artifact": {"path": boundary.name, "sha256": sha256(boundary)},
        "source_take_id": "take-1",
        "source_time_seconds": 0.5,
        "reviewer": "tester",
        "reviewed_at": "2026-08-16T00:00:00+00:00",
    }
    snapshot = tmp_path / "legacy-project.json"
    original = json.dumps(payload, indent=2) + "\n"
    snapshot.write_text(original, encoding="utf-8")

    project = load_editorial_project(snapshot)

    assert project.boundaries[0].boundary_id == "legacy-boundary"
    assert project.shots[0].takes[0].conditioning_boundary_id == "legacy-boundary"
    assert snapshot.read_text(encoding="utf-8") == original


def test_resolve_cut_rejects_changed_conditioning_boundary(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    boundary = tmp_path / "boundary.png"
    generate_fixture_video(artifact)
    boundary.write_bytes(b"approved boundary")
    payload = project_payload(artifact)
    shot = payload["shots"][0]  # type: ignore[index]
    take = shot["takes"][0]  # type: ignore[index]
    payload["boundaries"] = [
        {
            "boundary_id": "boundary-1",
            "artifact": {"path": boundary.name, "sha256": sha256(boundary)},
            "source_take_id": "take-1",
            "source_time_seconds": 0.5,
            "reviewer": "tester",
            "reviewed_at": "2026-08-16T00:00:00+00:00",
        }
    ]
    take["conditioning_boundary_id"] = "boundary-1"
    project = EditorialProject.model_validate(payload)
    boundary.write_bytes(b"changed boundary")

    with pytest.raises(EditorialError, match="conditioning artifact hash changed"):
        resolve_cut(project, make_cut(), project_manifest_path=tmp_path / "project.json")


def test_exact_boundary_join_rejects_off_by_one_source_frame(tmp_path: Path) -> None:
    artifact = tmp_path / "take.mp4"
    boundary = tmp_path / "boundary.png"
    generate_fixture_video(artifact)
    boundary.write_bytes(b"approved boundary")
    payload = project_payload(artifact)
    child_shot = json.loads(json.dumps(payload["shots"][0]))  # type: ignore[index]
    child_shot.update(
        {
            "shot_id": "shot-2",
            "number": 2,
            "title": "Continuation",
            "selected_take_id": "take-2",
        }
    )
    child_take = child_shot["takes"][0]
    child_take.update(
        {
            "take_id": "take-2",
            "shot_id": "shot-2",
            "conditioning_boundary_id": "boundary-1",
        }
    )
    payload["shots"].append(child_shot)  # type: ignore[union-attr]
    payload["boundaries"] = [
        {
            "boundary_id": "boundary-1",
            "artifact": {"path": boundary.name, "sha256": sha256(boundary)},
            "source_take_id": "take-1",
            "source_time_seconds": 23 / 24,
            "source_frame": 23,
            "reviewer": "tester",
            "reviewed_at": "2026-08-16T00:00:00+00:00",
        }
    ]
    project = EditorialProject.model_validate(payload)
    cut = CutManifest(
        project_id="project-1",
        cut_id="off-by-one",
        revision=1,
        clips=[
            CutClip(
                clip_id="clip-1",
                shot_id="shot-1",
                take_id="take-1",
                edit=EditDecision(source_out_frame_inclusive=22),
            ),
            CutClip(
                clip_id="clip-2",
                shot_id="shot-2",
                take_id="take-2",
                edit=EditDecision(source_in_frame=1),
            ),
        ],
    )

    with pytest.raises(EditorialError, match="retain exact boundary frame 23"):
        resolve_cut(project, cut, project_manifest_path=tmp_path / "project.json")
