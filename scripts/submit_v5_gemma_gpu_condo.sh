#!/usr/bin/env bash
# Duplicate only the ten L40S conditions on the user's regular condo.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PARTITION=l40s-gcondo
# Use the normal default account unless CONDO_ACCOUNT is explicitly set.
export ACCOUNT="${CONDO_ACCOUNT:-}"
export QOS=copsy-l40s-gcondo
export GPU_TYPES=l40s
export RESULTS_DIR="${RESULTS_DIR:-v5/results/gemma_gpu_comparison_condo}"
exec bash "$SCRIPT_DIR/submit_v5_gemma_gpu_comparison.sh" "$@"
