# V6.1 training diagnostic

V6.1 is the current v6 draft: the v5 full English-example prompts plus the
agreed negation-target guidance and examples. Prompt IDs start with `p0061`;
the output schema remains `bloom_v6`. No other mismatch-review hypotheses
have been added. The existing v5 launchers and defaults remain unchanged.

## Frozen sample

`dev_train_diagnostic_6_1_freeze.json` fixes 200 dev_train records:

| Language | Targeted errors | Relevant correct controls | Broader correct controls | Total |
|---|---:|---:|---:|---:|
| English | 12 | 16 | 16 | 44 |
| German | 10 | 16 | 16 | 42 |
| Hebrew | 10 | 16 | 16 | 42 |
| Spanish | 7 | 16 | 16 | 39 |
| Tagalog | 1 | 16 | 16 | 33 |
| Total | 40 | 80 | 80 | 200 |

Targeted cases are manually selected plausible examples of the intervention's
scope, not independently adjudicated errors. Some have ambiguous functions or
parsing confounds. They include the plate, Noah's Ark, ownership, adult-uptake,
agency and action-inference examples discussed during development. They are
all human Rejection / v5 Gemma Denial mismatches. This intentionally targets
the motivating error direction; both Rejection and Denial controls test the
reverse risk.

Relevant controls use a reproducible retrieval rule: previously correct
Rejection/Denial records enriched for multiword negation and ownership,
deixis, preference or action words in the target or nearby turns. This is
feature enrichment, not a claim that every control exemplifies the same
pragmatic mechanism. Each language has eight of each label.

Broader controls span Rejection, Denial, Nonexistence (with Nonpossession
collapsed) and Excluded. The intended Uncoded quota could not be met from
eligible, previously correct cases; deterministic fallbacks and actual class
counts are recorded in the freeze. The report still tracks new Uncoded
outputs and uncertainty.

All cases require two available human labels that agree after the existing
label collapse, and neither human may have marked repetition Yes. One record
is selected per target utterance. At most two selected records can occur in
any 20-observed-turn window within a transcript/half, across all three groups.
Observed turns are reconstructed from the union of dev_train context windows;
missing turns make this a conservative proximity cap, not an independence
guarantee. Original context windows are unchanged.

The selected inputs, human references and saved v5 predictions are portable
files under `splits/<language>/dev_train_diagnostic_6_1*.jsonl`. Membership,
selection reasons, original batch positions, seeds, source hashes and runtime
signatures are recorded in the freeze. Running the builder again verifies
the frozen sample rather than resampling it. All selected records are
designated inspected development material; historical v5 reports are retained.

## Run on Oscar

Transfer the implementation and new split/freeze files to the Oscar checkout
before running these commands from the repository root. Results directories
are gitignored; the launcher does not need the full historical v5 result files.

```bash
python3 scripts/v61_diagnostic.py
DRY_RUN=1 bash scripts/submit_v61_diagnostic.sh
bash scripts/submit_v61_diagnostic.sh
```

This submits five regular-condo jobs, one per language, each with one L40S,
four CPUs, 48 GB RAM and a 12-hour scheduling limit. Scheduling can be changed
with `WALLTIME`, `CONDO_ACCOUNT` and `LANGUAGES`. For example:

```bash
LANGUAGES=english bash scripts/submit_v61_diagnostic.sh
```

Inference is fixed to the Gemma baseline: model weights, Ollama 0.32.14,
model/template digests and parameter values, batch 1, temperature 0, context
32,768, generation cap 8,000, no normalization and no model retries. Each
record retains its original effective seed, read from the v5 raw response,
rather than acquiring a new seed based on subset position. Parameter-order
differences are accepted only when parameter names and values match exactly.
Every request uses the existing allowlist to remove human labels, selection
groups and evaluation metadata from the record sent to the model.

Validated records are checkpointed atomically. Re-submitting resumes saved
records; a completed run performs no further inference. An interrupted
unfinished request may be repeated on resume, as in the original Gemma
baseline. A recorded response/transport/validation failure stops the run and
blocks an unamended retry. No inference settings, model selection or split
can be changed through inherited v5 environment variables.

No v5 inference is submitted. No check or lockbox records are used.

## Compare results

Download `v6/results/dev_train_diagnostic_6_1/` from Oscar, then run:

```bash
python3 scripts/summarize_v61_diagnostic.py
```

The report lives at
`v6/results/dev_train_diagnostic_6_1/report/report.html`, with a full JSON
audit beside it. Partial language conditions are shown as incomplete and
excluded from metrics. Complete conditions must match the freeze, checkpoint,
runtime and original per-record seeds.

Report targeted repairs separately from regressions in the two control
groups, by language. Include both Rejection-to-Denial and Denial-to-Rejection
confusions, all other label changes, uncertainty and Uncoded. Inspect whether
changed explanations identify the intended target, rather than just matching
the reference label. Do not promote solely on pooled diagnostic accuracy or
treat individual tokens from a shared episode as independent evidence.

This sample is intentionally optimized for training development. Use it to
decide whether a full dev_train run is worthwhile, then freeze the selected
candidate before a separately authorized held-out generalization check.

## Changed-case viewer

Run `python3 scripts/build_v61_changes_viewer.py` to build
`v6/results/dev_train_diagnostic_6_1/changes_viewer.html`. It compares the
validated saved predictions without launching inference. The viewer defaults
to label changes, with separate filters for newly agreeing cases, newly
disagreeing controls, and certainty-only changes. Filter by language or sample
group, search by utterance/ID/transcript, and compare the v5 and v6.1 comments
beside the human reference and highlighted transcript context. Human coding
notes are available in a disclosure below the transcript. Record-specific
URL fragments preserve the selected case when opening a saved link.
