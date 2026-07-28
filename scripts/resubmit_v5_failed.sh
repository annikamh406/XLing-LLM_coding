#!/usr/bin/env bash
# Resubmit only the incomplete v5 cells from the 2026-07-24 model sweep.
#
# - GPT-OSS: Hebrew, Spanish, and Tagalog failed because Slurm exposed no GPUs.
#   Keep the original prompt and batch size 5 for a directly comparable rerun.
# - Qwen 3.6: Tagalog duplicated one record ID in a size-5 batch. Batch size 1
#   makes duplicate IDs impossible while retaining the original prompt and
#   deterministic decoding.
#
# Inspect without submitting:
#   DRY_RUN=1 ./scripts/resubmit_v5_failed.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
status=0

if ! env \
    MODELS="gpt-oss:120b" \
    CELLS="hebrew:engex spanish:engex tagalog:engex" \
    BATCH_SIZE=5 \
    LIMIT="" \
    SPLIT=dev_train \
    RUN_SETS=unmasked \
    RESULTS_DIR=v5/results \
    LOG_DIR=v5/results/logs \
    PROMPT_OVERRIDE="" \
    PROMPT_VERSION_OVERRIDE="" \
    WALLTIME="${GPT_WALLTIME:-24:00:00}" \
    "$SCRIPT_DIR/submit_v5_models.sh"; then
  echo "ERROR: at least one GPT-OSS rerun was not submitted." >&2
  status=1
fi

if ! env \
    MODELS="qwen3.6:35b-a3b" \
    CELLS="tagalog:engex" \
    BATCH_SIZE=1 \
    LIMIT="" \
    SPLIT=dev_train \
    RUN_SETS=unmasked \
    RESULTS_DIR=v5/results \
    LOG_DIR=v5/results/logs \
    PROMPT_OVERRIDE="" \
    PROMPT_VERSION_OVERRIDE="" \
    WALLTIME="${QWEN_WALLTIME:-24:00:00}" \
    "$SCRIPT_DIR/submit_v5_models.sh"; then
  echo "ERROR: the Qwen 3.6 Tagalog rerun was not submitted." >&2
  status=1
fi

exit "$status"
