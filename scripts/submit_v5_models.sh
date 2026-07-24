#!/usr/bin/env bash
# Submit the primary v5 model-comparison matrix to Slurm.
#
# Default models:
#   gemma4:31b
#   qwen3.5:122b
#   qwen3.6:35b-a3b
#   gpt-oss:120b
#
# Default cells are the five primary, unmasked v5 prompts:
#   english:en  german:engex  hebrew:engex  spanish:engex  tagalog:engex
#
# Prefer the two purpose-specific wrappers:
#   ./scripts/submit_v5_smoke.sh  # four models x first 10 English items
#   ./scripts/submit_v5_full.sh   # four models x five full dev_train cells
#
# Useful overrides:
#   DRY_RUN=1 ./scripts/submit_v5_smoke.sh
#   MODELS="qwen3.5:122b" CELLS="english:en" LIMIT=10 \
#     ./scripts/submit_v5_models.sh
#   CELLS="german:engex hebrew:engex" ./scripts/submit_v5_full.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODELS="${MODELS:-gemma4:31b qwen3.5:122b qwen3.6:35b-a3b gpt-oss:120b}"
CELLS="${CELLS:-english:en german:engex hebrew:engex spanish:engex tagalog:engex}"
DRY_RUN="${DRY_RUN:-}"
WALLTIME="${WALLTIME:-24:00:00}"
NUM_CTX="${NUM_CTX:-32768}"

# Forward run settings through Slurm's normal environment inheritance. Do not
# put RUN_SETS directly in --export: its value may itself contain a comma.
export LIMIT="${LIMIT:-}"
export SPLIT="${SPLIT:-dev_train}"
export RUN_SETS="${RUN_SETS:-unmasked}"
export BATCH_SIZE="${BATCH_SIZE:-5}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/oscar/data/shared/ollama_models}"

# Slurm requires the output directory to exist at submission time.
mkdir -p v5/results/logs

submit() {
  if [[ -n "$DRY_RUN" ]]; then
    printf 'DRY:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

submission_status=0

for model in $MODELS; do
  case "$model" in
    gemma4:31b)
      gpus=1
      memory=48g
      ;;
    qwen3.5:122b)
      gpus=2
      memory=96g
      ;;
    qwen3.6:35b-a3b)
      gpus=1
      memory=48g
      ;;
    gpt-oss:120b)
      gpus=2
      memory=96g
      ;;
    *)
      echo "ERROR: no v5 resource profile for model '$model'." >&2
      echo "Add an explicit profile in scripts/submit_v5_models.sh before submitting it." >&2
      exit 2
      ;;
  esac

  model_tag="${model%%:*}"
  if [[ -n "$LIMIT" ]]; then
    run_tag="smoke"
  else
    run_tag="full"
  fi

  for cell in $CELLS; do
    language="${cell%%:*}"
    variant="${cell##*:}"
    if ! submit sbatch \
        --job-name="v5-${run_tag}-${model_tag}-${language}-${variant}" \
        --gres="gpu:${gpus}" \
        --mem="$memory" \
        --time="$WALLTIME" \
        --export=ALL \
        scripts/sbatch_v5.sh "$model" "$language" "$variant" \
        --num-ctx "$NUM_CTX"; then
      echo "ERROR: failed to submit $model $language/$variant." >&2
      submission_status=1
    fi
  done
done

exit "$submission_status"
