# V5 focused model/prompt experiments

Date: 2026-07-27.

## Decisions

- Retire `qwen3.5:122b` from new default runs. Its v5 full runs repeatedly
  exhausted the 8,000-token thinking budget without final content, and its
  Tagalog run also duplicated a record ID.
- Retain `gemma4:31b`, `qwen3.6:35b-a3b`, and `gpt-oss:120b`.
- Do not create a Qwen-specific policy prompt yet. Qwen 3.6 completed four of
  five languages and was close to Gemma overall; its missing Tagalog run was a
  duplicate-ID validation failure, not a systematic semantic failure.
- Test the condensed prompt on all three active models. If it helps only
  GPT-OSS, it can become GPT-specific without changing the common policy.
- Test Qwen's recommended non-greedy thinking-mode decoding separately.
  Qwen's documentation warns that greedy decoding can cause degradation and
  endless repetition, whereas the original v5 sweep used temperature 0:
  <https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/quickstart.md>

The condensed prompt is
`v5/bloom_v5_english_prompt_condensed.md`. It preserves the v5 label order,
Rejection/Denial live-move test, exclusion licenses, uncertainty rule, flags,
and strict output contract while removing most repeated prose and examples.

## Repair the incomplete full runs

From the Oscar checkout:

```bash
DRY_RUN=1 ./scripts/resubmit_v5_failed.sh
./scripts/resubmit_v5_failed.sh
```

This submits:

- GPT-OSS Hebrew, Spanish, and Tagalog with the original prompts and batch
  size 5. The hardened worker now aborts immediately if Slurm exposes no CUDA
  devices, preventing another silent CPU-only run.
- Qwen 3.6 Tagalog with the original prompt and batch size 1. A one-record
  schema cannot contain duplicate IDs.

## Prompt experiment sample

`scripts/build_v5_prompt_experiment_split.py` deterministically creates:

- `splits/english/dev_train_prompttest_v5.jsonl`
- `splits/english/dev_train_prompttest_v5_human_reference.jsonl`
- `splits/english/dev_train_prompttest_v5_manifest.json`

It uses only `dev_train`, excludes IDs already listed in
`splits/english/inspected_rows.txt`, requires double-coded human consensus,
and enriches the difficult Rejection and Denial classes. Because the class mix
is artificial, its overall accuracy is a paired prompt diagnostic rather than
a population-weighted performance estimate.

The runner strips all human and evaluation fields before prompting. If any
sample records are later read during qualitative error analysis, append those
specific IDs to `splits/english/inspected_rows.txt`.

## Oscar experiment matrix

Inspect the default 20-job matrix:

```bash
DRY_RUN=1 ./scripts/submit_v5_prompt_experiments.sh
```

Submit it:

```bash
./scripts/submit_v5_prompt_experiments.sh
```

The default arms are:

1. `core` — Gemma, Qwen 3.6, and GPT-OSS crossed with:
   - full versus condensed prompt;
   - batch size 1 versus 5;
   - deterministic temperature 0.
2. `gpt-reasoning` — the same four GPT-OSS prompt/batch cells with the native
   Harmony `Reasoning: high` control.
3. `qwen-sampling` — the same four Qwen prompt/batch cells with temperature
   0.6, top-p 0.95, top-k 20, min-p 0, and fixed base seed 20260727.

The native GPT reasoning-effort header is not applied to Gemma or Qwen,
because it is not a comparable control for those model families. Prompt
compactness and batch size are compared across all three models.

Useful reductions:

```bash
# Core cross-model prompt/batch comparison only (12 jobs)
ARMS=core ./scripts/submit_v5_prompt_experiments.sh

# GPT-only dry run
MODELS="gpt-oss:120b" ARMS="core gpt-reasoning" \
  DRY_RUN=1 ./scripts/submit_v5_prompt_experiments.sh

# Cheapest first-stage check: condensed prompt, batch size 1
PROMPTS=condensed BATCH_SIZES=1 ARMS=core \
  ./scripts/submit_v5_prompt_experiments.sh
```

Experiment outputs and logs stay isolated under
`v5/results/prompt_experiments/`; they are not automatically added to the
main coding viewer.

## Summarize completed conditions

```bash
python3 scripts/summarize_v5_prompt_experiments.py
```

The script writes `v5/results/prompt_experiments/summary.csv` and reports:

- exact and project-collapsed accuracy;
- Rejection, Denial, Nonexistence, and Excluded accuracy;
- certainty use and accuracy when certain;
- paired wins/losses and an exact sign-test p-value relative to each model's
  full-prompt, batch-5, temperature-0 baseline.

## Promotion criteria

- Prefer a condensed GPT prompt only if it improves paired accuracy,
  especially both directions of the Rejection/Denial boundary, without
  increasing `Excluded` or reflexive `Uncoded`.
- Prefer batch size 1 only if its gain justifies extra prompt-evaluation cost;
  it also has the operational benefit of making duplicate IDs impossible.
- Prefer Qwen sampling if it improves accuracy or eliminates validation
  failures. Do not infer a Qwen-specific prompt need from decoding failures.
- After selecting a condition on `dev_train`, run that frozen condition on
  `dev_check_1`, then `dev_check_2`, following `LLM_validation_plan.md`.
