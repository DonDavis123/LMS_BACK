from django.urls import path

from .views import ExportRecordsView

urlpatterns = [
    path(
        "<str:entity>/",
        ExportRecordsView.as_view(),
        name="export-records",
    ),
]
