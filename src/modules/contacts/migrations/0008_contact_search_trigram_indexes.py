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
        ("contacts", "0007_contact_list_indexes"),
    ]

    operations = [
        # Idempotent, and never dropped on reverse: the extension may be
        # shared with other apps / Supabase itself.
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddIndex(
            model_name="djangocontactmodel",
            index=GinIndex(
                OpClass(Upper("name"), name="gin_trgm_ops"),
                name="contacts_name_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangocontactmodel",
            index=GinIndex(
                OpClass(Upper("email"), name="gin_trgm_ops"),
                name="contacts_email_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="djangocontactmodel",
            index=GinIndex(
                OpClass(Upper("secondary_email"), name="gin_trgm_ops"),
                name="contacts_sec_email_trgm_idx",
            ),
        ),
    ]
