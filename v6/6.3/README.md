# V6.3: Category scope and clearer Rejection/Denial examples

Derived from V6.2 with two approved changes:

- Remind the model that the Rejection/Denial distinction applies after
  checking Nonpossession and Nonexistence. Answering a factual question or
  correcting someone does not override an absence interpretation.
- Replace the ambiguous rule-discussion and placement contrasts. A direct
  prohibition can itself support Rejection without a separately transcribed
  action. Reporting a rule in response to a rule question illustrates Denial.
  Opposing a proposed puzzle placement illustrates Rejection; attempting it
  and requesting help illustrates reporting difficulty. A reasonably
  supported tie still favors Rejection with `certain` = `No`.

The shared section is `rejection_denial_section.md`. It is included in all
five full prompts with English examples and in the policy. Worked examples
K and T are revised consistently, replacing their earlier ambiguous contexts.
The Nonexistence definition and mandatory label order are unchanged.
Schema, output labels, language inventories and all other examples remain
unchanged. Prompt IDs are `p0063*`; the schema remains `bloom_v6`.

Rebuild from the repository root:

```bash
python3 v6/6.3/make_prompts.py
```

V6.2 and earlier prompts, freezes and results are preserved. This is a combined
intervention, so the run cannot isolate the effects of its two changes.

## Submit the same 200 cases on Oscar

From the repository root:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v63_diagnostic.sh
bash scripts/submit_v63_diagnostic.sh
```

The launcher submits five Gemma4:31b jobs: English 44, German 42, Hebrew 42,
Spanish 39 and Tagalog 33 records. IDs, order, supplied context, references,
40/80/80 diagnostic groups and original per-record seeds match the previous
runs exactly. Batch size is 1, temperature 0, context 32,768 and generation
cap 8,000, with the same frozen weights/runtime checks and L40S hardware.
Each job requests four CPUs, 48 GB RAM and 12 hours by default.
`LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect scheduling only.
The previously faulty node/GPU remain excluded.

The freeze is `v6/dev_train_diagnostic_6_3_freeze.json`. Outputs and checkpoints
are isolated in `v6/results/dev_train_diagnostic_6_3/`; earlier checkpoints
are not imported. Validated V6.3 records can be resumed by submitting again.
A recorded genuine failure requires review before rerunning. No local
inference has been launched.

## Score

After downloading the result directory:

```bash
python3 scripts/summarize_v63_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_3/report/report.html`. The report
compares V6.3 with V5 and V6.2, separately by language and diagnostic group,
and retains directional confusions, uncertainty and row-level explanations.
Portable V6.2 predictions in `baselines/` were copied only after validating
all 200 source predictions against their checkpoints and runtime provenance;
their hashes and source hashes are recorded in the new freeze. Old result
directories are not required on Oscar for submission or scoring.

Only complete language conditions enter metrics. This selected training
diagnostic measures development fit and control regressions, not population
accuracy or held-out generalization.
