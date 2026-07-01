#!/usr/bin/env bash
#SBATCH --job-name=xling-v3-tagalog
#SBATCH --partition=l40s-gcondo
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48g
#SBATCH --time=6:00:00
#SBATCH --output=v3/results/logs/sbatch_v3_tagalog_%j.out
# If your condo requires an account, uncomment and set it:
##SBATCH --account=l40s-gcondo
#
# Unattended batch run of the two v3 Tagalog jobs (p003-tl-loc + p003-tl-engex)
# on the combined splits/tagalog dev_train. Pick the model with MODEL=...:
#   sbatch --export=ALL,MODEL=gemma4:31b scripts/sbatch_v3_tagalog.sh
#   sbatch scripts/sbatch_v3_tagalog.sh          # defaults to qwen3:32b
#
# A batch job has no controlling terminal, so closing your laptop or dropping
# SSH cannot kill it.
#
# Storage note: we deliberately DO NOT set OLLAMA_MODELS (models live in
# ~/.ollama; see sbatch_v3_qwen.sh).
set -uo pipefail

cd "$SLURM_SUBMIT_DIR" || exit 1

MODEL="${MODEL:-qwen3:32b}"

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
ollama serve >"v3/results/logs/ollama_serve_${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
# Make sure the server dies with the job rather than lingering on the node.
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT

# Wait (up to ~2 min) for the server to accept requests before coding.
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

# Confirm the model is present (it persists on disk between sessions).
if ! ollama list | grep -q "${MODEL%%:*}"; then
  echo "${MODEL} not found locally; pulling..."
  ollama pull "$MODEL"
fi

# --- Run both Tagalog jobs sequentially ----------------------------------------
# Defaults match the settings that stabilized the gemma rerun.
MODEL="$MODEL" ./scripts/run_v3_tagalog.sh --num-predict 8000 --timeout 1200 --ollama-url "$OLLAMA_URL" "$@"
