#!/usr/bin/env bash
# One full 250-record development diagnostic, with no validation inputs or retries.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -c 'import sys; sys.path.insert(0,"scripts"); from run_hebrew_nfc_dev import verify_dev; verify_dev()'
export LIMIT="" SPLIT=dev_train_promptpair_v5 RUN_SETS=unmasked BATCH_SIZE=5
export RESULTS_DIR=v5/results/hebrew_nfc_dev LOG_DIR=v5/results/hebrew_nfc_dev/logs
export PROMPT_OVERRIDE=v5/bloom_v5_hebrew_prompt_english_examples.md
export PROMPT_VERSION_OVERRIDE=p005nfc-he-full-b5-t0-s20261009
export CAPTURE_RUNTIME=1 MIN_GPU_MEMORY_MIB=45000
export OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=false OLLAMA_KV_CACHE_TYPE=f16
export EXPECTED_OLLAMA_VERSION=0.32.14
export EXPECTED_MODEL_BLOB_SHA256=f5ee307a2982106a6eb82b62b2c00b575c9072145a759ae4660378acda8dcf2d
mkdir -p "$LOG_DIR"
args=(sbatch --partition=l40s-gcondo --qos=copsy-l40s-gcondo --constraint=l40s
  --gres=gpu:1 --ntasks=1 --cpus-per-task=4 --mem=48g --time="${WALLTIME:-24:00:00}"
  --signal=B:TERM@60 --open-mode=append --job-name=qwen-he-nfc-dev
  --output="$LOG_DIR/sbatch_%j.out" --export=ALL)
[[ -z "${CONDO_ACCOUNT:-}" ]] || args+=(--account="$CONDO_ACCOUNT")
args+=(scripts/sbatch_hebrew_nfc_dev.sh qwen3.6:35b-a3b hebrew engex
  --num-ctx 32768 --num-predict 8000 --temperature 0 --seed 20261009 --max-retries 0 --resume)
if [[ -n "${DRY_RUN:-}" ]]; then printf 'DRY:';printf ' %q' "${args[@]}";printf '\n';else "${args[@]}";fi
