from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.reminders.application.dto.create_reminder import CreateReminderDTO
from src.modules.reminders.presentation.api.dependencies.reminder_dependencies import (
    get_create_reminder_use_case,
    get_get_reminders_use_case,
)

from ..serializers.create_reminder import CreateReminderSerializer
from ..serializers.reminder import ReminderSerializer


class ReminderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        task_id = request.query_params.get("task_id")
        meeting_id = request.query_params.get("meeting_id")

        try:
            from uuid import UUID

            parsed_task_id = UUID(task_id) if task_id else None
            parsed_meeting_id = UUID(meeting_id) if meeting_id else None

            reminders = get_get_reminders_use_case().execute(
                current_user_id=request.user.id,
                task_id=parsed_task_id,
                meeting_id=parsed_meeting_id,
            )
        except (ValueError, TypeError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ReminderSerializer(reminders, many=True).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CreateReminderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dto = CreateReminderDTO(
            subject=data["subject"],
            remind_at=data["remind_at"],
            user_id=request.user.id,
            task_id=data.get("task_id"),
            meeting_id=data.get("meeting_id"),
        )

        try:
            reminder = get_create_reminder_use_case().execute(dto)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ReminderSerializer(reminder).data,
            status=status.HTTP_201_CREATED,
        )
