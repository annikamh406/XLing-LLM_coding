# Changes from v5 to v6

Date: 2026-11-03.

## Scope

Initial v6 development draft. Inherits the v5 policy and five full unmasked
prompts, one per language, all with English examples. Localized-example
variants remain archived in v5 and are not carried forward. The v4 Gemma
comparison favored English examples in all four non-English languages;
subsequent v5 baseline and validation runs used English examples throughout.
See `v4/2026-07-23_gemma_v4_error_analysis.md`.
The initial intervention is named **v6.1**, with prompt IDs `p0061*`; policy and
schema version are `bloom_v6`. Output fields and allowed labels are unchanged.
Rebuild with `python3 v6/make_v6_prompts.py`.

Masked and condensed variants have not been ported. Runtime defaults,
validation freezes, source data and v5 artifacts are unchanged. No v6
inference has been run.

## Identify the target of negation before classifying its function

Adds the user-approved guidance after the literal-content/live-move test:

- Distinguish same-clause (sentential) negation from negation referring back
  to discourse or an action (anaphoric use), without relying on punctuation.
- A following clause can explain a protest rather than supply what is negated.
- Adult uptake can address that explanation rather than the target of `no`.
- Infer unmentioned actions or claims only with adequate contextual evidence;
  record uncertainty when the evidence does not clearly support a reading.

Retains the "no that's my plate" illustration and a contrast between
protesting toy handling and correcting an explicit ownership claim. The
contrast is illustrative, not a quotation from the corpus. No automatic
Rejection rule for ownership statements or bare `no` is introduced.

## Development evidence

Motivated by discussion of v5 Gemma dev_train errors: English `eng_003888`
(plate), `eng_005376` (Noah's Ark), `eng_004782` ("this mine"), Hebrew
`heb_000444` ("this is mine"), and Spanish `spa_000188` (ownership) and
`spa_002529` (dog approaches). These examples were inspected for development;
they are not independent evidence of generalization. The exact physical
action in the plate example remains inferred, not explicitly transcribed.

## Evaluation criteria

Compare against the frozen v5 full dev_train baseline at the same inference
settings. Track corrected Rejection-to-Denial errors, newly introduced
Denial-to-Rejection errors, overall agreement and uncertainty. Do not assume
every historical human-consensus label is correct; retain the v5
policy/reference adjudication principle.

Treat gains on inspected training examples as development fit. Freeze the
candidate before the next authorized held-out generalization check; do not
inspect or run test_lockbox during development.

## Exploratory mismatch review (2026-11-03)

Screened all 230 v5 Gemma dev_train Rejection/Denial mismatch records in both
directions (224 distinct target utterances), with fuller context review for
selected cases. Recorded all screened IDs in each language's
`splits/<language>/inspected_rows.txt`, preserving existing entries. Historical
baseline reports were not regenerated.

The local evidence report is `v6/results/mismatch_review/report.html`, with
source hash, selected cases, inspection audit and proposed experiment arms in
`report.json`. Results folders remain gitignored. Additional hypotheses are:
wrong conversational antecedent, factual identification mistaken for action
choice, clause-type/tense misreading, loss of refusal continuity through
clarification, and hypothetical preference mistaken for refusal. Several
mismatches instead warrant policy/reference adjudication. These are
overlapping exploratory hypotheses, not an exhaustive causal classification
or estimates of failure prevalence.

No additional prompt rules from that review have been implemented. Current
v6 retains only the agreed negation-target addition relative to v5.

## V6.1 diagnostic implementation

The 200-record training diagnostic is frozen in
`dev_train_diagnostic_6_1_freeze.json`; see `DIAGNOSTIC_6_1.md` for selection,
launch and scoring. It contains 40 targeted mismatches, 80 relevant correct
controls and 80 broader correct controls, with original v5 singleton seeds
preserved per record. Five Gemma-only jobs use a separate v6.1 namespace.
Saved v5 predictions are reused; no inference has been launched locally.
