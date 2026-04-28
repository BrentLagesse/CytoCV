"""Run one artifact-maintenance sweep and exit."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core.services.artifact_maintenance import run_artifact_maintenance


class Command(BaseCommand):
    help = "Run one CytoCV artifact-maintenance sweep."

    def handle(self, *args, **options):
        run_artifact_maintenance()
        self.stdout.write(self.style.SUCCESS("Artifact maintenance completed"))
