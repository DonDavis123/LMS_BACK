from django.urls import path

from .views import (
    CreateLeadView,
    GetLeadsView,
    UpdateLeadView,
)


urlpatterns = [
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
        "<uuid:lead_id>/",
        UpdateLeadView.as_view(),
        name="update-lead",
    ),
]