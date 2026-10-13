from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from src.modules.accounts.application.dto.delete_account import (
    DeleteAccountDTO,
)
from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_delete_account_use_case,
)


class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def delete(
        self,
        request,
        account_id: UUID,
    ):
        dto = DeleteAccountDTO(
            account_id=account_id,
        )

        ctx = get_tenant_context(request)
        use_case = get_delete_account_use_case(ctx)

        try:
            use_case.execute(
                data=dto,
                current_user_id=request.user.id,
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "message": "Account deleted successfully.",
                "account_id": account_id,
            },
            status=status.HTTP_200_OK,
        )