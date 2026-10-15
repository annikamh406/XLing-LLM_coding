#!/usr/bin/env bash
# Eight requests on one L40S; every cell gets a fresh server and separate evidence.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/check_v5_validation_freeze.py
mkdir -p v5/results/hebrew_parser_diagnostic/logs
args=(sbatch --partition=l40s-gcondo --qos=copsy-l40s-gcondo --constraint=l40s
  --gres=gpu:1 --ntasks=1 --cpus-per-task=4 --mem=48g --time=06:00:00
  --signal=B:TERM@60 --job-name=qwen-he-parser
  --output=v5/results/hebrew_parser_diagnostic/logs/sbatch_%j.out)
[[ -z "${CONDO_ACCOUNT:-}" ]] || args+=(--account="$CONDO_ACCOUNT")
args+=(scripts/sbatch_qwen_hebrew_diagnostic.sh)
if [[ -n "${DRY_RUN:-}" ]]; then printf 'DRY:';printf ' %q' "${args[@]}";printf '\n';else "${args[@]}";fi
