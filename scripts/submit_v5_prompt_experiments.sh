#!/usr/bin/env bash
# Submit the English v5 prompt/decoding experiment matrix.
#
# Default matrix (20 jobs on a deterministic class-enriched dev_train sample):
#   core:           3 models x 2 prompts x 2 batch sizes = 12
#   gpt-reasoning:  GPT-OSS x 2 prompts x 2 batch sizes, Reasoning: high = 4
#   qwen-sampling:  Qwen 3.6 x 2 prompts x 2 batch sizes, recommended sampling = 4
#
# Inspect without submitting:
#   DRY_RUN=1 ./scripts/submit_v5_prompt_experiments.sh
#
# Useful reductions:
#   ARMS=core MODELS="gpt-oss:120b" DRY_RUN=1 \
#     ./scripts/submit_v5_prompt_experiments.sh
#   PROMPTS=condensed BATCH_SIZES=1 ./scripts/submit_v5_prompt_experiments.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODELS="${MODELS:-gemma4:31b qwen3.6:35b-a3b gpt-oss:120b}"
PROMPTS="${PROMPTS:-full condensed}"
BATCH_SIZES="${BATCH_SIZES:-1 5}"
ARMS="${ARMS:-core gpt-reasoning qwen-sampling}"
SPLIT_NAME="${SPLIT_NAME:-dev_train_prompttest_v5}"
RESULTS_DIR="${RESULTS_DIR:-v5/results/prompt_experiments}"
WALLTIME="${WALLTIME:-24:00:00}"
NUM_CTX="${NUM_CTX:-32768}"
DRY_RUN="${DRY_RUN:-}"
unset LIMIT

if [[ -n "$DRY_RUN" ]]; then
  echo "DRY: python3 scripts/build_v5_prompt_experiment_split.py"
  echo "DRY: mkdir -p $RESULTS_DIR/logs"
else
  python3 scripts/build_v5_prompt_experiment_split.py
  mkdir -p "$RESULTS_DIR/logs"
fi

contains_word() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    [[ "$item" == "$needle" ]] && return 0
  done
  return 1
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

model_profile() {
  case "$1" in
    gemma4:31b)       PROFILE_GPUS=1; PROFILE_MEMORY=48g ;;
    qwen3.6:35b-a3b) PROFILE_GPUS=1; PROFILE_MEMORY=48g ;;
    gpt-oss:120b)    PROFILE_GPUS=2; PROFILE_MEMORY=96g ;;
    *)
      echo "ERROR: no prompt-experiment resource profile for '$1'." >&2
      return 2
      ;;
  esac
}

prompt_path() {
  case "$1" in
    full)      printf '%s' "v5/bloom_v5_english_prompt.md" ;;
    condensed) printf '%s' "v5/bloom_v5_english_prompt_condensed.md" ;;
    *) echo "ERROR: unknown prompt arm '$1'." >&2; return 2 ;;
  esac
}

submit_condition() {
  local model="$1"
  local prompt_arm="$2"
  local batch_size="$3"
  local reasoning="$4"
  local decoding="$5"
  local prompt
  local prompt_version
  local model_tag
  local reason_tag
  local -a runner_args

  model_profile "$model" || return
  prompt="$(prompt_path "$prompt_arm")" || return
  model_tag="${model%%:*}"
  reason_tag="${reasoning:-default}"
  prompt_version="p005x-${prompt_arm}-b${batch_size}-r${reason_tag}-${decoding}"
  runner_args=(--num-ctx "$NUM_CTX" --temperature 0)

  if [[ -n "$reasoning" ]]; then
    runner_args+=(--reasoning-effort "$reasoning")
  fi
  if [[ "$decoding" == "qsample" ]]; then
    # Qwen's thinking-mode recommendation: avoid greedy decoding.
    runner_args=(
      --num-ctx "$NUM_CTX"
      --temperature 0.6
      --seed 20260727
      --top-p 0.95
      --top-k 20
      --min-p 0
    )
  fi

  submit sbatch \
    --job-name="v5x-${model_tag}-${prompt_arm}-b${batch_size}-${reason_tag}-${decoding}" \
    --gres="gpu:${PROFILE_GPUS}" \
    --mem="$PROFILE_MEMORY" \
    --time="$WALLTIME" \
    --output="$RESULTS_DIR/logs/sbatch_v5x_%x_%j.out" \
    --export="ALL,SPLIT=${SPLIT_NAME},RUN_SETS=unmasked,BATCH_SIZE=${batch_size},RESULTS_DIR=${RESULTS_DIR},LOG_DIR=${RESULTS_DIR}/logs,PROMPT_OVERRIDE=${prompt},PROMPT_VERSION_OVERRIDE=${prompt_version}" \
    scripts/sbatch_v5.sh "$model" english en "${runner_args[@]}"
}

read -r -a selected_models <<<"$MODELS"
read -r -a selected_arms <<<"$ARMS"
status=0

if contains_word core "${selected_arms[@]}"; then
  for model in $MODELS; do
    for prompt_arm in $PROMPTS; do
      for batch_size in $BATCH_SIZES; do
        submit_condition "$model" "$prompt_arm" "$batch_size" "" "t0" || status=1
      done
    done
  done
fi

if contains_word gpt-reasoning "${selected_arms[@]}" &&
   contains_word "gpt-oss:120b" "${selected_models[@]}"; then
  for prompt_arm in $PROMPTS; do
    for batch_size in $BATCH_SIZES; do
      submit_condition "gpt-oss:120b" "$prompt_arm" "$batch_size" "high" "t0" ||
        status=1
    done
  done
fi

if contains_word qwen-sampling "${selected_arms[@]}" &&
   contains_word "qwen3.6:35b-a3b" "${selected_models[@]}"; then
  for prompt_arm in $PROMPTS; do
    for batch_size in $BATCH_SIZES; do
      submit_condition "qwen3.6:35b-a3b" "$prompt_arm" "$batch_size" "" "qsample" ||
        status=1
    done
  done
fi

exit "$status"
