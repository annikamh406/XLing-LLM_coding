# Gemma v4 error analysis: annotated summary by language

Date: 2026-07-23  
Model: `gemma4:31b`  
Primary scope: full, unmasked v4 `dev_train` runs

## Scope and method

This analysis uses only **uninspected** development rows, following the v4
falsification protocol. A model error is counted only when:

1. both human coders supplied a Bloom label;
2. the two human labels agree after the evaluation collapse; and
3. Gemma's collapsed label differs from that agreed-human label.

The evaluation collapse groups `Nonpossession` with `Nonexistence`. Where that
matters, the annotations below name the original human labels.

The primary runs are:

- English: `p004`
- German: `p004-de-engex`
- Hebrew: `p004-he-engex`
- Spanish: `p004-es-engex`
- Tagalog: `p004-tl-engex`

The English-example (`engex`) variant had the highest clean-consensus accuracy
for Gemma in all four non-English languages. The differences from the localized
variant were small, however, and most errors were shared across variants. The
patterns below therefore should not be interpreted as artifacts of the example
language.

Important qualification: “error” here means disagreement with the
agreed-human reference, not an independent adjudication that the reference is
correct. Several examples expose tension between the current v4 policy and the
older human coding. Those are marked **policy/reference tension**.

Contamination-control update: after the statistics were computed, every
specific record cited below was appended to its language's
`inspected_rows.txt`. The tables therefore describe the clean status at the
start of this analysis; future regenerated reports will correctly treat the
cited examples as inspected development material.

## Headline results

| Language | Clean consensus N | Errors | Accuracy | Most frequent error |
|---|---:|---:|---:|---|
| English | 800 | 151 | 81.1% | Rejection → Denial (54) |
| German | 659 | 115 | 82.5% | Rejection → Denial (28) |
| Hebrew | 596 | 83 | 86.1% | Rejection → Denial (36) |
| Spanish | 751 | 119 | 84.2% | Rejection → Denial (47) |
| Tagalog | 182 | 13 | 92.9% | Denial → Rejection and Denial → Excluded (3 each) |
| **Total** | **2,988** | **481** | **83.9%** | **Rejection → Denial (167)** |

### Stability across the localized and English-example variants

| Language | Engex errors | Localized errors | Engex errors also made by localized run | Prediction agreement across all consensus rows |
|---|---:|---:|---:|---:|
| German | 115 | 129 | 105/115 (91.3%) | 93.6% |
| Hebrew | 83 | 87 | 72/83 (86.7%) | 94.6% |
| Spanish | 119 | 127 | 102/119 (85.7%) | 93.6% |
| Tagalog | 13 | 16 | 10/13 (76.9%) | 95.1% |

## Cross-language error signature

| Agreed-human label → Gemma | N | Share of all errors |
|---|---:|---:|
| Rejection → Denial | 167 | 34.7% |
| Denial → Rejection | 64 | 13.3% |
| Rejection → Uncoded | 56 | 11.6% |
| Nonexistence/Nonpossession → Denial | 40 | 8.3% |
| Denial → Uncoded | 30 | 6.2% |
| Denial → Excluded | 26 | 5.4% |
| Excluded → Denial | 24 | 5.0% |
| Other cells | 74 | 15.4% |

Four broad problems account for most of the residual error:

1. **Speech act versus proposition.** Rejection–Denial confusions comprise
   231/481 errors (48.0%). Gemma often treats a refusal, protest, correction
   during joint action, or veto of a placement as a truth-conditional claim.
   It also makes the reverse mistake when a factual or ability claim occurs
   near a directive.
2. **`Uncoded` is still a retreat option.** Gemma maps 94 genuine content
   labels to `Uncoded` (56 Rejections, 30 Denials, and 8
   Nonexistence/Nonpossession cases). Its comments often explicitly say that
   the surrounding activity is visible but the exact prejacent is unclear.
3. **Existence and possession are treated as ordinary Denial.** Forty
   agreed-human Nonexistence/Nonpossession cases become Denial. This is
   especially visible with Spanish `no está`/`no tiene`, German possession
   questions, Hebrew `ʔeyn`, and Tagalog `wala`.
4. **The analysis boundary is unstable in both directions.** Gemma assigns a
   content label to 42 agreed-human `Excluded` rows, but also maps 50 agreed
   content rows to `Excluded`. Some are genuine model failures (missed
   singing, mimicry, or homographs); others reveal policy/reference
   inconsistencies.

Gemma's binary certainty is directionally useful but does not catch most
errors. Accuracy is lower on `certain = No` rows in every language, but
378/481 errors (78.6%) were nevertheless marked `certain = Yes`.

## English

### Error profile

- Rejection → Denial: 54
- Denial → Rejection: 23
- Content label → Uncoded: 34
- Nonexistence/Nonpossession → Denial: 9
- Agreed-human Excluded → content label: 13
  - eight missed mimicry cases;
  - four missed `not_a_negation` cases;
  - one missed singing case.

### Annotated examples

**`eng_000449`: “Mom, I am not going [to] eat.”**  
Reference: Rejection. Gemma: Denial.

The child is announcing noncompliance in an active eating conflict. Gemma
describes the line as “a claim about their own future action/intent,” allowing
the declarative syntax to override its refusal function. This is the central
English Rejection → Denial pattern.

**`eng_001513`: “why not?” after “you don't turn anything.”**  
Reference: Rejection. Gemma: Denial.

The child's question challenges or resists the prohibition. Gemma instead
treats the request for justification as a Denial. Three adjacent `why not?`
tokens receive the same mistaken label, showing that a single discourse error
can produce several token-level errors.

**`eng_004258`: “no” after “is there [a pencil] in the kitchen?”**  
Reference: Nonexistence. Gemma: Denial.

Gemma correctly understands that the child says the pencil is not there, but
then calls that an ordinary factual Denial. The error is label selection, not
failure to understand the discourse.

**`eng_003819`: “they don't fit,” immediately after the adult says “they
don't fit.”**  
Reference: Excluded + mimicry. Gemma: Denial.

This is a direct miss of the v4 exact-echo rule. Gemma's comment itself says
that the child repeats the adult's statement, but it neither sets `mimicry`
nor uses `Excluded`.

**`eng_002267`: “gone store.”**  
Reference: Excluded + `not_a_negation`. Gemma: Nonexistence.

Here `gone` is the ordinary motion/resultative predicate in “gone [to the]
store,” not a child negation marker. Gemma infers Nana's absence and forces a
Bloom function onto a false-positive candidate. Two following `gone` rows in
the same exchange are also misclassified.

**`eng_004223`: “can't you hear … shouting” in song lyrics.**  
Reference: Excluded + singing. Gemma: Denial.

Gemma analyzes the lyric's propositional content and misses the transcript's
song context.

**`eng_004229`: “I can't” after “well, you try.”**  
Reference: Denial. Gemma: Rejection.

Gemma says the inability claim resists the mother's directive. That rationale
is licensed by the current v4 exception for ability statements used as
resistance. This is therefore a **policy/reference tension**, not a clean
prompt-comprehension failure. The same issue recurs in `eng_000945` and
`eng_004230`.

**`eng_000683`: “no” after “do you see these pictures?”**  
Reference: Denial. Gemma: Uncoded.

Gemma identifies the factual question but retreats because the following
adult-child sequence of `no`s resembles a game. This illustrates that the
“Uncoded as last resort” rule has not fully displaced Gemma's v3 behavior.

### English diagnosis

The main English prompt-addressable problem is not lack of context. Gemma's
comments usually identify the relevant context correctly, but it converts
refusal-like intentions into propositions and existence/possession into
Denial. Mechanical misses of mimicry, locative `gone`, and singing remain.
Ability-after-directive cases should be adjudicated before they are used to
change the prompt.

## German

### Error profile

- Rejection → Denial: 28
- Denial → Rejection: 18
- Content label → Uncoded: 27
- Nonexistence/Nonpossession → Denial: 9
- Nonexistence → Excluded: 8
- Agreed-human Excluded → content label: 6
- Agreed content → Excluded: 24

German also has the lowest human-human agreement structure of the five
languages: only 659 of 1,049 clean double-coded rows have collapsed-label
agreement. The Gemma error set therefore sits inside a relatively difficult
and reference-ambiguous corpus.

### Annotated examples

**`ger_003220`: “ne, nein, so nicht!” (“no, not like that!”) after the
mother proposes a way of lying something down.**  
Reference: Rejection. Gemma: Denial.

Gemma sees a correction of the mother's proposition; the human coding treats
the child's turn as vetoing the proposed action. This is a prototypical
speech-act-versus-proposition boundary case.

**`ger_004646`: “ne” after “we're already finished eating.”**  
Reference: Rejection. Gemma: Denial.

Gemma treats the child's response as contradicting the claim that eating is
finished. The human label treats the turn as resistance within the ongoing
meal. Again, the same semantic content supports two analyses; activity and
uptake determine the project label.

**`ger_003214`–`ger_003218`: “nich … nich … ne … nein … ne” during playful
interaction.**  
Reference: Rejection for all five tokens. Gemma: Uncoded.

Gemma notices play, laughter, and fragmentary form but does not use the
activity frame to commit. One unresolved turn creates five errors, so raw
token counts overstate the number of distinct discourse failures.

**`ger_008425`: “nein” after “do you also have a tricycle?”**  
Reference: Nonpossession for both humans. Gemma: Denial.

This is a clear dedicated-label miss. Gemma accurately calls it a factual
answer about having something, but fails to select `Nonpossession`.

**`ger_006386`: `doch`.**  
Reference: Excluded. Gemma: Denial.

Gemma interprets `doch` as contradicting an implied negative proposition.
That is linguistically reasonable, but the project's candidate-negator policy
treats affirmative/contradictory `doch` as outside the negation analysis.
This needs a project-specific lexical decision, not more general discourse
reasoning.

**`ger_008631`: “geht nicht” immediately echoing the adult's “das geht
nicht.”**  
Reference: Denial. Gemma: Excluded + mimicry.

Gemma follows the current v4 exact-echo rule. English exact echoes such as
`eng_003819` are indeed coded Excluded by both humans, while this German echo
is coded Denial. This is a strong **policy/reference tension**.

**`ger_009503`: “die Taste weg” (roughly “the key/button away”).**  
Reference: Nonexistence. Gemma: Excluded + `not_a_negation`.

Gemma reads `weg` as a directional/resultative particle; the humans treat the
removed/absent key as Nonexistence. The German false-positive rule and the
human treatment of resultative `weg` are not yet aligned sharply enough.

**`ger_004276`–`ger_004283`: repeated “nein” after “do you want to be a
donkey?”**  
Reference: Denial. Gemma: Rejection.

Gemma treats the question as a proposal and the answer as refusal, exactly as
v4's “classify the question's move” rule encourages. Eight adjacent tokens
are counted as errors. This cluster should be adjudicated before prompting
Gemma away from its current answer.

### German diagnosis

German combines the general Rejection–Denial problem with three
language/reference-specific issues:

1. `doch`, `ne`, `weg`, and uncertain reconstructions such as
   `[=? nichts]` are not consistently separated into genuine negation versus
   false-positive candidate;
2. possession answers are under-assigned to `Nonpossession`; and
3. exact echoes and question-based refusals expose direct tension between the
   current policy and historical labels.

## Hebrew

### Error profile

- Rejection → Denial: 36
- Rejection → Uncoded: 9
- Denial → Rejection: 6
- Agreed-human Excluded → content label: 16
  - 11 have target `lo`;
  - four have target `al` in a sung passage;
  - one has target `af` meaning “nose.”
- Nonexistence/Nonpossession → Denial: 4

### Annotated examples

**`heb_001371`–`heb_001379`: repeated `loʔ lišon` (“not/to sleep”; in
context, “don't sleep”).**  
Reference: Rejection. Gemma: Denial for nine tokens.

Gemma repeatedly glosses the form as a state-of-affairs claim that someone is
not sleeping. The humans treat it as a prohibitive move. This is the single
largest identifiable Hebrew cluster and shows that the infinitival form needs
discourse-sensitive interpretation.

**`heb_000655`: `loʔ betoḳ ha-miṭā šelī` (roughly “not in my bed”) in the
transition to bedtime.**  
Reference: Rejection. Gemma: Denial.

Gemma describes a location claim; the human coding treats the line as
resistance to going to bed. As in English and German, the model understands
the literal content but misses the activity-level function.

**`heb_000310`: bare `loʔ` after the grandmother offers to turn the child's
chair/help her climb.**  
Reference: Rejection. Gemma: Uncoded.

The immediately preceding turn supplies a plausible offer, but Gemma calls the
fragment unresolved. This is a clean failure of the last-resort `Uncoded`
instruction.

**`heb_001774`: `higadeti lo shalom` (“I said hello to him”).**  
Reference: Excluded. Gemma: Denial.

The target `lo` is the dative pronoun “to him,” not the negative `loʔ`.
Gemma translates the sentence as “I did not say hello.” This is a direct
homograph error.

**`heb_003153`: `heviʔu lo harbe moc̣ecim` (“they brought him many
pacifiers”).**  
Reference: Excluded. Gemma: Denial.

The utterance contains a target dative `lo` in a context involving absence and
pacifiers. Gemma lets the discourse topic and possible negative reading
override token-level targeting. This is especially important because a
genuine negative `loʔ` can occur in the same utterance as a dative `lo`.

**`heb_004771`: `ʔaf` while naming body parts.**  
Reference: Excluded. Gemma: Nonexistence.

`ʔaf` means “nose” here. Gemma interprets it as a negative quantifier meaning
“none/not any,” despite the surrounding body-part list.

**`heb_001367`–`heb_001370`: `ʔal tiraʔ` in a sung passage.**  
Reference: Excluded + singing. Gemma: Rejection.

Gemma correctly recognizes a negative imperative (“don't be afraid/look”) but
misses that the child is singing. Four token errors arise from this one
passage.

**`heb_002094`: “no one is sitting on the sofa.”**  
Reference: Nonexistence. Gemma: Denial.

Gemma again understands the proposition but fails to promote referent absence
to `Nonexistence`.

**`heb_001721`: `loʔ` after “are you going to kindergarten tomorrow?”**  
Reference: Denial. Gemma: Rejection.

Gemma interprets the future question as a proposal and the answer as refusal.
The human label treats it as information-seeking. This is a
**policy/reference tension** about how to distinguish plans from proposals.

### Hebrew diagnosis

Hebrew has two unusually crisp language-specific problems:

1. Gemma needs to distinguish romanized homographs at the **target-token**
   level (`lo` negative versus dative, `al` negative imperative versus other
   uses, `af` negative quantifier versus “nose”).
2. `loʔ` plus an infinitive can be a prohibitive/refusal move even though
   Gemma prefers a declarative “not doing” interpretation.

The singing miss is mechanical. Future-plan questions need adjudication
because the proposal-versus-information distinction remains unstable.

## Spanish

### Error profile

- Rejection → Denial: 47
- Rejection → Uncoded: 15
- Denial → Rejection: 14
- Nonexistence/Nonpossession → Denial: 16
- Agreed-human Excluded → content/Uncoded: 7
- Agreed content → Excluded: 17

### Annotated examples

**`spa_001982`: `ahí no` (“not there”) while father and child decide where a
puzzle piece goes.**  
Reference: Rejection. Gemma: Denial.

Gemma treats the line as a factual claim that the piece does not fit there.
The humans treat it as the child's veto of the proposed placement. Several
adjacent `ahí no`/`al revés no` rows receive the same mistaken Denial label.

**`spa_002710`: `no gusta esto, fea` (“I don't like this; [it's] ugly”) while
choosing a book.**  
Reference: Rejection. Gemma: Denial.

Gemma treats dislike as a preference proposition. The human label treats it
as the means by which the child rejects the item in the active exchange.

**`spa_003929`: `Juan no está` (“Juan isn't here”).**  
Reference: Nonexistence for both humans. Gemma: Denial.

The absence is explicit and occurs in a hide-and-seek frame. Gemma's comment
correctly says that Juan is not present but still selects Denial.

**`spa_004302`: `que no tiene esto` (“it doesn't have this”), referring to a
missing toy part.**  
Reference: Nonpossession for both humans. Gemma: Denial.

The model again understands the missing-part relation but does not select the
dedicated possession/existence category.

**`spa_002206`: `no` followed immediately by `aquí` while pointing to a
picture.**  
Reference: Denial. Gemma: Excluded + `not_a_negation`.

Gemma interprets the `no` as a false start before the location answer. This is
plausible and shows that Step 0 can overfire, excluding dysfluent but
human-coded negations. It needs adjudication rather than automatic conversion
into a new counterexample.

**`spa_000637`–`spa_000643`: isolated `no` tokens during fragmentary
child-led play.**  
Reference: Excluded, with no shared licensing flag. Gemma: Uncoded.

Under the written v4 policy, ambiguity alone leads to `Uncoded`, while
`Excluded` requires singing, mimicry, or `not_a_negation`. Gemma's answer is
policy-consistent. These reference rows should not be used to strengthen an
Excluded rule until their intended licensing basis is resolved.

**`spa_002209`–`spa_002210`: `no` after the mother's directive `a tumbarte`
(“lie down”).**  
Reference: Denial. Gemma: Rejection.

Gemma explicitly cites the directive and the mother's surprised uptake. That
is exactly the reasoning v4 requests for Rejection. This is a strong
**policy/reference tension**.

**`spa_005044`: `no viene` immediately echoing the mother's `que no
vienen`.**  
Reference: Denial. Gemma: Excluded + mimicry.

As with German `geht nicht`, Gemma follows the current exact-echo rule but
disagrees with the historical human labels. English echoes are treated
differently by the reference.

### Spanish diagnosis

Spanish errors are dominated by:

1. treating vetoes of placement, choice, or manipulation as factual Denial;
2. failing to reserve `Nonexistence`/`Nonpossession` for `no está`, `no
   están`, and `no tiene` absence constructions; and
3. inconsistent treatment of disfluency and immediate echo between the
   written policy and human reference.

## Tagalog

### Error profile

Only 13 clean-consensus errors occur:

- Denial → Excluded: 3
- Denial → Rejection: 3
- Rejection → Denial: 2
- Nonexistence/Nonpossession → Denial: 2
- Nonexistence → Uncoded: 2
- Rejection → Uncoded: 1

### Annotated examples

**`tgm_000495` and `tgm_000497`: `hindi, laro na ako` (roughly “no, I'm
playing now”) while the mother tells the child to listen and move on.**  
Reference: Rejection. Gemma: Denial.

Gemma says the child denies the mother's description of the scene. The
following turns (“listen,” “we're finished,” “come on”) instead support an
activity-level refusal.

**`tgn_000151` and `tgn_000156`: `nana [: wala na]` (“none left/all gone”).**  
Reference: Nonexistence. Gemma: Uncoded.

Gemma recognizes the form as `wala na` and even glosses it “none left,” but
retreats because the referent is not explicit. The lexical construction
itself supplies the existence function; an unnamed referent should not force
`Uncoded`.

**`tgm_000700`: `baka wala siyang manok` (“maybe she doesn't have a
chicken”).**  
Reference: Nonpossession for both humans. Gemma: Denial.

This is another clear dedicated-label miss: Gemma's comment describes lack of
possession but selects Denial.

**`tgm_000483`–`tgm_000485`: repeated variants of `hindi` after the child
counts in English.**  
Reference: Denial. Gemma: Excluded + `not_a_negation`.

Gemma interprets the sequence as chanting or sound play without a proposition.
The surrounding counting makes that plausible. Three token errors come from
one utterance, and the case should be adjudicated before it becomes a prompt
example.

**`tgm_000089`: `hindi pa` (“not yet”) after “shall I put it in now?”**  
Reference: Denial. Gemma: Rejection.

Gemma treats the answer as refusing the proposed timing. This follows the
current question-move rule, so it is a **policy/reference tension**.

**`tgm_000092`: `huwag diyan` (“don't [do/put it] there”).**  
Reference: Denial. Gemma: Rejection.

Gemma treats the negative imperative as stopping an action. That is also what
the current v4 negative-imperative rule predicts unless the line is a detached
general norm. The row therefore needs adjudication.

### Tagalog diagnosis

Gemma is strongest on unmasked Tagalog. Its few clear problems are failure to
commit to `Nonexistence` for `wala na`, failure to use `Nonpossession` for
`wala` possession, and occasional Rejection → Denial in an active compliance
exchange. Several of the reverse Denial → Rejection errors are likely
policy/reference conflicts rather than model failures.

## What is ready to drive prompt revision

These findings are robust enough to use in the next prompt-design step:

1. Gemma still needs a stronger operational distinction between **literal
   propositional content** and the **move made in the current activity**.
   Its comments often demonstrate literal understanding but the wrong Bloom
   abstraction.
2. `Nonexistence` and especially `Nonpossession` need to remain available
   even when the utterance is a grammatically ordinary negative assertion.
   “It is not here” and “I do not have it” are propositions, but the coding
   scheme assigns them dedicated labels.
3. `Uncoded` remains overused when the negator's construction or the
   surrounding activity supplies the function but the exact referent/prejacent
   is missing.
4. Hebrew needs target-token homograph checks; English/German/Hebrew still
   need more reliable mechanical use of singing and mimicry evidence.
5. A single discourse interpretation can create many token errors through
   within-utterance repetition. Prompt evaluation should therefore track both
   token errors and distinct conversational clusters.

## What should be adjudicated before prompt revision

The following should not be turned directly into new prompt examples:

1. **Ability after a directive:** v4 licenses Rejection when an inability
   claim resists a just-issued directive, but several English consensus rows
   remain Denial.
2. **Questions about plans, wants, and timing:** Gemma's Rejection analysis
   often follows v4, while German, Hebrew, Spanish, and Tagalog human labels
   sometimes remain Denial.
3. **Negative imperatives:** some Spanish and Tagalog human Denial labels
   conflict with v4's action-stopping Rejection rule.
4. **Exact echoes:** English reference rows often use Excluded + mimicry,
   while comparable German and Spanish echoes retain content labels.
5. **Licensing Excluded:** some Spanish and German consensus rows are
   Excluded without a shared singing/mimicry/not-a-negation flag, contrary to
   the written policy.
6. **Resultative/locative forms:** `gone` and German `weg` alternate between
   human Nonexistence and false-positive/not-a-negation treatment in closely
   related uses.

Without adjudication, tightening the prompt around these rows risks teaching
Gemma to reproduce historical inconsistencies rather than the intended v4
policy.

## Secondary masked-run result

The masked arm is not the primary basis for prompt revision, but it helps
separate lexical from discourse signal. On the exact clean-consensus rows
shared by the masked and unmasked datasets:

| Language | Shared N | Unmasked accuracy | Masked accuracy | Masked change |
|---|---:|---:|---:|---:|
| English | 707 | 82.5% | 80.5% | -2.0 pp |
| German | 616 | 82.6% | 80.8% | -1.8 pp |
| Hebrew | 490 | 87.3% | 84.9% | -2.4 pp |
| Spanish | 648 | 84.4% | 81.6% | -2.8 pp |
| Tagalog | 163 | 94.5% | 81.6% | -12.9 pp |

Context alone retains most performance in English, German, Hebrew, and
Spanish. Tagalog is different: removing the negator lexeme sharply degrades
accuracy, consistent with the strong category information carried by `wala`,
`wala na`, `hindi`, and related forms.

## Source artifacts

- `v4/Bloom_coding_policy_v4.md`
- `v4/CHANGES_FROM_V3.md`
- `v4/results/llm-human-audit_dev_train_gemma4_31b_bloom_v4_p004*.csv`
- `v4/results/dev_train_gemma4_31b_bloom_v4_p004*_predictions.jsonl`
- `v4/results/certainty_agreement/certainty_agreement_by_run.csv`
