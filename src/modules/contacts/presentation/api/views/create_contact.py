from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.application.dto.create_contact import (
    CreateContactDTO,
)
from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_create_contact_use_case,
)
from ..serializers.create_contact import CreateContactSerializer


class CreateContactView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreateContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        dto = CreateContactDTO(
            account_id=data.get("account_id"),
            contact_owner_id=data.get("contact_owner_id"),
            name=data["name"],
            email=data.get("email"),
            secondary_email=data.get("secondary_email"),
            phone=data.get("phone"),
            other_phone=data.get("other_phone"),
            mobile=data.get("mobile"),
            home_phone=data.get("home_phone"),
            assistant_phone=data.get("assistant_phone"),
            title=data.get("title"),
            department=data.get("department"),
            lead_source=data.get("lead_source"),
            vendor_name=data.get("vendor_name"),
            date_of_birth=data.get("date_of_birth"),
            assistant=data.get("assistant"),
            email_opt_out=data.get("email_opt_out", False),
            reporting_to_id=data.get("reporting_to_id"),
            mailing_address=data.get("mailing_address"),
            mailing_city=data.get("mailing_city"),
            mailing_state=data.get("mailing_state"),
            mailing_country=data.get("mailing_country"),
            mailing_postal_code=data.get("mailing_postal_code"),
            other_address=data.get("other_address"),
            description=data.get("description"),
        )

        use_case = get_create_contact_use_case()

        try:
            contact = use_case.execute(
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
                "id": str(contact.id),
                "message": "Contact created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )