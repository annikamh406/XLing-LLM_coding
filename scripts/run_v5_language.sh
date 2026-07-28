#!/usr/bin/env bash
# Run one v5 (model, language, example-variant) cell against one or both arms.
#
# Required env:
#   MODEL     normally gemma4:31b
#   LANGUAGE  english | german | hebrew | spanish | tagalog
#   VARIANT   en | loc | engex   (English takes en)
# Optional env:
#   LIMIT       default "" = full split; use only for smoke tests
#   SPLIT       default dev_train
#   RUN_SETS    default unmasked; set masked or unmasked,masked for the
#               secondary masked experiment
#   RESULTS_DIR default v5/results
#   PROMPT_OVERRIDE / PROMPT_VERSION_OVERRIDE
#               optional paired overrides for model/prompt experiments;
#               currently supported only for RUN_SETS=unmasked
#
# Example:
#   MODEL=gemma4:31b LANGUAGE=german VARIANT=engex \
#     ./scripts/run_v5_language.sh --num-predict 8000 --timeout 1200
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODEL="${MODEL:?set MODEL}"
LANGUAGE="${LANGUAGE:?set LANGUAGE}"
VARIANT="${VARIANT:?set VARIANT (en|loc|engex)}"
LIMIT="${LIMIT:-}"
SPLIT="${SPLIT:-dev_train}"
RUN_SETS="${RUN_SETS:-unmasked}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
RESULTS_DIR="${RESULTS_DIR:-v5/results}"
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

if [[ "$LANGUAGE" == "english" ]]; then
  [[ "$VARIANT" == "en" ]] || {
    echo "English takes VARIANT=en" >&2
    exit 2
  }
  PROMPT="v5/bloom_v5_english_prompt.md"
  PROMPT_VERSION="p005"
else
  case "$VARIANT" in
    loc)   PROMPT="v5/bloom_v5_${LANGUAGE}_prompt.md" ;;
    engex) PROMPT="v5/bloom_v5_${LANGUAGE}_prompt_english_examples.md" ;;
    *) echo "VARIANT must be loc or engex for $LANGUAGE" >&2; exit 2 ;;
  esac
  PROMPT_VERSION="p005-${LANG_CODE}-${VARIANT}"
fi

if [[ -n "${PROMPT_OVERRIDE:-}" || -n "${PROMPT_VERSION_OVERRIDE:-}" ]]; then
  if [[ -z "${PROMPT_OVERRIDE:-}" || -z "${PROMPT_VERSION_OVERRIDE:-}" ]]; then
    echo "PROMPT_OVERRIDE and PROMPT_VERSION_OVERRIDE must be set together." >&2
    exit 2
  fi
  if [[ "$RUN_SETS" != "unmasked" ]]; then
    echo "Prompt overrides currently require RUN_SETS=unmasked." >&2
    exit 2
  fi
  PROMPT="$PROMPT_OVERRIDE"
  PROMPT_VERSION="$PROMPT_VERSION_OVERRIDE"
fi

COMMON_ARGS=(
  --split "$SPLIT"
  --model "$MODEL"
  --batch-size "${BATCH_SIZE:-5}"
  --schema-version bloom_v5
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
  local log_file="$LOG_DIR/${SPLIT}_${MODEL//[:\/]/_}_bloom_v5_${prompt_version}${LIMIT_SUFFIX}.log"

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
        "${PROMPT_VERSION/p005/p005m}" \
        "$@"
      ;;
    *) echo "Unknown RUN_SETS entry: $run_set" >&2; status=1 ;;
  esac
done

if [[ "$status" -eq 0 ]]; then
  echo "All ${MODEL} ${LANGUAGE}/${VARIANT} v5 runs finished successfully."
else
  echo "At least one ${MODEL} ${LANGUAGE}/${VARIANT} run failed; see ${LOG_DIR}." >&2
fi
exit "$status"
