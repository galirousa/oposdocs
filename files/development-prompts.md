# Development Prompts

Companion to `oposiciones-infrastructure-plan.md`. Each prompt is one session's work for a coding agent (Claude Code or similar), in order. Run them on separate branches and review between each.

**Prompt 0 is not optional.** It creates the file the agent re-reads every session. Without it you will spend every subsequent prompt re-explaining the project and getting inconsistent decisions.

**On ordering:** the infrastructure plan's §15 build order put SEO inside each feature. That was wrong given your requirements. Discoverability is now Prompt 3, before documents exist, because it sets the URL taxonomy, the template contract and the rendering strategy — all three are painful to change once you have 50,000 indexed pages.

---

## Prompt 0 — Project context file

```
Create a CLAUDE.md at the repository root that will be read at the start of
every future session. It should be concise and factual, not aspirational.

Include:

PROJECT
A web platform for people preparing Spanish public-sector exams (oposiciones).
Users search, browse and download study documents: official documents
(BOE, convocatorias, bases), editorial documents (curated by us), and
user-contributed notes. Editorial staff curate which oposiciones appear on
the homepage and which official documents attach to each. Revenue is
advertising, so organic discoverability is the business model, not a
marketing afterthought.

STACK
Django 5 + PostgreSQL 16 + Redis + Celery. Garage (S3-compatible) for files.
Caddy reverse proxy. Docker Compose on a single self-hosted server behind a
Cloudflare Tunnel. Server-rendered HTML; no SPA.

TWO NON-NEGOTIABLE CONSTRAINTS
1. Every public page must be fully rendered in the initial HTML response.
   No content that requires JavaScript to appear. Search engine crawlers and
   AI crawlers largely do not execute JS, and content they cannot see does
   not exist.
2. The app is stateless. No local disk writes, no filesystem sessions, no
   local upload directory. All configuration from environment variables.
   This is what makes future scaling a config change rather than a rewrite.

LANGUAGE
Interface and content in Spanish (es-ES). Code, comments, commit messages
and identifiers in English. Database stores Spanish content; do not
translate domain terms — oposición, convocatoria, temario, tema, cuerpo,
escala, ámbito, plaza stay as-is in model and field names where they are
domain concepts.

CONVENTIONS
- Type hints on all function signatures.
- ruff for lint and format. Settings split into base/dev/prod.
- Tests with pytest-django. Every model gets factory-boy factories.
- Migrations reviewed by hand, never auto-applied in CI without review.
- No secrets in the repo. django-environ reads from .env; .env.example is
  committed with dummy values.

Then create .env.example, .gitignore, pyproject.toml with ruff and pytest
config, and a README with local setup steps.
```

---

## Prompt 1 — Foundations and deployment loop

Get the deployment pipeline working before there is anything to deploy. This is the phase people skip and regret.

```
Set up the project skeleton and a working deployment loop. No application
features yet.

1. Django 5 project with settings split: config/settings/{base,dev,prod}.py,
   using django-environ. Include django-extensions, django-debug-toolbar
   (dev only), whitenoise for static files.

2. docker-compose.yml for local development: web (runserver), postgres:16,
   redis:7, and a celery worker. Named volumes for pg data. Hot reload on
   the web container.

3. docker-compose.prod.yml: gunicorn behind Caddy, postgres, redis, celery
   worker, celery beat. Caddy config with automatic HTTPS. Postgres and
   Redis bound to the internal Docker network only, never published to the
   host. Bind-mount data directories to host paths, not anonymous volumes.

4. Multi-stage Dockerfile. Build stage installs dependencies, runtime stage
   is slim and runs as a non-root user. Include poppler-utils, tesseract-ocr
   and the spa language pack in the runtime image — we need them later and
   forgetting them causes confusing failures at that point.

5. A health check endpoint at /healthz that verifies database and Redis
   connectivity and returns JSON. This is what external uptime monitoring
   will poll.

6. GitHub Actions workflow: run ruff, run pytest, build the image, push to
   GHCR on main. A separate manually-triggered deploy job that SSHes to the
   host, pulls, runs migrations, and restarts. Deployment must be a single
   command I can also run by hand.

7. A Makefile with: up, down, logs, shell, test, migrate, lint.

Done when: `make up` gives me a working local site, `make test` passes, and
the CI workflow runs green on a pull request.
```

---

## Prompt 2 — Editorial core

```
Build the editorial domain models and admin. No documents or user accounts
yet.

Models in an `oposiciones` app, following the schema in section 4 of the
infrastructure plan:

Oposicion: slug (unique), nombre, ambito (choices: estado, autonomica,
local), comunidad (nullable, only for autonómica/local), cuerpo, escala,
grupo (A1, A2, B, C1, C2, E), titulacion_requerida, sistema_selectivo
(oposicion, concurso-oposicion, concurso), organismo_convocante,
descripcion (rich text), is_featured (bool), homepage_order (int),
is_published (bool), created_at, updated_at.

Convocatoria: FK oposicion, anio, referencia_boe, url_boe, plazas (int),
plazas_libre, plazas_discapacidad, fecha_publicacion, fecha_limite_solicitud,
estado (choices: anunciada, abierta, cerrada, en_proceso, resuelta),
notas.

Tema: FK oposicion, numero, titulo, bloque (nullable grouping), ordering by
(oposicion, numero) with a unique constraint on that pair.

Requirements:
- Slugs auto-generated from nombre + ambito + comunidad, unique, and
  IMMUTABLE once published. Changing a published slug breaks every inbound
  link and every search ranking we have earned. Enforce this in the model
  and surface it as a read-only field in the admin after publication.
- A `derived_title` property producing the natural Spanish name users
  actually search for, e.g. "Auxiliar Administrativo del Estado" — this
  becomes the H1 and the <title>.

Admin:
- Oposicion list with filters on ambito, comunidad, grupo, is_featured,
  is_published. Inline editing of homepage_order and is_featured directly
  in the changelist.
- Convocatoria and Tema as inlines on Oposicion.
- A dedicated admin view for homepage curation: drag-to-reorder featured
  oposiciones, or at minimum a filtered list with bulk actions.
- Spanish verbose_name and verbose_name_plural throughout, since editors
  will read this interface.

Also: a management command `seed_oposiciones` that loads 15-20 real
state-level oposiciones as fixtures so we have plausible data to build
against.

Done when: an editor can create an oposición with temario and convocatorias,
mark it featured, and see it ordered on a (still bare) homepage.
```

---

## Prompt 3 — Discoverability foundation

This is the prompt that makes or breaks both requirements. It comes before documents deliberately.

```
Build the discoverability layer: URL taxonomy, page templates, structured
data, and machine-readable surfaces. This must exist before we add
documents, because it defines the contract every future page conforms to.

URL TAXONOMY (design once, never change)
/                                              homepage
/oposiciones/                                  index, faceted
/oposiciones/{ambito}/{slug}/                  oposición detail
/oposiciones/{ambito}/{slug}/temario/          temario
/oposiciones/{ambito}/{slug}/convocatorias/    convocatorias list
/convocatorias/{anio}/{slug}/                  convocatoria detail
Lowercase, hyphenated, no IDs, no trailing query params in canonical form.
Accented characters transliterated in slugs (oposición -> oposicion).
Design it so /oposiciones/autonomica/{comunidad}/{slug}/ slots in later
without breaking existing URLs.

PAGE STRUCTURE — "answer first"
Every oposición page opens with a factual paragraph, in the initial HTML,
stating: what the role is, which body convokes it, the grupo, the required
qualification, and the current convocatoria status. Written as prose that
stands alone when extracted with no surrounding page context. This single
paragraph is what an LLM will quote when asked "qué es la oposición a
auxiliar administrativo del estado".

Immediately below, a FACTS BLOCK rendered as a semantic <dl> with the same
data as key-value pairs. Human-scannable and trivially machine-extractable.
Render the identical data in JSON-LD. Never let the visible facts and the
structured data diverge — generate both from one source.

STRUCTURED DATA (JSON-LD, one reusable template tag)
- Site-wide: Organization, and WebSite with a SearchAction pointing at our
  search endpoint (sitelinks searchbox eligibility).
- Oposición: CollectionPage + BreadcrumbList + ItemList of its documents.
- Convocatoria: use JobPosting. These are literally public job openings,
  and JobPosting makes us eligible for Google Jobs, which is a large and
  underexploited traffic source in this niche. Required fields: title,
  description, datePosted, validThrough (fecha_limite_solicitud),
  hiringOrganization, jobLocation, employmentType. Only emit it when
  estado is 'abierta' and validThrough is in the future — stale
  JobPosting markup gets you penalised.
- Add FAQPage markup where an oposición has editorial Q&A content.
Validate everything against schema.org and Google's Rich Results Test.

CRAWLER ACCESS
robots.txt served from Django, not a static file, so it is environment-aware
(staging must be fully disallowed).

Allow, explicitly and by name:
  Googlebot, Bingbot, Google-Extended
  GPTBot, OAI-SearchBot, ChatGPT-User
  ClaudeBot, Claude-User, Claude-SearchBot
  PerplexityBot, Perplexity-User
  CCBot, Applebot, Applebot-Extended
We WANT AI crawlers. Being cited by an assistant is distribution, and this
is a discovery product — blocking them forfeits the channel. Set
Crawl-delay for the aggressive ones since our upstream bandwidth is limited.

Disallow: /admin/, /api/internal/, and any URL with filter query parameters
(crawl traps).

Add a comment in robots.txt noting that Cloudflare's "Block AI Scrapers and
Crawlers" setting must be OFF in the dashboard, or this file is overridden
at the edge and none of it takes effect.

MACHINE-READABLE SURFACES
- /llms.txt following the llms.txt convention: a markdown document
  describing what the site is, its main sections, and a linked index of
  published oposiciones. Generated from the database, cached.
- Content negotiation: appending .md to any public URL returns clean
  markdown of that page — heading, facts block as a markdown table, prose,
  and a document list. No navigation chrome, no ads, no boilerplate. This
  is cheap in Django and makes us dramatically easier for an agent to
  consume than any competitor.
- Sitemaps: a sitemap index with separate sitemaps per section, using
  Django's sitemap framework. lastmod from updated_at. Auto-ping search
  engines on publish.

TECHNICAL SEO
- Canonical URL on every page, self-referencing.
- Unique title and meta description per page, generated from data with
  sensible templates, overridable per object in the admin.
- OpenGraph and Twitter card tags.
- <html lang="es">. Plan hreflang for future ca/gl/eu regional content.
- Faceted filter combinations: canonical to the unfiltered page and
  noindex,follow. Only curated facet combinations get indexable URLs.
- Reserve fixed-height containers for ad slots now, before ads exist, so
  we never ship layout shift.

Do NOT add: any client-side rendering of content, infinite scroll on
indexable listings, or content behind interaction.

Done when: Rich Results Test passes on an oposición and a convocatoria page,
/llms.txt and .md endpoints return sensible output, and the raw HTML of an
oposición page contains the full factual answer with JavaScript disabled.
```

---

## Prompt 4 — Documents and ingestion

```
Build the document model and ingestion pipeline. Editorial and official
documents only — no user uploads yet.

Models per section 4 of the plan. The critical design point: source_type,
visibility and moderation_status are THREE INDEPENDENT FIELDS. Do not
collapse them. A user document can be public; an official document can be
temporarily private.

Document: title, description, uploader (nullable FK), source_type
(official|editorial|user), visibility (public|registered|private),
moderation_status (pending|approved|rejected|flagged|taken_down),
storage_key, sha256 (unique, indexed), mime_type, size_bytes, page_count,
extracted_text (TextField), extraction_status, license, download_count,
created_at, updated_at.
M2M to Oposicion and to Tema. FK nullable to Convocatoria.

Storage: django-storages with the S3 backend pointed at Garage. Content-
addressed keys: documents/{sha256[:2]}/{sha256}. Thumbnails at
thumbs/{sha256}.webp.

Celery pipeline, chained tasks, each independently retryable:
1. Hash and dedupe — if sha256 exists, link to the existing Document
   instead of storing a duplicate.
2. ClamAV scan.
3. Text extraction — pdftotext for PDFs with a text layer, python-docx for
   Word.
4. OCR fallback — if extraction yields under ~100 chars per page, queue
   Tesseract with lang=spa. Separate low-priority queue, capped
   concurrency, page-count ceiling so one 800-page scan cannot starve
   everything else.
5. Thumbnail from page 1 via pdftoppm, converted to WebP.
6. Mark indexed.

Failure must degrade gracefully: a document with failed extraction still
exists and is still findable by title and tags, just not by full text.
Surface extraction_status in the admin so someone can investigate.

Document detail pages, following the Prompt 3 contract:
- Answer-first paragraph, facts block, JSON-LD.
- Use schema.org DigitalDocument with about, license, isAccessibleForFree,
  datePublished, dateModified.
- Render an extracted-text preview (first ~500 words) in the initial HTML.
  This is what makes documents findable at all — a page containing only a
  title and a download button is invisible to both Google and an LLM.
- THIN CONTENT GUARD: documents with no description AND no extracted text
  get noindex. Thousands of empty pages will damage sitewide rankings.
  Enforce this in the template, driven by a model property.
- Duplicate guard: when one document serves several oposiciones, pick one
  canonical URL and canonicalise the others to it.

Done when: an editor uploads a PDF in the admin, and within a minute it has
extracted text, a thumbnail, and a detail page that passes Rich Results
Test.
```

---

## Prompt 5 — Search

```
Implement search using PostgreSQL full-text search, behind an abstraction
that lets us swap in Meilisearch later without touching call sites.

Define a SearchBackend protocol with index(doc), remove(doc),
query(text, filters, page) -> results. Implement PostgresSearchBackend.
Select via a settings variable.

Postgres specifics that matter for Spanish:
- Install the unaccent and pg_trgm extensions via migration.
- Create a custom text search configuration combining unaccent with the
  built-in 'spanish' dictionary. Without this, "oposicion" will not match
  "oposición" and users type both forms constantly. Verify with a test
  asserting the accented and unaccented queries return identical results.
- search_vector as a generated column, GIN indexed, weighted:
  title A, tema/tag names B, description C, extracted_text D.
- pg_trgm index on Oposicion.nombre and Document.title for typo-tolerant
  autocomplete.

Search results page:
- Server-rendered at /buscar/?q=... with real pagination (numbered links in
  HTML, not infinite scroll).
- Facets: ámbito, grupo, oposición, source_type, año, tipo de archivo.
- Filtered result pages are noindex,follow and canonical to /buscar/.
- Highlight matched terms using ts_headline.
- Empty-state that suggests popular oposiciones rather than showing nothing.

Also add /api/buscar/ returning JSON, documented with an OpenAPI schema at
/api/schema/. Public, read-only, rate-limited. This is deliberate: it gives
agents and downstream tools a clean way to query us, which is a second
discovery channel alongside crawling.

Done when: searching "auxiliar administrativo" and "auxiliar administrativó"
return the same results, facets work, and p95 latency is under 300ms on the
seed dataset.
```

---

## Prompt 6 — Accounts and authorization

```
Add authentication and the role model. Django auth plus django-allauth.

- Email/password with mandatory verification, plus Google sign-in.
- Argon2 password hashing. Rate-limited login (django-axes or allauth's
  built-in limiter).
- Transactional email via SMTP to an external provider (Brevo), configured
  from environment variables. Never send mail from the server directly —
  the residential IP will not deliver.
- A stable UUID external_id on User, separate from email, so we can migrate
  to an external identity provider later without orphaning uploads.

Roles as Django groups: Registered, Contributor, Moderator, Editor, Admin,
with the permission matrix from section 7 of the plan. Contributors skip
the moderation queue; Moderators handle reports; Editors manage oposiciones
and official documents.

Document access control in one place — a single `can_access(user, document)`
function used by both views and the presigned-URL generator, so the rule
cannot drift between them:
- approved + public: everyone
- approved + registered: authenticated users
- private: owner and staff only
- pending/rejected/taken_down: owner and staff only

Presigned URLs: 15-minute expiry, generated per request AFTER the permission
check, with Cache-Control: private, no-store. Public documents are served
through the CDN with long TTLs instead. A private document must never be
cacheable at the edge.

Crucially: authentication must not affect the public rendering path.
Anonymous crawlers must receive identical, fully-rendered HTML for public
pages. No consent-wall, no login-wall, no interstitial on indexable content.

Done when: the four access rules have passing tests, and an anonymous
request to a public document page returns full content with a 200.
```

---

## Prompt 7 — User contributions and moderation

This step carries the legal risk. Everything before it is publishable without it.

```
Add user uploads and the moderation workflow.

Upload flow:
- Presigned direct-to-storage upload from the browser, so the app server
  never handles the bytes.
- Required at upload: title, at least one oposición, and an explicit
  licence declaration the user must actively select (own work / official
  public document / permission granted). No default selection.
- Client and server file type and size validation.
- After upload, the Prompt 4 pipeline runs, then the document lands in the
  moderation queue with moderation_status=pending.

Moderation queue in the admin:
- Filterable list with thumbnail, extracted text preview, uploader history,
  and duplicate detection by sha256.
- Bulk approve/reject with a required reason on rejection, which emails
  the uploader.
- Full audit trail: who changed what status, when, why. Immutable log.

Reports and takedowns:
- Report model: document, reporter (nullable for anonymous), reason
  (copyright, incorrect, inappropriate, duplicate), detail, status.
- A public /aviso-legal/ page with LSSI-required operator details and a
  /retirada-de-contenido/ page with a takedown form. These pages are what
  our safe harbour under Ley 34/2002 depends on — they must be reachable
  from every page footer.
- Taken-down documents return 410 Gone, not 404, and are removed from the
  sitemap and search index immediately.

SEO handling of user content:
- Pending documents: noindex, and excluded from sitemaps entirely.
- Only approved documents enter the search index and the sitemap.
- Uploader profile pages: noindex by default. They are thin and add no
  search value.

Done when: an upload can be reviewed, approved, appears in search, and a
takedown request removes it from the index and returns 410.
```

---

## Prompt 8 — Consent and advertising

```
Add the consent layer and ad slots. Consent first, ads second — never the
reverse.

- Integrate a TCF v2.2 certified CMP (Google's own CMP is free and
  sufficient). Required by Google to serve ads in the EEA.
- No non-essential cookies and no ad scripts fire before consent. Verify
  with a clean-profile network trace.
- Rejecting must be exactly as easy as accepting — one click, same visual
  prominence. This is explicit AEPD guidance and enforcement in Spain is
  real.
- Consent state stored client-side; log consent events server-side for
  audit.

Ads:
- AdSense, in the fixed-height containers reserved in Prompt 3.
- Load asynchronously, below the fold on first paint.
- No ads on the aviso legal, privacy, or takedown pages.

Critical: crawlers must never see the consent banner as blocking content.
The banner is an overlay on top of fully-rendered HTML, not a gate in front
of it. Verify by fetching pages with a Googlebot user agent and confirming
the full content is present.

Then measure Core Web Vitals before and after enabling ads, and record both
numbers. If LCP or CLS regresses meaningfully, fix it before shipping — ad
revenue depends on rankings, so an ad implementation that hurts rankings is
self-defeating.

Done when: PageSpeed Insights shows green CWV with ads enabled, and a
clean-profile trace shows zero ad network requests before consent.
```

---

## Working notes

**Verify after Prompt 3, not at the end.** Fetch your own pages with `curl -A "GPTBot"` and with JavaScript disabled. If the factual answer isn't in the raw HTML, nothing downstream matters.

**Check Cloudflare's AI crawler setting.** It's in Security → Bots, and on some plans blocking is the default. It overrides your robots.txt at the edge, which means you can ship a perfect robots.txt and still be invisible to every assistant. This has caught a lot of people.

**The bandwidth tension is real.** AI crawlers can be aggressive, and you're on a home connection. Rate-limit them at Cloudflare rather than blocking them — you want the traffic, you just want it paced.

**Prompts 1–5 give you a publishable product** with no user-generated content and therefore no copyright exposure. That's a good place to validate demand before taking on Prompt 7.
