#!/usr/bin/env bash
# Submit four independent 10-item English dev_train smoke tests, one per model.
#
# The smoke outputs include `_limit-10` in their filenames, so they cannot
# collide with the later full-run outputs.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LIMIT="${LIMIT:-10}"
export CELLS="${CELLS:-english:en}"
export WALLTIME="${WALLTIME:-04:00:00}"
export RUN_SETS="${RUN_SETS:-unmasked}"

exec "$SCRIPT_DIR/submit_v5_models.sh"
