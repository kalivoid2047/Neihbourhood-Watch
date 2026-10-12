"""Nearby incident visibility and SOS sirens.

- A reported incident shows up for anyone whose device is close by, member of
  the neighbourhood or not, and is pushed to their live map.
- A new SOS alarms users within SOS_ALERT_RADIUS_M, not those far away, and
  never the sender.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.incidents.models import Incident
from apps.notifications.models import Notification, NotificationPreference

PASSWORD = "ZimSecurePass123!"
HERE = (-17.829320, 31.052240)
FAR = (-17.929320, 31.052240)  # ~11 km south


def make_user(n, *, home=None, device=None, device_age=timedelta(minutes=1)):
    role, _ = Role.objects.get_or_create(
        code=Role.Code.RESIDENT, defaults={"name": "Resident", "is_system": True}
    )
    kwargs = {}
    if home:
        kwargs.update(latitude=home[0], longitude=home[1])
    if device:
        kwargs.update(
            last_latitude=device[0],
            last_longitude=device[1],
            last_location_at=timezone.now() - device_age,
        )
    return User.objects.create_user(
        email=f"user{n}@example.com",
        password=PASSWORD,
        full_name=f"User {n}",
        phone_number=f"+2637712{n:05d}",
        national_id=f"63-{n:07d}X47",
        role=role,
        **kwargs,
    )


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def report(client, severity="yellow"):
    return client.post(
        "/api/incidents/",
        {
            "title": "Broken window",
            "description": "Seen on the corner",
            "category": "vandalism",
            "severity": severity,
            "latitude": f"{HERE[0]:.6f}",
            "longitude": f"{HERE[1]:.6f}",
            "occurred_at": timezone.now().isoformat(),
        },
        format="json",
    )


class NearbyIncidentVisibilityTests(TestCase):
    def setUp(self):
        patcher = patch("apps.notifications.tasks.send_notifications_batch.delay")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.reporter = make_user(1, device=HERE)
        self.close = make_user(2, device=(HERE[0] + 0.005, HERE[1]))  # ~550 m
        self.far = make_user(3, device=FAR)

    def test_nearby_user_sees_incident_on_map_and_can_open_it(self):
        res = report(client_for(self.reporter))
        self.assertEqual(res.status_code, 201, res.content)
        incident_id = res.json()["id"]

        listing = client_for(self.close).get("/api/incidents/").json()
        ids = [i["id"] for i in listing.get("results", listing)]
        self.assertIn(incident_id, ids)
        self.assertEqual(client_for(self.close).get(f"/api/incidents/{incident_id}/").status_code, 200)

    def test_far_user_cannot_see_incident(self):
        incident_id = report(client_for(self.reporter)).json()["id"]
        listing = client_for(self.far).get("/api/incidents/").json()
        self.assertNotIn(incident_id, [i["id"] for i in listing.get("results", listing)])
        self.assertEqual(client_for(self.far).get(f"/api/incidents/{incident_id}/").status_code, 404)

    def test_stale_device_fix_falls_back_to_home(self):
        # Device fix is a day old and says "far"; home is right here.
        user = make_user(4, home=HERE, device=FAR, device_age=timedelta(days=1))
        self.assertEqual(user.effective_location(), HERE)

    def test_nearby_endpoint_includes_unjoined_neighbourhood_incidents(self):
        incident_id = report(client_for(self.reporter)).json()["id"]
        res = client_for(self.far).get(
            "/api/incidents/nearby/", {"latitude": HERE[0], "longitude": HERE[1], "radius_m": 1000}
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(incident_id, [i["id"] for i in res.json()])

    def test_new_incident_is_pushed_to_nearby_users_only(self):
        with patch("apps.core.broadcasting.broadcast_incident_nearby") as push:
            report(client_for(self.reporter))
        push.assert_called_once()
        recipients = set(push.call_args.args[1])
        self.assertIn(self.close.pk, recipients)
        self.assertNotIn(self.far.pk, recipients)
        self.assertNotIn(self.reporter.pk, recipients)

    def test_location_endpoint_updates_last_known_position(self):
        res = client_for(self.far).post(
            "/api/me/location", {"latitude": HERE[0], "longitude": HERE[1]}, format="json"
        )
        self.assertEqual(res.status_code, 204)
        self.far.refresh_from_db()
        self.assertEqual(self.far.effective_location(), HERE)

    def test_location_endpoint_rejects_garbage(self):
        res = client_for(self.far).post("/api/me/location", {"latitude": 99, "longitude": 0}, format="json")
        self.assertEqual(res.status_code, 400)


class SosSirenTests(TestCase):
    def setUp(self):
        # Delivery runs in Celery; these tests assert on what was queued.
        patcher = patch("apps.notifications.tasks.send_notifications_batch.delay")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sender = make_user(10, device=HERE)
        self.close = make_user(11, device=(HERE[0] + 0.005, HERE[1]))
        self.far = make_user(12, device=FAR)
        self.muted = make_user(13, device=(HERE[0] + 0.003, HERE[1]))
        NotificationPreference.objects.create(user=self.muted, sos_alerts=False)

    def trigger(self):
        return client_for(self.sender).post(
            "/api/sos/",
            {"current_latitude": f"{HERE[0]:.6f}", "current_longitude": f"{HERE[1]:.6f}"},
            format="json",
        )

    def test_sos_alarms_nearby_users_not_far_muted_or_sender(self):
        res = self.trigger()
        self.assertEqual(res.status_code, 201, res.content)
        alarmed = set(
            Notification.objects.filter(sos_alert_id=res.json()["id"], channel="dashboard").values_list(
                "recipient_id", flat=True
            )
        )
        self.assertEqual(alarmed, {self.close.pk})

    def test_sos_notification_is_critical_and_carries_location(self):
        self.trigger()
        notif = Notification.objects.get(recipient=self.close, channel="dashboard")
        self.assertEqual(notif.priority, "critical")
        self.assertEqual(notif.payload["kind"], "sos_alert")
        self.assertAlmostEqual(float(notif.payload["latitude"]), HERE[0], places=5)

    def test_sos_is_not_rate_limited(self):
        with patch("apps.notifications.services._RATE_LIMIT_MAX", 0):
            self.trigger()
        self.assertTrue(Notification.objects.filter(recipient=self.close, channel="dashboard").exists())

    def test_resolving_tells_alarmed_users_to_stop(self):
        alert_id = self.trigger().json()["id"]
        with patch("apps.core.broadcasting.broadcast_sos_ended") as ended:
            client_for(self.sender).post(f"/api/sos/{alert_id}/resolve/")
        ended.assert_called_once()
        self.assertEqual(set(ended.call_args.args[1]), {self.close.pk})
