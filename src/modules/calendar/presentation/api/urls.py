from django.urls import path

from .views.calendar_events import CalendarEventsView

urlpatterns = [
    path("events/", CalendarEventsView.as_view(), name="calendar-events"),
]
