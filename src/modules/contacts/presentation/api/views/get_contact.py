from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_contacts_use_case,
)
from ..serializers.get_contacts import ContactSerializer


class GetContactsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        use_case = get_contacts_use_case()

        contacts = use_case.execute()

        serializer = ContactSerializer(
            contacts,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )