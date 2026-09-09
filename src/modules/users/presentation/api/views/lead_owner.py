from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.users.application.use_cases.get_lead_owners import (
    GetLeadOwnersUseCase,
)
from src.modules.users.infrastructure.persistence.user_repository import (
    DjangoUserRepository,
)

from ..serializers.lead_owner import LeadOwnerSerializer


class GetLeadOwnersView(APIView):

    permission_classes = [
        IsAuthenticated,
    ]

    def get(self, request):

        use_case = GetLeadOwnersUseCase(
            user_repository=DjangoUserRepository(),
        )

        owners = use_case.execute()

        serializer = LeadOwnerSerializer(
            owners,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )