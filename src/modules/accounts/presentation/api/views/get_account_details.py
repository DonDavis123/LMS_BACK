from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_account_details_use_case,
)

from ..serializers.get_account_serializer import AccountDetailsSerializer


class GetAccountDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, account_id: UUID):
        use_case = get_account_details_use_case()

        account = use_case.execute(
            account_id=account_id,
        )

        if account is None:
            return Response(
                {"detail": "Account not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AccountDetailsSerializer(account)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )