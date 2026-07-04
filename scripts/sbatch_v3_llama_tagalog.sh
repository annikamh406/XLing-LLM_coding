#!/usr/bin/env bash
#SBATCH --job-name=xling-v3-llama-tl
#SBATCH --partition=l40s-gcondo
#SBATCH --gres=gpu:2
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64g
#SBATCH --time=12:00:00
#SBATCH --output=v3/results/logs/sbatch_v3_llama_tagalog_%j.out
# If your condo requires an account, uncomment and set it:
##SBATCH --account=l40s-gcondo
#
# Rerun only the two failed llama3.3:70b Tagalog limit-100 jobs:
#   p003-tl-loc and p003-tl-engex.
#
# Submit from the repository root on Oscar:
#   sbatch scripts/sbatch_v3_llama_tagalog.sh
#
# BATCH_SIZE=1 is deliberate. The original size-5 runs repeatedly produced
# duplicate record_ids and omitted other records. With one record per request,
# the generated per-batch schema permits only that record_id and exactly one
# prediction, eliminating that failure mode. This changes the batching context
# relative to the other v3 runs and should be recorded when interpreting the
# comparison.
set -uo pipefail

cd "$SLURM_SUBMIT_DIR" || exit 1

MODEL=llama3.3:70b
export OLLAMA_SCHED_SPREAD=1

# Use a job-unique server port so another Ollama job on the same node cannot
# silently capture these requests.
OLLAMA_PORT=$((20000 + SLURM_JOB_ID % 10000))
export OLLAMA_HOST=127.0.0.1:${OLLAMA_PORT}
OLLAMA_URL="http://127.0.0.1:${OLLAMA_PORT}/api/chat"

module load ollama 2>/dev/null || true
ollama serve >"v3/results/logs/ollama_serve_${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT

echo "Waiting for Ollama to come up..."
for i in $(seq 1 60); do
  if ollama list >/dev/null 2>&1; then
    echo "Ollama is up after ${i} checks."
    break
  fi
  sleep 2
done
if ! ollama list >/dev/null 2>&1; then
  echo "ERROR: Ollama did not become ready; aborting." >&2
  exit 1
fi

if ! ollama list | grep -q "$MODEL"; then
  echo "$MODEL not found locally; pulling (~43 GB, one-time)..."
  ollama pull "$MODEL"
fi

# Two GPUs plus the pinned context keep the 70B model and KV cache off CPU.
# Existing successful non-Tagalog outputs are never inspected or overwritten.
BATCH_SIZE=1 MODEL="$MODEL" ./scripts/run_v3_tagalog.sh \
  --num-ctx 16384 \
  --num-predict 8000 \
  --timeout 1200 \
  --ollama-url "$OLLAMA_URL" \
  "$@"
