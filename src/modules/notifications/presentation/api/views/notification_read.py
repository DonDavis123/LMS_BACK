from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.notifications.presentation.api.dependencies.notification_dependencies import get_mark_notification_read_use_case
from src.modules.notifications.presentation.api.serializers.notification import NotificationSerializer


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        if request.data != {"is_read": True}:
            return Response(
                {"detail": "Only marking a notification as read is supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            notification = get_mark_notification_read_use_case().execute(
                notification_id,
                request.user.id,
            )
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_404_NOT_FOUND)
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)
