#!/usr/bin/env bash
# Run the two v3 Tagalog coding jobs SEQUENTIALLY on a single GPU / single
# Ollama server:
#   Tagalog : p003-tl-loc   (localized prompt, Tagalog examples)
#   Tagalog : p003-tl-engex (English-example prompt)
#
# Both jobs run on the COMBINED split dir splits/tagalog/, which concatenates
# the two separately-split corpora (tagalog_mpi tgm_* + tagalog_new tgn_*,
# built by scripts/combine_tagalog_splits.py). The combined files are
# deterministically shuffled, so a --limit prefix samples both corpora;
# results can be evaluated together or per corpus via the record-id prefix /
# 'corpus' field.
#
# Model-agnostic like run_v3_100_all_langs.sh:
#   MODEL=gemma4:31b ./scripts/run_v3_tagalog.sh
#   MODEL=qwen3:32b  ./scripts/run_v3_tagalog.sh
#
# LIMIT defaults to 100 to match the v3 limit-100 protocol; set LIMIT="" to
# code the full split (~323 dev_train rows).
#
# Sequential on purpose (see run_v3_100_all_langs.sh): avoids the GPU/server
# contention from the parallel 2026-06-30 run. Pass-through args go straight
# to run_bloom_coding.py, e.g.:
#   ./scripts/run_v3_tagalog.sh --num-predict 8000 --timeout 1200
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
  --batch-size "$BATCH_SIZE"
  --schema-version bloom_v3
  --results-dir "$RESULTS_DIR"
)
LIMIT_SUFFIX=""
if [[ -n "$LIMIT" ]]; then
  COMMON_ARGS+=(--limit "$LIMIT")
  LIMIT_SUFFIX="_limit-${LIMIT}"
fi

status=0

run_job() {
  local prompt="$1"
  local prompt_version="$2"
  shift 2
  local log_file="$LOG_DIR/${SPLIT}_${MODEL//[:\/]/_}_bloom_v3_${prompt_version}${LIMIT_SUFFIX}.log"

  echo "=== Starting tagalog ${prompt_version}; log: ${log_file} ==="
  if "$PYTHON_BIN" scripts/run_bloom_coding.py \
      "${COMMON_ARGS[@]}" \
      --split-dir "splits/tagalog" \
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
run_job v3/bloom_v3_tagalog_prompt.md                  p003-tl-loc   "$@"
run_job v3/bloom_v3_tagalog_prompt_english_examples.md p003-tl-engex "$@"

if [[ "$status" -eq 0 ]]; then
  echo "Both ${MODEL} v3 Tagalog runs finished successfully."
else
  echo "At least one ${MODEL} Tagalog run failed. Check logs in ${LOG_DIR}." >&2
fi

exit "$status"
