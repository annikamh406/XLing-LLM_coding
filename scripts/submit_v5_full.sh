#!/usr/bin/env bash
# Submit the full primary v5 dev_train matrix:
# four models x five language/prompt cells = 20 independent Slurm jobs.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${LIMIT:-}" ]]; then
  echo "ERROR: submit_v5_full.sh does not accept LIMIT; it always runs the full split." >&2
  exit 2
fi

export LIMIT=""
export CELLS="${CELLS:-english:en german:engex hebrew:engex spanish:engex tagalog:engex}"
export WALLTIME="${WALLTIME:-24:00:00}"
export RUN_SETS="${RUN_SETS:-unmasked}"

exec "$SCRIPT_DIR/submit_v5_models.sh"
