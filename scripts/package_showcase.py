#!/usr/bin/env python3
"""Build a deliberately minimal, privacy-filtered recorded showcase package.

The selection is a private maintainer artifact. This script is the only route by
which fields from an original run may enter the checked-in public manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

MAX_STATIC_ASSET_BYTES = 25 * 1024 * 1024
ALLOWED_STARTING_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class PackageError(RuntimeError):
    """The requested package would violate a publication invariant."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise PackageError(f"Expected an object in {path}")
    return value


def resolve_inside(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as error:
        raise PackageError(f"Path escapes repository: {relative}") from error
    return candidate


def require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageError(f"{name} must be an object")
    return value


def public_subset(value: Any, allowed: set[str]) -> dict[str, Any]:
    source = require_object(value, "metadata")
    return {key: source[key] for key in allowed if key in source and source[key] is not None}


def published_prompt(original_prompt: str, selection: dict[str, Any], asset_id: str) -> str:
    """Return the explicitly approved public prompt without altering private provenance."""
    override = selection.get("public_prompt")
    if override is None:
        return original_prompt
    if not isinstance(override, str) or not override.strip():
        raise PackageError(f"Asset {asset_id} public_prompt must be a non-empty string")
    return override


def first_run_record(job_directory: Path) -> Path:
    records = sorted(job_directory.glob("*.run.json"))
    if len(records) != 1:
        raise PackageError(f"Expected exactly one run record in {job_directory}")
    return records[0]


def source_review(project: dict[str, Any]) -> dict[str, Any]:
    shots = project.get("shots")
    if not isinstance(shots, list) or not shots:
        return {}
    takes = require_object(shots[0], "first shot").get("takes")
    if not isinstance(takes, list) or not takes:
        return {}
    return public_subset(
        require_object(takes[0], "first take").get("review", {}),
        {"technical", "creative", "delivery"},
    )


def publish_copy(source: Path, destination: Path, expected_hash: str, artifact_name: str) -> int:
    """Copy a selected immutable artifact without replacing conflicting bytes."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != expected_hash:
            raise PackageError(f"Refusing to replace conflicting destination: {destination}")
    else:
        shutil.copyfile(source, destination)
    if sha256(destination) != expected_hash:
        raise PackageError(f"Published copy does not match source: {artifact_name}")
    return destination.stat().st_size


def public_asset(root: Path, selection: dict[str, Any], output: Path) -> dict[str, Any]:
    asset_id = selection.get("id")
    if not isinstance(asset_id, str) or not asset_id:
        raise PackageError("Asset ID must be a non-empty string")
    source_name = selection.get("source")
    job_name = selection.get("job_directory")
    expected_hash = selection.get("expected_sha256")
    if not all(
        isinstance(value, str) and value for value in (source_name, job_name, expected_hash)
    ):
        raise PackageError(f"Asset {asset_id} has incomplete private source metadata")
    source = resolve_inside(root, source_name)
    job_directory = resolve_inside(root, job_name)
    if not source.is_file():
        raise PackageError(f"Missing source for {asset_id}: {source}")
    source_hash = sha256(source)
    if source_hash != expected_hash:
        raise PackageError(f"Source hash changed for {asset_id}: {source_hash}")
    size = source.stat().st_size
    if size >= MAX_STATIC_ASSET_BYTES:
        raise PackageError(f"{asset_id} is too large for a Pages static asset: {size}")

    job_path = job_directory / "job.json"
    project_path = job_directory / "final-video.project.json"
    run_path = first_run_record(job_directory)
    for sidecar in (job_path, project_path, run_path):
        if not sidecar.is_file():
            raise PackageError(f"Missing provenance sidecar: {sidecar}")
    job = read_json(job_path)
    project = read_json(project_path)
    run = read_json(run_path)

    prompt = job.get("prompt")
    reference_name = job.get("reference")
    expected_reference_hash = selection.get("expected_reference_sha256")
    if not isinstance(prompt, str) or not prompt.strip():
        raise PackageError(f"Asset {asset_id} has no publishable prompt")
    prompt = published_prompt(prompt, selection, asset_id)
    if not isinstance(reference_name, str) or not reference_name:
        raise PackageError(f"Asset {asset_id} has no starting-image reference")
    if not isinstance(expected_reference_hash, str) or not expected_reference_hash:
        raise PackageError(f"Asset {asset_id} has no expected starting-image hash")
    reference = resolve_inside(job_directory, reference_name)
    if reference.suffix.lower() not in ALLOWED_STARTING_IMAGE_SUFFIXES:
        raise PackageError(f"Asset {asset_id} starting image has an unsupported type")
    if not reference.is_file():
        raise PackageError(f"Missing starting image for {asset_id}: {reference}")
    reference_hash = sha256(reference)
    if reference_hash != expected_reference_hash:
        raise PackageError(f"Starting image hash changed for {asset_id}: {reference_hash}")
    reference_size = reference.stat().st_size
    if reference_size >= MAX_STATIC_ASSET_BYTES:
        raise PackageError(f"{asset_id} starting image is too large for a Pages static asset")
    reference_filename = (
        f"{asset_id}-starting-frame-{reference_hash[:12]}{reference.suffix.lower()}"
    )
    reference_destination = output / "starting-frames" / reference_filename
    publish_copy(reference, reference_destination, reference_hash, f"{asset_id} starting image")

    filename = f"{asset_id}-{source_hash[:12]}.mp4"
    destination = output / "media" / filename
    publish_copy(source, destination, source_hash, asset_id)

    settings = public_subset(
        job.get("settings", {}),
        {"width", "height", "frame_rate", "frames_per_clip", "offload", "max_batch_size", "join"},
    )
    engine = public_subset(run.get("engine", {}), {"name", "pipeline", "precision", "quantization"})
    review = source_review(project)
    return {
        "id": asset_id,
        "title": selection.get("title", asset_id),
        "selection_reason": selection.get("selection_reason", "Recorded local workflow example."),
        "prompt": prompt,
        "published": {"url": f"/showcase/media/{filename}", "sha256": source_hash, "bytes": size},
        "starting_frame": {
            "url": f"/showcase/starting-frames/{reference_filename}",
            "sha256": reference_hash,
            "bytes": reference_size,
        },
        "media": {
            **public_subset(
                selection.get("media", {}),
                {"duration_seconds", "width", "height", "frame_rate", "video_codec", "audio_codec"},
            ),
            "resolution_provenance": "native",
        },
        "settings": settings,
        "engine": engine,
        "lineage": {"parent_asset_id": selection.get("parent_asset_id")},
        "review": {
            "technical": review.get("technical", "unverified"),
            "creative": "pending_human_review",
            "delivery": review.get("delivery", "pending"),
        },
        "rights": public_subset(
            selection.get("rights", {}), {"status", "publication_basis", "reuse_terms"}
        ),
        "limitations": selection.get(
            "limitations",
            ["Recorded result; this hosted showcase does not run the generation model."],
        ),
    }


def package(root: Path, selection_path: Path, output: Path) -> dict[str, Any]:
    root = root.resolve()
    selection = read_json(selection_path)
    assets = selection.get("assets")
    if not isinstance(assets, list) or not assets:
        raise PackageError("Selection must contain at least one asset")
    ids = [asset.get("id") if isinstance(asset, dict) else None for asset in assets]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        raise PackageError("Asset IDs must be present and unique")
    manifest_assets = [
        public_asset(root, require_object(asset, "asset"), output) for asset in assets
    ]
    by_id = {asset["id"]: asset for asset in manifest_assets}
    for asset in manifest_assets:
        parent_id = asset["lineage"].get("parent_asset_id")
        if parent_id:
            if parent_id not in by_id:
                raise PackageError(f"Unknown parent asset ID: {parent_id}")
            asset["lineage"]["parent_asset_sha256"] = by_id[parent_id]["published"]["sha256"]
    manifest = {
        "schema_version": selection.get("schema_version"),
        "package_id": selection.get("package_id"),
        "mode": "recorded_showcase",
        "notice": (
            "Generated locally. This hosted showcase plays recorded outputs and does not run "
            "the model."
        ),
        "privacy_notice": (
            "The recorded starting frame and generation prompt are published for each selected "
            "clip. Run records, timestamps, paths, and unselected inputs remain private."
        ),
        "assets": manifest_assets,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--selection",
        type=Path,
        help="Private selection record (required unless the ignored default exists).",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    selection = args.selection or root / "outputs/publication/selection.json"
    if not selection.is_file():
        parser.error("--selection is required; the default private selection was not found")
    output = args.output or root / "web/public/showcase"
    manifest = package(root, selection.resolve(), output.resolve())
    total = sum(asset["published"]["bytes"] for asset in manifest["assets"])
    print(f"Packaged {len(manifest['assets'])} assets ({total} bytes) in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
