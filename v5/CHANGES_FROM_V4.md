# Changes from v4 to v5

Date: 2026-07-24.

Scope: everything that differs between the v4 pipeline (policy `bloom_v4`,
prompts `p004*`/`p004m*`, schema `bloom_v4`) and the v5 pipeline (policy
`bloom_v5`, prompts `p005*`/`p005m*`, schema `bloom_v5`).

The evidence base is the full, unmasked Gemma v4 `dev_train` run analyzed in
`v4/2026-07-23_gemma_v4_error_analysis.md`. On the pre-analysis clean,
double-coded consensus subset, Gemma coded 2,988 rows with 481 disagreements
(83.9% agreement): English 81.1%, German 82.5%, Hebrew 86.1%, Spanish 84.2%,
and Tagalog 92.9%. The dominant confusion was human Rejection -> model Denial
(167); the reverse direction contributed 64. Other robust patterns were 94
content labels mapped to `Uncoded`, 40 Nonexistence/Nonpossession labels
mapped to Denial, and mechanical boundary errors involving singing, mimicry,
and homographs.

Every record cited in that analysis was added to its language's
`inspected_rows.txt` after the v4 statistics were computed. Those examples
are development material and must not be used to claim an unbiased v5 gain.

## 1. Adjudication principle and deliberately retained rules

Project decision, 2026-07-24: when Gemma's answer follows the written prompt
but conflicts with an older agreed-human label, treat that row as a likely
reference error or policy/reference mismatch. Do not modify the prompt to
reproduce the historical label. Such rows can be adjudicated or reported
separately, but they are not evidence of prompt noncompliance.

Accordingly, v5 does **not** reverse or weaken these v4 rules:

- an inability claim used to resist a just-issued directive can be
  `Rejection`;
- answers to questions are classified by the question's discourse move, so
  an offer, proposal, permission, compliance, plan, want, or timing question
  can receive a refusal answer;
- negative imperatives used to stop an action are `Rejection`;
- explicit imitation and exact, contentless adult echoes license
  `Excluded` + `mimicry`;
- `Excluded` still requires a licensing flag; and
- existence/resultative candidates are interpreted by the written semantic
  and false-positive rules, not by copying inconsistent historical labels.

This decision specifically prevents the v5 prompt from treating the
ability-after-directive, future-plan, timing, negative-imperative, and
cross-language exact-echo examples flagged for adjudication as model errors.

## 2. Prompt and policy changes

The nine unmasked prompts are generated from v4 by
`v5/make_v5_prompts.py`. The changes are shared across languages; the
pre-existing false-positive inventories remain language-specific.

### Mandatory label order

The prompt now tests labels in the explicit order `Nonpossession` ->
`Nonexistence` -> `Rejection` -> `Denial` -> `Uncoded`.

- Possession answers such as `do you have X?` / `no` use the dedicated
  `Nonpossession` label rather than ordinary factual Denial.
- Absence, missing, gone, finished, used-up, `none left`, and `no more`
  meanings use `Nonexistence`, even when the entity is implicit but
  recoverable.
- `Denial` is the residual content label only after the dedicated labels and
  Rejection have been ruled out.

This targets the 40 existence/possession -> Denial errors without changing
the substantive category definitions.

### Literal content versus live discourse move

Before choosing Rejection or Denial, the model must separately state:

1. the literal negative proposition; and
2. what the child is doing with it in the current exchange.

A declarative-looking location, preference, intention, or future statement
is `Rejection` when it is the move used to veto or replace a concrete
placement, object choice, turn, or course of action currently in play.
Activity alone is explicitly insufficient: a specific thing or action must
be opposed. This targets both directions of the Rejection/Denial confusion
without changing the v4 question, directive, ability, or imperative rules.

### `Uncoded` requires an unrecoverable function

The last-resort rule now distinguishes a missing referent or prejacent from a
missing communicative function.

- `none left`, `no more`, `all gone`, and Tagalog `wala na` can establish
  `Nonexistence` without naming the entity;
- an ongoing offer, negotiation, toy struggle, placement dispute, or
  compliance exchange can establish Rejection; and
- a preceding question can supply the omitted offer, possession, existence,
  or factual prejacent.

If one label is best but another remains plausible, the model must choose the
best label and set `certain` = `No`; it must not retreat to `Uncoded`.

### Target occurrence alignment and contextual reconstruction

The unmasked prompts use `negator_index_in_utterance` to identify which
occurrence is being coded, preventing meaning from being transferred from a
nearby negator or identical-looking form. The index is an alignment device,
not an instruction to interpret the transcription literally.

The model is explicitly allowed to reconstruct the best-supported meaning of
an incomplete, phonologically approximate, misspelled, or imperfectly
transcribed production using CHAT annotations, the surrounding utterance, and
discourse context. Imperfect transcription alone does not license
`not_a_negation`; unresolved interpretive doubt belongs in `certain` = `No`
and `comments`.

No separate uncertainty flag was added. The existing per-language
false-positive inventories already cover the substantive lexical decisions,
including Hebrew dative `lo`, prepositional `al`, and `af` meaning “nose.”

### Mechanical exclusion preflight

Before interpreting proposition content, the model must scan for:

1. song or singing context;
2. imitation markers or an exact, contentless adult echo; and
3. a known non-negation reading of the indexed occurrence.

The model is warned not to assign the label that a lyric or echoed sentence
would have received as an independent child assertion.

### Added worked examples

Four structure-preserving teaching examples were added:

- X: `not there - here` while moving a puzzle piece -> `Rejection`;
- Y: negative answer to `do you have crayons?` -> `Nonpossession`;
- Z: unnamed `none left` during a search -> `Nonexistence`; and
- AA: a negator in a line marked `[=! sings]` -> `Excluded` + singing.

The v4 examples and all disputed v4 rules remain in place.

## 3. Schema and runner

The output structure is unchanged. The schema identifier and required
`schema_version` value are bumped from `bloom_v4` to `bloom_v5` so runs
remain traceable.

`scripts/run_bloom_coding.py` now defaults to the English v5 prompt, schema
`bloom_v5`, prompt version `p005`, and `v5/results/`. Older versions remain
reproducible by passing their prompt, version strings, and results directory
explicitly.

The v5 Slurm helpers default to the primary five-cell Gemma evaluation:
English plus the English-example prompt for German, Hebrew, Spanish, and
Tagalog. Those variants had the best clean-consensus v4 result in every
non-English language, although the differences were small and most errors
were shared. The unmasked arm is primary; masked runs are optional.

## 4. Optional masked arm

`v5/make_masked_prompts.py` derives nine `p005m*` prompts. It explicitly
removes visible-lexeme Step 0, false-positive inventories, homograph checks,
and not-a-negation preflight from this pre-screened arm. Singing and mimicry
remain judgeable from visible context.

The masked arm is secondary because masking reduced Gemma accuracy on the
shared clean-consensus rows by 2.0 percentage points in English, 1.8 in
German, 2.4 in Hebrew, 2.8 in Spanish, and 12.9 in Tagalog.

## 5. How to evaluate v5

Judge prompt effects only on rows outside the updated
`splits/*/inspected_rows.txt` lists. Use the full split; a limit-100 run would
mostly sample inspected development rows.

Primary expectations:

1. Rejection -> Denial decreases without a compensating increase in Denial
   -> Rejection.
2. Nonexistence/Nonpossession -> Denial decreases.
3. Content -> `Uncoded` decreases without lower accuracy on newly committed
   rows.
4. Target-token homograph, singing, and mimicry misses decrease.
5. `certain` remains a calibration measure rather than an alternative label.

For prompt-compliance analysis, do not count a policy-following answer as a
prompt failure merely because the historical human reference disagrees.
Track both token-level errors and distinct conversational clusters, because
one interpretation can create several adjacent token errors.
