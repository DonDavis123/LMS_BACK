from django.urls import path

from .views.call_detail import CallDetailView
from .views.call_list import CallListView


urlpatterns = [
    path("", CallListView.as_view(), name="calls"),
    path("<uuid:call_id>/", CallDetailView.as_view(), name="call-detail"),
]
