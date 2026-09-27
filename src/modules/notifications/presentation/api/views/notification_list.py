from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from src.modules.notifications.presentation.api.dependencies.notification_dependencies import get_notifications_use_case
from src.modules.notifications.presentation.api.serializers.notification import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = request.query_params.get("unread", "false").lower() == "true"
        notifications = get_notifications_use_case().execute(
            current_user_id=request.user.id,
            as_of=timezone.now(),
            unread_only=unread_only,
        )
        return Response(NotificationSerializer(notifications, many=True).data, status=status.HTTP_200_OK)


class UnreadNotificationListView(NotificationListView):
    def get(self, request):
        from django.utils import timezone
        from rest_framework import status
        from rest_framework.response import Response

        notifications = get_notifications_use_case().execute(
            current_user_id=request.user.id,
            as_of=timezone.now(),
            unread_only=True,
        )
        return Response(NotificationSerializer(notifications, many=True).data, status=status.HTTP_200_OK)
