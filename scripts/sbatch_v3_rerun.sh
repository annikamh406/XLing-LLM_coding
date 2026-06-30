#!/usr/bin/env bash
#SBATCH --job-name=xling-v3-rerun
#SBATCH --partition=l40s-gcondo
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48g
#SBATCH --time=6:00:00
#SBATCH --output=v3/results/logs/sbatch_v3_rerun_%j.out
# If your condo requires an account, uncomment and set it:
##SBATCH --account=l40s-gcondo
#
# Unattended batch rerun of the 3 failed v3 limit-100 jobs (he-loc, he-engex,
# de-loc). A batch job has no controlling terminal, so closing your laptop or
# dropping SSH cannot kill it — unlike the interactive `interact` session, which
# died mid-run. Submit with:  sbatch scripts/sbatch_v3_rerun.sh
set -uo pipefail

cd "$SLURM_SUBMIT_DIR" || exit 1

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
if ! ollama list | grep -q "gemma4:31b"; then
  echo "gemma4:31b not found locally; pulling..."
  ollama pull gemma4:31b
fi

# --- Run the three failed jobs sequentially -----------------------------------
# rerun_v3_100_failures.sh does he-loc, he-engex, de-loc one at a time and
# relies on the hardened run_bloom_coding.py (retryable timeouts / empty content
# / dropped connections). Extra args pass straight through.
./scripts/rerun_v3_100_failures.sh "$@"
