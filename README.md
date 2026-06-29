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
packages/
  core/     Python image-processing core
infra/
  docker/   Docker assets and deployment helpers
docs/       Product documentation
```

## Testing

Run the current smoke checks from this directory:

```sh
python -m unittest discover -s tests
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

## License

Source code of PixelReForge is licensed under the AGPL-3.0-or-later. See `LICENSE`.
Unless otherwise specified, all artwork, sprites, textures, icons, illustrations and other visual assets of PixelReForge © 2026 by WindOfEchos are licensed under Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0). To view a copy of this license, visit https://creativecommons.org/licenses/by-nc-nd/4.0/
