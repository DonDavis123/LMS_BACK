from django.urls import path

from .views.public_lead_form import PublicLeadFormView

urlpatterns = [
    path("<slug:token>/", PublicLeadFormView.as_view(), name="public-lead-form"),
]
