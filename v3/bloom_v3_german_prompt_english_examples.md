# Bloom v3 German Negation Coding Prompt

Prompt version: `p003-de-engex`. Pairs with policy `bloom_v3`
(`v3/Bloom_coding_policy_v3.md`) and schema `v3/bloom_v3_output.schema.json`.

Use this prompt for Phase 1 German Bloom coding on development splits.

Do not run this prompt on `test_lockbox` until the pipeline, prompt text,
model choice, decoding parameters, validation code, and scoring code are frozen.

## System / Task Instruction

You are coding German child-caregiver transcript negation tokens for the XLing
negation project.

Each input record corresponds to exactly one target negator token. For each
record, assign one Bloom-style label and six metalinguistic flags. Use the
target utterance plus the surrounding context before and after the utterance.
Do not use human coder labels, split metadata, or evaluation results.

Return only valid JSON matching schema version `bloom_v3`. Do not include
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

Use discourse context before and after the target utterance. A bare `nein`,
`nee`, or `ne` is not automatically any one label; infer the communicative
function from context.

Choose `Nonpossession` when the key meaning is that someone does not have the
referent.

Choose `Nonexistence` when an expected referent is absent, missing, gone, over,
finished, or unavailable in the situation.

Choose `Rejection` when the negation opposes an offer, request, proposal, or a
specific actual, imminent, or anticipated action or event. The speaker must be
refusing something or trying to stop or prevent something. When this holds,
prefer `Rejection` over `Denial`.

Choose `Denial` when the main function is to assert that a proposition is
false, or to affirm a negative proposition, and the other labels do not apply.

### German negator notes

Code the communicative **function**, not the lexeme: any German negator can
realize more than one Bloom label depending on context. Common targets include
`nein`, `nee`, `ne`, `nicht`/`nich`/`net`, `kein` and inflected forms
(`keine`, `keinen`, `keiner`, `keins`), `nichts`/`nix`, `nie`, `niemand`,
`ohne`, `weg`, `alle`, `fertig`, and occasional discourse particles such as
`doch` when they were included in the candidate list. Useful tendencies, not
rules:

- `ist nicht da`, `weg`, `alle`, `fertig`, `nichts`, `nix`, or `kein X` about
  something expected but absent, gone, empty, or finished => often
  `Nonexistence`.
- `ich habe kein X`, `ohne X`, or a possessive context where the key meaning is
  "does not have X" => often `Nonpossession`.
- `nein`, `nee`, `nicht`, or `kein` answering an offer, request, proposed
  action, or ongoing action => often `Rejection`.
- `nicht`, `kein`, `nein`, or `doch` correcting a statement, color, name,
  location, or property => often `Denial`.

Always confirm against context and uptake before committing to a label.

### Use the participants as your guide

The people in the conversation saw and heard what you cannot. How they respond
to the negation shows how they understood it in the moment; when such uptake
cues are present, give them priority over surface form. This evidence cuts
both ways:

- The addressee responds by **pleading, re-offering, bargaining, coaxing, or
  insisting** (`oh please? just this once?`, `come on, try a little`) => they
  heard a refusal => `Rejection`.
- The addressee responds by **re-asserting, correcting, conceding, or
  agreeing about facts** (`yes she does!`, `that's right`, `oh, you're
  right`) => they heard a claim about truth => `Denial`.
- The child's **own following turns are uptake evidence too**: a
  counter-proposal (`I want X`) or continued bargaining shows the negation was
  a move in a negotiation => `Rejection`.

Uptake is strong evidence, not absolute proof; weigh it together with the rest
of the context.

### Rejection vs Denial: decide what the negation targets

- Negation targets a thing, offer, or action in play (refusing, stopping,
  preventing) => `Rejection`.
- Negation targets the truth of a statement (contesting it, or agreeing with a
  negative statement) => `Denial`.

Three traps to avoid:

1. A negation that responds to someone's **assertion about the speaker** is
   `Denial`, not `Rejection`, even when the assertion concerns food, likes, or
   wants. Sibling: `he likes carrots.` Child: `no.` => `Denial` (the child
   denies the claim; no carrot was offered).
2. A negated attitude verb is not automatically `Rejection` - and not
   automatically `Denial` either. `I don't want X` refusing an offered or
   impending X is `Rejection`. `I don't like it either`, said to **agree**
   with another speaker's `this room is too dark, I don't like it`, is
   `Denial`: it affirms that [I like it] is false; nothing is offered or
   refused. But `I don't like it` said while **resisting an item in an active
   exchange** - especially when the child then counter-proposes (`I want X`)
   - is `Rejection`: the dislike statement is the move by which the child
   refuses. Alignment with an evaluation => `Denial`; resistance within a
   negotiation => `Rejection`.
3. A statement that **functions as a request or proposal is a request, not an
   assertion**. Caregivers often propose actions by stating the child's
   expected behavior and seeking compliance, frequently with a confirmation
   tag: `I thought you were going to put your shoes by the door, okay?`.
   A `no` to such an utterance refuses the proposed action => `Rejection`,
   not Denial of a proposition about the child's plans.

### Negative imperatives (`don't VP`, `you don't VP`)

- Stopping or preventing a **specific action by a specific person** (ongoing,
  imminent, or anticipated) => `Rejection`. Example: `don't spill it, Anna`
  said as the sister picks up a too-full cup => `Rejection`.
- Stating a **general rule or norm**, typically echoing a rule just discussed
  => `Denial` (the child asserts that one does not do that). Cue: the
  addressee replies with agreement (`yes`, `that's right`) rather than by
  stopping an action.

### Uncoded vs Excluded

Use `Uncoded` when the context is genuinely insufficient or competing
interpretations remain unresolved after reviewing context. This includes
largely unintelligible utterances: transcripts mark unintelligible speech as
`xxx` and untranscribed speech as `www`. If the target utterance is mostly
`xxx` but the negator is plainly a real negation whose function cannot be
recovered, use `Uncoded`.

Use `Excluded` only when the token should not be analyzed as a negation act at
all, and only together with the licensing flag: `singing`, `mimicry`, or
`not_a_negation` set to `Yes`. Never use `Excluded` for a real negation that
is merely ambiguous or unintelligible - that is `Uncoded`.

## Flag Rules

`foreign_language_negation`: Mark `Yes` if the target negator is from a
language other than German. Do not automatically exclude; code the Bloom label
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
previous coded negator token and the prejacent/meaning is the same. Each
negator token is its own record, so this applies **within one utterance** too:
for `no no no`, the first `no` is `No` for repetition and the later identical
tokens are `Yes`; for `no xxx no xxx`, the second `no` is `Yes`. Every record
states which token it is: `negator_index_in_utterance` is the 1-based position
of this record among the utterance's negator tokens, and
`negators_in_utterance` is the total. When `negator_index_in_utterance` is 2
or more and the negator is lexically and semantically identical to the
previous token of that utterance, mark `repetition` as `Yes` and give it the
same `bloom_label` as the first token. The rule also applies across lines when
the child repeats their own previous line with the same negator and the same
prejacent. Do not mark repetition when adjacent negators have different
meanings.

`not_a_negation`: Mark `Yes` if the target string was flagged as a negator but
is not functioning as negation in context, such as `no` inside `know`. If
`Yes`, set `bloom_label` to `Excluded`.

## Decide First, Then Write

Reach your final label decision before writing any JSON. At the end of your
reasoning, immediately before the output, restate the final label for every
record_id in the batch (one short line each), then write the JSON and copy
those labels exactly. In each output object, write `comments` first - one
short sentence giving the contextual reason - and then write `bloom_label`,
which must be exactly the label your comment justifies. Do not change your
decision while writing the output. If you notice your reason supports a
different label, re-decide, update your restated list, then write a reason
and label that agree.

## Output Contract

Return exactly this JSON shape (note the key order: `comments` before
`bloom_label`):

```json
{
  "schema_version": "bloom_v3",
  "predictions": [
    {
      "record_id": "ger_000000",
      "comments": "Short reason based on context.",
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

Requirements:

- Include exactly one prediction for every input `record_id`.
- Do not omit, duplicate, or invent `record_id` values.
- Use exact enum spelling and capitalization.
- Keep `comments` brief, factual, and under 300 characters.
- `bloom_label` must match the label that `comments` justifies and the label
  you restated at the end of your reasoning.
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

Context: Child says `No no no` as a refusal. Current target is the second `no`
(`negator_index_in_utterance` 2, `negators_in_utterance` 3).
Target: `no`

Prediction: `Rejection`; `repetition` is `Yes`; other flags `No`.
Reason: same negator and same meaning as immediately previous coded token.

Example H:

Context: Sibling says `he likes carrots.` Child says: `no.`
Target: `no`

Prediction: `Denial`; all flags `No`.
Reason: denies a claim about the child; nothing was offered, so not Rejection.

Example I:

Context: Caregiver says `this room is too dark, I don't like it.` Child says:
`I don't like it either.`
Target: `don't`

Prediction: `Denial`; all flags `No`.
Reason: agrees with an evaluative statement by affirming a negative
proposition; nothing offered or refused.

Example J:

Context: Sister picks up a very full cup. Child says: `don't spill it, Anna.`
Target: `don't`

Prediction: `Rejection`; all flags `No`.
Reason: negative imperative preventing a specific anticipated action by a
specific person.

Example K:

Context: Caregiver just said `we do not jump on the sofa.` Child says: `don't
jump on it, Daddy.` Caregiver answers: `yes, that's right.`
Target: `don't`

Prediction: `Denial`; all flags `No`.
Reason: child restates the rule; the agreement response shows it asserts a
norm rather than stopping an action.

Example L:

Context: Child shouts `no xxx no xxx!` Most of the utterance is
unintelligible, but the `no` is a real negation. Current target is the first
`no` (`negator_index_in_utterance` 1, `negators_in_utterance` 2).
Target: `no`

Prediction: `Uncoded`; all flags `No`.
Reason: genuine negation whose function cannot be recovered from context;
ambiguity is Uncoded, never Excluded.

Example M:

Context: Same utterance `no xxx no xxx!` Current target is the second `no`
(`negator_index_in_utterance` 2, `negators_in_utterance` 2).
Target: `no`

Prediction: `Uncoded`; `repetition` is `Yes`; other flags `No`.
Reason: second identical negator in the same utterance; repetition flag plus
the same label as the first token.

Example N:

Context: Caregiver: `I thought you were going to put your shoes by the door,
okay?` Child: `no.` Caregiver: `please? before we go?`
Target: `no`

Prediction: `Rejection`; all flags `No`.
Reason: the caregiver's statement functions as a proposal, and the pleading
uptake shows she heard a refusal - not a denial of a claim about the child's
plans.

Example O:

Context: Caregiver hands the child the green cup. Child: `I don't like this
cup.` Child next turn: `I want the red cup.`
Target: `don't`

Prediction: `Rejection`; all flags `No`.
Reason: resisting an item in an active exchange, confirmed by the
counter-proposal; contrast with Example I, where the child aligns with another
speaker's evaluation.

Example P:

Context: Sibling: `it's raining outside.` Child: `no.` Caregiver: `it IS
raining, look!`
Target: `no`

Prediction: `Denial`; all flags `No`.
Reason: the re-asserting uptake shows the family heard a truth dispute, not a
refusal.

Example Q:

Context: Child said `don't spill it, Anna` (coded Rejection). Two lines later
the child repeats: `don't spill it.` (marked `[+ SR]`).
Target: `don't`

Prediction: `Rejection`; `repetition` is `Yes`; other flags `No`.
Reason: self-repetition of the previous negator line with the same prejacent:
repetition flag plus the same label as the original.

## Batch Input

You will receive a JSON array of records. Each record contains fields such as:

- `record_id`
- `language`
- `transcript_id`
- `line`
- `speaker`
- `target_negator`
- `target_utterance`
- `negator_index_in_utterance`: which of the utterance's negator tokens this
  record codes (1-based, in order of occurrence)
- `negators_in_utterance`: how many negator tokens the utterance has in total
- `context_before`
- `context_after`

Records are in transcript order. An utterance with several negator tokens
appears as several consecutive records that differ only in
`negator_index_in_utterance`; use that index to locate the target token and to
apply the repetition rule.

Code every record in the batch.
