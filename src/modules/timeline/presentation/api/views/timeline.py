from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from src.modules.timeline.presentation.api.dependencies.timeline_dependencies import get_timeline_use_case
from src.modules.timeline.presentation.api.serializers.timeline import TimelineEventSerializer


class TimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, entity_type: str, entity_id):
        try:
            result = get_timeline_use_case().execute(entity_type, entity_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(TimelineEventSerializer(result, many=True).data)
