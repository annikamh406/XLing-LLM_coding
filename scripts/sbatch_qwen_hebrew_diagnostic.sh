#!/usr/bin/env bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
module load ollama
command -v ollama >/dev/null
export OLLAMA_MODELS=/oscar/data/shared/ollama_models
export OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=false OLLAMA_KV_CACHE_TYPE=f16
export EXPECTED_OLLAMA_VERSION=0.32.14
export EXPECTED_MODEL_BLOB_SHA256=f5ee307a2982106a6eb82b62b2c00b575c9072145a759ae4660378acda8dcf2d
memory=$(nvidia-smi --id="${CUDA_VISIBLE_DEVICES:?Slurm must expose a GPU}" --query-gpu=memory.total --format=csv,noheader,nounits)
[[ "$memory" =~ ^[0-9]+$ ]] && ((memory>=45000)) || { echo 'Expected one 48 GB GPU' >&2; exit 2; }
exec python3 scripts/diagnose_qwen_hebrew.py --output "v5/results/hebrew_parser_diagnostic/job_${SLURM_JOB_ID}"
