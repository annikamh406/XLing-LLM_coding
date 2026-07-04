# Changes from v3 to v4

Date: 2026-07-04.
Scope: everything that differs between the v3 pipeline (policy `bloom_v3`,
prompt `p003*`, schema `bloom_v3`) and the v4 pipeline (policy `bloom_v4`,
prompts `p004*`/`p004m*`, schema `bloom_v4`), with the motivation for each
change.

Context: v3 was evaluated with limit-100 runs on all five languages with
three models (gemma4:31b, qwen3:32b, llama3.3:70b) and both example variants
(loc/engex). The error analysis is
`v3/2026-07-04_error_analysis_limit-100.md`; of 242 distinct
consensus-disagreement errors, 117 were shared by two or more models, i.e.
most error mass was systematic and prompt-addressable. Model confusion
signatures: qwen over-`Denial` (rejection->denial 67), llama over-`Rejection`
(denial->rejection 54, generic comments), gemma over-`Uncoded`
(rejection->uncoded 19). German was the weakest language, driven by
false-positive candidate negators; Hebrew romanization homographs were the
second-biggest `Excluded` failure. Every error row read for that analysis was
appended to `splits/<language>/inspected_rows.txt` the same day, so v4 must
be judged on the uninspected remainder of each split.

A deliberate scope decision, from the model-format research in the same
document: **one shared prompt across models.** Chat-template differences are
handled by Ollama, structured outputs already pin the JSON, and the per-model
failure modes are semantic biases targeted by the shared rule changes below.
No per-model prompt forks.

## 1. Policy: `Bloom_coding_policy_v3.md` -> `Bloom_coding_policy_v4.md`

| Change | Reason (error category / rows) |
|---|---|
| New **rule 0 / Step 0**: decide whether the target token is a negation at all before assigning a function label; false positives are `Excluded` + `not_a_negation`. | Category 4 of the error analysis. de: excluded->nonexistence 21 (`alle`/`weg`/`ohne`/`doch`/`na`: ger_000108/131/135/144/145/147); he: `lo` dative, `al` preposition, `af` 'nose' (heb_000197/200/201/203/204/294); es: echo `no ?`, disfluent `ni` (spa_000050/070/075); en: `gone where?` (eng_000492). |
| **Nonexistence tightened**: absent/gone/used-up *entity* only; failed actions and non-holding properties are never `Nonexistence`. | Category 3. qwen/llama coded `passt nicht`/`no me cabe` as "the fitting is absent" (ger_000166/168/172, spa_000446/447, heb_000431). |
| New Rejection-vs-Denial rule: **answers to questions — classify the question's move, not its syntax** (offer/proposal/permission/compliance question -> `Rejection`; fact question -> `Denial`), with the two anti-paraphrase warnings stated in both directions. | Category 1 — the largest error mass in every language. Offer-questions coded Denial: eng_000633, spa_000486, ger_000124, heb_000272. Fact-questions coded Rejection: spa_000191, eng_000072/73, ger_000120/121. Directly targets qwen's over-Denial and llama's over-Rejection, which are mirror images of this missing rule. |
| New Rejection-vs-Denial rule: **negated ability/fit/success is a claim about the world** -> `Denial` by default, never `Nonexistence`; `Rejection` only as resistance to a just-issued directive (uptake test). | Category 2. `no puedo`/`no me cabe`/`I can't eat it now`/`passt nicht` -> Denial per humans (spa_000041/42/446/447/451/488, ger_000141/143/160/168, eng_000077/481, heb_000434); counter-case `hindi kasya` resisting a directive -> Rejection (tgm_000087). |
| New note: **normative statements** deployed to stop an ongoing activity -> `Rejection`; detached rule statement met with agreement -> `Denial`. | spa_000071/72/74 (`no hay que comerlas` while stopping the eating), coded Denial by all six erring runs. |
| **`Uncoded` demoted to last resort**: when the surrounding activity (negotiation, toy struggle, compliance dispute) determines the function, commit to the label and put residual doubt in `certain` = `No`. | Category 6, gemma-specific. ger_000101/134/139, eng_000634/635/645/650. |
| **Mimicry flag**: explicit imitation markers (`[+ IMIT]`, `[+ IMI]`, `[=! imitates]`) and exact echoes of the immediately preceding adult turn are mimicry -> `Excluded`. | Category 5. eng_000620/621/623/624/625/644; German echo `weg is(t) er` (ger_000145). Mirrors the `[+ SR]` repetition rule, which models already apply well. |
| **Comments must cite the deciding context line**; the end-of-reasoning restatement now names the deciding evidence per record. | Category 7, llama-specific process failure ("Child refuses or resists something" comments with no context use; 12/14 single-coder disagreements in Hebrew engex). Shared change that mostly disciplines llama. |
| New required field **`certain`** (`Yes`/`No`), emitted after `bloom_label`. | User request 2026-07-04. Yes/No rather than a percentage for two reasons: (a) it mirrors the human coders' `certain_bloom` yes/no column, so LLM-vs-human certainty is directly comparable; (b) verbalized numeric confidences from LLMs are poorly calibrated and cluster in a narrow band, while a binary forced choice is the same instrument the humans used. Guardrails written into policy and prompts: `certain` never substitutes for choosing one best label, and uncertainty goes into `certain` = `No`, not into `Uncoded`. |
| Policy title/scope now **multilingual**; per-language content is confined to negator inventories, false-positive readings, and examples. | The policy was English-titled but is the canonical rules document for all five languages since the 2026-06-25 split generalization. |
| New policy appendix: **masked-negator variant** (see section 5). | User request 2026-07-04. |

## 2. Prompts: `p003*` -> `p004*` (nine files, generated)

The nine v4 prompts are generated from their v3 counterparts by
`v4/make_v4_prompts.py` — each edit is anchored and asserted to match exactly
once per file, so the nine files cannot silently diverge. Edits, mirroring
the policy changes above:

1. Version strings and cross-references bumped (`p003*` -> `p004*`,
   `bloom_v3` -> `bloom_v4`).
2. Task instruction adds the `certain` judgment; Allowed Output Labels
   defines it.
3. Step 0 (is it a negation at all?) inserted into the coding rules.
4. Nonexistence definition tightened (entity absence only).
5. New per-language section **"Known false-positive readings"** — the one
   deliberately language-specific rule addition (German `alle`/`doch`/`weg`/
   `fertig`/`ohne`/`na`; Hebrew `lo`-dative/`al`-preposition/`af`-nose;
   Spanish echo-`no ?`/disfluent `ni`; English in-word `no`/locative `gone`;
   Tagalog `di`/frozen `wala` phrases/sound-play). Existing per-language
   negator-notes sections got a cross-reference to it, since some of their
   "often Nonexistence" tendencies (`weg`, `alle`, `fertig`) were feeding
   category-4 errors.
6. "Three traps" becomes **"Five traps"**: trap 4 = question-move
   classification; trap 5 = ability/fit; plus the normative-statement
   contrast.
7. Uncoded-vs-Excluded section replaced with the last-resort version.
8. Mimicry flag rule extended with the imitation markers; not_a_negation
   rule cross-references the false-positive section.
9. Decide First, Then Write requires citing deciding evidence and covers
   `certain`.
10. Output contract adds `certain` after `bloom_label` (key order is
    meaningful under constrained decoding: reason -> label -> confidence).
11. Six new worked examples **R–W** (offer-question -> Rejection;
    fact-question -> Denial; doesn't-fit -> Denial; inability-as-resistance
    -> Rejection; `[+ IMIT]` -> Excluded/mimicry; garbled-but-committed
    Rejection with `certain` = `No`). All are structure-preserving
    paraphrases; provenance: R <- eng_000633/spa_000486, S <-
    spa_000191/eng_000072-73, T <- spa_000446/ger_000168, U <- tgm_000087,
    V <- eng_000621/623-625, W <- ger_000134/eng_000645.

Two deliberate design notes:

- **Shared rule text.** The new rule text (traps 4–5, Step 0 preamble,
  Uncoded section, examples R–W) is identical English in all nine files,
  including the loc variants whose older examples are localized. The v3
  loc-vs-engex comparison showed no consistent difference, so no
  translations were commissioned for v4; if loc examples earn their keep in
  the v4 runs, R–W can be localized in a later version.
- The v3 files are untouched and remain reproducible.

## 3. Schema: `bloom_v3_output.schema.json` -> `bloom_v4_output.schema.json`

- `schema_version` const -> `bloom_v4`.
- New required per-prediction key `certain` (`Yes`/`No`), ordered after
  `bloom_label`.
- `record_id` pattern generalized from `^eng_[0-9]{6}$` to
  `^(eng|ger|heb|spa|tgm|tgn)_[0-9]{6}$` (the v3 file predated the
  multilingual splits; the runtime per-batch schema always enumerated exact
  IDs, so this only affects the canonical document).

## 4. Runner: `scripts/run_bloom_coding.py`

- Defaults bumped: schema `bloom_v4`, prompt version `p004`, prompt
  `v4/bloom_v4_english_prompt.md`, results dir `v4/results/` (lockbox runs
  still auto-route to `results/lockbox/`).
- `certain` is validated and grammar-enforced (added to the per-batch
  structured-outputs schema between `bloom_label` and `flags`), **gated on
  schema version**: `schema_has_certain()` returns False for
  `bloom_v1/v2/v3`, so reproductions of older runs validate against their
  original contract (verified: v4 output missing `certain` is rejected; v3
  output containing `certain` is rejected).
- No other behavior changes; v1–v3 remain reproducible via
  `--prompt/--schema-version/--prompt-version/--results-dir`.

## 5. Masked-negator variant (new)

Purpose: measure how much of the coding signal comes from discourse context
versus the negator lexeme itself.

**Input construction** (`scripts/build_masked_splits.py`, run 2026-07-04 for
all five languages -> `splits/<language>_masked/`):

- **Pre-filter**: any record where *either* human coder marked
  `not_a_negation` = Yes, `repetition` = Yes, or
  `foreign_language_negation` = Yes is dropped before prompting — all three
  judgments require seeing the token, so the masked model cannot be asked to
  make them (user decisions 2026-07-04; the foreign-language flag was added
  after review of the first masked-prompt draft). Drop rates on dev_train:
  en 200/1521, de 106/1502, he 187/963, es 209/1478, tl 50/323.
- **Masking**: `target_negator` -> `[MASKED]`; every occurrence of that
  negator in `target_utterance` -> `[MASKED]`. All occurrences are masked so
  an unmasked copy of the same word cannot leak the masked one; only the
  record's own negator lexeme is masked, so a *different* negator in the
  same utterance stays visible (`No, I didn't` with target `no` keeps
  `didn't`). Context lines and every other field are unchanged, per the
  "everything else as is" decision.
- Matching is CHAT-aware: parenthesized elisions (`nich(t)`, `(hin)di`),
  `@`-suffixes, angle-bracket grouping, romanization glottals (`loʔ` -> `lo`)
  and diacritics, `_`-joined multiwords (`all_gone` for `all gone`), and
  `[: correction]` tokens. When the negator sits inside a correction
  (`diba [: hindi ba]?`), the corrected surface token is masked too —
  otherwise the child's rendition leaks the token. Sentence punctuation is
  preserved (`nein.` -> `[MASKED].`).
- Records that still cannot be masked are dropped (an unmaskable record
  would leak its negator) and listed in `masking_manifest.json`. Current
  total: exactly one record corpus-wide (ger_011655, fused
  `deh [: geh]nich(t).`).
- Known residual leak, accepted: phonological fragments/onsets of the
  negator (`&n` before a masked `no`) are not masked.

**Prompts**: `v4/make_masked_prompts.py` derives the nine
`bloom_v4_*_masked.md` variants (prompt versions `p004m*`) from the v4
prompts: a masked-variant instruction block (code from context alone;
examples are shown unmasked as teaching material), forced
`repetition` = `No`, `not_a_negation` = `No`, and
`foreign_language_negation` = `No`, Step 0 skipped, and the batch-input
field note. Schema is unchanged (`bloom_v4`), so the same runner
works:

```
python3 scripts/run_bloom_coding.py --split-dir splits/german_masked \
    --prompt v4/bloom_v4_german_prompt_masked.md --prompt-version p004m-de-loc ...
```

**Evaluation note**: masked-run metrics must be compared against unmasked v4
runs on the *same filtered row set* (the masked splits' record_ids), not
against full-split numbers — the pre-filter removes rows (repetitions,
false positives) that are systematically easier or harder than average.

## 6. Downstream tooling still to update

- The IRR report and audit-CSV builder do not yet read the `certain` field
  from predictions (rows carry it; R scripts select columns by name, so
  nothing breaks, but the calibration comparisons — accuracy on
  `certain` = Yes vs No, and LLM `certain` vs human `certain_bloom` /
  consensus structure — need to be added before the v4 report).
- The multi-model viewer (`scripts/build_coding_viewer.R`) likewise.
- v4 run scripts added 2026-07-04: `scripts/submit_v4_all.sh` submits the
  27-job matrix (3 models x 9 language/example cells; each job runs its
  unmasked + masked arms sequentially on a private Ollama server with a
  job-unique port; llama jobs get 2 GPUs, `OLLAMA_SCHED_SPREAD`, and
  `--num-ctx 16384` per the 2026-07-01 incident). Full-split by default —
  limit-100 would score mostly on inspected rows. The old v3 sbatch scripts
  remain for reproduction only.

## 7. Expectations and what would falsify these changes

Falsification discipline: all rules above were mined from the limit-100
rows now recorded in `splits/*/inspected_rows.txt`. Judge v4 only on rows
outside those lists. Check, in order of importance:

1. **Headline**: clean-subset LLM-human agreement within or above the
   human-human band per language, with German's gap to the other languages
   substantially narrowed (its errors were dominated by categories 1 and 4,
   both directly ruled on).
2. **Confusion cells**: qwen rejection->denial and llama denial->rejection
   shrink markedly; de/he excluded->coded shrinks; nonexistence
   over-assignment (denial->nonexistence) shrinks. If qwen's over-Denial
   persists unchanged, trap 4 failed and likely needs examples in the
   question-answer direction per language.
3. **Uncoded rate** (gemma especially) drops toward human rates without
   accuracy loss on the committed rows; `certain` = No should absorb the
   former Uncoded overflow.
4. **Calibration**: accuracy on `certain` = Yes rows exceeds accuracy on
   `certain` = No rows for every model; if not, the field is decorative and
   should be reconsidered (e.g., dropped or reworded) rather than reported.
5. **Compliance checks**: zero thinking/output contradictions; comments cite
   context lines; no `Excluded` without a licensing flag; `[+ IMIT]` lines
   excluded as mimicry.
6. **Masked arm** (secondary, no pass/fail): masked accuracy quantifies the
   context-only signal; the interesting statistics are the masked-unmasked
   gap per category and language on the shared row set.
