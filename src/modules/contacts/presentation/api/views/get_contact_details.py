from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_contact_details_use_case,
)

from ..serializers.get_contact_details import ContactDetailsSerializer


class GetContactDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contact_id: UUID):
        use_case = get_contact_details_use_case()

        contact = use_case.execute(
            contact_id=contact_id,
        )

        if contact is None:
            return Response(
                {"detail": "Contact not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = ContactDetailsSerializer(contact)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )