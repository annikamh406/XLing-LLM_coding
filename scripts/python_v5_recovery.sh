#!/usr/bin/env bash
# Redirect only Qwen inference; runtime capture and other Python calls stay normal.
set -euo pipefail
if [[ "${1:-}" == scripts/run_bloom_coding.py && "${MODEL:-}" == qwen3.6:35b-a3b ]]; then
  shift
  exec "${VALIDATION_PYTHON:-python3}" scripts/run_v5_validation_recovery.py "$@"
fi
exec "${VALIDATION_PYTHON:-python3}" "$@"
