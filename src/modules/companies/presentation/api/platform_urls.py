from django.urls import path

from .views.platform_audit_logs import PlatformAuditLogListView
from .views.platform_overview import PlatformOverviewView

urlpatterns = [
    path(
        "audit-logs/",
        PlatformAuditLogListView.as_view(),
        name="platform-audit-logs",
    ),
    path(
        "overview/",
        PlatformOverviewView.as_view(),
        name="platform-overview",
    ),
]
