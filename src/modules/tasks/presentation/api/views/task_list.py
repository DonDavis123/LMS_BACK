from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.tasks.application.dto.create_task import CreateTaskDTO
from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus
from src.modules.tasks.presentation.api.dependencies.task_dependencies import (
    get_create_task_use_case,
    get_tasks_use_case,
)

from ..serializers.create_task import CreateTaskSerializer
from ..serializers.task import TaskSerializer


class TaskListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tasks = get_tasks_use_case().execute()

        serializer = TaskSerializer(tasks, many=True)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = CreateTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        dto = CreateTaskDTO(
            subject=data["subject"],
            owner_id=data["owner_id"],
            created_by_id=request.user.id,
            due_date=data.get("due_date"),
            priority=TaskPriority(data["priority"]),
            reminder_at=data.get("reminder_at"),
            lead_id=data.get("lead_id"),
            contact_id=data.get("contact_id"),
            account_id=data.get("account_id"),
            status=TaskStatus(data["status"]),
            description=data.get("description"),
        )

        try:
            task = get_create_task_use_case().execute(dto)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TaskSerializer(task).data,
            status=status.HTTP_201_CREATED,
        )
