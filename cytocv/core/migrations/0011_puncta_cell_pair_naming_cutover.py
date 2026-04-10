from __future__ import annotations

from django.db import migrations


PROPERTY_KEY_RENAMES = {
    "stats_red_line_width_px": "stats_puncta_line_width_px",
    "stats_red_line_width_unit": "stats_puncta_line_width_unit",
    "nuclear_cellular_mode": "nuclear_cell_pair_mode",
    "nuclear_cellular_status": "nuclear_cell_pair_status",
    "nuclear_cellular_contour_channel": "nuclear_cell_pair_contour_channel",
    "nuclear_cellular_measurement_channel": "nuclear_cell_pair_measurement_channel",
    "nuclear_cellular_contour_source": "nuclear_cell_pair_contour_source",
}


def _rewrite_properties(apps, schema_editor):
    CellStatistics = apps.get_model("core", "CellStatistics")
    for cell_stat in CellStatistics.objects.iterator():
        properties = dict(cell_stat.properties or {})
        if not properties:
            continue

        rewritten = {}
        changed = False
        for key, value in properties.items():
            new_key = PROPERTY_KEY_RENAMES.get(key, key)
            if new_key != key:
                changed = True
            rewritten[new_key] = value

        if changed:
            cell_stat.properties = rewritten
            cell_stat.save(update_fields=["properties"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_channel_naming_cutover"),
    ]

    operations = [
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="distance",
            new_name="puncta_distance",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="line_green_intensity",
            new_name="puncta_line_intensity",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="green_to_red_distance_1",
            new_name="distance_of_green_from_red_1",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="green_to_red_distance_2",
            new_name="distance_of_green_from_red_2",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="green_to_red_distance_3",
            new_name="distance_of_green_from_red_3",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="cellular_intensity_sum",
            new_name="cell_pair_intensity_sum",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="cellular_intensity_sum_blue",
            new_name="cell_pair_intensity_sum_blue",
        ),
        migrations.RemoveField(
            model_name="cellstatistics",
            name="red_dot_distance",
        ),
        migrations.RemoveField(
            model_name="cellstatistics",
            name="cen_red_dot_distance",
        ),
        migrations.RemoveField(
            model_name="cellstatistics",
            name="red_line_green_intensity",
        ),
        migrations.RemoveField(
            model_name="cellstatistics",
            name="green_line_green_intensity",
        ),
        migrations.RunPython(_rewrite_properties, migrations.RunPython.noop),
    ]
