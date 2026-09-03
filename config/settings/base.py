"""Base settings shared by every environment.

All configuration comes from environment variables (django-environ). The app
writes nothing to local disk: sessions live in Redis, uploads in S3-compatible
object storage, static files are baked into the image and served by whitenoise.
"""

from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# .env is read if present (local development outside Docker); in containers the
# environment is injected by compose and the file simply does not exist.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
# The container healthcheck curls http://localhost:8000/healthz, so loopback
# must always be an allowed host regardless of the public domain in .env.
# Without this, /healthz 400s with DisallowedHost on every healthcheck tick.
ALLOWED_HOSTS += ["localhost", "127.0.0.1", "[::1]"]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Public origin used to build absolute URLs (canonical, sitemaps, JSON-LD).
SITE_URL = env("SITE_URL", default="http://localhost:8000")
SITE_NAME = "OposDocs"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "django.contrib.humanize",
    # Third party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # Local apps
    "accounts",
    "core",
    "oposiciones",
    "documents",
    "posts",
    "search",
    "sources",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.MarkdownNegotiationMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database and cache ----------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# Stateless app: sessions live in the cache, never on disk.
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth ------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# django-allauth: email/password with mandatory verification, plus Google.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
# Built-in rate limits (login failures, etc.) are enabled by default; keep them.
# allauth is mounted at /cuentas/, so Django's default /accounts/login/ would
# 404 every @login_required redirect.
LOGIN_URL = "/cuentas/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_CLIENT_ID", default=""),
            "secret": env("GOOGLE_CLIENT_SECRET", default=""),
        },
        "SCOPE": ["profile", "email"],
    }
}

# --- Internationalisation --------------------------------------------------

LANGUAGE_CODE = env("LANGUAGE_CODE", default="es-es")
TIME_ZONE = env("TIME_ZONE", default="Europe/Madrid")
USE_I18N = True
USE_TZ = True

# --- Static files (whitenoise, baked into the image) -----------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "access_key": env("AWS_ACCESS_KEY_ID", default=""),
            "secret_key": env("AWS_SECRET_ACCESS_KEY", default=""),
            "bucket_name": env("AWS_STORAGE_BUCKET_NAME", default="opos-documents"),
            "endpoint_url": env("AWS_S3_ENDPOINT_URL", default=""),
            "region_name": env("AWS_S3_REGION_NAME", default="garage"),
            "custom_domain": env("AWS_S3_CUSTOM_DOMAIN", default="") or None,
            "file_overwrite": True,  # content-addressed keys make overwrite idempotent
            "querystring_expire": env.int("PRESIGNED_URL_EXPIRY", default=900),
        },
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

PRESIGNED_URL_EXPIRY = env.int("PRESIGNED_URL_EXPIRY", default=900)
# Browser-facing S3 endpoint when it differs from the internal one (local
# dev: containers reach minio:9000, the browser reaches localhost:9000).
AWS_S3_PUBLIC_ENDPOINT_URL = env("AWS_S3_PUBLIC_ENDPOINT_URL", default="")

# --- Celery ----------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_TASK_DEFAULT_QUEUE = "default"
# OCR is CPU-hungry: separate low-priority queue with capped concurrency so a
# single 800-page scan cannot starve everything else (worker started with
# dedicated -Q ocr -c settings in compose).
CELERY_TASK_ROUTES = {
    "documents.tasks.ocr_document": {"queue": "ocr"},
    # Harvesting gets its own queue with a single worker at concurrency 1, so
    # two harvest tasks can never run at the same time however they are
    # enqueued (see sources/tasks.py for the four-part throttle).
    "sources.tasks.*": {"queue": "harvest"},
}
CELERY_TASK_TIME_LIMIT = 60 * 30
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 25

# --- Email (external provider; never send from the server directly) --------

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# --- Document pipeline -----------------------------------------------------

CLAMAV_HOST = env("CLAMAV_HOST", default="")
CLAMAV_PORT = env.int("CLAMAV_PORT", default=3310)
OCR_LANGUAGE = env("OCR_LANGUAGE", default="spa")
OCR_MAX_PAGES = env.int("OCR_MAX_PAGES", default=300)

# --- Search ----------------------------------------------------------------

SEARCH_BACKEND = env("SEARCH_BACKEND", default="postgres")

# --- Admin bootstrap (accounts/management/commands/create_admin.py) --------

DJANGO_ADMIN_USERNAME = env("DJANGO_ADMIN_USERNAME", default="admin")
DJANGO_ADMIN_EMAIL = env("DJANGO_ADMIN_EMAIL", default="admin@example.com")
# Empty means "use the development placeholder", which create_admin refuses
# to do when DEBUG is off. Set this in the server .env to bootstrap an admin.
DJANGO_ADMIN_PASSWORD = env("DJANGO_ADMIN_PASSWORD", default="")

# --- Official source harvesting (sources app) ------------------------------

# Identify ourselves to public services; they are entitled to know who is
# calling and how to reach us if we misbehave. Derived from SITE_URL rather
# than hardcoded, so the bot can never advertise a domain we do not serve.
HARVEST_USER_AGENT = env(
    "HARVEST_USER_AGENT",
    default=f"OposdocsBot/1.0 (+{SITE_URL.rstrip('/')}/robots.txt)",
)
# Seconds between two downloads inside one day's harvest.
HARVEST_DOWNLOAD_DELAY = env.float("HARVEST_DOWNLOAD_DELAY", default=1.5)
# How many recent days the nightly job re-checks. Anything larger than the
# longest outage you expect makes missed nights self-healing.
HARVEST_CATCHUP_DAYS = env.int("HARVEST_CATCHUP_DAYS", default=7)
# Oldest day the backfill walks back to.
HARVEST_BACKFILL_START = env("HARVEST_BACKFILL_START", default="2020-01-01")
# Pause between backfill days. The backfill enqueues the next day only after
# the current one finishes, so this is the whole pacing knob: 120s over ~2,400
# days is roughly three days of wall clock at a load the server will not feel.
HARVEST_BACKFILL_COUNTDOWN = env.int("HARVEST_BACKFILL_COUNTDOWN", default=120)
# Lock expiry, so a worker killed mid-harvest cannot block harvesting forever.
HARVEST_LOCK_TIMEOUT = env.int("HARVEST_LOCK_TIMEOUT", default=60 * 60 * 6)
# Refuse absurdly large annexes rather than OOM a small worker.
HARVEST_MAX_PDF_BYTES = env.int("HARVEST_MAX_PDF_BYTES", default=60 * 1024 * 1024)

# Nightly at 06:40 Europe/Madrid: the BOE is published early morning, and by
# then the previous day is settled. Only ever one entry, because harvest_recent
# walks the whole catch-up window itself.
CELERY_BEAT_SCHEDULE = {
    "harvest-boe-nightly": {
        "task": "sources.tasks.harvest_recent",
        "schedule": crontab(hour=6, minute=40),
        "options": {"queue": "harvest", "expires": 60 * 60 * 12},
    },
}

# --- Crawlers and indexing -------------------------------------------------

# False on staging: robots.txt then disallows everything.
ALLOW_INDEXING = env.bool("ALLOW_INDEXING", default=False)

# --- Advertising -----------------------------------------------------------

ADSENSE_CLIENT_ID = env("ADSENSE_CLIENT_ID", default="")
ADS_ENABLED = env.bool("ADS_ENABLED", default=False)

# --- Logging ---------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
