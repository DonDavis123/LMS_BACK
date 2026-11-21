from django.db import connection
from django.test import TestCase

EXPECTED = {
    "leads_name_trgm_idx",
    "leads_email_trgm_idx",
    "leads_company_trgm_idx",
    "contacts_name_trgm_idx",
    "contacts_email_trgm_idx",
    "contacts_sec_email_trgm_idx",
    "accounts_name_trgm_idx",
    "accounts_website_trgm_idx",
    "accounts_phone_trgm_idx",
    "deals_name_trgm_idx",
}


class TrigramIndexTests(TestCase):
    """The search indexes exist and are trigram GIN indexes on UPPER(column)."""

    def test_trigram_indexes_are_created(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname, indexdef FROM pg_indexes WHERE indexname = ANY(%s)",
                [sorted(EXPECTED)],
            )
            found = dict(cursor.fetchall())

        self.assertEqual(set(found), EXPECTED)
        for name, definition in found.items():
            self.assertIn("gin", definition.lower(), name)
            self.assertIn("gin_trgm_ops", definition, name)
            self.assertIn("upper(", definition.lower(), name)
