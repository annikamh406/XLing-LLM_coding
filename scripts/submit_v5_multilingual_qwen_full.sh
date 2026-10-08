#!/usr/bin/env bash
# Submit Qwen full-prompt/batch-5 on the frozen multilingual production-pair samples.
# Four jobs; existing Gemma and condensed-Qwen outputs are preserved.
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
  for required in "$split_path" "$full_prompt"; do
    if [[ ! -f "$required" ]]; then
      echo "ERROR: missing required artifact: $required" >&2
      exit 2
    fi
  done

  if ! submit sbatch \
      --job-name="v5y-qwen-full-b5-$language" \
      --gres="gpu:1" \
      --mem="48g" \
      --time="$WALLTIME" \
      --output="$LOG_DIR/sbatch_v5y_%x_%j.out" \
      --export="ALL,SPLIT=$SPLIT_NAME,RUN_SETS=unmasked,BATCH_SIZE=5,RESULTS_DIR=$RESULTS_DIR,LOG_DIR=$LOG_DIR,PROMPT_OVERRIDE=$full_prompt,PROMPT_VERSION_OVERRIDE=p005y-$code-full-b5-rdefault-t0" \
      scripts/sbatch_v5.sh qwen3.6:35b-a3b "$language" engex \
      --num-ctx "$NUM_CTX" --temperature 0; then
    echo "ERROR: failed to submit Qwen $language." >&2
    status=1
  fi
done

exit "$status"
