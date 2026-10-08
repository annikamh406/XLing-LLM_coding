#!/usr/bin/env bash
# Same frozen Qwen full/batch-5 experiment on preemptible, 48-GB GPU capacity.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PARTITION=gpu-scavenger
export ACCOUNT=gpu-scavenger
export RESUME=1
# Verify available node features with sinfo on Oscar; override when needed.
export GPU_CONSTRAINT="${GPU_CONSTRAINT:-l40s|a6000}"
export MIN_GPU_MEMORY_MIB="${MIN_GPU_MEMORY_MIB:-45000}"
# Isolate from queued condo attempts. Requeues reuse this same folder.
export RESULTS_DIR="${RESULTS_DIR:-v5/results/multilingual_production_pair_scavenger}"
exec bash "$SCRIPT_DIR/submit_v5_multilingual_qwen_full.sh" "$@"
