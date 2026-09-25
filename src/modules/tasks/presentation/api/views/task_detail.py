from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.tasks.application.dto.update_task import UpdateTaskDTO
from src.modules.tasks.domain.enums.task_priority import TaskPriority
from src.modules.tasks.domain.enums.task_status import TaskStatus
from src.modules.tasks.presentation.api.dependencies.task_dependencies import (
    get_delete_task_use_case,
    get_task_use_case,
    get_update_task_use_case,
)

from ..serializers.task import TaskSerializer
from ..serializers.task_read import TaskReadSerializer
from ..serializers.update_task import UpdateTaskSerializer


class TaskDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        task = get_task_use_case().execute(task_id)

        if task is None:
            return Response(
                {"detail": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            TaskReadSerializer(task).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, task_id):
        serializer = UpdateTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fields = serializer.validated_data

        if "priority" in fields:
            fields["priority"] = TaskPriority(fields["priority"])

        if "status" in fields:
            fields["status"] = TaskStatus(fields["status"])

        dto = UpdateTaskDTO(
            task_id=task_id,
            fields=fields,
        )

        try:
            task = get_update_task_use_case().execute(dto, current_user_id=request.user.id)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            TaskSerializer(task).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, task_id):
        try:
            get_delete_task_use_case().execute(task_id, current_user_id=request.user.id)
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Task deleted successfully."},
            status=status.HTTP_200_OK,
        )
