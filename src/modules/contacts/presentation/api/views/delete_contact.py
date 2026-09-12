from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.application.dto.delete_contact import DeleteContactDTO
from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_delete_contact_use_case,
)


class DeleteContactView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, contact_id: UUID):
        dto = DeleteContactDTO(
            contact_id=contact_id,
        )

        use_case = get_delete_contact_use_case()

        try:
            contact = use_case.execute(data=dto)

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "message": "Contact deleted successfully.",
                "contact_id": contact.id,
            },
            status=status.HTTP_200_OK,
        )