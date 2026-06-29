# PixelReForge API

FastAPI backend for PixelReForge.

The API accepts image uploads, creates processing jobs, reports progress, serves previews, and returns completed results. Image processing must be delegated to `packages/core`.

## First local prototype

Create and activate a project-local virtual environment from `pixelreforge-src/`:

```sh
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install backend dependencies from the repository root:

```sh
python -m pip install -r apps/api/requirements.txt
```

Run the API from the repository root:

```sh
python -m uvicorn apps.api.pixelreforge_api.main:app --reload
```

Available endpoints:

- `GET /health`
- `POST /api/jobs?scale=4` with multipart field `file`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/download`

The first implementation stores files under `runtime/jobs/<job_id>/` and processes jobs with FastAPI `BackgroundTasks`. The default `scale=4` keeps the current real JPEG fixture usable while auto scale detection continues to be developed in Core.
