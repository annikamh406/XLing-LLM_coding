#!/usr/bin/env bash
#SBATCH --job-name=xling-v3-llama
#SBATCH --partition=l40s-gcondo
#SBATCH --gres=gpu:2
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64g
#SBATCH --time=24:00:00
#SBATCH --output=v3/results/logs/sbatch_v3_llama_%j.out
# If your condo requires an account, uncomment and set it:
##SBATCH --account=l40s-gcondo
#
# Unattended batch run of all 9 v3 limit-100 jobs with llama3.3:70b:
#   en p003; es loc+engex; de loc+engex; he loc+engex; tl loc+engex.
# Submit with:  sbatch scripts/sbatch_v3_llama.sh
#
# Two GPUs on purpose: llama3.3:70b at q4 is ~43 GB of weights, which does not
# fit on a single 48 GB L40S once the KV cache is added. OLLAMA_SCHED_SPREAD
# below makes Ollama split the layers across both GPUs so nothing spills to
# CPU. One Ollama server, one job at a time — this is not the parallel-run GPU
# contention that broke the 2026-06-30 run.
#
# Time note: 24h covers all 9 jobs. Per-token generation is slower than
# qwen3:32b on one GPU, but llama3.3 has no thinking channel, so per-item
# output is much shorter than qwen's.
#
# Storage note: we deliberately DO NOT set OLLAMA_MODELS. llama3.3:70b adds
# ~43 GB to ~/.ollama (on top of ~38 GB for gemma4:31b + qwen3:32b), for ~81 GB
# total — still under the 100 GB home soft quota, but run `checkquota` before
# the first submit. data+rfeiman is ~85% full so the models should NOT be
# relocated there.
set -uo pipefail

cd "$SLURM_SUBMIT_DIR" || exit 1

MODEL=llama3.3:70b
# Force the model to be split across both allocated GPUs instead of loading
# onto one and offloading the overflow to CPU.
export OLLAMA_SCHED_SPREAD=1

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
if ! ollama list | grep -q "$MODEL"; then
  echo "$MODEL not found locally; pulling (~43 GB, one-time)..."
  ollama pull "$MODEL"
fi

# --- Run all nine jobs sequentially --------------------------------------------
# run_v3_100_all_langs.sh does en/es/de/he one at a time, then run_v3_tagalog.sh
# does tl-loc + tl-engex. Both rely on the hardened run_bloom_coding.py
# (retryable timeouts / empty content / dropped connections). Extra args pass
# straight through; defaults below match the settings that stabilized the gemma
# rerun. NOT -e up top: if the main sweep fails partway, still attempt Tagalog.
#
# --num-ctx 16384 is CRITICAL for llama3.3:70b. Left unpinned (job 3611671,
# 2026-07-01) Ollama used llama3.3's full ~128k default context, so the KV cache
# alone was ~40 GiB. Weights (~39 GiB) + that KV blew past the two L40S's 90 GiB
# combined, spilling 29/81 layers to CPU; every /api/chat then ran past the
# 1200s timeout (HTTP 500) and all nine runs failed. Pinning ctx to 16384
# (prompt ~3k tokens + --num-predict 8000, with headroom) shrinks the KV cache
# to ~5 GiB so the whole model stays on GPU. gemma/qwen didn't need this: smaller
# models with smaller default contexts fit on a single GPU.
status=0
MODEL="$MODEL" ./scripts/run_v3_100_all_langs.sh --num-ctx 16384 --num-predict 8000 --timeout 1200 --ollama-url "$OLLAMA_URL" "$@" || status=1
MODEL="$MODEL" ./scripts/run_v3_tagalog.sh       --num-ctx 16384 --num-predict 8000 --timeout 1200 --ollama-url "$OLLAMA_URL" "$@" || status=1

if [[ "$status" -eq 0 ]]; then
  echo "All nine ${MODEL} v3 limit-100 runs finished successfully."
else
  echo "At least one ${MODEL} run failed. Check logs in v3/results/logs." >&2
fi
exit "$status"
