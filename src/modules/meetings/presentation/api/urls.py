from django.urls import path

from .views.meeting_conference import MeetingConferenceView
from .views.meeting_detail import MeetingDetailView
from .views.meeting_list import MeetingListView


urlpatterns = [
    path("", MeetingListView.as_view(), name="meetings"),
    path("<uuid:meeting_id>/", MeetingDetailView.as_view(), name="meeting-detail"),
    path(
        "<uuid:meeting_id>/conference/",
        MeetingConferenceView.as_view(),
        name="meeting-conference",
    ),
]
