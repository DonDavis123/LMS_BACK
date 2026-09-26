from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.reminders.application.dto.update_reminder import UpdateReminderDTO
from src.modules.reminders.presentation.api.dependencies.reminder_dependencies import (
    get_delete_reminder_use_case,
    get_get_reminder_use_case,
    get_update_reminder_use_case,
)

from ..serializers.reminder import ReminderSerializer
from ..serializers.update_reminder import UpdateReminderSerializer


class ReminderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reminder_id):
        reminder = get_get_reminder_use_case().execute(
            reminder_id,
            current_user_id=request.user.id,
        )

        if reminder is None:
            return Response(
                {"detail": "Reminder not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ReminderSerializer(reminder).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, reminder_id):
        serializer = UpdateReminderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dto = UpdateReminderDTO(
            reminder_id=reminder_id,
            fields=serializer.validated_data,
        )

        try:
            reminder = get_update_reminder_use_case().execute(
                dto,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ReminderSerializer(reminder).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, reminder_id):
        try:
            get_delete_reminder_use_case().execute(
                reminder_id,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"message": "Reminder deleted successfully."},
            status=status.HTTP_200_OK,
        )
