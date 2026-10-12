from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import SyncQueue
from .serializers import SyncPushSerializer, SyncQueueSerializer
from .services import SyncPushService


class SyncQueueView(generics.ListAPIView):
    """GET /api/sync/queue/ — return failed/conflict/pending items for the authenticated user.

    Clients poll this endpoint to discover mutations that need manual
    resolution (conflict) or have errored out (failed).
    """

    serializer_class = SyncQueueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        qs = SyncQueue.objects.filter(user=self.request.user, deleted_at__isnull=True).order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class SyncPushView(APIView):
    """POST /api/sync/push/ — apply a batch of offline mutations.

    Accepts a JSON body ``{"items": [...]}`` where each item is an offline
    mutation.  Returns per-item results so the client knows which mutations
    were applied, which conflicted, and which failed.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = SyncPushSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = SyncPushService.push(request.user, serializer.validated_data["items"])
        return Response({"results": results}, status=status.HTTP_200_OK)
