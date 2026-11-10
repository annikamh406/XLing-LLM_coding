# V6.5: Preference answers within a current interaction

Derived from V6.4 by replacing only the carrots preference-report example
with the approved pair:

- During current toy play, the adult asks "Do you like this?", the child says
  "No", and the adult stops: Rejection, even though it answers a preference
  question.
- During a discussion of animals, "I don't like ducks" reports a preference:
  Denial when a rejecting function is not reasonably supported.

These are constructed illustrations, not verbatim transcript excerpts. The
first is motivated by the clearer English toy-duck exchange; the second makes
the contrast explicit. The Spanish car case is not used as an exemplar or
treated as adjudicated: `tere [: quiere]` is a transcription correction to
"wants", not a person named Tere, and the surrounding exchange requires care.

The existing "don't want that" example and guidance permitting implicit
rejection remain. This change illustrates how an answer to a preference
question can function as rejection; it does not require a recorded offer,
add a blanket preference-to-Rejection rule, or alter human references.

All five full prompts and the shared policy use the same example pair.
V6.4's Denial-last wording, absence-as-correction example, other examples,
label order, schema and coding rules are unchanged. IDs are `p0065*`; schema
remains `bloom_v6`. Rebuild with `python3 v6/6.5/make_prompts.py`.

## Submit on Oscar

From the repository root:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v65_diagnostic.sh
bash scripts/submit_v65_diagnostic.sh
```

Five Gemma4:31b jobs run the same frozen 200 training cases: English 44,
German 42, Hebrew 42, Spanish 39 and Tagalog 33. IDs, order, context, human
references, 40/80/80 groups and original per-record seeds are unchanged.
This retains ambiguous diagnostic cases for monitoring; the new illustrations
do not attempt to encode every historical human/model disagreement.

Settings remain batch 1, temperature 0, context 32,768 and generation cap
8,000. Each job requests one L40S, four CPUs, 48 GB RAM and 12 hours by default;
runtime/weights checks and faulty node/GPU exclusions remain.
`LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect scheduling only.

Freeze: `v6/dev_train_diagnostic_6_5_freeze.json`. Outputs and validated
resumable checkpoints: `v6/results/dev_train_diagnostic_6_5/`. Earlier
versions/results are preserved. No earlier checkpoints are imported; recorded
genuine failures stop for review. No local inference has been launched.

## Score

After downloading results:

```bash
python3 scripts/summarize_v65_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_5/report/report.html`. Comparisons
against V5, V6.2 and V6.4 are separated by language and group, with directional
confusions, uncertainty and row-level explanations. Portable V6.4 comparator
predictions were validated against complete source checkpoints and runtime
provenance; all comparator and source hashes are frozen. Old result directories
are not needed for submission/scoring. Only complete language conditions enter
metrics. This selected training diagnostic is not an estimate of population
accuracy or held-out generalization.
