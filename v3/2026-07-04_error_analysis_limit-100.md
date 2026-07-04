# v3 limit-100 error analysis (all languages, all models)

Date: 2026-07-04.
Scope: every `llm-human-audit_*_limit-100.csv` in `v3/results/` — gemma4:31b,
qwen3:32b, llama3.3:70b × English/German/Hebrew/Spanish/Tagalog × loc/engex
prompt variants (24 runs). "Error" = LLM label differs from the collapsed
label on rows where **both human coders agree** (consensus rows only;
single-coder rows tabulated separately). This analysis feeds the v4
prompt/policy revision.

Contamination note: every distinct error record read for this analysis
(30 en, 42 de, 43 es, 28 he, 15 tl) was appended to
`splits/<language>/inspected_rows.txt` on 2026-07-04 (the German, Hebrew,
Spanish, and Tagalog lists were created for this purpose). These rows are
development data from now on.

## Headline numbers (accuracy on consensus rows)

| lang | consensus N | gemma4 | qwen3 | llama3.3 |
|---|---|---|---|---|
| en (loc) | 79 | 82.3 | 77.2 | 79.7 |
| de (loc/engex) | 58 | 65.5 / 69.0 | 48.3 / 62.1 | 69.0 / 67.2 |
| es (loc/engex) | 64 | 78.1 / 75.0 | 64.1 / 67.2 | 60.9 / 60.9 |
| he (loc/engex) | 59 | 86.4 / 84.7 | 81.4 / 78.0 | 71.2 / 72.9 |
| tl (loc) | 62 | 79.0 | 88.7 | (failed batches, rerun pending) |

Notes: German is the weakest language for every model. loc vs engex made no
consistent difference (largest gap: qwen3 German, loc 30 errors vs engex 22;
elsewhere ±2 rows), so there is no evidence yet for preferring either example
variant. Of 242 distinct (lang, record, variant) errors, 117 were made by ≥2
models — the majority of error mass is systematic, i.e. prompt-addressable,
not model noise.

Model-level confusion signatures (consensus rows, all languages pooled):

- **gemma4**: rejection→denial 44, rejection→uncoded 19 (over-`Uncoded`).
- **qwen3**: rejection→denial 67 (strong over-`Denial` bias).
- **llama3.3**: denial→rejection 54 (strong over-`Rejection` bias),
  denial/rejection→nonexistence 23, plus shallow comments ("Child refuses or
  resists something") showing little context use.

## Error categories

### 1. Rejection vs Denial on answers to questions and proposals (largest; all languages, all models)

The v3 trap-3 rule covers *statements* that function as proposals, but most
negations in these transcripts answer *questions*, and the models classify by
the surface question rather than by what the question is doing:

- Question is an **offer / proposal / permission / directive probe**
  ("would you like to have your lunch?", "o lo sabes poner tú solo?",
  "das soll Mama Gisela geben?", "willst das mal hier rein tun?") → a negative
  answer refuses → `Rejection`. qwen and gemma call these `Denial` ("denies
  the proposition in the question"). Examples: eng_000633, spa_000486,
  ger_000124, heb_000272.
- Question is **information-seeking about facts** ("están calientes?",
  "no story+time?", "wie das is(t) jetz(t) für meine Katzen?") → a negative
  answer asserts falsity/confirms a negative → `Denial`. llama calls nearly
  every bare "no" a refusal. Examples: spa_000191, eng_000072/73,
  ger_000120/121.
- Child-side want/dislike statements inside an active negotiation
  ("I don't wanna", "nich(t) haben", "die nich(t)") → `Rejection`; models
  drift to `Denial`/`Nonexistence`. Examples: eng_000487, ger_000162/165.
- Normative "one shouldn't" statements deployed to stop eating/handling
  ("no hay que comerlas" + the child's own follow-ups) were coded `Rejection`
  by humans, `Denial` by all six runs (spa_000071/72/74).

v4 suggestion: extend trap 3 from "statements that function as proposals" to
a general **classify the move, not the sentence type** rule: decide what the
negated turn *does* (refuse vs. assert-false), with question-function cues
(offer/directive question vs. fact question) spelled out and two paraphrased
examples per direction. This directly targets qwen's over-Denial and llama's
over-Rejection, which are mirror images of the same missing rule.

### 2. Inability / does-not-fit / failure predicates scatter (all languages)

"no puedo", "no me cabe / no cabo", "I can't eat it now", "I can't get down",
"passt nich(t)", "geht nich(t)", "loʔ ʔadōm"-style corrections during joint
activity. Humans code these `Denial` (assertion that a proposition about
ability/fit/state is false). Models scatter: llama → `Rejection` ("child
refuses"), qwen/llama → `Nonexistence` ("expected fitting is absent").
Examples: spa_000041/42/446/447/451/488, ger_000141/143/160/166/168/172,
eng_000077/481, heb_000434.

Counter-case to preserve: when the negated-ability line is the child's move
to resist a **live directive** (mother: "lagay mo" → child: "hindi kasya",
tgm_000087), humans code `Rejection`. The discriminator is the same uptake
principle already in the prompt: refusal-uptake vs. fact-uptake.

v4 suggestion: explicit rule — negated ability/fit/success predicates are
claims about the world → `Denial` by default; `Rejection` only when the
utterance functions as refusal of a directive just issued to the speaker
(check uptake). Never `Nonexistence` (see 3).

### 3. Nonexistence over-extended to failed actions and predicate negation

`Nonexistence` is being applied whenever "something isn't the case" —
"passt nicht" → "the fitting is absent". qwen/llama do this constantly
(de: denial→nonexistence 12, es: 15).

v4 suggestion: tighten the `Nonexistence` definition — it is about an
**entity** that is absent/gone/used up from the situation, not about actions
that fail or properties that don't hold.

### 4. False-positive negator tokens not excluded (biggest in German and Hebrew; language-specific content)

The candidate-negator search list over-generates, humans respond with
`Excluded` + `not_a_negation`, and the models instead force a Bloom label
(de: excluded→nonexistence 21). The specific traps are language-specific:

- **German**: `alle` (completive "all gone" in "alles alle" — sometimes a
  quantifier, often excluded by coders), `weg` (echo of caregiver "weg is(t)
  er"), `ohne`, affirmative-particle `doch` ("muss(t) du doch Eis
  mitnehm(e)n"), `na` ("na da?"). ger_000108/131/135/144/145/147.
- **Hebrew (romanized)**: homographs — `lo` as the dative pronoun 'to him'
  ("nixnas lo ba-einaym") and inside "shelo" 'his'; `al` as the preposition
  'on' ("al hacipor", "asim... al ze"); `af` as 'nose' ("ʔaf" offered as a
  body-part word). heb_000197/200/201/203/204/294.
- **Spanish**: echo-question "no?" (child querying the adult's "no", not
  negating: spa_000050/70); disfluent `ni` in a repair ("ni [/] niñito",
  spa_000075).
- **English**: `gone` in a where-question ("gone where?", eng_000492).

v4 suggestion: (a) shared rule as an explicit **first step**: before choosing
a function label, decide whether the target token is actually functioning as
negation here — the search list over-generates by design, and `Excluded` +
`not_a_negation` is the correct output for false positives; (b) a short
per-language "known false-positive readings" block (this is the one place a
language-specific prompt difference is necessary — same slot in every prompt,
different content, exactly like the negator inventory already is).

### 5. Imitation/mimicry lines not excluded (English; echo cases elsewhere)

English transcripts mark these lines `[+ IMIT]` and humans exclude them as
mimicry; models code them anyway (eng_000620/621/623/624/625/644; the
adjacent non-IMIT line eng_000626 is real negation — the marker separates
them cleanly). German echo cases (child repeats caregiver's "weg is(t) er")
pattern with category 4.

v4 suggestion: mechanical rule — a target line marked `[+ IMIT]`, or an exact
echo of the immediately preceding adult turn with no added content, is
mimicry → `Excluded` + `mimicry` flag. (Mirror of the existing `[+ SR]`
repetition rule, which models apply well.)

### 6. gemma-specific: `Uncoded` overused on fragmented child speech

gemma retreats to `Uncoded` where humans commit (19 rejection→uncoded;
ger_000101/134/139, eng_000634/635/645/650). Humans use the surrounding
*activity* frame (ongoing food negotiation, toy struggle) to license a label
even when individual turns are fragmentary.

v4 suggestion: strengthen the `Uncoded` paragraph — `Uncoded` is a last
resort; before using it, ask whether the surrounding activity (an active
offer/negotiation/dispute) determines the function even if the specific
target of the "no" is unclear.

### 7. llama-specific: context not consulted before labeling

llama's comments are frequently generic ("Child refuses or resists
something", "Child says no to an unknown thing") and it has by far the most
disagreements on single-coder rows (12/14 in Hebrew engex). This is a
process failure, not a rule failure.

v4 suggestion (shared, but aimed at llama): require the `comments` field to
cite the specific context line(s) (line number or quoted fragment) that
determined the label; the "Decide First, Then Write" section already forces a
per-record restatement, so add "with its deciding evidence" there.

## Model-specific prompt format: research conclusion

Question: do gemma4/qwen3/llama3.3 need differently-formatted prompts?

Findings:

- **gemma** has no system role; Ollama's chat template folds the system
  message into the first user turn automatically. Google's guidance is to put
  system-level instructions in the user turn — which is effectively what our
  pipeline does after templating. Markdown-heading structure (what we use) is
  the recommended delimiter style.
- **qwen3** treats the system message as high-leverage (good — the prompt is
  sent as the system message) and supports thinking-mode toggles
  (`/no_think`, `think: false`). Qwen's model card recommends **against
  greedy decoding in thinking mode** (risk of loops/repetition); we run
  temperature 0 with thinking enabled, mitigated by the token cap +
  temperature-bumped retries already in the runner. If qwen runs show
  runaway-thinking retries, the fix is a runner option (disable thinking or
  raise qwen's temperature), not a prompt change.
- **llama3.3** uses a standard system role and Meta's guidance (clear
  instructions, few-shot examples, explicit output constraints) matches the
  current prompt's structure.
- Output-format conformance is a non-issue for all three: Ollama structured
  outputs grammar-constrain the JSON server-side.

Decision: **keep one shared prompt across models.** The chat-template
differences are handled by Ollama; the failure modes that differ by model
(qwen over-Denial, llama over-Rejection, gemma over-Uncoded) are semantic
biases best addressed by the shared rule clarifications above — and keeping
the prompt identical is what makes the three models comparable as coders.
The only per-model knobs worth touching live in the runner/sbatch layer
(qwen thinking mode / temperature), not in the prompt files.

Language-specific deviation: only category 4's per-language false-positive
block (and the existing per-language negator inventories/examples). All rule
text stays shared.

## Priority for v4

1. Category 1 (question/proposal Rejection-vs-Denial rule) — largest error
   mass in every language, hits qwen and llama's dominant confusion cells.
2. Category 4 (false-positive step + per-language trap lists) — largest
   `Excluded` mass; mostly mechanical; German and Hebrew gain the most.
3. Categories 2+3 (ability/fit → Denial; Nonexistence = absent entity).
4. Category 5 ([+ IMIT] → mimicry) — mechanical, English.
5. Categories 6+7 (Uncoded-last-resort; evidence-citing comments).

Falsification per the usual protocol: these rules were mined from the
limit-100 rows now in `inspected_rows.txt`; the v4 run must be judged on the
uninspected remainder of each dev_train split.

Sources for the model-format research:

- https://ai.google.dev/gemma/docs/core/prompt-structure
- https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4
- https://qwen.readthedocs.io/en/latest/getting_started/quickstart.html
- https://huggingface.co/Qwen/Qwen3-4B (thinking-mode + sampling guidance)
- https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_3/
- https://aws.amazon.com/blogs/machine-learning/best-prompting-practices-for-using-meta-llama-3-with-amazon-sagemaker-jumpstart/
