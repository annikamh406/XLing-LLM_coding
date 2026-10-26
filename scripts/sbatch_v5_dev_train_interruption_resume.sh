#!/usr/bin/env bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
python3 scripts/run_v5_dev_train_interruption_resume.py --verify
export PYTHON_BIN=scripts/python_v5_dev_train_interruption_resume.sh
exec bash scripts/sbatch_v5.sh "$@"
