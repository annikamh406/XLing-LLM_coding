#!/usr/bin/env bash
# Verify that all three active v5 English smoke tests produced complete output.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

RESULTS_DIR="${RESULTS_DIR:-v5/results}"
EXPECTED_PREDICTIONS="${EXPECTED_PREDICTIONS:-10}"
EXPECTED_BATCHES="${EXPECTED_BATCHES:-2}"
MODELS="${MODELS:-gemma4:31b qwen3.6:35b-a3b gpt-oss:120b}"
status=0

printf '%-22s %12s %12s %s\n' "MODEL" "PREDICTIONS" "BATCHES" "STATUS"

for model in $MODELS; do
  model_slug="${model//:/_}"
  prediction_file="$RESULTS_DIR/dev_train_${model_slug}_bloom_v5_p005_limit-10_predictions.jsonl"
  raw_file="$RESULTS_DIR/dev_train_${model_slug}_bloom_v5_p005_limit-10_raw_responses.jsonl"

  if [[ ! -f "$prediction_file" || ! -f "$raw_file" ]]; then
    printf '%-22s %12s %12s %s\n' "$model" "-" "-" "MISSING"
    status=1
    continue
  fi

  prediction_count="$(wc -l <"$prediction_file" | tr -d ' ')"
  batch_count="$(wc -l <"$raw_file" | tr -d ' ')"
  model_status="OK"

  if [[ "$prediction_count" != "$EXPECTED_PREDICTIONS" ||
        "$batch_count" != "$EXPECTED_BATCHES" ]]; then
    model_status="INCOMPLETE"
    status=1
  fi

  shopt -s nullglob
  failed_batches=(
    "$RESULTS_DIR"/dev_train_"${model_slug}"_bloom_v5_p005_limit-10_failed_batch-*.json
  )
  shopt -u nullglob
  if (( ${#failed_batches[@]} > 0 )); then
    model_status="FAILED-BATCH"
    status=1
  fi

  printf '%-22s %12s %12s %s\n' \
    "$model" "$prediction_count" "$batch_count" "$model_status"
done

if (( status == 0 )); then
  echo "All three v5 smoke tests are complete; the full matrix is ready to submit."
else
  echo "At least one smoke test is missing or incomplete. Check v5/results/logs before submitting full runs." >&2
fi

exit "$status"
