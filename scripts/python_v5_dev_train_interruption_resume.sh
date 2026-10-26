#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == scripts/run_bloom_coding.py ]]; then
  shift
  exec python3 scripts/run_v5_dev_train_interruption_resume.py "$@"
fi
exec python3 "$@"
