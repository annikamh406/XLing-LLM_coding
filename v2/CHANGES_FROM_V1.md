# Changes from v1 to v2

Date: 2026-06-10.
Scope: everything that differs between the v1 pipeline (policy `bloom_v1`,
prompt `p001`, schema `bloom_v1`) and the v2 pipeline (policy `bloom_v2`,
prompt `p002`, schema `bloom_v2`), with the motivation for each change.

All changes are driven by an error analysis of the single v1 run:
gemma4:31b, `dev_train`, `--limit 20 --batch-size 1`, run 2026-05-28.
Artifacts: `v1/results/` (predictions, raw responses with chain-of-thought,
IRR report, item-level audit CSV, interactive coding viewer). v1 headline
numbers: LLM-vs-human agreement 61.1% (Coder EB) and 50.0% (Coder WP) against
a human-human baseline of 72.2%; on the 13 rows where both humans agreed, the
LLM matched 8 (61.5%).

## The v1 error analysis in brief

Of the 20 coded rows, the LLM disagreed with an agreed human label on 5 rows,
used a wrong status label on 1, and missed a repetition flag on 1. Four error
mechanisms accounted for everything:

1. **Thinking/output contradiction (5/20 rows).** The model's chain-of-thought
   concluded one label and the emitted JSON contained a different one
   (eng_000003, eng_000068, eng_000069, eng_000070, eng_000071). On
   eng_000003 and eng_000068 the reasoning had reached exactly the label both
   humans chose, and the output flipped away from it. This alone cost 2 of
   the 5 consensus misses.
2. **Rejection over-use.** The LLM coded Rejection 13/20 times vs the humans'
   10 and 8. v1's unscoped tie-break ("if it can be interpreted as Rejection,
   use Rejection") pulled statement-directed negations into Rejection
   (eng_000005, eng_000068 — both humans: Denial).
3. **Negative imperatives mishandled.** "don't do that, Mummy" / "you don't
   do that" (eng_000012/13) were coded Rejection, but both humans read them
   as the child restating a just-stated rule (Denial; the mother answers
   "yes, that's right"). Conversely "don't forget it, Didi" (eng_000003) is
   prevention of a specific action and the humans coded Rejection.
4. **Status labels and repetition.** For the mostly-unintelligible
   "not xxx not xxx" the model output Excluded (eng_000069) even though its
   own comment described the Uncoded criteria; it missed the repetition flag
   both humans put on the second `not` (eng_000070); and it gave the two
   tokens of that one utterance different labels (Excluded vs Denial). With
   `--batch-size 1` the model could not have known eng_000070 was the second
   token: nothing in a v1 record identified token position.

## 1. Policy: `Bloom_coding_policy_v1.md` -> `Bloom_coding_policy_v2.md`

| Change | Reason |
|---|---|
| Rejection definition tightened: must oppose a thing, offer, action, or event in play (refusing or preventing it). The Rejection-over-Denial tie-break still exists but only applies when that holds. | Error mechanism 2. v1's tie-break made Rejection the default whenever an action was loosely involved. |
| New rule: a negation responding to a **statement** is Denial, even when the statement concerns preferences/desires — including assertions about the child ("she loves peanut butter sandwiches" -> "no") and agreement with another speaker's evaluative statement ("I won't like it" -> "I don't like it too"). | eng_000068 and eng_000005: both humans coded Denial, LLM coded Rejection. |
| New negative-imperative rule: stopping/preventing a specific action by a specific person = Rejection; restating a general rule or norm = Denial. Cue given: addressee responds with agreement ("that's right") rather than compliance. | Error mechanism 3 (eng_000003 vs eng_000012/13 — the v1 model got these exactly swapped). |
| Excluded narrowed: only valid together with a licensing flag (`singing`, `mimicry`, `not_a_negation`). Unintelligible-but-real negation is Uncoded, never Excluded. | eng_000069: model used Excluded for an unintelligible negation while its comment described Uncoded. |
| Repetition flag made explicitly within-utterance: each negator token is one row, so "no no no" and "not xxx not xxx" carry the flag on tokens 2+; repeated tokens with the same meaning get the **same** Bloom label as the first token. | eng_000070 (missed flag) and the Excluded/Denial label split across the two tokens of one utterance. |
| New output-consistency requirement: decide the label first; `comments` states the reason and `bloom_label` must be the label that reason justifies. | Error mechanism 1. |
| Six worked examples added (17-22), all lifted from the v1 error rows: assertion-about-child denial, agreement-with-evaluation denial, prevent-action imperative, rule-statement imperative, unintelligible -> Uncoded, within-utterance repetition pair. | Few-shot coverage for every observed error bucket. |
| Version string `bloom_v1` -> `bloom_v2`; changelog section added at the end of the policy file. | Versioning discipline per `LLM_validation_plan.md` (policy frozen per evaluation round). |

Label set, flag set, and all other v1 rules are unchanged.

## 2. Prompt: `bloom_v1_english_initial_prompt.md` (p001) -> `bloom_v2_english_prompt.md` (p002)

| Change | Reason |
|---|---|
| All policy rule changes above mirrored into the prompt (Rejection-vs-Denial decision guide with the two named traps, negative-imperative section, Uncoded-vs-Excluded section). | Keep prompt and policy in lockstep, as v1 did. |
| **`comments` now precedes `bloom_label` in the output JSON**, and a "Decide First, Then Write" section requires the label to match the stated reason. | Error mechanism 1. Because generation is sequential, emitting the justification first conditions the label on the just-written reason, closing the gap where the model reasons to X and emits Y. This is the main structural fix. |
| New examples H-M (denial of assertion about the child; agreement-denial; prevent-action imperative; rule-statement imperative; unintelligible -> Uncoded; within-utterance repetition with token indices shown). | One few-shot example per observed error bucket, phrased from the actual error rows. |
| Batch Input section documents `negator_index_in_utterance` / `negators_in_utterance` and ties the repetition rule to them. | See section 4; eng_000070 was unanswerable from a v1 record. |
| Repetition rule restated in terms of the index fields, with "No, I didn't" kept as the negative example (2 tokens, different prejacents, no flag). | Same. |

## 3. Schema: `bloom_v1_output.schema.json` -> `bloom_v2_output.schema.json`

| Change | Reason |
|---|---|
| `schema_version` const `bloom_v1` -> `bloom_v2`. | Must match the policy version. |
| Property/`required` order in `predictions` items changed to `record_id`, `comments`, `bloom_label`, `flags`. | Documents the comments-first output shape. JSON Schema treats objects as unordered, so this is descriptive; the enforced contract (keys, enums, lengths) is unchanged. |

No labels, flags, or constraints changed.

## 4. Data pipeline: token-position fields (affects `datasets/` and `splits/english/`)

New fields on every record, emitted by `scripts/build_english_llm_dataset.py`
and passed through by `scripts/create_english_llm_splits.py`:

- `negator_index_in_utterance`: 1-based position of this record among the
  utterance's negator tokens (workbook row order, which is occurrence order —
  the same order the human coders saw).
- `negators_in_utterance`: total negator tokens in the utterance.

Reason: one coded row = one negator token, so an utterance with several
tokens yields several records that were otherwise **indistinguishable** (same
transcript, line, utterance, even the same `target_negator` string). With
`--batch-size 1` in v1, the model literally could not know that eng_000070
was the second `not` of "not xxx not xxx", so the repetition flag was
undecidable. 1,364 of the 9,628 dataset rows (14%) are in multi-negator
utterances, so this is not a corner case.

Reproducibility verification (all checks 2026-06-10):

1. Before any change, both pipeline scripts were rerun unmodified and
   reproduced the existing datasets and all 18 split files **byte-for-byte**
   (Python 3.12; the seeded 20,000-iteration split search is deterministic).
2. After the change, every regenerated JSONL/CSV was compared field-by-field
   against the frozen copies: identical record ids, identical split
   membership (same split score), all v1 fields unchanged; the only
   difference is the two added keys. Human-reference files are bit-identical.
   `test_lockbox` membership is untouched.
3. The exact pre-change bytes are frozen in `v1/inputs/` (gitignored except
   its README; the same state is also in Git history, where the split JSONLs
   are tracked).

## 5. Runner: `scripts/run_bloom_coding.py`

| Change | Reason |
|---|---|
| `SCHEMA_VERSION`/`PROMPT_VERSION` constants replaced by `--schema-version` (default `bloom_v2`) and `--prompt-version` (default `p002`) CLI options; defaults for `--prompt` and `--results-dir` now point at `v2/`. | One runner serves all versions; defaults track the current version; old versions remain runnable via flags. |
| `negator_index_in_utterance` / `negators_in_utterance` added to `PROMPT_RECORD_FIELDS`. | The model must receive the new fields (they are not evaluation data). |
| `prompt_record()` now omits fields absent from a record instead of sending nulls. | Running against the frozen v1 splits in `v1/inputs/` produces byte-identical prompt payloads to the original v1 run (unit-checked); new splits include the new fields automatically. |
| Validation logic is key-order-agnostic (unchanged), so it accepts the comments-first output shape with no code change. | Noted for completeness. |

Recommended invocation change: v1 used `--batch-size 1`; for v2 prefer
`--batch-size 5` or more so consecutive tokens of the same utterance share a
request and the model can also see its neighboring decisions.

## 6. Folder layout (organizational, no content changes)

Also done 2026-06-10, alongside the v2 work: each version's policy, prompt,
schema, and results now live together under `v1/` and `v2/`;
version-independent infrastructure (`scripts/`, `splits/`, `datasets/`,
`LLM_validation_plan.md`) stays at the top level. The split diagnostics SVG
moved to `splits/english/diagnostics/` (it describes the splits, not a model
run), and `scripts/create_english_llm_splits.py` writes it there now. v1
files were moved with `git mv`; nothing was deleted. The full v1 run inputs
are frozen under `v1/inputs/` (see its README for the exact v1 reproduction
command).

## What would falsify these changes

When scoring the v2 run, check the v1 error buckets directly:

1. Zero (or near-zero) rows where the emitted label contradicts the comment.
2. LLM Rejection rate near the human rate (~40-50% on dev_train-like data),
   not ~65%.
3. eng_000003/5/12/13/68-style items (imperatives, statement-responses)
   agreeing with the human consensus.
4. No Excluded without a licensing flag; unintelligible rows coded Uncoded.
5. Repetition flags present on token 2+ of multi-negator utterances, with
   labels consistent across the utterance.

If LLM-human agreement does not move toward the 72.2% human-human baseline on
`dev_train`, revisit the Rejection/Denial wording before touching
`dev_check_1` (per the progression protocol in `LLM_validation_plan.md`).
