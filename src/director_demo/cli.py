from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from director_demo.config import Settings
from director_demo.director import create_shot_plan
from director_demo.stitcher import stitch_clips

app = typer.Typer(no_args_is_help=True, help="Local-first AI film director tools.")


@app.command()
def plan(
    script: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("shot-plan.json"),
) -> None:
    """Turn a source script into a validated JSON shot plan."""
    result = create_shot_plan(script.read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(out)


@app.command()
def stitch(
    clips_folder: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Argument()],
    reencode: Annotated[
        bool, typer.Option(help="Normalize heterogeneous clips with H.264/AAC.")
    ] = False,
) -> None:
    """Concatenate sequentially named MP4 clips."""
    result = stitch_clips(
        clips_folder,
        output,
        ffmpeg_binary=Settings().ffmpeg_binary,
        reencode=reencode,
    )
    typer.echo(result)


if __name__ == "__main__":
    app()
