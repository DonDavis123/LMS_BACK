from datetime import timedelta
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from src.modules.shared.application.dto.list_query import ListQuery, PaginatedResult
from src.modules.shared.infrastructure.persistence.ordering import (
    SortableField,
    apply_ordering,
)

from src.modules.leads.application.interfaces.lead_import_job_repository import (
    LeadImportJobRepository,
)

from .django_lead_import_job_model import LeadImportJob


class DjangoLeadImportJobRepository(LeadImportJobRepository):

    SORTABLE_FIELDS = {
        "file_name": SortableField("file_name", is_text=True),
        "status": SortableField("status", is_text=True),
        "created_at": SortableField("created_at"),
        "finished_at": SortableField("finished_at"),
    }

    # Fields the caller may save through save_progress.
    PROGRESS_FIELDS = frozenset({
        "status",
        "header_row",
        "sheet_name",
        "headers",
        "mapping",
        "options",
        "rows",
        "total_rows",
        "processed_rows",
        "created_count",
        "updated_count",
        "skipped_count",
        "failed_count",
        "problems",
        "update_snapshots",
        "failure_message",
        "started_at",
        "finished_at",
        "undone_at",
        "undone_by",
        "rows_purged_at",
    })

    # Only finished jobs have their rows purged; running ones still need them.
    FINISHED_STATUSES = (
        LeadImportJob.Status.COMPLETED,
        LeadImportJob.Status.FAILED,
        LeadImportJob.Status.UNDONE,
        LeadImportJob.Status.PARTLY_UNDONE,
    )

    def __init__(self, *, company_id: UUID):
        if company_id is None:
            raise ValueError("company_id is required.")
        self._company_id = company_id

    def _base_queryset(self):
        return LeadImportJob.objects.filter(company_id=self._company_id)

    def create(
        self,
        *,
        created_by_id: UUID,
        file_name: str,
        headers: list,
        header_row: int = 1,
        sheet_name: str | None = None,
        mapping: dict | None = None,
        options: dict | None = None,
        rows: list | None = None,
        total_rows: int = 0,
    ) -> LeadImportJob:
        return LeadImportJob.objects.create(
            # Always the repository's own company, never a caller-supplied one.
            company_id=self._company_id,
            created_by_id=created_by_id,
            file_name=file_name,
            status=LeadImportJob.Status.QUEUED,
            header_row=header_row,
            sheet_name=sheet_name,
            headers=headers,
            mapping=mapping or {},
            options=options or {},
            rows=rows,
            total_rows=total_rows,
        )

    def get_for_company(self, job_id: UUID) -> LeadImportJob | None:
        try:
            return self._base_queryset().get(id=job_id)
        except LeadImportJob.DoesNotExist:
            return None

    def lock_for_processing(self, job_id: UUID) -> LeadImportJob | None:
        # select_for_update needs an open transaction; fail loudly rather
        # than silently skipping the lock.
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError(
                "lock_for_processing must be called inside transaction.atomic()."
            )
        try:
            return self._base_queryset().select_for_update().get(id=job_id)
        except LeadImportJob.DoesNotExist:
            return None

    def save_progress(self, job: LeadImportJob, fields: dict) -> LeadImportJob:
        unknown = set(fields) - self.PROGRESS_FIELDS
        if unknown:
            raise ValueError(
                f"Cannot save unsupported job fields: {', '.join(sorted(unknown))}."
            )
        if job.company_id != self._company_id:
            raise ValueError("Job does not belong to this company.")

        for name, value in fields.items():
            setattr(job, name, value)

        now = timezone.now()
        job.last_activity_at = now
        job.save(update_fields=sorted({*fields, "last_activity_at"}))
        return job

    def list_for_company(self, query: ListQuery) -> PaginatedResult[LeadImportJob]:
        # Stored rows can be large; history never needs them.
        queryset = (
            self._base_queryset()
            .select_related("created_by")
            .defer("rows", "update_snapshots")
        )

        if query.search:
            queryset = queryset.filter(file_name__icontains=query.search)

        total = queryset.count()
        queryset = apply_ordering(queryset, query, self.SORTABLE_FIELDS)

        offset = (query.page - 1) * query.page_size
        jobs = list(queryset[offset:offset + query.page_size])

        return PaginatedResult(
            results=jobs,
            page=query.page,
            page_size=query.page_size,
            total=total,
        )

    def find_stalled(
        self,
        older_than_seconds: int,
        limit: int = 50,
    ) -> list[LeadImportJob]:
        cutoff = timezone.now() - timedelta(seconds=older_than_seconds)
        return list(
            LeadImportJob.objects.filter(
                status__in=(
                    LeadImportJob.Status.QUEUED,
                    LeadImportJob.Status.PROCESSING,
                ),
                last_activity_at__lt=cutoff,
            )
            .defer("rows", "update_snapshots")
            .order_by("last_activity_at")[:limit]
        )

    def purge_rows_older_than(self, days: int) -> int:
        cutoff = timezone.now() - timedelta(days=days)
        return LeadImportJob.objects.filter(
            status__in=self.FINISHED_STATUSES,
            created_at__lt=cutoff,
            rows_purged_at__isnull=True,
        ).update(
            rows=None,
            rows_purged_at=timezone.now(),
        )
