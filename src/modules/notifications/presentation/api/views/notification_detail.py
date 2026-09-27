from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from src.modules.notifications.presentation.api.dependencies.notification_dependencies import (
    get_delete_notification_use_case,
    get_notification_use_case,
    get_mark_notification_read_use_case,
)
from src.modules.notifications.presentation.api.serializers.notification import NotificationSerializer


class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, notification_id):
        notification = get_notification_use_case().execute(notification_id, request.user.id, timezone.now())
        if notification is None:
            return Response({"detail": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)

    def patch(self, request, notification_id):
        if set(request.data.keys()) - {"is_read"} or request.data.get("is_read") is not True:
            return Response({"detail": "Only marking a notification as read is supported."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            notification = get_mark_notification_read_use_case().execute(notification_id, request.user.id)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)

    def delete(self, request, notification_id):
        try:
            get_delete_notification_use_case().execute(notification_id, request.user.id)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)
        return Response({"message": "Notification deleted successfully."}, status=status.HTTP_200_OK)
