"""Phase 6: Sync API tests."""

import uuid
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.incidents.models import Incident
from apps.neighborhoods.models import Neighborhood
from apps.sync.models import SyncQueue

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_UID = 0


def make_neighborhood(name="Hood", **kwargs):
    global _UID
    _UID += 1
    return Neighborhood.objects.create(name=name, code=f"hood-{_UID}", city="Harare", province="Harare", **kwargs)


def make_user(**kwargs):
    global _UID
    _UID += 1
    return User.objects.create_user(
        email=f"sync{_UID}@test.invalid",
        full_name=f"Sync User {_UID}",
        phone_number=f"+2637702{_UID:05d}",
        national_id=f"83{_UID:07d}A00",
        password="Pass123!",
        **kwargs,
    )


def make_incident(user, **kwargs):
    defaults = {
        "reporter": user,
        "title": "Sync Incident",
        "description": "desc",
        "category": Incident.Category.THEFT,
        "severity": Incident.Severity.YELLOW,
        "status": Incident.Status.PENDING,
        "latitude": "0.0",
        "longitude": "0.0",
        "occurred_at": timezone.now(),
    }
    defaults.update(kwargs)
    return Incident.objects.create(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# SyncQueue list endpoint
# ──────────────────────────────────────────────────────────────────────────────

class SyncQueueListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/sync/queue/")
        self.assertEqual(resp.status_code, 401)

    def test_empty_queue(self):
        resp = self.client.get("/api/sync/queue/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 0)

    def test_returns_own_items_only(self):
        other = make_user()
        SyncQueue.objects.create(
            user=self.user,
            entity_type="incident",
            entity_id=uuid.uuid4(),
            operation=SyncQueue.Operation.CREATE,
            local_modified_at=timezone.now(),
            idempotency_key="key-own",
            status=SyncQueue.Status.FAILED,
        )
        SyncQueue.objects.create(
            user=other,
            entity_type="incident",
            entity_id=uuid.uuid4(),
            operation=SyncQueue.Operation.CREATE,
            local_modified_at=timezone.now(),
            idempotency_key="key-other",
            status=SyncQueue.Status.FAILED,
        )
        resp = self.client.get("/api/sync/queue/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["idempotency_key"], "key-own")

    def test_filter_by_status(self):
        SyncQueue.objects.create(
            user=self.user,
            entity_type="incident",
            entity_id=uuid.uuid4(),
            operation=SyncQueue.Operation.CREATE,
            local_modified_at=timezone.now(),
            idempotency_key="key-pending",
            status=SyncQueue.Status.PENDING,
        )
        SyncQueue.objects.create(
            user=self.user,
            entity_type="incident",
            entity_id=uuid.uuid4(),
            operation=SyncQueue.Operation.CREATE,
            local_modified_at=timezone.now(),
            idempotency_key="key-failed",
            status=SyncQueue.Status.FAILED,
        )
        resp = self.client.get("/api/sync/queue/?status=failed")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["idempotency_key"], "key-failed")


# ──────────────────────────────────────────────────────────────────────────────
# SyncPush endpoint
# ──────────────────────────────────────────────────────────────────────────────

@mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
class SyncPushTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def _push(self, items):
        return self.client.post("/api/sync/push/", {"items": items}, format="json")

    def test_requires_auth(self, _mock):
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/sync/push/", {"items": []}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_empty_items_rejected(self, _mock):
        resp = self._push([])
        self.assertEqual(resp.status_code, 400)

    def test_create_incident_synced(self, _mock):
        entity_id = uuid.uuid4()
        resp = self._push([
            {
                "entity_type": "incident",
                "entity_id": str(entity_id),
                "operation": "create",
                "payload": {
                    "title": "Offline Incident",
                    "description": "happened offline",
                    "category": "theft",
                    "severity": "yellow",
                    "latitude": "0.0",
                    "longitude": "0.0",
                    "occurred_at": timezone.now().isoformat(),
                },
                "local_modified_at": timezone.now().isoformat(),
                "idempotency_key": f"create-{entity_id}",
            }
        ])
        self.assertEqual(resp.status_code, 200)
        result = resp.data["results"][0]
        self.assertEqual(result["status"], "synced")
        self.assertTrue(Incident.objects.filter(pk=entity_id).exists())

    def test_create_incident_idempotent(self, _mock):
        entity_id = uuid.uuid4()
        key = f"idem-{entity_id}"
        item = {
            "entity_type": "incident",
            "entity_id": str(entity_id),
            "operation": "create",
            "payload": {
                "title": "Idempotent",
                "description": "desc",
                "category": "theft",
                "severity": "yellow",
                "latitude": "0.0",
                "longitude": "0.0",
                "occurred_at": timezone.now().isoformat(),
            },
            "local_modified_at": timezone.now().isoformat(),
            "idempotency_key": key,
        }
        self._push([item])
        resp = self._push([item])
        self.assertEqual(resp.status_code, 200)
        result = resp.data["results"][0]
        self.assertIn(result["status"], ("synced", "already_synced"))
        self.assertEqual(Incident.objects.filter(title="Idempotent").count(), 1)

    def test_update_incident_synced(self, _mock):
        incident = make_incident(self.user)
        resp = self._push([
            {
                "entity_type": "incident",
                "entity_id": str(incident.pk),
                "operation": "update",
                "payload": {"title": "Updated Offline"},
                "local_modified_at": timezone.now().isoformat(),
                "idempotency_key": f"update-{incident.pk}",
            }
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "synced")
        incident.refresh_from_db()
        self.assertEqual(incident.title, "Updated Offline")

    def test_update_conflict_detected(self, _mock):
        incident = make_incident(self.user)
        past_time = timezone.now() - __import__("datetime").timedelta(hours=1)
        resp = self._push([
            {
                "entity_type": "incident",
                "entity_id": str(incident.pk),
                "operation": "update",
                "payload": {"title": "Stale Update"},
                "local_modified_at": past_time.isoformat(),
                "idempotency_key": f"conflict-{incident.pk}",
            }
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "conflict")
        incident.refresh_from_db()
        self.assertNotEqual(incident.title, "Stale Update")

    def test_delete_incident_synced(self, _mock):
        incident = make_incident(self.user)
        resp = self._push([
            {
                "entity_type": "incident",
                "entity_id": str(incident.pk),
                "operation": "delete",
                "payload": {},
                "local_modified_at": timezone.now().isoformat(),
                "idempotency_key": f"delete-{incident.pk}",
            }
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "synced")
        incident.refresh_from_db()
        self.assertIsNotNone(incident.deleted_at)

    def test_unknown_entity_type_stored_as_pending(self, _mock):
        resp = self._push([
            {
                "entity_type": "custom_sensor",
                "entity_id": str(uuid.uuid4()),
                "operation": "create",
                "payload": {"reading": 42},
                "local_modified_at": timezone.now().isoformat(),
                "idempotency_key": "sensor-001",
            }
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "pending")
        self.assertTrue(SyncQueue.objects.filter(idempotency_key="sensor-001").exists())

    def test_update_nonexistent_incident_fails(self, _mock):
        resp = self._push([
            {
                "entity_type": "incident",
                "entity_id": str(uuid.uuid4()),
                "operation": "update",
                "payload": {"title": "ghost"},
                "local_modified_at": timezone.now().isoformat(),
                "idempotency_key": "update-ghost-001",
            }
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["results"][0]["status"], "failed")


# ──────────────────────────────────────────────────────────────────────────────
# Analytics endpoint
# ──────────────────────────────────────────────────────────────────────────────

class AnalyticsListTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/analytics/")
        self.assertEqual(resp.status_code, 401)

    def test_empty_response(self):
        resp = self.client.get("/api/analytics/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 0)

    def test_snapshot_appears_in_list(self):
        from apps.analytics.models import AnalyticsSnapshot
        hood = make_neighborhood("Analytics Hood")
        AnalyticsSnapshot.objects.create(
            snapshot_type="daily_risk",
            neighborhood=hood,
            period_start=timezone.now() - __import__("datetime").timedelta(days=1),
            period_end=timezone.now(),
            metrics={"total": 5},
        )
        resp = self.client.get("/api/analytics/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["snapshot_type"], "daily_risk")

    def test_filter_by_neighborhood(self):
        from apps.analytics.models import AnalyticsSnapshot
        hood1 = make_neighborhood("Hood A")
        hood2 = make_neighborhood("Hood B")
        for hood in (hood1, hood2):
            AnalyticsSnapshot.objects.create(
                snapshot_type="daily_risk",
                neighborhood=hood,
                period_start=timezone.now() - __import__("datetime").timedelta(days=1),
                period_end=timezone.now(),
                metrics={},
            )
        resp = self.client.get(f"/api/analytics/?neighborhood={hood1.pk}")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 1)
