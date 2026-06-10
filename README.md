# XLing LLM Coding

This folder contains the Phase 1 English Bloom-coding LLM pilot.

## Layout

Version-independent infrastructure lives at the top level; everything specific
to one policy/prompt iteration lives in its version folder (`v1/`, `v2/`, ...).

- `LLM_validation_plan.md`: validation and lockbox rules (all versions).
- `scripts/run_bloom_coding.py`: Ollama runner for development coding.
- `splits/english/*.jsonl`: transcript-level evaluation splits (shared across
  versions; `splits/english/diagnostics/` holds split diagnostics).
- `datasets/`: token-level source datasets (ignored by Git).
- `v1/inputs/`: frozen byte-exact copies of the datasets and splits the v1 run
  used (ignored by Git apart from its README; same state is in Git history).

Since 2026-06-10 every dataset/split record carries
`negator_index_in_utterance` and `negators_in_utterance` so the model knows
which token of a multi-negator utterance it is coding (needed for the
repetition flag). Regenerating with these fields was verified to change
nothing else: identical record ids, split membership, and all other fields.

Per version (current version: **v2**):

- `v2/CHANGES_FROM_V1.md`: complete v1 -> v2 change log — every policy,
  prompt, schema, pipeline, and runner change with the v1 error analysis that
  motivated it, plus the criteria for judging whether the changes worked.
- `v2/Bloom_coding_policy_v2.md`: label and flag policy, with a changelog of
  what changed from v1 and why.
- `v2/bloom_v2_english_prompt.md`: prompt (`p002`).
- `v2/bloom_v2_output.schema.json`: output schema contract.
- `v2/results/`: run outputs and evaluation reports for v2 (ignored by Git).

v1 artifacts are frozen under `v1/` (policy, prompt `p001`, schema, and
`v1/results/` with the limit-20 run, the IRR report, the item-level audit CSV,
and the interactive coding viewer). `v1/results/build_visualization_tool.R`
(untracked) rebuilds the viewer HTML from the audit CSV plus the split, human
reference, and raw-response files; run it with `Rscript` after re-rendering
the IRR report.

`datasets/`, `*/results/`, and split CSV duplicates are ignored by Git.

## Smoke Test On Oscar With Ollama

Start an Ollama server on a GPU node first:

```bash
interact -n 4 -m 32g -q gpu -g 1 -t 1:00:00
module load ollama
ollama serve
```

In a second SSH session, connect to the same GPU node and run:

```bash
module load ollama
cd XLing-LLM_coding
python3 scripts/run_bloom_coding.py --split dev_train --model gemma4:31b --limit 20 --batch-size 5
```

The runner defaults to the current version (v2 prompt, `bloom_v2` schema,
prompt version `p002`) and writes under `v2/results/dev/`. Prefer
`--batch-size` of 5 or more: multiple negator tokens from the same utterance
then appear in the same request, which the repetition-flag instructions rely
on.

Useful options:

```bash
python3 scripts/run_bloom_coding.py --help
python3 scripts/run_bloom_coding.py --split dev_train --model llama3.2 --limit 20
# reproduce the v1 run exactly (frozen inputs, original prompt/schema/batching):
python3 scripts/run_bloom_coding.py --split dev_train --model gemma4:31b \
  --limit 20 --batch-size 1 \
  --prompt v1/bloom_v1_english_initial_prompt.md \
  --schema-version bloom_v1 --prompt-version p001 \
  --split-dir v1/inputs/splits/english \
  --results-dir v1/results/dev
```

Output filenames include split, model, schema version, prompt ID, and optional
limit, e.g. `dev_train_gemma4_31b_bloom_v2_p002_limit-20_predictions.jsonl`.
The schema version, prompt ID, and prompt path are also stored in the raw
response metadata and terminal summary.

If a batch repeatedly fails schema validation, the runner writes a
`*_failed_batch-N.json` debug file under the results directory with the parsed
model payload, raw response, and validation error.

The runner refuses to run on `test_lockbox` unless `--allow-lockbox` is passed.
