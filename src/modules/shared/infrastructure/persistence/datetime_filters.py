from datetime import date, datetime, time, timedelta

from django.utils import timezone


def apply_datetime_filter(queryset, db_field, operator, value, field):
    """
    Filters a DateTimeField by calendar day or by exact instant.

    Date-only values ("YYYY-MM-DD") are treated as whole calendar days in the
    project's configured time zone (settings.TIME_ZONE); full ISO datetimes
    are treated as exact instants. Ranges are inclusive of both ends, so
    "on/before" and "between" include every record on the last day. That is
    what makes a "from today to today" range return today's records.
    """
    if operator == "between":
        if not isinstance(value, dict) or "from" not in value or "to" not in value:
            raise ValueError(f"Value for '{field}' must contain 'from' and 'to'.")
        start, _ = _parse_datetime(value["from"], field)
        end, end_is_day = _parse_datetime(value["to"], field)
        if end_is_day:
            end = _next_day_start(end)
        if start > end or (end_is_day and start == end):
            raise ValueError(f"'from' must not be after 'to' for '{field}'.")
        upper = f"{db_field}__lt" if end_is_day else f"{db_field}__lte"
        return queryset.filter(**{f"{db_field}__gte": start, upper: end})

    parsed, is_day = _parse_datetime(value, field)
    if operator == "equals":
        if is_day:
            return queryset.filter(
                **{
                    f"{db_field}__gte": parsed,
                    f"{db_field}__lt": _next_day_start(parsed),
                }
            )
        return queryset.filter(**{db_field: parsed})
    if operator == "after":
        return queryset.filter(**{f"{db_field}__gte": parsed})
    if operator == "before":
        if is_day:
            return queryset.filter(**{f"{db_field}__lt": _next_day_start(parsed)})
        return queryset.filter(**{f"{db_field}__lte": parsed})
    raise ValueError(
        f"Operator '{operator}' is not supported for date/datetime field '{field}'."
    )


def _next_day_start(day_start: datetime) -> datetime:
    next_day = day_start.astimezone(timezone.get_current_timezone()).date() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(next_day, time.min))


def _parse_datetime(value, field) -> tuple[datetime, bool]:
    """Returns (timezone-aware datetime, is_date_only)."""
    if not isinstance(value, str):
        raise ValueError(f"Value for '{field}' must be an ISO date/datetime string.")
    try:
        day = date.fromisoformat(value)
    except ValueError:
        pass
    else:
        return timezone.make_aware(datetime.combine(day, time.min)), True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Invalid date/datetime value for '{field}'.")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed, False
