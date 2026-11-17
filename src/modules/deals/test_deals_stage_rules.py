from django.utils import timezone
from rest_framework import status

from src.modules.deals.domain.enums.deal_stage import DEFAULT_PROBABILITY, DealStage
from src.modules.deals.infrastructure.persistence.models import DjangoDealModel
from src.modules.deals.deal_factories import URL, DealApiTestBase
from src.modules.timeline.infrastructure.persistence.models import (
    TimelineEvent,
    TimelineEventTarget,
)


class DealStageRuleTests(DealApiTestBase):
    def setUp(self):
        super().setUp()
        self.deal_id = self.create().data["id"]

    def move(self, stage, **extra):
        return self.client.post(
            f"{URL}{self.deal_id}/move/", {"stage": stage, **extra}, format="json"
        )

    def row(self):
        return DjangoDealModel.objects.get(id=self.deal_id)

    def test_default_probability_table(self):
        self.assertEqual(
            {stage.value: probability for stage, probability in DEFAULT_PROBABILITY.items()},
            {
                "New": 10,
                "Quotation Sent": 40,
                "Negotiation": 70,
                "Won": 100,
                "Lost": 0,
            },
        )

    def test_each_stage_gets_its_default_probability(self):
        for stage in ("Quotation Sent", "Negotiation", "New", "Won"):
            with self.subTest(stage=stage):
                response = self.move(stage)

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                self.assertEqual(response.data["stage"], stage)
                self.assertEqual(
                    response.data["probability"],
                    DEFAULT_PROBABILITY[DealStage(stage)],
                )
                self.assertEqual(self.row().probability, DEFAULT_PROBABILITY[DealStage(stage)])

        response = self.move("Lost", lost_reason="No budget")
        self.assertEqual(response.data["probability"], 0)

    def test_explicit_probability_overrides_the_default(self):
        response = self.move("Negotiation", probability=55)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["probability"], 55)
        self.assertEqual(self.row().probability, 55)

    def test_probability_boundaries_are_accepted(self):
        for value in (0, 100):
            with self.subTest(value=value):
                response = self.move("Quotation Sent", probability=value)

                self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
                self.assertEqual(response.data["probability"], value)

    def test_probability_outside_0_100_is_rejected(self):
        for value in (-1, 101, 1000):
            with self.subTest(value=value):
                response = self.move("Negotiation", probability=value)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("between 0 and 100", response.data["detail"])

        self.assertEqual(self.row().stage, "New")
        self.assertEqual(self.row().probability, 10)

    def test_non_integer_probability_is_rejected(self):
        for value in ("high", 12.5, True):
            with self.subTest(value=value):
                response = self.move("Negotiation", probability=value)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(set(response.data), {"detail"})

    def test_unknown_stage_is_rejected(self):
        response = self.move("Maybe")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stage", response.data["detail"])

    def test_won_sets_closed_at_and_forces_100(self):
        before = timezone.now()

        response = self.move("Won", probability=20)  # explicit value is ignored

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["stage"], "Won")
        self.assertEqual(response.data["probability"], 100)
        self.assertIsNotNone(response.data["closed_at"])
        row = self.row()
        self.assertGreaterEqual(row.closed_at, before)
        self.assertEqual(row.probability, 100)
        self.assertIsNone(row.lost_reason)

    def test_lost_without_reason_is_rejected(self):
        for body in ({}, {"lost_reason": ""}, {"lost_reason": "   "}, {"lost_reason": None}):
            with self.subTest(body=body):
                response = self.move("Lost", **body)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("lost reason", response.data["detail"])

        row = self.row()
        self.assertEqual(row.stage, "New")
        self.assertIsNone(row.closed_at)

    def test_lost_sets_zero_reason_and_closed_at(self):
        response = self.move("Lost", lost_reason="  Chose a competitor ", probability=60)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["probability"], 0)
        self.assertEqual(response.data["lost_reason"], "Chose a competitor")
        self.assertIsNotNone(response.data["closed_at"])
        self.assertEqual(self.row().probability, 0)

    def test_reopening_a_lost_deal_clears_closed_at_and_reason(self):
        self.move("Lost", lost_reason="No budget")

        response = self.move("Negotiation")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["probability"], 70)
        self.assertIsNone(response.data["closed_at"])
        self.assertIsNone(response.data["lost_reason"])
        row = self.row()
        self.assertIsNone(row.closed_at)
        self.assertIsNone(row.lost_reason)

    def test_reopening_a_won_deal_clears_closed_at(self):
        self.move("Won")

        response = self.move("Quotation Sent")

        self.assertEqual(response.data["probability"], 40)
        self.assertIsNone(response.data["closed_at"])

    def test_won_to_lost_requires_a_reason_and_resets_closed_at(self):
        won = self.move("Won").data
        self.assertEqual(self.move("Lost").status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.row().stage, "Won")

        lost = self.move("Lost", lost_reason="Contract cancelled").data

        self.assertEqual(lost["probability"], 0)
        self.assertNotEqual(lost["closed_at"], won["closed_at"])

    def test_moving_to_the_same_closed_stage_keeps_closed_at(self):
        first = self.move("Won").data["closed_at"]

        again = self.move("Won")

        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertEqual(again.data["closed_at"], first)

    def test_moving_to_the_current_open_stage_keeps_an_overridden_probability(self):
        self.move("Negotiation", probability=55)

        response = self.move("Negotiation")

        self.assertEqual(response.data["probability"], 55)

    # -- the same rules apply when the stage is changed through PATCH ----

    def test_patch_stage_applies_the_stage_rules(self):
        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"stage": "Quotation Sent"}, format="json"
        )
        self.assertEqual(response.data["probability"], 40)

        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"stage": "Won"}, format="json"
        )
        self.assertEqual(response.data["probability"], 100)
        self.assertIsNotNone(response.data["closed_at"])

        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"stage": "Lost"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.patch(
            f"{URL}{self.deal_id}/",
            {"stage": "Lost", "lost_reason": "Went silent"},
            format="json",
        )
        self.assertEqual(response.data["probability"], 0)
        self.assertEqual(response.data["lost_reason"], "Went silent")

        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"stage": "New"}, format="json"
        )
        self.assertEqual(response.data["probability"], 10)
        self.assertIsNone(response.data["closed_at"])
        self.assertIsNone(response.data["lost_reason"])

    def test_patch_probability_override_on_an_open_deal(self):
        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"probability": 33}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["probability"], 33)

    def test_patch_cannot_override_the_probability_of_a_closed_deal(self):
        self.move("Won")

        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"probability": 50}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.row().probability, 100)

    def test_patch_lost_reason_only_applies_to_lost_deals(self):
        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"lost_reason": "x"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.move("Lost", lost_reason="Old reason")
        response = self.client.patch(
            f"{URL}{self.deal_id}/", {"lost_reason": "New reason"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["lost_reason"], "New reason")


class DealTimelineTests(DealApiTestBase):
    def event_types(self, deal_id, entity_type="DEAL"):
        events = TimelineEvent.objects.filter(
            company=self.company,
            targets__entity_type=entity_type,
            targets__entity_id=deal_id,
            is_deleted=False,
        ).order_by("created_at", "id")
        return [event.event_type for event in events]

    def events_of(self, deal_id, event_type):
        return list(
            TimelineEvent.objects.filter(
                company=self.company,
                event_type=event_type,
                targets__entity_type="DEAL",
                targets__entity_id=deal_id,
            )
        )

    def test_create_records_deal_created_on_deal_contact_and_account(self):
        deal_id = self.create(contact_id=str(self.contact.id)).data["id"]

        (event,) = self.events_of(deal_id, "DEAL_CREATED")

        self.assertEqual(event.company_id, self.company.id)
        self.assertEqual(event.actor_id, self.superadmin.id)
        self.assertEqual(event.metadata["deal_id"], deal_id)
        targets = set(
            TimelineEventTarget.objects.filter(event=event).values_list(
                "entity_type", "entity_id"
            )
        )
        self.assertEqual(
            {(kind, str(entity_id)) for kind, entity_id in targets},
            {
                ("DEAL", deal_id),
                ("CONTACT", str(self.contact.id)),
                ("ACCOUNT", str(self.account.id)),
            },
        )

    def test_create_without_contact_targets_deal_and_account_only(self):
        deal_id = self.create().data["id"]

        (event,) = self.events_of(deal_id, "DEAL_CREATED")

        kinds = set(
            TimelineEventTarget.objects.filter(event=event).values_list(
                "entity_type", flat=True
            )
        )
        self.assertEqual(kinds, {"DEAL", "ACCOUNT"})

    def test_stage_change_records_from_and_to(self):
        deal_id = self.create().data["id"]

        self.client.post(f"{URL}{deal_id}/move/", {"stage": "Negotiation"}, format="json")

        (event,) = self.events_of(deal_id, "DEAL_STAGE_CHANGED")
        self.assertEqual(event.metadata["from_stage"], "New")
        self.assertEqual(event.metadata["to_stage"], "Negotiation")
        self.assertEqual(self.event_types(deal_id), ["DEAL_CREATED", "DEAL_STAGE_CHANGED"])

    def test_won_records_stage_changed_and_won(self):
        deal_id = self.create().data["id"]

        self.client.post(f"{URL}{deal_id}/move/", {"stage": "Won"}, format="json")

        types = self.event_types(deal_id)
        self.assertCountEqual(types, ["DEAL_CREATED", "DEAL_STAGE_CHANGED", "DEAL_WON"])
        (won,) = self.events_of(deal_id, "DEAL_WON")
        self.assertEqual(won.metadata["amount"], "100000.00")
        (changed,) = self.events_of(deal_id, "DEAL_STAGE_CHANGED")
        self.assertEqual(changed.metadata["to_stage"], "Won")

    def test_lost_records_stage_changed_and_lost(self):
        deal_id = self.create().data["id"]

        self.client.post(
            f"{URL}{deal_id}/move/",
            {"stage": "Lost", "lost_reason": "No budget"},
            format="json",
        )

        self.assertCountEqual(
            self.event_types(deal_id),
            ["DEAL_CREATED", "DEAL_STAGE_CHANGED", "DEAL_LOST"],
        )
        (lost,) = self.events_of(deal_id, "DEAL_LOST")
        self.assertEqual(lost.metadata["lost_reason"], "No budget")

    def test_rejected_move_records_nothing(self):
        deal_id = self.create().data["id"]

        self.client.post(f"{URL}{deal_id}/move/", {"stage": "Lost"}, format="json")

        self.assertEqual(self.event_types(deal_id), ["DEAL_CREATED"])

    def test_patch_records_deal_updated_with_changes(self):
        deal_id = self.create().data["id"]

        self.client.patch(f"{URL}{deal_id}/", {"name": "Renamed", "amount": "5.00"}, format="json")

        (event,) = self.events_of(deal_id, "DEAL_UPDATED")
        self.assertEqual(
            event.metadata["changes"]["name"],
            {"old_value": "Big Deal", "new_value": "Renamed"},
        )
        self.assertEqual(
            event.metadata["changes"]["amount"],
            {"old_value": "100000.00", "new_value": "5.00"},
        )

    def test_patch_without_changes_records_nothing(self):
        deal_id = self.create().data["id"]

        self.client.patch(f"{URL}{deal_id}/", {"name": "Big Deal"}, format="json")

        self.assertEqual(self.event_types(deal_id), ["DEAL_CREATED"])

    def test_patch_stage_records_updated_and_stage_events(self):
        deal_id = self.create().data["id"]

        self.client.patch(f"{URL}{deal_id}/", {"stage": "Won"}, format="json")

        self.assertCountEqual(
            self.event_types(deal_id),
            ["DEAL_CREATED", "DEAL_UPDATED", "DEAL_STAGE_CHANGED", "DEAL_WON"],
        )

    def test_delete_records_deal_deleted(self):
        deal_id = self.create(contact_id=str(self.contact.id)).data["id"]

        self.client.delete(f"{URL}{deal_id}/")

        (event,) = self.events_of(deal_id, "DEAL_DELETED")
        self.assertEqual(event.actor_id, self.superadmin.id)
        self.assertEqual(event.metadata["deal_id"], deal_id)
        kinds = set(
            TimelineEventTarget.objects.filter(event=event).values_list(
                "entity_type", flat=True
            )
        )
        self.assertEqual(kinds, {"DEAL", "CONTACT", "ACCOUNT"})

    def test_deal_timeline_endpoint(self):
        deal_id = self.create().data["id"]
        self.client.post(f"{URL}{deal_id}/move/", {"stage": "Negotiation"}, format="json")

        response = self.client.get(f"/api/timeline/deals/{deal_id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [event["event_type"] for event in response.data],
            ["DEAL_STAGE_CHANGED", "DEAL_CREATED"],  # newest first
        )

    def test_event_is_visible_on_the_account_timeline(self):
        self.create()

        response = self.client.get(f"/api/timeline/accounts/{self.account.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("DEAL_CREATED", [event["event_type"] for event in response.data])

    def test_a_failed_write_leaves_no_event_behind(self):
        deal_id = self.create().data["id"]
        before = TimelineEvent.objects.count()

        self.client.patch(f"{URL}{deal_id}/", {"amount": "-1"}, format="json")

        self.assertEqual(TimelineEvent.objects.count(), before)
