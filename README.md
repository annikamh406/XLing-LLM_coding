# XLing LLM Coding

This folder contains the Phase 1 English Bloom-coding LLM pilot.

## Contents

- `Bloom_coding_policy_v1.md`: label and flag policy.
- `LLM_validation_plan.md`: validation and lockbox rules.
- `prompts/bloom_v1_english_initial_prompt.md`: initial prompt.
- `schemas/bloom_v1_output.schema.json`: output schema contract.
- `splits/english/*.jsonl`: transcript-level evaluation splits.
- `scripts/run_bloom_coding.py`: Ollama runner for development coding.

`datasets/`, `results/`, and split CSV duplicates are ignored by Git.

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
python3 scripts/run_bloom_coding.py --split dev_train --model llama3.2 --limit 20
```

Useful options:

```bash
python3 scripts/run_bloom_coding.py --help
python3 scripts/run_bloom_coding.py --split dev_train --model llama3.2 --limit 20 --batch-size 2
python3 scripts/run_bloom_coding.py --split dev_train --model gemma2:9b --limit 20
```

The runner writes predictions and raw model responses under `results/dev/`.
It refuses to run on `test_lockbox` unless `--allow-lockbox` is passed.
