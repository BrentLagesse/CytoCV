#!/bin/bash
set -e

echo "${0}: starting analysis worker..."
exec python manage.py run_analysis_worker
