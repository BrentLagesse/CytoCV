from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_green_red_intensity_total_max_average"),
    ]

    operations = [
        migrations.AddField(
            model_name="segmentedimage",
            name="cell_inclusion_mode",
            field=models.CharField(
                choices=[
                    ("cell_pairs_only", "Cell pairs only"),
                    ("single_cells_only", "Single cells only"),
                    (
                        "single_cells_and_cell_pairs",
                        "Single cells and cell pairs",
                    ),
                ],
                default="cell_pairs_only",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="cellstatistics",
            name="cell_type",
            field=models.CharField(
                choices=[
                    ("single_cell", "Single Cell"),
                    ("cell_pair", "Cell Pair"),
                    ("unknown", "Unknown"),
                ],
                default="unknown",
                max_length=16,
            ),
        ),
    ]
