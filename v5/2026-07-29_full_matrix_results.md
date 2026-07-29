# V5 full-matrix results and completion status

Date: 2026-07-29

## Completion status

The active v5 model/language matrix is complete.

| Run family | Expected | Complete model outputs | Scored audit/IRR |
|---|---:|---:|---:|
| Full `dev_train`: 3 active models × 5 languages | 15 | 15 | 15 |
| Active-model English smoke tests | 3 | 3 | Not included in the viewer |
| Focused prompt experiments | 20 | 20 | Summarized separately |

Every full run has the expected number of predictions, the same number of
unique record IDs, and complete raw-response coverage:

| Language | Expected rows per model |
|---|---:|
| English | 1,521 |
| German | 1,502 |
| Hebrew | 963 |
| Spanish | 1,478 |
| Tagalog | 323 |

The four repaired runs copied back on July 29—Qwen Tagalog and GPT-OSS Hebrew,
Spanish, and Tagalog—had complete model outputs but initially lacked local
audit/IRR artifacts. They have now been scored and added to the viewer.

## LLM agreement with human consensus

Accuracy is computed only where both human coders supplied the same collapsed
Bloom label. Nonpossession is collapsed into Nonexistence, matching the main
IRR reports and viewer. The consensus denominator is identical across models
within each language.

| Language | Consensus n | Gemma 4 31B | Qwen 3.6 35B-A3B | GPT-OSS 120B |
|---|---:|---:|---:|---:|
| English | 838 | 84.8% | **87.1%** | 75.5% |
| German | 701 | **83.2%** | 78.7% | 73.0% |
| Hebrew | 624 | **86.2%** | 81.4% | 65.4% |
| Spanish | 794 | 85.6% | **85.8%** | 71.7% |
| Tagalog | 197 | **88.8%** | **88.8%** | 81.7% |
| **Macro-average across languages** | — | **85.7%** | 84.4% | 73.5% |
| **Pooled consensus rows** | 3,154 | **85.2%** | 83.9% | 72.4% |

Gemma and Qwen remain the viable finalists. Gemma is strongest in German and
Hebrew, Qwen is strongest in English and essentially tied in Spanish, and they
tie in Tagalog. The small aggregate edge for Gemma should not be treated as a
final model-selection test because the five language samples have different
sizes and no across-language paired inferential comparison is reported here.

GPT-OSS trails both finalists in every language. Its strongest full run is
Tagalog (81.7%); Hebrew is weakest (65.4%). This is consistent with the focused
experiment finding that GPT-OSS needs high reasoning, whereas these original
full-matrix runs used default reasoning.

## Class-level observations for the repaired runs

| Model/language | Overall | Rejection | Denial | Nonexistence | Excluded |
|---|---:|---:|---:|---:|---:|
| Qwen Tagalog | 88.8% | 93.0% | 78.7% | 94.5% | 100.0% (n=5) |
| GPT-OSS Hebrew | 65.4% | 64.7% | 65.6% | 81.5% | 36.2% |
| GPT-OSS Spanish | 71.7% | 70.6% | 70.7% | 88.2% | 50.0% |
| GPT-OSS Tagalog | 81.7% | 84.2% | 62.3% | 97.3% | 80.0% (n=5) |

The repaired Qwen Tagalog run is fully competitive with Gemma. GPT-OSS has a
consistent Rejection/Denial weakness, especially Tagalog Denial, even though
its Nonexistence accuracy is relatively high. Excluded percentages for Tagalog
have only five consensus examples and should not drive decisions.

## Certainty behavior

GPT-OSS answers `certain = Yes` on 98–99% of consensus rows in every language,
so its certainty field provides almost no triage value. Gemma says Yes on
91–95% and Qwen on 94–98%; for both finalists, accuracy among Yes responses is
usually modestly higher than overall accuracy, but the No cells remain small.

## Leftover failure artifacts

Old failure files were retained as provenance and do not represent unfinished
active runs:

- Qwen Tagalog has an obsolete July 27 duplicate-ID failure log and
  `failed_batch-14` file. The July 29 batch-size-1 rerun contains all 323 unique
  records and supersedes it.
- GPT-OSS Hebrew, Spanish, and Tagalog each retain an obsolete July 27 timeout
  log and `failed_batch-1` file. Their July 29 outputs are complete.
- Five full-run attempts for retired `qwen3.5:122b` failed with runaway
  generations or a duplicate ID and have only logs/failed-batch files. They are
  not part of the active matrix. Its legacy 10-row smoke test did complete.

No active expected v5 or prompt-experiment run is missing or incomplete.

## Decision

The full multilingual matrix supports the focused-experiment recommendation:

1. advance deterministic Qwen full-prompt/batch-5 as the pragmatic setting;
2. advance Gemma full-prompt/batch-1 as the accuracy-seeking challenger;
3. do not promote GPT-OSS without first validating its high-reasoning setting;
4. evaluate the two finalists on untouched `dev_check_1` before selecting one.

See
[`2026-07-29_prompt_experiment_results.md`](2026-07-29_prompt_experiment_results.md)
for the 20-condition prompt, batch, reasoning, and decoding analysis.
