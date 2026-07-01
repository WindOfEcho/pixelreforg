# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.8] - 2026-07-01

### Added

- Explicit `ai-pixel-v2` restoration algorithm for rough AI-generated pixel art.
- New Core `ai_pixel.py` module with resampled grid, dominant-color-cluster aggregation, and isolated-pixel neighborhood cleanup.
- Web algorithm selector option `AI pixel v2`; Smart auto does not select it yet.
- API accepts `algorithm=ai-pixel-v2` through the existing job creation contract.
- Regression tests for explicit Core/API `ai-pixel-v2` processing and for ensuring auto mode does not select it.

### Changed

- Fractional scale detection is enabled for explicit `ai-pixel-v2` jobs.
- Reconstruction metadata now records `artifact_cleanup` and `isolated_pixels_replaced` for `ai-pixel-v2`.

## [0.0.7] - 2026-07-01

### Added

- Different X/Y scale test fixtures (`test-Xx5-Yx6.png`, `test-Xx5-Yx6.3.png`) with regression tests.
- Enriched job creation log with `input_filename` and `content_type` fields.
- Enriched job completion metadata with `scale_x`, `scale_y`, `source_size`, `target_size`, `resize_method`.
- `scale_detection` metadata sub-dict (`integer` / `fractional`) in pipeline result metadata for auto mode.

### Changed

- `_best_fractional_scale` rewritten to enumerate target sizes instead of stepping through scales; prefers larger scales among viable candidates, improving different X/Y scale detection.
- `_select_scale_and_algorithm` introduced for auto mode — runs both integer and fractional detectors and selects the best algorithm/scale automatically.

## [0.0.6] - 2026-07-01

### Added

- `resampled-grid-v2` fractional restoration algorithm with resampled grid aggregation for float scale factors.
- Float manual scale mode — user can enter non-integer scale factors (e.g. `1.5`, `2.25`, `3.59375`) for non-integer pixel-art upscales.
- Original size override now applies the requested target size instead of being stored as a reserved setting.
- `noisy-pixel-v1` algorithm extended to support fractional grid restoration using dominant-color-cluster aggregation for JPEG/AI artifacts.
- API and Web fractional settings: slider (`step=0.25`, range `1.0`–`16.0`) combined with numeric input for precise float scale entry.
- `fractional_scale_step` query parameter in API job creation endpoint.
- Regression coverage for existing fractional scale fixtures (`test-x3.6.png`, `test-x6.3.png`).

### Changed

- `pipeline.process_image` resolves explicit `resampled-grid-v2`; `noisy-pixel-v1` now switches to fractional grid aggregation when scale is non-integer.
- `scale_detection.py` supports original-size override and bounded fractional scale candidates for `resampled-grid-v2` and `noisy-pixel-v1`.
- `resize.py` — new `downscale_by_resampled_grid` function implementing resampled grid aggregation per output cell.
- `original_width`/`original_height` override now always applied when provided, regardless of scale type.
- Web `SettingsPanel.svelte` — `Resampled v2` is selectable; manual scale has both slider and numeric input; original size remains in Advanced.
- `api.ts` — passes `fractional_scale_step` to API; `types.ts` — added `fractionalScaleStep` field to job creation payload.
- `help.ts` — added tooltip text for fractional scale and fractional grid settings.

## [0.0.5] - 2026-07-01

### Added

- Production API logging with structured JSON output, request IDs via `ContextVar`, and `log_successful_requests` setting controlling whether successful requests are logged.
- Optional Sentry integration for the backend (`sentry-sdk[fastapi]`), configurable via `PIXELREFORGE_SENTRY_DSN` and `PIXELREFORGE_SENTRY_TRACES_SAMPLE_RATE` environment variables.
- New configuration module `settings.py` — environment-based `ApiSettings` dataclass with env, debug, log format/level, and Sentry DSN fields.
- New `logging_config.py` module — JSON and plain-text formatters with `RequestContextFilter` for automatic request ID injection.
- New `logging_context.py` module — `ContextVar`-based request ID propagation from API middleware to background job processing.
- New `sentry_config.py` module — Sentry SDK initialisation with FastAPI and logging integrations.
- Atomic metadata writes via temp-file rename (`write_metadata` writes to `.json.tmp` then replaces) to prevent partial/corrupt reads.
- Structured logging events throughout the job lifecycle: `job_created`, `job_processing_started`, `job_processing_completed`, `job_cancelled`, `job_processing_failed`.
- Request ID propagation from HTTP middleware to background `process_job` via `set_request_id`/`reset_request_id`.

### Changed

- API tests migrated from `unittest.TestCase` to `pytest` fixtures (`client` fixture, `monkeypatch`, `capsys`, `caplog`).
- Expanded test coverage: request ID header preservation, JSON logging output, environment-based settings read, Sentry enable/disable logic, processing failure logging with job ID, and empty metadata file regression test.
- Dockerfile (`infra/docker/api.Dockerfile`) sets production defaults: `PIXELREFORGE_ENV=production`, `PIXELREFORGE_LOG_FORMAT=json`, `PIXELREFORGE_LOG_LEVEL=INFO`.
- `sentry-sdk[fastapi]>=2.0` added to `apps/api/requirements.txt`.

### Fixed

- `read_metadata` now catches `Pydantic ValidationError` from empty or partially-written metadata files and returns `None` (resulting in HTTP 404) instead of crashing with an unhandled exception. Logs `job_metadata_unreadable` event on failure. (Fixes **PYTHON-FASTAPI-3**)

## [0.0.4] - 2026-06-30

### Added

- New `noisy-pixel-v1` restoration algorithm with dominant-color cluster resampling for JPEG and AI artifacts.
- New `preflight.py` module — automatic image analysis that scores noise, JPEG artifacts, and AI artifacts to recommend the best algorithm.
- New `palette.py` module — near-duplicate color merging with presets (off, light, medium, strong) and custom merge distance / target colors.
- Algorithm selector in Settings panel (Smart auto, Fast integer, Noisy pixel) with disable states for unimplemented algorithms.
- Palette cleanup control with inline help, custom mode sliders for merge distance and target colors.
- Original size override input fields (width/height) in advanced settings.
- Notification auto-dismiss with animated countdown progress bar and proper timer cancellation via `SvelteMap`.
- Help tooltips for all new settings (algorithm, palette cleanup, color bucket, merge distance, target colors).
- API support for `algorithm`, `palette_cleanup`, `palette_merge_distance`, `palette_target_colors`, `noisy_color_bucket_size`, `original_width`, `original_height` query parameters.
- Metadata fields in job responses: `algorithm_requested`, `algorithm_used`, `algorithm_version`, `original_size_override`, `palette_cleanup`, `analysis` (with preflight scores), `palette` (color counts, top colors), `reconstruction` (resize method, bucket size).
- Test fixtures `test-ai-1.png`, `test-ai-2.png` and new test modules `test_core_palette.py`, `test_core_preflight.py`, `test_ai_fixtures_pytest.py`.
- API integration tests for auto algorithm fallback and explicit noisy-pixel algorithm.

### Changed

- Core `pipeline.process_image` now resolves algorithm based on preflight analysis when set to `auto`; orchestrates palette cleanup and returns rich metadata.
- Settings panel now shows scale mode and advanced options only when a concrete algorithm is selected.
- Download button height increased from `min-h-13` to `min-h-14` with wider horizontal padding.
- Button tracking increased from `0.08em` to `0.12em` for consistency.
- Image preview containers use `max-w-full`/`min-w-0` to prevent overflow in constrained layouts.
- Result metadata panel now shows algorithm (requested → used), recommended algorithm, and palette cleanup info.
- Job polling timeout increased from ~30 seconds to 120 seconds with explicit deadline constant.

### Fixed

- Radio input `accent-color` now uses theme color for visibility.
- Notification dismissal now properly clears its auto-dismiss timer.
- Notification timers tracked in a `SvelteMap` to avoid stale closure references on re-render.

## [0.0.3] - 2026-06-30

### Added

- Landing page at `/` and dedicated processing route at `/process` with separate SEO metadata.
- Tailwind CSS and shadcn-svelte compatible UI primitives for buttons, sliders, and tooltips while preserving the PixelReForge mascot theme.
- Interactive result comparison with side-by-side and slider modes, synchronized preview pan/scroll, and matched source/result display size.
- Compact metadata help tooltips for processing result details.

### Changed

- Refactored the large global stylesheet into semantic theme tokens plus Tailwind utility-based component styling.
- Unified small UI/help text typography across algorithm settings and result metadata.
- Renamed result metadata from `Target size` to `Result size` and grouped it with `Source size`.
- Non-error notifications now auto-dismiss only while the PixelReForge tab is visible; errors remain until dismissed.

### Fixed

- File picker no longer allows broad unsupported `image/*` selection; UI now pre-validates PNG, JPEG, GIF, and WebP.
- Debug and production UI errors now show different levels of detail without leaking raw technical errors in production.
- Help icon alignment inside the circular `?` button.

## [0.0.2] - 2026-06-29

### Added

- Warm pastel fox visual theme based on the PixelReForge mascot palette.
- Reusable Svelte restoration UI components for hero, upload, settings, result, help, and notifications.
- Themed in-app notifications for warnings, errors, and successful restoration messages.
- Regression fixtures and tests for integer-scale PNG/JPEG restoration.
- Docker Compose launch flow and Dockerfiles for API and Web services.

### Changed

- Split the large restoration route into smaller components and moved shared styling into a global theme stylesheet.
- Web API client now supports `PUBLIC_API_BASE_URL` with a localhost fallback.

### Fixed

- PNG uploads no longer show the auto scale JPEG/fractional-scale browser warning.
- JPEG uploads now show a themed warning inside the app instead of a blocking browser dialog.
- Auto scale detection no longer divides by zero when `min_scale` is set to `1`.

## [0.0.1] - 2026-06-28

### Added

- MVP Prototype
- SvelteKit web interface for uploading pixel art images, selecting manual scale, previewing input and result, and downloading restored PNG output.
- FastAPI backend with health check, job creation, job status, background processing, runtime file storage, and result download endpoints.
- local Python image-processing Core with image IO, scale estimation, resize restoration, processing models, and pipeline entry points.
- smoke tests for project structure, Core processing, and API upload/status/download flow.
