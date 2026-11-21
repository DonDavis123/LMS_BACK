from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import migrations
from django.db.models.functions import Upper


class Migration(migrations.Migration):
    """
    Trigram indexes so "contains" search and filters do not scan the table.

    Django's icontains / istartswith / iendswith query UPPER(column), so the
    indexes are on UPPER(column) with gin_trgm_ops.
    """

    dependencies = [
        ("leads", "0012_lead_list_indexes"),
    ]

    operations = [
        # Idempotent, and never dropped on reverse: the extension may be
        # shared with other apps / Supabase itself.
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=GinIndex(
                OpClass(Upper("name"), name="gin_trgm_ops"),
                name="leads_name_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=GinIndex(
                OpClass(Upper("email"), name="gin_trgm_ops"),
                name="leads_email_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangoleadmodel",
            index=GinIndex(
                OpClass(Upper("company_name"), name="gin_trgm_ops"),
                name="leads_company_trgm_idx",
            ),
        ),
    ]
