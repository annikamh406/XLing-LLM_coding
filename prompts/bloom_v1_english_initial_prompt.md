# Bloom v1 English Negation Coding Prompt

Use this prompt for Phase 1 English Bloom coding on development splits.

Do not run this prompt on `test_lockbox` until the pipeline, prompt text,
model choice, decoding parameters, validation code, and scoring code are frozen.

## System / Task Instruction

You are coding English child-caregiver transcript negation tokens for the XLing
negation project.

Each input record corresponds to exactly one target negator token. For each
record, assign one Bloom-style label and six metalinguistic flags. Use the
target utterance plus the surrounding context before and after the utterance.
Do not use human coder labels, split metadata, or evaluation results.

Return only valid JSON matching schema version `bloom_v1`. Do not include
Markdown, prose outside JSON, or extra keys.

## Allowed Output Labels

`bloom_label` must be exactly one of:

- `Nonexistence`
- `Rejection`
- `Denial`
- `Nonpossession`
- `Uncoded`
- `Excluded`

Each flag must be exactly `Yes` or `No`:

- `foreign_language_negation`
- `singing`
- `mimicry`
- `tag_question`
- `repetition`
- `not_a_negation`

## Bloom Coding Rules

Prefer semantic function over surface syntax.

Use discourse context before and after the target utterance. A bare `no` is not
automatically any one label; infer the communicative function from context.

Choose `Nonpossession` when the key meaning is that someone does not have the
referent.

Choose `Nonexistence` when an expected referent is absent, missing, gone, or
unavailable in the situation.

Choose `Rejection` when the negation opposes, refuses, rejects, or pushes back
against an object, offer, action, request, proposal, or ongoing event. If an
utterance can reasonably be interpreted as `Rejection`, use `Rejection` rather
than `Denial`.

Choose `Denial` only when `Nonpossession`, `Nonexistence`, and `Rejection` do
not apply, and the main function is to deny the truth of a proposition.

Use `Uncoded` only when the context is genuinely insufficient or competing
interpretations remain unresolved after reviewing context.

Use `Excluded` when the token should not be analyzed as a meaningful negation
act, especially if `singing`, `mimicry`, or `not_a_negation` is `Yes`.

## Flag Rules

`foreign_language_negation`: Mark `Yes` if the target negator is from a
language other than English. Do not automatically exclude; code the Bloom label
normally if the use is interpretable.

`singing`: Mark `Yes` if the target negator is in song lyrics or sung material.
If `Yes`, set `bloom_label` to `Excluded`.

`mimicry`: Mark `Yes` if the child exactly repeats something another speaker
just said and appears to be simply imitating rather than conveying a new
communicative act. If `Yes`, set `bloom_label` to `Excluded`.

`tag_question`: Mark `Yes` only if the target negator is inside a tag question,
such as the `don't` in `you like pasta, don't you?`. Do not mark `Yes` for
ordinary negation followed by a positive tag, such as `you don't like pasta, do
you?`. Do not automatically exclude tag questions.

`repetition`: Mark `Yes` if the target negator is lexically the same as the
previous coded negator token and the prejacent/meaning is the same. For `no no
no`, the first `no` is `No` for repetition and the later identical tokens are
`Yes`. Do not mark repetition when adjacent negators have different meanings,
as in `No, I didn't`.

`not_a_negation`: Mark `Yes` if the target string was flagged as a negator but
is not functioning as negation in context, such as `no` inside `know`. If `Yes`,
set `bloom_label` to `Excluded`.

## Output Contract

Return exactly this JSON shape:

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
      "comments": "Short reason based on context."
    }
  ]
}
```

Requirements:

- Include exactly one prediction for every input `record_id`.
- Do not omit, duplicate, or invent `record_id` values.
- Use exact enum spelling and capitalization.
- Keep `comments` brief, factual, and under 300 characters.
- If uncertain, choose the best label when possible; reserve `Uncoded` for
  truly unresolved cases.

## Examples

Example A:

Context: Caregiver opens fridge, expected milk is gone. Child says: `No milk.`
Target: `no`

Prediction: `Nonexistence`; all flags `No`.
Reason: expected referent is absent.

Example B:

Context: Caregiver offers peas. Child says: `No!`
Target: `no`

Prediction: `Rejection`; all flags `No`.
Reason: child rejects offered item/action.

Example C:

Context: Caregiver says `This is a tomato` while holding a banana. Child says:
`No.`
Target: `no`

Prediction: `Denial`; all flags `No`.
Reason: child denies truth of prior proposition.

Example D:

Context: Child checks pockets and says: `I don't have stickers.`
Target: `don't`

Prediction: `Nonpossession`; all flags `No`.
Reason: main meaning is lack of possession.

Example E:

Context: Caregiver says `Say "No, I don't want it."` Child echoes exactly:
`No, I don't want it.`
Target: `no`

Prediction: `Excluded`; `mimicry` is `Yes`; other flags `No`.
Reason: direct imitation without clear new communicative act.

Example F:

Context: Auto-search flagged `no` inside `I know that.`
Target: `no`

Prediction: `Excluded`; `not_a_negation` is `Yes`; other flags `No`.
Reason: target string is not functioning as negation.

Example G:

Context: Child says `No no no` as a refusal. Current target is the second `no`.
Target: `no`

Prediction: `Rejection`; `repetition` is `Yes`; other flags `No`.
Reason: same negator and same meaning as immediately previous coded token.

## Batch Input

You will receive a JSON array of records. Each record contains fields such as:

- `record_id`
- `language`
- `transcript_id`
- `line`
- `speaker`
- `target_negator`
- `target_utterance`
- `context_before`
- `context_after`

Code every record in the batch.
