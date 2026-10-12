"""Phase 5: Notification Engine — test suite.

Coverage
--------
* Provider layer (InApp, Push, SMS)
* NotificationDispatchService.dispatch(), dispatch_incident_alert(), dispatch_sos_alert()
* Preference gating and rate-limiting
* Celery tasks (send_notifications_batch, retry_failed_notifications, cleanup_old_notifications)
* REST API (list, read, delete, preferences)
"""

from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import DeviceToken, EmergencyContact, User
from apps.incidents.models import Incident
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership
from apps.notifications.models import Notification, NotificationPreference, NotificationTemplate
from apps.notifications.services import (
    InAppProvider,
    NotificationDispatchService,
    PushProvider,
    SMSProvider,
)
from apps.notifications.tasks import (
    cleanup_old_notifications,
    retry_failed_notifications,
    send_notifications_batch,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_UID = 0


def make_user(**kwargs):
    global _UID
    _UID += 1
    defaults = {
        "email": f"user{_UID}@test.invalid",
        "full_name": f"User {_UID}",
        "phone_number": f"+2637700{_UID:05d}",
        "national_id": f"63{_UID:07d}A00",
        "password": "TestPass123!",
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_notification(user, **kwargs):
    defaults = {
        "recipient": user,
        "channel": Notification.Channel.DASHBOARD,
        "title": "Test",
        "body": "Body",
        "status": Notification.Status.QUEUED,
        "priority": Notification.Priority.NORMAL,
    }
    defaults.update(kwargs)
    return Notification.objects.create(**defaults)


_HOOD = 0


def make_neighborhood(**kwargs):
    global _HOOD
    _HOOD += 1
    defaults = {
        "name": f"Hood {_HOOD}",
        "code": f"hood-{_HOOD}",
        "city": "Cape Town",
        "province": "Western Cape",
        "is_active": True,
    }
    defaults.update(kwargs)
    return Neighborhood.objects.create(**defaults)


def make_incident(reporter, neighborhood=None, **kwargs):
    defaults = {
        "reporter": reporter,
        "neighborhood": neighborhood,
        "title": "Test incident",
        "description": "desc",
        "category": Incident.Category.THEFT,
        "severity": Incident.Severity.YELLOW,
        "status": Incident.Status.VERIFIED,
        "latitude": "-33.924900",
        "longitude": "18.424100",
        "occurred_at": timezone.now(),
    }
    defaults.update(kwargs)
    return Incident.objects.create(**defaults)


# ──────────────────────────────────────────────────────────────────────────────
# Provider tests
# ──────────────────────────────────────────────────────────────────────────────

class InAppProviderTests(TestCase):
    def test_marks_sent(self):
        user = make_user()
        notif = make_notification(user)
        ok = InAppProvider().send(notif)
        notif.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(notif.status, Notification.Status.SENT)
        self.assertIsNotNone(notif.sent_at)


class PushProviderTests(TestCase):
    def test_fails_without_device_tokens(self):
        user = make_user()
        notif = make_notification(user, channel=Notification.Channel.PUSH)
        ok = PushProvider().send(notif)
        notif.refresh_from_db()
        self.assertFalse(ok)
        self.assertEqual(notif.status, Notification.Status.FAILED)
        self.assertIn("device tokens", notif.error_message)

    @staticmethod
    def _fake_fcm(delivered=True, detail="ok", available=True):
        """A stand-in FCM client, so tests never touch the network."""
        client = mock.MagicMock()
        client.is_available.return_value = available
        client.send.return_value = (delivered, detail)
        return client

    def test_succeeds_with_active_token(self):
        user = make_user()
        DeviceToken.objects.create(
            user=user,
            platform="android",
            token="fcm-token-abc",
            device_id="dev-1",
            is_active=True,
        )
        notif = make_notification(user, channel=Notification.Channel.PUSH)

        client = self._fake_fcm()
        with mock.patch("apps.notifications.fcm.FCMClient", return_value=client):
            ok = PushProvider().send(notif)

        notif.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(notif.status, Notification.Status.SENT)
        client.send.assert_called_once()
        self.assertEqual(client.send.call_args.kwargs["token"], "fcm-token-abc")

    def test_fails_when_fcm_is_not_configured(self):
        """A server without FCM credentials must report failure, not pretend.

        The previous stub marked these as sent, which made a silent
        misconfiguration look like successful delivery.
        """
        user = make_user()
        DeviceToken.objects.create(
            user=user, platform="android", token="fcm-token-xyz", is_active=True
        )
        notif = make_notification(user, channel=Notification.Channel.PUSH)

        client = self._fake_fcm(available=False)
        with mock.patch("apps.notifications.fcm.FCMClient", return_value=client):
            ok = PushProvider().send(notif)

        notif.refresh_from_db()
        self.assertFalse(ok)
        self.assertEqual(notif.status, Notification.Status.FAILED)
        self.assertIn("not configured", notif.error_message)

    def test_deactivates_tokens_that_fcm_reports_as_dead(self):
        user = make_user()
        device = DeviceToken.objects.create(
            user=user, platform="android", token="stale-token", is_active=True
        )
        notif = make_notification(user, channel=Notification.Channel.PUSH)

        client = self._fake_fcm(delivered=False, detail="UNREGISTERED")
        with mock.patch("apps.notifications.fcm.FCMClient", return_value=client):
            ok = PushProvider().send(notif)

        device.refresh_from_db()
        self.assertFalse(ok)
        self.assertFalse(device.is_active)

    def test_one_dead_device_does_not_block_the_others(self):
        user = make_user()
        DeviceToken.objects.create(
            user=user, platform="android", token="dead", is_active=True
        )
        DeviceToken.objects.create(
            user=user, platform="ios", token="live", is_active=True
        )
        notif = make_notification(user, channel=Notification.Channel.PUSH)

        client = mock.MagicMock()
        client.is_available.return_value = True
        client.send.side_effect = lambda token, **kwargs: (
            (False, "UNREGISTERED") if token == "dead" else (True, "ok")
        )

        with mock.patch("apps.notifications.fcm.FCMClient", return_value=client):
            ok = PushProvider().send(notif)

        notif.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(notif.status, Notification.Status.SENT)

    def test_payload_carries_the_incident_the_client_must_re_fetch(self):
        user = make_user()
        DeviceToken.objects.create(
            user=user, platform="android", token="tok", is_active=True
        )
        neighborhood = make_neighborhood()
        incident = make_incident(user, neighborhood, severity=Incident.Severity.RED)
        notif = make_notification(user, channel=Notification.Channel.PUSH)
        notif.incident = incident
        notif.save(update_fields=["incident"])

        client = self._fake_fcm()
        with mock.patch("apps.notifications.fcm.FCMClient", return_value=client):
            PushProvider().send(notif)

        data = client.send.call_args.kwargs["data"]
        self.assertEqual(data["kind"], "incident_alert")
        self.assertEqual(data["incident_id"], str(incident.pk))
        self.assertEqual(data["severity"], "red")

    def test_fails_without_recipient(self):
        notif = Notification.objects.create(
            recipient=None,
            channel=Notification.Channel.PUSH,
            title="T",
            body="B",
        )
        ok = PushProvider().send(notif)
        self.assertFalse(ok)


class SMSProviderTests(TestCase):
    def test_succeeds_with_phone_number(self):
        user = make_user(phone_number="+263771999001")
        notif = make_notification(user, channel=Notification.Channel.SMS)
        ok = SMSProvider().send(notif)
        notif.refresh_from_db()
        self.assertTrue(ok)
        self.assertEqual(notif.status, Notification.Status.SENT)

    def test_fails_without_phone(self):
        user = make_user()
        user.phone_number = ""
        user.save(update_fields=["phone_number"])
        notif = make_notification(user, channel=Notification.Channel.SMS)
        ok = SMSProvider().send(notif)
        notif.refresh_from_db()
        self.assertFalse(ok)
        self.assertIn("phone", notif.error_message)

    def test_uses_payload_phone_override(self):
        user = make_user()
        user.phone_number = ""
        user.save(update_fields=["phone_number"])
        notif = make_notification(
            user,
            channel=Notification.Channel.SMS,
            payload={"emergency_contact_phone": "+263771111222"},
        )
        ok = SMSProvider().send(notif)
        notif.refresh_from_db()
        self.assertTrue(ok)


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch service tests
# ──────────────────────────────────────────────────────────────────────────────

class DispatchServiceTests(TestCase):
    def setUp(self):
        self.user = make_user()

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_creates_notification(self, mock_delay):
        ids = NotificationDispatchService.dispatch(
            target_users=[self.user],
            title="Hello",
            body="World",
            channel=Notification.Channel.DASHBOARD,
        )
        self.assertEqual(len(ids), 1)
        notif = Notification.objects.get(pk=ids[0])
        self.assertEqual(notif.title, "Hello")
        self.assertEqual(notif.status, Notification.Status.QUEUED)
        mock_delay.assert_called_once_with(ids)

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_respects_channel_preference(self, mock_delay):
        pref = NotificationPreference.objects.create(
            user=self.user,
            dashboard_enabled=False,
        )
        ids = NotificationDispatchService.dispatch(
            target_users=[self.user],
            title="Hello",
            body="World",
            channel=Notification.Channel.DASHBOARD,
        )
        self.assertEqual(ids, [])
        mock_delay.assert_not_called()

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_respects_rate_limit(self, mock_delay):
        # Flood the window with existing notifications
        for _ in range(20):
            make_notification(self.user, channel=Notification.Channel.DASHBOARD)

        ids = NotificationDispatchService.dispatch(
            target_users=[self.user],
            title="Flood",
            body="Test",
            channel=Notification.Channel.DASHBOARD,
        )
        self.assertEqual(ids, [])

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_incident_alert_notifies_members(self, mock_delay):
        neighborhood = Neighborhood.objects.create(
            name="Test Hood",
            is_active=True,
        )
        member = make_user()
        NeighborhoodMembership.objects.create(
            neighborhood=neighborhood,
            user=member,
        )
        incident = Incident.objects.create(
            reporter=make_user(),
            neighborhood=neighborhood,
            title="Break-in",
            description="desc",
            category=Incident.Category.THEFT,
            severity=Incident.Severity.RED,
            status=Incident.Status.VERIFIED,
            latitude="0.0",
            longitude="0.0",
            occurred_at=timezone.now(),
        )
        NotificationDispatchService.dispatch_incident_alert(incident)
        notifs = Notification.objects.filter(recipient=member)
        self.assertGreaterEqual(notifs.count(), 1)

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_incident_alert_uses_template(self, mock_delay):
        neighborhood = Neighborhood.objects.create(name="Hood2", is_active=True)
        member = make_user()
        NeighborhoodMembership.objects.create(neighborhood=neighborhood, user=member)
        NotificationTemplate.objects.create(
            event_type=NotificationTemplate.EventType.INCIDENT_VERIFIED,
            title_template="Alert: {title}",
            body_template="Severity: {severity} at {address}",
            channels=[Notification.Channel.DASHBOARD],
            is_active=True,
        )
        incident = Incident.objects.create(
            reporter=make_user(),
            neighborhood=neighborhood,
            title="Vandalism",
            description="desc",
            category=Incident.Category.VANDALISM,
            severity=Incident.Severity.YELLOW,
            status=Incident.Status.VERIFIED,
            latitude="0.0",
            longitude="0.0",
            address="10 Test St",
            occurred_at=timezone.now(),
        )
        NotificationDispatchService.dispatch_incident_alert(incident)
        notif = Notification.objects.filter(recipient=member).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.title, "Alert: Vandalism")
        self.assertIn("10 Test St", notif.body)

    # ── Radius targeting ──────────────────────────────────────────────────
    #
    # Membership alone used to decide the audience, which meant a resident
    # standing 200 m from an incident heard nothing if they happened to be
    # registered to the neighbouring area.

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_alerts_a_nearby_non_member(self, mock_delay):
        neighborhood = make_neighborhood(alert_radius_m=5000)
        # ~600 m north of the incident, and not a member of its neighbourhood.
        neighbour = make_user(latitude="-33.919500", longitude="18.424100")
        incident = make_incident(make_user(), neighborhood)

        NotificationDispatchService.dispatch_incident_alert(incident)

        self.assertTrue(Notification.objects.filter(recipient=neighbour).exists())

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_does_not_alert_someone_far_away(self, mock_delay):
        neighborhood = make_neighborhood(alert_radius_m=5000)
        # ~33 km south — outside any sensible alarm radius.
        distant = make_user(latitude="-34.220000", longitude="18.424100")
        incident = make_incident(make_user(), neighborhood)

        NotificationDispatchService.dispatch_incident_alert(incident)

        self.assertFalse(Notification.objects.filter(recipient=distant).exists())

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_still_alerts_a_distant_member(self, mock_delay):
        """Membership remains a union with distance, not an intersection."""
        neighborhood = make_neighborhood(alert_radius_m=1000)
        member = make_user(latitude="-34.220000", longitude="18.424100")
        NeighborhoodMembership.objects.create(neighborhood=neighborhood, user=member)
        incident = make_incident(make_user(), neighborhood)

        NotificationDispatchService.dispatch_incident_alert(incident)

        self.assertTrue(Notification.objects.filter(recipient=member).exists())

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_reporter_is_not_alerted_about_their_own_report(self, mock_delay):
        neighborhood = make_neighborhood(alert_radius_m=5000)
        reporter = make_user(latitude="-33.924900", longitude="18.424100")
        NeighborhoodMembership.objects.create(neighborhood=neighborhood, user=reporter)
        incident = make_incident(reporter, neighborhood)

        NotificationDispatchService.dispatch_incident_alert(incident)

        self.assertFalse(Notification.objects.filter(recipient=reporter).exists())

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_respects_a_narrow_neighbourhood_radius(self, mock_delay):
        neighborhood = make_neighborhood(alert_radius_m=250)
        # ~600 m away: inside the 5 km default, outside this hood's 250 m.
        neighbour = make_user(latitude="-33.919500", longitude="18.424100")
        incident = make_incident(make_user(), neighborhood)

        NotificationDispatchService.dispatch_incident_alert(incident)

        self.assertFalse(Notification.objects.filter(recipient=neighbour).exists())

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_a_user_is_alerted_once_even_when_both_rules_match(self, mock_delay):
        """A nearby member must not get two copies of the same alert."""
        neighborhood = make_neighborhood(alert_radius_m=5000)
        member = make_user(latitude="-33.925000", longitude="18.424200")
        NeighborhoodMembership.objects.create(neighborhood=neighborhood, user=member)
        incident = make_incident(make_user(), neighborhood)

        NotificationDispatchService.dispatch_incident_alert(incident)

        dashboard = Notification.objects.filter(
            recipient=member, channel=Notification.Channel.DASHBOARD
        )
        self.assertEqual(dashboard.count(), 1)

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_incident_alert_no_neighborhood(self, mock_delay):
        incident = Incident.objects.create(
            reporter=self.user,
            neighborhood=None,
            title="No hood",
            description="desc",
            category=Incident.Category.THEFT,
            severity=Incident.Severity.YELLOW,
            status=Incident.Status.VERIFIED,
            latitude="0.0",
            longitude="0.0",
            occurred_at=timezone.now(),
        )
        # Should not raise, should not create notifications
        NotificationDispatchService.dispatch_incident_alert(incident)
        self.assertEqual(Notification.objects.count(), 0)

    @mock.patch("apps.notifications.tasks.send_notifications_batch.delay")
    def test_dispatch_sos_alert_notifies_emergency_contacts(self, mock_delay):
        from apps.sos.models import SOSAlert
        neighborhood = Neighborhood.objects.create(name="SOS Hood", is_active=True)
        sos_user = make_user()
        EmergencyContact.objects.create(
            user=sos_user,
            name="Jane Doe",
            phone_number="+263771555666",
            relationship="spouse",
            priority=1,
            can_receive_sos=True,
        )
        sos_alert = SOSAlert.objects.create(
            user=sos_user,
            neighborhood=neighborhood,
            current_latitude="0.0",
            current_longitude="0.0",
            started_at=timezone.now(),
        )
        NotificationDispatchService.dispatch_sos_alert(sos_alert)
        notifs = Notification.objects.filter(sos_alert=sos_alert)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.channel, Notification.Channel.SMS)
        self.assertEqual(notif.priority, Notification.Priority.CRITICAL)
        self.assertEqual(notif.payload["emergency_contact_phone"], "+263771555666")


# ──────────────────────────────────────────────────────────────────────────────
# Task tests
# ──────────────────────────────────────────────────────────────────────────────

class SendNotificationsBatchTaskTests(TestCase):
    def test_delivers_dashboard_notification(self):
        user = make_user()
        notif = make_notification(user)
        result = send_notifications_batch([str(notif.pk)])
        notif.refresh_from_db()
        self.assertEqual(notif.status, Notification.Status.SENT)
        self.assertEqual(result["sent"], 1)

    def test_skips_already_sent(self):
        user = make_user()
        notif = make_notification(user, status=Notification.Status.SENT)
        result = send_notifications_batch([str(notif.pk)])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["sent"], 0)

    def test_handles_unknown_channel_gracefully(self):
        user = make_user()
        notif = make_notification(user, channel="unknown")
        result = send_notifications_batch([str(notif.pk)])
        notif.refresh_from_db()
        self.assertEqual(notif.status, Notification.Status.FAILED)
        self.assertEqual(result["failed"], 1)


class RetryFailedNotificationsTaskTests(TestCase):
    def test_requeues_recent_failed(self):
        user = make_user()
        notif = make_notification(user, status=Notification.Status.FAILED)
        with mock.patch("apps.notifications.tasks.send_notifications_batch.delay") as mock_delay:
            result = retry_failed_notifications()
        self.assertEqual(result["requeued"], 1)
        notif.refresh_from_db()
        self.assertEqual(notif.status, Notification.Status.QUEUED)

    def test_skips_max_retried(self):
        user = make_user()
        notif = make_notification(user, status=Notification.Status.FAILED, retry_count=3)
        with mock.patch("apps.notifications.tasks.send_notifications_batch.delay"):
            result = retry_failed_notifications()
        self.assertEqual(result["requeued"], 0)

    def test_skips_old_failures(self):
        user = make_user()
        notif = make_notification(user, status=Notification.Status.FAILED)
        Notification.objects.filter(pk=notif.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        with mock.patch("apps.notifications.tasks.send_notifications_batch.delay"):
            result = retry_failed_notifications()
        self.assertEqual(result["requeued"], 0)


class CleanupOldNotificationsTaskTests(TestCase):
    def test_soft_deletes_old_notifications(self):
        user = make_user()
        notif = make_notification(user, status=Notification.Status.SENT)
        Notification.objects.filter(pk=notif.pk).update(
            created_at=timezone.now() - timedelta(days=91)
        )
        result = cleanup_old_notifications()
        self.assertEqual(result["deleted"], 1)
        notif.refresh_from_db()
        self.assertIsNotNone(notif.deleted_at)

    def test_spares_recent_notifications(self):
        user = make_user()
        make_notification(user, status=Notification.Status.SENT)
        result = cleanup_old_notifications()
        self.assertEqual(result["deleted"], 0)


# ──────────────────────────────────────────────────────────────────────────────
# API tests
# ──────────────────────────────────────────────────────────────────────────────

class NotificationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.other = make_user()
        self.client.force_authenticate(user=self.user)
        self.notif = make_notification(self.user)

    # list
    def test_list_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/me/notifications/")
        self.assertEqual(resp.status_code, 401)

    def test_list_returns_own_notifications(self):
        make_notification(self.other)  # should not appear
        resp = self.client.get("/api/me/notifications/")
        self.assertEqual(resp.status_code, 200)
        ids = [n["id"] for n in resp.data["results"] if "results" in resp.data] or [n["id"] for n in resp.data]
        self.assertIn(str(self.notif.pk), ids)
        self.assertEqual(len(ids), 1)

    def test_list_excludes_soft_deleted(self):
        self.notif.deleted_at = timezone.now()
        self.notif.save(update_fields=["deleted_at", "updated_at", "last_modified_at"])
        resp = self.client.get("/api/me/notifications/")
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get("results", resp.data)
        self.assertEqual(len(data), 0)

    # read
    def test_mark_as_read(self):
        resp = self.client.patch(f"/api/notifications/{self.notif.pk}/read/")
        self.assertEqual(resp.status_code, 200)
        self.notif.refresh_from_db()
        self.assertEqual(self.notif.status, Notification.Status.READ)
        self.assertIsNotNone(self.notif.read_at)

    def test_mark_read_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.patch(f"/api/notifications/{self.notif.pk}/read/")
        self.assertEqual(resp.status_code, 401)

    def test_cannot_mark_others_notification_as_read(self):
        other_notif = make_notification(self.other)
        resp = self.client.patch(f"/api/notifications/{other_notif.pk}/read/")
        self.assertEqual(resp.status_code, 404)

    # delete
    def test_soft_delete(self):
        resp = self.client.delete(f"/api/notifications/{self.notif.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.notif.refresh_from_db()
        self.assertIsNotNone(self.notif.deleted_at)

    def test_delete_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.delete(f"/api/notifications/{self.notif.pk}/")
        self.assertEqual(resp.status_code, 401)

    def test_cannot_delete_others_notification(self):
        other_notif = make_notification(self.other)
        resp = self.client.delete(f"/api/notifications/{other_notif.pk}/")
        self.assertEqual(resp.status_code, 404)


class NotificationPreferenceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def test_get_creates_default_preferences(self):
        resp = self.client.get("/api/me/notification-preferences/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["dashboard_enabled"])
        self.assertTrue(resp.data["push_enabled"])
        self.assertFalse(resp.data["sms_enabled"])

    def test_patch_updates_preference(self):
        resp = self.client.patch(
            "/api/me/notification-preferences/",
            {"sms_enabled": True, "push_enabled": False},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["sms_enabled"])
        self.assertFalse(resp.data["push_enabled"])

    def test_preferences_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get("/api/me/notification-preferences/")
        self.assertEqual(resp.status_code, 401)
