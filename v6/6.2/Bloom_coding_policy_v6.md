# Bloom Coding Policy for LLM Pilot

Policy version: `bloom_v6`

Supersedes `bloom_v5` (`v5/Bloom_coding_policy_v5.md`). What changed and why
is documented separately in `v6/CHANGES_FROM_V5.md` — kept out of this file so
the policy stays a pure rules document that can be used in prompts without
leaking evaluation details.

## Scope
This document defines how an LLM should assign Bloom-style functional labels
to negator tokens in child-caregiver transcripts. The policy is multilingual (English, German, Hebrew, Spanish, Tagalog): all rules
below are language-general; per-language content is confined to the negator
inventories, the known false-positive readings, and the worked examples in
the per-language prompts.

Current project conventions:
- One coded line per negator token.
- Repetitions are coded with a `repetition` flag when criteria are met.
- In downstream analysis, rows flagged as repetition are excluded.

## Label set
Primary Bloom labels:
- `Nonexistence`
- `Rejection`
- `Denial`
- `Nonpossession`

Status labels:
- `Uncoded`: use only when genuinely too ambiguous to choose a Bloom label.
- `Excluded`: use only when the token should not be analyzed as a meaningful negation act, AND at least one of the licensing flags applies (`singing`, `mimicry`, or `not_a_negation`). Ambiguity alone never licenses `Excluded`; ambiguous-but-real negation is `Uncoded`.

## High-level decision rules
0. **Is the token a negation at all?** The candidate-negator
   search lists over-generate by design. Before assigning a function label,
   decide whether the target token is actually functioning as negation in
   this context. False positives (homographs, discourse particles,
   quantifier readings, echo questions, disfluencies — see the per-language
   false-positive notes in the prompts) are `Excluded` with
   `not_a_negation` = `Yes`. Never force a Bloom label onto a non-negation.
1. Prefer semantic function over surface syntax.
2. Use discourse context before and after the target utterance.
3. Use the participants' responses as interpretation evidence (see below).
4. Choose `Nonpossession` when the key meaning is that someone does not have the referent.
5. Choose `Nonexistence` when an expected referent is absent or unavailable in context. `Nonexistence` is about an **entity** that is absent, gone, or used up — not about actions that fail or properties that do not hold: "it doesn't fit" and "I can't open it" negate propositions and are never `Nonexistence`.
6. Choose `Rejection` when the negation opposes an offer, request, proposal, or a specific actual, imminent, or anticipated action or event — the speaker is refusing it or trying to prevent it.
7. Choose `Denial` when the main function of the negation is to assert that some proposition is false (or to affirm a negative proposition), and `Nonpossession`, `Nonexistence`, and `Rejection` do not apply.
8. Use `Uncoded` if competing interpretations remain unresolved after context review, or if the utterance is too unintelligible to recover the function of a genuine negation. `Uncoded` is a last resort: when the surrounding activity determines the function even though the single turn is fragmentary, commit to the label and express residual doubt through `certain` = `No` instead.
9. Use `Excluded` only for mimicry, singing, or not-a-negation false positives (see Label set above).

### Mandatory label order

After establishing that the indexed target occurrence is a genuine negator,
test labels in this order: `Nonpossession`, `Nonexistence`, `Rejection`,
`Denial`, then `Uncoded`. Dedicated possession/existence labels override
ordinary factual Denial. Denial is the residual content label, not the default
for every declarative-looking negative sentence.

### Target occurrence alignment and contextual reconstruction

Use `negator_index_in_utterance` to identify which occurrence is being coded.
Interpret it using the transcription, CHAT annotations, surrounding
utterance, and discourse context. A production may be incomplete,
phonologically approximate, misspelled, or imperfectly transcribed; use its
best-supported intended meaning rather than requiring a literal surface
reading. Do not transfer the interpretation of another occurrence to the
indexed target, and do not use `not_a_negation` merely because the
transcription is imperfect. Put unresolved interpretive doubt in `certain` =
`No` and `comments`.

### Missing referent is not missing function

`Uncoded` is licensed by an unrecoverable **function**, not merely an unnamed
referent or incomplete prejacent. Constructions such as `none left`, `no
more`, `all gone`, and Tagalog `wala na` identify `Nonexistence` even when the
entity is implicit. A preceding question can supply the missing possession,
existence, offer, or fact under discussion.

### Mechanical flag preflight

Before interpreting propositional content, scan the indexed target line for
singing/song context, imitation markers or an exact contentless adult echo,
and known false-positive readings. Apply `Excluded` with the corresponding
licensing flag before analyzing what the lyric or echoed sentence would mean
as an independent assertion.

### Rejection versus Denial

Classify the negation by what the child is doing with it in the exchange. Use both the child's words and the surrounding context.

- **Rejection:** the child is refusing, resisting, stopping, avoiding, or trying to change something in the situation—an item, activity, action, placement, or who gets to do something.
- **Denial:** the child is correcting a claim, answering a factual question, or describing how things are, without a reasonably supported rejecting function.

**Consider Rejection first.** If Rejection and Denial are both plausible, prefer `Rejection` and set `certain` to `No`. Assign `Denial` only when the factual reading is best supported and a rejecting function is not reasonably supported. An utterance can express a proposition while functioning as a rejection.

#### Identify what the negator targets

A negator may negate material in the same clause or refer back to something in the interaction: a statement, offer, or ongoing or proposed action. Transcripts may omit commas and other punctuation, so punctuation alone cannot establish which interpretation applies.

In "no that's my plate," for example, "that's my plate" may explain an objection rather than state what `no` negates. Determine what the child is opposing before assigning the label.

#### The target may be implicit

Something must be rejected for the function to be Rejection, but that thing need not be explicitly described elsewhere in the transcript. The child's utterance, together with the surrounding context, may provide enough evidence to infer it.

Do not require a transcribed offer, instruction, or action as independent evidence. "I don't want that" can itself support the inference that the child is rejecting something. Uncertainty about exactly what "that" refers to does not necessarily make the rejecting function unclear.

Base the inference on the available evidence. If both a rejecting and a factual interpretation remain plausible, prefer `Rejection` and record the uncertainty.

#### Interpret the surrounding turns

Identify which conversational move the indexed negator responds to. An earlier exchange can remain relevant, but do not automatically carry the interpretation of one `no` over to another after the question, referent, or activity changes.

Following turns can clarify the function:

- Continued bargaining, an alternative proposal, or efforts to coax the child can support Rejection.
- Factual correction or clarification can support Denial.
- An adult may respond to the child's **explanation**, rather than to what the negator targets. After "no that's my plate," "it is?" may address ownership without establishing whether `no` rejected an action.

Weigh these responses with the whole exchange; no single response determines the label.

#### Contrasting examples

**Ownership as an explanation for rejecting an action**

Adult is handling the child's toy.
Child: "No that's mine!"
Adult: "Yes, it's yours. I'm just putting it away."

→ `Rejection`: ownership explains the objection to handling or putting away the toy.

**Ownership as a factual correction**

Adult: "That's Anna's toy."
Child: "No that's mine!"

→ `Denial`: the child corrects an ownership claim, with no evidence that the negation resists an action.

**An implicit rejected item**

During play, the child says "don't want that." The transcript does not identify the item or record an offer.

→ Prefer `Rejection` when the utterance is plausibly directed at something in the current situation. An explicitly recorded offer is not required.

**A report about a preference**

Adult: "What foods don't you like?"
Child: "I don't like carrots."

→ `Denial` when the exchange concerns the child's preferences and there is no reasonably supported refusal of carrots in the situation.

**Changing a placement versus correcting a location**

Adult starts putting a puzzle piece in a slot.
Child: "Not there—here."

→ `Rejection`: the child opposes the placement and proposes another.

Adult: "The spare tire is at the front."
Child: "No, there," pointing to the back.

→ `Denial`: the child corrects where the tire is located, without opposing a placement or other action.

**An inability statement used to resist a request**

Adult: "Climb up."
Child: "I can't."
Adult: "Come on, try."

→ `Rejection`: the inability statement functions as resistance to the requested action.

**A report of inability**

While trying to open a box, the child says "I can't open it" and seeks help.

→ `Denial` when the child is reporting difficulty rather than refusing or resisting the activity.

## Required coding fields (per negator token)
- `bloom_label`: one of `Nonexistence`, `Rejection`, `Denial`, `Nonpossession`, `Uncoded`, `Excluded`
- `comments`: free text (short). The comment must state the contextual reason for the chosen label, **citing the specific context line or quoted fragment that determined it**, and the label must be the one the comment justifies.
- `certain`: `Yes` or `No`. Self-reported confidence in the
  chosen label, mirroring the human coders' `certain_bloom` field. `Yes`
  means no other label is seriously considered; `No` means a second label
  remains plausible. `certain` = `No` never substitutes for choosing the
  single best label, and mere uncertainty is expressed through
  `certain` = `No`, not through `Uncoded`.

Metalinguistic flags:
- `foreign_language_negation`: `Yes` or `No`
- `singing`: `Yes` or `No`
- `mimicry`: `Yes` or `No`
- `tag_question`: `Yes` or `No`
- `repetition`: `Yes` or `No`
- `not_a_negation`: `Yes` or `No`

## Flag policy
- `foreign_language_negation`: Mark `Yes` if the negator is in a language other than the one that the transcript is in-e.g., if you are coding in Spanish, mark Yes if you find a negator in Arabic. Do not exclude- code as normal IF you speak the language
- `singing`: Mark `Yes` if the negator is in the lyrics of a song. Code as excluded if `Yes`
- `mimicry`: Mark `Yes` if the utterance is an exact repetition of something someone said previously, and you judge that the child was simply mimicking, and did not mean to convey additional meaning. Code as excluded if `Yes`. Transcripts often mark imitation explicitly on the child's line (`[+ IMIT]`, `[+ IMI]`, `[=! imitates]`): treat a target line carrying such a marker as mimicry unless context clearly shows the child is doing more than echoing; an exact echo of the immediately preceding adult turn with nothing added is mimicry even without a marker.
- `tag_question`: Mark `Yes` if the negator is a part of a tag question. A tag question is a usually confirmatory question at the end of an utterance: e.g., in "you like pasta, don't you?", "don't you" is a tag question. Mark `Yes` only if the negator is within the tag question. So mark yes for the above example, but do not mark Yes for an utterance such as "You don't like pasta, do you?". Do not exclude- code as normal
- `repetition`: Mark `Yes` if the negator is the same as the previous coded negator token and the prejacent is the same. This applies **within a single utterance** as well as across lines: each negator token gets its own row, so "no no no" is three rows with the second and third flagged `repetition`, and "no xxx no xxx" is two rows with the second flagged `repetition`. It also applies when the child **repeats their own previous line** with the same negator and the same prejacent (transcripts often mark these `[+ SR]`, self-repetition): the repeated line's negator is flagged `repetition` (confirmed by adjudication, 2026-06-11). Do not exclude- code as normal, and give repeated tokens with the same meaning the **same Bloom label** as the first token.
- `not_a_negation`: Mark `Yes` if the word that was flagged as a negation was not intended as a negation in context. Code as excluded if `Yes`. The per-language known false-positive readings (see the prompts) are the most common source of `Yes` here.

## Unintelligible material
Transcripts mark unintelligible speech with `xxx` (and `www` for untranscribed
speech). If the target utterance is largely unintelligible but the negator
itself is plainly a real negation:

- Code the function from whatever context is available, including the
  surrounding **activity**: in an ongoing food negotiation, toy struggle, or
  compliance dispute, a bare or garbled child negation is usually a move in
  that activity (most often `Rejection`), and coders commit to a label,
  reporting `certain` = `No` when doubts remain.
- If the function cannot be determined even from the activity context, use
  `Uncoded` — **never** `Excluded`. `Excluded` asserts the token is not a
  real negation act (song, mimicry, false positive); unintelligibility is
  missing evidence, not a non-negation.

## Output consistency
Decide the label first, then write the output. For every record, identify the
specific context line(s) — quoted fragment or line number — that determined
the label; a label with no citable deciding evidence should be reconsidered. The `comments` field states the reason and cites that evidence;
`bloom_label` must be exactly the label that reasoning concluded. If, while
writing, you find your reasoning supports a different label, re-decide before
emitting anything — the emitted reason and label must agree. When coding a
batch, **restate your final label for every record_id at the end of your
reasoning, immediately before writing the output, and copy those labels
exactly**.

## Output constraints for LLM use
- Return predictions using schema version `bloom_v6`.
- Return one JSON object per negator token, keyed by the input `record_id`.
- Never return multiple Bloom labels for a single token.
- If uncertain, still choose the best Bloom label when possible and report `certain` = `No`; reserve `Uncoded` for truly unresolved cases.
- Use the exact enum strings in this document. Do not add extra labels or flag values.

Recommended batch output shape (note the key order: `comments` precedes
`bloom_label` — state the reason, then the label it justifies — and `certain`
follows the label):

```json
{
  "schema_version": "bloom_v6",
  "predictions": [
    {
      "record_id": "eng_000000",
      "comments": "Child rejects caregiver's request or action in context (cites deciding line).",
      "bloom_label": "Rejection",
      "certain": "Yes",
      "flags": {
        "foreign_language_negation": "No",
        "singing": "No",
        "mimicry": "No",
        "tag_question": "No",
        "repetition": "No",
        "not_a_negation": "No"
      }
    }
  ]
}
```

## Masked-negator variant
A parallel evaluation arm probes how much of the coding signal comes from
context rather than from the negator lexeme itself:

- Input records are pre-filtered: any record where **either human coder**
  marked `not_a_negation` = `Yes`, `repetition` = `Yes`, or
  `foreign_language_negation` = `Yes` is removed before prompting, because
  all three judgments require seeing the token (built by
  `scripts/build_masked_splits.py` into `splits/<language>_masked/`).
- In the remaining records, `target_negator` is replaced by `[MASKED]` and
  every occurrence of that negator in `target_utterance` is replaced by
  `[MASKED]` (all occurrences, so that unmasked copies of the same word
  cannot leak the masked token). Context lines, speaker, and indices are
  unchanged.
- The model codes the Bloom function from the utterance frame and discourse
  context alone, always answering `repetition` = `No`,
  `not_a_negation` = `No`, and `foreign_language_negation` = `No`
  (pre-screened; Step 0 does not apply).
- Masked runs use the same schema (`bloom_v6`) and the masked prompt
  variants (prompt versions `p00611m*`).

## Notes for evaluation setup
- Keep `Excluded` and `Uncoded` available in prediction space.
- Track metrics both with and without repetition rows.
- For model-vs-human comparisons, report confusion particularly among `Rejection`, `Denial`, and `Nonexistence`.
- Cross-line self-repetition rows are flagged per this policy even though older human coding sheets often left them unflagged; interpret human-flag agreement on `repetition` accordingly.
- `certain` enables two new comparisons: calibration (is LLM accuracy higher on `certain` = `Yes` rows?) and human alignment (does LLM certainty track the human coders' `certain_bloom` and split/consensus structure?).
