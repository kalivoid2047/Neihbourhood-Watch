import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add retry_count to the existing Notification model
        migrations.AddField(
            model_name="notification",
            name="retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        # NotificationPreference
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_modified_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("push_enabled", models.BooleanField(default=True)),
                ("sms_enabled", models.BooleanField(default=False)),
                ("dashboard_enabled", models.BooleanField(default=True)),
                ("incident_alerts", models.BooleanField(default=True)),
                ("sos_alerts", models.BooleanField(default=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["user"], name="notif_pref_user_idx")],
            },
        ),
        # NotificationTemplate
        migrations.CreateModel(
            name="NotificationTemplate",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_modified_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("incident_verified", "Incident Verified"),
                            ("incident_resolved", "Incident Resolved"),
                            ("incident_assigned", "Incident Assigned"),
                            ("sos_alert", "SOS Alert"),
                        ],
                        max_length=80,
                        unique=True,
                    ),
                ),
                ("title_template", models.CharField(max_length=220)),
                ("body_template", models.TextField()),
                (
                    "priority",
                    models.CharField(
                        choices=[
                            ("low", "Low"),
                            ("normal", "Normal"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        default="normal",
                        max_length=16,
                    ),
                ),
                ("channels", models.JSONField(default=list)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["event_type", "is_active"], name="notif_tmpl_event_idx"),
                ],
            },
        ),
    ]
