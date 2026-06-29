# PixelReForge Web

SvelteKit frontend for PixelReForge.

Current stack: SvelteKit, TypeScript, scoped CSS.

This app talks to the FastAPI backend through documented HTTP endpoints only.

## MVP flow

The first Web UI provides a single-page restoration flow:

- choose or drag-and-drop an image;
- select manual scale from 2x to 16x;
- submit the image to `POST /api/jobs`;
- poll job metadata;
- preview and download the restored PNG;
- show result metadata such as source size, target size, scale, and confidence.

Future algorithm settings are visible as disabled controls so the layout already has space for auto detection, downscale methods, JPEG tolerance, grid offset search, and palette cleanup.

## Local run

Start the API from the repository root:

```sh
python -m uvicorn apps.api.pixelreforge_api.main:app --reload
```

Start the Web UI from `apps/web`:

```sh
npm install
npm run dev
```

The MVP uses `PUBLIC_API_BASE_URL` and falls back to `http://localhost:8000`.

Run the Web UI through Docker Compose from the repository root:

```sh
docker compose up --build web
```

## Checks

Run from `apps/web`:

```sh
npm run check
npm run build
```
