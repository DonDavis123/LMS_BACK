from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.presentation.api.dependencies.user_dependencies import (
    get_lead_owners_use_case,
)

from ..serializers.lead_owner import LeadOwnerSerializer


class GetLeadOwnersView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        use_case = get_lead_owners_use_case()

        owners = use_case.execute()

        serializer = LeadOwnerSerializer(
            owners,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )