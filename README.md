# XLing LLM Coding

This folder contains the Phase 1 English Bloom-coding LLM pilot.

## Layout

Version-independent infrastructure lives at the top level; everything specific
to one policy/prompt iteration lives in its version folder (`v1/`, `v2/`, ...).

- `LLM_validation_plan.md`: validation and lockbox rules (all versions).
- `scripts/run_bloom_coding.py`: Ollama runner for development coding.
- `scripts/llm_human_irr_report.Rmd` + `scripts/render_irr_report.R`: shared
  IRR report template and its renderer — `Rscript scripts/render_irr_report.R
  <version>` scores every run in that version folder (see step 5 below).
- `scripts/build_coding_viewer.R`: builds the interactive coding viewer
  (`coding_viewer.html`, gitignored). It auto-discovers every scored run
  (`v*/results/*llm-human-audit*.csv`), so it picks up new versions with no
  configuration: rebuild with `Rscript scripts/build_coding_viewer.R` after
  rendering a new IRR report. The viewer has a run selector (version / split /
  model), the per-run explorer (conversation context, three-coder comparison,
  model reasoning, IRR tables), and an "Agreement across versions" tab that
  plots agreement or kappa over versions with the dev split of each run
  indicated by marker shape and axis label.
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

## Multilingual splits (German, Hebrew, Spanish)

The English splits come from the dedicated `scripts/build_english_llm_dataset.py`
and `scripts/create_english_llm_splits.py`. The other languages are built by
generalized ports that share one config module:

- `scripts/_pipeline_config.py`: per-language workbook paths, coder pair,
  transcript-sheet layout, exclusion rule, and the canonical Bloom-label map.
- `scripts/build_llm_dataset.py [langs...]`: token-level dataset + human
  reference (defaults to german, hebrew, spanish). Writes
  `datasets/<lang>_llm_dataset.jsonl` etc.
- `scripts/create_llm_splits.py [langs...]`: transcript-level splits into
  `splits/<lang>/` with the same 20/25/25/30 targets, balancing objective, and
  SVG diagnostics. **Needs pandas/numpy** — run with the x86_64 interpreter at
  `/Users/annika/miniconda/bin/python3` (the arm64 `python3.10` has a broken
  pandas build); the builder has no such dependency.

Per-language quirks handled by the generalized reader, and decisions made
(2026-06-25), because the source workbooks are messier than English:

- **Single `Transcript` sheet** (no First/Second-half split, no `Half` column);
  ages still parse from the same `@ID:` lines.
- **No `exclusion` column**, so there is no "RED ... TT5" pre-output drop step
  (0 rows dropped for these languages).
- **Mixed header styles** (spaced "Not a negation?" vs R-dotted
  "Not.a.negation?") matched case/separator-insensitively; some masters lack
  `Tag Question?` / `Not a negation?` (read from coder sheets) and `Child_ID`.
- **`coded_by` carries real names** (Hebrew "Ronnie", Spanish "Daliza"/
  "Grethell"), surfaced as coders in the diagnostics.
- **Bloom labels are normalized** to the canonical six (Nonexistence,
  Rejection, Denial, Nonpossession, Uncoded, Excluded); the raw coder sheets
  contain spelling/case variants (`Nonposession`, `Nonexistance`, lowercase
  `denial`/`excluded`, ...). The dataset summary's `unmapped_bloom_labels`
  flags any label the map does not cover (currently empty for all three).
  Coder records keep `bloom_label_raw` alongside the normalized `bloom_label`.
- **German has three coder workbooks** (PZ, MP, AR); the canonical IRR pair is
  **PZ + MP** (project decision 2026-06-25). All three are row-aligned to the
  master, but only PZ+MP are used for German.

All coder workbooks are row-aligned to their master `Code` sheet (verified: 0
alignment mismatches, 0 missing context windows, no record/transcript leakage
across splits).

Per version (current version: **v3**):

- `v3/CHANGES_FROM_V2.md`: complete v2 -> v3 change log — every change with
  the v2 adjudications that motivated it, plus the criteria for judging
  whether the changes worked. (Same pattern as `v2/CHANGES_FROM_V1.md`.)
- `v3/Bloom_coding_policy_v3.md`: label and flag policy. Since v3 the policy
  is a pure rules document: change history lives only in the CHANGES file, so
  the policy can be used in prompts without leaking evaluation details. (The
  v2 policy keeps its embedded changelog; v2 is frozen.)
- `v3/bloom_v3_english_prompt.md`: prompt (`p003`).
- `v3/bloom_v3_output.schema.json`: output schema contract.
- `v3/results/`: run outputs and evaluation reports for v3 (ignored by Git).

v1 artifacts are frozen under `v1/` (policy, prompt `p001`, schema, and
`v1/results/` with the limit-20 run, the IRR report, the item-level audit CSV,
and the original single-run coding viewer). The untracked
`v1/results/build_visualization_tool.R` is the frozen v1 single-run viewer
builder; for anything new, use `scripts/build_coding_viewer.R` instead.

`datasets/`, `*/results/`, and split CSV duplicates are ignored by Git.

## Running A Coding Pass On Oscar

The repo lives on GitHub (`annikamh406/XLing-LLM_coding`) and is cloned on
Oscar at `/oscar/data/rfeiman/amcderm6/XLing-LLM_coding`. A run only needs
Git-tracked files (splits, prompt, scripts) — the gitignored `datasets/` and
`v1/inputs/` do not need to exist on Oscar.

### 1. Push from the local machine

```bash
cd ~/Documents/Research/XLing/Data/XLing-LLM_coding
git add -A && git commit -m "describe the change"
git push
```

### 2. Pull on Oscar and start Ollama on a GPU node

```bash
ssh <user>@ssh.ccv.brown.edu
cd data/amcderm6/XLing-LLM_coding
git pull

interact -n 4 -m 32g -q gpu -g 1 -t 1:00:00
module load ollama
ollama serve
```

Note the GPU node name that `interact` gives you (e.g. `gpu1404`) and leave
`ollama serve` running in this session.

Model storage (avoid filling your home quota): Ollama saves pulled models to
`~/.ollama` by default, and each model is large (gemma4:31b is ~28 GB). One
model usually fits, but a second one can exceed the home-directory quota. To
keep the model store in your data space instead, export `OLLAMA_MODELS` in the
same shell *before* `ollama serve` (and before any `ollama pull`):

```bash
export OLLAMA_MODELS=/oscar/data/rfeiman/amcderm6/ollama-models
mkdir -p "$OLLAMA_MODELS"
# one-time, to relocate a model already in home instead of re-downloading it:
# mv ~/.ollama/models/* "$OLLAMA_MODELS"/
```

`ollama serve` and `ollama pull` must see the same `OLLAMA_MODELS` value, so
set it in every session that talks to Ollama (step 2 and step 3).

Walltime guidance: `-t 1:00:00` is enough for a limit-20 smoke test
(~10 minutes at v1 pace, since the model thinks at length per token). A full
`dev_train` pass (1,521 records) took roughly 26 s/record in v1, so request
on the order of `-t 8:00:00` for that.

### 3. Run the coder from a second SSH session on the same node

```bash
ssh <user>@ssh.ccv.brown.edu   # new terminal
ssh <gpu-node-name>            # hop to the node running ollama serve
module load ollama
cd data/amcderm6/XLing-LLM_coding
# if you set OLLAMA_MODELS in step 2, export the same value here too
# first time only, if the model is not yet in the model store:
ollama pull gemma4:31b

python3 scripts/run_bloom_coding.py --split dev_train --model gemma4:31b --limit 20 --batch-size 5
```

The runner defaults to the current version (v3 prompt, `bloom_v3` schema,
prompt version `p003`) and writes directly into `v3/results/` (a
`test_lockbox` run is automatically routed to `v3/results/lockbox/` to keep
the final evaluation physically separate). Prefer
`--batch-size` of 5 or more: multiple negator tokens from the same utterance
then appear in the same request, which the repetition-flag instructions rely
on (v1 used `--batch-size 1`).

### 4. Copy results back to the local machine

Results are gitignored, so copy them with rsync (run from the local machine):

```bash
rsync -av <user>@ssh.ccv.brown.edu:/oscar/data/rfeiman/amcderm6/XLing-LLM_coding/v3/results/ \
  ~/Documents/Research/XLing/Data/XLing-LLM_coding/v3/results/
```

### 5. Score the run

```bash
Rscript scripts/render_irr_report.R v3
Rscript scripts/build_coding_viewer.R
```

The first command finds every `*_predictions.jsonl` under `v3/results/`
(including legacy `dev/` and `lockbox/` subfolders) and renders the shared
report template
(`scripts/llm_human_irr_report.Rmd`) for each, writing
`llm-human-irr_<run>.html` and `llm-human-audit_<run>.csv` next to the run
files. Names are stable per run, so re-rendering overwrites instead of
accumulating duplicates; pass `--overwrite` to re-render an existing report.
The template is the v1 report parameterized (verified to reproduce the v1
audit byte-for-byte), so numbers are comparable across versions.

The second command rebuilds the viewer; the new run appears in the run
selector and on the agreement-across-versions chart automatically.

Then check the run against the falsification criteria at the bottom of the
current CHANGES file (`v3/CHANGES_FROM_V2.md`). Important: the 20 smoke-test
rows (eng_000001-15, eng_000067-71) are development data — they were mined
for prompt examples and adjudicated — so headline dev_train metrics are
computed on the remaining ~1,501 uninspected rows; the inspected chunk is
reported separately as a rule-compliance check (see the contamination-control
section of `v3/CHANGES_FROM_V2.md`).

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
  --results-dir v1/results
```

### 6. Run the Hebrew/German 100-row prompt variants

The v3 multilingual prompt variants mirror the Spanish setup:

- `p003-he-loc`: Hebrew prompt with Hebrew-localized examples.
- `p003-he-engex`: Hebrew prompt with English examples.
- `p003-de-loc`: German prompt with German-localized examples.
- `p003-de-engex`: German prompt with English examples.

For actual server-side concurrency, start `ollama serve` with parallelism
enabled if the GPU memory can handle it:

```bash
OLLAMA_NUM_PARALLEL=4 ollama serve
```

Then start all four 100-row `dev_train` jobs in parallel from a second session:

```bash
cd data/amcderm6/XLing-LLM_coding
bash scripts/run_v3_100_multilingual.sh
```

The launcher defaults to `MODEL=gemma4:31b`, `LIMIT=100`, `BATCH_SIZE=5`, and
`SPLIT=dev_train`. Override those with environment variables or pass normal
runner flags through to all four jobs:

```bash
MODEL=gemma4:31b LIMIT=100 BATCH_SIZE=5 bash scripts/run_v3_100_multilingual.sh --overwrite --num-ctx 8192
```

Each run writes distinct output filenames under `v3/results/` because the
prompt-version tags differ. Per-job logs go to `v3/results/logs/`.

Output filenames include split, model, schema version, prompt ID, and optional
limit, e.g. `dev_train_gemma4_31b_bloom_v2_p002_limit-20_predictions.jsonl`.
The schema version, prompt ID, and prompt path are also stored in the raw
response metadata and terminal summary.

If a batch repeatedly fails schema validation, the runner writes a
`*_failed_batch-N.json` debug file under the results directory with the parsed
model payload, raw response, and validation error.

The runner refuses to run on `test_lockbox` unless `--allow-lockbox` is passed.
