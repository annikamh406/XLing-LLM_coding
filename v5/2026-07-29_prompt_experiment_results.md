# V5 prompt-experiment results

Date: 2026-07-29

## Executive conclusion

Do not replace the shared full v5 prompt with the condensed prompt, and do not
promote Qwen's sampled decoding. Advance two deterministic conditions to
`dev_check_1`:

1. **Pragmatic default:** `qwen3.6:35b-a3b`, full prompt, batch 5,
   temperature 0.
2. **Accuracy-seeking challenger:** `gemma4:31b`, full prompt, batch 1,
   temperature 0.

The Gemma challenger has the highest observed accuracy (85.4%), but it is not
distinguishable from Qwen full/batch-5 on this paired sample (17 Gemma-only
wins, 14 Qwen-only wins; two-sided exact sign test \(p=.720\)) and takes 43.9
instead of 15.9 seconds per record on the one-GPU jobs. Keeping both for the
next untouched split avoids selecting on a small, class-enriched difference.

If GPT-OSS remains in the comparison, use the full prompt, batch 5, and native
high reasoning. That condition reaches 77.6%, a 6.1-point improvement over its
matched default-reasoning baseline (\(p=.040\)), but remains below the selected
Gemma and Qwen conditions on this diagnostic.

## What was evaluated

All 20 planned conditions completed with 246 validated predictions apiece:

- three models: Gemma 4 31B, Qwen 3.6 35B-A3B, and GPT-OSS 120B;
- full versus condensed v5 prompt;
- batch size 1 versus 5;
- deterministic temperature-0 decoding for every model;
- high versus default reasoning for GPT-OSS;
- recommended non-greedy sampling versus temperature 0 for Qwen.

The same 246 English `dev_train` rows were used in every condition. The sample
excludes previously inspected rows, requires human-coder consensus, and
deliberately enriches the difficult Rejection and Denial classes:

| Consensus class | n |
|---|---:|
| Rejection | 80 |
| Denial | 80 |
| Nonexistence | 50 |
| Excluded | 28 |
| Nonpossession | 6 |
| Uncoded | 2 |

Nonpossession is collapsed into Nonexistence for the headline accuracy, as in
the main project analyses. Overall accuracy is therefore a paired prompt
diagnostic, not a population-weighted performance estimate. Uncoded has only
two examples and should not be interpreted separately.

## Best condition by model

| Model | Best observed condition | Overall | Rejection | Denial | Nonexistence | Excluded | sec/row |
|---|---|---:|---:|---:|---:|---:|---:|
| Gemma 4 31B | full, batch 1, default reasoning, temp 0 | **85.4%** | 95.0% | 77.5% | 92.9% | 71.4% | 43.9 |
| Qwen 3.6 35B-A3B | condensed, batch 5, temp 0 | **84.6%** | 95.0% | 86.3% | 82.1% | 60.7% | 15.0 |
| GPT-OSS 120B | full, batch 5, high reasoning, temp 0 | **77.6%** | 81.3% | 80.0% | 91.1% | 39.3% | 6.8 |

Qwen's nominal best is only 0.4 points above its full-prompt/batch-5 baseline
(17 wins, 16 losses, \(p=1.000\)). That does not justify a Qwen-specific
condensed prompt, so the full prompt is the cleaner promotion choice.

## Factor findings

### Prompt length

The condensed prompt has no stable benefit. Relative to the full prompt in the
same model/batch/decoding cell, its change ranges from a 4.1-point loss to a
1.6-point gain, and the direction changes across conditions. In particular:

- Gemma: -0.8 points at batch 1, +1.6 at batch 5;
- Qwen, temperature 0: -0.4 at batch 1, +0.4 at batch 5;
- GPT-OSS, default reasoning: +1.2 at batch 1, +0.8 at batch 5;
- GPT-OSS, high reasoning: +0.8 at batch 1, -0.4 at batch 5.

This fails the criterion for changing the shared prompt.

### Batch size

Batch 1 helps Gemma most: the full-prompt arm gains 4.1 points over batch 5
(18 wins, 8 losses, \(p=.076\)). The gain comes with a 77% runtime increase
(43.9 versus 24.8 seconds per record), so it is a challenger rather than an
automatic default. Batch effects are not portable: they are small or reverse
under Qwen temperature-0 and GPT high-reasoning conditions.

### GPT reasoning effort

High reasoning improves every matched GPT prompt/batch cell by 1.2 to 6.1
points. The largest and cleanest gain is full prompt/batch 5:

| Reasoning | Accuracy | Change from default | Paired wins/losses |
|---|---:|---:|---:|
| Default | 71.5% | — | — |
| High | 77.6% | **+6.1 points** | 31 / 16 (\(p=.040\)) |

High reasoning is therefore supported as a GPT-specific inference setting.

### Qwen sampling

Every sampled Qwen arm is worse than its matched temperature-0 arm:

| Prompt | Batch | Sampling minus temperature 0 |
|---|---:|---:|
| Full | 1 | -1.6 points |
| Full | 5 | -2.0 points |
| Condensed | 1 | -1.6 points |
| Condensed | 5 | -6.5 points |

The proposed sampling control neither improves accuracy nor solves a validation
failure in these completed runs. Keep temperature 0.

## Cautions

- The exact sign tests are paired and two-sided but are not corrected for the
  many experimental comparisons. Treat \(p\)-values as diagnostics, not final
  confirmatory evidence.
- The class-enriched sample intentionally overweights Rejection and Denial.
  The next split is needed before estimating operational accuracy.
- Excluded has only 28 rows and varies markedly by model. It remains a useful
  safety check, not a stable standalone ranking.
- Runtime comparisons are safest within model. Gemma and Qwen both used one
  L40S GPU, while GPT-OSS used two.
- No prompt-test row was opened for qualitative error analysis in producing
  this aggregate report, so the inspected-row list does not need updating.

## Next action

Freeze the selected Qwen and Gemma settings and run them on `dev_check_1`.
Score the split without prompt edits, compare the paired aggregate and
Rejection/Denial results, and retain both through `dev_check_2` if their
difference remains small. Do not inspect individual `dev_check_1` items before
the promotion decision.

The machine-readable results are in
`v5/results/prompt_experiments/summary.csv`; the self-contained
`coding_viewer.html` exposes the same matrix in its **Prompt experiments** tab.
