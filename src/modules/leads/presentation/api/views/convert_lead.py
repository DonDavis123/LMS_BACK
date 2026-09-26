from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.dto.convert_lead import (
    ConvertAccountDTO,
    ConvertContactDTO,
    ConvertLeadDTO,
)

from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_convert_lead_use_case,
)

from ..serializers.convert_lead import ConvertLeadSerializer


class ConvertLeadView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, lead_id):

        serializer = ConvertLeadSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        data = serializer.validated_data

        # -----------------------------------------
        # Account DTO
        # -----------------------------------------

        account_dto = None

        if data.get("account") is not None:

            account_data = data["account"]

            account_dto = ConvertAccountDTO(
                account_name=account_data["account_name"],
                account_site=account_data.get("account_site"),
                account_number=account_data.get("account_number"),
                account_type=account_data.get("account_type"),
                industry=account_data.get("industry"),
                annual_revenue=account_data.get("annual_revenue"),
                rating=account_data.get("rating"),
                phone=account_data.get("phone"),
                website=account_data.get("website"),
                ticker_symbol=account_data.get("ticker_symbol"),
                ownership=account_data.get("ownership"),
                employees=account_data.get("employees"),
                sic_code=account_data.get("sic_code"),
                billing_address=account_data.get("billing_address"),
                billing_city=account_data.get("billing_city"),
                billing_state=account_data.get("billing_state"),
                billing_country=account_data.get("billing_country"),
                billing_postal_code=account_data.get(
                    "billing_postal_code"
                ),
                description=account_data.get("description"),
            )

        # -----------------------------------------
        # Contact DTO
        # -----------------------------------------

        contact_dto = None

        if data.get("contact") is not None:

            contact_data = data["contact"]

            contact_dto = ConvertContactDTO(
                name=contact_data["name"],
                email=contact_data.get("email"),
                secondary_email=contact_data.get(
                    "secondary_email"
                ),
                phone=contact_data.get("phone"),
                other_phone=contact_data.get(
                    "other_phone"
                ),
                mobile=contact_data.get("mobile"),
                home_phone=contact_data.get(
                    "home_phone"
                ),
                assistant_phone=contact_data.get(
                    "assistant_phone"
                ),
                title=contact_data.get("title"),
                department=contact_data.get(
                    "department"
                ),
                lead_source=contact_data.get(
                    "lead_source"
                ),
                vendor_name=contact_data.get(
                    "vendor_name"
                ),
                date_of_birth=contact_data.get(
                    "date_of_birth"
                ),
                assistant=contact_data.get(
                    "assistant"
                ),
                email_opt_out=contact_data.get(
                    "email_opt_out",
                    False,
                ),
                reporting_to_id=contact_data.get(
                    "reporting_to_id"
                ),
                mailing_address=contact_data.get(
                    "mailing_address"
                ),
                mailing_city=contact_data.get(
                    "mailing_city"
                ),
                mailing_state=contact_data.get(
                    "mailing_state"
                ),
                mailing_country=contact_data.get(
                    "mailing_country"
                ),
                mailing_postal_code=contact_data.get(
                    "mailing_postal_code"
                ),
                other_address=contact_data.get(
                    "other_address"
                ),
                description=contact_data.get(
                    "description"
                ),
            )

        # -----------------------------------------
        # Build DTO
        # -----------------------------------------

        dto = ConvertLeadDTO(
            lead_id=UUID(str(lead_id)),

            account_action=data.get("account_action"),
            account_id=data.get("account_id"),
            account=account_dto,

            contact_action=data["contact_action"],
            contact_id=data.get("contact_id"),
            contact=contact_dto,
        )

        use_case = get_convert_lead_use_case()

        try:

            use_case.execute(
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
                "message": "Lead converted successfully."
            },
            status=status.HTTP_200_OK,
        )