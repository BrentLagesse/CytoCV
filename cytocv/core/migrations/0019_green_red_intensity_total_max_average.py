from django.db import migrations, models


INTENSITY_FIELD_RENAMES = (
    ("red_intensity_1", "red_in_red_total_intensity_1"),
    ("red_intensity_2", "red_in_red_total_intensity_2"),
    ("red_intensity_3", "red_in_red_total_intensity_3"),
    ("green_intensity_1", "green_in_red_total_intensity_1"),
    ("green_intensity_2", "green_in_red_total_intensity_2"),
    ("green_intensity_3", "green_in_red_total_intensity_3"),
    ("red_in_green_intensity_1", "red_in_green_total_intensity_1"),
    ("red_in_green_intensity_2", "red_in_green_total_intensity_2"),
    ("red_in_green_intensity_3", "red_in_green_total_intensity_3"),
    ("green_in_green_intensity_1", "green_in_green_total_intensity_1"),
    ("green_in_green_intensity_2", "green_in_green_total_intensity_2"),
    ("green_in_green_intensity_3", "green_in_green_total_intensity_3"),
)

INTENSITY_PREFIXES = (
    "red_in_red",
    "green_in_red",
    "red_in_green",
    "green_in_green",
)


def nullable_intensity_field():
    return models.FloatField(blank=True, default=None, null=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_expand_image_path_field_lengths"),
    ]

    operations = []

    for old_name, new_name in INTENSITY_FIELD_RENAMES:
        operations.append(
            migrations.RenameField(
                model_name="cellstatistics",
                old_name=old_name,
                new_name=new_name,
            )
        )
        operations.append(
            migrations.AlterField(
                model_name="cellstatistics",
                name=new_name,
                field=nullable_intensity_field(),
            )
        )

    for prefix in INTENSITY_PREFIXES:
        for index in range(1, 4):
            for statistic in ("max", "average"):
                operations.append(
                    migrations.AddField(
                        model_name="cellstatistics",
                        name=f"{prefix}_{statistic}_intensity_{index}",
                        field=nullable_intensity_field(),
                    )
                )
