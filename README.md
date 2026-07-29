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
  model reasoning, IRR tables), and a "Compare runs" tab. The comparison opens
  on the current run's language, supports multi-select language checkboxes plus
  model / prompt-example filters, and plots each selected language separately
  in a responsive grid. Agreement or kappa and optional diagnostic coder lines
  share the same controls; exact filtered results remain in the table below.
  A separate "Prompt experiments" tab summarizes the class-enriched v5
  condition matrix without mixing it into the population-oriented run trends;
  when prompt-experiment outputs and their generated split are present, the
  viewer refreshes and embeds `v5/results/prompt_experiments/summary.csv`.
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

Per version (current version: **v5**):

- `v5/CHANGES_FROM_V4.md`: complete v4 -> v5 change log, including the
  adjudication principle, retained rules, prompt changes, and falsification
  criteria.
- `v5/Bloom_coding_policy_v5.md`: label and flag policy. Since v3 the policy
  is a pure rules document: change history lives only in the CHANGES file, so
  the policy can be used in prompts without leaking evaluation details. (The
  v2 policy keeps its embedded changelog; v2 is frozen.)
- `v5/bloom_v5_english_prompt.md`: English prompt (`p005`); the four
  non-English languages each have localized- and English-example variants.
- `v5/bloom_v5_output.schema.json`: output schema contract.
- `v5/results/`: run outputs and evaluation reports for v5 (ignored by Git).

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

### Recommended v5 Slurm workflow

The v5 batch launchers use CCV's shared Ollama model store by default and
start one private, job-local Ollama server per Slurm job. Do not start a
separate interactive `ollama serve` process for these runs.

Three-model, first-10-English-record smoke test:

```bash
DRY_RUN=1 ./scripts/submit_v5_smoke.sh  # inspect the three sbatch commands
./scripts/submit_v5_smoke.sh
```

The three active models and their L40S allocations are:

- `gemma4:31b`: one GPU;
- `qwen3.6:35b-a3b`: one GPU;
- `gpt-oss:120b`: two GPUs.

`qwen3.5:122b` is retired from new default runs after its v5 full-run
thinking-channel failures. It remains available only as an explicit legacy
override.

All three use the unmasked English v5 prompt, `dev_train`, batch size 5, a
32,768-token context window, and `LIMIT=10`. Their output filenames contain
`_limit-10`, so the smoke outputs cannot collide with the later full outputs.
Once the jobs leave the queue, verify all three produced 10 validated
predictions in two size-5 batches:

```bash
./scripts/check_v5_smoke.sh
```

After all smoke jobs finish successfully, submit the complete primary matrix:

```bash
DRY_RUN=1 ./scripts/submit_v5_full.sh  # inspect the 15 sbatch commands
./scripts/submit_v5_full.sh
```

This submits 15 independent jobs: three models times English plus the
English-example prompt for German, Hebrew, Spanish, and Tagalog. It runs the
full unmasked `dev_train` split and never accesses `test_lockbox`. Useful
status commands are:

```bash
squeue -u "$USER"
find v5/results/logs -maxdepth 1 -type f -name 'sbatch_v5_*.out' -print
```

To submit only selected models or cells, override `MODELS` or `CELLS`:

```bash
MODELS="qwen3.6:35b-a3b gpt-oss:120b" \
CELLS="english:en german:engex" \
./scripts/submit_v5_full.sh
```

To repair the incomplete July 2026 full runs and run the focused
cross-model prompt experiments, see
[`v5/PROMPT_EXPERIMENT_PLAN.md`](v5/PROMPT_EXPERIMENT_PLAN.md). The short
entry points are:

```bash
DRY_RUN=1 ./scripts/resubmit_v5_failed.sh
DRY_RUN=1 ./scripts/submit_v5_prompt_experiments.sh
```

The completed 2026-07-29 matrix and promotion recommendations are documented
in
[`v5/2026-07-29_full_matrix_results.md`](v5/2026-07-29_full_matrix_results.md)
and
[`v5/2026-07-29_prompt_experiment_results.md`](v5/2026-07-29_prompt_experiment_results.md).

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

The runner defaults to the current version (v5 prompt, `bloom_v5` schema,
prompt version `p005`) and writes directly into `v5/results/` (a
`test_lockbox` run is automatically routed to `v5/results/lockbox/` to keep
the final evaluation physically separate). Prefer
`--batch-size` of 5 or more: multiple negator tokens from the same utterance
then appear in the same request, which the repetition-flag instructions rely
on (v1 used `--batch-size 1`).

### 4. Copy results back to the local machine

Results are gitignored, so copy them with rsync (run from the local machine):

```bash
rsync -av <user>@ssh.ccv.brown.edu:/oscar/data/rfeiman/amcderm6/XLing-LLM_coding/v5/results/ \
  ~/Documents/Research/XLing/Data/XLing-LLM_coding/v5/results/
```

### 5. Score the run

```bash
Rscript scripts/render_irr_report.R v5
Rscript scripts/build_coding_viewer.R
```

The first command finds every `*_predictions.jsonl` under `v5/results/`
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

Then check the run against the falsification criteria in
`v5/CHANGES_FROM_V4.md`. Rows listed in each language's
`splits/*/inspected_rows.txt` are development material, so headline metrics
must be computed on the uninspected remainder; report the inspected rows
separately as a rule-compliance check.

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

### 7. Rerun the failed Llama Tagalog jobs

The dedicated Oscar job reruns only `p003-tl-loc` and `p003-tl-engex` with
`llama3.3:70b`. It uses two L40S GPUs, pins the context window at 16,384
tokens, and sets `BATCH_SIZE=1` so each generated schema permits exactly one
record ID and one prediction:

```bash
sbatch scripts/sbatch_v3_llama_tagalog.sh
```

The singleton batching is a targeted workaround for Llama repeatedly
duplicating IDs in size-5 Tagalog batches. It differs from the size-5 protocol
used for the other v3 runs and should be noted in comparisons. Successful
non-Tagalog Llama outputs are not touched.

The runner refuses to run on `test_lockbox` unless `--allow-lockbox` is passed.
