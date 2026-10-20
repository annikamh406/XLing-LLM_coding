#!/usr/bin/env bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
python3 scripts/check_v5_dev_train_current.py
export PYTHON_BIN=scripts/python_v5_dev_train_current.sh
exec bash scripts/sbatch_v5.sh "$@"
