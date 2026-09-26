from django.urls import path

from .views.reminder_detail import ReminderDetailView
from .views.reminder_list import ReminderListView


urlpatterns = [
    path("", ReminderListView.as_view(), name="reminders"),
    path("<uuid:reminder_id>/", ReminderDetailView.as_view(), name="reminder-detail"),
]
