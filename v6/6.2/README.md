# V6.2: Rejection first, conservative Denial

Implements the user-approved consolidated section in
`rejection_denial_section.md`. When Rejection and Denial are both reasonably
supported, choose Rejection with `certain` = `No`. Something must be rejected,
but evidence for it can come from the child's utterance; independent
transcription of an offer, instruction or action is not required.

The five full English-example prompts and policy are derived from 6.1.1.
The consolidated section replaces the accumulated uptake, literal/live-move,
anaphora, five-trap and negative-imperative decision prose, rather than being
appended to it. The existing worked examples retain their labels; three
explanations are made consistent with the new rule (no offer/directive
requirement, no inference solely from adult agreement). An explicit sentence
in the Uncoded instructions sends a Rejection/Denial tie to the new tie-break.
Dedicated possession/existence labels, exclusion/flag rules, schema and other
coding conventions are unchanged. This deliberately adopts an asymmetric
coding policy; historical human agreement alone is not adjudicated accuracy.

Generate the prompts with `python3 v6/6.2/make_prompts.py`. Prompt IDs are
`p0062*`; schema remains `bloom_v6`. Prior versions and their freezes remain
unchanged.

## Submit all languages on the same 200 records

From the repository root on Oscar:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v62_diagnostic.sh
bash scripts/submit_v62_diagnostic.sh
```

The launcher defaults to five Gemma jobs:

| Language | Records |
|---|---:|
| English | 44 |
| German | 42 |
| Hebrew | 42 |
| Spanish | 39 |
| Tagalog | 33 |
| Total | 200 |

The IDs, order, original context windows, human references, 40/80/80 groups,
and original per-record seeds are **identical to the frozen 6.1 diagnostic**.
No resampling or new held-out material. This is 200 records across languages,
not 200 per language.

Gemma4:31b uses batch 1, temperature 0, the same weights, Ollama 0.32.14,
model/template/parameter signatures, L40S hardware, context 32,768 and generation
cap 8,000. Every job requests four CPUs, 48 GB RAM and 12 hours by default.
`LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect scheduling only. The launcher
excludes `gpu3001`; runtime validation also rejects the previously faulty GPU
UUID. No inference overrides, normalization or model retries are added.

Outputs, logs and checkpoints go to the separate namespace
`v6/results/dev_train_diagnostic_6_2/`. V6.1/6.1.1 checkpoints are not imported;
all five languages are coded anew with v6.2. This does not depend on finishing
the separate Tagalog 6.1.1 recovery. Validated v6.2 records can be resumed;
recorded failures stop for review under the existing strict diagnostic policy.

## Score

After downloading the new result directory:

```bash
python3 scripts/summarize_v62_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_2/report/report.html`. It compares the
new outputs against the portable saved v5 and v6.1 predictions, separately by
language and diagnostic group. The JSON retains label changes, directional
confusions, uncertainty, Uncoded and row-level explanations. Only complete
language conditions enter metrics. Compare the new policy's intended
Rejection preference with both targeted repairs and control disagreements;
this selected training diagnostic is not a population/generalization estimate.

Freeze: `v6/dev_train_diagnostic_6_2_freeze.json`. The builder only verifies
the sample on subsequent calls and refuses silent regeneration. The original
6.1.1 prompt freeze and 6.1 sample freeze are checked for provenance.
