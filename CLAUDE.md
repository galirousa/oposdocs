# CLAUDE.md

Read this at the start of every session before making changes.

## PROJECT

A web platform for people preparing Spanish public-sector exams (oposiciones).
Users search, browse and download study documents: official documents
(BOE, convocatorias, bases), editorial documents (curated by us), and
user-contributed notes — uploaded as files or written on the site itself in
markdown (*apuntes*). Editorial staff curate which oposiciones appear on the
homepage and which official documents attach to each. Revenue is advertising,
so organic discoverability is the business model, not a marketing afterthought.

## STACK

Django 5 + PostgreSQL 16 + Redis + Celery. Garage (S3-compatible) for files.
Caddy reverse proxy. Docker Compose on a single self-hosted server behind a
Cloudflare Tunnel. Server-rendered HTML; no SPA.

## TWO NON-NEGOTIABLE CONSTRAINTS

1. **Every public page must be fully rendered in the initial HTML response.**
   No content that requires JavaScript to appear. Search engine crawlers and AI
   crawlers largely do not execute JS, and content they cannot see does not
   exist.
2. **The app is stateless.** No local disk writes, no filesystem sessions, no
   local upload directory. All configuration from environment variables. This is
   what makes future scaling a config change rather than a rewrite.

## LANGUAGE

Interface and content in Spanish (es-ES). Code, comments, commit messages and
identifiers in English. Database stores Spanish content; do not translate domain
terms — oposición, convocatoria, temario, tema, cuerpo, escala, ámbito, plaza
stay as-is in model and field names where they are domain concepts.

## CONVENTIONS

- Type hints on all function signatures.
- `ruff` for lint and format. Settings split into `base`/`dev`/`prod`.
- Tests with `pytest-django`. Every model gets factory-boy factories.
- Migrations reviewed by hand, never auto-applied in CI without review.
- No secrets in the repo. `django-environ` reads from `.env`; `.env.example` is
  committed with dummy values.

## PHASE: DEMO → MVP

The demo phase is over. The build plan in `files/development-prompts.md` has
been walked end to end and the result runs, so the question is no longer "does
this work at all" but "can this take real users, real content and real traffic
without losing data or breaking the law". Development is now MVP work.

What that changes about how we build:

- **Demo shortcuts are debt with a name, not background noise.** Each one is
  listed under KNOWN GAPS below. Closing one is a task; adding a new one needs
  a line there and a reason.
- **Data is real from now on.** No destructive migration without a tested
  rollback, no `--fake`, no manual edits in prod psql. Backups (§12 of the
  plan) must exist before the first outside user, and an untested backup does
  not count.
- **Public URLs are commitments.** The taxonomy and published slugs are frozen;
  anything else public that ships now gets a redirect plan, not a rename.
- **Every feature ships whole**: migration, factories, tests, admin, Spanish
  UI strings, sitemap/JSON-LD where the page is public, and a `.md` view where
  the rest of the section has one. A feature that skips these is not done.
- **Verify in the running app, not just in pytest.** Fetch the page with
  JavaScript disabled and with a crawler user agent before calling it shipped.

## REPOSITORY STATE

A working application, not a skeleton. Layout: `config/settings/{base,dev,prod}.py`
for settings, Django apps at the root of the repo (`accounts`, `core`,
`oposiciones`, `documents`, `posts`, `search`), `templates/` and `static/` at the
root, `docker-compose.yml` for local development and `docker-compose.prod.yml`
for the server, plus `Dockerfile`, `Makefile`, `deploy.sh` and CI in
`.github/`. `make up` migrates, syncs roles, seeds and serves on :8000.

Shipped: editorial core (oposición/convocatoria/tema), the discoverability
layer (URL taxonomy, JSON-LD, robots.txt, `/llms.txt`, `.md` negotiation,
sitemaps), documents with the Celery ingestion pipeline, Postgres full-text
search behind a backend protocol, accounts and role groups, user uploads with
moderation and takedowns, the consent layer, and user-written markdown posts
(*apuntes*) with autosave and drafts. See README.md for the detail.

### Known gaps to close for the MVP

- No backups of any kind. Highest-stakes item in the plan (§12); nothing else
  on this list matters as much.
- The repository is **not under version control yet**. `git init` before the
  next feature; the deploy story assumes a remote.
- User uploads pass through the app server. The plan calls for a presigned
  direct-to-storage upload from the browser (`documents/storage_utils.py`
  already has `presigned_put_url`).
- The consent banner is a hand-rolled placeholder. AdSense in the EEA needs a
  TCF v2.2 certified CMP before ads are switched on.
- No ClamAV in the dev stack; the scan task skips itself when `CLAMAV_HOST` is
  empty. Prod compose has the container — verify it actually runs.
- Search covers `Document` only. `SearchBackend`/`SearchResult` are typed to
  it, so indexing posts means widening that abstraction, not bolting on.
- `Report` has a foreign key to `Document` only, so the takedown form cannot
  reference a post. Posts are withdrawn from the admin.
- Core Web Vitals have never been measured, with or without ads.

## REFERENCE DOCUMENTS

- `files/oposiciones-infrastructure-plan.md` — architecture, data model,
  ingestion pipeline, search, legal risk, operations. The data model in §4 is
  authoritative.
- `files/development-prompts.md` — the ordered build plan, one prompt per
  session. Walked end to end; it is now a record of intent, not a queue. Read
  it to find out *why* something was built a given way, and treat its "done
  when" clauses as the acceptance criteria the MVP still has to hold to.

Two decisions from those documents that are expensive to reverse, so treat them
as settled:

- `source_type`, `visibility` and `moderation_status` are three independent
  fields on `Document`. Never collapse them into one.
- URL slugs are immutable once published, and the URL taxonomy is designed once
  and not changed.
