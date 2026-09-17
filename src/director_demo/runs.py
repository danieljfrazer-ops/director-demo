from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field


class RunRecord(BaseModel):
    """Durable, versioned provenance for one render attempt."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    run_id: str
    job_id: str
    label: str
    tags: list[str] = Field(default_factory=list)
    status: str
    started_at: str
    completed_at: str | None = None
    elapsed_seconds: float | None = None
    spec: dict[str, Any]
    engine: dict[str, Any]
    system: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any]
    performance: dict[str, Any] = Field(default_factory=dict)
    media: dict[str, Any] | None = None
    review: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None


def sha256_path(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_run_record(record: RunRecord, path: Path) -> Path:
    """Atomically replace a run's sidecar so crashes do not leave partial JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def export_run_history(outputs_root: Path, public_root: Path) -> Path:
    """Validate ignored run sidecars and expose local media to the browser UI.

    Videos are hard-linked when possible, avoiding a second copy on the same volume.
    The generated index and media directory remain ignored by Git.
    """

    records: list[dict[str, Any]] = []
    media_root = public_root / "media"
    media_root.mkdir(parents=True, exist_ok=True)

    for sidecar in sorted(outputs_root.rglob("*.run.json")):
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        record = RunRecord.model_validate(payload)
        item = record.model_dump(mode="json")
        artifacts = cast(dict[str, Any], item["artifacts"])
        video_value = artifacts.get("video")
        if isinstance(video_value, dict) and video_value.get("path"):
            source = Path(str(video_value["path"]))
            if not source.is_absolute():
                source = (Path.cwd() / source).resolve()
            if source.is_file():
                target = media_root / f"{record.run_id}{source.suffix.lower()}"
                if target.exists() and not os.path.samefile(source, target):
                    target.unlink()
                if not target.exists():
                    try:
                        os.link(source, target)
                    except OSError:
                        shutil.copy2(source, target)
                video_value["url"] = f"/media/{target.name}"
        item["record_path"] = str(sidecar.resolve())
        records.append(item)

    records.sort(key=lambda record: str(record["started_at"]), reverse=True)
    output = public_root / "runs.json"
    output.write_text(
        json.dumps({"schema_version": 1, "runs": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    return output
