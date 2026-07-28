#!/usr/bin/env bash
#SBATCH --job-name=xling-v5
#SBATCH --partition=l40s-gcondo
#SBATCH --gres=gpu:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48g
#SBATCH --time=24:00:00
#SBATCH --output=v5/results/logs/sbatch_v5_%x_%j.out
##SBATCH --account=l40s-gcondo
#
# Worker for one v5 (model, language, variant) cell:
#   sbatch scripts/sbatch_v5.sh gemma4:31b german engex
#
# Normally submit through scripts/submit_v5_models.sh, which supplies the
# correct GPU count, memory, context window, and walltime for each model.
#
# RUN_SETS defaults to unmasked. Set RUN_SETS=masked or
# RUN_SETS=unmasked,masked to run the optional masked arm.
set -uo pipefail

cd "$SLURM_SUBMIT_DIR" || exit 1

MODEL="${1:?usage: sbatch scripts/sbatch_v5.sh MODEL LANGUAGE VARIANT [runner args]}"
LANGUAGE="${2:?missing LANGUAGE}"
VARIANT="${3:?missing VARIANT (en|loc|engex)}"
shift 3

# CCV hosts the models used by the v5 comparison in a shared, read-only Ollama
# store. Honor an explicit caller setting, but use the shared store by default
# so jobs do not duplicate tens of GB in the home directory.
export OLLAMA_MODELS="${OLLAMA_MODELS:-/oscar/data/shared/ollama_models}"

# The two 120B-class models require two L40S GPUs. Fail early if this worker was
# submitted directly with too few GPUs instead of silently spilling to CPU.
case "$MODEL" in
  qwen3.5:122b|gpt-oss:120b) REQUIRED_GPUS=2 ;;
  *)                         REQUIRED_GPUS=1 ;;
esac
if [[ -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  echo "ERROR: Slurm exposed no CUDA devices to $MODEL." >&2
  echo "SLURM_JOB_ID=${SLURM_JOB_ID:-unset} SLURM_JOB_NODELIST=${SLURM_JOB_NODELIST:-unset} SLURM_JOB_GPUS=${SLURM_JOB_GPUS:-unset}" >&2
  echo "Refusing to let Ollama silently run this GPU job on CPU." >&2
  exit 2
fi
IFS=',' read -r -a VISIBLE_GPUS <<<"$CUDA_VISIBLE_DEVICES"
if (( ${#VISIBLE_GPUS[@]} < REQUIRED_GPUS )); then
  echo "ERROR: $MODEL requires $REQUIRED_GPUS GPU(s), but CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}." >&2
  echo "Submit through scripts/submit_v5_models.sh to get the correct resources." >&2
  exit 2
fi
echo "GPU preflight: model=$MODEL required=$REQUIRED_GPUS visible=$CUDA_VISIBLE_DEVICES"

if (( REQUIRED_GPUS > 1 )); then
  export OLLAMA_SCHED_SPREAD=1
fi

OLLAMA_PORT=$((20000 + SLURM_JOB_ID % 10000))
export OLLAMA_HOST=127.0.0.1:${OLLAMA_PORT}
OLLAMA_URL="http://127.0.0.1:${OLLAMA_PORT}/api/chat"

module load ollama 2>/dev/null || true
if ! command -v ollama >/dev/null 2>&1; then
  echo "ERROR: the Ollama executable is unavailable after 'module load ollama'." >&2
  exit 1
fi
WORKER_LOG_DIR="${LOG_DIR:-v5/results/logs}"
mkdir -p "$WORKER_LOG_DIR"
ollama serve >"$WORKER_LOG_DIR/ollama_serve_${SLURM_JOB_ID}.log" 2>&1 &
OLLAMA_PID=$!
trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT

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

AVAILABLE_MODELS="$(ollama list | awk 'NR > 1 {print $1}')"
if ! grep -Fxq "$MODEL" <<<"$AVAILABLE_MODELS"; then
  if [[ "${ALLOW_MODEL_PULL:-0}" == "1" ]]; then
    echo "$MODEL not found in $OLLAMA_MODELS; ALLOW_MODEL_PULL=1, so pulling..."
    ollama pull "$MODEL" || exit 1
  else
    echo "ERROR: $MODEL is not available in OLLAMA_MODELS=$OLLAMA_MODELS." >&2
    echo "The v5 jobs default to CCV's shared model store and do not download models." >&2
    echo "Set ALLOW_MODEL_PULL=1 with a writable OLLAMA_MODELS only if a download is intentional." >&2
    exit 2
  fi
fi

MODEL="$MODEL" LANGUAGE="$LANGUAGE" VARIANT="$VARIANT" \
LIMIT="${LIMIT:-}" SPLIT="${SPLIT:-dev_train}" RUN_SETS="${RUN_SETS:-unmasked}" \
  ./scripts/run_v5_language.sh \
    --num-predict 8000 --timeout 1200 --ollama-url "$OLLAMA_URL" "$@"
