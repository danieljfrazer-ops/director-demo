import json
import os
from pathlib import Path

from director_demo.runs import RunRecord, export_run_history, sha256_path, write_run_record


def make_record(tmp_path: Path) -> RunRecord:
    video = tmp_path / "take.mp4"
    video.write_bytes(b"video-fixture")
    return RunRecord(
        run_id="run-001",
        job_id="job-001",
        label="Dialogue control",
        tags=["baseline", "dialogue"],
        status="completed",
        started_at="2026-08-15T20:00:00+00:00",
        completed_at="2026-08-15T20:01:00+00:00",
        elapsed_seconds=60,
        spec={"width": 448, "height": 256, "prompt": "The actor blinks."},
        engine={"name": "LTX-2.5 Fast distilled", "quantization": "none"},
        artifacts={"video": {"path": str(video), "sha256": sha256_path(video)}},
    )


def test_write_run_record_is_valid_json(tmp_path: Path) -> None:
    path = write_run_record(make_record(tmp_path), tmp_path / "take.run.json")
    assert json.loads(path.read_text())["run_id"] == "run-001"
    assert not (tmp_path / ".take.run.json.tmp").exists()


def test_export_run_history_hardlinks_video_and_adds_url(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    public = tmp_path / "public"
    record = make_record(tmp_path)
    write_run_record(record, outputs / "take.run.json")

    index_path = export_run_history(outputs, public)

    index = json.loads(index_path.read_text())
    video = index["runs"][0]["artifacts"]["video"]
    exported = public / video["url"].removeprefix("/")
    assert exported.read_bytes() == b"video-fixture"
    assert os.stat(exported).st_ino == os.stat(tmp_path / "take.mp4").st_ino
