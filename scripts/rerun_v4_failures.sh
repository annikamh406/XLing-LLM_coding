#!/usr/bin/env bash
# Rerun the two v4 cells whose runs aborted on a stuck batch (finished
# 2026-07-05/06), leaving no predictions file:
#
#   1. gemma4:31b  german:engex  MASKED arm only  (p004m-de-engex,
#      failed_batch-251, thinking-channel runaway -> empty content). The
#      unmasked p004-de-engex arm completed (1502 rows), so only the masked
#      arm is resubmitted.
#   2. llama3.3:70b  english:en  BOTH arms  (p004 failed_batch-30 AND
#      p004m failed_batch-7, both "Duplicate record_id"). Both English base
#      arms aborted, so the whole cell is resubmitted with the default
#      RUN_SETS=unmasked,masked.
#
# Why the FIRST rerun (2026-07-06/07) went nowhere, and why this one is
# different: run_bloom_coding.py retries a failed batch with a bumped
# temperature and a per-attempt seed, but that seed used to be fixed to the
# attempt index (1, 2). A fixed seed makes the retries deterministic across
# submissions too, so a batch that exhausts its retries once fails identically
# on every resubmit -- exactly what happened. The retry loop now draws a RANDOM
# per-attempt seed and escalates temperature (0.4 -> 0.7), so a fresh submit
# genuinely resamples. On top of that, this rerun shrinks BATCH_SIZE from 5 to
# 2: fewer records per call means fewer siblings for a duplicate/omitted
# record_id to collide with, and a shorter runway for gemma's thinking loop.
# (Predictions are flushed only after every batch validates, so an aborted run
# leaves no predictions file and a rerun overwrites only that cell's outputs.)
#
# This wraps scripts/submit_v4_all.sh (NOT a direct python call like the v3
# rerun) so each cell lands as its own Slurm job with the correct per-model
# resources: gemma on 1 L40S/48g, llama on 2 L40S/64g + OLLAMA_SCHED_SPREAD +
# --num-ctx 16384 (the 2026-07-01 KV-cache incident).
#
# Usage (on Oscar, from anywhere):
#   ./scripts/rerun_v4_failures.sh            # submit both reruns
#   DRY_RUN=1 ./scripts/rerun_v4_failures.sh  # print the sbatch commands only
#
# After the jobs finish, pull the results back and regenerate reports + viewer:
#   Rscript scripts/render_irr_report.R v4 --exclude 'limit-'
#   Rscript scripts/build_coding_viewer.R
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

# Smaller batches for the stuck cells (default is 5). Override at call time if
# a cell still won't clear, e.g. BATCH_SIZE=1 ./scripts/rerun_v4_failures.sh.
export BATCH_SIZE="${BATCH_SIZE:-2}"

# 1. gemma4:31b — masked German-engex arm only.
RUN_SETS=masked CELLS="german:engex" MODELS="gemma4:31b" ./scripts/submit_v4_all.sh

# 2. llama3.3:70b — English base cell, both arms (default RUN_SETS).
CELLS="english:en" MODELS="llama3.3:70b" ./scripts/submit_v4_all.sh
