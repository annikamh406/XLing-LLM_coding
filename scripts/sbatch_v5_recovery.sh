#!/usr/bin/env bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
python3 scripts/check_v5_recovery_freeze.py
export VALIDATION_PYTHON="${VALIDATION_PYTHON:-python3}"
export PYTHON_BIN=scripts/python_v5_recovery.sh
exec bash scripts/sbatch_v5.sh "$@"
