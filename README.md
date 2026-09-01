# opos

Web platform for people preparing Spanish public-sector exams (*oposiciones*).
Users search, browse and download study documents: official documents (BOE,
convocatorias, bases), editorial documents curated by staff, and user-contributed
notes.

Interface and content are in Spanish (es-ES); code, comments and commit messages
are in English. See [CLAUDE.md](CLAUDE.md) for the project conventions and the
two constraints — server-rendered HTML and a stateless app — that every change
has to respect.

## Status

Working demo covering prompts 1–7 of the build plan (plus the consent layer of
prompt 8):

- **Foundations** — settings split (`config/settings/{base,dev,prod}.py`),
  Docker Compose for dev and prod, multi-stage Dockerfile (poppler + tesseract
  + spa included), `/healthz`, GitHub Actions CI, Makefile, `deploy.sh`.
- **Editorial core** — `Oposicion`/`Convocatoria`/`Tema` with immutable
  published slugs, Spanish admin, `seed_oposiciones` (17 real state-level
  oposiciones).
- **Discoverability** — fixed URL taxonomy, answer-first pages, facts `<dl>` +
  JSON-LD from one source, JobPosting on open convocatorias, environment-aware
  robots.txt welcoming AI crawlers, `/llms.txt`, `.md` content negotiation on
  every public URL, sitemap index, canonical/OG/meta everywhere, reserved
  fixed-height ad slots.
- **Documents** — three independent axes (`source_type` / `visibility` /
  `moderation_status`), content-addressed S3 storage, Celery pipeline
  (ClamAV → pdftotext/docx → Tesseract OCR fallback on a low-priority queue →
  WebP thumbnail → index), thin-content noindex guard, duplicate
  canonicalisation, 410 for takedowns.
- **Search** — `SearchBackend` protocol with a Postgres FTS implementation:
  `es_unaccent` config (accent-insensitive), weighted generated column,
  trigram indexes, faceted `/buscar/`, public JSON API at `/api/buscar/` with
  an OpenAPI schema at `/api/schema/`.
- **Accounts** — allauth (email + Google), Argon2, UUID `external_id`, role
  groups from the §7 matrix, `can_access()` used by views and the presigned
  URL generator alike.
- **Contributions** — upload form with mandatory licence declaration,
  sha256 dedupe, moderation queue with audit log, reports, aviso legal and
  takedown pages.
- **Consent** — overlay banner (never a gate), equal accept/reject, no ad
  scripts before consent, server-side consent audit log.
- **Posts (*apuntes*)** — study notes written on the site in markdown at
  `/apuntes/`: rendered and sanitised on save (allowlist, `nofollow ugc` on
  outbound links) so the formatted text ships in the first HTML response;
  a working copy per post that makes autosave safe (autosaving never changes
  what readers see), drafts, publish/unpublish, immutable slug from first
  publication, sitemap + Article JSON-LD + `.md` output.

Local object storage is MinIO for zero-setup dev; production compose runs
Garage. Swap is a config change — the app only sees `AWS_S3_ENDPOINT_URL`.

## Stack

Django 5, PostgreSQL 16, Redis, Celery, Garage (S3-compatible object storage),
Caddy, Docker Compose. Deployed to a single self-hosted server behind a
Cloudflare Tunnel.

Planning documents live in [files/](files/):

- `oposiciones-infrastructure-plan.md` — architecture, data model, ingestion,
  search, legal and operational plan.
- `development-prompts.md` — the ordered build plan.

## Requirements

- Docker and Docker Compose
- Python 3.12+ (only needed to run tools outside the containers)
- `make`

## Local setup

```bash
git clone <repository-url> opos
cd opos
cp .env.example .env
```

Edit `.env`: at minimum set `SECRET_KEY` and `POSTGRES_PASSWORD` to local
values. Every setting the app reads comes from this file — the app never writes
to local disk and has no config file.

Bring up the stack (web, postgres, redis, celery worker, minio):

```bash
make up
```

Startup runs migrations, syncs the role groups and loads the seed data
automatically. The site is then at http://localhost:8000 and the admin at
http://localhost:8000/admin/. Create an admin account with:

```bash
make superuser
```

## Everyday commands

```bash
make up        # start the stack
make down      # stop it
make logs      # tail container logs
make shell     # Django shell
make test      # pytest
make migrate   # apply migrations
make lint      # ruff check and format
```

## Running tools on the host

Optional — everything above works inside the containers. To run `ruff` and
`pytest` directly:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Tests need PostgreSQL and Redis reachable at the hosts named in `.env`.

## Working notes

- Migrations are reviewed by hand and never auto-applied in CI.
- No secrets in the repository. `.env` is ignored; `.env.example` is committed
  with dummy values and should be updated whenever a new setting is introduced.
- Check any new public page with JavaScript disabled: if the factual content is
  not in the raw HTML response, it does not count as shipped.
