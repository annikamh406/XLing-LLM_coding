# Frozen v1 inputs

Byte-exact copies, made 2026-06-10, of the dataset and split files as they
existed when the v1 run was executed (gemma4:31b, prompt `p001`, schema
`bloom_v1`, dev_train limit-20, run date 2026-05-28) and when the v1 IRR
report and audit CSV were generated.

- `datasets/`: output of `scripts/build_english_llm_dataset.py` as of
  2026-05-27/28 (source workbooks:
  `Data/Transcripts/English/2024-03-04_negation_coding_bloom_choi{,_EB,_WP}.xlsx`).
- `splits/english/`: output of `scripts/create_english_llm_splits.py`
  (seed 20260527, 20000 iterations) over those datasets.

Snapshot reason: on 2026-06-10 the pipeline scripts were extended to add
`negator_index_in_utterance` / `negators_in_utterance` fields and the live
files under `datasets/` and `splits/english/` were regenerated with the new
fields. Regeneration was verified to change nothing except adding those two
fields (same record_ids, same split membership, all v1 fields identical), but
these copies preserve the exact v1 bytes regardless.

The same v1 state is also recoverable from Git history (the split JSONL files
are tracked; see commits prior to 2026-06-10). This folder is gitignored
because it duplicates ~190 MB already represented in history.

To reproduce the v1 run exactly, point the runner at these frozen splits:

```bash
python3 scripts/run_bloom_coding.py --split dev_train --model gemma4:31b \
  --limit 20 --batch-size 1 \
  --prompt v1/bloom_v1_english_initial_prompt.md \
  --schema-version bloom_v1 --prompt-version p001 \
  --split-dir v1/inputs/splits/english \
  --results-dir v1/results/dev
```
