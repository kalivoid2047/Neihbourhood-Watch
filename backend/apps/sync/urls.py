from django.urls import path

from .views import SyncPushView, SyncQueueView

urlpatterns = [
    path("sync/queue/", SyncQueueView.as_view(), name="sync-queue"),
    path("sync/push/", SyncPushView.as_view(), name="sync-push"),
]
