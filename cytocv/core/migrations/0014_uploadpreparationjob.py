from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
import core.models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_biorientation_split"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UploadPreparationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("job_uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("new_run_uuids", models.JSONField(default=list)),
                ("restored_run_uuids", models.JSONField(default=list)),
                ("valid_run_uuids", models.JSONField(default=list)),
                ("config_snapshot", models.JSONField(default=dict)),
                ("error_lines", models.JSONField(default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelling", "Cancelling"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("current_phase", models.CharField(default="Queued", max_length=64)),
                ("cancellation_requested", models.BooleanField(default=False)),
                ("failure_summary", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        default=core.models.get_guest_user,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        to_field="id",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
