# Bloom Coding Policy for LLM Pilot (English)

Policy version: `bloom_v1`

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
- `Excluded`: use when the token should not be analyzed as a meaningful negation act (for example, mimicry, singing, false positive).

## High-level decision rules
1. Prefer semantic function over surface syntax.
2. Use discourse context before and after the target utterance.
3. Choose `Nonpossession` when the key meaning is that someone does not have the referent.
4. Choose `Nonexistence` when expected referent is absent or unavailable in context.
5. Choose `Rejection` when the negation is used to oppose/reject an object or action in context.
6. Choose `Denial` only when `Nonpossession`, `Nonexistence`, and `Rejection` do not apply, and you judge that the meaning of the negation is to deny the truth of some proposition.
7. Use `Uncoded` only if competing interpretations remain unresolved after context review.
8. Use `Excluded` for mimicry, singing, or not-a-negation flags.

Priority rule for ambiguous cases:
- If an utterance can be interpreted as `Rejection`, code `Rejection` (not `Denial`).
- Example: `I don't want broccoli` should be coded as `Rejection`.
- Code as denial when the thing that's important in the context is the content/truth of the statement, code as rejection when the thing that's important in the context is the speech act of rejecting

## Required coding fields (per negator token)
- `bloom_label`: one of `Nonexistence`, `Rejection`, `Denial`, `Nonpossession`, `Uncoded`, `Excluded`
- `comments`: free text (short)

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
- `repetition`: Mark `Yes` if the negator is the same as the previous line, and the prejacent is the same. So if a child says "no no no", that would be three lines, but the second and third line would be tagged as repetition. Do not exclude- code as normal
- `not_a_negation`: Mark `Yes` if the word that was flagged as a negation was not intended as a negation in context. Code as excluded if `Yes`

## Output constraints for LLM use
- Return predictions using schema version `bloom_v1`.
- Return one JSON object per negator token, keyed by the input `record_id`.
- Never return multiple Bloom labels for a single token.
- If uncertain, still choose the best Bloom label when possible; reserve `Uncoded` for truly unresolved cases.
- Use the exact enum strings in this document. Do not add extra labels or flag values.

Recommended batch output shape:

```json
{
  "schema_version": "bloom_v1",
  "predictions": [
    {
      "record_id": "eng_000001",
      "bloom_label": "Rejection",
      "flags": {
        "foreign_language_negation": "No",
        "singing": "No",
        "mimicry": "No",
        "tag_question": "No",
        "repetition": "No",
        "not_a_negation": "No"
      },
      "comments": "Child rejects caregiver's request or action in context."
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

## Notes for evaluation setup
- Keep `Excluded` and `Uncoded` available in prediction space.
- Track metrics both with and without repetition rows.
- For model-vs-human comparisons, report confusion particularly among `Rejection`, `Denial`, and `Nonexistence`.
