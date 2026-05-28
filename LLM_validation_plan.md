# LLM Validation Plan (Few-Shot In-Context Coding)

## Goal
Build and validate an LLM pipeline that assigns coding labels on the XLing negation dataset, and compare performance against human-human reliability baselines.

This plan assumes no model fine-tuning at first: prompt + schema + curated examples (few-shot in-context coding).

## Scope (Phase 1)
Start with Bloom coding only.

Target outputs per negator token:
- `bloom_label`
- flags: `foreign_language_negation`, `singing`, `mimicry`, `tag_question`, `repetition`, `not_a_negation`

Reference policy:
- `Data/XLing-LLM_coding/Bloom_coding_policy_v1.md`

## 1. Freeze label policy before modeling
1. Lock allowed labels and definitions.
2. Lock tie-break rules (especially Denial as fallback-only).
3. Lock repetition convention (one row per negator token; analysis excludes repetition rows).
4. Version the policy file and do not change it mid-evaluation.

## 2. Build evaluation splits (by transcript/session)
Do not split by random row. Split by transcript/session to avoid leakage.

Per language:
1. `dev_train`: used for prompt iteration and error analysis.
2. `dev_check_1`: first out-of-slice dev checkpoint.
3. `dev_check_2`: second out-of-slice dev checkpoint.
4. `test_lockbox`: held out and untouched until final evaluation.

Suggested starting split:
- 20% `dev_train`
- 25% `dev_check_1`
- 25% `dev_check_2`
- 30% `test_lockbox`

Requirements:
- Preserve class coverage (Nonexistence, Rejection, Denial, Nonpossession, Uncoded, Excluded).
- Preserve edge-case coverage (mimicry, singing, false positives, repetition).

Progression protocol:
1. Tune prompts only on `dev_train`.
2. When metrics stabilize on `dev_train`, run on `dev_check_1`.
3. If `dev_check_1` shows acceptable generalization, run on `dev_check_2`.
4. If performance drops on a check split, revise prompt/examples and restart at step 1 (without touching `test_lockbox`).
5. Only evaluate on `test_lockbox` after all dev splits are satisfactory and the pipeline is frozen.

Lockbox discipline:
- Default scripts and prompts should operate only on `dev_train`, `dev_check_1`,
  and `dev_check_2`.
- Do not inspect `test_lockbox.jsonl`, `test_lockbox.csv`, or
  `test_lockbox_human_reference.jsonl` for prompt design, examples, error
  analysis, manual spot checks, or debugging.
- LLM runner scripts should reject `test_lockbox` by default and require an
  explicit final-evaluation override such as `--allow-lockbox`.
- Before using the override, write a freeze manifest recording the prompt file,
  schema file, model/version, decoding parameters, preprocessing code, scoring
  code, and output directory.
- Store lockbox outputs separately from dev outputs and do not revise prompt,
  model choice, preprocessing, or scoring after seeing lockbox metrics.

## 3. Establish human baseline first
For the same split/task definition, compute human-human baseline metrics:
1. Exact-match agreement.
2. Cohen's kappa (overall labels).
3. Per-label precision/recall/F1.
4. Binary detection diagnostics (negation vs not-negation), if needed.

Use this baseline as the target band for LLM performance.

Primary evaluation rule:

Treat the LLM as an additional independent coder, not as a classifier being
scored against a single adjudicated gold label. Agreement metrics should be
computed pairwise between the LLM and each human coder on rows where both sides
have comparable non-missing Bloom labels or flags, using the same denominators
and label-collapsing rules as the human-human IRR report. Rows where human
coders disagree are not adjudicated for the primary evaluation.

This means a single gold Bloom label is not required for Phase 1. A gold or
adjudicated label would only be needed for a different claim: that the LLM is
accurate relative to a selected correct answer. The Phase 1 claim is instead
whether the LLM behaves like another coder, and whether LLM-human reliability is
in the same range as human-human reliability.

Evaluation structure:

1. Primary IRR evaluation: add the LLM as another coder in the IRR report and
   compare LLM-human agreement/kappa with human-human agreement/kappa.
2. Agreed-human subset check: on rows where two human coders agree, report LLM
   agreement with that agreed label. Treat this as a consensus subset, not a
   fully adjudicated gold standard.
3. Human-disagreement analysis: on rows where human coders disagree, report
   whether the LLM agrees with coder A, agrees with coder B, agrees with
   neither, or uses `Uncoded`/`Excluded`.
4. Prompt-tuning criterion: tune on dev data to bring LLM-human pairwise
   agreement into the human-human reliability band, rather than optimizing
   against one selected coder as the sole answer key.

Implementation note: implement the LLM-as-coder extension to the IRR report
after the first pass of LLM coding output exists, so the matching logic,
missingness handling, and flag columns can follow the actual output format.

## 4. Prepare model input format
Per negator token record, include:
1. Language
2. Transcript ID
3. Line number
4. Target negator
5. Target utterance
6. Preceding/following context window (fixed size)
7. Any required metadata needed for flags

Output format:
- strict JSON schema with enum constraints
- `schema_version` should match the coding policy version, currently `bloom_v1`
- one prediction object per negator token, keyed by `record_id`
- local validation should reject outputs with missing, duplicate, or unexpected `record_id` values
- reusable schema file: `Data/XLing-LLM_coding/schemas/bloom_v1_output.schema.json`

## 5. Prompt design (few-shot)
Prompt sections:
1. Task instruction (what to predict)
2. Coding policy rules (from Bloom policy)
3. Output schema contract
4. Curated examples (5-15 per language to start)

Guidelines:
- Keep prompt deterministic and concise.
- Keep examples balanced across categories and edge cases.
- Keep decoding deterministic for reproducibility (temperature near 0).

## 6. Iterative validation loop (dev only)
Repeat until stable:
1. Run LLM on `dev_train`.
2. Score LLM-human pairwise agreement using the IRR evaluation rule.
3. Generate confusion matrices and top error buckets.
4. Revise prompt/examples only.
5. Re-run and compare deltas.

Checkpoint cycle:
1. After each major prompt revision, run `dev_check_1`.
2. Promote only if results are stable and close to `dev_train`.
3. Then run `dev_check_2` before considering freeze.

Priority error buckets to monitor:
- Rejection vs Denial
- Nonexistence vs Nonpossession
- Excluded/Uncoded handling
- Repetition/flag handling

## 7. Freeze pipeline
When performance stabilizes across `dev_train`, `dev_check_1`, and `dev_check_2`:
1. Freeze model choice/version.
2. Freeze prompt text.
3. Freeze context window size and preprocessing.
4. Freeze decoding params.
5. Freeze post-processing/scoring code.

No further prompt edits after freeze.

## 8. Final lockbox evaluation
Run exactly once on `test_lockbox` after freeze.

Report:
1. Overall LLM-human exact match and kappa, compared with the human-human baseline.
2. Agreed-human subset performance.
3. Human-disagreement siding analysis.
4. Per-language breakdown.
5. Confusion matrices and gap vs the human-human reliability band.

## 9. Decision criteria for go/no-go
Minimum criteria to proceed beyond Bloom:
1. LLM performance is close to human baseline on core labels.
2. No catastrophic failure on exclusion/flag logic.
3. Error profile is interpretable and auditable.
4. Results are reproducible under rerun.

## 10. Phase 2 extension
After Bloom succeeds:
1. Add Choi labels.
2. Add selected high-value columns from new schema.
3. Re-run split/eval pipeline with the same lockbox discipline.

## Practical Week-1 Checklist
1. Finalize and version Bloom policy file.
2. Create transcript-level split manifests per language.
3. Include `dev_train`, `dev_check_1`, `dev_check_2`, and `test_lockbox` assignments in each manifest.
4. Export token-level evaluation dataset for Bloom fields + flags.
5. Implement IRR scoring script (pairwise exact match, kappa, agreed-human subset, disagreement analysis, confusion matrices).
6. Draft initial prompt and run first `dev_train` pass.
7. Review top 50 errors and revise examples.

## Files to maintain in this folder
- `Data/XLing-LLM_coding/Bloom_coding_policy_v1.md`
- `Data/XLing-LLM_coding/LLM_validation_plan.md`
- `Data/XLing-LLM_coding/splits/` (manifests)
- `Data/XLing-LLM_coding/schemas/` (JSON schemas for LLM output validation)
- `Data/XLing-LLM_coding/prompts/` (versioned prompts)
- `Data/XLing-LLM_coding/results/` (dev + lockbox metrics)
