from django.urls import path

from .views.company_detail import CompanyDetailView
from .views.company_list import CompanyListCreateView
from .views.company_status import ActivateCompanyView, SuspendCompanyView

urlpatterns = [
    path("", CompanyListCreateView.as_view(), name="platform-companies"),
    path(
        "<uuid:company_id>/",
        CompanyDetailView.as_view(),
        name="platform-company-detail",
    ),
    path(
        "<uuid:company_id>/suspend/",
        SuspendCompanyView.as_view(),
        name="platform-company-suspend",
    ),
    path(
        "<uuid:company_id>/activate/",
        ActivateCompanyView.as_view(),
        name="platform-company-activate",
    ),
]
