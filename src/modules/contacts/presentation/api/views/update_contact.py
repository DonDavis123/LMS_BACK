from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.application.dto.update_contact import (
    UpdateContactDTO,
)
from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_update_contact_use_case,
)

from ..serializers.update_contact import UpdateContactSerializer


class UpdateContactView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, contact_id: UUID):
        serializer = UpdateContactSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        dto = UpdateContactDTO(
            contact_id=contact_id,
            fields=serializer.validated_data,
        )

        use_case = get_update_contact_use_case()

        try:
            contact = use_case.execute(
                data=dto,
                current_user_id=request.user.id,
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Contact updated successfully.",
                "contact_id": contact.id,
            },
            status=status.HTTP_200_OK,
        )