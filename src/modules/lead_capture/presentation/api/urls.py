from django.urls import path

from .views.lead_form import (
    BlockLeadFormView,
    LeadFormView,
    RegenerateLeadFormLinkView,
    UnblockLeadFormView,
)

urlpatterns = [
    path("form/", LeadFormView.as_view(), name="lead-capture-form"),
    path("form/block/", BlockLeadFormView.as_view(), name="lead-capture-form-block"),
    path(
        "form/unblock/",
        UnblockLeadFormView.as_view(),
        name="lead-capture-form-unblock",
    ),
    path(
        "form/regenerate-link/",
        RegenerateLeadFormLinkView.as_view(),
        name="lead-capture-form-regenerate-link",
    ),
]
