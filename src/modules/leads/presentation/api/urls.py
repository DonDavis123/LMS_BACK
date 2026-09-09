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



]