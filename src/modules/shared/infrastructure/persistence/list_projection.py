def list_columns(model, *related_columns: str) -> tuple[str, ...]:
    """
    Column names for ``queryset.only()`` on a list query.

    Returns every column of ``model`` plus the given related columns
    (e.g. ``"owner__name"``). Use it with ``select_related`` when the list
    returns the whole row but only needs a few columns of each joined table,
    so the joins stop pulling whole user / account / contact rows.

    Related columns must belong to a relation that is also named in
    ``select_related`` (Django joins it and loads only those columns).
    """
    own = tuple(field.name for field in model._meta.concrete_fields)
    return own + tuple(related_columns)
