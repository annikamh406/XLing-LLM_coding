#!/usr/bin/env bash
# Rerun the two v4 cells whose runs aborted on a duplicate-record_id batch
# (finished 2026-07-05/06), leaving no predictions file:
#
#   1. gemma4:31b  german:engex  MASKED arm only  (p004m-de-engex,
#      failed_batch-251). The unmasked p004-de-engex arm completed (1502 rows),
#      so only the masked arm is resubmitted.
#   2. llama3.3:70b  english:en  BOTH arms  (p004 failed_batch-30 AND
#      p004m failed_batch-7). Both English base arms aborted, so the whole
#      cell is resubmitted with the default RUN_SETS=unmasked,masked.
#
# Why a resubmit can succeed where the original didn't: a duplicate-record_id
# batch is a ValidationError, which run_bloom_coding.py already retries with the
# error fed back, temperature bumped to 0.4, and a varied per-attempt seed
# (see the retry loop ~line 588). These batches exhausted those retries and the
# run then raise'd, aborting before any predictions were written (predictions
# are flushed only after every batch validates). A fresh submit draws new
# samples, so the stuck batch may clear. If a cell fails identically again, the
# batch is genuinely stuck: rerun that cell with a smaller BATCH_SIZE (e.g.
# BATCH_SIZE=2) so the duplicate has fewer siblings to collide with, or fix the
# repair path in run_bloom_coding.py.
#
# This wraps scripts/submit_v4_all.sh (NOT a direct python call like the v3
# rerun) so each cell lands as its own Slurm job with the correct per-model
# resources: gemma on 1 L40S/48g, llama on 2 L40S/64g + OLLAMA_SCHED_SPREAD +
# --num-ctx 16384 (the 2026-07-01 KV-cache incident). A rerun overwrites only
# that cell's outputs.
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

# 1. gemma4:31b — masked German-engex arm only.
RUN_SETS=masked CELLS="german:engex" MODELS="gemma4:31b" ./scripts/submit_v4_all.sh

# 2. llama3.3:70b — English base cell, both arms (default RUN_SETS).
CELLS="english:en" MODELS="llama3.3:70b" ./scripts/submit_v4_all.sh
