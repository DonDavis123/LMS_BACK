from uuid import UUID

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.accounts.application.interfaces.account_summary_generator import (
    AccountSummaryError,
    AccountSummaryUnavailableError,
)
from src.modules.accounts.presentation.api.dependencies.account_dependencies import (
    get_generate_account_summary_use_case,
    get_account_summary_use_case,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.throttles import (
    AIGenerationCompanyThrottle,
    AIGenerationUserThrottle,
)
from src.modules.shared.presentation.tenant import get_tenant_context

from ..serializers.account_summary import AccountSummarySerializer


class GenerateAccountSummaryView(APIView):
    """The AI summary of an account.

    ``GET`` returns the stored summary (``204`` when none was written yet).
    It never calls the model, so opening an account costs nothing.

    ``POST`` writes a fresh summary of the account's history and stores it,
    permanently replacing the previous one. It is POST because every call
    costs a model request.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]
    # Every POST costs a Gemini request: limited per user and per company
    # (GET never calls the model and is not counted).
    throttle_classes = [AIGenerationUserThrottle, AIGenerationCompanyThrottle]

    def get(self, request, account_id):
        use_case = get_account_summary_use_case(get_tenant_context(request))

        try:
            result = use_case.execute(UUID(str(account_id)))
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_404_NOT_FOUND,
            )

        if result is None:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            AccountSummarySerializer(result).data,
            status=status.HTTP_200_OK,
        )

    def post(self, request, account_id):
        use_case = get_generate_account_summary_use_case(get_tenant_context(request))

        try:
            result = use_case.execute(UUID(str(account_id)))
        except AccountSummaryUnavailableError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except AccountSummaryError as error:
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
            AccountSummarySerializer(result).data,
            status=status.HTTP_200_OK,
        )
