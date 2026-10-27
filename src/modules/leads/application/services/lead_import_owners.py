"""Owner assignment for lead import.

Three modes, chosen once per import:
  - ``me`` (default): the user running the import owns every lead.
  - ``from_file``: each row's owner cell is matched to an eligible web user
    (``owner_value_mapping`` first, then email, then exact full name). A
    blank cell, or a value that is not an eligible web user, takes the
    FALLBACK (one owner, or several in rotation).
  - ``selected``: one owner, or a group in rotation, for every lead. The
    file's owner column is ignored.

Eligible owner = active, non-deleted ADMIN or SUPERADMIN of the caller's
company: the same rule as ``CreateLeadUseCase`` (an owner must exist, be
active, and have role ADMIN or SUPERADMIN).

The owners list for the frontend picker already exists: ``GET /lead-owners/``
(users module, ``GetLeadOwnersView``). It returns exactly the eligible users.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from uuid import UUID

from src.modules.users.domain.entities.role import UserRole

from .lead_import_validation import (
    CODE_OWNER_AMBIGUOUS,
    CODE_OWNER_INELIGIBLE,
    CODE_OWNER_NOT_FOUND,
    RowProblem,
)

MODE_ME = "me"
MODE_FROM_FILE = "from_file"
MODE_SELECTED = "selected"
MODES = (MODE_ME, MODE_FROM_FILE, MODE_SELECTED)

KIND_SINGLE = "single"
KIND_ROUND_ROBIN = "round_robin"
KINDS = (KIND_SINGLE, KIND_ROUND_ROBIN)

ON_UNMATCHED_FALLBACK = "use_fallback"
ON_UNMATCHED_ERROR = "error"
ON_UNMATCHED_CHOICES = (ON_UNMATCHED_FALLBACK, ON_UNMATCHED_ERROR)

SOURCE_ME = "me"
SOURCE_FILE = "file"
SOURCE_MAPPED_VALUE = "mapped_value"
SOURCE_FALLBACK = "fallback"
SOURCE_SELECTED = "selected"
SOURCES = (SOURCE_ME, SOURCE_FILE, SOURCE_MAPPED_VALUE, SOURCE_FALLBACK, SOURCE_SELECTED)

MIN_ROTATION_OWNERS = 2
MAX_VALUE_MAPPINGS = 500
MAX_SHOWN_VALUE = 60

_ELIGIBLE_ROLES = {UserRole.ADMIN.value, UserRole.SUPERADMIN.value}

DEFAULT_OWNER_COLUMN = "Owner (email or full name)"
OWNER_FIELD = "owner"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _norm_id(value) -> str | None:
    """A UUID as lower-case text; anything else is kept (trimmed) so that
    validate_plan can report it. Blank -> None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return str(UUID(text))
    except ValueError:
        return text


def _norm_text(value) -> str:
    """Trimmed, single-spaced, case-insensitive form used for matching."""
    return " ".join(str(value).split()).casefold() if value is not None else ""


def _shown(value) -> str:
    text = " ".join(str(value).split()) if value is not None else ""
    if len(text) > MAX_SHOWN_VALUE:
        return text[: MAX_SHOWN_VALUE - 3] + "..."
    return text


def _unique(values) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value is not None and value not in seen:
            seen.append(value)
    return seen


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@dataclass
class OwnerChoice:
    """One owner, or several in rotation."""

    kind: str = KIND_SINGLE
    owner_id: str | None = None
    owner_ids: list[str] = dataclass_field(default_factory=list)

    @classmethod
    def from_dict(cls, data) -> "OwnerChoice":
        if not isinstance(data, dict):
            return cls()
        raw_ids = data.get("owner_ids")
        ids = _unique(_norm_id(v) for v in raw_ids) if isinstance(raw_ids, (list, tuple)) else []
        kind = data.get("kind")
        return cls(
            kind=str(kind).strip().lower() if isinstance(kind, str) and kind.strip() else KIND_SINGLE,
            owner_id=_norm_id(data.get("owner_id")),
            owner_ids=ids,
        )

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "owner_id": self.owner_id,
            "owner_ids": list(self.owner_ids),
        }

    def all_ids(self) -> list[str]:
        return _unique([self.owner_id, *self.owner_ids])

    def rotation_ids(self) -> list[str]:
        return list(self.owner_ids)


@dataclass
class OwnerPlan:
    mode: str = MODE_ME
    # Used by from_file. ``single`` with no owner means the current user.
    fallback: OwnerChoice = dataclass_field(default_factory=OwnerChoice)
    # Required for mode "selected".
    selected: OwnerChoice = dataclass_field(default_factory=OwnerChoice)
    on_unmatched: str = ON_UNMATCHED_FALLBACK
    # {raw file value: user id}; lets the user map a file value to a user.
    owner_value_mapping: dict[str, str] = dataclass_field(default_factory=dict)
    change_owner_on_update: bool = False

    @classmethod
    def from_dict(cls, data) -> "OwnerPlan":
        """Tolerant parse; never raises. Odd values are kept as they are so
        ``validate_plan`` can explain them to the user."""
        if not isinstance(data, dict):
            return cls()

        mode = data.get("mode")
        on_unmatched = data.get("on_unmatched")
        raw_mapping = data.get("owner_value_mapping")
        mapping: dict[str, str] = {}
        if isinstance(raw_mapping, dict):
            for key, value in raw_mapping.items():
                if isinstance(key, str):
                    mapping[key] = _norm_id(value) or ""

        return cls(
            mode=str(mode).strip().lower() if isinstance(mode, str) and mode.strip() else MODE_ME,
            fallback=OwnerChoice.from_dict(data.get("fallback")),
            selected=OwnerChoice.from_dict(data.get("selected")),
            on_unmatched=(
                str(on_unmatched).strip().lower()
                if isinstance(on_unmatched, str) and on_unmatched.strip()
                else ON_UNMATCHED_FALLBACK
            ),
            owner_value_mapping=mapping,
            change_owner_on_update=data.get("change_owner_on_update") is True,
        )

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "fallback": self.fallback.to_dict(),
            "selected": self.selected.to_dict(),
            "on_unmatched": self.on_unmatched,
            "owner_value_mapping": dict(self.owner_value_mapping),
            "change_owner_on_update": self.change_owner_on_update,
        }


# ---------------------------------------------------------------------------
# Eligible owners
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EligibleOwner:
    id: UUID
    name: str
    email: str
    role: str = ""


@dataclass(frozen=True)
class IneligibleUser:
    """An active company user who cannot own leads (e.g. a sales executive).
    Only used to give a precise warning when a file value names such a user."""

    id: UUID
    name: str
    email: str


def _role_text(user) -> str:
    role = getattr(user, "role", None)
    return str(getattr(role, "value", role))


def load_eligible_owners(tenant_context, user_repository) -> list[EligibleOwner]:
    """Active ADMIN / SUPERADMIN users of the caller's company.

    ``user_repository`` is the company-scoped repository built from the same
    tenant context; the company is checked again here. One query: call it once
    per request or batch, never per row.
    """
    owners = []
    for user in user_repository.get_lead_owners():
        if not user.is_active or user.is_deleted:
            continue
        if _role_text(user) not in _ELIGIBLE_ROLES:
            continue
        if user.company_id is not None and user.company_id != tenant_context.company_id:
            continue
        owners.append(
            EligibleOwner(id=user.id, name=user.name, email=user.email, role=_role_text(user))
        )
    return owners


def load_ineligible_users(
    tenant_context, user_repository, eligible_owners
) -> list[IneligibleUser]:
    """Active company users who are NOT eligible owners (one query). Optional:
    without it, such values are reported as "not found" instead of "cannot
    own leads"."""
    eligible_ids = {owner.id for owner in eligible_owners}
    return [
        IneligibleUser(id=user.id, name=user.name, email=user.email)
        for user in user_repository.get_assignable_users()
        if user.id not in eligible_ids
        and (user.company_id is None or user.company_id == tenant_context.company_id)
    ]


# ---------------------------------------------------------------------------
# Plan validation
# ---------------------------------------------------------------------------

def validate_plan(
    plan: OwnerPlan,
    eligible_owners,
    owner_column_mapped: bool,
    current_user_id,
) -> list[str]:
    """Plain-English problems with the plan; an empty list means it is usable."""
    errors: list[str] = []
    eligible_ids = {str(owner.id) for owner in eligible_owners}
    current_id = str(current_user_id) if current_user_id is not None else None

    if plan.mode not in MODES:
        errors.append(
            "Owner assignment must be one of: me, from_file or selected. "
            "Pick one of the three options."
        )
    if plan.on_unmatched not in ON_UNMATCHED_CHOICES:
        errors.append(
            "'When an owner is not found' must be either use_fallback or error. "
            "Pick one of the two options."
        )
    for label, choice in (("selected", plan.selected), ("fallback", plan.fallback)):
        if choice.kind not in KINDS:
            errors.append(
                f"The {label} owners must be a single owner or a rotation. "
                "Choose one of the two."
            )

    uses_current_user = plan.mode == MODE_ME or (
        plan.mode == MODE_FROM_FILE
        and plan.fallback.kind == KIND_SINGLE
        and plan.fallback.owner_id is None
    )

    if plan.mode == MODE_FROM_FILE and not owner_column_mapped:
        errors.append(
            "Owner assignment 'from file' needs a file column mapped to the Owner "
            "field. Map a column in the mapping step, or choose 'me' or 'selected owners'."
        )

    if plan.mode == MODE_SELECTED:
        errors.extend(_choice_errors("selected owners", plan.selected, required=True))
    if plan.mode == MODE_FROM_FILE:
        errors.extend(_choice_errors("fallback owners", plan.fallback, required=False))

    # Unknown or ineligible ids anywhere in the plan.
    for label, choice in (("selected owners", plan.selected), ("fallback owners", plan.fallback)):
        for owner_id in choice.all_ids():
            if owner_id not in eligible_ids:
                errors.append(
                    f"The {label} include a user ({owner_id}) who is not an active "
                    "admin or superadmin of your company. Remove them and choose "
                    "someone else."
                )

    if len(plan.owner_value_mapping) > MAX_VALUE_MAPPINGS:
        errors.append(
            f"You mapped more than {MAX_VALUE_MAPPINGS} owner values. Map fewer "
            "values and let the rest use the fallback owner."
        )
    for raw_value, user_id in plan.owner_value_mapping.items():
        if not _norm_text(raw_value):
            errors.append("An owner value in the mapping is blank. Remove that entry.")
        elif user_id not in eligible_ids:
            errors.append(
                f"The owner value '{_shown(raw_value)}' is mapped to a user who is not "
                "an active admin or superadmin of your company. Pick another user."
            )

    if uses_current_user and (current_id is None or current_id not in eligible_ids):
        errors.append(
            "You are not an active admin or superadmin, so you cannot own imported "
            "leads. Choose other owners."
        )

    return _unique(errors)


def _choice_errors(label: str, choice: OwnerChoice, required: bool) -> list[str]:
    if choice.kind == KIND_ROUND_ROBIN:
        if len(choice.owner_ids) < MIN_ROTATION_OWNERS:
            return [
                f"A rotation needs at least {MIN_ROTATION_OWNERS} {label}. Select two "
                "or more, or choose a single owner instead."
            ]
    elif choice.kind == KIND_SINGLE and required and choice.owner_id is None:
        return [f"Choose the owner who should receive every lead (no {label} selected)."]
    return []


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OwnerResult:
    owner_id: UUID
    source: str  # "me" | "file" | "mapped_value" | "fallback" | "selected"
    owner_name: str = ""
    warning: RowProblem | None = None


def _owner_problem(
    code, *, row_number, column, value, assigned_name, rejected
) -> RowProblem:
    subject = f"{column} '{_shown(value)}'"
    if code == CODE_OWNER_AMBIGUOUS:
        reason = f"{subject} matches more than one user"
        fix = "Use the person's email address in your file so they can be told apart."
    elif code == CODE_OWNER_INELIGIBLE:
        reason = f"{subject} is a user who cannot own leads (only active admins and superadmins can)"
        fix = "Use an admin or superadmin, or map this value to one."
    else:
        reason = f"{subject} does not match any admin or superadmin in your company"
        fix = (
            "Correct the cell in your file (use the person's email), or map this "
            "value to a user."
        )
    if rejected:
        message = f"Row {row_number}: {reason}, so this row was not imported."
        fix += " Or let unmatched owners use the fallback owner instead of stopping."
    else:
        message = f"Row {row_number}: {reason}, so the lead was given to {assigned_name} instead."
    return RowProblem(
        row_number=row_number,
        column=column,
        field=OWNER_FIELD,
        value=value,
        code=code,
        message=message,
        how_to_fix=fix,
    )


class OwnerResolver:
    """Decides the owner of each row, in row order.

    Rotation uses one running counter (``cursor``): it advances only when a
    row actually takes an owner from a rotation, so persisting ``cursor`` in
    ``job.options["round_robin_cursor"]`` after each batch and passing it back
    in keeps the rotation exact across batches and after a resume.
    """

    def __init__(
        self,
        plan: OwnerPlan,
        eligible_owners,
        current_user_id,
        cursor: int = 0,
        ineligible_users=(),
        owner_column: str = DEFAULT_OWNER_COLUMN,
    ):
        self._plan = plan
        self._column = owner_column or DEFAULT_OWNER_COLUMN
        self._cursor = max(int(cursor or 0), 0)
        self._by_id = {str(owner.id): owner for owner in eligible_owners}
        self._current = self._by_id.get(str(current_user_id))

        self._by_email: dict[str, EligibleOwner] = {}
        self._by_name: dict[str, list[EligibleOwner]] = {}
        for owner in eligible_owners:
            self._by_email.setdefault(_norm_text(owner.email), owner)
            self._by_name.setdefault(_norm_text(owner.name), []).append(owner)

        self._blocked_emails = {_norm_text(u.email) for u in ineligible_users}
        self._blocked_names = {_norm_text(u.name) for u in ineligible_users}

        self._value_mapping = {
            _norm_text(raw): user_id
            for raw, user_id in plan.owner_value_mapping.items()
            if _norm_text(raw)
        }

    @property
    def cursor(self) -> int:
        """Persist this after each batch (job.options["round_robin_cursor"])."""
        return self._cursor

    # -- public ------------------------------------------------------------

    def resolve(self, row_number: int, owner_cell_value=None) -> OwnerResult | RowProblem:
        mode = self._plan.mode
        if mode == MODE_SELECTED:
            return self._from_choice(self._plan.selected, SOURCE_SELECTED, row_number)
        if mode == MODE_FROM_FILE:
            return self._resolve_from_file(row_number, owner_cell_value)
        return self._me(row_number)

    # -- modes -------------------------------------------------------------

    def _me(self, row_number: int) -> OwnerResult | RowProblem:
        if self._current is None:
            return self._unavailable(row_number, "You")
        return OwnerResult(self._current.id, SOURCE_ME, self._current.name)

    def _resolve_from_file(self, row_number, cell) -> OwnerResult | RowProblem:
        text = " ".join(str(cell).split()) if cell is not None else ""
        if not text:
            return self._fallback(row_number, None)  # blank: silent fallback

        key = _norm_text(text)
        mapped_id = self._value_mapping.get(key)
        if mapped_id is not None:
            owner = self._by_id.get(mapped_id)
            if owner is not None:
                return OwnerResult(owner.id, SOURCE_MAPPED_VALUE, owner.name)
            return self._unmatched(row_number, text, CODE_OWNER_INELIGIBLE)

        owner = self._by_email.get(key)
        if owner is not None:
            return OwnerResult(owner.id, SOURCE_FILE, owner.name)

        matches = self._by_name.get(key, [])
        if len(matches) == 1:
            return OwnerResult(matches[0].id, SOURCE_FILE, matches[0].name)
        if len(matches) > 1:
            return self._unmatched(row_number, text, CODE_OWNER_AMBIGUOUS)

        if key in self._blocked_emails or key in self._blocked_names:
            return self._unmatched(row_number, text, CODE_OWNER_INELIGIBLE)
        return self._unmatched(row_number, text, CODE_OWNER_NOT_FOUND)

    def _unmatched(self, row_number, text, code) -> OwnerResult | RowProblem:
        if self._plan.on_unmatched == ON_UNMATCHED_ERROR:
            return _owner_problem(
                code, row_number=row_number, column=self._column, value=text,
                assigned_name="", rejected=True,
            )
        return self._fallback(row_number, (text, code))

    def _fallback(self, row_number, replaced) -> OwnerResult | RowProblem:
        result = self._from_choice(self._plan.fallback, SOURCE_FALLBACK, row_number)
        if replaced is None or isinstance(result, RowProblem):
            return result
        text, code = replaced
        warning = _owner_problem(
            code, row_number=row_number, column=self._column, value=text,
            assigned_name=result.owner_name, rejected=False,
        )
        return OwnerResult(result.owner_id, result.source, result.owner_name, warning)

    # -- single / rotation -------------------------------------------------

    def _from_choice(self, choice: OwnerChoice, source: str, row_number: int):
        if choice.kind == KIND_ROUND_ROBIN:
            # Plan order; anyone no longer eligible is skipped, never assigned.
            rotation = [
                self._by_id[i] for i in choice.rotation_ids() if i in self._by_id
            ]
            if not rotation:
                return self._unavailable(row_number, "The selected owners")
            owner = rotation[self._cursor % len(rotation)]
            self._cursor += 1  # only rows that really use a rotation advance it
            return OwnerResult(owner.id, source, owner.name)

        if choice.owner_id is None:
            # Fallback default: the current user.
            if self._current is None:
                return self._unavailable(row_number, "You")
            return OwnerResult(self._current.id, source, self._current.name)
        owner = self._by_id.get(choice.owner_id)
        if owner is None:
            return self._unavailable(row_number, "The selected owner")
        return OwnerResult(owner.id, source, owner.name)

    def _unavailable(self, row_number: int, who: str) -> RowProblem:
        verb = "are" if who in {"You", "The selected owners"} else "is"
        return RowProblem(
            row_number=row_number,
            column=self._column,
            field=OWNER_FIELD,
            value=None,
            code=CODE_OWNER_INELIGIBLE,
            message=(
                f"Row {row_number}: {who} {verb} no longer an active admin or "
                "superadmin, so this row was not imported."
            ),
            how_to_fix="Choose different owners and start the import again.",
        )


# ---------------------------------------------------------------------------
# Preview summary
# ---------------------------------------------------------------------------

def summarize_assignments(
    plan: OwnerPlan,
    eligible_owners,
    current_user_id,
    rows,
    cursor: int = 0,
    ineligible_users=(),
    owner_column: str = DEFAULT_OWNER_COLUMN,
) -> dict:
    """What the owner step shows before the import starts.

    ``rows``: the stored rows (``row_number`` + ``cleaned``) that WILL be
    imported, in file order (pass only valid, non-skipped rows, so rotation in
    the preview equals rotation in the real run). Uses a fresh resolver; the
    real cursor is not touched.

    Returns ``{"total", "rejected", "per_owner", "unmatched_values"}``:
      - ``per_owner``: ``[{owner_id, name, email, total, by_source}]``
        (``by_source`` has a count for each source), largest first;
      - ``unmatched_values``: file values that were not an eligible user, with
        ``count``, the reason ``code``, ``first_row``, ``rejected`` (true when
        the plan stops those rows) and ``fell_back_to`` (the owners they got,
        with counts), so the user can map them to a person if they wish.
    """
    resolver = OwnerResolver(
        plan, eligible_owners, current_user_id, cursor=cursor,
        ineligible_users=ineligible_users, owner_column=owner_column,
    )
    owners = {str(o.id): o for o in eligible_owners}

    per_owner: dict[str, dict] = {}
    unmatched: dict[str, dict] = {}
    rejected = 0
    total = 0

    for row in rows:
        total += 1
        row_number = row["row_number"]
        cell = (row.get("cleaned") or {}).get(OWNER_FIELD)
        result = resolver.resolve(row_number, cell)

        problem = result if isinstance(result, RowProblem) else result.warning
        if problem is not None and problem.value is not None:
            entry = unmatched.setdefault(
                _norm_text(problem.value),
                {
                    "value": " ".join(str(problem.value).split()),
                    "code": problem.code,
                    "count": 0,
                    "first_row": row_number,
                    "rejected": isinstance(result, RowProblem),
                    "fell_back_to": {},
                },
            )
            entry["count"] += 1

        if isinstance(result, RowProblem):
            rejected += 1
            continue

        owner_key = str(result.owner_id)
        owner = owners.get(owner_key)
        bucket = per_owner.setdefault(
            owner_key,
            {
                "owner_id": owner_key,
                "name": owner.name if owner else result.owner_name,
                "email": owner.email if owner else "",
                "total": 0,
                "by_source": {source: 0 for source in SOURCES},
            },
        )
        bucket["total"] += 1
        bucket["by_source"][result.source] += 1

        if result.warning is not None:
            fell = unmatched[_norm_text(result.warning.value)]["fell_back_to"]
            fell[owner_key] = fell.get(owner_key, 0) + 1

    unmatched_values = []
    for entry in unmatched.values():
        fell = entry.pop("fell_back_to")
        entry["fell_back_to"] = [
            {
                "owner_id": owner_id,
                "name": per_owner[owner_id]["name"],
                "count": count,
            }
            for owner_id, count in sorted(fell.items(), key=lambda kv: -kv[1])
        ]
        unmatched_values.append(entry)
    unmatched_values.sort(key=lambda e: (-e["count"], e["value"].casefold()))

    return {
        "total": total,
        "rejected": rejected,
        "per_owner": sorted(
            per_owner.values(), key=lambda b: (-b["total"], b["name"].casefold())
        ),
        "unmatched_values": unmatched_values,
    }
