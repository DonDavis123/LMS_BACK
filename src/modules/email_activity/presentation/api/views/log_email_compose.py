from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.email_activity.application.dto.log_email_compose import (
    LogEmailComposeCommand,
)
from src.modules.email_activity.presentation.api.dependencies.email_activity_dependencies import (
    get_log_email_compose_use_case,
)
from src.modules.email_activity.presentation.api.serializers import (
    LogEmailComposeRequestSerializer,
    LogEmailComposeResponseSerializer,
    validation_detail,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context


class LogEmailComposeView(APIView):
    """``POST /api/email-activity/compose/``

    Records "email opened in Gmail" on the timeline of each target record.

    Read rules, mirrored from the existing screens: a user may log against
    every record they may open, so any company user for contacts and for
    leads (the lead detail view has no role check; only the lead LIST is
    admin-only, as in ``mailing``'s ids selection). Records of other
    companies, soft-deleted or missing records are answered as ``not_found``.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request):
        ctx = get_tenant_context(request)

        serializer = LogEmailComposeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": validation_detail(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data

        # The actor is the authenticated user; nothing about it is read from the body.
        command = LogEmailComposeCommand(
            actor_id=ctx.user_id,
            actor_name=(request.user.name or request.user.email),
            client_ref=data["client_ref"],
            channel=data["channel"],
            targets=data["targets"],
            subject=data.get("subject"),
            batch_index=data.get("batch_index"),
            batch_total=data.get("batch_total"),
        )

        try:
            result = get_log_email_compose_use_case(ctx).execute(command)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            LogEmailComposeResponseSerializer(result).data,
            status=status.HTTP_201_CREATED if result.logged else status.HTTP_200_OK,
        )
