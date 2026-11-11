from enum import Enum


class MailEntity(str, Enum):
    """The list a mail selection is made on."""

    CONTACTS = "contacts"
    LEADS = "leads"
    ACCOUNTS = "accounts"
