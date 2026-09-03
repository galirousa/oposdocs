import pytest


@pytest.fixture(autouse=True)
def _eager_celery(settings):
    """Run pipeline tasks synchronously in tests."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(autouse=True)
def _local_memory_cache(settings):
    """Tests must not require Redis."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    settings.SESSION_ENGINE = "django.contrib.sessions.backends.db"


@pytest.fixture(autouse=True)
def _indexing_on(settings):
    settings.ALLOW_INDEXING = True
    settings.DEBUG = False


@pytest.fixture(autouse=True)
def _memory_storage(settings):
    """Tests must not require MinIO/Garage either."""
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    }
