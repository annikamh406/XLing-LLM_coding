#!/usr/bin/env bash
# Submit the frozen multilingual production-pair experiment:
#   Gemma 4 31B: full English-example language prompt, batch 1, temp 0
#   Qwen 3.6 35B-A3B: condensed English-example language prompt, batch 5, temp 0
#
# Both conditions use the identical frozen dev_train_promptpair_v5 IDs within
# each language. No GPT model, dev_check split, or lockbox input is referenced.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

LANGUAGES="${LANGUAGES:-german hebrew spanish tagalog}"
SPLIT_NAME="dev_train_promptpair_v5"
RESULTS_DIR="${RESULTS_DIR:-v5/results/multilingual_production_pair}"
LOG_DIR="${LOG_DIR:-$RESULTS_DIR/logs}"
WALLTIME="${WALLTIME:-24:00:00}"
NUM_CTX="${NUM_CTX:-32768}"
DRY_RUN="${DRY_RUN:-}"

mkdir -p "$LOG_DIR"

language_code() {
  case "$1" in
    german) printf '%s' de ;;
    hebrew) printf '%s' he ;;
    spanish) printf '%s' es ;;
    tagalog) printf '%s' tl ;;
    *) echo "ERROR: unsupported language '$1'." >&2; return 2 ;;
  esac
}

submit() {
  if [[ -n "$DRY_RUN" ]]; then
    printf 'DRY:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

status=0
for language in $LANGUAGES; do
  code="$(language_code "$language")" || exit 2
  split_path="splits/$language/$SPLIT_NAME.jsonl"
  full_prompt="v5/bloom_v5_${language}_prompt_english_examples.md"
  condensed_prompt="v5/bloom_v5_${language}_prompt_condensed_english_examples.md"
  for required in "$split_path" "$full_prompt" "$condensed_prompt"; do
    if [[ ! -f "$required" ]]; then
      echo "ERROR: missing required artifact: $required" >&2
      exit 2
    fi
  done

  if ! submit sbatch \
      --job-name="v5y-gemma-full-b1-$language" \
      --gres="gpu:1" \
      --mem="48g" \
      --time="$WALLTIME" \
      --output="$LOG_DIR/sbatch_v5y_%x_%j.out" \
      --export="ALL,SPLIT=$SPLIT_NAME,RUN_SETS=unmasked,BATCH_SIZE=1,RESULTS_DIR=$RESULTS_DIR,LOG_DIR=$LOG_DIR,PROMPT_OVERRIDE=$full_prompt,PROMPT_VERSION_OVERRIDE=p005y-$code-full-b1-rdefault-t0" \
      scripts/sbatch_v5.sh gemma4:31b "$language" engex \
      --num-ctx "$NUM_CTX" --temperature 0; then
    echo "ERROR: failed to submit Gemma $language." >&2
    status=1
  fi

  if ! submit sbatch \
      --job-name="v5y-qwen-cond-b5-$language" \
      --gres="gpu:1" \
      --mem="48g" \
      --time="$WALLTIME" \
      --output="$LOG_DIR/sbatch_v5y_%x_%j.out" \
      --export="ALL,SPLIT=$SPLIT_NAME,RUN_SETS=unmasked,BATCH_SIZE=5,RESULTS_DIR=$RESULTS_DIR,LOG_DIR=$LOG_DIR,PROMPT_OVERRIDE=$condensed_prompt,PROMPT_VERSION_OVERRIDE=p005y-$code-condensed-b5-rdefault-t0" \
      scripts/sbatch_v5.sh qwen3.6:35b-a3b "$language" engex \
      --num-ctx "$NUM_CTX" --temperature 0; then
    echo "ERROR: failed to submit Qwen $language." >&2
    status=1
  fi
done

exit "$status"
