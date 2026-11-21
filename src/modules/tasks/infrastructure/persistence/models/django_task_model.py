import uuid

from django.conf import settings
from django.db import models

from src.modules.accounts.infrastructure.persistence.django_account_model import (
    DjangoAccountModel,
)
from src.modules.contacts.infrastructure.persistence.django_contact_model import (
    DjangoContactModel,
)
from src.modules.leads.infrastructure.persistence.django_lead_model import (
    DjangoLeadModel,
)
from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus


class DjangoTaskModel(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    subject = models.CharField(
        max_length=255,
    )

    due_date = models.DateField(
        blank=True,
        null=True,
    )

    priority = models.CharField(
        max_length=100,
        choices=[
            (priority.value, priority.value)
            for priority in TaskPriority
        ],
        default=TaskPriority.NORMAL,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_tasks",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
        blank=True,
        null=True,
    )

    reminder_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    lead = models.ForeignKey(
        DjangoLeadModel,
        on_delete=models.PROTECT,
        related_name="tasks",
        blank=True,
        null=True,
    )

    contact = models.ForeignKey(
        DjangoContactModel,
        on_delete=models.PROTECT,
        related_name="tasks",
        blank=True,
        null=True,
    )

    account = models.ForeignKey(
        DjangoAccountModel,
        on_delete=models.PROTECT,
        related_name="tasks",
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=100,
        choices=[
            (status.value, status.value)
            for status in TaskStatus
        ],
        default=TaskStatus.NOT_STARTED,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    is_deleted = models.BooleanField(
        default=False,
    )

    company = models.ForeignKey(
        "companies.DjangoCompanyModel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        db_index=True,
    )

    class Meta:
        db_table = "tasks"
        indexes = [
            # List filters / sorts (see migration 0005_task_list_indexes and
            # 0006_task_assigned_index).
            models.Index(
                fields=["company", "is_deleted", "created_at"],
                name="tasks_co_created_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "status"],
                name="tasks_co_status_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "due_date"],
                name="tasks_co_due_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "owner"],
                name="tasks_co_owner_idx",
            ),
            models.Index(
                fields=["company", "is_deleted", "assigned_to"],
                name="tasks_co_assigned_idx",
            ),
            # "Next task" of a contact (contact list subquery).
            models.Index(
                fields=["contact", "is_deleted", "due_date", "created_at"],
                name="tasks_contact_next_idx",
            ),
        ]

    def __str__(self):
        return self.subject
