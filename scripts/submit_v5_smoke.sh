#!/usr/bin/env bash
# Submit three independent 10-item English dev_train smoke tests, one per
# active model. qwen3.5:122b is intentionally retired from new default runs.
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
