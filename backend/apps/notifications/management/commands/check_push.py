"""Diagnose the push-notification pipeline.

    python manage.py check_push
    python manage.py check_push --send-to user@example.com

Checks each link in the chain separately, because they fail for different
reasons and the symptom on the phone ("no alarm") is identical for all of them.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import DeviceToken


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"


class Command(BaseCommand):
    help = "Check that push notifications are configured and can be delivered."

    def add_arguments(self, parser):
        parser.add_argument(
            "--send-to",
            metavar="EMAIL",
            help="Send a real test push to every active device of this user.",
        )

    def handle(self, *args, **options):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Push notification check"))
        self.stdout.write("")

        client = self._check_configuration()
        self._check_devices()

        recipient = options.get("send_to")
        if recipient:
            self._send_test(client, recipient)
        else:
            self.stdout.write("")
            self.stdout.write(
                f"{DIM}Tip: once a phone has signed in, send a real test push with"
                f"\n     python manage.py check_push --send-to you@example.com{RESET}"
            )
        self.stdout.write("")

    # ── Steps ────────────────────────────────────────────────────────────────

    def _check_configuration(self):
        from apps.notifications.fcm import FCMClient

        client = FCMClient()

        self._line("FCM_ENABLED", client.enabled, str(client.enabled))
        self._line("FCM_PROJECT_ID", bool(client.project_id), client.project_id or "(not set)")

        credentials_ok = bool(client.credentials_file)
        detail = client.credentials_file or "(not set)"
        if credentials_ok:
            import os

            if not os.path.exists(client.credentials_file):
                credentials_ok = False
                detail = f"{client.credentials_file}  → file does not exist"
            elif not os.access(client.credentials_file, os.R_OK):
                credentials_ok = False
                detail = f"{client.credentials_file}  → not readable by this user"
        self._line("FCM_CREDENTIALS_FILE", credentials_ok, detail)

        libraries_ok = True
        try:
            import google.oauth2.service_account  # noqa: F401
            import requests  # noqa: F401
        except ImportError as exc:
            libraries_ok = False
            self._line("Python libraries", False, f"{exc}  → pip install google-auth requests")
        if libraries_ok:
            self._line("Python libraries", True, "google-auth, requests")

        available = client.is_available()
        self.stdout.write("")
        if available:
            self.stdout.write(f"  {GREEN}Configuration looks complete.{RESET}")
            # Actually mint a token: a well-formed key for the wrong project,
            # or a revoked one, passes every check above and still fails here.
            try:
                client._access_token()
                self.stdout.write(f"  {GREEN}Authenticated with Google successfully.{RESET}")
            except Exception as exc:
                self.stdout.write(f"  {RED}Could not authenticate: {exc}{RESET}")
        else:
            self.stdout.write(
                f"  {YELLOW}Push is not active. The mobile app will still alarm, but on"
                f"\n  its own polling schedule — up to ~15 minutes late when backgrounded."
                f"\n  See docs/FIREBASE_SETUP.md.{RESET}"
            )

        return client

    def _check_devices(self):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Registered devices"))
        self.stdout.write("")

        active = DeviceToken.objects.filter(is_active=True)
        total = active.count()

        if not total:
            self.stdout.write(
                f"  {YELLOW}No active device tokens.{RESET}\n"
                f"  {DIM}A phone registers automatically when a user signs in. If none\n"
                f"  appear, the app could not reach POST /api/me/device-tokens —\n"
                f"  check the device log for lines starting 'PushService:'.{RESET}"
            )
            return

        self.stdout.write(f"  {GREEN}{total} active device token(s){RESET}")
        for platform in ("android", "ios", "web"):
            count = active.filter(platform=platform).count()
            if count:
                self.stdout.write(f"    {platform:<8} {count}")

        stale = active.filter(
            last_seen_at__lt=timezone.now() - timezone.timedelta(days=60)
        ).count()
        if stale:
            self.stdout.write(
                f"  {DIM}{stale} not seen in 60+ days — likely uninstalled.{RESET}"
            )

    def _send_test(self, client, email):
        from apps.accounts.models import User
        from apps.notifications.fcm import FCMUnavailable

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"Test push to {email}"))
        self.stdout.write("")

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            self.stdout.write(f"  {RED}No user with that email address.{RESET}")
            return

        devices = list(DeviceToken.objects.filter(user=user, is_active=True))
        if not devices:
            self.stdout.write(f"  {RED}That user has no active devices registered.{RESET}")
            return

        for device in devices:
            label = f"{device.platform}:{device.token[:18]}…"
            try:
                delivered, detail = client.send(
                    token=device.token,
                    data={
                        "kind": "test",
                        "title": "Test push",
                        "body": "If you can see this, push delivery works.",
                    },
                )
            except FCMUnavailable as exc:
                self.stdout.write(f"  {RED}✗{RESET} {label}  {exc}")
                return

            if delivered:
                self.stdout.write(f"  {GREEN}✓{RESET} {label}  accepted by FCM")
            else:
                self.stdout.write(f"  {RED}✗{RESET} {label}  {detail}")

        self.stdout.write("")
        self.stdout.write(
            f"  {DIM}'Accepted by FCM' means Google took the message, not that the\n"
            f"  phone displayed it. A test push is not an alarm — it carries\n"
            f"  kind=test, so the app logs it and does not sound a siren.{RESET}"
        )

    # ── Output helper ────────────────────────────────────────────────────────

    def _line(self, label, ok, detail):
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        self.stdout.write(f"  {mark} {label:<22} {DIM}{detail}{RESET}")
