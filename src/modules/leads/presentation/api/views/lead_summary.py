from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.leads.application.interfaces.lead_summary_generator import (
    LeadSummaryError,
    LeadSummaryUnavailableError,
)
from src.modules.leads.presentation.api.dependencies.lead_dependencies import (
    get_generate_lead_summary_use_case,
    get_lead_summary_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.lead_summary import LeadSummarySerializer


class GenerateLeadSummaryView(APIView):
    """The AI summary of a lead.

    ``GET`` returns the stored summary (``204`` when none was written yet).
    It never calls the model, so opening a lead costs nothing.

    ``POST`` writes a fresh summary of the lead's history and stores it,
    permanently replacing the previous one. It is POST because every call
    costs a model request.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, lead_id):
        use_case = get_lead_summary_use_case(get_tenant_context(request))

        try:
            result = use_case.execute(UUID(str(lead_id)))
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        if result is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            LeadSummarySerializer(result).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, lead_id):
        use_case = get_generate_lead_summary_use_case(get_tenant_context(request))

        try:
            result = use_case.execute(UUID(str(lead_id)))
        except LeadSummaryUnavailableError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except LeadSummaryError as error:
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
            LeadSummarySerializer(result).data,
            status=status.HTTP_200_OK,
        )
