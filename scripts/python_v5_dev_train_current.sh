#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == scripts/run_bloom_coding.py ]]; then
  shift
  exec python3 scripts/run_v5_dev_train_current.py "$@"
fi
exec python3 "$@"
