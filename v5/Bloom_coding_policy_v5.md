# Bloom Coding Policy for LLM Pilot

Policy version: `bloom_v5`

Supersedes `bloom_v4` (`v4/Bloom_coding_policy_v4.md`). What changed and why
is documented separately in `v5/CHANGES_FROM_V4.md` — kept out of this file so
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

### Literal content versus live discourse move

State both (a) the literal negative proposition and (b) what the child is
doing with it in the current exchange. A location, preference, intention, or
other declarative-looking form is `Rejection` when it is the child's move for
vetoing or replacing a concrete placement, object choice, turn, or course of
action currently in play. Activity alone is insufficient: the context must
show a specific thing/action being opposed. If only truth is at issue, use
`Denial` unless a dedicated possession/existence label applies.

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

### Interlocutor uptake
The people in the conversation saw and heard what we cannot; how they respond
to the negation shows how they understood it in the moment. When uptake cues
are present, they take priority over surface form. This evidence cuts both
ways:

- If the addressee responds by **pleading, re-offering, bargaining, coaxing,
  or insisting** ("oh please? just this once?", "come on, try a little"), they understood
  the negation as a refusal => `Rejection`.
- If the addressee responds by **re-asserting, correcting, conceding, or
  agreeing about facts** ("yes she does!", "that's right", "oh, you're
  right"), they understood it as a claim about truth => `Denial`.
- The child's **own following turns count as uptake evidence too**: a
  counter-proposal ("I want X") or continued bargaining shows the negation was
  a move in a negotiation => `Rejection`.

Uptake is strong evidence, not absolute proof — caregivers sometimes redirect
regardless of what the child meant. Weigh it together with the rest of the
context.

### Rejection vs Denial
The "prefer Rejection when it reasonably applies" tie-break is kept, but
**Rejection requires that the negation targets a thing, offer, action, or
event** — something whose occurrence or acceptance the speaker is opposing.

If the negation instead responds to a **statement** by contesting or negating
its truth, code `Denial`, even when the statement is about preferences,
desires, or actions. In particular:

- A negation responding to someone else's assertion **about the speaker**
  (e.g., sibling: "he likes carrots" — child: "no") is `Denial`: the child is
  denying the claim, not refusing a carrot that was offered.
- A negated attitude verb is **not automatically** `Rejection` — but it is
  also not automatically `Denial`. "I don't want X" refusing an offered or
  impending X is `Rejection`. "I don't like it either", produced to **agree
  with** another speaker's evaluative statement ("this room is too dark, I
  don't like it"), is `Denial`: it affirms the negative proposition
  [I like it] = false. But
  "I don't like it" said while resisting an item in an active exchange —
  especially when the child follows up with a counter-proposal ("I want X") —
  is `Rejection`: the dislike statement is the move by which the child
  refuses. Alignment with an evaluation => `Denial`; resistance within a
  negotiation => `Rejection`.
- A statement that **functions as a request or proposal** is a request, not
  an assertion. Caregivers often propose actions by stating the
  child's expected behavior and seeking compliance, frequently with a
  confirmation tag: "I thought you were going to put your shoes by the door,
  okay?". Negating such an utterance refuses the proposed action =>
  `Rejection`, not Denial of a proposition about the child's intentions.
  Uptake usually disambiguates: a caregiver who answers the "no" by pleading
  or re-asking heard a refusal.
- **Answers to questions: classify the question's move, not its syntax**. A question that offers, proposes, requests, or seeks
  permission or compliance ("would you like lunch?", "should I give this to
  Grandma?", "can you put it on by yourself?") is a proposal: a negative
  answer refuses => `Rejection`. A question that seeks information about a
  fact ("is it hot?", "did you have story time today?") is an assertion
  probe: a negative answer asserts the proposition is false => `Denial`.
  Every refusal can be paraphrased as "denying the proposition inside the
  question" — that paraphrase does not make it a Denial. Equally, a bare
  "no" is not automatically a refusal — check what the question was doing.
- **Negated ability, fit, or success is a claim about the world**. "I can't open it", "it doesn't fit", "it doesn't work" assert that a
  proposition about ability or fit is false => `Denial` by default, and
  never `Nonexistence` (nothing is absent). Code `Rejection` only when such
  a statement is the child's move to resist a directive just issued to them
  (caregiver: "climb up" — child: "I can't", with uptake showing a
  compliance struggle rather than a factual exchange).
- **Normative statements**: "one shouldn't eat those!" deployed
  to stop an ongoing activity is a prohibiting move => `Rejection`; the same
  sentence as a detached rule statement, met with agreement, is `Denial`
  (parallel to the negative-imperative rule below).

Tie-break summary: rejecting a thing/action in play => `Rejection`;
disputing or asserting (the falsity of) a proposition => `Denial`. Code as
denial when what matters in context is the content/truth of a statement; code
as rejection when what matters is the speech act of refusing or stopping
something.

### Negative imperatives
Utterances of the form "don't VP" / "you don't VP" need a function decision:

- If the speaker is trying to **stop or prevent a specific action by a
  specific person** (ongoing, imminent, or anticipated), code `Rejection`.
  Examples: "don't close it" while the caregiver is closing the box; "don't
  spill it, Anna" as the sister picks up a too-full cup.
- If the utterance functions as **stating a general rule or norm** — the child
  asserting how one behaves, typically echoing a rule just discussed — code
  `Denial` (the child asserts the proposition that one does/should not do
  that). Contextual cues for the rule-statement reading: the rule was just
  articulated in prior discourse; the subject is generic; the addressee
  responds with **agreement** ("yes", "that's right") rather than by
  complying or stopping.

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
- Return predictions using schema version `bloom_v5`.
- Return one JSON object per negator token, keyed by the input `record_id`.
- Never return multiple Bloom labels for a single token.
- If uncertain, still choose the best Bloom label when possible and report `certain` = `No`; reserve `Uncoded` for truly unresolved cases.
- Use the exact enum strings in this document. Do not add extra labels or flag values.

Recommended batch output shape (note the key order: `comments` precedes
`bloom_label` — state the reason, then the label it justifies — and `certain`
follows the label):

```json
{
  "schema_version": "bloom_v5",
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
- Masked runs use the same schema (`bloom_v5`) and the masked prompt
  variants (prompt versions `p005m*`).

## Notes for evaluation setup
- Keep `Excluded` and `Uncoded` available in prediction space.
- Track metrics both with and without repetition rows.
- For model-vs-human comparisons, report confusion particularly among `Rejection`, `Denial`, and `Nonexistence`.
- Cross-line self-repetition rows are flagged per this policy even though older human coding sheets often left them unflagged; interpret human-flag agreement on `repetition` accordingly.
- `certain` enables two new comparisons: calibration (is LLM accuracy higher on `certain` = `Yes` rows?) and human alignment (does LLM certainty track the human coders' `certain_bloom` and split/consensus structure?).
