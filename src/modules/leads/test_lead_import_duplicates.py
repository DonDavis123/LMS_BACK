from django.test import SimpleTestCase

from src.modules.leads.application.services.lead_import_duplicates import (
    DUPLICATE_EXISTING,
    DUPLICATE_IN_FILE,
    NEW,
    classify,
    describe_duplicate,
    duplicate_problem,
    find_in_file_duplicates,
    in_file_match,
    normalize_email,
    normalize_phone,
)

INDEX = {
    "emails": {"john@x.com": {"id": "L1", "name": "John", "is_converted": False}},
    "phones": {
        "9876543210": {"id": "L2", "name": "Priya Shah", "is_converted": False},
        "1112223333": {"id": "L3", "name": "Old Co", "is_converted": True},
    },
}


class NormalizeTests(SimpleTestCase):
    def test_email(self):
        self.assertEqual(normalize_email("  John@X.com "), "john@x.com")
        self.assertIsNone(normalize_email("   "))
        self.assertIsNone(normalize_email(None))

    def test_phone(self):
        self.assertEqual(normalize_phone("+91 98765-43210"), "9876543210")
        self.assertEqual(normalize_phone("9876543210"), "9876543210")
        self.assertEqual(normalize_phone("0044 20 7946 0958"), "2079460958")
        self.assertEqual(normalize_phone("123-4567"), "1234567")
        self.assertIsNone(normalize_phone("12345"))
        self.assertIsNone(normalize_phone(None))


class InFileTests(SimpleTestCase):
    def rows(self, *cleaned):
        return [{"row_number": i + 2, "cleaned": c} for i, c in enumerate(cleaned)]

    def test_email_duplicates_first_kept(self):
        rows = self.rows({"email": "a@x.com"}, {"email": "A@X.com "}, {"email": "a@x.com"})
        self.assertEqual(find_in_file_duplicates(rows), {3: 2, 4: 2})

    def test_phone_only_among_rows_without_email(self):
        rows = self.rows(
            {"phone": "9876543210"},
            {"mobile_number": "+91 98765 43210"},
            {"email": "z@x.com", "phone": "9876543210"},
        )
        self.assertEqual(find_in_file_duplicates(rows), {3: 2})

    def test_email_row_is_not_matched_to_earlier_no_email_row_by_phone(self):
        rows = self.rows({"phone": "9876543210"}, {"email": "z@x.com", "phone": "9876543210"})
        self.assertEqual(find_in_file_duplicates(rows), {})

    def test_short_numbers_never_match(self):
        rows = self.rows({"phone": "12345"}, {"phone": "12345"})
        self.assertEqual(find_in_file_duplicates(rows), {})


class ClassifyTests(SimpleTestCase):
    def test_email_match(self):
        m = classify({"email": "John@X.com "}, INDEX)
        self.assertEqual((m.kind, m.matched_on, m.lead_id), (DUPLICATE_EXISTING, "email", "L1"))

    def test_phone_match_when_no_email(self):
        m = classify({"mobile_number": "+91 98765-43210"}, INDEX)
        self.assertEqual((m.kind, m.matched_on, m.name), (DUPLICATE_EXISTING, "phone", "Priya Shah"))

    def test_email_row_never_matches_by_phone(self):
        m = classify({"email": "new@x.com", "phone": "9876543210"}, INDEX)
        self.assertEqual(m.kind, NEW)

    def test_name_and_company_never_match(self):
        self.assertEqual(classify({"name": "John", "company_name": "Old Co"}, INDEX).kind, NEW)


class DescribeTests(SimpleTestCase):
    def test_texts(self):
        msg, fix = describe_duplicate(classify({"mobile_number": "9876543210"}, INDEX))
        self.assertEqual(msg, "Same phone number as an existing lead (Priya Shah).")
        for choice in ("Skip", "Update existing", "Create anyway"):
            self.assertIn(choice, fix)
        msg, _ = describe_duplicate(in_file_match(5, {"email": "a@x.com"}))
        self.assertEqual(msg, "Same email as row 5 in this file.")

    def test_converted_uses_converted_locked_code(self):
        m = classify({"phone": "111 222 3333"}, INDEX)
        self.assertEqual(duplicate_problem(m, row_number=4, column="Phone", field="phone", value="x").code, "converted_locked")
