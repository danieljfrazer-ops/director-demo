from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from director_demo.config import Settings
from director_demo.director import create_shot_plan
from director_demo.editorial import (
    AssemblyRecord,
    CutManifest,
    EditorialError,
    EditorialProject,
    QualityReview,
    TakeRecord,
    assemble_cut,
    check_assembly_freshness,
    dependency_digest,
    export_editorial_history,
    load_cut_manifest,
    load_editorial_project,
    register_take,
    resolve_cut,
    select_take,
    timeline_duration,
    update_take_review,
    write_model,
)
from director_demo.ltx import LtxError, LtxRenderSpec, NativeLtxRenderer
from director_demo.production import (
    LtxPromptMode,
    ProductionError,
    build_production_manifest,
    write_manifest,
)
from director_demo.runs import export_run_history
from director_demo.schemas import ShotPlan
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


@app.command("shot-plan-schema")
def shot_plan_schema() -> None:
    """Print the exact JSON schema expected from a local planning LLM."""
    typer.echo(json.dumps(ShotPlan.model_json_schema(), indent=2))


@app.command("compile-production")
def compile_production(
    shot_plan: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    project_root: Annotated[Path, typer.Option("--project-root")] = Path("data/project"),
    out: Annotated[Path, typer.Option("--out", "-o")] = Path("data/project/production.json"),
    prompt_mode: Annotated[LtxPromptMode, typer.Option("--prompt-mode")] = (
        LtxPromptMode.CONTEXT_LOCKED
    ),
) -> None:
    """Compile validated creative JSON into an M5-safe production manifest."""
    try:
        plan_data = json.loads(shot_plan.read_text(encoding="utf-8"))
        manifest = build_production_manifest(
            ShotPlan.model_validate(plan_data),
            project_root=project_root,
            prompt_mode=prompt_mode,
        )
        typer.echo(write_manifest(manifest, out))
    except (json.JSONDecodeError, ValueError, ProductionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


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


@app.command("editorial-schemas")
def editorial_schemas() -> None:
    """Print the versioned editorial project, cut, and assembly schemas."""
    typer.echo(
        json.dumps(
            {
                "editorial_project": EditorialProject.model_json_schema(),
                "cut_manifest": CutManifest.model_json_schema(),
                "assembly_record": AssemblyRecord.model_json_schema(),
            },
            indent=2,
        )
    )


@app.command("validate-cut")
def validate_cut(
    project: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    cut: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Validate take selection, immutable hashes, edits, media, and cut dependencies."""
    settings = Settings()
    try:
        project_model = load_editorial_project(project)
        cut_model = load_cut_manifest(cut)
        clips = resolve_cut(
            project_model,
            cut_model,
            project_manifest_path=project,
            ffprobe_binary=settings.ffprobe_binary,
        )
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        json.dumps(
            {
                "project_id": project_model.project_id,
                "cut_id": cut_model.cut_id,
                "revision": cut_model.revision,
                "clip_count": len(clips),
                "duration_seconds": timeline_duration(clips, cut_model.delivery),
                "dependency_digest": dependency_digest(cut_model, clips),
            },
            indent=2,
        )
    )


@app.command("assemble-cut")
def assemble_cut_command(
    project: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    cut: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Argument()],
) -> None:
    """Assemble one versioned, non-destructive editorial cut and provenance record."""
    settings = Settings()
    try:
        record = assemble_cut(
            project,
            cut,
            output,
            ffmpeg_binary=settings.ffmpeg_binary,
            ffprobe_binary=settings.ffprobe_binary,
        )
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(record.model_dump_json(indent=2))


@app.command("export-editorial")
def export_editorial(
    projects: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path("examples"),
    outputs: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path("outputs"),
    public: Annotated[Path, typer.Option(file_okay=False)] = Path("web/public"),
) -> None:
    """Export validated projects, cuts, reviews, edits, and deliveries for the local UI."""
    try:
        typer.echo(export_editorial_history(projects, outputs, public))
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


@app.command("check-assembly")
def check_assembly(
    project: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    cut: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    assembly: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Report whether an assembled delivery still matches its manifests and artifacts."""
    settings = Settings()
    try:
        record = AssemblyRecord.model_validate_json(assembly.read_text(encoding="utf-8"))
        freshness = check_assembly_freshness(
            record,
            project,
            cut,
            ffprobe_binary=settings.ffprobe_binary,
        )
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(freshness.model_dump_json(indent=2))
    if not freshness.fresh:
        raise typer.Exit(3)


@app.command("register-take")
def register_take_command(
    project: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    shot_id: Annotated[str, typer.Argument()],
    take: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Atomically append an immutable take document without selecting it."""
    try:
        updated = register_take(
            load_editorial_project(project),
            shot_id,
            TakeRecord.model_validate_json(take.read_text(encoding="utf-8")),
        )
        typer.echo(write_model(updated, project))
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


@app.command("review-take")
def review_take_command(
    project: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    shot_id: Annotated[str, typer.Argument()],
    take_id: Annotated[str, typer.Argument()],
    review: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
) -> None:
    """Atomically apply a structured technical/creative review to one take."""
    try:
        updated = update_take_review(
            load_editorial_project(project),
            shot_id,
            take_id,
            QualityReview.model_validate_json(review.read_text(encoding="utf-8")),
        )
        typer.echo(write_model(updated, project))
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


@app.command("select-take")
def select_take_command(
    project: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    shot_id: Annotated[str, typer.Argument()],
    take_id: Annotated[str | None, typer.Argument()] = None,
) -> None:
    """Select an approved take, or omit TAKE_ID to explicitly clear selection."""
    try:
        updated = select_take(load_editorial_project(project), shot_id, take_id)
        typer.echo(write_model(updated, project))
    except (EditorialError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc


@app.command("ltx-preflight")
def ltx_preflight() -> None:
    """Check the pinned native LTX runtime, models, disk, and local tools."""
    settings = Settings()
    renderer = NativeLtxRenderer(
        runtime_root=settings.ltx_runtime_root,
        models_root=settings.ltx_models_root,
        ffprobe_binary=settings.ffprobe_binary,
        minimum_free_gib=settings.ltx_minimum_free_gib,
    )
    report = renderer.preflight()
    typer.echo(f"runtime_commit={report.runtime_commit or 'unknown'}")
    typer.echo(f"mps_backend={report.mps_backend or 'unknown'}")
    typer.echo(f"entrypoint_options={len(report.entrypoint_options)}")
    typer.echo(f"free_disk_gib={report.free_disk_gib:.1f}")
    if report.issues:
        for issue in report.issues:
            typer.echo(f"BLOCKED: {issue}", err=True)
        raise typer.Exit(2)
    typer.echo("ready")


@app.command("render-ltx")
def render_ltx(
    image: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    prompt_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[Path, typer.Argument()],
    width: Annotated[int | None, typer.Option()] = None,
    height: Annotated[int | None, typer.Option()] = None,
    frames: Annotated[int | None, typer.Option()] = None,
    frame_rate: Annotated[float | None, typer.Option("--fps")] = None,
    seed: Annotated[int, typer.Option()] = 42,
    offload: Annotated[
        str | None, typer.Option(help="Weight residency: disk, cpu, or none.")
    ] = None,
    max_batch_size: Annotated[int | None, typer.Option("--max-batch-size")] = None,
    parent_take_id: Annotated[
        str | None, typer.Option(help="Immutable parent take for a targeted retake.")
    ] = None,
    conditioning_boundary_id: Annotated[
        str | None,
        typer.Option(help="Approved boundary artifact identifier used for conditioning."),
    ] = None,
    retake_reason: Annotated[
        str | None, typer.Option(help="Why this new immutable take is being attempted.")
    ] = None,
    label: Annotated[str | None, typer.Option(help="Human-readable experiment label.")] = None,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Repeatable run tag.")] = None,
    event_log: Annotated[Path | None, typer.Option()] = None,
    dry_run: Annotated[bool, typer.Option(help="Print the exact LTX command only.")] = False,
) -> None:
    """Render one approved image-conditioned take through strict LTX-2.5."""
    settings = Settings()
    renderer = NativeLtxRenderer(
        runtime_root=settings.ltx_runtime_root,
        models_root=settings.ltx_models_root,
        ffprobe_binary=settings.ffprobe_binary,
        minimum_free_gib=settings.ltx_minimum_free_gib,
    )
    spec = LtxRenderSpec(
        image=image,
        prompt=prompt_file.read_text(encoding="utf-8").strip(),
        output=output,
        width=width if width is not None else settings.ltx_default_width,
        height=height if height is not None else settings.ltx_default_height,
        frames=frames if frames is not None else settings.ltx_default_frames,
        frame_rate=(
            frame_rate if frame_rate is not None else settings.ltx_default_frame_rate
        ),
        seed=seed,
        offload=offload if offload is not None else settings.ltx_default_offload,
        max_batch_size=(
            max_batch_size
            if max_batch_size is not None
            else settings.ltx_default_max_batch_size
        ),
        parent_take_id=parent_take_id,
        conditioning_boundary_id=conditioning_boundary_id,
        retake_reason=retake_reason,
    )
    try:
        if dry_run:
            typer.echo(json.dumps(renderer.command(spec), indent=2))
            return
        metadata = renderer.render(
            spec,
            event_log=event_log or output.parent / "events.jsonl",
            label=label,
            tags=tuple(tag or ()),
        )
    except LtxError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(metadata, indent=2))


@app.command("export-runs")
def export_runs(
    outputs_root: Annotated[Path, typer.Option("--outputs", exists=True, file_okay=False)] = Path(
        "outputs"
    ),
    public_root: Annotated[Path, typer.Option("--public", file_okay=False)] = Path("web/public"),
) -> None:
    """Export validated local run records for the read-only browser archive."""
    typer.echo(export_run_history(outputs_root, public_root))


if __name__ == "__main__":
    app()
