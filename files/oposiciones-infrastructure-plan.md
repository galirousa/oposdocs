# Infrastructure Plan — Document Platform for Oposiciones (Spain)

## 1. Shape of the system

This is a **document repository with editorial curation, full-text search, and user contributions**, monetised by ads. That combination has a specific consequence: almost all your value and almost all your risk sit in the ingestion pipeline (what gets in, what text you extract from it, whether you're allowed to host it). Everything else is a fairly ordinary web app.

So the plan is: one boring server running a boring monolith, with real effort spent on the document pipeline and the moderation workflow.

**Design rule for the whole thing:** the app containers hold no state. No local uploads directory, no local session files, config from environment variables only. If you hold that line from day one, every scaling step later is "add a machine", not "rewrite".

---

## 2. Recommended stack

| Layer | Choice | Why |
|---|---|---|
| App | **Django** (Python) | Django admin gives you the editorial back-office essentially for free — that's a whole feature you don't build. Auth, permissions, migrations included. Server-rendered = good SEO, which is your revenue. |
| Database | **PostgreSQL 16** | Also your search engine at launch (see §6). One less service. |
| Queue / cache | **Redis** + **Celery** | Background jobs for text extraction, OCR, thumbnails. Redis doubles as cache and session store. |
| Object storage | **Garage** (self-hosted, S3-compatible) | Runs on your box as one small container. Keeps the S3 API so nothing in your code changes if you ever move the files off-site. |
| Reverse proxy | **Caddy** | Automatic TLS, ~10 lines of config. Traefik if you prefer labels. |
| CDN / edge | **Cloudflare** (free tier) | Not self-hostable, and the one external service I'd argue hardest for. See §3a. |
| Orchestration | **Docker Compose** | On one host. Kubernetes is not justified here and may never be. |
| Host | **Your server** | See §3a for what genuinely can't live there. |
| Error tracking | **GlitchTip** (self-hosted) | Sentry-compatible SDK, but runs on Django + Postgres in a couple hundred MB. Self-hosted Sentry needs Kafka and ClickHouse and ~16 GB of RAM on its own — don't. |
| Transactional email | **External provider** | The other thing that can't practically be self-hosted. See §3a. |

**If you'd rather not use Python:** Laravel + Filament (PHP) or Rails + ActiveAdmin (Ruby) map onto this plan almost one-for-one — both give you the admin panel and batteries-included auth that make Django attractive here. Avoid a Next.js + separate API split at this stage: you'd hand-build the admin, hand-build auth, and split one deployable into two for no benefit at your size.

Where Python earns its place specifically: the PDF/text-extraction ecosystem (pypdf, pdfplumber, Tika, pytesseract) is the best of the three, and that pipeline is the core of the product.

---

## 3. Launch architecture

```
                      Internet
                         │
                  ┌──────▼──────┐
                  │ Cloudflare  │  DNS, TLS, WAF, CDN cache, origin IP hidden
                  └──────┬──────┘
                         │  (tunnel or origin-locked firewall)
   ┌─────────────────────▼──────────────────────────────┐
   │  YOUR SERVER  (Docker Compose)                     │
   │                                                    │
   │   Caddy ──► Django (gunicorn) ──┐                  │
   │                                 │                  │
   │             Celery worker ──────┤                  │
   │             Celery beat         │                  │
   │             ClamAV              │                  │
   │                                 │                  │
   │             Postgres ◄──────────┤                  │
   │             Redis    ◄──────────┤                  │
   │             Garage (S3) ◄───────┘   files + thumbs │
   │             GlitchTip                              │
   │             Netdata                                │
   └───────┬─────────────────────────────┬──────────────┘
           │ restic (encrypted)          │ SMTP
   ┌───────▼────────────┐        ┌───────▼──────────┐
   │ Offsite backup     │        │ Email provider   │
   │ (B2 / Storage Box) │        │ (Brevo / SES)    │
   └────────────────────┘        └──────────────────┘

   ┌────────────────────┐
   │ External uptime    │ ──► pings your server from outside
   │ (Healthchecks/BS)  │
   └────────────────────┘
```

Everything that can run on your box does. Postgres, Redis and Garage all use bind-mounted volumes on the host; containers stay disposable, data does not.

---

## 3a. What genuinely cannot live on your server

Three things, and each for a different reason. I'd push back on self-hosting any of them.

**Offsite backups.** This one is definitional — a backup on the same machine as the data is not a backup. If that server dies, is stolen, or gets encrypted by ransomware, you lose the product. Budget €3–6/month for Backblaze B2 or a Hetzner Storage Box and push encrypted restic snapshots there nightly. This is the single most important line item in the entire plan.

**External uptime monitoring.** A monitor running on the server it monitors reports "all fine" right up until it stops reporting anything, and then tells you nothing about why. Healthchecks.io and BetterStack both have free tiers sufficient for this. Netdata still runs locally for host metrics — the two answer different questions.

**Outbound transactional email.** You need account verification, password resets and moderation notices to actually arrive. Running your own SMTP from a fresh IP means Gmail and Outlook silently bin your mail for months while you build reputation, and if your server is on a residential range you will never get delivery at all. Use Brevo (300/day free, EU company), Amazon SES, or Mailgun. Self-hosting mail is a hobby, not an infrastructure decision.

**Cloudflare is a strong recommendation but not strictly mandatory.** It's free, it hides your origin IP, it absorbs volumetric DDoS, and it caches your public PDFs so your upstream bandwidth isn't the bottleneck. The argument gets stronger the less robust your connection is. If you want to avoid it on principle, you can serve directly from Caddy — but then your server's IP is public, your upstream link is your CDN, and a bored teenager with a booter can take you offline. A Cloudflare Tunnel is a good middle path: no inbound ports open at all, which is especially valuable on a home or office connection.

**Everything else self-hosts cleanly:** object storage (Garage), search (Meilisearch when you need it), error tracking (GlitchTip), metrics (Netdata, later Prometheus + Grafana + Loki), and git + CI (Forgejo with an Actions runner, if you'd rather not use GitHub).

---

## 3b. Hosting from a home or office connection

This is workable, and plenty of real services run this way. But it introduces five problems that don't exist in a datacentre, and two of them should be solved before you write any application code.

### Do these before launch

**1. Add a second disk and mirror it.** Right now a single drive failure loses the database, every uploaded document, and the business. On a home machine there's no hypervisor quietly replicating your blocks underneath you. A ZFS mirror is the best value here — it gives you redundancy, block checksumming (which catches silent corruption that RAID alone won't), and cheap local snapshots you can restore from in seconds after a bad migration. Two matched drives is the smallest amount of money that removes the largest risk in this plan.

Size for growth: temarios and scanned notes run 5–50 MB each, so a library of 10,000 documents is comfortably 200–400 GB before thumbnails and backups.

RAID is still not a backup. You need both — §12.

**2. Use a Cloudflare Tunnel.** On a residential line this stops being an optional hardening measure and starts solving four problems at once:

- **CGNAT.** Many Spanish fibre providers no longer hand out public IPv4 by default. A tunnel dials outbound, so it works regardless.
- **Dynamic IP.** No DDNS scripts, no stale DNS after a router reboot.
- **No inbound ports.** Nothing on your home network is exposed to the internet, which matters a great deal more when that network also has your laptop and your NAS on it.
- **Your home IP stays private.** This one is worth dwelling on: an IP geolocates to roughly your neighbourhood, and you are building a site that will eventually annoy commercial academies with legal departments. Don't publish your home address by accident.

### Plan for these

**3. Uptime is now your problem, and it's an SEO problem.** Power cuts, router firmware updates, ISP maintenance, and someone unplugging the wrong thing all become outages. Google reduces crawl rate against a flaky origin and rankings recover slowly — and since your revenue is ad impressions against organic traffic, uptime converts fairly directly into money. A cheap UPS (even 30 minutes) is the highest-return €80 you'll spend: it covers the brownouts and short cuts that cause most home-server downtime, and it prevents the mid-write power loss that corrupts a database.

**4. Upstream bandwidth is your real ceiling.** Spanish FTTH is usually symmetric, which helps, but a document repository has a long-tail access pattern — thousands of documents each fetched rarely — so CDN cache hit rates are mediocre and a lot of requests reach your origin. This is why §14 flags documents as the first thing to move off-box. Note also that Cloudflare's free plan isn't intended for serving large volumes of non-HTML files; a PDF library is a grey area, and **R2 is the sanctioned path** if you grow into it. Because everything already speaks S3, that migration is a credentials change.

**5. Check your ISP contract.** Most Spanish residential terms prohibit running commercial services, and enforcement is rare but not zero. A business line costs more but gives you a static public IP, an SLA, and permission. If this becomes real revenue, upgrade.

### One legal knock-on

Spain's LSSI (Ley 34/2002, art. 10) requires a public *aviso legal* naming the operator and a domicile. Combined with copyright complaints from academies, that means your home address becomes the published contact for legal notices. Use a *domiciliación de empresas* service (€20–50/month) or set up an SL before launch. Decide this early — retrofitting the operator identity after you've been publishing is awkward.

---

## 4. Data model — the one decision worth getting right now

You described documents as "public, official or user provided". Those are **three independent axes** collapsed into one word, and if you store them in a single column you will regret it within months.

Split them:

- **`source_type`** — where it came from: `official` (BOE, ministerio, convocatoria oficial), `editorial` (produced or curated by you), `user` (uploaded by a member).
- **`visibility`** — who can see it: `public` (indexable by Google, no login), `registered` (login required), `private` (uploader only).
- **`moderation_status`** — `pending`, `approved`, `rejected`, `flagged`, `taken_down`.

A user-uploaded document can be public. An official document can be temporarily private while you check it. A rejected document is neither. Only the three-axis model expresses all of that.

Core tables:

```
User
Oposicion          slug, nombre, ámbito (estado|autonómica|local),
                   comunidad, cuerpo/escala, grupo (A1|A2|C1|C2),
                   is_featured, homepage_order, descripción
Convocatoria       oposicion_fk, año, referencia_boe, url_boe,
                   plazas, fecha_límite, estado
Tema               oposicion_fk, número, título      (temario structure)
Document           title, description, uploader_fk,
                   source_type, visibility, moderation_status,
                   storage_key, sha256, mime, size, page_count,
                   license, extracted_text, search_vector,
                   download_count, created_at
DocumentOposicion  m2m — a document can serve several oposiciones
DocumentTema       m2m
Report             document_fk, reporter, reason, status   (takedowns)
Vote               document_fk, user_fk, value
```

Two details that pay for themselves: **`sha256`** lets you reject duplicate uploads at ingest (a shared-notes site accumulates the same PDF fifty times), and **`license`** on every document forces you to record *why* you're allowed to host each file.

---

## 5. Ingestion pipeline

Runs as Celery tasks, chained. Never inline in the request.

1. **Presigned direct upload** — browser uploads straight to object storage using a short-lived presigned URL. Your app server never touches the bytes. This alone saves you an enormous amount of bandwidth and memory.
2. **Hash and dedupe** — SHA-256; if it already exists, link the user to the existing document instead of storing a copy.
3. **Virus scan** — ClamAV. Non-negotiable for user uploads.
4. **Text extraction** — `pdftotext` (poppler) for PDFs with a text layer; python-docx / Tika for the long tail of formats.
5. **OCR fallback** — if extraction yields under ~100 characters per page, queue Tesseract with the `spa` language pack. Scanned handwritten notes are common here. OCR is CPU-hungry: give it a separate low-priority queue and a page-count cap so one 800-page scan can't stall everything.
6. **Thumbnail** — `pdftoppm` on page 1, WebP, stored alongside the original.
7. **Index** — write the search vector.
8. **Moderation** — `source_type = user` lands in the review queue; official and editorial documents auto-approve.

Extraction failure should downgrade gracefully: the document still exists and is still findable by title and tags, it's just not full-text searchable. Flag it in the admin so someone can look.

---

## 6. Search

**Start with PostgreSQL full-text search.** For a corpus in the tens of thousands of documents it is genuinely good, and it costs you zero additional infrastructure.

Specifics that matter for Spanish:

- Use the built-in `spanish` text search configuration for stemming and stopwords.
- Install the **`unaccent`** extension and build a custom configuration on top of it. Without this, `oposicion` will not match `oposición` and your users type both. This is the single most common mistake on Spanish-language search.
- Weight fields: title `A`, tags/temas `B`, description `C`, extracted body `D`.
- Store `search_vector` as a generated column with a GIN index; refresh via trigger or in the indexing task.
- Facets (oposición, ámbito, grupo, año, source_type, file type) are ordinary indexed `WHERE` clauses.
- Add `pg_trgm` for fuzzy matching on titles and oposición names, which covers most typo cases in the autocomplete.

**Put this behind a `SearchBackend` interface** with `index(doc)`, `remove(doc)`, `query(...)`. Then swapping is a day's work, not a rewrite.

**Switch to Meilisearch when** any of these is true: the corpus passes roughly 100k documents; p95 search latency exceeds ~300 ms; or you want instant-as-you-type results with real typo tolerance. Meilisearch is a single container with an EU-friendly self-hosted licence and would run on the same box initially. Elasticsearch/OpenSearch is overkill unless you end up doing something far more analytical.

---

## 7. Authentication and authorization

You said auth can be offloaded. My recommendation is **don't, initially** — with Django you'd be adding a network dependency and a user-record synchronisation problem to replace something the framework already does well.

**Launch:** Django auth + `django-allauth` for email/password plus Google sign-in (which is what most Spanish consumer users will pick). Argon2 password hashing, mandatory email verification before upload rights, rate-limited login.

**Escape hatch:** implement your session layer as OIDC-compatible from the start. If you later want out of the password business, you point it at an external IdP and migrate. Keep a stable external `user_id` on your side that isn't the email address, so a provider change doesn't orphan anyone's uploads.

**If you offload anyway,** pick an EU-hosted provider for GDPR simplicity — Zitadel Cloud or Auth0's EU region. Self-hosting Keycloak is possible but it is a genuinely heavy piece of operational work and it undercuts your "keep it simple" goal.

**Authorization** is coarse and fits Django's group/permission system directly:

| Role | Can |
|---|---|
| Anonymous | Browse and search public documents |
| Registered | Download, upload (post-verification), vote, report |
| Contributor | Uploads skip the moderation queue |
| Moderator | Approve, reject, handle reports |
| Editor | Manage oposiciones, homepage, official documents |
| Admin | Everything, including user management |

Document-level checks reduce to: is it approved, does its visibility permit this user, or is this user the owner.

---

## 8. Editorial control

This is where Django admin repays the framework choice. Out of the box you get CRUD for oposiciones, convocatorias, and documents; a moderation queue as a filtered changelist with bulk approve/reject actions; and homepage curation via `is_featured` and `homepage_order`. Budget a couple of days of admin customisation, not a couple of weeks of building a back-office.

Worth considering for official content: the **BOE publishes open data with an API**. Convocatorias, bases, and corrections are all there. A scheduled job that pulls new convocatorias matching your tracked oposiciones and drops them into an editorial review queue would make "official documents" largely self-maintaining, and it's a real differentiator against the forums and Telegram groups you're competing with.

---

## 9. Storage and delivery

- **Public documents:** served through Cloudflare with long cache TTLs. Cheap and fast.
- **Registered-only and private documents:** short-lived presigned URLs (5–15 minutes), generated per request after the permission check, with caching explicitly disabled. Do not let a private document land in an edge cache.
- **Thumbnails and previews:** always public and cached — they're what makes search results scannable.
- **Bucket layout:** `documents/{sha256[:2]}/{sha256}` for originals, `thumbs/{sha256}.webp` for previews. Content-addressed storage means deduplication is free and re-uploads are idempotent.

**On running Garage locally:** a single-node S3 service on the same box is, physically, a directory with extra steps — and that's fine. You're paying a small amount of overhead to keep the storage interface honest, so that moving files off-box later is a config change rather than a refactor. Point Garage at a dedicated filesystem path (ideally a separate disk or volume from Postgres, since document reads and database writes have very different IO patterns).

A note on **MinIO**, which you'll see recommended everywhere: its community edition has been progressively stripped of features and pushed toward the commercial product, and it's AGPL. Garage (AGPL, from Deuxfleurs) is smaller, calmer, and aimed squarely at self-hosters. SeaweedFS is the other reasonable pick if you expect very large object counts.

Since you lose the managed provider's durability guarantees, **your backup discipline is now the only thing standing between you and permanent data loss.** Content-addressed layout helps here: restic deduplicates it beautifully and incremental snapshots stay small.

---

## 10. Ads, consent, and SEO

These three are one system, because ad revenue depends on organic traffic and organic traffic depends on page speed, which ads degrade.

**Consent.** Spain is GDPR plus LOPDGDD, and the AEPD's guidance is strict: rejecting must be as easy as accepting, and no non-essential cookies or ad scripts may fire before consent. Google requires a TCF v2.2-certified CMP to serve ads in the EEA. Google's own free CMP satisfies this; Cookiebot and Didomi are the paid alternatives. Build the consent gate before you build the ad slots, not after.

**Ad delivery.** AdSense to start, Google Ad Manager if volume justifies it later. Reserve fixed-height containers for every ad slot so late-loading ads don't shift layout — cumulative layout shift is both a ranking signal and the thing that makes ad-supported sites feel cheap.

**SEO.** Every oposición, convocatoria, and public document needs its own server-rendered URL with a real text snippet from the extracted content, otherwise Google has nothing to index and you have no traffic. Generate `sitemap.xml` from the database. Add `Dataset`/`Article` structured data. Plan URL structure for regional expansion (`/oposiciones/{ámbito}/{comunidad}/{cuerpo}`) even if you launch with state-level only.

One realistic caveat: RPMs in this niche are modest, and AdSense approval is not guaranteed for sites built largely on user uploads. Treat moderation quality as a revenue prerequisite, not just a legal one.

---

## 11. Legal risk — read this before writing code

Notes for oposiciones are heavily produced by commercial academies (Adams, MAD, CEF and others), and a substantial fraction of what users will try to upload is scanned copyrighted material. This is the biggest non-technical risk in the project.

What protects you is the safe harbour in **Ley 34/2002 (LSSI-CE)**, and it only applies if you act on notice. Concretely, before launch you need:

- A published **notice-and-takedown** process with a reachable contact, and an SLA you actually meet.
- The `Report` table wired to a moderator queue with an audit trail of what was removed and when.
- Terms of service where uploaders warrant they hold the rights, plus a required licence declaration per upload.
- A moderation policy that rejects anything that looks like a scanned commercial textbook — cover pages, publisher logos, consistent professional typesetting are decent heuristics for flagging.

Officially published material (BOE, convocatorias, ministry documents) is generally reusable and is your safest core content. Lean on it.

I'm not a lawyer and this isn't legal advice — get a Spanish IP/internet lawyer to review your ToS and takedown process. It is a cheap consultation relative to the exposure.

---

## 12. Operations

**Backups — now the highest-stakes part of the plan.** Nightly `pg_dump` plus WAL archiving, and the Garage data directory, both pushed with **restic** (encrypted client-side, deduplicated) to Backblaze B2 or a Storage Box. Retention: 7 daily, 4 weekly, 6 monthly. **Schedule a quarterly restore drill onto a scratch machine** — an untested backup is a rumour, and on self-hosted infrastructure it's the rumour your business depends on.

**Disk redundancy.** You're on a single disk today, which means a drive failure is total loss back to your last snapshot. Fix this before launch — see §3b. Use ZFS mirror rather than plain RAID 1 if you have the choice: checksumming catches bit rot that RAID silently passes through, and local snapshots give you a five-second rollback after a bad migration. RAID is not a backup — it protects against a dead disk, not a bad `DELETE` or a ransomware event — so you need both.

**RAM and CPU.** With 16–32 GB you have generous headroom: Postgres, Redis, Django, Celery, Garage, GlitchTip and later Meilisearch all fit without tuning gymnastics. Give Postgres `shared_buffers` around 25% of total and leave the rest to the page cache. Your actual constraint will be **CPU during OCR** and **disk space as the library grows**, not memory — so cap OCR concurrency to leave a core or two for serving requests, and put Tesseract work on its own low-priority queue.

**Monitoring.** GlitchTip on-box for application errors. Netdata on-box for host metrics — and on your own hardware, watch SMART attributes and disk temperature too, which you'd never have thought about on a VPS. External uptime checks from off-box (§3a). Add Prometheus + Grafana + Loki only when you have more than one machine and grep stops working.

**CI/CD.** Either GitHub Actions building and pushing to GHCR, then SSH to the host for `docker compose pull && up -d`; or fully self-hosted with **Forgejo** plus its Actions runner and built-in container registry, which is a light install and keeps the whole loop on your box. If the server is your only machine, note that building images on it competes with serving traffic — schedule deploys accordingly or build elsewhere.

**Security baseline — more your problem now.** SSH keys only, root login disabled, firewall allowing only 22/80/443 (or nothing inbound at all if you use a Cloudflare Tunnel), unattended security upgrades, Postgres/Redis/Garage bound to the Docker network and never published to the host, fail2ban on SSH. Restrict port 80/443 to Cloudflare's published IP ranges so nobody can bypass the edge and hit your origin directly.

**Single point of failure.** One server means maintenance is downtime and hardware failure is an outage of unknown length. That's an acceptable trade at launch — just decide in advance what your recovery story is, because "restore to a rented VPS from the offsite backup" is a plan you want to have written down before you need it, not during.

---

## 13. Cost at launch

| Item | Monthly |
|---|---|
| Server | €0 (yours) |
| Electricity (~60 W continuous, Spanish domestic rates) | ~€10–13 |
| Offsite backup (B2, ~500 GB) | ~€3 |
| Transactional email (Brevo free tier) | €0 |
| Cloudflare (incl. Tunnel) | €0 |
| External uptime monitoring | €0 |
| Domain | ~€1 |
| Legal domicile (*domiciliación*) | €20–50 |
| **Total** | **~€35–65/month** |

Plus one-off hardware you should buy before launch: **a second drive for the mirror** (€60–120) and **a UPS** (€80–150).

The honest read: once electricity and a legal address are counted, self-hosting isn't meaningfully cheaper than a €30/month VPS. What you're actually buying is control, no egress metering, and hardware you already own — which are good reasons. Just don't choose it expecting it to be free, and treat the disk mirror and UPS as part of the cost of doing it properly rather than as optional extras.

---

## 14. Expansion path

Each step is independent and triggered by a measurement, not a hunch.

| Trigger | Action |
|---|---|
| OCR saturating CPU and delaying uploads | Separate high/low priority Celery queues first; only then a second machine |
| Upstream bandwidth saturated serving PDFs | Push harder on Cloudflare caching; then move the documents bucket to external object storage and keep everything else in-house |
| Corpus >100k docs or search p95 >300 ms | Meilisearch as another container on the same box; it's light |
| RAM pressure between Postgres, Garage and workers | Add RAM before adding machines — usually the cheapest fix you have |
| App CPU-bound at peak | Second app instance behind Caddy — trivial, because the app is stateless |
| Downtime starting to cost real ad revenue | Rent a small VPS as a warm standby with replicated Postgres; keep your server as primary |
| Growth beyond Spain-only or multi-region | Reconsider architecture from evidence, not in advance |

Owning the hardware changes the shape of this table: your first several scaling moves are **upgrades to one machine** (more RAM, more disk, better CPU) rather than more machines. That's simpler and cheaper, and it's a real advantage of your setup — right up until you hit the ceiling of a single box, at which point the stateless-app discipline from §1 is what lets you spread out without a rewrite.

The one genuinely hybrid move worth planning for: **documents are the part most likely to outgrow a home connection first**, since they're large, cacheable, and bandwidth-hungry. Because they sit behind the S3 API, moving just that bucket to a provider is a credentials change. Everything else stays yours.

Kubernetes is not on this list on purpose. You are unlikely to need it, and adopting it early would cost you more engineering time than every step above combined.

---

## 15. Suggested build order

1. **Foundations** — Django project, Postgres, Docker Compose, Caddy, CI/CD, deployed and reachable over HTTPS. Nothing else. Get the deployment loop working before there's anything to deploy.
2. **Editorial core** — oposiciones, convocatorias, temas; admin configured; homepage curation. Populate with real state-level data by hand. At this point you have a useful directory site with zero user features.
3. **Documents** — model, presigned upload, ClamAV, text extraction, thumbnails. Editorial and official documents only. Still no public uploads.
4. **Search** — Postgres FTS with unaccent, facets, result pages, sitemap.
5. **Accounts** — allauth, roles, download permissions.
6. **User contributions** — upload flow, moderation queue, reports, takedown process, ToS. This is the step that carries the legal risk; do it after everything else works.
7. **Monetisation** — CMP and consent gate first, then ad slots.

Steps 1–4 give you a genuinely publishable product with no user-generated-content risk at all. That's a good place to validate demand before taking on step 6.
