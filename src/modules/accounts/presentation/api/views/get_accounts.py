from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_accounts_use_case,
)
from src.modules.shared.presentation.query_params import parse_list_query

from ..serializers.get_accounts import AccountSerializer


class GetAccountsView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        ctx = get_tenant_context(request)
        try:
            query = parse_list_query(request.query_params)
            result = get_accounts_use_case(ctx).execute(query)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AccountSerializer(result.results, many=True)

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
