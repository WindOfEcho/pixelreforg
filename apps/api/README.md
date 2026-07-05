# PixelReForge API

FastAPI backend for PixelReForge.

The API accepts image uploads, creates processing jobs, reports progress, serves previews, and returns completed results. Image processing must be delegated to `packages/core`.

## Local Run

Create and activate a project-local virtual environment from the repository root:

```sh
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install Core and API as editable Python packages:

```sh
python -m pip install -e "packages/core[test]" -e "apps/api[test]"
```

Run the API from the repository root:

```sh
python -m uvicorn pixelreforge_api.main:app --reload
```

Or run it through Docker Compose from the repository root:

```sh
docker compose up --build api
```

Available endpoints:

- `GET /health`
- `POST /api/jobs?scale=4` with multipart field `file`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/download`

The first implementation stores files under `runtime/jobs/<job_id>/` and processes jobs with FastAPI `BackgroundTasks`. The default `scale=4` keeps the current real JPEG fixture usable while auto scale detection continues to be developed in Core.

Runtime files are resolved from the current working directory by default. Set `PIXELREFORGE_ROOT` when the API is launched from another directory.
