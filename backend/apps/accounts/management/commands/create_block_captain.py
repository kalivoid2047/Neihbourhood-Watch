from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.neighborhoods.models import Neighborhood, NeighborhoodMembership


class Command(BaseCommand):
    help = (
        "Create a block captain, or promote an existing account to one. "
        "Captains sign in on the normal login page with their email and password."
    )

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", help="Required when creating a new account.")
        parser.add_argument("--full-name", default="")
        parser.add_argument("--phone", default="")
        parser.add_argument("--national-id", default="")
        parser.add_argument(
            "--neighborhood",
            help="Neighbourhood code to join as block captain, so its incidents show on their map.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        role, _ = Role.objects.get_or_create(
            code=Role.Code.BLOCK_CAPTAIN,
            defaults={"name": Role.Code.BLOCK_CAPTAIN.label, "is_system": True},
        )
        email = User.objects.normalize_email(options["email"])

        neighborhood = None
        if options["neighborhood"]:
            try:
                neighborhood = Neighborhood.objects.get(code=options["neighborhood"])
            except Neighborhood.DoesNotExist as exc:
                raise CommandError(f"No neighbourhood with code '{options['neighborhood']}'.") from exc

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            missing = [
                flag
                for flag, key in (
                    ("--password", "password"),
                    ("--full-name", "full_name"),
                    ("--phone", "phone"),
                    ("--national-id", "national_id"),
                )
                if not options[key]
            ]
            if missing:
                raise CommandError(f"Creating a new account also needs: {', '.join(missing)}")
            user = User.objects.create_user(
                email=email,
                password=options["password"],
                full_name=options["full_name"],
                phone_number=options["phone"],
                national_id=options["national_id"],
            )
            verb = "Created"
        else:
            if options["password"]:
                user.set_password(options["password"])
            verb = "Promoted"

        user.role = role
        user.verification_status = User.VerificationStatus.APPROVED
        user.otp_verified_at = user.otp_verified_at or timezone.now()
        user.is_active = True
        user.save()

        if neighborhood:
            NeighborhoodMembership.objects.update_or_create(
                user=user,
                neighborhood=neighborhood,
                deleted_at__isnull=True,
                defaults={"role": NeighborhoodMembership.Role.BLOCK_CAPTAIN},
            )

        self.stdout.write(self.style.SUCCESS(f"{verb} block captain {user.email}."))
