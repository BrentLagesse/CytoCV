from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_cen_dot_mother_daughter_choices"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="cellstatistics",
            name="biorientation",
        ),
        migrations.AddField(
            model_name="cellstatistics",
            name="colinear_dots",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="cellstatistics",
            name="off_axis_dots",
            field=models.IntegerField(default=0),
        ),
    ]
