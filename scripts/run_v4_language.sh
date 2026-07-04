#!/usr/bin/env bash
# Run the v4 coding jobs for ONE (model, language, example-variant) cell,
# sequentially on a single Ollama server: the unmasked run, then the matching
# masked-negator run (splits/<language>_masked + p004m* prompt).
#
# Required env:
#   MODEL     e.g. gemma4:31b / qwen3:32b / llama3.3:70b
#   LANGUAGE  english | german | hebrew | spanish | tagalog
#   VARIANT   en | loc | engex   (english has no loc/engex split; use "en")
# Optional env:
#   LIMIT       default "" = FULL split. The v4 protocol is full dev_train:
#               the first ~100 rows per language are development data
#               (splits/*/inspected_rows.txt), so a limit-100 run would score
#               mostly on mined rows. Set LIMIT=N only for smoke tests.
#   SPLIT       default dev_train
#   RUN_SETS    default "unmasked,masked"; subset to rerun one arm
#   RESULTS_DIR default v4/results
#
# Pass-through args go straight to run_bloom_coding.py, e.g.:
#   MODEL=qwen3:32b LANGUAGE=german VARIANT=loc \
#     ./scripts/run_v4_language.sh --num-predict 8000 --timeout 1200
#
# Sequential inside one job on purpose; parallelism happens ACROSS sbatch
# jobs, each with its own GPU allocation and job-unique Ollama port (see
# scripts/sbatch_v4.sh and the 2026-07-01 port cross-wiring incident).
set -uo pipefail   # NOT -e: still attempt the masked run if unmasked fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODEL="${MODEL:?set MODEL}"
LANGUAGE="${LANGUAGE:?set LANGUAGE}"
VARIANT="${VARIANT:?set VARIANT (en|loc|engex)}"
LIMIT="${LIMIT:-}"
SPLIT="${SPLIT:-dev_train}"
RUN_SETS="${RUN_SETS:-unmasked,masked}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RESULTS_DIR="${RESULTS_DIR:-v4/results}"
LOG_DIR="${LOG_DIR:-$RESULTS_DIR/logs}"

mkdir -p "$LOG_DIR"

case "$LANGUAGE" in
  english) LANG_CODE="" ;;
  german)  LANG_CODE="de" ;;
  hebrew)  LANG_CODE="he" ;;
  spanish) LANG_CODE="es" ;;
  tagalog) LANG_CODE="tl" ;;
  *) echo "Unknown LANGUAGE: $LANGUAGE" >&2; exit 2 ;;
esac

# Prompt file + prompt-version for the unmasked run; masked versions are
# derived from them (file: *_masked.md, version: p004 -> p004m).
if [[ "$LANGUAGE" == "english" ]]; then
  [[ "$VARIANT" == "en" ]] || { echo "english takes VARIANT=en" >&2; exit 2; }
  PROMPT="v4/bloom_v4_english_prompt.md"
  PROMPT_VERSION="p004"
else
  case "$VARIANT" in
    loc)   PROMPT="v4/bloom_v4_${LANGUAGE}_prompt.md" ;;
    engex) PROMPT="v4/bloom_v4_${LANGUAGE}_prompt_english_examples.md" ;;
    *) echo "VARIANT must be loc or engex for $LANGUAGE" >&2; exit 2 ;;
  esac
  PROMPT_VERSION="p004-${LANG_CODE}-${VARIANT}"
fi

COMMON_ARGS=(
  --split "$SPLIT"
  --model "$MODEL"
  --batch-size "${BATCH_SIZE:-5}"
  --schema-version bloom_v4
  --results-dir "$RESULTS_DIR"
)
LIMIT_SUFFIX=""
if [[ -n "$LIMIT" ]]; then
  COMMON_ARGS+=(--limit "$LIMIT")
  LIMIT_SUFFIX="_limit-${LIMIT}"
fi

status=0

run_job() {
  local split_dir="$1"
  local prompt="$2"
  local prompt_version="$3"
  shift 3
  local log_file="$LOG_DIR/${SPLIT}_${MODEL//[:\/]/_}_bloom_v4_${prompt_version}${LIMIT_SUFFIX}.log"

  echo "=== Starting ${prompt_version} (${split_dir}); log: ${log_file} ==="
  if "$PYTHON_BIN" scripts/run_bloom_coding.py \
      "${COMMON_ARGS[@]}" \
      --split-dir "$split_dir" \
      --prompt "$prompt" \
      --prompt-version "$prompt_version" \
      "$@" >"$log_file" 2>&1; then
    echo "    ${prompt_version} finished OK."
  else
    echo "    ${prompt_version} FAILED (see ${log_file})." >&2
    status=1
  fi
}

for run_set in ${RUN_SETS//,/ }; do
  case "$run_set" in
    unmasked)
      run_job "splits/${LANGUAGE}" "$PROMPT" "$PROMPT_VERSION" "$@"
      ;;
    masked)
      run_job "splits/${LANGUAGE}_masked" \
        "${PROMPT%.md}_masked.md" \
        "${PROMPT_VERSION/p004/p004m}" \
        "$@"
      ;;
    *) echo "Unknown RUN_SETS entry: $run_set" >&2; status=1 ;;
  esac
done

if [[ "$status" -eq 0 ]]; then
  echo "All ${MODEL} ${LANGUAGE}/${VARIANT} v4 runs finished successfully."
else
  echo "At least one ${MODEL} ${LANGUAGE}/${VARIANT} run failed; see ${LOG_DIR}." >&2
fi
exit "$status"
