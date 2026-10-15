#!/usr/bin/env bash
# Six diagnostic requests: three input representations, two T=0 repeats each.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 scripts/check_v5_validation_freeze.py
mkdir -p v5/results/hebrew_parser_diagnostic/logs
for variant in original compose-o-macron nfc; do
  args=(sbatch --partition=l40s-gcondo --qos=copsy-l40s-gcondo --constraint=l40s
    --gres=gpu:1 --ntasks=1 --cpus-per-task=4 --mem=48g --time=02:00:00
    --signal=B:TERM@60 --job-name="qwen-he-$variant"
    --output=v5/results/hebrew_parser_diagnostic/logs/sbatch_%j.out)
  [[ -z "${CONDO_ACCOUNT:-}" ]] || args+=(--account="$CONDO_ACCOUNT")
  args+=(scripts/sbatch_qwen_hebrew_diagnostic.sh --input-variant "$variant"
    --cells t0-buffered-r1 t0-buffered-r2)
  if [[ -n "${DRY_RUN:-}" ]]; then printf 'DRY:';printf ' %q' "${args[@]}";printf '\n';else "${args[@]}";fi
done
