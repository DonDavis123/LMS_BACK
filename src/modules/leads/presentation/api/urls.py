from django.urls import path

from .views import CreateLeadView, GetLeadsView


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
]