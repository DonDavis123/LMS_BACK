from django.urls import path

from .views.call_detail import CallDetailView
from .views.call_history import CallRecordHistoryView
from .views.call_list import CallListView
from .views.call_record_list import CallRecordListView
from .views.call_recording import (
    CallRecordingDetailView,
    CallRecordingFileView,
    CallRecordingListView,
)


urlpatterns = [
    path("", CallListView.as_view(), name="calls"),
    path("records/", CallRecordListView.as_view(), name="call-records"),
    path("<uuid:call_id>/", CallDetailView.as_view(), name="call-detail"),
    path(
        "<uuid:call_id>/history/",
        CallRecordHistoryView.as_view(),
        name="call-record-history",
    ),
    path(
        "<uuid:call_id>/recordings/",
        CallRecordingListView.as_view(),
        name="call-recordings",
    ),
    path(
        "<uuid:call_id>/recordings/<uuid:recording_id>/",
        CallRecordingDetailView.as_view(),
        name="call-recording-detail",
    ),
    path(
        "<uuid:call_id>/recordings/<uuid:recording_id>/file/",
        CallRecordingFileView.as_view(),
        name="call-recording-file",
    ),
]
