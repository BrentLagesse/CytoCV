from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_uploadedimage_scale_info"),
    ]

    operations = [
        migrations.AddField(
            model_name="uploadedimage",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
    ]
