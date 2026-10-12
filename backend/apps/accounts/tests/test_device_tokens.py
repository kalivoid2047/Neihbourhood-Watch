"""Tests for the push device-token endpoint used by the mobile app.

The mobile client calls POST on every launch and on every FCM token rotation,
so the endpoint has to be idempotent, and it must handle a token moving between
users — which is what happens when a handset changes hands.
"""

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase

from apps.accounts.models import DeviceToken, User


PASSWORD = "ZimSecurePass123!"

_UID = 0


def make_user(**kwargs):
    global _UID
    _UID += 1
    defaults = {
        "email": f"device{_UID}@test.invalid",
        "full_name": f"Device User {_UID}",
        "phone_number": f"+2637711{_UID:05d}",
        "national_id": f"71{_UID:07d}B00",
        "password": PASSWORD,
    }
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class DeviceTokenEndpointTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = reverse("device-tokens")

    def test_registers_a_token(self):
        response = self.client.post(
            self.url,
            {"token": "fcm-abc", "platform": "android", "device_id": "pixel-7"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        device = DeviceToken.objects.get(token="fcm-abc")
        self.assertEqual(device.user, self.user)
        self.assertTrue(device.is_active)
        self.assertIsNotNone(device.last_seen_at)

    def test_re_registering_the_same_token_is_idempotent(self):
        payload = {"token": "fcm-abc", "platform": "android"}
        first = self.client.post(self.url, payload, format="json")
        second = self.client.post(self.url, payload, format="json")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(DeviceToken.objects.filter(token="fcm-abc").count(), 1)

    def test_a_token_moves_to_its_new_owner(self):
        """A handed-down handset must stop alerting its previous owner."""
        previous_owner = make_user()
        DeviceToken.objects.create(
            user=previous_owner, platform="android", token="shared-handset"
        )

        response = self.client.post(
            self.url, {"token": "shared-handset", "platform": "android"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        device = DeviceToken.all_objects.get(token="shared-handset")
        self.assertEqual(device.user, self.user)
        self.assertFalse(
            DeviceToken.objects.filter(user=previous_owner, is_active=True).exists()
        )

    def test_reactivates_a_previously_removed_token(self):
        DeviceToken.objects.create(
            user=self.user,
            platform="android",
            token="fcm-abc",
            is_active=False,
            deleted_at=timezone.now(),
        )

        self.client.post(self.url, {"token": "fcm-abc", "platform": "android"}, format="json")

        device = DeviceToken.all_objects.get(token="fcm-abc")
        self.assertTrue(device.is_active)
        self.assertIsNone(device.deleted_at)

    def test_rejects_an_empty_token(self):
        response = self.client.post(self.url, {"token": "   "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_removes_a_token_on_sign_out(self):
        DeviceToken.objects.create(user=self.user, platform="android", token="fcm-abc")

        response = self.client.delete(self.url, {"token": "fcm-abc"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Soft-deleted, so only `all_objects` can still see it.
        device = DeviceToken.all_objects.get(token="fcm-abc")
        self.assertFalse(device.is_active)
        self.assertIsNotNone(device.deleted_at)

    def test_cannot_remove_another_users_token(self):
        other = make_user()
        DeviceToken.objects.create(user=other, platform="android", token="not-mine")

        response = self.client.delete(self.url, {"token": "not-mine"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(DeviceToken.objects.get(token="not-mine").is_active)

    def test_requires_authentication(self):
        anonymous = APIClient()
        response = anonymous.post(self.url, {"token": "fcm-abc"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
