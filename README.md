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
- **Official sources (harvesting)** — nightly Celery Beat job that pulls
  section II.B of the BOE (*Oposiciones y concursos*) from the open-data API,
  stores each PDF as an `official` document and drops it in the moderation
  queue. Ledger of every item seen (`HarvestedItem`), per-day run record
  (`HarvestRun`), and keyword rules (`HarvestRule`) that attach items to an
  oposición. Backfills to 2020 one day at a time. See *Harvesting* below.
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
make admin     # create the superuser non-interactively
```

## Harvesting official documents

The `sources` app harvests BOE section **II.B — Oposiciones y concursos** from
`https://www.boe.es/datosabiertos/api/boe/sumario/YYYYMMDD`. Around 20–30 items
and 5–10 MB a day.

Requests identify themselves as `OposdocsBot/1.0 (+<SITE_URL>/robots.txt)`,
derived from `SITE_URL` so the bot cannot advertise a domain we do not serve.

```bash
make harvest-recent                     # the last 7 days (what the nightly job does)
DAY=2026-09-01 make harvest-day         # one specific day
SINCE=2020-01-01 make backfill          # the full backfill, in the foreground
```

Imported documents are `source_type=official`, `license=official_public`, and
**`moderation_status=pending`**: nothing reaches the public site until it is
approved in the admin. Approve in bulk under *Documentos*; triage what the
harvester found under *Items capturados*.

### Why it cannot overwhelm the server

Four independent throttles, because any one alone leaves a hole:

1. A dedicated `harvest` queue served by one worker at `--concurrency 1`, so
   two harvest tasks never execute at once however they were enqueued.
2. A Redis lock: Beat firing while a backfill is mid-flight is a no-op, not a
   task queued up behind it.
3. Downloads inside a day are sequential with `HARVEST_DOWNLOAD_DELAY` between
   them — one file at a time, never a fan-out.
4. The backfill enqueues the next day only *after* the current one finishes,
   with `HARVEST_BACKFILL_COUNTDOWN` seconds in between. At the default 120s,
   2020→today is roughly three days of unattended trickle.

The nightly job re-checks `HARVEST_CATCHUP_DAYS` (7) days and skips those with
a completed run, so a missed night — downtime, or the lock held by a backfill —
heals itself without any manual catch-up.

Beat runs in production only. Dev has the harvest worker but no beat container,
so local development never starts downloading the BOE on its own.

## Deploying

The container image is **private** on GHCR, so the server needs a registry
login once, as the user that runs the deploy:

```bash
echo <TOKEN> | docker login ghcr.io -u <github-username> --password-stdin
```

`<TOKEN>` is a classic personal access token with the `read:packages` scope.
Docker writes it to `~/.docker/config.json`, so it survives reboots. Without
it, `deploy.sh` stops with the exact command to run — it will not fall back to
building the image on the machine that is serving traffic (pass
`ALLOW_LOCAL_BUILD=1` if you really want that).

Then, on the server:

```bash
cd /srv/opos && git pull && ./deploy.sh
```

The `git pull` matters as much as the image pull: compose services and their
commands live in the repo, so a new worker (or a changed `beat` command) only
appears if the checkout is updated too.

### Bootstrapping the admin user

Set `DJANGO_ADMIN_PASSWORD` in the server's `.env`, then:

```bash
docker compose -f docker-compose.prod.yml run --rm web python manage.py create_admin
```

It creates or updates the superuser named by `DJANGO_ADMIN_USERNAME`
(default `admin`) and is safe to re-run. With `DEBUG` off it refuses to fall
back to the development placeholder, so an unset password is an error rather
than a weak admin account. Change the password at `/admin/password_change/`
after the first login.

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
