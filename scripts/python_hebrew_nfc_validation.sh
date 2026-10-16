#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == scripts/run_bloom_coding.py ]]; then
  shift
  exec python3 scripts/run_hebrew_nfc_validation.py "$@"
fi
exec python3 "$@"
