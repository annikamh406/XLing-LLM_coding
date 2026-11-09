# V6.3.1: V6.3 examples without the scope reminder

This candidate removes only the opening scope-reminder paragraph from V6.3:

> **Apply this distinction after checking Nonpossession and Nonexistence.** Answering a factual question or contradicting a claim does not by itself establish Denial. If the negation expresses absence, use Nonexistence, even when it also corrects someone.

All V6.3 example changes remain, including worked examples K and T. The
Rejection-first preference, implicit-context guidance, Nonexistence definition,
mandatory label order, schema and all other coding instructions are unchanged.
The paragraph is removed from all five full English-example prompts and the
policy. Only prompt IDs and policy paths otherwise differ from V6.3.
Prompt IDs are `p00631*`; schema remains `bloom_v6`.

Rebuild from the repository root:

```bash
python3 v6/6.3.1/make_prompts.py
```

## Submit on Oscar

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v631_diagnostic.sh
bash scripts/submit_v631_diagnostic.sh
```

Five Gemma4:31b jobs use the exact same frozen 200 training cases: English 44,
German 42, Hebrew 42, Spanish 39 and Tagalog 33. IDs, order, context, human
references, 40/80/80 diagnostic groups, original per-record seeds and inference
settings are unchanged. Batch size is 1, temperature 0, context 32,768 and
generation cap 8,000. The existing runtime/weights checks, one-L40S requirement
and faulty node/GPU exclusions remain. Each job requests four CPUs, 48 GB RAM
and 12 hours by default. `LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect
scheduling only.

The freeze is `v6/dev_train_diagnostic_6_3_1_freeze.json`. Outputs and validated
resumable checkpoints go to `v6/results/dev_train_diagnostic_6_3_1/`. Prior
version files/results are preserved and their checkpoints are not imported.
Recorded genuine failures stop for review before rerunning. No local model
inference has been launched.

## Score

After downloading results:

```bash
python3 scripts/summarize_v631_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_3_1/report/report.html`. The report
compares V6.3.1 with V5, V6.2 and V6.3 by language and diagnostic group. The
V6.3 comparison tests removal of the reminder while retaining examples; the
V6.2 comparison tests example changes without the reminder. Portable V6.3
predictions were copied only after validating the complete source run and
runtime provenance; V6.2 predictions are inherited from its frozen portable
comparator. Both are hashed in the new manifest, so old result directories
are not needed for submission or scoring.

Only complete language conditions enter metrics. This is a selected training
diagnostic, not an estimate of population accuracy or held-out generalization.
