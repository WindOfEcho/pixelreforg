from collections.abc import Sequence

from PIL import Image

from ..models import CancelCallback, ProgressCallback
from .extraction import frames_from_images
from .models import AtlasFrame, SheetExtractionSettings, SpriteSheetResult, SpriteSheetSettings
from .packing import pack_frames


def create_sprite_sheet(
    images: Sequence[Image.Image],
    names: Sequence[str],
    settings: SpriteSheetSettings | None = None,
    *,
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> SpriteSheetResult:
    """Build a deterministic atlas from independently uploaded sprite images."""

    resolved_settings = settings or SpriteSheetSettings()
    _report(progress, "normalize_inputs", 10.0, "Normalizing sprite images...")
    frames, warnings = frames_from_images(images, names, resolved_settings, cancel=cancel)
    _report(progress, "pack_sprites", 55.0, "Packing sprites into atlas...")
    packed = pack_frames(frames, resolved_settings, cancel=cancel)
    _report(progress, "render_atlas", 85.0, "Rendering atlas image...")
    result = SpriteSheetResult(
        atlas=packed.atlas,
        frames=packed.frames,
        metadata=_metadata(packed.frames, packed.atlas.size, resolved_settings),
        warnings=warnings,
    )
    _report(progress, "complete", 95.0, "Sprite atlas is ready.")
    return result


def repack_sprite_sheet(
    image: Image.Image,
    extraction_settings: SheetExtractionSettings,
    settings: SpriteSheetSettings | None = None,
    *,
    name_prefix: str = "frame",
    progress: ProgressCallback | None = None,
    cancel: CancelCallback | None = None,
) -> SpriteSheetResult:
    """Extract frames from a source sheet and pack them into a new atlas."""

    from .extraction import extract_sprites_from_sheet

    resolved_settings = settings or SpriteSheetSettings()
    _report(progress, "extract_sprites", 15.0, "Extracting sprites from sheet...")
    extracted = extract_sprites_from_sheet(image, extraction_settings, name_prefix=name_prefix, cancel=cancel)
    _report(progress, "trim_sprites", 38.0, "Applying sprite bounds...")
    frames, warnings = frames_from_images(
        [frame.image for frame in extracted],
        [frame.name for frame in extracted],
        resolved_settings,
        cancel=cancel,
    )
    _report(progress, "pack_sprites", 60.0, "Packing sprites into atlas...")
    packed = pack_frames(frames, resolved_settings, cancel=cancel)
    _report(progress, "render_atlas", 85.0, "Rendering atlas image...")
    result = SpriteSheetResult(
        atlas=packed.atlas,
        frames=packed.frames,
        metadata=_metadata(packed.frames, packed.atlas.size, resolved_settings),
        warnings=warnings,
    )
    _report(progress, "complete", 95.0, "Sprite atlas is ready.")
    return result


def _metadata(
    frames: Sequence[AtlasFrame],
    atlas_size: tuple[int, int],
    settings: SpriteSheetSettings,
) -> dict[str, object]:
    return {
        "frames": {
            frame.name: {
                "frame": {"x": frame.x, "y": frame.y, "w": frame.width, "h": frame.height},
                "rotated": frame.rotated,
                "trimmed": frame.trimmed,
                "spriteSourceSize": {
                    "x": frame.source_rect[0],
                    "y": frame.source_rect[1],
                    "w": frame.source_rect[2],
                    "h": frame.source_rect[3],
                },
                "sourceSize": {"w": frame.source_size[0], "h": frame.source_size[1]},
            }
            for frame in frames
        },
        "meta": {
            "app": "PixelReForge",
            "version": "1.0",
            "image": "sprite-sheet.png",
            "format": "RGBA",
            "size": {"w": atlas_size[0], "h": atlas_size[1]},
            "scale": "1",
            "packingMode": settings.packing_mode,
        },
    }


def _report(progress: ProgressCallback | None, stage: str, percent: float, message: str) -> None:
    if progress is not None:
        progress(stage, percent, message)
