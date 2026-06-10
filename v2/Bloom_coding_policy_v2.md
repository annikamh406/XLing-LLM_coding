# Bloom Coding Policy for LLM Pilot (English)

Policy version: `bloom_v2`

Supersedes `bloom_v1` (`v1/Bloom_coding_policy_v1.md`). Changes from v1 are
listed in the changelog at the end; every change is motivated by an error
observed in the v1 dev_train limit-20 run.

## Scope
This document defines how an LLM should assign Bloom-style functional labels to English negator tokens in child-caregiver transcripts.

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
1. Prefer semantic function over surface syntax.
2. Use discourse context before and after the target utterance.
3. Choose `Nonpossession` when the key meaning is that someone does not have the referent.
4. Choose `Nonexistence` when expected referent is absent or unavailable in context.
5. Choose `Rejection` when the negation opposes an offer, request, proposal, or a specific actual, imminent, or anticipated action or event — the speaker is refusing it or trying to prevent it.
6. Choose `Denial` when the main function of the negation is to assert that some proposition is false (or to affirm a negative proposition), and `Nonpossession`, `Nonexistence`, and `Rejection` do not apply.
7. Use `Uncoded` if competing interpretations remain unresolved after context review, or if the utterance is too unintelligible to recover the function of a genuine negation.
8. Use `Excluded` only for mimicry, singing, or not-a-negation false positives (see Label set above).

### Rejection vs Denial (tightened in v2)
The v1 rule "if it can be interpreted as Rejection, code Rejection" is kept,
but **Rejection requires that the negation targets a thing, offer, action, or
event** — something whose occurrence or acceptance the speaker is opposing.

If the negation instead responds to a **statement** by contesting or negating
its truth, code `Denial`, even when the statement is about preferences,
desires, or actions. In particular:

- A negation responding to someone else's assertion **about the speaker**
  (e.g., sibling: "she loves peanut butter sandwiches" — child: "no") is
  `Denial`: the child is denying the claim, not refusing a sandwich that was
  offered.
- A negated attitude verb is **not automatically** `Rejection`. "I don't want
  X" refusing an offered or impending X is `Rejection`. But "I don't like it
  too", produced to **agree with** another speaker's evaluative statement
  ("I won't like it"), is `Denial`: it affirms the negative proposition
  [I like it] = false; nothing is being offered or refused.

Tie-break summary: rejecting a thing/action in play => `Rejection`;
disputing or asserting (the falsity of) a proposition => `Denial`. Code as
denial when what matters in context is the content/truth of a statement; code
as rejection when what matters is the speech act of refusing or stopping
something.

### Negative imperatives (new in v2)
Utterances of the form "don't VP" / "you don't VP" need a function decision:

- If the speaker is trying to **stop or prevent a specific action by a
  specific person** (ongoing, imminent, or anticipated), code `Rejection`.
  Examples: "don't wipe it off" while the caregiver is wiping; "don't forget
  it, Didi" to preempt the sister forgetting.
- If the utterance functions as **stating a general rule or norm** — the child
  asserting how one behaves, typically echoing a rule just discussed — code
  `Denial` (the child asserts the proposition that one does/should not do
  that). Contextual cues for the rule-statement reading: the rule was just
  articulated in prior discourse; the subject is generic; the addressee
  responds with **agreement** ("yes", "that's right") rather than by
  complying or stopping.

## Required coding fields (per negator token)
- `bloom_label`: one of `Nonexistence`, `Rejection`, `Denial`, `Nonpossession`, `Uncoded`, `Excluded`
- `comments`: free text (short). The comment must state the contextual reason for the chosen label, and the label must be the one the comment justifies.

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
- `mimicry`: Mark `Yes` if the utterance is an exact repetition of something someone said previously, and you judge that the child was simply mimicking, and did not mean to convey additional meaning. Code as excluded if `Yes`
- `tag_question`: Mark `Yes` if the negator is a part of a tag question. A tag question is a usually confirmatory question at the end of an utterance: e.g., in "you like pasta, don't you?", "don't you" is a tag question. Mark `Yes` only if the negator is within the tag question. So mark yes for the above example, but do not mark Yes for an utterance such as "You don't like pasta, do you?". Do not exclude- code as normal
- `repetition`: Mark `Yes` if the negator is the same as the previous coded negator token and the prejacent is the same. This applies **within a single utterance** as well as across lines: each negator token gets its own row, so "no no no" is three rows with the second and third flagged `repetition`, and "not xxx not xxx" is two rows with the second flagged `repetition`. Do not exclude- code as normal, and give repeated tokens with the same meaning the **same Bloom label** as the first token.
- `not_a_negation`: Mark `Yes` if the word that was flagged as a negation was not intended as a negation in context. Code as excluded if `Yes`

## Unintelligible material (new in v2)
Transcripts mark unintelligible speech with `xxx` (and `www` for untranscribed
speech). If the target utterance is largely unintelligible but the negator
itself is plainly a real negation:

- Code the function from whatever context is available.
- If the function cannot be determined, use `Uncoded` — **never** `Excluded`.
  `Excluded` asserts the token is not a real negation act (song, mimicry,
  false positive); unintelligibility is missing evidence, not a non-negation.

## Output consistency (new in v2)
Decide the label first, then write the output. The `comments` field states the
reason; `bloom_label` must be exactly the label that reasoning concluded. If,
while writing, you find your reasoning supports a different label, re-decide
before emitting anything — the emitted reason and label must agree. (In the v1
run, 5 of 20 outputs contradicted the model's own stated reasoning.)

## Output constraints for LLM use
- Return predictions using schema version `bloom_v2`.
- Return one JSON object per negator token, keyed by the input `record_id`.
- Never return multiple Bloom labels for a single token.
- If uncertain, still choose the best Bloom label when possible; reserve `Uncoded` for truly unresolved cases.
- Use the exact enum strings in this document. Do not add extra labels or flag values.

Recommended batch output shape (note `comments` precedes `bloom_label`: state
the reason, then the label it justifies):

```json
{
  "schema_version": "bloom_v2",
  "predictions": [
    {
      "record_id": "eng_000001",
      "comments": "Child rejects caregiver's request or action in context.",
      "bloom_label": "Rejection",
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

## English examples (one row = one negator token)

Flags shown for every example:
- `F` = `foreign_language_negation`
- `S` = `singing`
- `M` = `mimicry`
- `T` = `tag_question`
- `R` = `repetition`
- `NAN` = `not_a_negation`

| Ex | Context + Utterance (target in **bold**) | Target token | Bloom label | F | S | M | T | R | NAN | Why |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Caregiver opens fridge, expected milk is gone. Child: "**No** milk." | no | Nonexistence | No | No | No | No | No | No | Expected referent (milk) absent in context. |
| 2 | English transcript. Caregiver offers broccoli; child replies "**Nein**!" | nein | Rejection | Yes | No | No | No | No | No | Foreign-language negator used as clear rejection; not excluded if interpretable. |
| 3 | Caregiver offers peas to child. Child: "**No**!" | no | Rejection | No | No | No | No | No | No | Child rejects offered item/action. |
| 4 | Caregiver: "Take a bite." Child: "I do **n't** want peas." | n't | Rejection | No | No | No | No | No | No | Semantically rejecting participation in action. |
| 5 | Caregiver: "This is a tomato" (holding banana). Child: "**No**." | no | Denial | No | No | No | No | No | No | Child denies truth of prior proposition. |
| 6 | Child asks: "You like pasta, do**n't** you?" (negator is in tag only). | n't | Uncoded | No | No | No | Yes | No | No | Tag-question negator is flagged but often ambiguous for Bloom function. |
| 7 | Child checks pockets: "I do **n't** have stickers." | n't | Nonpossession | No | No | No | No | No | No | Main meaning is lack of possession by child. |
| 8 | Child points at sibling: "He has **no** shoes." | no | Nonpossession | No | No | No | No | No | No | Asserts another person lacks possession. |
| 9 | Child says "**No**" after long unclear pause; no clear antecedent. | no | Uncoded | No | No | No | No | No | No | Insufficient context to resolve function confidently. |
| 10 | Caregiver sings "No no no" in song; child repeats: "**No**" in melody. | no | Excluded | No | Yes | No | No | No | Yes | Negator occurs as song lyric. |
| 11 | Caregiver: "Say 'No, I don't want it.'" Child echoes exactly: "**No**, I don't want it." | no | Excluded | No | No | Yes | No | No | No | Direct imitation without clear new communicative act. |
| 12 | Auto-search flagged "know" in "I **know** that" as negation token "no". | no (false hit) | Excluded | No | No | No | No | No | Yes | False positive string match, not actual negation. |
| 13 | Child: "**No** no no" (first token). | no | Rejection | No | No | No | No | No | No | First token establishes meaning; not repetition relative to prior line. |
| 14 | Child: "no **no** no" (second token, same meaning). | no | Rejection | No | No | No | No | Yes | No | Lexically + semantically identical to immediately previous negator line. |
| 15 | Caregiver: "Are you coming?" Child: "**No**, I did**n't** finish." (target `n't`) | n't | Denial | No | No | No | No | No | No | Negates proposition "I finished"; not repetition relative to `No`. |
| 16 | Child searches toy box and says: "There is **no** truck." | no | Nonexistence | No | No | No | No | No | No | Absence of expected object. |
| 17 | Sibling: "She loves peanut butter sandwiches." Child: "**No**." | no | Denial | No | No | No | No | No | No | Denies a claim about the child; no sandwich was offered, so not Rejection. |
| 18 | Caregiver: "That will spill and I won't like it." Child: "I do**n't** like it too." | n't | Denial | No | No | No | No | No | No | Agrees with an evaluative statement by affirming the negative proposition; nothing offered or refused. |
| 19 | Sister is about to leave a toy behind. Child: "Do**n't** forget it, Didi." | n't | Rejection | No | No | No | No | No | No | Negative imperative preventing a specific anticipated action by a specific person. |
| 20 | Caregiver just said "we do not throw food." Child: "Do**n't** do that, Mummy." Caregiver: "Yes, that's right." | n't | Denial | No | No | No | No | No | No | Child restates the rule (one does not do that); addressee confirms with agreement, not compliance. |
| 21 | Child shouts: "**not** xxx not xxx!" — mostly unintelligible, but a real negation. | not | Uncoded | No | No | No | No | No | No | Genuine negation whose function cannot be recovered; ambiguity is Uncoded, never Excluded. |
| 22 | Same utterance "not xxx **not** xxx!" (second token, same apparent meaning). | not | Uncoded | No | No | No | No | Yes | No | Second identical negator in the same utterance: repetition Yes, same label as the first token. |

## Notes for evaluation setup
- Keep `Excluded` and `Uncoded` available in prediction space.
- Track metrics both with and without repetition rows.
- For model-vs-human comparisons, report confusion particularly among `Rejection`, `Denial`, and `Nonexistence`.

## Changelog: v1 -> v2
All changes are motivated by the v1 dev_train limit-20 run
(`v1/results/2026-06-09_llm-human-audit_dev-train_gemma4-31b_limit-20.csv`):

1. **Rejection vs Denial scope tightened.** v1's "prefer Rejection when
   possible" rule caused systematic over-use of Rejection (13/20 LLM vs 10 and
   8 for the human coders). Rejection now requires an opposed thing/offer/
   action/event; negations responding to statements are Denial. Motivating
   rows: eng_000005 ("I don't like it too" — both humans Denial), eng_000068
   ("no" after "she loves peanut butter..." — both humans Denial).
2. **Negative-imperative rule added.** Stop-a-specific-action imperatives are
   Rejection; rule/norm restatements are Denial. Motivating rows: eng_000003
   ("don't forget it, Didi" — both humans Rejection), eng_000012/eng_000013
   ("don't do that, Mummy" / "you don't do that" — both humans Denial, mother
   answers "yes, that's right").
3. **Excluded narrowed; unintelligible = Uncoded.** The v1 model used
   Excluded for an unintelligible-but-real negation (eng_000069) while its own
   comment described the Uncoded criteria. Excluded now requires a licensing
   flag.
4. **Within-utterance repetition made explicit.** The model missed the
   repetition flag on the second `not` of "not xxx not xxx" (eng_000070; both
   humans flagged it) and gave the two tokens of the same utterance different
   labels (Excluded vs Denial). Same-utterance identical negators with the
   same meaning now explicitly get repetition `Yes` and the same label. To
   make this decidable from a single record, the data pipeline now emits
   `negator_index_in_utterance` (1-based token position) and
   `negators_in_utterance` (total tokens) on every record (added 2026-06-10;
   verified to change nothing else in the datasets or splits — v1 inputs are
   frozen byte-exact under `v1/inputs/`).
5. **Output-consistency requirement added; `comments` precedes `bloom_label`
   in the output shape.** In 5 of 20 v1 records the emitted JSON label
   contradicted the conclusion of the model's own chain-of-thought
   (eng_000003, eng_000068, eng_000069, eng_000070, eng_000071); on
   eng_000003 and eng_000068 the reasoning had reached the humans' answer and
   the output flipped away from it. Writing the justification before the label
   ties the label to the stated reason at decoding time.
6. Schema version bumped to `bloom_v2` (same label/flag enums as v1).
