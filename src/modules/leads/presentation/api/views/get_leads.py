from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_leads_use_case,
)

from ..serializers import LeadSerializer
from src.modules.leads.presentation.permissions.is_admin import IsAdmin


class GetLeadsView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsAdmin,
    ]

    def get(self, request):

        use_case = get_leads_use_case()

        leads = use_case.execute()

        serializer = LeadSerializer(
            leads,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )