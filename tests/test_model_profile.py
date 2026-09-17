from pathlib import Path
from runpy import run_path


def test_legacy_pack_remains_distilled_and_excludes_huge_bf16_weights() -> None:
    script = Path(__file__).parents[1] / "scripts" / "download_ltx25.py"
    namespace = run_path(str(script))
    files = namespace["FILES"]

    assert any("distilled-transformer-comfy-int8-convrot" in name for name in files)
    assert any("gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot" in name for name in files)
    assert not any("distilled-transformer-bf16" in name for name in files)
    assert not any("dev-transformer" in name for name in files)


def test_legacy_int8_pack_is_blocked_on_macos() -> None:
    script = Path(__file__).parents[1] / "scripts" / "download_ltx25.py"
    namespace = run_path(str(script))

    assert namespace["platform_is_supported"]("darwin") is False
    assert namespace["platform_is_supported"]("linux") is True
    assert "aten::_int_mm" in namespace["MPS_REJECTION"]
