# Bloom v4 Tagalog Negation Coding Prompt

Prompt version: `p004-tl-loc`. Pairs with policy `bloom_v4`
(`v4/Bloom_coding_policy_v4.md`) and schema `v4/bloom_v4_output.schema.json`.

Use this prompt for Phase 1 Tagalog Bloom coding on development splits.

Do not run this prompt on `test_lockbox` until the pipeline, prompt text,
model choice, decoding parameters, validation code, and scoring code are frozen.

## System / Task Instruction

You are coding Tagalog child-caregiver transcript negation tokens for the XLing
negation project.

Each input record corresponds to exactly one target negator token. For each
record, assign one Bloom-style label, a `certain` judgment, and six
metalinguistic flags. Use the
target utterance plus the surrounding context before and after the utterance.
Do not use human coder labels, split metadata, or evaluation results.

Return only valid JSON matching schema version `bloom_v4`. Do not include
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

Use discourse context before and after the target utterance. A bare `hindi` is
not automatically any one label; infer the communicative function from context.

**Step 0 - is the target token a negation at all?** The candidate list that
flagged the target token over-generates by design: some flagged tokens are
not functioning as negation in their context (see the known false-positive
readings below). Decide this first. If the token is not performing a negation
act here, the answer is `Excluded` with `not_a_negation` = `Yes` - do not
force a Bloom label onto a false positive.

Choose `Nonpossession` when the key meaning is that someone does not have the
referent.

Choose `Nonexistence` when an expected referent is absent, missing, gone, or
unavailable in the situation. `Nonexistence` is about an **entity** that is absent, gone, or used up from the situation - not about actions that fail or properties that do not hold: `it doesn't fit` and `I can't open it` negate propositions and are never `Nonexistence`.

Choose `Rejection` when the negation opposes an offer, request, proposal, or a
specific actual, imminent, or anticipated action or event. The speaker must be
refusing something or trying to stop or prevent something. When this holds,
prefer `Rejection` over `Denial`.

Choose `Denial` when the main function is to assert that a proposition is
false, or to affirm a negative proposition, and the other labels do not apply.

### Tagalog negator notes

Code the communicative **function**, not the lexeme: any Tagalog negator can
realize more than one Bloom label depending on context. The main targets are
`hindi` (not / "no"; often shortened to `di` or `'di`), `wala` (existential and
possessive negator, with linker forms like `walang` and `wala nang`), `huwag`/
`wag` (prohibitive "don't"), `ayaw` (negative volition "don't want / don't
like", including contractions like `ayoko` = `ayaw ko`), `aywan`/`ewan`
("don't know"), `bawal` ("not allowed"), and `ubos` ("used up / all gone").
Useful tendencies, not rules:

- `wala` about something expected but absent (`wala nang gatas`, `wala na`,
  `ubos na`) => often `Nonexistence`.
- `wala` with a possessor (`wala akong X`, "I don't have X") =>
  often `Nonpossession`.
- `huwag`/`wag` stopping or preventing a specific action => often `Rejection`;
  as a general rule or norm (like `bawal`) => often `Denial`.
- `ayaw`/`ayoko` refusing an offer or impending thing => often `Rejection`.
- `hindi` answering an offer or proposal => `Rejection`; `hindi` contesting or
  confirming the truth of a statement => `Denial`.

Always confirm against context and uptake before committing to a label.

Before applying these tendencies, run Step 0: several of these candidate
forms have common non-negation readings (see the known false-positive
readings below).

### Known false-positive readings (Tagalog)

Check these before coding; when the token is not negating here, use
`Excluded` + `not_a_negation`:

- `di` as part of another word or a mishearing, rather than short `hindi`.
- `wala` inside frozen expressions (`walang anuman` 'you're welcome').
- `ewan`/`aywan` ('dunno') as a filler shrug with no target proposition;
  when it genuinely denies knowledge, code it normally.
- Sound-play: a child chanting a negator repeatedly while babbling
  (`hindi hindi hindi` with no proposition or action in play) is `Excluded`
  + `not_a_negation` only when clearly non-communicative; if it is a real
  negation whose function cannot be recovered, it is `Uncoded`.

### Use the participants as your guide

The people in the conversation saw and heard what you cannot. How they respond
to the negation shows how they understood it in the moment; when such uptake
cues are present, give them priority over surface form. This evidence cuts
both ways:

- The addressee responds by **pleading, re-offering, bargaining, coaxing, or
  insisting** (`sige na? isa na lang?`, `sige na, tikman mo lang`) => they
  heard a refusal => `Rejection`.
- The addressee responds by **re-asserting, correcting, conceding, or
  agreeing about facts** (`gusto nga niya!`, `tama`, `ah, tama ka`) => they
  heard a claim about truth => `Denial`.
- The child's **own following turns are uptake evidence too**: a
  counter-proposal (`gusto ko ng X`) or continued bargaining shows the negation
  was a move in a negotiation => `Rejection`.

Uptake is strong evidence, not absolute proof; weigh it together with the rest
of the context.

### Rejection vs Denial: decide what the negation targets

- Negation targets a thing, offer, or action in play (refusing, stopping,
  preventing) => `Rejection`.
- Negation targets the truth of a statement (contesting it, or agreeing with a
  negative statement) => `Denial`.

Five traps to avoid:

1. A negation that responds to someone's **assertion about the speaker** is
   `Denial`, not `Rejection`, even when the assertion concerns food, likes, or
   wants. Sibling: `gusto niya ng carrots.` Child: `hindi.` => `Denial` (the
   child denies the claim; no carrot was offered).
2. A negated attitude verb is not automatically `Rejection` — and not
   automatically `Denial` either. `ayaw ko` refusing an offered or
   impending thing is `Rejection`. `ayaw ko rin`, said to **agree**
   with another speaker's `ang dilim ng kwartong ito, ayaw ko`, is
   `Denial`: it affirms that [gusto ko ito] is false; nothing is offered or
   refused. But `ayaw ko` said while **resisting an item in an active
   exchange** — especially when the child then counter-proposes (`gusto ko ng
   X`) — is `Rejection`: the dislike statement is the move by which the child
   refuses. Alignment with an evaluation => `Denial`; resistance within a
   negotiation => `Rejection`.
3. A statement that **functions as a request or proposal is a request, not an
   assertion**. Caregivers often propose actions by stating the child's
   expected behavior and seeking compliance, frequently with a confirmation
   tag: `akala ko ilalagay mo ang sapatos mo sa tabi ng pinto, okay?`.
   A `hindi` to such an utterance refuses the proposed action => `Rejection`,
   not Denial of a proposition about the child's plans. Uptake usually
   confirms it: a caregiver who answers the `hindi` by pleading or re-asking
   heard a refusal.

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

### Negative imperatives (`huwag`/`wag` + verb, e.g. `wag mong itapon`)

Tagalog negative commands use `huwag` (usually `wag` in speech) before the
verb (`wag mong itapon`, `wag kang tumalon`); rules and norms are often stated
with `bawal` ("not allowed") or negated declaratives.

- Stopping or preventing a **specific action by a specific person** (ongoing,
  imminent, or anticipated) => `Rejection`. Example: `wag mong itapon, Ana`
  said as the sister picks up a too-full cup => `Rejection`.
- Stating a **general rule or norm**, typically echoing a rule just discussed
  => `Denial` (the child asserts that one does not do that). Cue: the
  addressee replies with agreement (`oo`, `tama`) rather than by
  stopping an action. Example: after the caregiver says `bawal tumalon sa
  sofa`, the child says `wag tumalon sa sofa, Tatay` and the caregiver
  answers `oo, tama` => `Denial`.

### Uncoded vs Excluded

`Uncoded` is a **last resort**, not a safe harbor. Before using it, ask
whether the surrounding **activity** determines the function even though the
single turn is fragmentary: in an ongoing food negotiation, toy struggle, or
compliance dispute, a bare or garbled negation by the child is usually a move
in that activity (most often `Rejection`), and coders commit to a label. Use
`Uncoded` only when, after weighing the activity context and uptake,
competing interpretations genuinely remain unresolved - and when you can
commit to a best label but doubts remain, report `certain` = `No` instead of
retreating to `Uncoded`.

This includes largely unintelligible utterances: transcripts mark
unintelligible speech as `xxx` and untranscribed speech as `www`. If the
target utterance is mostly `xxx` but the negator is plainly a real negation
whose function cannot be recovered even from the activity context, use
`Uncoded`.

Use `Excluded` only when the token should not be analyzed as a negation act at
all, and only together with the licensing flag: `singing`, `mimicry`, or
`not_a_negation` set to `Yes`. Never use `Excluded` for a real negation that
is merely ambiguous or unintelligible - that is `Uncoded`.

## Flag Rules

`foreign_language_negation`: Mark `Yes` if the target negator is from a
language other than Tagalog (for example an English `no`, `not`, or `don't` in
a code-switched utterance — common in this corpus — or a Bisaya `dili`). Do
not automatically exclude; code the Bloom label normally if the use is
interpretable.

`singing`: Mark `Yes` if the target negator is in song lyrics or sung material.
If `Yes`, set `bloom_label` to `Excluded`.

`mimicry`: Mark `Yes` if the child exactly repeats something another speaker
just said and appears to be simply imitating rather than conveying a new
communicative act. If `Yes`, set `bloom_label` to `Excluded`. Transcripts often mark imitation explicitly on the child's line (`[+ IMIT]`, `[+ IMI]`, `[=! imitates]`): treat a target line carrying such a marker as mimicry unless context clearly shows the child is doing more than echoing. An exact echo of the immediately preceding adult turn with nothing added is mimicry even without a marker.

`tag_question`: Mark `Yes` only if the target negator is inside a tag question,
such as the `di` in `gusto mo ng pasta, di ba?` or the `hindi` in `..., hindi
ba?`. Do not mark `Yes` for ordinary negation followed by a positive tag, such
as `ayaw mo ng pasta, ano?`. Do not automatically exclude tag questions.

`repetition`: Mark `Yes` if the target negator is lexically the same as the
previous coded negator token and the prejacent/meaning is the same. Each
negator token is its own record, so this applies **within one utterance** too:
for `ayaw ayaw ayaw`, the first `ayaw` is `No` for repetition and the later
identical tokens are `Yes`; for `hindi xxx hindi xxx`, the second `hindi` is
`Yes`. Every record states which token it is: `negator_index_in_utterance` is
the 1-based position of this record among the utterance's negator tokens, and
`negators_in_utterance` is the total. When `negator_index_in_utterance` is 2
or more and the negator is lexically and semantically identical to the
previous token of that utterance, mark `repetition` as `Yes` and give it the
**same** `bloom_label` as the first token. The rule also applies **across
lines** when the child repeats their own previous line with the same negator
and the same prejacent (transcripts often mark these `[+ SR]`,
self-repetition): flag the repeated line's negator `Yes` and keep the same
label. Do not mark repetition when adjacent negators have different meanings,
as in `hindi, ayaw ko` (two records: `hindi` is token 1 of 2, `ayaw` is token
2 of 2, but they negate different prejacents, so neither is flagged).

`not_a_negation`: Mark `Yes` if the target string was flagged as a negator but
is not functioning as negation in context, such as `di` matched inside a larger
word like `dito` or `diyan`, `wag` inside `tawag` ("call"), or a negator-like
string inside child babble. If `Yes`, set `bloom_label` to `Excluded`.


When judging `not_a_negation`, check the known false-positive readings
section above; those patterns are the most common source of
`not_a_negation` = `Yes`.

## Decide First, Then Write

Reach your final label decision before writing any JSON. For every record,
identify the specific context line(s) - a quoted fragment or line number -
that determined your label. If you cannot point to any deciding evidence,
reconsider the label, and consider whether `certain` should be `No`. At the
**end of your reasoning, immediately before the output, restate the final
label for every record_id in the batch** (one short line each, naming the
deciding evidence), then write the JSON and copy those labels exactly. In
each output object, write `comments` first - one short sentence giving the
contextual reason, citing the deciding line or fragment - then write
`bloom_label`, which must be exactly the label your comment justifies, then
`certain`. Do not change your decision while writing the output. If you
notice your reason supports a different label, re-decide, update your
restated list, then write a reason and label that agree.

## Output Contract

Return exactly this JSON shape (note the key order: `comments` before
`bloom_label`, then `certain`, then `flags`):

```json
{
  "schema_version": "bloom_v4",
  "predictions": [
    {
      "record_id": "tgm_000000",
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

Context: Caregiver opens fridge, expected milk is gone. Child says: `wala nang
gatas.`
Target: `wala`

Prediction: `Nonexistence`; all flags `No`.
Reason: expected referent is absent.

Example B:

Context: Caregiver offers peas. Child says: `ayaw!`
Target: `ayaw`

Prediction: `Rejection`; all flags `No`.
Reason: child rejects offered item/action.

Example C:

Context: Caregiver says `kamatis ito` while holding a banana. Child says:
`hindi.`
Target: `hindi`

Prediction: `Denial`; all flags `No`.
Reason: child denies truth of prior proposition.

Example D:

Context: Child checks pockets and says: `wala akong stickers.`
Target: `wala`

Prediction: `Nonpossession`; all flags `No`.
Reason: main meaning is lack of possession.

Example E:

Context: Caregiver says `sabihin mo, "hindi, ayaw ko."` Child echoes exactly:
`hindi, ayaw ko.`
Target: `hindi`

Prediction: `Excluded`; `mimicry` is `Yes`; other flags `No`.
Reason: direct imitation without clear new communicative act.

Example F:

Context: Auto-search flagged `di` inside `pumunta ka dito.`
Target: `di`

Prediction: `Excluded`; `not_a_negation` is `Yes`; other flags `No`.
Reason: target string is part of a larger word (`dito`), not functioning as
negation.

Example G:

Context: Child says `ayaw ayaw ayaw` as a refusal. Current target is the second
`ayaw` (`negator_index_in_utterance` 2, `negators_in_utterance` 3).
Target: `ayaw`

Prediction: `Rejection`; `repetition` is `Yes`; other flags `No`.
Reason: same negator and same meaning as immediately previous coded token.

Example H:

Context: Sibling says `gusto niya ng carrots.` Child says: `hindi.`
Target: `hindi`

Prediction: `Denial`; all flags `No`.
Reason: denies a claim about the child; nothing was offered, so not Rejection.

Example I:

Context: Caregiver says `ang dilim ng kwartong ito, ayaw ko.` Child says:
`ayaw ko rin.`
Target: `ayaw`

Prediction: `Denial`; all flags `No`.
Reason: agrees with an evaluative statement by affirming a negative
proposition; nothing offered or refused.

Example J:

Context: Sister picks up a very full cup. Child says: `wag mong itapon, Ana.`
Target: `wag`

Prediction: `Rejection`; all flags `No`.
Reason: negative imperative preventing a specific anticipated action by a
specific person.

Example K:

Context: Caregiver just said `bawal tumalon sa sofa.` Child says: `wag tumalon
sa sofa, Tatay.` Caregiver answers: `oo, tama.`
Target: `wag`

Prediction: `Denial`; all flags `No`.
Reason: child restates the rule; the agreement response shows it asserts a
norm rather than stopping an action.

Example L:

Context: Child shouts `hindi xxx hindi xxx!` Most of the utterance is
unintelligible, but the `hindi` is a real negation. Current target is the first
`hindi` (`negator_index_in_utterance` 1, `negators_in_utterance` 2).
Target: `hindi`

Prediction: `Uncoded`; all flags `No`.
Reason: genuine negation whose function cannot be recovered from context;
ambiguity is Uncoded, never Excluded.

Example M:

Context: Same utterance `hindi xxx hindi xxx!` Current target is the second
`hindi` (`negator_index_in_utterance` 2, `negators_in_utterance` 2).
Target: `hindi`

Prediction: `Uncoded`; `repetition` is `Yes`; other flags `No`.
Reason: second identical negator in the same utterance; repetition flag plus
the same label as the first token.

Example N:

Context: Caregiver: `akala ko ilalagay mo ang sapatos mo sa tabi ng pinto,
okay?` Child: `hindi.` Caregiver: `sige na? bago tayo umalis?`
Target: `hindi`

Prediction: `Rejection`; all flags `No`.
Reason: the caregiver's statement functions as a proposal, and the pleading
uptake shows she heard a refusal - not a denial of a claim about the child's
plans.

Example O:

Context: Caregiver hands the child the green cup. Child: `ayaw ko ng basong
ito.` Child next turn: `gusto ko ng pulang baso.`
Target: `ayaw`

Prediction: `Rejection`; all flags `No`.
Reason: resisting an item in an active exchange, confirmed by the
counter-proposal; contrast with Example I, where the child aligns with another
speaker's evaluation.

Example P:

Context: Sibling: `umuulan sa labas.` Child: `hindi.` Caregiver: `umuulan nga,
tingnan mo!`
Target: `hindi`

Prediction: `Denial`; all flags `No`.
Reason: the re-asserting uptake shows the family heard a truth dispute, not a
refusal.

Example Q:

Context: Child said `wag mong itapon, Ana` (coded Rejection). Two lines later
the child repeats: `wag mong itapon.` (marked `[+ SR]`).
Target: `wag`

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
