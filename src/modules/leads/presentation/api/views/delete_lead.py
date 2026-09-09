from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_delete_lead_use_case,
)


class DeleteLeadView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, lead_id):
        use_case = get_delete_lead_use_case()

        try:
            use_case.execute(UUID(str(lead_id)))
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Lead deleted successfully."},
            status=status.HTTP_200_OK,
        )