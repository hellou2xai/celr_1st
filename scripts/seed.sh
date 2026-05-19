#!/usr/bin/env bash
# Manual seed trigger. Render runs `python -m seed.seed` via preDeployCommand
# automatically; this script exists so you can re-run it from Render's Shell
# tab or from your laptop pointed at the same DATABASE_URL.
#
# Usage:
#   FORCE_RESEED=true ./scripts/seed.sh
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m seed.seed
