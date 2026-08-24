from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image
import pytest

from pixelreforge_core import RestoreSettings, process_image


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
OUTPUT = ROOT / "tests" / "output" / "algorithm-regression-stats.json"

pytestmark = pytest.mark.regression


@dataclass(frozen=True)
class RegressionCase:
    fixture_name: str
    settings: RestoreSettings
    expected_size: tuple[int, int] | None = None
    reference_name: str | None = None
    thumbnail_max_size: int | None = None
    case_name: str | None = None


BASE_REGRESSION_CASES = (
    RegressionCase(
        "zephyr-small-test-x2.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (16, 16),
        "zephyr-small-original-16x16px.png",
    ),
    RegressionCase(
        "zephyr-small-test-x3.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (16, 16),
        "zephyr-small-original-16x16px.png",
    ),
    RegressionCase(
        "zephyr-small-test-x4.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (16, 16),
        "zephyr-small-original-16x16px.png",
    ),
    RegressionCase(
        "zephyr-small-test-jpegs-x1-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (16, 16),
    ),
    RegressionCase(
        "zephyr-small-test-jpegs-x3-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (16, 16),
        "zephyr-small-original-16x16px.png",
    ),
    RegressionCase(
        "zephyr-small-test-jpegs-x4-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (16, 16),
        "zephyr-small-original-16x16px.png",
    ),
    RegressionCase(
        "test-x3.6.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        (32, 32),
        "test-original-32x32px.png",
    ),
    RegressionCase(
        "test-x6.3.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        (32, 32),
        "test-original-32x32px.png",
    ),
    RegressionCase(
        "test-jpegs-x3.6-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        (32, 32),
        "test-original-32x32px.png",
    ),
    RegressionCase(
        "test-jpegs-x6.3-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        (32, 32),
        "test-original-32x32px.png",
    ),
    RegressionCase(
        "test-bicubic_resize-x4.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        (32, 32),
        "test-original-32x32px.png",
    ),
    RegressionCase(
        "test-bilinear_resize-x4.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        (32, 32),
        "test-original-32x32px.png",
    ),
    RegressionCase(
        "zephyr-silly-x4-crop-left1-top2.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
    ),
    RegressionCase(
        "zephyr-silly-x4-crop-right2-bottom1.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
    ),
    RegressionCase(
        "zephyr-fullbody-test-x4.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (40, 92),
        "zephyr-fullbody-original-40x92.png",
    ),
    RegressionCase(
        "zephyr-fullbody-test-x6.3.png",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (40, 92),
        "zephyr-fullbody-original-40x92.png",
    ),
    RegressionCase(
        "zephyr-fullbody-test-jpegs-x1-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (40, 92),
    ),
    RegressionCase(
        "zephyr-fullbody-test-jpegs-x4-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (40, 92),
        "zephyr-fullbody-original-40x92.png",
    ),
    RegressionCase(
        "zephyr-fullbody-test-jpegs-x6.3-90.jpg",
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=8),
        (40, 92),
        "zephyr-fullbody-original-40x92.png",
    ),
)

AI_REGRESSION_CASES = tuple(
    RegressionCase(
        path.name,
        RestoreSettings(algorithm="auto", scale_mode="auto", min_scale=1, max_scale=16),
        thumbnail_max_size=256,
        case_name=f"{path.name}:auto",
    )
    for path in sorted(FIXTURES.glob("test-ai-*.png"))
)

AI_GRID_HYPOTHESIS_CASES = tuple(
    RegressionCase(
        path.name,
        RestoreSettings(
            algorithm="ai-grid-hypothesis-v1",
            scale_mode="auto",
            min_scale=2,
            max_scale=16,
        ),
        thumbnail_max_size=256,
        case_name=f"{path.name}:ai-grid-hypothesis-v1",
    )
    for path in sorted(FIXTURES.glob("test-ai-*.png"))
)

REGRESSION_CASES = (
    BASE_REGRESSION_CASES + AI_REGRESSION_CASES + AI_GRID_HYPOTHESIS_CASES
)


def test_algorithm_regression_matrix_records_statistics() -> None:
    records = [_run_case(case) for case in REGRESSION_CASES]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")

    assert all(
        record["target_size"][0] >= 1 and record["target_size"][1] >= 1
        for record in records
    )
    assert all(record["algorithm_used"] for record in records)
    assert all(record["duration_ms"] >= 0.0 for record in records)


def _run_case(case: RegressionCase) -> dict[str, object]:
    image = Image.open(FIXTURES / case.fixture_name)
    original_source_size = image.size
    if case.thumbnail_max_size is not None:
        image.thumbnail((case.thumbnail_max_size, case.thumbnail_max_size))

    started = perf_counter()
    result = process_image(image, case.settings)
    duration_ms = (perf_counter() - started) * 1000.0

    record: dict[str, object] = {
        "case": case.case_name or case.fixture_name,
        "fixture": case.fixture_name,
        "original_source_size": list(original_source_size),
        "source_size": list(result.source_size),
        "target_size": list(result.target_size),
        "expected_size": list(case.expected_size) if case.expected_size else None,
        "algorithm_requested": result.algorithm_requested,
        "algorithm_used": result.algorithm_used,
        "scale_x": result.scale.scale_x,
        "scale_y": result.scale.scale_y,
        "confidence_x": result.scale.confidence_x,
        "confidence_y": result.scale.confidence_y,
        "confidence": result.scale.confidence,
        "scale_method": result.scale.method,
        "warnings": list(result.warnings),
        "resize_method": (result.reconstruction or {}).get("resize_method"),
        "duration_ms": round(duration_ms, 3),
    }
    if result.scale.details is not None:
        record["scale_details"] = result.scale.details

    if result.analysis is not None:
        record["recommended_algorithm"] = result.analysis.get("recommended_algorithm")
        record["recommendation_confidence"] = result.analysis.get(
            "recommendation_confidence"
        )
        record["recommendation_reason"] = result.analysis.get("recommendation_reason")
        record["noise_score"] = result.analysis.get("noise_score")
        record["ai_artifact_score"] = result.analysis.get("ai_artifact_score")
        record["grid_confidence"] = result.analysis.get("grid_confidence")
        record["jpeg_artifact_score"] = result.analysis.get("jpeg_artifact_score")
        record["ai_pixel_v2_score"] = result.analysis.get("ai_pixel_v2_score")
        record["unique_color_count"] = result.analysis.get("unique_color_count")
        record["estimated_palette_size"] = result.analysis.get("estimated_palette_size")
        record["near_duplicate_color_ratio"] = result.analysis.get(
            "near_duplicate_color_ratio"
        )

    if result.palette is not None:
        record["palette_cleanup_applied"] = result.palette.get("cleanup_applied")
        record["palette_color_count_before"] = result.palette.get("color_count_before")
        record["palette_color_count_after"] = result.palette.get("color_count_after")

    if result.reconstruction is not None:
        record["artifact_cleanup"] = result.reconstruction.get("artifact_cleanup")
        record["isolated_pixels_replaced"] = result.reconstruction.get(
            "isolated_pixels_replaced"
        )

    if case.reference_name is not None:
        reference = Image.open(FIXTURES / case.reference_name).convert("RGBA")
        restored = result.image.convert("RGBA")
        if restored.size == reference.size:
            record["mae"] = round(
                _mean_absolute_error(np.asarray(restored), np.asarray(reference)), 3
            )

    return record


def _mean_absolute_error(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.mean(np.abs(actual.astype(np.int16) - expected.astype(np.int16))))
