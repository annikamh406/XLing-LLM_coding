#!/usr/bin/env bash
# Rerun every v4 arm whose run aborted on a stuck batch (inventory checked
# 2026-07-21), leaving no predictions file. This submits 6 Slurm jobs covering
# 10 missing arms:
#
#   gemma4:31b
#     - german:engex  MASKED only (p004m-de-engex; failed batch 251)
#
#   llama3.3:70b
#     - english:en    BOTH arms (p004 batch 30; p004m batch 7)
#     - hebrew:engex  BOTH arms (p004 batch 182; p004m batch 51)
#     - hebrew:loc    MASKED only (p004m-he-loc batch 51)
#     - tagalog:loc   BOTH arms (p004-tl-loc batch 3; p004m-tl-loc batch 1)
#     - tagalog:engex BOTH arms (p004-tl-engex batch 3; p004m-tl-engex batch 1)
#
# All other v4 matrix arms already have full-length prediction files locally.
# Restricting RUN_SETS per group avoids overwriting completed arms.
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
# Usage on Oscar:
#   cd /oscar/data/rfeiman/amcderm6/XLing-LLM_coding
#   git pull
#   DRY_RUN=1 ./scripts/rerun_v4_failures.sh  # verify the 6 sbatch commands
#   ./scripts/rerun_v4_failures.sh            # submit all 10 missing arms
#   squeue -u "$USER"                         # monitor the jobs
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
# These are specifically the missing full dev_train arms. Clear any inherited
# smoke-test limit and pin the split so a stale shell variable cannot submit a
# different workload by accident.
export LIMIT=""
export SPLIT="dev_train"

# 1. gemma4:31b — masked German-engex arm only.
RUN_SETS=masked CELLS="german:engex" MODELS="gemma4:31b" ./scripts/submit_v4_all.sh

# 2. llama3.3:70b — four cells missing both arms. Each cell is one Slurm
# job; its unmasked and masked runs execute sequentially on the allocated GPUs.
RUN_SETS=unmasked,masked \
  CELLS="english:en hebrew:engex tagalog:loc tagalog:engex" \
  MODELS="llama3.3:70b" ./scripts/submit_v4_all.sh

# 3. llama3.3:70b — Hebrew localized examples, masked arm only. The matching
# unmasked p004-he-loc run is already complete (963 rows).
RUN_SETS=masked CELLS="hebrew:loc" MODELS="llama3.3:70b" \
  ./scripts/submit_v4_all.sh
