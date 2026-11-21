from django.contrib.postgres.indexes import GinIndex
from django.db import migrations
from django.db.models.functions import Upper
from django.db.models.indexes import OpClass


class Migration(migrations.Migration):
    """
    Trigram indexes so "contains" search and filters do not scan the table.

    Django's icontains / istartswith / iendswith query UPPER(column), so the
    indexes are on UPPER(column) with gin_trgm_ops.
    """

    dependencies = [
        ("deals", "0003_deal_relation_indexes"),
    ]

    operations = [
        # Idempotent, and never dropped on reverse: the extension may be
        # shared with other apps / Supabase itself.
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="djangodealmodel",
            index=GinIndex(
                OpClass(Upper("name"), name="gin_trgm_ops"),
                name="deals_name_trgm_idx",
            ),
        ),
    ]
