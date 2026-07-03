"""Run one artifact-maintenance sweep and exit."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.services.artifact_maintenance import run_artifact_maintenance


class Command(BaseCommand):
    """Expose artifact cleanup as an operator-invoked, single-sweep command."""

    help = "Run one CytoCV artifact-maintenance sweep."

    def handle(self, *args, **options):
        """Execute the same sweep used by the background worker once."""

        run_artifact_maintenance()
        self.stdout.write(self.style.SUCCESS("Artifact maintenance completed"))
