FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIXELREFORGE_ENV=production \
    PIXELREFORGE_LOG_FORMAT=json \
    PIXELREFORGE_LOG_LEVEL=INFO \
    PIXELREFORGE_ROOT=/app

WORKDIR /app

COPY packages/core/pyproject.toml /app/packages/core/pyproject.toml
COPY packages/core/README.md /app/packages/core/README.md
COPY packages/core/pixelreforge_core /app/packages/core/pixelreforge_core
COPY apps/api/pyproject.toml /app/apps/api/pyproject.toml
COPY apps/api/README.md /app/apps/api/README.md
COPY apps/api/pixelreforge_api /app/apps/api/pixelreforge_api

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir /app/packages/core /app/apps/api

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "pixelreforge_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
