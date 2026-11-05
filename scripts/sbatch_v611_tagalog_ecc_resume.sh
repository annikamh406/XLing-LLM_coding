#!/usr/bin/env bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory required}"
LANGUAGE=tagalog
python3 scripts/resume_v611_tagalog_ecc.py --verify
[[ "${SLURMD_NODENAME:-${SLURM_JOB_NODELIST:-}}" != gpu3001 ]] || { echo "Faulty node excluded" >&2; exit 2; }
python3 scripts/v611_diagnostic.py
case "$LANGUAGE" in english|german|hebrew|spanish|tagalog) ;; *) exit 2 ;; esac
[[ -n "${CUDA_VISIBLE_DEVICES:-}" && "$CUDA_VISIBLE_DEVICES" != *,* ]] || { echo 'One allocated L40S is required.' >&2;exit 2; }
export OLLAMA_MODELS="${OLLAMA_MODELS:-/oscar/data/shared/ollama_models}"
export OLLAMA_HOST="127.0.0.1:$((20000 + SLURM_JOB_ID % 10000))"
export OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=false OLLAMA_KV_CACHE_TYPE=f16
export EXPECTED_OLLAMA_VERSION=0.32.14
export EXPECTED_MODEL_BLOB_SHA256=280af6832eca23cb322c4dcc65edfea98a21b8f8ab07dc7553bd6f7e6e7a3313
OLLAMA_URL="http://$OLLAMA_HOST/api/chat"
LOG_DIR=v6/results/dev_train_diagnostic_6_1_1/ecc_recovery/logs
mkdir -p "$LOG_DIR"
module load ollama 2>/dev/null || true
command -v ollama >/dev/null
ollama serve >"$LOG_DIR/ollama_${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
RUNNER_PID=''
cleanup() {
  [[ -z "$RUNNER_PID" ]] || kill -TERM -- "-$RUNNER_PID" 2>/dev/null || true
  kill "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT
trap 'echo "Interrupted; resume retains validated records.";exit 143' TERM INT
for i in $(seq 1 60); do
  if ollama list >/dev/null 2>&1; then break;fi
  sleep 2
done
ollama list >/dev/null
RUNTIME="$LOG_DIR/runtime_${SLURM_JOB_ID}_restart-${SLURM_RESTART_COUNT:-0}.json"
python3 scripts/capture_coding_runtime.py --model gemma4:31b --ollama-url "$OLLAMA_URL" --output "$RUNTIME"
setsid python3 scripts/resume_v611_tagalog_ecc.py --ollama-url "$OLLAMA_URL" --runtime "$RUNTIME" &
RUNNER_PID=$!
wait "$RUNNER_PID"
RUNNER_PID=''
