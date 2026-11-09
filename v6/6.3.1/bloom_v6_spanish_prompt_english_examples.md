# Bloom v6 Spanish Negation Coding Prompt

Prompt version: `p00631-es-engex`. Pairs with policy `bloom_v6`
(`v6/6.3.1/Bloom_coding_policy_v6.md`) and schema `v6/bloom_v6_output.schema.json`.

Use this prompt for Phase 1 Spanish Bloom coding on development splits.

Do not run this prompt on `test_lockbox` until the pipeline, prompt text,
model choice, decoding parameters, validation code, and scoring code are frozen.

## System / Task Instruction

You are coding Spanish child-caregiver transcript negation tokens for the XLing
negation project.

Each input record corresponds to exactly one target negator token. For each
record, assign one Bloom-style label, a `certain` judgment, and six
metalinguistic flags. Use the
target utterance plus the surrounding context before and after the utterance.
Do not use human coder labels, split metadata, or evaluation results.

Return only valid JSON matching schema version `bloom_v6`. Do not include
Markdown, prose outside JSON, or extra keys.

## Allowed Output Labels

`bloom_label` must be exactly one of:

- `Nonexistence`
- `Rejection`
- `Denial`
- `Nonpossession`
- `Uncoded`
- `Excluded`

`certain` must be exactly `Yes` or `No`: after choosing the label, report
whether you are confident in it. `Yes` means you would not seriously consider
a different label for this token; `No` means a second label remains
plausible. Report `No` honestly rather than defaulting to `Yes` - but never
use `certain` as a substitute for choosing the single best label.

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

**Step 0 - is the target token a negation at all?** The candidate list that
flagged the target token over-generates by design: some flagged tokens are
not functioning as negation in their context (see the known false-positive
readings below). Decide this first. If the token is not performing a negation
act here, the answer is `Excluded` with `not_a_negation` = `Yes` - do not
force a Bloom label onto a false positive.

### Align and interpret the target occurrence

Use `negator_index_in_utterance` to identify which occurrence this record
targets. Interpret that occurrence using the transcription, CHAT annotations,
surrounding utterance, and discourse context. The production may be
incomplete, phonologically approximate, misspelled, or imperfectly
transcribed; reconstruct its best-supported intended meaning rather than
requiring a literal reading of the surface form.

Do not accidentally transfer the meaning or function of another occurrence
to the indexed target. Do not classify a token as `not_a_negation` merely
because its transcription is imperfect. If two interpretations remain
seriously plausible, choose the best-supported label, set `certain` = `No`,
and describe the ambiguity briefly in `comments`.

### Choose the label in this order

After Step 0, use this order. Do not jump directly from “this sentence states
something false” to `Denial`:

1. **Nonpossession first:** if the core meaning is that a person does not
   have, own, or possess the referent, choose `Nonpossession`. This includes a
   negative answer to `do you have X?` and clauses such as `I don't have X`.
   These are grammatically factual assertions, but the dedicated possession
   label overrides `Denial`.
2. **Then Nonexistence:** if an expected entity is absent, missing, not
   present, gone, finished, or used up, choose `Nonexistence`. This includes
   `X isn't here`, `there is no X`, `no one`, `none left`, and `no more X`.
   An entity can be implicit but recoverable from the activity. Failed
   actions and non-holding properties (`it doesn't fit`, `I can't open it`)
   are not `Nonexistence`.
3. **Then Rejection:** if the negation is the speaker's move for refusing an
   offered thing, blocking or replacing a proposed action, resisting a
   directive, vetoing a placement/choice, or stopping an actual, imminent, or
   anticipated event, choose `Rejection`.
4. **Then Denial:** use `Denial` for a truth claim only after
   `Nonpossession`, `Nonexistence`, and `Rejection` have been ruled out.
   `Denial` is the residual content label, not the default for every
   declarative-looking negative sentence.
5. Use `Uncoded` only if the function itself remains unrecoverable after the
   checks above.

### Known false-positive readings (Spanish)

Check these before coding; when the token is not negating here, use
`Excluded` + `not_a_negation`:

- `no ?` as an echo question: the child repeats an adult's `no` with rising
  intonation to ask about it. The child is querying the adult's negation,
  not producing one.
- `ni` as a disfluency or repair fragment (`ni [/] niñito`), not the
  negative conjunction `ni ... ni ...`.
- `no` inside quoted, read-aloud, or role-played material where the child
  performs someone else's words (see also the `mimicry` flag).

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

**Directing someone's behavior**

During cookie-making, the child tells Dad: "Don't eat those." The transcript does not describe Dad reaching for a cookie.

→ `Rejection`: the child's instruction itself supports an attempt to prevent eating. An independently recorded action is not required.

**Reporting a rule**

Adult: "What is the rule about the sofa?"
Child: "We don't jump on it."

→ `Denial`: the child answers a question about a rule; the exchange supports reporting the rule rather than directing someone's behavior.

**Vetoing a placement**

During a puzzle, the adult proposes a slot.
Child: "Not there."
Adult: "I think it goes there."
Child: "Not there."

→ `Rejection`: the child opposes the proposed placement. The adult's factual disagreement does not establish that the child is merely describing a fact.

**Reporting a failed attempt**

The child tries putting a piece into a slot.
Child: "It doesn't fit. Help me."

→ `Denial`: the child reports difficulty and seeks help with the attempt.

If the exchange reasonably supports both reporting a placement problem and opposing the placement, prefer `Rejection` and set `certain` to `No`.

**An inability statement used to resist a request**

Adult: "Climb up."
Child: "I can't."
Adult: "Come on, try."

→ `Rejection`: the inability statement functions as resistance to the requested action.

**A report of inability**

While trying to open a box, the child says "I can't open it" and seeks help.

→ `Denial` when the child is reporting difficulty rather than refusing or resisting the activity.

### Uncoded vs Excluded

`Uncoded` means **the function is unrecoverable**, not merely that the
referent, exact wording, or full prejacent is missing.

Before using it, ask:

- Does the construction itself identify the function? `none left`, `no
  more`, `all gone`, and Tagalog `wala na` express `Nonexistence` even when
  the missing item is unnamed.
- Does the surrounding activity identify the move? In an ongoing offer,
  negotiation, toy struggle, placement dispute, or compliance exchange, a
  bare or garbled negation that opposes the current course of action is
  usually `Rejection`.
- Does a preceding question supply the missing prejacent? A bare negative
  answer inherits the offer, possession, existence, or fact under discussion.

If the remaining plausible alternatives are Rejection and Denial, apply the
Rejection-first tie-break above: choose `Rejection` with `certain` = `No`.
Do not use `Uncoded` for that tie.

Use `Uncoded` only when at least two functions remain genuinely plausible
after these checks and neither construction, activity, question, nor uptake
resolves them. If one label is best but doubt remains, choose it and report
`certain` = `No`.

Transcripts mark unintelligible speech as `xxx` and untranscribed speech as
`www`. Unintelligibility does not erase a recoverable construction or
activity-level function. If the target is a real negation but its function
cannot be recovered even from those sources, use `Uncoded`.

Use `Excluded` only when the token should not be analyzed as a negation act at
all, and only together with a licensing flag: `singing`, `mimicry`, or
`not_a_negation` = `Yes`. Never use `Excluded` for a real negation that is
merely ambiguous or unintelligible.

### Mechanical flag preflight

Run this scan **before** interpreting the lyric's or echo's propositional
content:

1. If the target is in a line marked or contextually identified as singing
   or song lyrics, choose `Excluded` + `singing` = `Yes`.
2. If the target line has an imitation marker (`[+ IMIT]`, `[+ IMI]`,
   `[=! imitates]`) or is an exact, contentless echo of the immediately
   preceding adult line, choose `Excluded` + `mimicry` = `Yes`.
3. If the indexed target occurrence has a listed non-negation reading, choose
   `Excluded` + `not_a_negation` = `Yes`.

Do not first assign the label that the quoted, sung, or imitated sentence
would have had if it were an independent child assertion.

## Flag Rules

`foreign_language_negation`: Mark `Yes` if the target negator is from a
language other than Spanish. Do not automatically exclude; code the Bloom label
normally if the use is interpretable.

`singing`: Mark `Yes` if the target negator is in song lyrics or sung material.
If `Yes`, set `bloom_label` to `Excluded`.

`mimicry`: Mark `Yes` if the child exactly repeats something another speaker
just said and appears to be simply imitating rather than conveying a new
communicative act. If `Yes`, set `bloom_label` to `Excluded`. Transcripts often mark imitation explicitly on the child's line (`[+ IMIT]`, `[+ IMI]`, `[=! imitates]`): treat a target line carrying such a marker as mimicry unless context clearly shows the child is doing more than echoing. An exact echo of the immediately preceding adult turn with nothing added is mimicry even without a marker.

`tag_question`: Mark `Yes` only if the target negator is inside a tag question,
such as the `don't` in `you like pasta, don't you?`. Do not mark `Yes` for
ordinary negation followed by a positive tag, such as `you don't like pasta, do
you?`. Do not automatically exclude tag questions.

`repetition`: Mark `Yes` if the target negator is lexically the same as the
previous coded negator token and the prejacent/meaning is the same. Each
negator token is its own record, so this applies **within one utterance** too:
for `no no no`, the first `no` is `No` for repetition and the later identical
tokens are `Yes`; for `no xxx no xxx`, the second `no` is `Yes`. Every
record states which token it is: `negator_index_in_utterance` is the 1-based
position of this record among the utterance's negator tokens, and
`negators_in_utterance` is the total. When `negator_index_in_utterance` is 2
or more and the negator is lexically and semantically identical to the
previous token of that utterance, mark `repetition` as `Yes` and give it the
**same** `bloom_label` as the first token. The rule also applies **across
lines** when the child repeats their own previous line with the same negator
and the same prejacent (transcripts often mark these `[+ SR]`,
self-repetition): flag the repeated line's negator `Yes` and keep the same
label. Do not mark repetition when adjacent negators have different meanings,
as in `No, I didn't` (two records: `no` is token 1 of 2, `n't` is token 2 of
2, but they negate different prejacents, so neither is flagged).

`not_a_negation`: Mark `Yes` if the target string was flagged as a negator but
is not functioning as negation in context, such as `no` inside `know`. If `Yes`,
set `bloom_label` to `Excluded`.


When judging `not_a_negation`, check the known false-positive readings
section above; those patterns are the most common source of
`not_a_negation` = `Yes`.

## Decide First, Then Write

Reach the final decision in this order for every record:

1. Align the target occurrence using `negator_index_in_utterance`, then
   interpret it contextually.
2. Run the singing/mimicry/not-a-negation preflight.
3. State the literal negative content.
4. Check `Nonpossession`, then `Nonexistence`.
5. State the live discourse move and decide `Rejection` versus residual
   `Denial`.
6. Use `Uncoded` only if the function itself remains unresolved.
7. Set `certain` = `No` if a second label remains seriously plausible.

Identify the specific context line(s) - a quoted fragment or line number -
that determined the label. A comment that merely paraphrases the proposition
(`child says X is false`) is not enough when Rejection is possible: state
whether a concrete thing/action was being accepted, blocked, or replaced.

At the **end of your reasoning, immediately before the output, restate the
final label for every record_id in the batch** (one short line each, naming
the deciding evidence), then write the JSON and copy those labels exactly.
Write `comments` first, then the matching `bloom_label`, then `certain`. If
the reason supports a different label, re-decide before emitting the object.

## Output Contract

Return exactly this JSON shape (note the key order: `comments` before
`bloom_label`, then `certain`, then `flags`):

```json
{
  "schema_version": "bloom_v6",
  "predictions": [
    {
      "record_id": "spa_000000",
      "comments": "Short reason citing the deciding context line.",
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

Requirements:

- Include exactly one prediction for every input `record_id`.
- Do not omit, duplicate, or invent `record_id` values.
- Use exact enum spelling and capitalization.
- Keep `comments` brief, factual, and under 300 characters, citing the
  specific context line or quoted fragment that determined the label.
- `bloom_label` must match the label that `comments` justifies and the label
  you restated at the end of your reasoning.
- `certain` is `Yes` when you would not seriously consider another label,
  `No` when a second label remains plausible. `certain` = `No` on a real
  negation still requires your single best `bloom_label`; do not use
  `Uncoded` to express mere uncertainty.
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
Reason: corrects a claim about the child; a rejecting function is not reasonably supported in this exchange.

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

Context: Caregiver asks: `what is the rule about the sofa?`
Child: `we don't jump on it.`
Target: `don't`

Prediction: `Denial`; `certain` `Yes`; all flags `No`.
Reason: child answers a question about a rule; the exchange supports reporting
the rule rather than directing someone's behavior.

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

Example R:

Context: Caregiver: `do you want your snack now?` Child: `no.` Caregiver:
`okay, later then.`
Target: `no`

Prediction: `Rejection`; `certain` `Yes`; all flags `No`.
Reason: the question offers a snack, so the `no` refuses the offer - not a
denial of the proposition [child wants snack], even though it could be
paraphrased that way.

Example S:

Context: Caregiver: `is the soup still hot?` Child: `no.` Caregiver: `good,
then eat up.`
Target: `no`

Prediction: `Denial`; `certain` `Yes`; all flags `No`.
Reason: the question asks about a fact; the `no` asserts that [the soup is
hot] is false. Nothing is offered or refused.

Example T:

Context: Child tries putting a puzzle piece into a slot and says:
`it doesn't fit. Help me.`
Target: `doesn't`

Prediction: `Denial`; `certain` `Yes`; all flags `No`.
Reason: child reports difficulty and seeks help with the attempt. Nothing is
absent, so this is not `Nonexistence`. If an exchange reasonably supports both
reporting a placement problem and opposing the placement, prefer `Rejection`
and set `certain` to `No`.

Example U:

Context: Caregiver holds out boots: `put these on.` Child: `I can't.`
Caregiver: `come on, you do it every day.`
Target: `can't`

Prediction: `Rejection`; `certain` `Yes`; all flags `No`.
Reason: the inability statement is the child's move to resist the directive
just issued, and the coaxing uptake shows a compliance struggle - contrast
with Example T, where the same shape reports a fact.

Example V:

Context: Caregiver: `be careful, don't drop the plate.` The child's next
line is marked as imitation: `don't drop the plate . [+ IMIT]`
Target: `don't`

Prediction: `Excluded`; `mimicry` is `Yes`; other flags `No`.
Reason: the line is an explicit imitation of the caregiver's warning, not a
new negation act by the child.

Example W:

Context: In an ongoing tug-of-war over a toy that the caregiver keeps trying
to take back, the child produces a fragmentary `no &+da xxx.` The caregiver
keeps coaxing afterwards.
Target: `no`

Prediction: `Rejection`; `certain` `No`; all flags `No`.
Reason: the single turn is garbled, but the surrounding struggle makes a
refusing move the best reading; the residual doubt is reported via `certain`
= `No`, not via `Uncoded`.

Example X:

Context: Caregiver starts putting a puzzle piece in the left slot: `this one
goes here.` Child moves the piece away and says: `not there - here.`
Target: `not`

Prediction: `Rejection`; `certain` `Yes`; all flags `No`.
Reason: the child uses `not there` to veto and replace the caregiver's
proposed placement. Its literal location content does not make the live move
a Denial.

Example Y:

Context: Caregiver: `do you have any crayons in your bag?` Child checks and
answers: `no.`
Target: `no`

Prediction: `Nonpossession`; `certain` `Yes`; all flags `No`.
Reason: the negative answer means that the child does not have the crayons;
the dedicated possession label overrides ordinary factual Denial.

Example Z:

Context: Child and caregiver are searching a container for more blocks. The
child looks inside and says: `none left.` The exact kind of block is not
named in the target line.
Target: `none`

Prediction: `Nonexistence`; `certain` `Yes`; all flags `No`.
Reason: `none left` directly expresses that the expected entities are used up;
an implicit referent does not make the function Uncoded.

Example AA:

Context: The transcript marks the child as singing: `can't you hear the train
coming . [=! sings]`
Target: `can't`

Prediction: `Excluded`; `singing` is `Yes`; other flags `No`.
Reason: the target is inside song lyrics; do not code the lyric's factual
content as Denial.

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
