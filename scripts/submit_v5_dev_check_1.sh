#!/usr/bin/env bash
# Two frozen finalists x five complete validation splits; no submission locally.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
"${PYTHON_BIN:-python3}" scripts/check_v5_validation_freeze.py
LANGUAGES="${LANGUAGES:-english german hebrew spanish tagalog}"
MODELS="${MODELS:-gemma4:31b qwen3.6:35b-a3b}"
WALLTIME="${WALLTIME:-48:00:00}"
RESULTS_DIR=v5/results/dev_check_1
LOG_DIR="$RESULTS_DIR/logs"
mkdir -p "$LOG_DIR"
ROUTING_ARGS=(--partition=l40s-gcondo --qos=copsy-l40s-gcondo --constraint=l40s)
[[ -z "${CONDO_ACCOUNT:-}" ]] || ROUTING_ARGS+=(--account="$CONDO_ACCOUNT")
# Validate all overrides before submitting any jobs.
for language in $LANGUAGES; do
  case "$language" in english|german|hebrew|spanish|tagalog) ;; *) echo "Unsupported language: $language" >&2; exit 2 ;; esac
done
for model in $MODELS; do
  case "$model" in gemma4:31b|qwen3.6:35b-a3b) ;; *) echo "Unsupported model: $model" >&2; exit 2 ;; esac
done
submit() {
  if [[ -n "${DRY_RUN:-}" ]]; then printf 'DRY:'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}
for language in $LANGUAGES; do
  case "$language" in
    english) code=en; variant=en; prompt=v5/bloom_v5_english_prompt.md ;;
    german) code=de; variant=engex; prompt=v5/bloom_v5_german_prompt_english_examples.md ;;
    hebrew) code=he; variant=engex; prompt=v5/bloom_v5_hebrew_prompt_english_examples.md ;;
    spanish) code=es; variant=engex; prompt=v5/bloom_v5_spanish_prompt_english_examples.md ;;
    tagalog) code=tl; variant=engex; prompt=v5/bloom_v5_tagalog_prompt_english_examples.md ;;
  esac
  for model in $MODELS; do
    case "$model" in
      gemma4:31b) batch=1; short=gemma; blob=280af6832eca23cb322c4dcc65edfea98a21b8f8ab07dc7553bd6f7e6e7a3313 ;;
      qwen3.6:35b-a3b) batch=5; short=qwen; blob=f5ee307a2982106a6eb82b62b2c00b575c9072145a759ae4660378acda8dcf2d ;;
    esac
    tag="p005v1-$code-full-b$batch-t0-s20261009"
    # With --export=ALL, Slurm may prefer an inherited value over its explicit
    # export-list value. Set both so a previous LIMIT or prompt cannot leak in.
    export LIMIT="" SPLIT=dev_check_1 RUN_SETS=unmasked BATCH_SIZE="$batch"
    export RESULTS_DIR LOG_DIR PROMPT_OVERRIDE="$prompt" PROMPT_VERSION_OVERRIDE="$tag"
    export MIN_GPU_MEMORY_MIB=45000 CAPTURE_RUNTIME=1 EXPECTED_OLLAMA_VERSION=0.32.14
    export EXPECTED_MODEL_BLOB_SHA256="$blob" OLLAMA_NUM_PARALLEL=1
    export OLLAMA_FLASH_ATTENTION=false OLLAMA_KV_CACHE_TYPE=f16
    submit sbatch "${ROUTING_ARGS[@]}" --gres=gpu:1 --mem=48g \
      --ntasks=1 --cpus-per-task=4 --time="$WALLTIME" \
      --requeue --signal=B:TERM@60 --open-mode=append \
      --job-name="v5-check1-$short-$code" --output="$LOG_DIR/sbatch_%x_%j.out" \
      --export="ALL,LIMIT=,SPLIT=dev_check_1,RUN_SETS=unmasked,BATCH_SIZE=$batch,RESULTS_DIR=$RESULTS_DIR,LOG_DIR=$LOG_DIR,PROMPT_OVERRIDE=$prompt,PROMPT_VERSION_OVERRIDE=$tag,MIN_GPU_MEMORY_MIB=45000,CAPTURE_RUNTIME=1,EXPECTED_OLLAMA_VERSION=0.32.14,EXPECTED_MODEL_BLOB_SHA256=$blob,OLLAMA_NUM_PARALLEL=1,OLLAMA_FLASH_ATTENTION=false,OLLAMA_KV_CACHE_TYPE=f16" \
      scripts/sbatch_v5_validation.sh "$model" "$language" "$variant" \
      --num-ctx 32768 --num-predict 8000 --temperature 0 --seed 20261009 --max-retries 0 --resume
  done
done
