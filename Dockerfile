# Multi-stage build. Runtime stage is slim, runs as a non-root user, and
# includes poppler-utils + tesseract-ocr + spa language pack: the ingestion
# pipeline needs them, and forgetting them causes confusing failures later.

FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

FROM build AS build-dev
RUN pip install .[dev]

FROM python:3.12-slim AS runtime-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-spa \
        curl \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 app
WORKDIR /app

FROM runtime-base AS runtime
COPY --from=build /opt/venv /opt/venv
COPY . .
# Bake static files into the image (whitenoise serves them; the app writes
# nothing to disk at runtime). Dummy env vars satisfy settings import only.
RUN SECRET_KEY=build-only DATABASE_URL=postgres://x:x@x/x DJANGO_SETTINGS_MODULE=config.settings.prod \
    python manage.py collectstatic --noinput \
    && chown -R app:app /app/staticfiles
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]

FROM runtime-base AS dev
COPY --from=build-dev /opt/venv /opt/venv
# Source is bind-mounted in development; copy anyway so the image also works standalone.
COPY . .
RUN chown -R app:app /app
USER app
EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
