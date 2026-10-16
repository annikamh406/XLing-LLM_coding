#!/usr/bin/env bash
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
python3 -c 'import sys; sys.path.insert(0,"scripts"); from run_hebrew_nfc_validation import verify_nfc; verify_nfc()'
export PYTHON_BIN=scripts/python_hebrew_nfc_validation.sh
exec bash scripts/sbatch_v5.sh "$@"
