from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_contacts_use_case,
)
from src.modules.contacts.presentation.api.serializers.get_contacts import (
    ContactSerializer,
)
from src.modules.shared.presentation.query_params import parse_list_query


class GetContactsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            query = parse_list_query(request.query_params)
            result = get_contacts_use_case().execute(query)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ContactSerializer(result.results, many=True)

        return Response(
            {
                "results": serializer.data,
                "pagination": {
                    "page": result.page,
                    "page_size": result.page_size,
                    "total": result.total,
                    "total_pages": result.total_pages,
                },
            },
            status=status.HTTP_200_OK,
        )
