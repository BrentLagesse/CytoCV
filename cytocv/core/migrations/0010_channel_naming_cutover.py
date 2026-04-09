from __future__ import annotations

from django.db import migrations


PROPERTY_KEY_RENAMES = {
    "stats_mcherry_width_px": "stats_red_line_width_px",
    "stats_mcherry_width_unit": "stats_red_line_width_unit",
    "stats_gfp_distance_px": "stats_cen_dot_distance_px",
    "stats_gfp_distance_threshold": "stats_cen_dot_distance_value",
    "stats_gfp_distance_mode": "stats_cen_dot_distance_mode",
    "stats_gfp_distance_unit": "stats_cen_dot_distance_unit",
}

CHANNEL_VALUE_RENAMES = {
    "DAPI": "Blue",
    "channel_blue": "Blue",
    "blue": "Blue",
    "mCherry": "Red",
    "channel_red": "Red",
    "red": "Red",
    "GFP": "Green",
    "channel_green": "Green",
    "green": "Green",
    "DIC": "DIC",
    "dic": "DIC",
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

        for channel_key in (
            "nuclear_cellular_contour_channel",
            "nuclear_cellular_measurement_channel",
        ):
            if channel_key not in rewritten:
                continue
            original = rewritten[channel_key]
            normalized = CHANNEL_VALUE_RENAMES.get(str(original), original)
            if normalized != original:
                rewritten[channel_key] = normalized
                changed = True

        if changed:
            cell_stat.properties = rewritten
            cell_stat.save(update_fields=["properties"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_analysisjob"),
    ]

    operations = [
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="line_gfp_intensity",
            new_name="line_green_intensity",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_contour_1_size",
            new_name="green_contour_1_size",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_contour_2_size",
            new_name="green_contour_2_size",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_contour_3_size",
            new_name="green_contour_3_size",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_to_mcherry_distance_1",
            new_name="green_to_red_distance_1",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_to_mcherry_distance_2",
            new_name="green_to_red_distance_2",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_to_mcherry_distance_3",
            new_name="green_to_red_distance_3",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="cellular_intensity_sum_DAPI",
            new_name="cellular_intensity_sum_blue",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="nucleus_intensity_sum_DAPI",
            new_name="nucleus_intensity_sum_blue",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="cytoplasmic_intensity_DAPI",
            new_name="cytoplasmic_intensity_blue",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="category_GFP_dot",
            new_name="category_cen_dot",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_dot_count",
            new_name="cen_dot_count",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_red_dot_distance",
            new_name="cen_red_dot_distance",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="mcherry_line_gfp_intensity",
            new_name="red_line_green_intensity",
        ),
        migrations.RenameField(
            model_name="cellstatistics",
            old_name="gfp_line_gfp_intensity",
            new_name="green_line_green_intensity",
        ),
        migrations.RunPython(_rewrite_properties, migrations.RunPython.noop),
    ]
