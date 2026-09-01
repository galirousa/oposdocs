"""Development settings: debug toolbar, relaxed hosts, console email."""

import sys

from .base import *
from .base import INSTALLED_APPS, MIDDLEWARE, env

DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "web", "testserver"])

TESTING = "pytest" in sys.modules

INSTALLED_APPS += ["django_extensions"]

if not TESTING:
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(
        MIDDLEWARE.index("django.middleware.common.CommonMiddleware"),
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
    # Inside Docker the client IP is the compose network gateway, so
    # INTERNAL_IPS cannot be enumerated reliably; show whenever DEBUG is on.
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# Plain static storage in dev: no manifest, no collectstatic needed.
from .base import STORAGES  # noqa: E402

STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}
