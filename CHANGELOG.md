# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
