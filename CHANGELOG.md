# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/2.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2026-06-28

### Added

- MVP Prototype
- SvelteKit web interface for uploading pixel art images, selecting manual scale, previewing input and result, and downloading restored PNG output.
- Themed in-app notifications for warnings, errors, and successful restoration messages.
- FastAPI backend with health check, job creation, job status, background processing, runtime file storage, and result download endpoints.
- local Python image-processing Core with image IO, scale estimation, resize restoration, processing models, and pipeline entry points.
- smoke tests for project structure, Core processing, API upload/status/download flow, and integer-scale fixture restoration.
- Docker Compose launch flow and Dockerfiles for API and Web services.

### Fixed

- PNG uploads no longer show the auto scale JPEG/fractional-scale browser warning.
- JPEG uploads now show a themed warning inside the app instead of a blocking browser dialog.
- Auto scale detection no longer divides by zero when `min_scale` is set to `1`.
