from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification, NotificationPreference
from .serializers import NotificationPreferenceSerializer, NotificationSerializer


class UserNotificationListView(generics.ListAPIView):
    """GET /api/me/notifications/ — paginated list for the authenticated user."""

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Notification.objects.filter(
                recipient=self.request.user,
                deleted_at__isnull=True,
            )
            .select_related("incident", "sos_alert")
            .order_by("-created_at")
        )


class NotificationReadView(APIView):
    """PATCH /api/notifications/{id}/read/ — mark a single notification as read."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            notif = Notification.objects.get(
                pk=pk,
                recipient=request.user,
                deleted_at__isnull=True,
            )
        except Notification.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if notif.status != Notification.Status.READ:
            notif.status = Notification.Status.READ
            notif.read_at = timezone.now()
            notif.save(update_fields=["status", "read_at", "updated_at", "last_modified_at"])

        return Response(NotificationSerializer(notif).data)


class NotificationDeleteView(APIView):
    """DELETE /api/notifications/{id}/ — soft-delete a notification."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        try:
            notif = Notification.objects.get(
                pk=pk,
                recipient=request.user,
                deleted_at__isnull=True,
            )
        except Notification.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        notif.deleted_at = timezone.now()
        notif.save(update_fields=["deleted_at", "updated_at", "last_modified_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPreferenceView(APIView):
    """GET|PATCH /api/me/notification-preferences/ — retrieve or update preferences."""

    permission_classes = [permissions.IsAuthenticated]

    def _get_or_create(self, user):
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        return pref

    def get(self, request):
        pref = self._get_or_create(request.user)
        return Response(NotificationPreferenceSerializer(pref).data)

    def patch(self, request):
        pref = self._get_or_create(request.user)
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
