# V6.4: Denial last and absence expressed as correction

Derived from V6.3.1 with the two approved interventions together:

- Sharpen the existing Denial definition and label-order item: Denial is a
  last-resort content category after checking Nonpossession, Nonexistence and
  Rejection. Correcting someone, answering a question or making a negative
  factual statement does not by itself establish Denial. The policy's
  high-level Denial rule is updated consistently.
- Replace worked example A ("No milk") with an absence-as-correction exchange:
  the adult says there is still milk in the fridge, and the child looks inside
  and says "No, there isn't any." Nonexistence still applies even though the
  child is correcting the adult.

All five full prompts use English examples and the same shared section.
The V6.3.1 example changes, Rejection-first tie-break, implicit-context
guidance, Nonexistence definition and mandatory category order are retained.
The removed V6.3 scope-reminder paragraph is not restored. Apart from version
identifiers and policy paths, only the approved passages change. IDs are
`p0064*`; schema remains `bloom_v6`.

Rebuild from the repository root:

```bash
python3 v6/6.4/make_prompts.py
```

## Submit on Oscar

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v64_diagnostic.sh
bash scripts/submit_v64_diagnostic.sh
```

This submits five Gemma4:31b jobs on the exact same frozen 200 training cases:
English 44, German 42, Hebrew 42, Spanish 39 and Tagalog 33. IDs, order,
context, references, 40/80/80 groups and original per-record seeds are
unchanged. Inference uses batch size 1, temperature 0, context 32,768 and
generation cap 8,000, with unchanged runtime and weights checks. Each job
requests one L40S, four CPUs, 48 GB RAM and 12 hours by default; the faulty
node/GPU remain excluded. `LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect
scheduling only.

Freeze: `v6/dev_train_diagnostic_6_4_freeze.json`. Outputs and validated
resumable checkpoints: `v6/results/dev_train_diagnostic_6_4/`. Earlier
versions and results are preserved; no earlier checkpoints are imported.
Recorded genuine failures stop for review before rerunning. No inference
has been launched locally.

## Score

After downloading the result directory:

```bash
python3 scripts/summarize_v64_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_4/report/report.html`. Comparisons with
V5, V6.2 and V6.3.1 are separated by language and diagnostic group, with
directional confusions, uncertainty and row-level explanations. Portable
V6.3.1 comparator predictions were validated against the completed source
checkpoints and runtime provenance before copying. Comparator and source
hashes are frozen; previous result directories are not needed on Oscar.

This combined intervention tests the reminder revision and example revision
together; it cannot separate their effects. The purposively selected training
diagnostic measures development fit and control regressions, not population
accuracy or held-out generalization. Only complete language conditions enter
the report's metrics.
