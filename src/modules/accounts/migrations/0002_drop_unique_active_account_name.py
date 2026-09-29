from django.db import migrations


class Migration(migrations.Migration):
    """
    Allow multiple active Accounts to share the same name.

    The database carried a partial unique index on
    lower(trim(account_name)) for non-deleted accounts. It was created
    outside of Django migrations, so it is not part of any model state;
    it is dropped with raw SQL. IF EXISTS keeps this safe on databases
    that never had the index.

    Reversing this migration recreates the index, which will fail if
    duplicate active account names exist by then.
    """

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS uniq_active_account_normalized_name;",
            reverse_sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uniq_active_account_normalized_name "
                "ON accounts (lower(trim(account_name))) "
                "WHERE NOT is_deleted;"
            ),
        ),
    ]
