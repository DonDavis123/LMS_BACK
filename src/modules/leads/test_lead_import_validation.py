from types import SimpleNamespace

from django.test import SimpleTestCase

from src.modules.leads.application.services.lead_import_validation import (
    PicklistSnapshot,
    build_problem,
    error_groups,
    validate_row,
)

SOURCES = [
    "None", "Advertisement", "Cold Call", "Employee Referral", "External Referral",
    "Online Store", "Partner", "Public Relations", "Sales Email Alias",
    "Seminar Partner", "Internal Seminar", "Trade Show",
]


def snapshot():
    return PicklistSnapshot(
        options={
            "lead_source": [(v, True) for v in SOURCES] + [("Old Fair", False)],
            "lead_status": [("None", True), ("Contacted", True)],
            "industry": [("None", True)],
            "rating": [("None", True), ("Active", True)],
        }
    )


COLUMNS = {
    "name": "Full Name", "email": "Email", "lead_source": "Lead Source",
    "number_of_employees": "Employees", "website": "Website",
}


class ValidateRowTests(SimpleTestCase):
    def test_valid_row_normalises_picklists_and_defaults_blanks(self):
        payload, problems = validate_row(
            2,
            {"name": "Asha", "email": "a@b.com", "lead_source": "cold   call",
             "lead_status": "contacted"},
            COLUMNS,
            snapshot(),
        )
        self.assertEqual(problems, [])
        self.assertEqual(payload["lead_source"], "Cold Call")
        self.assertEqual(payload["lead_status"], "Contacted")
        self.assertEqual(payload["industry"], "None")
        self.assertEqual(payload["rating"], "None")

    def test_collects_every_problem_in_the_row(self):
        payload, problems = validate_row(
            5,
            {"name": None, "email": "john@@gmail.com", "lead_source": "Linkdin",
             "number_of_employees": "-4", "website": "not a url"},
            COLUMNS,
            snapshot(),
        )
        self.assertIsNone(payload)
        codes = {p.field: p.code for p in problems}
        self.assertEqual(codes, {
            "name": "required", "email": "invalid_email",
            "lead_source": "unknown_option",
            "number_of_employees": "negative_number", "website": "invalid_url",
        })
        for problem in problems:
            self.assertIn("Row 5", problem.message)

    def test_hidden_option_and_long_value(self):
        _, problems = validate_row(
            3, {"name": "x" * 300, "lead_source": "old fair"}, COLUMNS, snapshot()
        )
        by_field = {p.field: p for p in problems}
        self.assertEqual(by_field["name"].code, "too_long")
        self.assertIn("no longer available", by_field["lead_source"].message)
        self.assertLessEqual(len(by_field["name"].message), 200)

    def test_unmapped_name_and_huge_number(self):
        _, problems = validate_row(
            4, {"number_of_employees": 10 ** 12}, {"number_of_employees": "Staff"}, snapshot()
        )
        by_field = {p.field: p for p in problems}
        self.assertIn("no column in your file is mapped", by_field["name"].message)
        self.assertEqual(by_field["number_of_employees"].code, "invalid_number")

    def test_never_raises(self):
        payload, problems = validate_row(9, {"name": object()}, None, snapshot())
        self.assertIsNone(payload)
        self.assertTrue(problems)

    def test_options_hint_truncates(self):
        self.assertTrue(snapshot().options_hint("lead_source").endswith(", ..."))

    def test_error_groups_sorted_and_accept_dicts(self):
        a = build_problem("duplicate", row_number=1, column="Email", field="email", value="a")
        b = build_problem("required", row_number=2, column="Name", field="name", value=None)
        groups = error_groups([a, b.to_dict(), b.to_dict()])
        self.assertEqual([g["code"] for g in groups], ["required", "duplicate"])
        self.assertEqual(groups[0]["count"], 2)
