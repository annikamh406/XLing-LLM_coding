#!/usr/bin/env bash
# Recheck the freeze on the compute node, including on a requeue.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
"${PYTHON_BIN:-python3}" scripts/check_v5_validation_freeze.py
exec bash scripts/sbatch_v5.sh "$@"
