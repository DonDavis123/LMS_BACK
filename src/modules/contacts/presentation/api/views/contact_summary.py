from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.contacts.application.interfaces.contact_summary_generator import (
    ContactSummaryError,
    ContactSummaryUnavailableError,
)
from src.modules.contacts.presentation.api.dependencies.contact_dependency import (
    get_generate_contact_summary_use_case,
    get_contact_summary_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.throttles import (
    AIGenerationCompanyThrottle,
    AIGenerationUserThrottle,
)
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.contact_summary import ContactSummarySerializer


class GenerateContactSummaryView(APIView):
    """The AI summary of a contact.

    ``GET`` returns the stored summary (``204`` when none was written yet).
    It never calls the model, so opening a contact costs nothing.

    ``POST`` writes a fresh summary of the contact's history and stores it,
    permanently replacing the previous one. It is POST because every call
    costs a model request.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]
    # Every POST costs a Gemini request: limited per user and per company
    # (GET never calls the model and is not counted).
    throttle_classes = [AIGenerationUserThrottle, AIGenerationCompanyThrottle]

    def get(self, request, contact_id):
        use_case = get_contact_summary_use_case(get_tenant_context(request))

        try:
            result = use_case.execute(UUID(str(contact_id)))
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        if result is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            ContactSummarySerializer(result).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, contact_id):
        use_case = get_generate_contact_summary_use_case(get_tenant_context(request))

        try:
            result = use_case.execute(UUID(str(contact_id)))
        except ContactSummaryUnavailableError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except ContactSummaryError as error:
            return Response(
                {"detail": error.user_message},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            ContactSummarySerializer(result).data,
            status=status.HTTP_200_OK,
        )
