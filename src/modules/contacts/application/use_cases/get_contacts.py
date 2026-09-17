from src.modules.contacts.application.interfaces.contact_repository import (
    ContactRepository,
)

class GetContactsUseCase:

    def __init__(self, contact_repository):
        self.contact_repository = contact_repository

    def execute(self):
        contacts = self.contact_repository.get_all_with_relations()

        return [
            {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "phone": contact.phone,
                "mobile": contact.mobile,
                "account_id": contact.account_id,
                "account_name": account_name,
                "contact_owner_id": contact.contact_owner_id,
                "contact_owner_name": contact_owner_name,
                "next_task_due_date": next_task_due_date,
                "next_task_status": next_task_status,
            }
            for (
                contact,
                account_name,
                contact_owner_name,
                next_task_due_date,
                next_task_status,
            ) in contacts
        ]