#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
python3 scripts/resume_v611_tagalog_ecc.py --verify
LOG_DIR=v6/results/dev_train_diagnostic_6_1_1/ecc_recovery/logs
mkdir -p "$LOG_DIR"
ROUTING=(--partition=l40s-gcondo --qos=copsy-l40s-gcondo --constraint=l40s --exclude=gpu3001)
[[ -z "${CONDO_ACCOUNT:-}" ]] || ROUTING+=(--account="$CONDO_ACCOUNT")
ARGS=(sbatch "${ROUTING[@]}" --gres=gpu:1 --ntasks=1 --cpus-per-task=4 --mem=48g
  --time="${WALLTIME:-12:00:00}" --requeue --signal=B:TERM@60 --open-mode=append
  --job-name=v611-ecc-tagalog --output="$LOG_DIR/sbatch_%x_%j.out"
  scripts/sbatch_v611_tagalog_ecc_resume.sh)
if [[ "${DRY_RUN:-0}" == 1 ]]; then printf 'DRY:';printf ' %q' "${ARGS[@]}";printf '\n';else "${ARGS[@]}";fi
