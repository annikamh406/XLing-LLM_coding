# V6.1.1: utterance as evidence

This remains the first Rejection/Denial intervention. It adds the approved
clarification that the child's words are evidence for the speech act:

- A child can initiate a rejection without an explicit preceding offer or
  instruction.
- An unclear referent does not necessarily make the function unclear.
- The same words can also correct a claim or describe a preference; use the
  whole exchange rather than automatically selecting either label.
- Adequate evidence for an inferred action or claim can come from the target
  utterance and surrounding context together.

The plate illustration, uptake distinction and contrasting toy examples from
6.1 are retained. No other mismatch-review hypotheses were added.

The five full English-example prompts and policy are derived from the preserved
6.1 files by `python3 v6/6.1.1/make_prompts.py`. Prompt IDs are `p00611*` and
the schema is unchanged (`bloom_v6`). The new prompt headers also correct the
parent's policy-path typo to point to this version's policy. V6.1 prompts,
generator, freeze, inputs and results remain unchanged.

## Same-subset diagnostic

`v6/dev_train_diagnostic_6_1_1_freeze.json` inherits the **exact** 200-record
6.1 diagnostic, without resampling: IDs, order, 40/80/80 groups, human
references, source context, original singleton seeds and all inference
settings. It checks its parent freeze by hash and compares inherited fields
directly. This is a repeated training diagnostic, not a new generalization
sample.

Validated 6.1 predictions are frozen in `baselines/*_v61_predictions.jsonl`.
Saved v5 predictions are reused from the original diagnostic. Raw responses
and checkpoints used to validate the 6.1 comparator are recorded by source
hash; they do not need to be transferred to run or score 6.1.1.

After pulling on Oscar, from the repository root:

```bash
git pull --ff-only
python3 scripts/v611_diagnostic.py
DRY_RUN=1 bash scripts/submit_v611_diagnostic.sh
bash scripts/submit_v611_diagnostic.sh
```

Five regular-condo jobs use Gemma4:31b, batch 1, temperature 0, the original
per-record seeds, frozen Ollama/model/template/parameters, one L40S, context
32,768 and generation cap 8,000. No normalization or model retries are added.
`LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect scheduling only. All outputs
and checkpoints go to `v6/results/dev_train_diagnostic_6_1_1/`; no previous
predictions are imported as checkpoints. Interrupted jobs resume validated
records; genuine recorded failures require review before an amended retry.

After downloading that results directory:

```bash
python3 scripts/summarize_v611_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_1_1/report/report.html`. It compares
6.1.1 with **both v5 and 6.1**, separately by sample group and language, with
paired repairs/regressions, label confusions, certainty/Uncoded changes and
three-version comments. Partial language conditions never enter agreement
metrics. Review whether 6.1's nine repairs persist and which of its thirteen
control disagreements are recovered, as well as any new disagreements.
Human-consensus agreement remains distinct from policy adjudication.

No additional inference, check-split access or lockbox access is needed to
prepare these files. Building the freeze requires the completed 6.1 results
once; subsequent verification uses the portable frozen snapshots.
