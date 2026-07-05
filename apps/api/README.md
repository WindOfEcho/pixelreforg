# PixelReForge API

FastAPI backend for PixelReForge.

The API accepts image uploads, creates processing jobs, reports progress, serves previews, and returns completed results. Image processing is delegated to `packages/core` through a separate worker process.

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

Run the worker in a second shell:

```sh
python -m pixelreforge_api.worker
```

Or run it through Docker Compose from the repository root:

```sh
docker compose up --build api worker
```

Available endpoints:

- `GET /health`
- `POST /api/jobs?scale=4` with multipart field `file`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/download`

The API stores uploads and results under `runtime/jobs/<job_id>/`. Job state is stored in a SQLite-backed `JobStore` at `runtime/pixelreforge.sqlite3` by default. `POST /api/jobs` only creates a `queued` job; the worker claims queued jobs and executes processing.

Job status, listing, cancellation, and download endpoints are limited by a signed anonymous session cookie. The public job response does not expose internal storage paths or the session owner id. Production deployments must set `PIXELREFORGE_SESSION_SECRET`.

Runtime files are resolved from the current working directory by default. Set `PIXELREFORGE_ROOT` when the API is launched from another directory.

Useful job settings:

- `PIXELREFORGE_DATABASE_URL`, default `sqlite:///<PIXELREFORGE_ROOT>/runtime/pixelreforge.sqlite3`
- `PIXELREFORGE_JOB_MAX_ATTEMPTS`, default `3`
- `PIXELREFORGE_JOB_TIMEOUT_SECONDS`, default `1800`
- `PIXELREFORGE_JOB_TTL_SECONDS`, default `86400`
- `PIXELREFORGE_WORKER_CONCURRENCY`, default `1`
- `PIXELREFORGE_SESSION_SECRET`, required when `PIXELREFORGE_ENV=production`
- `PIXELREFORGE_SESSION_COOKIE_NAME`, default `pixelreforge_session`
- `PIXELREFORGE_SESSION_MAX_AGE_SECONDS`, default `2592000`
