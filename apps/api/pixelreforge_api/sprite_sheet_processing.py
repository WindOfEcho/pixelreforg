from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path

from pixelreforge_core import ProcessingCancelled, SheetExtractionSettings, SpriteSheetSettings, create_sprite_sheet, repack_sprite_sheet
from pixelreforge_core.image_io import load_image, save_image

from .models import JobMetadata, SpriteSheetParameters
from .storage import ROOT, metadata_file_path_for_job, output_file_path_for_job


@dataclass(frozen=True, slots=True)
class SpriteSheetProcessingOutput:
    output_path: Path
    metadata_path: Path | None
    atlas_size: tuple[int, int]
    frame_count: int
    warnings: tuple[str, ...]


def process_sprite_sheet_job(
    metadata: JobMetadata,
    *,
    progress: Callable[[str, float, str], None],
    cancel: Callable[[], bool],
) -> SpriteSheetProcessingOutput:
    """Run the Core atlas pipeline for a persisted sprite-sheet job."""

    params = SpriteSheetParameters.model_validate(metadata.params)
    input_paths = metadata.input_paths or [metadata.input_path]
    input_names = metadata.input_filenames or [metadata.input_filename]
    if len(input_paths) != len(input_names):
        raise ValueError("Stored sprite input paths do not match their filenames.")
    images = []
    for index, path in enumerate(input_paths, start=1):
        if cancel():
            raise ProcessingCancelled("Sprite-sheet processing was cancelled.")
        progress("load_inputs", min(15.0, 5.0 + index * 10.0 / len(input_paths)), "Loading sprite images...")
        images.append(load_image(_resolve_runtime_path(path)))
    settings = SpriteSheetSettings(
        packing_mode=params.packing_mode,
        trim_transparent=params.trim_transparent,
        alpha_threshold=params.alpha_threshold,
        padding=params.padding,
        border_padding=params.border_padding,
        extrude=params.extrude,
        max_width=params.max_width,
        max_height=params.max_height,
        max_pixels=params.max_atlas_pixels,
        atlas_width=params.atlas_width,
        atlas_height=params.atlas_height,
        power_of_two=params.power_of_two,
        force_square=params.force_square,
        allow_rotation=params.allow_rotation,
        sort_mode=params.sort_mode,
        grid_columns=params.grid_columns,
        background_color=_parse_background_color(params.background_color),
    )
    if params.input_mode == "sheet":
        if len(images) != 1:
            raise ValueError("Sheet mode requires exactly one uploaded image.")
        result = repack_sprite_sheet(
            images[0],
            SheetExtractionSettings(
                mode=params.extraction_mode,
                cell_width=params.cell_width,
                cell_height=params.cell_height,
                columns=params.columns,
                rows=params.rows,
                offset_x=params.offset_x,
                offset_y=params.offset_y,
                gap_x=params.gap_x,
                gap_y=params.gap_y,
                alpha_threshold=params.alpha_threshold,
                max_frames=params.max_frames,
            ),
            settings,
            name_prefix=Path(input_names[0]).stem or "frame",
            progress=progress,
            cancel=cancel,
        )
    else:
        result = create_sprite_sheet(images, input_names, settings, progress=progress, cancel=cancel)

    if cancel():
        raise ProcessingCancelled("Sprite-sheet processing was cancelled.")
    output_path = output_file_path_for_job(metadata.job_id)
    save_image(result.atlas, output_path)
    metadata_path: Path | None = None
    if params.include_metadata:
        metadata_path = metadata_file_path_for_job(metadata.job_id)
        metadata_path.write_text(json.dumps(result.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return SpriteSheetProcessingOutput(
        output_path=output_path,
        metadata_path=metadata_path,
        atlas_size=result.atlas.size,
        frame_count=len(result.frames),
        warnings=result.warnings,
    )


def _resolve_runtime_path(relative_path: str) -> Path:
    resolved = (ROOT / relative_path).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("Stored sprite input path is outside the runtime directory.")
    return resolved


def _parse_background_color(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    channels = value.removeprefix("#")
    if len(channels) == 6:
        channels += "FF"
    return (
        int(channels[0:2], 16),
        int(channels[2:4], 16),
        int(channels[4:6], 16),
        int(channels[6:8], 16),
    )
