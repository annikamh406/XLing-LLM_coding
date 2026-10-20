#!/usr/bin/env bash
# Coordination owns priority; the frozen original worker owns inference.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?Slurm submission directory is required}"
exec python3 scripts/coordinate_v5_dev_train.py "$@"
