from pathlib import Path
from runpy import run_path


def test_m5_profile_uses_distilled_int8_convrot_weights() -> None:
    script = Path(__file__).parents[1] / "scripts" / "download_ltx25.py"
    namespace = run_path(str(script))
    files = namespace["FILES"]

    assert any("distilled-transformer-comfy-int8-convrot" in name for name in files)
    assert any("gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot" in name for name in files)
    assert not any("distilled-transformer-bf16" in name for name in files)
    assert not any("dev-transformer" in name for name in files)
