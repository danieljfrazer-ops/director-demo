import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import director_demo.ltx as ltx_module
from director_demo.cli import app
from director_demo.ltx import (
    PINNED_LTX_COMMIT,
    JsonlEventLog,
    LtxError,
    LtxImageConditioning,
    LtxModelPaths,
    LtxProgress,
    LtxProgressParser,
    LtxRenderSpec,
    NativeLtxRenderer,
    _attempt_process_log,
    validate_media,
)


def make_spec(tmp_path: Path, **overrides: object) -> LtxRenderSpec:
    image = tmp_path / "anchor.png"
    image.write_bytes(b"not-decoded-by-unit-tests")
    values: dict[str, object] = {
        "image": image,
        "prompt": "The actor breathes softly while the camera pushes in.",
        "output": tmp_path / "take.mp4",
    }
    values.update(overrides)
    return LtxRenderSpec(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"width": 480}, "multiples of 64"),
        ({"height": 288}, "multiples of 64"),
        ({"frames": 50}, "8n.*1"),
        ({"frame_rate": 0}, "positive"),
        ({"offload": "magic"}, "disk, cpu, none"),
        ({"max_batch_size": 0}, "batch size must be positive"),
        ({"parent_take_id": "take-001"}, "must record a retake reason"),
    ],
)
def test_render_spec_rejects_invalid_geometry(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(LtxError, match=message):
        make_spec(tmp_path, **overrides).validate()


def test_command_uses_strict_bf16_disk_streaming_profile(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    renderer = NativeLtxRenderer(
        runtime_root=tmp_path / "runtime",
        models_root=tmp_path / "models",
    )

    command = renderer.command(spec)

    assert "ltx_pipelines.distilled" in command
    assert command[command.index("--offload") + 1] == "disk"
    assert command[command.index("--max-batch-size") + 1] == "1"
    assert "--audio-skip-step" not in command
    assert "--quantization" not in command
    assert any("distilled-transformer-bf16" in value for value in command)
    assert any("video-vae-conv-bf16" in value for value in command)


def test_command_passes_multiple_images_at_exact_frames(tmp_path: Path) -> None:
    start = tmp_path / "start.png"
    end = tmp_path / "end.png"
    start.write_bytes(b"start")
    end.write_bytes(b"end")
    spec = make_spec(
        tmp_path,
        image=start,
        image_conditionings=(
            LtxImageConditioning("start-frame", start, 0),
            LtxImageConditioning("end-frame", end, 120),
        ),
    )
    renderer = NativeLtxRenderer(runtime_root=tmp_path / "runtime", models_root=tmp_path / "models")

    command = renderer.command(spec)
    image_positions = [index for index, value in enumerate(command) if value == "--image"]

    assert len(image_positions) == 2
    assert command[image_positions[0] + 1 : image_positions[0] + 4] == [
        str(start.resolve()),
        "0",
        "1.0",
    ]
    assert command[image_positions[1] + 1 : image_positions[1] + 4] == [
        str(end.resolve()),
        "120",
        "1.0",
    ]


def test_model_profile_lists_only_required_files(tmp_path: Path) -> None:
    models = LtxModelPaths(tmp_path)
    assert len(models.missing()) == 5
    for path in models.all():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert models.missing() == []


def test_preflight_uses_configured_absolute_runtime_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    models_root = tmp_path / "models"
    (runtime / ".venv/bin").mkdir(parents=True)
    (runtime / ".venv/bin/python").touch()
    (runtime / "pyproject.toml").touch()
    models = LtxModelPaths(models_root)
    for path in models.all():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    renderer = NativeLtxRenderer(
        runtime_root=runtime,
        models_root=models_root,
        minimum_free_gib=20.0,
    )
    disk_usage_type = type(shutil.disk_usage(tmp_path))
    gib = 1024**3
    monkeypatch.setattr(
        ltx_module.shutil,
        "disk_usage",
        lambda _: disk_usage_type(460 * gib, 435 * gib, 25 * gib),
    )
    monkeypatch.setattr(ltx_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(ltx_module.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(ltx_module.shutil, "which", lambda _: "/opt/homebrew/bin/ffprobe")
    monkeypatch.setattr(renderer, "_runtime_commit", lambda: PINNED_LTX_COMMIT)
    monkeypatch.setattr(renderer, "_probe_mps", lambda: ("mpsgraph_zc", None))
    monkeypatch.setattr(renderer, "_probe_entrypoint_options", lambda: ((), None))

    report = renderer.preflight()

    assert report.ok
    assert report.free_disk_gib == 25.0


def test_jsonl_event_log_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path)
    log.append("started", job_id="abc", seed=42)
    log.append("completed", job_id="abc", output="take.mp4")

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [record["event"] for record in records] == ["started", "completed"]
    assert all(record["job_id"] == "abc" for record in records)


def test_process_log_is_unique_to_attempt_run_id() -> None:
    first = _attempt_process_log(Path("take.mp4"), "job-20260101T000000Z")
    second = _attempt_process_log(Path("take.mp4"), "job-20260101T000001Z")
    assert first != second
    assert first.name == "take.job-20260101T000000Z.render.log"


def test_progress_parser_reports_real_two_pass_step_counters() -> None:
    events: list[LtxProgress] = []
    parser = LtxProgressParser(events.append)

    parser.feed(
        "INFO: Building text encoder\n"
        "INFO: Prompt encoding complete\n"
        "INFO: Running denoising loop (8 steps, 512x288 121 frames @ 24.0 fps)\r"
        " 25%|██▌       | 2/8 [01:38<04:57, 49.60s/it]\r"
        "INFO: Building video encoder + spatial upsampler\n"
        "INFO: Running denoising loop (3 steps, 1024x576 121 frames @ 24.0 fps)\r"
        " 67%|██████▋   | 2/3 [01:59<00:59, 59.96s/it]\r"
        "INFO: Building video decoder\nINFO: Building audio decoder + vocoder\n"
    )
    parser.finish()

    assert LtxProgress("base_denoise", "Initial generation", 2, 8) in events
    assert LtxProgress("refinement", "High-resolution refinement", 2, 3) in events
    assert events[-2].phase == "video_decode"
    assert events[-1].phase == "audio_decode"


def test_progress_callback_failure_does_not_break_parser() -> None:
    def fail(_: LtxProgress) -> None:
        raise RuntimeError("UI unavailable")

    parser = LtxProgressParser(fail)
    parser.feed("INFO: Running denoising loop (8 steps, 512x288 49 frames @ 24.0 fps)\r")
    parser.finish()


def test_validate_media_accepts_expected_video() -> None:
    spec = LtxRenderSpec(
        image=Path("anchor.png"),
        prompt="Motion.",
        output=Path("take.mp4"),
    )
    metadata = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1024,
                "height": 576,
                "avg_frame_rate": "24/1",
            },
            {"codec_type": "audio"},
        ]
    }
    validate_media(metadata, spec)


def test_validate_media_rejects_wrong_resolution() -> None:
    spec = LtxRenderSpec(
        image=Path("anchor.png"),
        prompt="Motion.",
        output=Path("take.mp4"),
    )
    metadata = {
        "streams": [
            {
                "codec_type": "video",
                "width": 512,
                "height": 576,
                "avg_frame_rate": "24/1",
            }
        ]
    }
    with pytest.raises(LtxError, match="Unexpected output size"):
        validate_media(metadata, spec)


def test_render_cli_dry_run_prints_exact_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "anchor.png"
    prompt = tmp_path / "prompt.txt"
    image.write_bytes(b"fixture")
    prompt.write_text("The actor blinks while the camera pushes in.")

    result = CliRunner().invoke(
        app,
        ["render-ltx", str(image), str(prompt), "take.mp4", "--dry-run"],
    )

    assert result.exit_code == 0
    command = json.loads(result.stdout)
    assert command[command.index("--offload") + 1] == "disk"
    assert command[command.index("--width") + 1] == "1024"
    assert command[command.index("--num-frames") + 1] == "121"
    assert "--audio-skip-step" not in command
