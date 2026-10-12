from uuid import UUID

from django.db.models import Count
from django.db.models.functions import Lower

from .models import User


def find_duplicate_emails() -> dict[str, list[tuple[UUID, str]]]:
    """Emails that collide when compared case-insensitively.

    Maps each lower-cased email to the ``(user id, stored email)`` pairs that
    share it. Soft-deleted users are included because the unique constraints
    apply to every row.
    """
    rows = (
        User.objects.annotate(email_lower=Lower("email"))
        .values("email_lower")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
        .order_by("email_lower")
    )
    duplicated = [row["email_lower"] for row in rows]
    if not duplicated:
        return {}

    users = (
        User.objects.annotate(email_lower=Lower("email"))
        .filter(email_lower__in=duplicated)
        .order_by("email_lower", "created_at", "id")
        .values_list("email_lower", "id", "email")
    )

    result: dict[str, list[tuple[UUID, str]]] = {}
    for email_lower, user_id, email in users:
        result.setdefault(email_lower, []).append((user_id, email))

    return result
