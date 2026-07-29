# Bloom v5 Hebrew Negation Coding — Condensed Prompt

Prompt version family: `p005c-he-engex`. Policy and output schema remain `bloom_v5`.
This is a shorter experimental rendering of the same policy, designed to test
whether a compact decision procedure improves model compliance.

## Task

Code each target negator in a Hebrew child-caregiver transcript. Use the
target utterance and both context windows. Each input record is one target
occurrence; use `negator_index_in_utterance` when an utterance contains more
than one negator.

Return only the schema-conforming JSON object. Include exactly one prediction
for every input `record_id`; never omit, duplicate, or invent an ID.

Allowed labels:

- `Nonpossession`
- `Nonexistence`
- `Rejection`
- `Denial`
- `Uncoded`
- `Excluded`

`certain` is `Yes` only when no second label is seriously plausible. Otherwise
choose the best label and use `No`. Uncertainty is not a reason to use
`Uncoded`.

## Decision procedure — apply in this order

### 1. Align the target

Interpret the indexed target occurrence, not a nearby negator. Reconstruct
imperfect child speech from CHAT annotations and discourse context. A
misspelling or incomplete production is not automatically `not_a_negation`.

### 2. Run the exclusion preflight

Use `Excluded` only when one of these licensing flags is `Yes`:

- `singing`: the target is in singing or song lyrics;
- `mimicry`: the target line has an imitation marker or is an exact,
  contentless echo of the immediately preceding adult line;
- `not_a_negation`: the indexed string is not functioning as negation.

Run the locale-specific ambiguity checks below before assigning a semantic label. Do not assign the semantic label that a lyric or imitation would have received as an independent child assertion.

## Hebrew locale appendix

- The Hebrew transcripts are romanized and may contain CHILDES markers,
  phonetic symbols, gloss-style repairs, and partial words. Treat variants
  such as `lo`/`loh` and `eyn`/`en`/`ein` as contextual spellings, not
  different Bloom functions.
- Frequent targets include `lo`, `eyn`/`en`/`ein`, negative-imperative `al`,
  `af`, `day`/`dai`, `bli`, `klum`, `shum`, `nigmar`, `maspiq`, and
  `tafsiq`/`tafsiqi`.
- Check homography before coding: `lo` may be the dative “to him” or occur
  inside `shelo`; `al` may mean “on/about”; `af` may mean “nose”; and
  `dai`/`maspik` may be nonnegative counting or praise.
- `eyn X`/`klum`/`nigmar` often marks absence, while `eyn li X` or `bli X`
  may mark nonpossession. `al` plus a verb and directed `day`/`tafsiq`/
  `maspiq` can reject or stop a specific action.

If the target is a real negation, continue. Do not use `Excluded` merely
because its meaning is ambiguous.

### 3. Check the dedicated labels

1. `Nonpossession`: the core meaning is that someone does not have, own, or
   possess something. A negative answer to `do you have X?` belongs here.
2. `Nonexistence`: an expected entity is absent, missing, not present, gone,
   finished, empty, or used up. `None left` and `no more` qualify even when the
   entity is implicit. Failed action, inability, fit, or malfunction does not.

These labels take priority over ordinary factual `Denial`.

### 4. Decide Rejection versus Denial from the live move

Do not classify from sentence shape alone. Identify:

1. the literal negative proposition; and
2. what the child is doing with it in this exchange.

Use `Rejection` when the negation is the child's move for:

- refusing an offered thing;
- rejecting a proposal, request, permission, choice, turn, or placement;
- resisting a directive;
- blocking, stopping, or replacing an actual, imminent, or anticipated action.

A location, preference, intention, future statement, or inability claim can be
`Rejection` when it is how the child opposes a concrete course of action
currently in play. Counter-proposals, bargaining, pleading, re-offering,
coaxing, or insisting are strong evidence of Rejection.

Use `Denial` when the negation makes or supports a truth claim after
Nonpossession, Nonexistence, and Rejection have been ruled out. This includes:

- contradicting or correcting an assertion;
- answering a genuinely information-seeking factual question;
- reporting inability, failed action, fit, malfunction, property, or state
  when no directive is being resisted;
- agreeing with a negative evaluation or restating a general rule.

For questions, classify the question's conversational move:

- offer/proposal/request/permission/compliance question + negative answer
  → `Rejection`;
- information question about a fact + negative answer → `Denial`;
- possession question + negative answer → `Nonpossession`;
- existence/availability question + negative answer → `Nonexistence`.

Do not infer Rejection merely because an activity is occurring. A specific
thing or action must be accepted, blocked, stopped, or replaced. Conversely,
do not call a live refusal Denial merely because its words can be paraphrased
as a false proposition.

### 5. Use Uncoded only as the last resort

Use `Uncoded` only when the token is a real negation but its communicative
function remains unrecoverable from construction, activity, preceding
question, and participant uptake. A missing referent is not enough. If one
label is best but another remains plausible, choose the best label and set
`certain` to `No`.

## Other flags

All six flags are required and use `Yes` or `No`.

- `foreign_language_negation`: target negation is in a language other than
  the transcript's coding language; do not automatically exclude an
  interpretable use.
- `singing`, `mimicry`, `not_a_negation`: defined in the exclusion preflight.
- `tag_question`: the indexed negator is inside a negative tag such as
  `isn't it?`; do not automatically exclude tag questions.
- `repetition`: the target repeats the same negator with the same meaning as
  the preceding coded occurrence, including clear self-repetition across
  lines. Repetition changes the flag, not the semantic label.

## Calibration examples

1. Caregiver: `Do you have crayons?` Child: `No.`  
   → `Nonpossession`.

2. Child searches an empty box: `None left.`  
   → `Nonexistence`.

3. Caregiver offers peas: `Want some?` Child: `No.`  
   → `Rejection`; the question is an offer.

4. Caregiver asks: `Is the soup hot?` Child: `No.`  
   → `Denial`; the question seeks a fact.

5. Caregiver starts placing a puzzle piece: `This goes here.` Child moves it
   and says: `Not there—here.`  
   → `Rejection`; the live move vetoes and replaces a proposed placement.

6. Caregiver: `Put your boots on.` Child: `I can't.` Caregiver: `Come on,
   try.`  
   → `Rejection`; the inability claim resists a directive.

7. Child tries a puzzle piece and says: `It doesn't fit.` Caregiver: `Turn it
   around.`  
   → `Denial`; it reports fit, and no directive was being resisted.

8. Adult: `He likes carrots.` Child: `No.` Adult: `Yes he does.`  
   → `Denial`; the exchange disputes truth, not an offered carrot.

9. Adult sings a line containing `can't`; transcript marks `[=! sings]`.  
   → `Excluded`, with `singing` = `Yes`.

## Output discipline

For each record, reason from the immediately relevant context and participant
uptake. In `comments`, cite the short fragment or line that decided the label
and say whether a concrete thing/action was being blocked when Rejection is
possible. Keep comments under 300 characters.

Before emitting JSON, verify:

- every input ID appears exactly once;
- the label follows the ordered procedure above;
- `comments`, `bloom_label`, `certain`, and all six flags are present;
- `Excluded` has `singing`, `mimicry`, or `not_a_negation` = `Yes`;
- uncertainty is expressed with `certain` = `No`, not a reflexive `Uncoded`.
