from dataclasses import dataclass


@dataclass(frozen=True)
class PublicLeadFormDTO:
    """The only things a visitor may learn about a form."""

    title: str
    company_name: str
    accepting_responses: bool


@dataclass(frozen=True)
class PublicLeadSubmissionDTO:
    name: str
    email: str
    phone: str
    description: str
