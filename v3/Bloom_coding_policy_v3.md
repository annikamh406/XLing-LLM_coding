# Bloom Coding Policy for LLM Pilot (English)

Policy version: `bloom_v3`

Supersedes `bloom_v2` (`v2/Bloom_coding_policy_v2.md`). What changed and why
is documented separately in `v3/CHANGES_FROM_V2.md` — kept out of this file so
the policy stays a pure rules document that can be used in prompts without
leaking evaluation details.

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
3. Use the participants' responses as interpretation evidence (see below).
4. Choose `Nonpossession` when the key meaning is that someone does not have the referent.
5. Choose `Nonexistence` when expected referent is absent or unavailable in context.
6. Choose `Rejection` when the negation opposes an offer, request, proposal, or a specific actual, imminent, or anticipated action or event — the speaker is refusing it or trying to prevent it.
7. Choose `Denial` when the main function of the negation is to assert that some proposition is false (or to affirm a negative proposition), and `Nonpossession`, `Nonexistence`, and `Rejection` do not apply.
8. Use `Uncoded` if competing interpretations remain unresolved after context review, or if the utterance is too unintelligible to recover the function of a genuine negation.
9. Use `Excluded` only for mimicry, singing, or not-a-negation false positives (see Label set above).

### Interlocutor uptake (new in v3)
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
  an assertion (new in v3). Caregivers often propose actions by stating the
  child's expected behavior and seeking compliance, frequently with a
  confirmation tag: "I thought you were going to put your shoes by the door,
  okay?". Negating such an utterance refuses the proposed action =>
  `Rejection`, not Denial of a proposition about the child's intentions.
  Uptake usually disambiguates: a caregiver who answers the "no" by pleading
  or re-asking heard a refusal.

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
- `repetition`: Mark `Yes` if the negator is the same as the previous coded negator token and the prejacent is the same. This applies **within a single utterance** as well as across lines: each negator token gets its own row, so "no no no" is three rows with the second and third flagged `repetition`, and "no xxx no xxx" is two rows with the second flagged `repetition`. It also applies when the child **repeats their own previous line** with the same negator and the same prejacent (transcripts often mark these `[+ SR]`, self-repetition): the repeated line's negator is flagged `repetition` (confirmed by adjudication, 2026-06-11). Do not exclude- code as normal, and give repeated tokens with the same meaning the **same Bloom label** as the first token.
- `not_a_negation`: Mark `Yes` if the word that was flagged as a negation was not intended as a negation in context. Code as excluded if `Yes`

## Unintelligible material
Transcripts mark unintelligible speech with `xxx` (and `www` for untranscribed
speech). If the target utterance is largely unintelligible but the negator
itself is plainly a real negation:

- Code the function from whatever context is available.
- If the function cannot be determined, use `Uncoded` — **never** `Excluded`.
  `Excluded` asserts the token is not a real negation act (song, mimicry,
  false positive); unintelligibility is missing evidence, not a non-negation.

## Output consistency
Decide the label first, then write the output. The `comments` field states the
reason; `bloom_label` must be exactly the label that reasoning concluded. If,
while writing, you find your reasoning supports a different label, re-decide
before emitting anything — the emitted reason and label must agree. When
coding a batch, **restate your final label for every record_id at the end of
your reasoning, immediately before writing the output, and copy those labels
exactly** (new in v3).

## Output constraints for LLM use
- Return predictions using schema version `bloom_v3`.
- Return one JSON object per negator token, keyed by the input `record_id`.
- Never return multiple Bloom labels for a single token.
- If uncertain, still choose the best Bloom label when possible; reserve `Uncoded` for truly unresolved cases.
- Use the exact enum strings in this document. Do not add extra labels or flag values.

Recommended batch output shape (note `comments` precedes `bloom_label`: state
the reason, then the label it justifies):

```json
{
  "schema_version": "bloom_v3",
  "predictions": [
    {
      "record_id": "eng_000000",
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
| 17 | Sibling: "He likes carrots." Child: "**No**." | no | Denial | No | No | No | No | No | No | Denies a claim about the child; no carrot was offered, so not Rejection. |
| 18 | Caregiver: "This room is too dark, I don't like it." Child: "I do**n't** like it either." | n't | Denial | No | No | No | No | No | No | Agrees with an evaluative statement by affirming the negative proposition; nothing offered or refused. |
| 19 | Sister picks up a very full cup. Child: "Do**n't** spill it, Anna." | n't | Rejection | No | No | No | No | No | No | Negative imperative preventing a specific anticipated action by a specific person. |
| 20 | Caregiver just said "we do not jump on the sofa." Child: "Do**n't** jump on it, Daddy." Caregiver: "Yes, that's right." | n't | Denial | No | No | No | No | No | No | Child restates the rule (one does not do that); addressee confirms with agreement, not compliance. |
| 21 | Child shouts: "**no** xxx no xxx!" — mostly unintelligible, but a real negation. | no | Uncoded | No | No | No | No | No | No | Genuine negation whose function cannot be recovered; ambiguity is Uncoded, never Excluded. |
| 22 | Same utterance "no xxx **no** xxx!" (second token, same apparent meaning). | no | Uncoded | No | No | No | No | Yes | No | Second identical negator in the same utterance: repetition Yes, same label as the first token. |
| 23 | Caregiver: "I thought you were going to put your shoes by the door, okay?" Child: "**No**." Caregiver: "Please? Before we go?" | no | Rejection | No | No | No | No | No | No | The statement functions as a proposal, and the pleading uptake shows the caregiver heard a refusal — not a denial of a claim about the child's plans. |
| 24 | Caregiver hands the child the green cup. Child: "I do**n't** like this cup." Child next turn: "I want the red cup." | n't | Rejection | No | No | No | No | No | No | Resisting an item in an active exchange, confirmed by the counter-proposal; contrast with Ex 18, where the child aligns with another speaker's evaluation. |
| 25 | Child: "**No**" after sibling says "it's raining outside." Caregiver: "It IS raining, look!" | no | Denial | No | No | No | No | No | No | The re-asserting uptake shows the family heard a truth dispute, not a refusal. |
| 26 | Child said "don't spill it, Anna" (coded Rejection). Two lines later the child repeats: "do**n't** spill it." (`[+ SR]`) | n't | Rejection | No | No | No | No | Yes | No | Self-repetition of the previous negator line with the same prejacent: repetition Yes, same label as the original. |

## Notes for evaluation setup
- Keep `Excluded` and `Uncoded` available in prediction space.
- Track metrics both with and without repetition rows.
- For model-vs-human comparisons, report confusion particularly among `Rejection`, `Denial`, and `Nonexistence`.
- Cross-line self-repetition rows (Ex 26) are flagged per this policy even though older human coding sheets often left them unflagged; interpret human-flag agreement on `repetition` accordingly.
