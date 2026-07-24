# Bloom v5 German Negation Coding Prompt (Masked Negator Variant)

Prompt version: `p005m-de-loc`. Pairs with policy `bloom_v5`
(`v5/Bloom_coding_policy_v5.md`) and schema `v5/bloom_v5_output.schema.json`.

Use this prompt for Phase 1 German Bloom coding on development splits.

Do not run this prompt on `test_lockbox` until the pipeline, prompt text,
model choice, decoding parameters, validation code, and scoring code are frozen.

## System / Task Instruction

You are coding German child-caregiver transcript negation tokens for the XLing
negation project.

Each input record corresponds to exactly one target negator token. For each
record, assign one Bloom-style label, a `certain` judgment, and six
metalinguistic flags. Use the
target utterance plus the surrounding context before and after the utterance.
Do not use human coder labels, split metadata, or evaluation results.

Return only valid JSON matching schema version `bloom_v5`. Do not include
Markdown, prose outside JSON, or extra keys.

**Masked-negator variant.** The target lexeme is hidden:
`target_negator` is `[MASKED]`, and its occurrences in `target_utterance`
are `[MASKED]`. Code from the utterance frame and discourse context.

Human pre-screening already removed rows marked `not_a_negation`,
`repetition`, or `foreign_language_negation`. Therefore always set those
three flags to `No`, skip Step 0 and the exact-lexeme/homograph checks, and
do not emit `Excluded` via `not_a_negation`. Continue to judge `singing`,
`mimicry`, and `tag_question` from the visible context.

Use `negator_index_in_utterance` only to align the masked slot with its
record; do not try to reconstruct the hidden lexeme.

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

Use discourse context before and after the target utterance. A bare `nein`,
`nee`, or `ne` is not automatically any one label; infer the communicative
function from context.

**Masked pre-screening.** Records requiring a visible
lexeme to identify `not_a_negation`, `repetition`, or
`foreign_language_negation` were removed before this arm. Do not repeat Step
0 from the unmasked prompt. Continue to detect singing and mimicry from the
visible transcript context.

### Locate the masked target slot

Use `negator_index_in_utterance` to align this record with the appropriate
masked slot. The lexeme and its homograph status were pre-screened and are
not available in this arm; do not try to reconstruct them.

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

Before applying these tendencies, run Step 0: several of these candidate
forms have common non-negation readings (see the known false-positive
readings below).

### Use the participants as your guide

The people in the conversation saw and heard what you cannot. How they respond
to the negation shows how they understood it in the moment; when such uptake
cues are present, give them priority over surface form. This evidence cuts
both ways:

- The addressee responds by **pleading, re-offering, bargaining, coaxing, or
  insisting** (`bitte? nur dieses eine Mal?`, `komm, probier mal ein bisschen`)
  => they heard a refusal => `Rejection`.
- The addressee responds by **re-asserting, correcting, conceding, or
  agreeing about facts** (`doch, mag sie!`, `genau`, `ach, du hast recht`) =>
  they heard a claim about truth => `Denial`.
- The child's **own following turns are uptake evidence too**: a
  counter-proposal (`ich will X`) or continued bargaining shows the negation
  was a move in a negotiation => `Rejection`.

Uptake is strong evidence, not absolute proof; weigh it together with the rest
of the context.

### Rejection vs Denial: decide what the negation targets

- Negation targets a thing, offer, or action in play (refusing, stopping,
  preventing) => `Rejection`.
- Negation targets the truth of a statement (contesting it, or agreeing with a
  negative statement) => `Denial`.

Before the five traps, perform a **literal-content / live-move
test**:

1. Paraphrase the literal negative content.
2. Separately name what the child is doing with it in this exchange.

If a puzzle placement, object choice, turn, food item, departure, or other
concrete course of action is currently being negotiated, and the child uses
the negation to block it or replace it with an alternative, the live move is
`Rejection` even when the words also describe location, preference, or a
future action. Examples of rejecting shapes include `not there` while moving
a proposed puzzle piece, `not that one - this one`, and `I'm not going` in a
compliance struggle.

Do not infer `Rejection` from activity alone. There must be a specific
thing/action in play plus evidence that the negation opposes it. If the
exchange only asks what is true and no course of action is being accepted,
blocked, or replaced, use `Denial` (unless a dedicated existence/possession
label applies).

Five traps to avoid:

1. A negation that responds to someone's **assertion about the speaker** is
   `Denial`, not `Rejection`, even when the assertion concerns food, likes, or
   wants. Sibling: `er mag Karotten.` Child: `nein.` => `Denial` (the child
   denies the claim; no carrot was offered).
2. A negated attitude verb is not automatically `Rejection` - and not
   automatically `Denial` either. `ich will X nicht` refusing an offered or
   impending X is `Rejection`. `ich mag es auch nicht`, said to **agree**
   with another speaker's `dieses Zimmer ist zu dunkel, ich mag es nicht`, is
   `Denial`: it affirms that [ich mag es] is false; nothing is offered or
   refused. But `ich mag es nicht` said while **resisting an item in an active
   exchange** - especially when the child then counter-proposes
   (`ich will X`) - is `Rejection`: the dislike statement is the move by which
   the child refuses. Alignment with an evaluation => `Denial`; resistance
   within a negotiation => `Rejection`.
3. A statement that **functions as a request or proposal is a request, not an
   assertion**. Caregivers often propose actions by stating the child's
   expected behavior and seeking compliance, frequently with a confirmation
   tag: `du wolltest doch deine Schuhe an die Tür stellen, okay?`.
   A `nein` to such an utterance refuses the proposed action => `Rejection`,
   not Denial of a proposition about the child's plans.

4. **Answers to questions: classify the question's move, not its syntax.**
   When the negation answers a question, first decide what the question was
   doing:
   - The question **offers, proposes, requests, or seeks permission or
     compliance** (`would you like lunch?`, `should I give this to Grandma?`,
     `can you put it on by yourself?`, `want to try?`) => a negative answer
     refuses the offered thing or proposed action => `Rejection`.
   - The question **seeks information about a fact** (`is it hot?`, `did you
     have story time today?`, `is that for your cats?`) => a negative answer
     asserts that the proposition is false => `Denial`.
   Do not code `Denial` merely because a `no` can be paraphrased as denying
   the proposition inside the question - every refusal can be paraphrased
   that way. And do not code `Rejection` merely because the answer is a bare
   `no` - check what the question was doing.
5. **Negated ability, fit, or success is a claim about the world.**
   `I can't open it`, `it doesn't fit`, `it doesn't work` assert that a
   proposition about ability or fit is false => `Denial` by default, and
   never `Nonexistence` (nothing is absent). Code `Rejection` only when such
   a statement is the child's move to resist a directive just issued to them
   (caregiver: `climb up` - child: `I can't`, with uptake showing a
   compliance struggle rather than a factual exchange).

One more contrast: a **normative statement deployed to stop an ongoing
activity** (`you shouldn't eat those!` while the addressee is eating them)
is a prohibiting move => `Rejection`; the same sentence produced as a
detached rule statement and met with agreement is `Denial` (see negative
imperatives below).

### Negative imperatives (`nicht + VP`, e.g. `verschütt es nicht`, `nicht springen`)

German negative commands negate an imperative or infinitive with `nicht` or a
`kein`-phrase (`verschütt es nicht`, `nicht springen`, `nicht anfassen`).

- Stopping or preventing a **specific action by a specific person** (ongoing,
  imminent, or anticipated) => `Rejection`. Example: `verschütt es nicht, Anna`
  said as the sister picks up a too-full cup => `Rejection`.
- Stating a **general rule or norm**, typically echoing a rule just discussed
  => `Denial` (the child asserts that one does not do that). Cue: the
  addressee replies with agreement (`ja`, `genau`) rather than by stopping an
  action.

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

Use `Uncoded` only when at least two functions remain genuinely plausible
after these checks and neither construction, activity, question, nor uptake
resolves them. If one label is best but doubt remains, choose it and report
`certain` = `No`.

Transcripts mark unintelligible speech as `xxx` and untranscribed speech as
`www`. Unintelligibility does not erase a recoverable construction or
activity-level function. If the target is a real negation but its function
cannot be recovered even from those sources, use `Uncoded`.

Use `Excluded` only when the token should not be analyzed as a negation act at
all, and only together with a licensing flag still judgeable in this
arm: `singing` or `mimicry` = `Yes`. Never use `Excluded` for a real negation that is
merely ambiguous or unintelligible.

### Mechanical flag preflight

Before interpreting propositional content, scan the visible transcript for
the two exclusion cues that remain judgeable in this arm:

1. If the target is in a line marked or contextually identified as singing
   or song lyrics, choose `Excluded` + `singing` = `Yes`.
2. If the target line has an imitation marker (`[+ IMIT]`, `[+ IMI]`,
   `[=! imitates]`) or is an exact, contentless echo of the immediately
   preceding adult line, choose `Excluded` + `mimicry` = `Yes`.

Do not first assign the label that the sung or imitated sentence would have
had as an independent child assertion.

## Flag Rules

`foreign_language_negation`: Always `No` in this variant; such rows were removed before prompting.

`singing`: Mark `Yes` if the target negator is in song lyrics or sung material.
If `Yes`, set `bloom_label` to `Excluded`.

`mimicry`: Mark `Yes` if the child exactly repeats something another speaker
just said and appears to be simply imitating rather than conveying a new
communicative act. If `Yes`, set `bloom_label` to `Excluded`. Transcripts often mark imitation explicitly on the child's line (`[+ IMIT]`, `[+ IMI]`, `[=! imitates]`): treat a target line carrying such a marker as mimicry unless context clearly shows the child is doing more than echoing. An exact echo of the immediately preceding adult turn with nothing added is mimicry even without a marker.

`tag_question`: Mark `Yes` only if the target negator is inside a tag question,
such as the `nicht` in `du magst Nudeln, nicht?` or the `ne` in `du magst
Nudeln, ne?`. Do not mark `Yes` for ordinary negation followed by a positive
tag, such as `du magst keine Nudeln, oder?`. Do not automatically exclude tag
questions.

`repetition`: Always `No` in this variant; rows
requiring a visible target lexeme to judge repetition were removed before
prompting.

`not_a_negation`: Always `No` in this variant; false-positive candidate
negators were removed before prompting.

## Decide First, Then Write

Reach the final decision in this order for every record:

1. Align the indexed masked slot with its record.
2. Run the visible singing/mimicry preflight.
3. State the literal negative content recoverable from the utterance frame.
4. Check `Nonpossession`, then `Nonexistence`.
5. State the live discourse move and decide `Rejection` versus residual
   `Denial`.
6. Use `Uncoded` only if the function itself remains unresolved.
7. Set `certain` = `No` if a second label remains seriously plausible.

Identify the specific context line(s) - a quoted fragment or line number -
that determined the label. A comment that merely paraphrases the proposition
is not enough when Rejection is possible: state whether a concrete
thing/action was being accepted, blocked, or replaced.

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
  "schema_version": "bloom_v5",
  "predictions": [
    {
      "record_id": "ger_000000",
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

Context: Caregiver opens fridge, expected milk is gone. Child says: `keine
Milch.`
Target: `keine`

Prediction: `Nonexistence`; all flags `No`.
Reason: expected referent is absent.

Example B:

Context: Caregiver offers peas. Child says: `nein!`
Target: `nein`

Prediction: `Rejection`; all flags `No`.
Reason: child rejects offered item/action.

Example C:

Context: Caregiver says `das ist eine Tomate` while holding a banana. Child
says: `nein.`
Target: `nein`

Prediction: `Denial`; all flags `No`.
Reason: child denies truth of prior proposition.

Example D:

Context: Child checks pockets and says: `ich habe keine Aufkleber.`
Target: `keine`

Prediction: `Nonpossession`; all flags `No`.
Reason: main meaning is lack of possession.

Example E:

Context: Caregiver says `sag "nein, ich will das nicht".` Child echoes exactly:
`nein, ich will das nicht.`
Target: `nein`

Prediction: `Excluded`; `mimicry` is `Yes`; other flags `No`.
Reason: direct imitation without clear new communicative act.

Example F:

Context: Auto-search flagged `nie` inside `Knie.`
Target: `nie`

Prediction: `Excluded`; `not_a_negation` is `Yes`; other flags `No`.
Reason: target string is part of a larger word, not functioning as negation.

Example G:

Context: Child says `nein nein nein` as a refusal. Current target is the second
`nein` (`negator_index_in_utterance` 2, `negators_in_utterance` 3).
Target: `nein`

Prediction: `Rejection`; `repetition` is `Yes`; other flags `No`.
Reason: same negator and same meaning as immediately previous coded token.

Example H:

Context: Sibling says `er mag Karotten.` Child says: `nein.`
Target: `nein`

Prediction: `Denial`; all flags `No`.
Reason: denies a claim about the child; nothing was offered, so not Rejection.

Example I:

Context: Caregiver says `dieses Zimmer ist zu dunkel, ich mag es nicht.` Child
says: `ich mag es auch nicht.`
Target: `nicht`

Prediction: `Denial`; all flags `No`.
Reason: agrees with an evaluative statement by affirming a negative
proposition; nothing offered or refused.

Example J:

Context: Sister picks up a very full cup. Child says: `verschütt es nicht,
Anna.`
Target: `nicht`

Prediction: `Rejection`; all flags `No`.
Reason: negative imperative preventing a specific anticipated action by a
specific person.

Example K:

Context: Caregiver just said `wir springen nicht aufs Sofa.` Child says: `nicht
springen, Papa.` Caregiver answers: `ja, genau.`
Target: `nicht`

Prediction: `Denial`; all flags `No`.
Reason: child restates the rule; the agreement response shows it asserts a
norm rather than stopping an action.

Example L:

Context: Child shouts `nein xxx nein xxx!` Most of the utterance is
unintelligible, but the `nein` is a real negation. Current target is the first
`nein` (`negator_index_in_utterance` 1, `negators_in_utterance` 2).
Target: `nein`

Prediction: `Uncoded`; all flags `No`.
Reason: genuine negation whose function cannot be recovered from context;
ambiguity is Uncoded, never Excluded.

Example M:

Context: Same utterance `nein xxx nein xxx!` Current target is the second
`nein` (`negator_index_in_utterance` 2, `negators_in_utterance` 2).
Target: `nein`

Prediction: `Uncoded`; `repetition` is `Yes`; other flags `No`.
Reason: second identical negator in the same utterance; repetition flag plus
the same label as the first token.

Example N:

Context: Caregiver: `du wolltest doch deine Schuhe an die Tür stellen, okay?`
Child: `nein.` Caregiver: `bitte? bevor wir gehen?`
Target: `nein`

Prediction: `Rejection`; all flags `No`.
Reason: the caregiver's statement functions as a proposal, and the pleading
uptake shows she heard a refusal - not a denial of a claim about the child's
plans.

Example O:

Context: Caregiver hands the child the green cup. Child: `ich mag diesen Becher
nicht.` Child next turn: `ich will den roten Becher.`
Target: `nicht`

Prediction: `Rejection`; all flags `No`.
Reason: resisting an item in an active exchange, confirmed by the
counter-proposal; contrast with Example I, where the child aligns with another
speaker's evaluation.

Example P:

Context: Sibling: `es regnet draußen.` Child: `nein.` Caregiver: `doch, es
regnet, schau!`
Target: `nein`

Prediction: `Denial`; all flags `No`.
Reason: the re-asserting uptake shows the family heard a truth dispute, not a
refusal.

Example Q:

Context: Child said `verschütt es nicht, Anna` (coded Rejection). Two lines
later the child repeats: `verschütt es nicht.` (marked `[+ SR]`).
Target: `nicht`

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

Context: Child is pressing a puzzle piece into a slot and says: `it doesn't
fit.` Caregiver: `try turning it around.`
Target: `doesn't`

Prediction: `Denial`; `certain` `Yes`; all flags `No`.
Reason: negated fit is a claim about the world - not `Nonexistence` (nothing
is absent) and not `Rejection` (no directive is being resisted).

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
- `target_negator`: always `[MASKED]` in this variant
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
