from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    """Choice-only metadata update for the mother/daughter CEN dot semantics.

    No data migration: historical rows keep their integer codes, but the
    schema-aware label helper surfaces a rerun-required label for legacy values.
    """

    dependencies = [
        ("core", "0011_puncta_cell_pair_naming_cutover"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cellstatistics",
            name="category_cen_dot",
            field=models.IntegerField(
                choices=[
                    (1, "Mother and daughter"),
                    (2, "Mother only"),
                    (3, "Daughter only"),
                    (4, "N/A"),
                ],
                default=4,
            ),
        ),
    ]
