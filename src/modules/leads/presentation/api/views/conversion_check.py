from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_conversion_check_use_case,
)


class ConversionCheckView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lead_id):

        use_case = get_conversion_check_use_case()

        try:
            result = use_case.execute(
                UUID(str(lead_id)),
            )

        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "lead_id": str(result.lead_id),

                "accounts": [
                    {
                        "id": str(account.id),
                        "account_name": account.account_name,
                        "website": account.website,
                        "phone": account.phone,
                    }
                    for account in result.account_matches
                ],

                "contacts": [
                    {
                        "id": str(contact.id),
                        "name": contact.name,
                        "email": contact.email,
                        "phone": contact.phone,
                        "mobile": contact.mobile,
                    }
                    for contact in result.contact_matches
                ],
            },
            status=status.HTTP_200_OK,
        )