import sys

from django.core.management.base import BaseCommand

from src.modules.companies.infrastructure.persistence.tenant_data_audit import (
    run_tenant_data_audit,
)


class Command(BaseCommand):
    help = (
        "Report rows without a company, rows whose company differs from the "
        "company of a related row, and inconsistent user/company assignments. "
        "Exits with code 1 if any count is non-zero, otherwise 0."
    )

    def handle(self, *args, **options):
        checks = run_tenant_data_audit()

        section_width = max(len(check.section) for check in checks)
        name_width = max(len(check.name) for check in checks)

        header = f"{'SECTION':<{section_width}}  {'CHECK':<{name_width}}  {'COUNT':>7}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        previous_section = None
        for check in checks:
            section = check.section if check.section != previous_section else ""
            previous_section = check.section
            self.stdout.write(
                f"{section:<{section_width}}  {check.name:<{name_width}}  "
                f"{check.count:>7}"
            )

        failing = [check for check in checks if check.count]
        self.stdout.write("")

        if not failing:
            self.stdout.write(
                self.style.SUCCESS("OK: every tenant data check is zero.")
            )
            return

        total = sum(check.count for check in failing)
        self.stdout.write(
            self.style.ERROR(
                f"FAILED: {len(failing)} check(s) reported rows "
                f"({total} in total)."
            )
        )
        sys.exit(1)
