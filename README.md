# PixelReForge

Restore pixel art to its original form.

PixelReForge is a web-first application for restoring pixel art images that were enlarged, blurred, compressed, or otherwise degraded. The project is built around a clean separation between image-processing core, HTTP API, and user interfaces.

The idea is based on the original pixeldetector project by Astropulse: https://github.com/Astropulse/pixeldetector

## Stack

- Frontend: SvelteKit, TypeScript, Tailwind CSS, shadcn-svelte.
- Backend: FastAPI, Python 3.13+.
- Core: Python, NumPy, Pillow, OpenCV, SciPy.
- Infrastructure: Docker and Docker Compose.
- Future desktop: Tauri.

## Structure

```text
apps/
  web/      SvelteKit frontend
  api/      FastAPI backend
    pyproject.toml
packages/
  core/     Python image-processing core
    pyproject.toml
infra/
  docker/   Docker assets and deployment helpers
```

## Python Setup

Create and activate a project-local virtual environment from this directory, then install the Python packages in editable mode:

```sh
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e "packages/core[test]" -e "apps/api[test]"
```

## Testing

Run the current smoke checks from this directory:

```sh
python -m pytest
```

## Docker Run

Run the API and Web UI from this directory:

```sh
docker compose up --build
```

Then open `http://localhost:5173`. The API is exposed at `http://localhost:8000`.

Stop the stack with:

```sh
docker compose down
```

## Deploy

Deployment uses `compose.prod.yml` with Caddy as HTTPS reverse proxy. Production images are pulled from GHCR and selected by an explicit release tag.

Create `.env` from `.env.example` and set the public domain:

```env
PIXELREFORGE_DOMAIN=example.com
PIXELREFORGE_GHCR_OWNER=windofechos
PIXELREFORGE_IMAGE_TAG=v0.1.0
PIXELREFORGE_PUBLIC_ORIGIN=https://example.com
PIXELREFORGE_PUBLIC_API_BASE_URL=https://example.com
PIXELREFORGE_CORS_ORIGINS=https://example.com
PIXELREFORGE_LOG_LEVEL=INFO
PIXELREFORGE_SESSION_SECRET=change-me-to-a-random-secret
PIXELREFORGE_SENTRY_DSN=
PIXELREFORGE_SENTRY_TRACES_SAMPLE_RATE=0.0
```

`PIXELREFORGE_SESSION_SECRET` is required in production. It signs anonymous session cookies that limit job metadata and result downloads to the browser that created the job.

Run from this directory after publishing the selected image tag:

```sh
PIXELREFORGE_IMAGE_TAG=v0.1.0 docker compose --env-file .env -f compose.prod.yml pull
PIXELREFORGE_IMAGE_TAG=v0.1.0 docker compose --env-file .env -f compose.prod.yml up -d
PIXELREFORGE_IMAGE_TAG=v0.1.0 docker compose --env-file .env -f compose.prod.yml ps
```

Caddy publishes only `80` and `443`, routes `/api/*` and `/health` to FastAPI, and routes the rest to the SvelteKit web container. For HTTPS, the domain must resolve to the VPS and ports `80/443` must be reachable for Let's Encrypt certificates.

## License

Source code of PixelReForge is licensed under the AGPL-3.0-or-later. See `LICENSE`.
Unless otherwise specified, all artwork, sprites, textures, icons, illustrations and other visual assets of PixelReForge © 2026 by WindOfEchos are licensed under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0). To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-nd/4.0/
