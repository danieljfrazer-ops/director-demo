from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.package_showcase import PackageError, package


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    job = root / "outputs/app-jobs/job-1"
    job.mkdir(parents=True)
    video = job / "final-video.mp4"
    video.write_bytes(b"immutable-video")
    reference = job / "references" / "starting-frame.png"
    reference.parent.mkdir()
    reference.write_bytes(b"immutable-starting-frame")
    (job / "job.json").write_text(
        json.dumps(
            {
                "job_id": "private-job-id",
                "prompt": "public creative direction",
                "reference": "references/starting-frame.png",
                "compiled_prompts": {"1": "private"},
                "references": [{"id": "private-reference", "path": "/private/reference.png"}],
                "settings": {"width": 1024, "height": 576, "frame_rate": 24, "private": "no"},
            }
        )
    )
    (job / "final-video.project.json").write_text(
        json.dumps(
            {
                "shots": [
                    {
                        "takes": [
                            {
                                "review": {
                                    "technical": "pass",
                                    "creative": "approved",
                                    "delivery": "pending",
                                    "reviewer": "private",
                                    "summary": "private",
                                }
                            }
                        ]
                    }
                ]
            }
        )
    )
    (job / "one.run.json").write_text(
        json.dumps(
            {
                "engine": {"name": "fixture", "precision": "bf16", "runtime_commit": "private"},
                "performance": {"peak_rss_bytes": 1},
            }
        )
    )
    selection = root / "selection.json"
    selection.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "package_id": "fixture",
                "assets": [
                    {
                        "id": "clip",
                        "title": "Clip",
                        "source": "outputs/app-jobs/job-1/final-video.mp4",
                        "job_directory": "outputs/app-jobs/job-1",
                        "expected_sha256": _sha(video),
                        "expected_reference_sha256": _sha(reference),
                        "selection_reason": "Recorded workflow example.",
                        "media": {
                            "duration_seconds": 1,
                            "width": 1024,
                            "height": 576,
                            "frame_rate": 24,
                            "private": "no",
                        },
                        "rights": {"status": "test", "private": "no"},
                    }
                ],
            }
        )
    )
    return root, selection


def test_package_copies_bytes_and_only_emits_allowlisted_fields(tmp_path: Path) -> None:
    root, selection = _fixture(tmp_path)
    manifest = package(root, selection, root / "public/showcase")
    asset = manifest["assets"][0]
    published = root / "public" / asset["published"]["url"].lstrip("/")
    starting_frame = root / "public" / asset["starting_frame"]["url"].lstrip("/")
    assert published.read_bytes() == b"immutable-video"
    assert starting_frame.read_bytes() == b"immutable-starting-frame"
    assert asset["published"]["sha256"] == _sha(published)
    assert asset["starting_frame"]["sha256"] == _sha(starting_frame)
    assert asset["prompt"] == "public creative direction"
    assert asset["review"] == {
        "technical": "pass",
        "creative": "pending_human_review",
        "delivery": "pending",
    }
    public_text = json.dumps(manifest)
    for forbidden in (
        "private-job-id",
        "compiled_prompts",
        "private-reference",
        "/private/reference.png",
        "runtime_commit",
        "reviewer",
        "summary",
        "peak_rss",
    ):
        assert forbidden not in public_text
    assert set(asset) == {
        "id",
        "title",
        "selection_reason",
        "prompt",
        "published",
        "starting_frame",
        "media",
        "settings",
        "engine",
        "lineage",
        "review",
        "rights",
        "limitations",
    }


def test_package_uses_explicit_public_prompt_override_without_leaking_original(
    tmp_path: Path,
) -> None:
    root, selection = _fixture(tmp_path)
    payload = json.loads(selection.read_text())
    payload["assets"][0]["public_prompt"] = "Approved showcase direction"
    selection.write_text(json.dumps(payload))

    manifest = package(root, selection, root / "public/showcase")

    public_text = json.dumps(manifest)
    assert manifest["assets"][0]["prompt"] == "Approved showcase direction"
    assert "public creative direction" not in public_text
    assert "public_prompt" not in public_text


@pytest.mark.parametrize("invalid_prompt", ["", "   ", 42, []])
def test_package_rejects_empty_or_non_string_public_prompt(
    tmp_path: Path, invalid_prompt: object
) -> None:
    root, selection = _fixture(tmp_path)
    payload = json.loads(selection.read_text())
    payload["assets"][0]["public_prompt"] = invalid_prompt
    selection.write_text(json.dumps(payload))

    with pytest.raises(PackageError, match="public_prompt must be a non-empty string"):
        package(root, selection, root / "public/showcase")


def test_package_rejects_path_escape(tmp_path: Path) -> None:
    root, selection = _fixture(tmp_path)
    payload = json.loads(selection.read_text())
    payload["assets"][0]["source"] = "../outside.mp4"
    selection.write_text(json.dumps(payload))
    with pytest.raises(PackageError, match="escapes repository"):
        package(root, selection, root / "public/showcase")


def test_package_rejects_changed_source(tmp_path: Path) -> None:
    root, selection = _fixture(tmp_path)
    payload = json.loads(selection.read_text())
    payload["assets"][0]["expected_sha256"] = "0" * 64
    selection.write_text(json.dumps(payload))
    with pytest.raises(PackageError, match="Source hash changed"):
        package(root, selection, root / "public/showcase")


def test_package_rejects_changed_starting_image(tmp_path: Path) -> None:
    root, selection = _fixture(tmp_path)
    payload = json.loads(selection.read_text())
    payload["assets"][0]["expected_reference_sha256"] = "0" * 64
    selection.write_text(json.dumps(payload))
    with pytest.raises(PackageError, match="Starting image hash changed"):
        package(root, selection, root / "public/showcase")


def test_package_refuses_conflicting_destination(tmp_path: Path) -> None:
    root, selection = _fixture(tmp_path)
    output = root / "public/showcase"
    manifest = package(root, selection, output)
    published = root / "public" / manifest["assets"][0]["published"]["url"].lstrip("/")
    published.write_bytes(b"different")
    with pytest.raises(PackageError, match="conflicting destination"):
        package(root, selection, output)


def test_package_requires_known_parent_and_publishes_only_parent_hash(tmp_path: Path) -> None:
    root, selection = _fixture(tmp_path)
    payload = json.loads(selection.read_text())
    payload["assets"][0]["parent_asset_id"] = "missing"
    selection.write_text(json.dumps(payload))
    with pytest.raises(PackageError, match="Unknown parent asset ID"):
        package(root, selection, root / "public/showcase")
