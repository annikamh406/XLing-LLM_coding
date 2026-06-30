#!/usr/bin/env bash
# Run all 7 v3 limit-100 coding jobs SEQUENTIALLY on a single GPU / single
# Ollama server:
#   English : p003                       (no localized/engex variants needed)
#   Spanish : p003-es-loc, p003-es-engex
#   German  : p003-de-loc, p003-de-engex
#   Hebrew  : p003-he-loc, p003-he-engex
#
# This is the model-agnostic full sweep. Pick the model with MODEL=...:
#   MODEL=gemma4:31b ./scripts/run_v3_100_all_langs.sh
#   MODEL=qwen3:32b  ./scripts/run_v3_100_all_langs.sh
#
# Sequential (not parallel) on purpose: one job at a time avoids the GPU/server
# contention that pushed batches past the timeout and aggravated thinking-channel
# runaway on the parallel 2026-06-30 run. Relies on the hardened
# run_bloom_coding.py (num_predict cap + retryable timeout/empty-content with
# reseeded retries) so a single bad batch resamples instead of aborting the run.
#
# Output/log filenames embed the sanitized model name, so qwen results never
# collide with gemma results in the same results dir.
#
# Pass-through args go straight to run_bloom_coding.py, e.g.:
#   ./scripts/run_v3_100_all_langs.sh --num-predict 8000 --timeout 1200
set -uo pipefail   # NOT -e: keep going to the next job if one fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODEL="${MODEL:-qwen3:32b}"
LIMIT="${LIMIT:-100}"
BATCH_SIZE="${BATCH_SIZE:-5}"
SPLIT="${SPLIT:-dev_train}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RESULTS_DIR="${RESULTS_DIR:-v3/results}"
LOG_DIR="${LOG_DIR:-$RESULTS_DIR/logs}"

mkdir -p "$LOG_DIR"

COMMON_ARGS=(
  --split "$SPLIT"
  --model "$MODEL"
  --limit "$LIMIT"
  --batch-size "$BATCH_SIZE"
  --schema-version bloom_v3
  --results-dir "$RESULTS_DIR"
)

status=0

run_job() {
  local language="$1"
  local prompt="$2"
  local prompt_version="$3"
  shift 3
  local log_file="$LOG_DIR/${SPLIT}_${MODEL//[:\/]/_}_bloom_v3_${prompt_version}_limit-${LIMIT}.log"

  echo "=== Starting ${language} ${prompt_version}; log: ${log_file} ==="
  if "$PYTHON_BIN" scripts/run_bloom_coding.py \
      "${COMMON_ARGS[@]}" \
      --split-dir "splits/${language}" \
      --prompt "$prompt" \
      --prompt-version "$prompt_version" \
      "$@" >"$log_file" 2>&1; then
    echo "    ${prompt_version} finished OK."
  else
    echo "    ${prompt_version} FAILED (see ${log_file})." >&2
    status=1
  fi
}

# One at a time, on the single GPU.
run_job english v3/bloom_v3_english_prompt.md                 p003        "$@"
run_job spanish v3/bloom_v3_spanish_prompt.md                 p003-es-loc "$@"
run_job spanish v3/bloom_v3_spanish_prompt_english_examples.md p003-es-engex "$@"
run_job german  v3/bloom_v3_german_prompt.md                  p003-de-loc "$@"
run_job german  v3/bloom_v3_german_prompt_english_examples.md p003-de-engex "$@"
run_job hebrew  v3/bloom_v3_hebrew_prompt.md                  p003-he-loc "$@"
run_job hebrew  v3/bloom_v3_hebrew_prompt_english_examples.md p003-he-engex "$@"

if [[ "$status" -eq 0 ]]; then
  echo "All seven ${MODEL} v3 limit-${LIMIT} runs finished successfully."
else
  echo "At least one ${MODEL} run failed. Check logs in ${LOG_DIR}." >&2
fi

exit "$status"
