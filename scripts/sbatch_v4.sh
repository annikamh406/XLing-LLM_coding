#!/usr/bin/env bash
#SBATCH --job-name=xling-v4
#SBATCH --partition=l40s-gcondo
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48g
#SBATCH --time=24:00:00
#SBATCH --output=v4/results/logs/sbatch_v4_%x_%j.out
# If your condo requires an account, uncomment and set it:
##SBATCH --account=l40s-gcondo
#
# Generic v4 sbatch worker for ONE (model, language, variant) cell:
#   sbatch [resource overrides] scripts/sbatch_v4.sh MODEL LANGUAGE VARIANT [extra runner args]
# e.g.
#   sbatch scripts/sbatch_v4.sh qwen3:32b german loc
#   sbatch --gres=gpu:2 --mem=64g scripts/sbatch_v4.sh llama3.3:70b english en --num-ctx 16384
#
# Normally submitted for the whole matrix by scripts/submit_v4_all.sh, which
# sets the right resources per model (llama3.3:70b needs 2 GPUs + SCHED_SPREAD
# + --num-ctx 16384; see the 2026-07-01 KV-cache incident).
#
# Each cell runs the unmasked and masked v4 arms sequentially on ONE private
# Ollama server. Parallelism happens across sbatch jobs: Slurm isolates the
# GPUs per job, and the job-unique port below prevents the 2026-07-01 failure
# where two jobs on one node shared 127.0.0.1:11434, cross-wired their
# readiness checks, and thrashed a single GPU.
#
# The v4 protocol runs the FULL split (no --limit): the first ~100 rows per
# language are development data (splits/*/inspected_rows.txt), so limit-100
# would score mostly on mined rows. For a smoke test: LIMIT=10 sbatch ...
#
# Storage note: we deliberately DO NOT set OLLAMA_MODELS. gemma4:31b +
# qwen3:32b + llama3.3:70b together are ~81 GB in ~/.ollama, under the 100 GB
# home soft quota (run `checkquota` if unsure). data+rfeiman is ~85% full so
# the models should NOT be relocated there.
set -uo pipefail

cd "$SLURM_SUBMIT_DIR" || exit 1

MODEL="${1:?usage: sbatch scripts/sbatch_v4.sh MODEL LANGUAGE VARIANT [runner args]}"
LANGUAGE="${2:?missing LANGUAGE}"
VARIANT="${3:?missing VARIANT (en|loc|engex)}"
shift 3

# llama3.3:70b (~43 GB weights) must be split across both allocated GPUs
# instead of loading onto one and offloading the overflow to CPU.
if [[ "$MODEL" == llama* ]]; then
  export OLLAMA_SCHED_SPREAD=1
fi

# Job-unique port. Two jobs on one node must not share 127.0.0.1:11434: the
# second `ollama serve` fails to bind, its readiness check then reaches the
# FIRST job's server, and both jobs funnel into one GPU, thrashing between
# models (this cross-wired the two 2026-07-01 tagalog jobs on gpu2708). With a
# unique port, a bind failure makes the readiness check fail loudly instead of
# silently using another job's server.
OLLAMA_PORT=$((20000 + SLURM_JOB_ID % 10000))
export OLLAMA_HOST=127.0.0.1:${OLLAMA_PORT}
OLLAMA_URL="http://127.0.0.1:${OLLAMA_PORT}/api/chat"

# --- Bring up Ollama on this node ---------------------------------------------
module load ollama 2>/dev/null || true   # adjust if your Ollama isn't a module
mkdir -p v4/results/logs
ollama serve >"v4/results/logs/ollama_serve_${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
# Make sure the server dies with the job rather than lingering on the node.
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT

# Wait (up to ~2 min) for the server to accept requests before coding.
echo "Waiting for Ollama on port ${OLLAMA_PORT}..."
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

# Confirm the model is present (it persists on disk between sessions).
if ! ollama list | grep -q "$MODEL"; then
  echo "$MODEL not found locally; pulling..."
  ollama pull "$MODEL"
fi

# --- Run this cell's unmasked + masked arms sequentially -----------------------
# Settings match what stabilized the v3 runs (num-predict cap + long timeout);
# extra args from the submit line pass straight through (llama adds
# --num-ctx 16384 there).
MODEL="$MODEL" LANGUAGE="$LANGUAGE" VARIANT="$VARIANT" \
LIMIT="${LIMIT:-}" SPLIT="${SPLIT:-dev_train}" RUN_SETS="${RUN_SETS:-unmasked,masked}" \
  ./scripts/run_v4_language.sh \
    --num-predict 8000 --timeout 1200 --ollama-url "$OLLAMA_URL" "$@"
