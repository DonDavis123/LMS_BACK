from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    """Who is acting and for which company.

    Built on the server from the authenticated user (never from request
    data) and handed to the dependency factories, which scope every
    repository to ``company_id``.
    """

    company_id: UUID
    user_id: UUID
    role: str
