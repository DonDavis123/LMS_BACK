from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.authentication.application.authorization.lead_permissions import (
    LeadPermissions,
)
from src.modules.mailing.application.dto.resolve_recipients import (
    FilterSelection,
    ResolveRecipientsCommand,
)
from src.modules.mailing.domain.enums.mail_entity import MailEntity
from src.modules.mailing.presentation.api.dependencies.mail_dependencies import (
    get_resolve_mail_recipients_use_case,
)
from src.modules.mailing.presentation.api.serializers import (
    ResolveRecipientsRequestSerializer,
    ResolveRecipientsResponseSerializer,
    validation_detail,
)
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context


class ResolveMailRecipientsView(APIView):
    """``POST /api/mail/recipients/resolve/``

    Read rules, mirrored from the existing screens:

    * contacts, accounts: any company user (their list and detail views).
    * leads, filter selection: admins only, as the lead list
      (``LeadPermissions.can_view_all_leads``).
    * leads, ids selection: any company user, as the lead detail view.
    """

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def post(self, request):
        ctx = get_tenant_context(request)

        serializer = ResolveRecipientsRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": validation_detail(serializer.errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data

        entity = MailEntity(data["entity"])
        selection = data["selection"]

        if (
            entity is MailEntity.LEADS
            and isinstance(selection, FilterSelection)
            and not LeadPermissions.can_view_all_leads(request.user)
        ):
            raise PermissionDenied("You do not have permission to view leads.")

        command = ResolveRecipientsCommand(
            selection=selection,
            include_secondary_email=data["include_secondary_email"],
            batch_size=data["batch_size"],
        )

        try:
            result = get_resolve_mail_recipients_use_case(entity, ctx).execute(command)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ResolveRecipientsResponseSerializer(result).data,
            status=status.HTTP_200_OK,
        )
