from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_accounts_use_case,
)

from ..serializers.get_accounts import AccountSerializer


class GetAccountsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        use_case = get_accounts_use_case()

        accounts = use_case.execute()

        serializer = AccountSerializer(
            accounts,
            many=True,
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )