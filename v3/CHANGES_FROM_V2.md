# Changes from v2 to v3

Date: 2026-06-11.
Scope: everything that differs between the v2 pipeline (policy `bloom_v2`,
prompt `p002`, schema `bloom_v2`) and the v3 pipeline (policy `bloom_v3`,
prompt `p003`, schema `bloom_v3`), with the motivation for each change.

Context: the v2 run (gemma4:31b, `dev_train`, `--limit 20 --batch-size 5`,
run 2026-06-10) was a large success — LLM-vs-EB 77.8% (kappa 0.62), LLM-vs-WP
90.0% (kappa 0.84), LLM-vs-consensus 100% (13/13), all above the 72.2%
human-human baseline. v3 is a refinement pass targeting the remaining
disagreements, which by definition lie on rows where the humans split or only
one human coded. Changes were adjudicated with the project lead on
2026-06-11.

## The v2 error analysis in brief

Two rows were adjudicated as LLM errors, with one shared theme: the model
ignored evidence about how the **participants themselves** interpreted the
negation.

1. **eng_000001** ("no." — v2 LLM: Denial; WP and adjudication: Rejection).
   The mother's "I thought you were gonna save that and put it right here,
   okay?" is a proposal phrased as a statement, and her uptake after the "no"
   — "yeah (.) please (.) for Mom?" — is a plea for compliance: she heard a
   refusal. The v2 model reasoned "it's a denial of the mother's proposition
   ('you were gonna save that')" — the v2 statement-implies-Denial rule
   over-firing on a directive statement. Note v1 coded this row Rejection;
   the v2 rule introduced this regression.
2. **eng_000007** ("I don't like xxx" — v2 LLM: Denial; EB and adjudication:
   Rejection). The child's next turn is "I want xxx": a counter-proposal in
   an ongoing food negotiation, so the dislike statement is the refusing
   move. Two mechanisms: (a) the v2 agreement-with-evaluation example
   (Example I, "I don't like it too") pattern-matched onto a superficially
   similar utterance; (b) this was also v2's one remaining thinking/output
   contradiction — the chain-of-thought concluded Rejection ("this is a
   refusal of the item provided -> Rejection") and the emitted JSON said
   Denial.

One v2 behavior was adjudicated as **correct against the human sheets**: the
LLM flagged `repetition` on cross-line self-repetitions (`[+ SR]` lines:
eng_000004, eng_000010, eng_000013) where the human coders had not. The
policy letter ("same negator as the previous line, same prejacent") supports
the LLM; the human sheets under-flag these.

## 1. Policy: `Bloom_coding_policy_v2.md` -> `Bloom_coding_policy_v3.md`

| Change | Reason |
|---|---|
| New top-level principle: **interlocutor uptake**. How participants respond to the negation shows how they understood it, and that takes priority over surface form. Bidirectional: pleading/re-offering/bargaining uptake => Rejection; re-asserting/correcting/agreeing-about-facts uptake => Denial. The child's own following turns (counter-proposals, continued bargaining) count as uptake too. | Both adjudicated errors. Generalizes the v2 negative-imperative cue (caregiver answering "that's right") into a global rule. Stated bidirectionally so it cannot recreate the v1 Rejection bias. |
| Statement-implies-Denial rule scoped: a statement that **functions as a request or proposal** (stating the child's expected behavior and seeking compliance, often with "okay?") is a request; negating it is `Rejection`, not Denial of a proposition about the child's intentions. | eng_000001 — the v2 rule treated the mother's proposal as an assertion. |
| Attitude-verb guidance sharpened into a three-way contrast: refusing an offer = Rejection; aligning with another speaker's evaluation = Denial; resisting an item in an active exchange (especially with a counter-proposal) = Rejection. | eng_000007 vs the v2 Example-I pattern (eng_000005), which stays Denial. |
| Repetition flag: explicit statement that the rule applies across lines when the child repeats their own previous line with the same negator and prejacent (`[+ SR]`), with the same Bloom label; recorded as adjudicated 2026-06-11. New evaluation note: human sheets under-flag these rows, so interpret human-flag agreement on `repetition` accordingly. | The three v2 flag mismatches, adjudicated in the LLM's favor. The rule was already implied; making it an explicit example prevents regression. |
| Output consistency strengthened: when coding a batch, restate the final label for every record_id at the end of the reasoning, immediately before writing the output, and copy those labels exactly. | eng_000007 was a reasoning/output flip. With multi-record batches the model writes all outputs after long reasoning; forcing a final per-record summary pins the labels at the point of emission. |
| Four worked examples added (23-26): proposal-statement with pleading uptake; dislike + counter-proposal; Denial-side uptake (re-assertion); cross-line `[+ SR]` self-repetition. | One per change, both directions represented. |
| **Changelog removed from the policy file** (new convention). The policy is now a pure rules document; change history lives here instead. | The policy is written as LLM-facing instructions and could plausibly be pasted into a prompt; the v2-style embedded changelog cites dev records together with their human consensus labels, which would leak evaluation answers into any such prompt. (In the current pipeline only the prompt file is sent to the model, so no leak has occurred — this is contamination-proofing and cleanliness.) v2 files are frozen and keep their embedded changelog. |
| Version string `bloom_v2` -> `bloom_v3`. | Versioning discipline per `LLM_validation_plan.md`. |

All other v2 rules, the label set, and the flag set are unchanged.

## 2. Prompt: `bloom_v2_english_prompt.md` (p002) -> `bloom_v3_english_prompt.md` (p003)

| Change | Reason |
|---|---|
| New section "Use the participants as your guide" (uptake principle, bidirectional, including the child's own next turns). | Both adjudicated errors. |
| "Two traps" becomes "three traps": trap 3 is the statement-that-is-a-proposal case, with the "okay?" tag and pleading-uptake cues. | eng_000001. |
| Trap 2 (attitude verbs) extended with the negotiation case and the alignment-vs-resistance contrast. | eng_000007. |
| "Decide First, Then Write" now requires restating the final label for every record_id at the end of reasoning before emitting JSON; output requirement added that `bloom_label` match that restated list. | The eng_000007 reasoning/output flip. |
| Repetition flag rule extended to cross-line self-repetition (`[+ SR]`), keeping the same label. | The adjudicated flag mismatches. |
| New examples N (proposal + pleading uptake => Rejection), O (dislike + counter-proposal => Rejection), P (re-assertion uptake => Denial), Q (cross-line self-repetition => repetition Yes, same label). All v2 examples kept, including Example I. | Few-shot coverage for each change; P keeps the uptake principle balanced toward Denial as well. |
| `schema_version` -> `bloom_v3`. | Versioning. |

## 3. Schema: `bloom_v2_output.schema.json` -> `bloom_v3_output.schema.json`

`schema_version` const bumped to `bloom_v3`; everything else identical.

## 4. Runner defaults

`scripts/run_bloom_coding.py` defaults bumped: prompt `v3/bloom_v3_english_prompt.md`,
schema version `bloom_v3`, prompt version `p003`. Results now go directly into
`v3/results/` — the `dev/` subfolder convention is retired (2026-06-11) so all
version folders share one flat layout; the plan's requirement to keep lockbox
outputs separate is enforced mechanically instead: a `test_lockbox` run is
auto-routed to `v3/results/lockbox/`. v1/v2 runs remain reproducible via
`--prompt/--schema-version/--prompt-version/--results-dir`
(and `--split-dir v1/inputs/splits/english` for exact v1 payloads).

## 5. Contamination control (added 2026-06-11)

Recognized after the v3 draft: the v2/v3 few-shot examples were lifted
near-verbatim from the very rows being evaluated, which made the dev_train
limit-20 metric close to circular. Quantified on v2: of the 13 consensus rows
in the chunk, the 5 that v1 missed (eng_000003/5/12/13/68) became prompt
Examples H-K — and those are exactly the 5 rows v2 newly got right. On
consensus rows NOT present in the prompt, v1 was already 8/8, so the chunk
provided **zero evidence that the rule changes generalize**. The 100%
consensus figure reported for v2 should be read with that caveat.

Mitigations, all applied to v3 before its first run:

1. **All evaluated-item content was paraphrased out of the v3 prompt and
   policy.** Examples H-Q and every rule-text quote are now
   structure-preserving paraphrases (same logic, different content words,
   names, and objects). No utterance from any inspected row appears in the
   prompt, and the output-contract template now uses the placeholder id
   `eng_000000` instead of a real record id (the v1/v2 templates paired
   `eng_000001` with `Rejection` — that row's actual adjudicated label).
   Deriving *rules* from dev_train errors remains sanctioned by the
   validation plan; importing verbatim *items* was the problem.
2. **Provenance is recorded.** Example/rule sources: H <- eng_000068,
   I <- eng_000005, J <- eng_000003, K <- eng_000012/13, L/M <- eng_000069/70,
   N <- eng_000001, O <- eng_000007, Q <- eng_000003/4; imperative rule text
   <- eng_000009-11; trap 3 <- eng_000001.
3. **The entire inspected chunk is excluded from headline metrics.** All 20
   smoke-test rows (eng_000001 - eng_000015, eng_000067 - eng_000071) are
   development data now — we read them, mined them, and adjudicated them.
   Headline dev_train metrics must be computed on the remaining ~1,501
   uninspected rows; report the inspected chunk separately as a
   rule-compliance check. The canonical machine-readable list is
   `splits/english/inspected_rows.txt`; the IRR report reads it and
   stratifies every run into "clean (headline)" vs "inspected (compliance
   check)" automatically, and the audit CSV carries an `inspected` column.

dev_check_1/2 and the lockbox were never at risk of *answer* leakage (splits
are transcript-disjoint), but the same discipline applies going forward: any
row whose content informs a prompt or policy edit joins the exclusion list.

## 6. Expectations and what would falsify these changes

Both adjudicated rows sit **outside the consensus denominator** (eng_000001
has one human label; eng_000007 is a human-split row), so these changes
cannot raise the inspected-chunk consensus figure — the risk runs the other
way. The v3 evaluation run should be the **full dev_train split** (1,521
rows), not limit-20. Check, in order of importance:

1. **Headline criterion — clean-subset agreement**: on the ~1,501 dev_train
   rows outside the inspected chunk, LLM-human pairwise agreement and
   LLM-vs-consensus are within or above the human-human band computed on the
   same rows. This is the first genuine generalization evidence for the
   v2+v3 rule changes.
2. **No regression on the inspected chunk** (now a rule-compliance check, not
   success evidence): all 13 consensus rows still match; eng_000005 and
   eng_000012/13 sit closest to the new rules. eng_000001 and eng_000007
   coded `Rejection` is *indicative* that the rules transfer across the
   paraphrase, nothing more.
3. Zero thinking/output contradictions, and each batch ends its reasoning
   with the restated per-record label list.
4. Repetition flags per policy, including cross-line `[+ SR]`
   self-repetitions (eng_000004/010/013-style rows, adjudicated correct) and
   within-utterance tokens.
5. No `Excluded` without a licensing flag.

If the clean-subset numbers hold in or above the human-human band, this is
the version to take to `dev_check_1` per the progression protocol in
`LLM_validation_plan.md`.
