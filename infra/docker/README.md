# PixelReForge Docker

Docker infrastructure for local development and hosted deployments.

Services:

- `api`: FastAPI HTTP process. Accepts uploads and creates queued jobs.
- `worker`: Python worker process. Claims queued jobs from SQLite and runs Core processing.
- `web`: SvelteKit frontend.
- `caddy`: production reverse proxy.

The `api` and `worker` services share the `pixelreforge-runtime` volume. It contains upload/result files under `runtime/jobs/` and the default SQLite job store at `runtime/pixelreforge.sqlite3`.
