"""Postgres extensions and the Spanish unaccented text search configuration.

Without the unaccent filter, "oposicion" does not match "oposición" — and
users type both constantly. Every to_tsvector/to_tsquery in the project uses
the 'es_unaccent' configuration created here.
"""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations

CREATE_CONFIG = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_ts_config WHERE cfgname = 'es_unaccent'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION es_unaccent (COPY = spanish);
        ALTER TEXT SEARCH CONFIGURATION es_unaccent
            ALTER MAPPING FOR hword, hword_part, word
            WITH unaccent, spanish_stem;
    END IF;
END
$$;
"""

DROP_CONFIG = "DROP TEXT SEARCH CONFIGURATION IF EXISTS es_unaccent;"


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []

    operations = [
        UnaccentExtension(),
        TrigramExtension(),
        migrations.RunSQL(CREATE_CONFIG, DROP_CONFIG),
    ]
