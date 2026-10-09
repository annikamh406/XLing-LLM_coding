#!/usr/bin/env bash
# Five languages x two GPU types x two identical repeats = twenty short jobs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
LANGUAGES="${LANGUAGES:-english german hebrew spanish tagalog}"
GPU_TYPES="${GPU_TYPES:-l40s a6000}"
REPEATS="${REPEATS:-1 2}"
RESULTS_DIR="${RESULTS_DIR:-v5/results/gemma_gpu_comparison}"
LOG_DIR="$RESULTS_DIR/logs"
WALLTIME="${WALLTIME:-04:00:00}"
DRY_RUN="${DRY_RUN:-}"
PARTITION="${PARTITION:-gpu-scavenger}"
ACCOUNT="${ACCOUNT-gpu-scavenger}"
ROUTING_ARGS=(--partition="$PARTITION")
[[ -z "$ACCOUNT" ]] || ROUTING_ARGS+=(--account="$ACCOUNT")
[[ -z "${QOS:-}" ]] || ROUTING_ARGS+=(--qos="$QOS")
mkdir -p "$LOG_DIR"
submit() {
  if [[ -n "$DRY_RUN" ]]; then printf 'DRY:'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}
for language in $LANGUAGES; do
  case "$language" in
    english) code=en; variant=en; prompt=v5/bloom_v5_english_prompt.md ;;
    german) code=de; variant=engex; prompt=v5/bloom_v5_german_prompt_english_examples.md ;;
    hebrew) code=he; variant=engex; prompt=v5/bloom_v5_hebrew_prompt_english_examples.md ;;
    spanish) code=es; variant=engex; prompt=v5/bloom_v5_spanish_prompt_english_examples.md ;;
    tagalog) code=tl; variant=engex; prompt=v5/bloom_v5_tagalog_prompt_english_examples.md ;;
    *) echo "Unknown language: $language" >&2; exit 2 ;;
  esac
  for file in "$prompt" "splits/$language/dev_train_gemma_gpu_v5.jsonl"; do
    [[ -f "$file" ]] || { echo "Missing $file" >&2; exit 2; }
  done
  for gpu in $GPU_TYPES; do
    [[ "$gpu" == l40s || "$gpu" == a6000 ]] || { echo "Unsupported GPU feature $gpu" >&2; exit 2; }
    for repeat in $REPEATS; do
      [[ "$repeat" == 1 || "$repeat" == 2 ]] || { echo "Repeat must be 1 or 2" >&2; exit 2; }
      tag="p005g-$code-$gpu-r$repeat-full-b1-t0"
      submit sbatch "${ROUTING_ARGS[@]}" \
        --constraint="$gpu" --gres=gpu:1 --mem=48g --time="$WALLTIME" \
        --requeue --signal=B:TERM@60 --open-mode=append \
        --job-name="gemma-gpu-$code-$gpu-r$repeat" \
        --output="$LOG_DIR/sbatch_%x_%j.out" \
        --export="ALL,SPLIT=dev_train_gemma_gpu_v5,RUN_SETS=unmasked,BATCH_SIZE=1,RESULTS_DIR=$RESULTS_DIR,LOG_DIR=$LOG_DIR,PROMPT_OVERRIDE=$prompt,PROMPT_VERSION_OVERRIDE=$tag,MIN_GPU_MEMORY_MIB=45000,CAPTURE_RUNTIME=1,OLLAMA_NUM_PARALLEL=1,OLLAMA_FLASH_ATTENTION=false,OLLAMA_KV_CACHE_TYPE=f16" \
        scripts/sbatch_v5.sh gemma4:31b "$language" "$variant" \
        --num-ctx 32768 --temperature 0 --seed 20261009 --max-retries 0 --resume
    done
  done
 done
