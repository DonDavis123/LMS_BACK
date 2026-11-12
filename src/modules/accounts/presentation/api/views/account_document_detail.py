from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from src.modules.accounts.application.dto.account_document import (
    DeleteAccountDocumentDTO,
    UpdateAccountDocumentDTO,
)
from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_delete_account_document_use_case,
    get_update_account_document_use_case,
)

from ..serializers.account_document import (
    AccountDocumentInputSerializer,
    AccountDocumentSerializer,
)

NOT_FOUND_MESSAGES = {"Account not found.", "Document not found."}


class AccountDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def put(self, request, account_id: UUID, document_id: UUID):
        serializer = AccountDocumentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        dto = UpdateAccountDocumentDTO(
            account_id=account_id,
            document_id=document_id,
            name=data["name"],
            url=data["url"],
        )

        ctx = get_tenant_context(request)
        use_case = get_update_account_document_use_case(ctx)

        try:
            document = use_case.execute(
                data=dto,
                current_user_id=request.user.id,
            )
        except ValueError as error:
            message = str(error)
            return Response(
                {"detail": message},
                status=(
                    status.HTTP_404_NOT_FOUND
                    if message in NOT_FOUND_MESSAGES
                    else status.HTTP_400_BAD_REQUEST
                ),
            )

        return Response(
            AccountDocumentSerializer(document).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, account_id: UUID, document_id: UUID):
        dto = DeleteAccountDocumentDTO(
            account_id=account_id,
            document_id=document_id,
        )

        ctx = get_tenant_context(request)
        use_case = get_delete_account_document_use_case(ctx)

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
                "message": "Document deleted successfully.",
                "document_id": document_id,
            },
            status=status.HTTP_200_OK,
        )
