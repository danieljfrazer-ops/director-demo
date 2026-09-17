from pathlib import Path

import pytest

from director_demo.editorial import ArtifactRef
from director_demo.extension import ExtensionClipPlan, make_extension_manifest

HASH_A = "a" * 64
HASH_B = "b" * 64


def test_extension_manifest_preserves_exact_parent_endpoint_lineage() -> None:
    manifest = make_extension_manifest(
        extension_id="extension-2",
        parent_job_id="parent-1",
        parent_extension_id="extension-1",
        lineage_depth=2,
        prompt="The actor continues walking without breaking stride.",
        parent_assembly=ArtifactRef(path=Path("parent-assembly.mp4"), sha256=HASH_A),
        parent_dependency_digest="c" * 64,
        endpoint_frame=ArtifactRef(path=Path("references/extension-start.png"), sha256=HASH_B),
        parent_frame_count=241,
        parent_frame_rate=24,
        clip_count=3,
        seconds_per_clip=5,
        seed=43,
    )

    assert manifest.endpoint_source_frame == 240
    assert manifest.plan.frames_per_clip == 121
    assert manifest.parent_extension_id == "extension-1"
    assert manifest.lineage_depth == 2


def test_extension_plan_rejects_duration_frame_mismatch() -> None:
    with pytest.raises(ValueError, match="frame count"):
        ExtensionClipPlan(
            clip_count=1,
            seconds_per_clip=5,
            frames_per_clip=49,
            seed=1,
        )
