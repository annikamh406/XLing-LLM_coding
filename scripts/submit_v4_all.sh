#!/usr/bin/env bash
# Submit the full v4 evaluation matrix to Slurm: 27 independent jobs =
# 3 models x 9 (language, example-variant) cells:
#
#   english:en   german:loc  german:engex  hebrew:loc  hebrew:engex
#   spanish:loc  spanish:engex  tagalog:loc  tagalog:engex
#
# Each job gets its own GPU allocation and job-unique Ollama port, so the
# jobs are safe to run in parallel (the 2026-07-01 cross-wiring needed a
# SHARED port; Slurm's gres isolation keeps GPUs private per job). Inside a
# job, the unmasked and masked arms run sequentially on one server.
#
# Resources per model:
#   gemma4:31b / qwen3:32b : 1x L40S, 48g  (fits on one GPU)
#   llama3.3:70b           : 2x L40S, 64g, OLLAMA_SCHED_SPREAD +
#                            --num-ctx 16384 (2026-07-01 incident: default
#                            128k ctx -> ~40 GB KV cache -> CPU spill ->
#                            every batch timed out)
#
# Usage:
#   ./scripts/submit_v4_all.sh                 # submit everything (27 jobs)
#   MODELS="qwen3:32b" ./scripts/submit_v4_all.sh          # one model (9 jobs)
#   CELLS="german:loc hebrew:engex" ./scripts/submit_v4_all.sh   # some cells
#   RUN_SETS=masked ./scripts/submit_v4_all.sh # only the masked arm
#   LIMIT=10 ./scripts/submit_v4_all.sh        # smoke test (see note below)
#   DRY_RUN=1 ./scripts/submit_v4_all.sh       # print sbatch commands only
#
# Full-split by default (no --limit): the first ~100 rows per language are
# development data (splits/*/inspected_rows.txt), so a limit-100 evaluation
# would score mostly on mined rows. Use LIMIT only for smoke tests.
#
# Rerunning a failed cell: resubmit just that cell, e.g.
#   CELLS="tagalog:loc" MODELS="llama3.3:70b" ./scripts/submit_v4_all.sh
# (finished runs are plain files in v4/results/; a rerun overwrites that
# cell's outputs only).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$LLM_DIR"

MODELS="${MODELS:-gemma4:31b qwen3:32b llama3.3:70b}"
CELLS="${CELLS:-english:en german:loc german:engex hebrew:loc hebrew:engex spanish:loc spanish:engex tagalog:loc tagalog:engex}"
DRY_RUN="${DRY_RUN:-}"

# Pass per-run settings to the jobs via the environment + `--export=ALL`, NOT
# inline in `--export=...`. Slurm's --export list is itself comma-delimited, so
# a value containing a comma (RUN_SETS="unmasked,masked") gets split — the
# stray "masked" became a bare var name and RUN_SETS arrived as just
# "unmasked", silently dropping the masked arm (observed on job 3645334). With
# --export=ALL, sbatch forwards the whole submitting environment as-is.
export LIMIT="${LIMIT:-}"
export SPLIT="${SPLIT:-dev_train}"
export RUN_SETS="${RUN_SETS:-unmasked,masked}"

# Slurm needs the -o directory to exist at submit time.
mkdir -p v4/results/logs

submit() {
  if [[ -n "$DRY_RUN" ]]; then
    echo "DRY: $*"
  else
    "$@"
  fi
}

for model in $MODELS; do
  # Short tag for job names: gemma4:31b -> gemma4, llama3.3:70b -> llama3.3
  model_tag="${model%%:*}"
  if [[ "$model" == llama* ]]; then
    resources=(--gres=gpu:2 --mem=64g)
    extra_args=(--num-ctx 16384)
  else
    resources=(--gres=gpu:1 --mem=48g)
    extra_args=()
  fi
  for cell in $CELLS; do
    language="${cell%%:*}"
    variant="${cell##*:}"
    submit sbatch \
      --job-name="v4-${model_tag}-${language}-${variant}" \
      "${resources[@]}" \
      --export=ALL \
      scripts/sbatch_v4.sh "$model" "$language" "$variant" \
      ${extra_args[@]+"${extra_args[@]}"}
  done
done
