from pathlib import Path

from director_demo.stitcher import _concat_escape, _natural_key


def test_natural_key_orders_numbered_clips() -> None:
    names = [Path("10.mp4"), Path("2.mp4"), Path("1.mp4")]
    assert [path.name for path in sorted(names, key=_natural_key)] == ["1.mp4", "2.mp4", "10.mp4"]


def test_concat_escape_handles_apostrophe() -> None:
    assert "'\\''" in _concat_escape(Path("director's-cut.mp4"))
