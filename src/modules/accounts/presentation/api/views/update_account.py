from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.accounts.application.dto.update_account import (
    UpdateAccountDTO,
)
from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_update_account_use_case,
)

from ..serializers.edit_account import UpdateAccountSerializer


class UpdateAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, account_id: UUID):
        serializer = UpdateAccountSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = serializer.validated_data

        dto = UpdateAccountDTO(
            account_id=account_id,

            account_name=data["account_name"],
            account_site=data.get("account_site"),
            account_number=data.get("account_number"),
            account_type=data.get("account_type"),
            industry=data.get("industry"),
            annual_revenue=data.get("annual_revenue"),
            rating=data.get("rating"),
            phone=data.get("phone"),
            website=data.get("website"),
            ticker_symbol=data.get("ticker_symbol"),
            ownership=data.get("ownership"),
            employees=data.get("employees"),
            sic_code=data.get("sic_code"),

            billing_address=data.get("billing_address"),
            billing_city=data.get("billing_city"),
            billing_state=data.get("billing_state"),
            billing_country=data.get("billing_country"),
            billing_postal_code=data.get("billing_postal_code"),

            description=data.get("description"),
        )

        use_case = get_update_account_use_case()

        try:
            account = use_case.execute(
                data=dto,
                current_user_id=request.user.id,
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Account updated successfully.",
                "account_id": account.id,
            },
            status=status.HTTP_200_OK,
        )