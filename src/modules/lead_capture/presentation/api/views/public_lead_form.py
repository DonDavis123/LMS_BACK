from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ParseError
from rest_framework.parsers import JSONParser
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
from ..throttles import PublicLeadFormThrottle

# Far above any valid submission (the field limits add up to ~2.5 KB).
MAX_BODY_BYTES = 10 * 1024


class RequestBodyTooLarge(APIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    default_detail = "The request is too large."
    default_code = "request_too_large"


class PublicLeadFormView(APIView):
    # Public endpoint: never run JWT authentication here. A stale or
    # expired Bearer token would otherwise be rejected with 401 before
    # AllowAny is even consulted.
    authentication_classes = []
    permission_classes = [AllowAny]
    # JSON only; anything else is answered 415.
    parser_classes = [JSONParser]
    # POST and GET use different scopes, see PublicLeadFormThrottle.
    throttle_classes = [PublicLeadFormThrottle]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # Runs before the handler, i.e. before the body is read or parsed.
        # Only the declared Content-Length is checked here; a body sent
        # without one (chunked) is not caught by this check.
        declared = request.META.get("CONTENT_LENGTH")
        if declared:
            try:
                size = int(declared)
            except ValueError:
                raise ParseError("Invalid Content-Length header.")
            if size > MAX_BODY_BYTES:
                raise RequestBodyTooLarge()

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
