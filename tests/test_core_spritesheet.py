from PIL import Image
import pytest

from pixelreforge_core import AtlasSizeError, ProcessingCancelled, SheetExtractionSettings, SpriteSheetError, SpriteSheetSettings, create_sprite_sheet, repack_sprite_sheet


def solid_sprite(size: tuple[int, int], color: tuple[int, int, int, int]) -> Image.Image:
    return Image.new("RGBA", size, color)


def test_grid_packing_preserves_pixels_and_metadata() -> None:
    result = create_sprite_sheet(
        [solid_sprite((2, 2), (255, 0, 0, 255)), solid_sprite((1, 3), (0, 0, 255, 255))],
        ["hero.png", "gem.png"],
        SpriteSheetSettings(packing_mode="grid", trim_transparent=False, padding=1, border_padding=2, grid_columns=2),
    )

    assert result.atlas.size == (9, 7)
    assert result.atlas.getpixel((2, 2)) == (255, 0, 0, 255)
    assert result.atlas.getpixel((5, 2)) == (0, 0, 255, 255)
    assert result.metadata["frames"] == {
        "hero": {
            "frame": {"x": 2, "y": 2, "w": 2, "h": 2},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": 2, "h": 2},
            "sourceSize": {"w": 2, "h": 2},
        },
        "gem": {
            "frame": {"x": 5, "y": 2, "w": 1, "h": 3},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": 1, "h": 3},
            "sourceSize": {"w": 1, "h": 3},
        },
    }


def test_trimming_records_original_source_bounds() -> None:
    source = Image.new("RGBA", (6, 5), (0, 0, 0, 0))
    source.paste((255, 40, 10, 255), (1, 2, 4, 4))

    result = create_sprite_sheet(
        [source],
        ["trimmed.png"],
        SpriteSheetSettings(packing_mode="grid", padding=0, grid_columns=1),
    )

    frame = result.metadata["frames"]["trimmed"]
    assert result.atlas.size == (3, 2)
    assert frame["trimmed"] is True
    assert frame["spriteSourceSize"] == {"x": 1, "y": 2, "w": 3, "h": 2}
    assert frame["sourceSize"] == {"w": 6, "h": 5}


def test_compact_packing_applies_border_padding_and_extrusion() -> None:
    result = create_sprite_sheet(
        [solid_sprite((2, 2), (255, 0, 0, 255)), solid_sprite((3, 1), (0, 0, 255, 255))],
        ["red.png", "blue.png"],
        SpriteSheetSettings(
            packing_mode="compact",
            trim_transparent=False,
            padding=2,
            border_padding=1,
            extrude=1,
            max_width=16,
            max_height=16,
        ),
    )

    frames = result.metadata["frames"]
    red = frames["red"]["frame"]
    blue = frames["blue"]["frame"]
    assert red["x"] >= 2 and red["y"] >= 2
    assert blue["x"] >= 2 and blue["y"] >= 2
    assert not (
        red["x"] < blue["x"] + blue["w"]
        and red["x"] + red["w"] > blue["x"]
        and red["y"] < blue["y"] + blue["h"]
        and red["y"] + red["h"] > blue["y"]
    )


def test_repack_sheet_auto_extracts_separate_transparent_regions() -> None:
    sheet = Image.new("RGBA", (7, 4), (0, 0, 0, 0))
    sheet.paste((255, 0, 0, 255), (0, 1, 2, 3))
    sheet.paste((0, 0, 255, 255), (5, 0, 6, 3))

    result = repack_sprite_sheet(
        sheet,
        SheetExtractionSettings(mode="auto"),
        SpriteSheetSettings(packing_mode="grid", trim_transparent=False, padding=0, grid_columns=2),
        name_prefix="atlas",
    )

    assert result.atlas.size == (4, 3)
    assert tuple(result.metadata["frames"]) == ("atlas_0001", "atlas_0002")
    assert result.atlas.getpixel((0, 0)) == (255, 0, 0, 255)
    assert result.atlas.getpixel((2, 0)) == (0, 0, 255, 255)


def test_repack_sheet_grid_skips_empty_cells() -> None:
    sheet = Image.new("RGBA", (6, 2), (0, 0, 0, 0))
    sheet.paste((255, 0, 0, 255), (0, 0, 2, 2))
    sheet.paste((0, 255, 0, 255), (4, 0, 6, 2))

    result = repack_sprite_sheet(
        sheet,
        SheetExtractionSettings(mode="grid", cell_width=2, cell_height=2, columns=3, rows=1),
        SpriteSheetSettings(packing_mode="grid", trim_transparent=False, padding=0, grid_columns=2),
    )

    assert tuple(result.metadata["frames"]) == ("frame_0001", "frame_0002")
    assert result.atlas.size == (4, 2)


def test_power_of_two_output_is_normalized_after_grid_packing() -> None:
    result = create_sprite_sheet(
        [solid_sprite((3, 3), (255, 255, 255, 255))],
        ["tile.png"],
        SpriteSheetSettings(packing_mode="grid", power_of_two=True),
    )

    assert result.atlas.size == (4, 4)


def test_fixed_atlas_rejects_sprites_that_do_not_fit() -> None:
    with pytest.raises(AtlasSizeError, match="fit"):
        create_sprite_sheet(
            [solid_sprite((5, 5), (255, 255, 255, 255))],
            ["large.png"],
            SpriteSheetSettings(packing_mode="compact", trim_transparent=False, atlas_width=4, atlas_height=4, max_width=4, max_height=4),
        )


def test_compact_packing_can_rotate_frames_to_fit_fixed_atlas() -> None:
    result = create_sprite_sheet(
        [solid_sprite((3, 2), (255, 0, 0, 255)), solid_sprite((3, 2), (0, 255, 0, 255))],
        ["first.png", "second.png"],
        SpriteSheetSettings(
            packing_mode="compact",
            trim_transparent=False,
            padding=0,
            max_width=4,
            max_height=3,
            atlas_width=4,
            atlas_height=3,
            allow_rotation=True,
        ),
    )

    frames = result.metadata["frames"]
    assert result.atlas.size == (4, 3)
    assert frames["first"]["rotated"] is True
    assert frames["second"]["rotated"] is True


def test_compact_padding_does_not_require_trailing_space_in_fixed_atlas() -> None:
    result = create_sprite_sheet(
        [solid_sprite((2, 2), (255, 255, 255, 255))],
        ["single.png"],
        SpriteSheetSettings(
            packing_mode="compact",
            trim_transparent=False,
            padding=1,
            max_width=2,
            max_height=2,
            atlas_width=2,
            atlas_height=2,
        ),
    )

    assert result.atlas.size == (2, 2)


def test_atlas_pixel_limit_is_enforced() -> None:
    with pytest.raises(AtlasSizeError, match="pixel count"):
        create_sprite_sheet(
            [solid_sprite((5, 5), (255, 255, 255, 255))],
            ["large.png"],
            SpriteSheetSettings(
                packing_mode="grid",
                max_width=5,
                max_height=5,
                max_pixels=16,
                atlas_width=5,
                atlas_height=5,
            ),
        )


def test_manual_sheet_grid_rejects_more_frames_than_configured_limit() -> None:
    sheet = solid_sprite((3, 2), (255, 255, 255, 255))

    with pytest.raises(SpriteSheetError, match="maximum frame count"):
        repack_sprite_sheet(
            sheet,
            SheetExtractionSettings(mode="grid", cell_width=1, cell_height=1, max_frames=4),
            SpriteSheetSettings(packing_mode="grid"),
        )


def test_auto_sheet_extraction_checks_cancellation_within_large_region() -> None:
    sheet = solid_sprite((5000, 1), (255, 255, 255, 255))
    calls = 0

    def cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2

    with pytest.raises(ProcessingCancelled):
        repack_sprite_sheet(
            sheet,
            SheetExtractionSettings(mode="auto"),
            SpriteSheetSettings(packing_mode="grid"),
            cancel=cancel,
        )


def test_compact_auto_packing_uses_available_atlas_bounds() -> None:
    sizes = [(4, 8), (12, 2), (10, 3), (16, 3)]
    result = create_sprite_sheet(
        [solid_sprite(size, (index * 30, 255 - index * 30, 100, 255)) for index, size in enumerate(sizes)],
        [f"sprite-{index}.png" for index in range(len(sizes))],
        SpriteSheetSettings(packing_mode="compact", trim_transparent=False, padding=1, max_width=16, max_height=16),
    )

    assert result.atlas.width <= 16
    assert result.atlas.height <= 16
