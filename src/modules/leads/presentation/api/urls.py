from django.urls import path

from .views import (
    CreateLeadView,
    GetLeadsView,
    UpdateLeadView,
    
    
    
)
from .views.lead_detail import GetLeadDetailsView
from src.modules.leads.presentation.api.views.delete_lead import (
    DeleteLeadView,
)
from src.modules.leads.presentation.api.views.convert_lead import (
    ConvertLeadView,
)
from src.modules.leads.presentation.api.views.conversion_check import (
    ConversionCheckView,
)
from src.modules.leads.presentation.api.views.lead_import import (
    ImportCancelView,
    ImportDraftView,
    ImportExclusionsView,
    ImportHistoryView,
    ImportMappingPreviewView,
    ImportProcessView,
    ImportProgressView,
    ImportRejectedFileView,
    ImportReportView,
    ImportResultsFileView,
    ImportRowsView,
    ImportStartView,
    ImportTemplateView,
    ImportUndoPreviewView,
    ImportUndoView,
    ImportUploadView,
    ImportValidateView,
)



urlpatterns = [
    # Lead import. These go before the <uuid:lead_id> routes below.
    path("import/template/", ImportTemplateView.as_view(), name="lead-import-template"),
    path("import/upload/", ImportUploadView.as_view(), name="lead-import-upload"),
    # Must stay before every <uuid:job_id> route.
    path("import/history/", ImportHistoryView.as_view(), name="lead-import-history"),
    path(
        "import/<uuid:job_id>/mapping-preview/",
        ImportMappingPreviewView.as_view(),
        name="lead-import-mapping-preview",
    ),
    path(
        "import/<uuid:job_id>/validate/",
        ImportValidateView.as_view(),
        name="lead-import-validate",
    ),
    path(
        "import/<uuid:job_id>/rows/",
        ImportRowsView.as_view(),
        name="lead-import-rows",
    ),
    path(
        "import/<uuid:job_id>/exclusions/",
        ImportExclusionsView.as_view(),
        name="lead-import-exclusions",
    ),
    path(
        "import/<uuid:job_id>/start/",
        ImportStartView.as_view(),
        name="lead-import-start",
    ),
    path(
        "import/<uuid:job_id>/process/",
        ImportProcessView.as_view(),
        name="lead-import-process",
    ),
    path(
        "import/<uuid:job_id>/progress/",
        ImportProgressView.as_view(),
        name="lead-import-progress",
    ),
    path(
        "import/<uuid:job_id>/report/",
        ImportReportView.as_view(),
        name="lead-import-report",
    ),
    path(
        "import/<uuid:job_id>/rejected-file/",
        ImportRejectedFileView.as_view(),
        name="lead-import-rejected-file",
    ),
    path(
        "import/<uuid:job_id>/results-file/",
        ImportResultsFileView.as_view(),
        name="lead-import-results-file",
    ),
    path(
        "import/<uuid:job_id>/undo-preview/",
        ImportUndoPreviewView.as_view(),
        name="lead-import-undo-preview",
    ),
    path(
        "import/<uuid:job_id>/undo/",
        ImportUndoView.as_view(),
        name="lead-import-undo",
    ),
    path(
        "import/<uuid:job_id>/cancel/",
        ImportCancelView.as_view(),
        name="lead-import-cancel",
    ),
    path(
        "import/<uuid:job_id>/",
        ImportDraftView.as_view(),
        name="lead-import-discard",
    ),

    path(
        "create/",
        CreateLeadView.as_view(),
        name="create-lead",
    ),

    path(
        "",
        GetLeadsView.as_view(),
        name="get-leads",
    ),

   path(
    "<uuid:lead_id>/update/",
    UpdateLeadView.as_view(),
    name="update-lead",
      
),

    path(
       "<uuid:lead_id>/",
       GetLeadDetailsView.as_view(),
       name="get-lead-details",
),

path(
    "<uuid:lead_id>/delete/",
    DeleteLeadView.as_view(),
    name="delete-lead",
),

path(
    "<uuid:lead_id>/convert/",
    ConvertLeadView.as_view(),
    name="convert-lead",
),
path(
    "<uuid:lead_id>/conversion-check/",
    ConversionCheckView.as_view(),
    name="conversion-check",
),



]