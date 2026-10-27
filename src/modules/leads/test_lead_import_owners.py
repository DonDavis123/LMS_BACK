from uuid import UUID

from django.test import SimpleTestCase

from src.modules.leads.application.services.lead_import_owners import (
    EligibleOwner,
    IneligibleUser,
    OwnerPlan,
    OwnerResolver,
    OwnerResult,
    summarize_assignments,
    validate_plan,
)
from src.modules.leads.application.services.lead_import_validation import RowProblem


def uid(n: int) -> UUID:
    return UUID(int=n)


ME, PRIYA, RAJ, SAM1, SAM2 = (uid(i) for i in range(1, 6))
OWNERS = [
    EligibleOwner(ME, "Me Admin", "me@x.com"),
    EligibleOwner(PRIYA, "Priya Shah", "priya@x.com"),
    EligibleOwner(RAJ, "Raj Kumar", "raj@x.com"),
    EligibleOwner(SAM1, "Sam Lee", "sam1@x.com"),
    EligibleOwner(SAM2, "Sam Lee", "sam2@x.com"),
]
BLOCKED = [IneligibleUser(uid(9), "Tara Exec", "tara@x.com")]


def plan(**kw):
    return OwnerPlan.from_dict(kw)


def resolver(p, cursor=0):
    return OwnerResolver(p, OWNERS, ME, cursor=cursor, ineligible_users=BLOCKED)


def rr(*ids):
    return {"kind": "round_robin", "owner_ids": [str(i) for i in ids]}


class PlanTests(SimpleTestCase):
    def test_defaults_and_round_trip(self):
        p = OwnerPlan.from_dict(None)
        self.assertEqual((p.mode, p.on_unmatched, p.change_owner_on_update), ("me", "use_fallback", False))
        self.assertEqual(p.fallback.kind, "single")
        again = OwnerPlan.from_dict(plan(mode="selected", selected=rr(PRIYA, RAJ)).to_dict())
        self.assertEqual(again.selected.owner_ids, [str(PRIYA), str(RAJ)])

    def test_validate_plan_messages(self):
        self.assertEqual(validate_plan(plan(), OWNERS, False, ME), [])
        self.assertTrue(validate_plan(plan(mode="from_file"), OWNERS, False, ME))
        self.assertTrue(validate_plan(plan(mode="selected"), OWNERS, False, ME))
        self.assertTrue(validate_plan(plan(mode="selected", selected=rr(PRIYA)), OWNERS, False, ME))
        bad = plan(mode="selected", selected={"kind": "single", "owner_id": str(uid(77))})
        self.assertTrue(any("not an active admin" in e for e in validate_plan(bad, OWNERS, False, ME)))
        mapped = plan(mode="from_file", owner_value_mapping={"Tara": str(uid(9))})
        self.assertTrue(validate_plan(mapped, OWNERS, True, ME))
        self.assertTrue(validate_plan(plan(), OWNERS, False, uid(9)))  # current user not eligible


class ResolverTests(SimpleTestCase):
    def test_me(self):
        r = resolver(plan()).resolve(2, "ignored")
        self.assertEqual((r.owner_id, r.source), (ME, "me"))

    def test_selected_single_and_ignores_file_column(self):
        p = plan(mode="selected", selected={"kind": "single", "owner_id": str(RAJ)})
        r = resolver(p).resolve(2, "priya@x.com")
        self.assertEqual((r.owner_id, r.source), (RAJ, "selected"))

    def test_rotation_continues_across_batches(self):
        p = plan(mode="selected", selected=rr(PRIYA, RAJ))
        first = resolver(p)
        batch1 = [first.resolve(n).owner_id for n in (2, 3, 4)]
        second = resolver(p, cursor=first.cursor)  # as restored from job.options
        batch2 = [second.resolve(n).owner_id for n in (5, 6)]
        self.assertEqual(batch1 + batch2, [PRIYA, RAJ, PRIYA, RAJ, PRIYA])
        self.assertEqual(second.cursor, 5)

    def test_from_file_email_name_and_mapped_value(self):
        p = plan(mode="from_file", owner_value_mapping={"the boss": str(RAJ)})
        res = resolver(p)
        self.assertEqual(res.resolve(2, " PRIYA@x.com ").source, "file")
        self.assertEqual(res.resolve(3, "raj  kumar").owner_id, RAJ)
        mapped = res.resolve(4, "The Boss")
        self.assertEqual((mapped.owner_id, mapped.source), (RAJ, "mapped_value"))

    def test_ambiguous_name_warns_and_falls_back(self):
        r = resolver(plan(mode="from_file")).resolve(7, "Sam Lee")
        self.assertEqual((r.owner_id, r.source, r.warning.code), (ME, "fallback", "owner_ambiguous"))
        self.assertIn("Row 7", r.warning.message)
        self.assertIn("Me Admin", r.warning.message)

    def test_unknown_value_fallback_vs_error(self):
        r = resolver(plan(mode="from_file")).resolve(3, "nobody@x.com")
        self.assertEqual((r.source, r.warning.code), ("fallback", "owner_not_found"))
        e = resolver(plan(mode="from_file", on_unmatched="error")).resolve(3, "nobody@x.com")
        self.assertIsInstance(e, RowProblem)
        self.assertEqual(e.code, "owner_not_found")
        self.assertIn("not imported", e.message)

    def test_known_but_ineligible_user(self):
        r = resolver(plan(mode="from_file")).resolve(3, "Tara Exec")
        self.assertEqual(r.warning.code, "owner_ineligible")

    def test_blank_cell_uses_fallback_silently(self):
        r = resolver(plan(mode="from_file")).resolve(3, "   ")
        self.assertEqual((r.source, r.warning), ("fallback", None))

    def test_from_file_rotation_fallback_advances_only_for_fallback_rows(self):
        p = plan(mode="from_file", fallback=rr(PRIYA, RAJ))
        res = resolver(p)
        got = [
            res.resolve(2, "").owner_id,                  # fallback -> Priya
            res.resolve(3, "sam1@x.com").owner_id,        # matched, no advance
            res.resolve(4, "who?").owner_id,              # fallback -> Raj
            res.resolve(5, None).owner_id,                # fallback -> Priya
        ]
        self.assertEqual(got, [PRIYA, SAM1, RAJ, PRIYA])
        self.assertEqual(res.cursor, 3)

    def test_error_rows_do_not_advance_rotation(self):
        p = plan(mode="from_file", fallback=rr(PRIYA, RAJ), on_unmatched="error")
        res = resolver(p)
        res.resolve(2, "nobody")
        self.assertEqual(res.cursor, 0)

    def test_owner_who_became_ineligible_is_never_assigned(self):
        p = plan(mode="selected", selected={"kind": "single", "owner_id": str(uid(42))})
        self.assertIsInstance(resolver(p).resolve(2), RowProblem)


class SummaryTests(SimpleTestCase):
    def test_counts_and_unmatched_values(self):
        p = plan(mode="from_file", fallback=rr(PRIYA, RAJ))
        rows = [
            {"row_number": 2, "cleaned": {"owner": "sam1@x.com"}},
            {"row_number": 3, "cleaned": {"owner": "Jon"}},
            {"row_number": 4, "cleaned": {"owner": "jon"}},
            {"row_number": 5, "cleaned": {}},
        ]
        s = summarize_assignments(p, OWNERS, ME, rows)
        self.assertEqual((s["total"], s["rejected"]), (4, 0))
        self.assertEqual(sum(o["total"] for o in s["per_owner"]), 4)
        jon = s["unmatched_values"][0]
        self.assertEqual((jon["value"], jon["count"], jon["code"]), ("Jon", 2, "owner_not_found"))
        self.assertEqual(sum(f["count"] for f in jon["fell_back_to"]), 2)
