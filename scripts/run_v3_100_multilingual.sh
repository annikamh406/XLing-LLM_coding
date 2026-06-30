#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODEL="${MODEL:-gemma4:31b}"
LIMIT="${LIMIT:-100}"
BATCH_SIZE="${BATCH_SIZE:-5}"
SPLIT="${SPLIT:-dev_train}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RESULTS_DIR="${RESULTS_DIR:-v3/results}"
LOG_DIR="$RESULTS_DIR/logs"

mkdir -p "$LOG_DIR"

COMMON_ARGS=(
  --split "$SPLIT"
  --model "$MODEL"
  --limit "$LIMIT"
  --batch-size "$BATCH_SIZE"
  --schema-version bloom_v3
  --results-dir "$RESULTS_DIR"
)

run_job() {
  local language="$1"
  local prompt="$2"
  local prompt_version="$3"
  shift 3
  local log_file="$LOG_DIR/${SPLIT}_${MODEL//[:\/]/_}_bloom_v3_${prompt_version}_limit-${LIMIT}.log"

  echo "Starting ${language} ${prompt_version}; log: ${log_file}"
  "$PYTHON_BIN" scripts/run_bloom_coding.py \
    "${COMMON_ARGS[@]}" \
    --split-dir "splits/${language}" \
    --prompt "$prompt" \
    --prompt-version "$prompt_version" \
    "$@" >"$log_file" 2>&1 &
}

run_job hebrew v3/bloom_v3_hebrew_prompt.md p003-he-loc "$@"
pid_he_loc=$!
run_job hebrew v3/bloom_v3_hebrew_prompt_english_examples.md p003-he-engex "$@"
pid_he_engex=$!
run_job german v3/bloom_v3_german_prompt.md p003-de-loc "$@"
pid_de_loc=$!
run_job german v3/bloom_v3_german_prompt_english_examples.md p003-de-engex "$@"
pid_de_engex=$!

status=0
for pid in "$pid_he_loc" "$pid_he_engex" "$pid_de_loc" "$pid_de_engex"; do
  if ! wait "$pid"; then
    status=1
  fi
done

if [[ "$status" -eq 0 ]]; then
  echo "All four multilingual v3 runs finished successfully."
else
  echo "At least one multilingual v3 run failed. Check logs in ${LOG_DIR}." >&2
fi

exit "$status"
