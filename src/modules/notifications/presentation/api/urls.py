from django.urls import path

from .views.notification_detail import NotificationDetailView
from .views.notification_list import NotificationListView, UnreadNotificationListView
from .views.notification_read import NotificationReadView


urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications"),
    path("unread/", UnreadNotificationListView.as_view(), name="notifications-unread"),
    path("<uuid:notification_id>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("<uuid:notification_id>/", NotificationDetailView.as_view(), name="notification-detail"),
]
