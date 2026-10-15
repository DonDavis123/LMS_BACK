from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.timeline.presentation.api.dependencies.timeline_dependencies import get_timeline_use_case
from src.modules.timeline.presentation.api.serializers.timeline import TimelineEventSerializer
from src.modules.shared.presentation.permissions import IsCompanyUser
from src.modules.shared.presentation.tenant import get_tenant_context


class TimelineView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request, entity_type: str, entity_id):
        try:
            result = get_timeline_use_case(get_tenant_context(request)).execute(entity_type, entity_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(TimelineEventSerializer(result, many=True).data)
