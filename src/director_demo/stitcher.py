from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class StitchError(RuntimeError):
    """Raised when clips cannot be assembled."""


def _natural_key(path: Path) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _concat_escape(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def stitch_clips(
    clips_folder: Path,
    output_path: Path,
    *,
    ffmpeg_binary: str = "ffmpeg",
    reencode: bool = False,
) -> Path:
    """Concatenate sequentially named MP4 clips using FFmpeg's concat demuxer.

    Stream-copy is fast but requires matching codecs, dimensions, frame rate, and
    audio layout. Set ``reencode=True`` when inputs are heterogeneous.
    """
    if shutil.which(ffmpeg_binary) is None:
        raise StitchError(f"FFmpeg binary not found: {ffmpeg_binary}")

    clips = sorted(clips_folder.glob("*.mp4"), key=_natural_key)
    if not clips:
        raise StitchError(f"No MP4 clips found in {clips_folder}")
    if output_path.resolve() in {clip.resolve() for clip in clips}:
        raise StitchError("Output path must not be one of the input clips")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="director-stitch-") as temp_dir:
        manifest = Path(temp_dir) / "concat.txt"
        manifest.write_text(
            "".join(f"file '{_concat_escape(clip)}'\n" for clip in clips),
            encoding="utf-8",
        )
        command = [ffmpeg_binary, "-hide_banner", "-y", "-f", "concat", "-safe", "0"]
        command += ["-i", str(manifest)]
        if reencode:
            command += [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
            ]
        else:
            command += ["-c", "copy", "-movflags", "+faststart"]
        command.append(str(output_path))
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise StitchError(completed.stderr.strip())
    return output_path
