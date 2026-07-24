#!/usr/bin/env bash
# Backward-compatible Gemma-only entry point for the generic v5 launcher.
#
# Usage:
#   ./scripts/submit_v5_gemma.sh
#   DRY_RUN=1 ./scripts/submit_v5_gemma.sh
#   CELLS="english:en german:engex" ./scripts/submit_v5_gemma.sh
#   LIMIT=10 ./scripts/submit_v5_gemma.sh  # smoke test only
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export MODELS="${MODELS:-${MODEL:-gemma4:31b}}"
exec "$SCRIPT_DIR/submit_v5_models.sh"
