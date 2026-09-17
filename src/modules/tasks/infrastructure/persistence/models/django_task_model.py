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

    class Meta:
        db_table = "tasks"

    def __str__(self):
        return self.subject
