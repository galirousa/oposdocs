"""Point the django.contrib.sites record (used by sitemaps and allauth) at
SITE_URL. Runs at migrate time in every environment, so each deploy gets its
own domain."""

from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations


def set_site_domain(apps, schema_editor) -> None:
    site_model = apps.get_model("sites", "Site")
    parsed = urlparse(settings.SITE_URL)
    domain = parsed.netloc or "localhost:8000"
    site_model.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": domain, "name": settings.SITE_NAME},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_initial"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(set_site_domain, migrations.RunPython.noop)]
