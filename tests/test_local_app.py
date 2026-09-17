import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import director_demo.local_app as local_app
from director_demo.local_app import (
    HTML,
    _assemble_job,
    _clip_conditionings,
    _job_for_api,
    _parse_byte_range,
    _progress_payload,
    _reference_clip_frame,
    _validate_request,
    cancel_job,
    create_extension_job,
    create_job,
    delete_job,
    import_completed_assembly,
)
from director_demo.ltx import LtxProgress


def test_local_app_uses_safe_m5_options() -> None:
    prompt, references, clips, duration, seed = _validate_request(
        {
            "prompt": "The camera remains locked while the subject breathes slowly.",
            "image_type": "image/png",
            "image_data": base64.b64encode(b"fixture").decode(),
            "clips": 2,
            "duration": 5,
            "seed": 42,
        }
    )

    assert prompt.startswith("The camera")
    assert references[0].image == b"fixture"
    assert references[0].reference_id == "start-frame"
    assert (references[0].extension, clips, duration, seed) == (".png", 2, 5, 42)


def test_run_polling_reconciles_cards_without_rebuilding_stable_media() -> None:
    assert "jobs.innerHTML=data.length" not in HTML
    assert "const jobRenderKey=" in HTML
    assert "node.dataset.renderKey!==key" in HTML
    assert "jobs.insertBefore(node,cursor)" in HTML


def test_local_app_reserves_prompt_space_for_continuity_prefix() -> None:
    with pytest.raises(ValueError, match="1–170 words"):
        _validate_request(
            {
                "prompt": "word " * 171,
                "image_type": "image/png",
                "image_data": base64.b64encode(b"fixture").decode(),
            }
        )


def _write_job(root: Path, job_id: str, status: str) -> Path:
    directory = root / job_id
    directory.mkdir()
    (directory / "job.json").write_text(json.dumps({"job_id": job_id, "status": status}))
    (directory / "reference.png").write_bytes(b"image")
    (directory / "final-video.mp4").write_bytes(b"video")
    return directory


def test_job_api_exposes_local_run_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    directory = _write_job(tmp_path, "job-123", "completed")

    assert _job_for_api("job-123")["folder_path"] == str(directory.resolve())


def test_import_completed_assembly_preserves_verified_source_and_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs_root = tmp_path / "jobs"
    source_video = tmp_path / "historical.mp4"
    source_video.write_bytes(b"immutable historical video")
    source_hash = local_app.sha256_path(source_video)
    source_record = tmp_path / "historical.assembly.json"
    source_record.write_text(
        json.dumps(
            {
                "status": "completed",
                "clips": [{"clip_id": "clip-1"}],
                "output": {"sha256": source_hash},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(local_app, "JOBS_ROOT", jobs_root)
    monkeypatch.setattr(local_app, "_video_frame_details", lambda *_: (97, 24.0))

    imported = import_completed_assembly(
        source_video,
        source_record,
        title="Retained continuity fixture",
        prompt_summary="Safe historical continuity evidence.",
    )

    directory = jobs_root / imported["job_id"]
    job = json.loads((directory / "job.json").read_text(encoding="utf-8"))
    assembly = json.loads(
        (directory / "final-video.assembly.json").read_text(encoding="utf-8")
    )
    assert job["status"] == "completed"
    assert job["job_type"] == "imported_assembly"
    assert job["duration_seconds"] == 4.042
    assert (directory / "final-video.mp4").read_bytes() == source_video.read_bytes()
    assert assembly["output"]["sha256"] == source_hash
    assert assembly["source_assembly_record"]["sha256"] == local_app.sha256_path(
        source_record
    )


def test_import_completed_assembly_rejects_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path / "jobs")
    source_video = tmp_path / "changed.mp4"
    source_video.write_bytes(b"changed")
    source_record = tmp_path / "changed.assembly.json"
    source_record.write_text(
        json.dumps({"status": "completed", "output": {"sha256": "wrong"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="video hash changed"):
        import_completed_assembly(
            source_video,
            source_record,
            title="Changed",
            prompt_summary="Must be rejected.",
        )


def test_delete_job_removes_only_selected_completed_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    selected = _write_job(tmp_path, "job-123", "failed")
    untouched = _write_job(tmp_path, "job-456", "completed")

    delete_job("job-123")

    assert not selected.exists()
    assert untouched.is_dir()
    assert (untouched / "final-video.mp4").is_file()


def test_delete_job_refuses_active_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    active = _write_job(tmp_path, "job-123", "running")

    with pytest.raises(ValueError, match="queued or running"):
        delete_job("job-123")

    assert active.is_dir()


def test_progress_payload_aggregates_real_steps_across_clips() -> None:
    progress = _progress_payload(
        LtxProgress("base_denoise", "Initial generation", current=4, total=8),
        clip_index=2,
        clip_count=3,
    )

    assert progress["clip_percent"] == 30.0
    assert progress["overall_percent"] == 42.5
    assert progress["step_current"] == 4
    assert progress["step_total"] == 8


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("bytes=0-1023", (0, 1023)),
        ("bytes=1024-", (1024, 4095)),
        ("bytes=-512", (3584, 4095)),
        ("bytes=4000-9999", (4000, 4095)),
    ],
)
def test_parse_byte_range_supports_browser_media_requests(
    header: str | None, expected: tuple[int, int] | None
) -> None:
    assert _parse_byte_range(header, 4096) == expected


@pytest.mark.parametrize("header", ["items=0-10", "bytes=", "bytes=99-20", "bytes=5000-"])
def test_parse_byte_range_rejects_invalid_requests(header: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        _parse_byte_range(header, 4096)


def test_cancel_queued_job_preserves_folder_and_marks_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    directory = _write_job(tmp_path, "job-123", "queued")
    try:
        job = cancel_job("job-123")
    finally:
        local_app.CANCEL_EVENTS.pop("job-123", None)

    assert job["status"] == "cancelled"
    assert directory.is_dir()
    assert (directory / "reference.png").is_file()


def test_cancel_completed_job_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    _write_job(tmp_path, "job-123", "completed")

    with pytest.raises(ValueError, match="queued or running"):
        cancel_job("job-123")


def test_multiple_references_have_editable_ids_and_timeline_positions() -> None:
    encoded = base64.b64encode(b"fixture").decode()

    _, references, clips, duration, _ = _validate_request(
        {
            "prompt": "The action moves smoothly from @start-frame to @end-frame.",
            "images": [
                {
                    "id": "start-frame",
                    "image_type": "image/png",
                    "image_data": encoded,
                    "position_percent": 0,
                    "name": "opening.png",
                },
                {
                    "id": "end-frame",
                    "image_type": "image/jpeg",
                    "image_data": encoded,
                    "position_percent": 100,
                    "name": "ending.jpg",
                },
            ],
            "clips": 2,
            "duration": 5,
            "seed": 7,
        }
    )

    assert [item.reference_id for item in references] == ["start-frame", "end-frame"]
    assert [item.position_percent for item in references] == [0, 100]
    assert (clips, duration) == (2, 5)


def test_reference_positions_map_across_continuation_clips() -> None:
    assert _reference_clip_frame(0, clips=2, frames_per_clip=121) == (0, 0)
    assert _reference_clip_frame(50, clips=2, frames_per_clip=121) == (0, 120)
    assert _reference_clip_frame(100, clips=2, frames_per_clip=121) == (1, 120)


def test_start_end_references_and_continuity_are_assigned_to_exact_clip_frames(
    tmp_path: Path,
) -> None:
    references = tmp_path / "references"
    references.mkdir()
    (references / "start.png").write_bytes(b"start")
    (references / "end.png").write_bytes(b"end")
    boundary = tmp_path / "boundary.png"
    boundary.write_bytes(b"boundary")
    job = {
        "clips": 2,
        "settings": {"frames_per_clip": 121},
        "references": [
            {"id": "start", "file": "references/start.png", "position_percent": 0},
            {"id": "end", "file": "references/end.png", "position_percent": 100},
        ],
    }

    first = _clip_conditionings(job, tmp_path, 0, None)
    second = _clip_conditionings(job, tmp_path, 1, boundary)

    assert [(item.reference_id, item.frame_index) for item in first] == [("start", 0)]
    assert [(item.reference_id, item.frame_index) for item in second] == [
        ("continuity-2", 0),
        ("end", 120),
    ]


def test_multiple_references_reject_duplicate_ids_and_frames() -> None:
    encoded = base64.b64encode(b"fixture").decode()
    base = {
        "prompt": "Motion between references.",
        "clips": 1,
        "duration": 5,
        "images": [
            {
                "id": "same",
                "image_type": "image/png",
                "image_data": encoded,
                "position_percent": 0,
            },
            {
                "id": "same",
                "image_type": "image/png",
                "image_data": encoded,
                "position_percent": 100,
            },
        ],
    }
    with pytest.raises(ValueError, match="IDs must be unique"):
        _validate_request(base)

    base["images"][1]["id"] = "other"  # type: ignore[index]
    base["images"][1]["position_percent"] = 0.1  # type: ignore[index]
    with pytest.raises(ValueError, match="same generated frame"):
        _validate_request(base)


def test_create_job_stores_each_reference_immutably_with_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class QueueStub:
        queued: list[str] = []

        def put(self, job_id: str) -> None:
            self.queued.append(job_id)

    encoded = base64.b64encode(b"fixture").decode()
    queue_stub = QueueStub()
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    monkeypatch.setattr(local_app, "JOB_QUEUE", queue_stub)
    try:
        job = create_job(
            {
                "prompt": "Move smoothly from @opening to @ending.",
                "images": [
                    {
                        "id": "opening",
                        "image_type": "image/png",
                        "image_data": encoded,
                        "position_percent": 0,
                        "name": "My Opening.png",
                    },
                    {
                        "id": "ending",
                        "image_type": "image/jpeg",
                        "image_data": encoded,
                        "position_percent": 100,
                        "name": "My Ending.jpg",
                    },
                ],
                "clips": 1,
                "duration": 5,
                "seed": 42,
            }
        )
    finally:
        local_app.CANCEL_EVENTS.clear()

    directory = tmp_path / job["job_id"]
    assert (directory / "references/opening.png").read_bytes() == b"fixture"
    assert (directory / "references/ending.jpg").read_bytes() == b"fixture"
    assert [item["id"] for item in job["references"]] == ["opening", "ending"]
    assert all(item["sha256"] for item in job["references"])
    assert queue_stub.queued == [job["job_id"]]


def test_create_extension_job_extracts_exact_parent_endpoint_and_records_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class QueueStub:
        queued: list[str] = []

        def put(self, job_id: str) -> None:
            self.queued.append(job_id)

    parent = _write_job(tmp_path, "parent-123", "completed")
    parent_job = json.loads((parent / "job.json").read_text())
    parent_job.update({"final_video": "final-video.mp4", "seed": 10})
    (parent / "job.json").write_text(json.dumps(parent_job))
    (parent / "final-video.assembly.json").write_text(
        json.dumps(
            {
                "project_id": "parent-123",
                "status": "completed",
                "dependency_digest": "d" * 64,
                "output": {
                    "path": "final-video.mp4",
                    "sha256": local_app.sha256_path(parent / "final-video.mp4"),
                },
            }
        )
    )
    queue_stub = QueueStub()
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    monkeypatch.setattr(local_app, "JOB_QUEUE", queue_stub)
    monkeypatch.setattr(local_app, "_video_frame_details", lambda *_: (241, 24.0))
    monkeypatch.setattr(
        local_app,
        "_extract_frame",
        lambda _source, frame, output, _ffmpeg: output.write_bytes(f"frame-{frame}".encode()),
    )
    try:
        job = create_extension_job(
            "parent-123",
            {
                "prompt": "The camera keeps moving forward while the actor continues walking.",
                "clips": 2,
                "duration": 5,
                "seed": 11,
            },
        )
    finally:
        local_app.CANCEL_EVENTS.clear()

    directory = tmp_path / job["job_id"]
    assert (directory / "parent-assembly.mp4").read_bytes() == b"video"
    assert (directory / "references/extension-start.png").read_bytes() == b"frame-240"
    assert job["parent_job_id"] == "parent-123"
    assert job["extension"]["endpoint_source_frame"] == 240
    assert job["extension"]["parent_dependency_digest"] == "d" * 64
    assert job["extension"]["lineage_depth"] == 1
    assert job["references"][0]["role"] == "inherited_assembly_endpoint"
    assert queue_stub.queued == [job["job_id"]]


def test_parent_run_cannot_be_deleted_while_extension_depends_on_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    parent = _write_job(tmp_path, "parent-123", "completed")
    child = _write_job(tmp_path, "child-456", "completed")
    child_job = json.loads((child / "job.json").read_text())
    child_job["parent_job_id"] = "parent-123"
    (child / "job.json").write_text(json.dumps(child_job))

    with pytest.raises(ValueError, match="immutable parent"):
        delete_job("parent-123")

    assert parent.is_dir()
    assert child.is_dir()


def test_extension_rejects_parent_video_changed_after_assembly(tmp_path: Path) -> None:
    video = tmp_path / "final-video.mp4"
    video.write_bytes(b"changed")
    video.with_suffix(".assembly.json").write_text(
        json.dumps(
            {
                "project_id": "parent-123",
                "status": "completed",
                "dependency_digest": "d" * 64,
                "output": {"sha256": "a" * 64},
            }
        )
    )

    with pytest.raises(ValueError, match="changed since assembly validation"):
        local_app._validate_parent_assembly("parent-123", video)


def test_extension_assembly_keeps_parent_and_drops_child_duplicate_frame_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    directory = tmp_path / "extension-123"
    references = directory / "references"
    references.mkdir(parents=True)
    (directory / "parent-assembly.mp4").write_bytes(b"parent")
    (references / "extension-start.png").write_bytes(b"endpoint")
    generated = directory / "clip-0001.mp4"
    generated.write_bytes(b"generated")
    job = {
        "job_id": "extension-123",
        "created_at": "2026-08-17T00:00:00+00:00",
        "parent_job_id": "parent-123",
        "settings": {"frames_per_clip": 121, "frame_rate": 24},
        "extension": {
            "parent_assembly": {"path": "parent-assembly.mp4", "sha256": "a" * 64},
            "endpoint_frame": {
                "path": "references/extension-start.png",
                "sha256": "b" * 64,
            },
            "parent_frame_count": 241,
            "parent_frame_rate": 24,
        },
    }
    (directory / "job.json").write_text(json.dumps(job))

    def fake_assemble(project_path: Path, cut_path: Path, output: Path) -> None:
        project = json.loads(project_path.read_text())
        cut = json.loads(cut_path.read_text())
        assert [shot["shot_id"] for shot in project["shots"]] == [
            "parent-assembly",
            "shot-0001",
        ]
        assert cut["clips"][0]["edit"]["source_out_frame_inclusive"] == 240
        assert cut["clips"][1]["edit"]["source_in_frame"] == 1
        assert project["boundaries"][0]["source_frame"] == 240
        output.write_bytes(b"assembled")

    monkeypatch.setattr(local_app, "assemble_cut", fake_assemble)

    result = _assemble_job("extension-123", [generated], [])

    assert result.read_bytes() == b"assembled"


def test_extension_assembly_has_exact_combined_frame_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("FFmpeg and ffprobe are required")
    monkeypatch.setattr(local_app, "JOBS_ROOT", tmp_path)
    directory = tmp_path / "extension-real"
    references = directory / "references"
    references.mkdir(parents=True)

    def generate(path: Path, frames: int, colour: str) -> None:
        duration = frames / 24
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
                f"color={colour}:size=320x192:rate=24:duration={duration}",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:sample_rate=48000:duration={duration}",
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

    parent = directory / "parent-assembly.mp4"
    generated = directory / "clip-0001.mp4"
    endpoint = references / "extension-start.png"
    generate(parent, 24, "blue")
    generate(generated, 49, "red")
    local_app._extract_frame(parent, 23, endpoint, "ffmpeg")
    job = {
        "job_id": "extension-real",
        "created_at": "2026-08-17T00:00:00+00:00",
        "parent_job_id": "parent-real",
        "settings": {"frames_per_clip": 49, "frame_rate": 24},
        "extension": {
            "parent_assembly": {"path": "parent-assembly.mp4", "sha256": "a" * 64},
            "endpoint_frame": {
                "path": "references/extension-start.png",
                "sha256": "b" * 64,
            },
            "parent_frame_count": 24,
            "parent_frame_rate": 24,
        },
    }
    (directory / "job.json").write_text(json.dumps(job))

    result = _assemble_job("extension-real", [generated], [])

    frame_count, frame_rate = local_app._video_frame_details(result, "ffprobe")
    assert frame_rate == 24
    assert frame_count == 72  # 24 parent + 49 child - one shared frame
