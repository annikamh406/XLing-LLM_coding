#!/usr/bin/env bash
# Five condo jobs; selected Gemma v6.6 records only. No v5 inference.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
python3 scripts/v66_diagnostic.py
LANGUAGES="${LANGUAGES:-english german hebrew spanish tagalog}"
for language in $LANGUAGES; do
  case "$language" in english|german|hebrew|spanish|tagalog) ;; *) echo "Unsupported language: $language" >&2; exit 2 ;; esac
done
LOG_DIR=v6/results/dev_train_diagnostic_6_6/logs
mkdir -p "$LOG_DIR"
ROUTING=(--partition=l40s-gcondo --qos=copsy-l40s-gcondo --constraint=l40s --exclude=gpu3001)
[[ -z "${CONDO_ACCOUNT:-}" ]] || ROUTING+=(--account="$CONDO_ACCOUNT")
for language in $LANGUAGES; do
  ARGS=(sbatch "${ROUTING[@]}" --gres=gpu:1 --ntasks=1 --cpus-per-task=4 --mem=48g
    --time="${WALLTIME:-12:00:00}" --requeue --signal=B:TERM@60 --open-mode=append
    --job-name="v66-diag-$language" --output="$LOG_DIR/sbatch_%x_%j.out"
    scripts/sbatch_v66_diagnostic.sh "$language")
  if [[ "${DRY_RUN:-0}" == 1 ]]; then printf 'DRY:';printf ' %q' "${ARGS[@]}";printf '\n';else "${ARGS[@]}";fi
done
