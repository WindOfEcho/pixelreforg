FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY apps/api/requirements.txt /tmp/api-requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/api-requirements.txt

COPY apps/api /app/apps/api
COPY packages/core /app/packages/core

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "apps.api.pixelreforge_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
