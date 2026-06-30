#!/usr/bin/env bash
# Rerun the three v3 limit-100 multilingual jobs that crashed on 2026-06-30:
#   p003-he-loc, p003-he-engex, p003-de-loc
# (p003-de-engex completed/was left running, so it is intentionally excluded.)
#
# Differences from run_v3_100_multilingual.sh, which broke these runs:
#   1. SEQUENTIAL execution. The original launched all four jobs in parallel
#      against one Ollama server / one GPU; contention pushed batches past the
#      timeout (he-loc, de-loc) and aggravated gemma's thinking-channel runaway
#      (he-engex). One job at a time removes the contention.
#   2. Relies on the run_bloom_coding.py hardening (num_predict cap + retryable
#      timeout/empty-content handling with reseeded retries) so a single bad
#      batch resamples instead of aborting the whole run.
#
# Pass-through args go to run_bloom_coding.py, e.g.:
#   ./scripts/rerun_v3_100_failures.sh --num-predict 8000 --timeout 1200
set -uo pipefail   # NOT -e: keep going to the next language if one fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODEL="${MODEL:-gemma4:31b}"
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
run_job hebrew v3/bloom_v3_hebrew_prompt.md p003-he-loc "$@"
run_job hebrew v3/bloom_v3_hebrew_prompt_english_examples.md p003-he-engex "$@"
run_job german v3/bloom_v3_german_prompt.md p003-de-loc "$@"

if [[ "$status" -eq 0 ]]; then
  echo "All three rerun jobs finished successfully."
else
  echo "At least one rerun job failed. Check logs in ${LOG_DIR}." >&2
fi

exit "$status"
