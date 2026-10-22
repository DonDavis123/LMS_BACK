from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.lead_capture.application.dto.public_lead_form_dto import (
    PublicLeadSubmissionDTO,
)
from src.modules.lead_capture.application.use_cases.submit_public_lead import (
    NOT_ACCEPTING_MESSAGE,
    FormNotAcceptingResponses,
)
from src.modules.lead_capture.presentation.api.dependencies.lead_form_dependencies import (
    get_public_lead_form_use_case,
    get_submit_public_lead_use_case,
    resolve_public_form,
)

from ..serializers.public_lead_form import PublicLeadSubmissionSerializer


class PublicLeadFormView(APIView):
    # Public endpoint: never run JWT authentication here. A stale or
    # expired Bearer token would otherwise be rejected with 401 before
    # AllowAny is even consulted.
    authentication_classes = []
    permission_classes = [AllowAny]

    @staticmethod
    def _target(token: str):
        target = resolve_public_form(token)
        if target is None:
            raise NotFound()
        return target

    def get(self, request, token):
        target = self._target(token)
        form = get_public_lead_form_use_case(target.company_id).execute(
            company_name=target.company_name
        )
        # Exactly these three fields: no owners, lead source, ids or counters.
        return Response(
            {
                "title": form.title,
                "company_name": form.company_name,
                "accepting_responses": form.accepting_responses,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, token):
        target = self._target(token)

        serializer = PublicLeadSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            get_submit_public_lead_use_case(target.company_id).execute(
                PublicLeadSubmissionDTO(**serializer.validated_data)
            )
        except FormNotAcceptingResponses:
            return Response(
                {"detail": NOT_ACCEPTING_MESSAGE}, status=status.HTTP_410_GONE
            )

        # Never return the lead or any id.
        return Response(
            {"detail": "Thanks, we've received your details."},
            status=status.HTTP_201_CREATED,
        )
