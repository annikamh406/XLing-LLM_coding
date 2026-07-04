#!/usr/bin/env python3
"""Generate the nine bloom_v4 prompt files from their bloom_v3 counterparts.

One-shot generator, kept for provenance: every v4 prompt is the matching v3
prompt plus the surgical edits below (documented in v4/CHANGES_FROM_V3.md).
Each edit asserts that its anchor matched exactly once per file, so silent
drift between the nine files fails loudly instead of producing skew.

Run from anywhere:  python3 v4/make_v4_prompts.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

V3 = Path(__file__).resolve().parent.parent / "v3"
V4 = Path(__file__).resolve().parent

# file name -> (language, record-id placeholder)
FILES = {
    "bloom_v3_english_prompt.md": ("English", "eng_000000"),
    "bloom_v3_german_prompt.md": ("German", "ger_000000"),
    "bloom_v3_german_prompt_english_examples.md": ("German", "ger_000000"),
    "bloom_v3_hebrew_prompt.md": ("Hebrew", "heb_000000"),
    "bloom_v3_hebrew_prompt_english_examples.md": ("Hebrew", "heb_000000"),
    "bloom_v3_spanish_prompt.md": ("Spanish", "spa_000000"),
    "bloom_v3_spanish_prompt_english_examples.md": ("Spanish", "spa_000000"),
    "bloom_v3_tagalog_prompt.md": ("Tagalog", "tgm_000000"),
    "bloom_v3_tagalog_prompt_english_examples.md": ("Tagalog", "tgm_000000"),
}

ALLOWED_LABELS_SECTION = """## Allowed Output Labels

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

"""

STEP_ZERO = """**Step 0 - is the target token a negation at all?** The candidate list that
flagged the target token over-generates by design: some flagged tokens are
not functioning as negation in their context (see the known false-positive
readings below). Decide this first. If the token is not performing a negation
act here, the answer is `Excluded` with `not_a_negation` = `Yes` - do not
force a Bloom label onto a false positive.

"""

NONEXISTENCE_ADDON = (
    " `Nonexistence` is about an **entity** that is absent, gone, or used up"
    " from the situation - not about actions that fail or properties that do"
    " not hold: `it doesn't fit` and `I can't open it` negate propositions"
    " and are never `Nonexistence`."
)

NOTES_CROSSREF = """
Before applying these tendencies, run Step 0: several of these candidate
forms have common non-negation readings (see the known false-positive
readings below).

"""

FALSE_POSITIVE_SECTIONS = {
    "English": """### Known false-positive readings (English)

Candidate tokens that are frequently not negation in context. Check these
before coding; when the token is not negating here, use `Excluded` +
`not_a_negation`:

- `no` inside another word picked up by string search (for example `know`).
- `gone` in a question about location (`gone where?`) or as a plain verb of
  leaving, rather than marking that an expected thing has disappeared.
- `uh uh` transcribed where it is a hesitation noise, not a refusal.

A real negator inside an imitation line is excluded via the `mimicry` flag,
not `not_a_negation`.

""",
    "German": """### Known false-positive readings (German)

The German candidate list includes several words that are frequently NOT
negation. Check these before coding; when the token is not negating here,
use `Excluded` + `not_a_negation`:

- `alle` as the quantifier 'all/everyone' (`alle raus`, `alles alle` in
  play): only the completive use ('all gone, empty, used up') is a negation
  candidate, and even that is excluded when the child is merely echoing or
  narrating an activity rather than remarking on an absence.
- `doch` as an affirmative or emphatic particle (`musst du doch Eis
  mitnehmen`): `doch` matters for negation only when it contradicts a
  negative ('doch!' = 'yes it is!'), and even then it usually flags the
  *other* speaker's negation, not one by the child.
- `weg` and `fertig` as plain descriptions of movement or completion,
  especially when the child echoes a caregiver's `weg is(t) er`.
- `ohne` ('without') in fragmentary utterances where no negation act is
  performed.
- `na` as a discourse particle (`na da?`), which is not a form of `nein`.

""",
    "Hebrew": """### Known false-positive readings (Hebrew, romanized)

Romanized Hebrew makes several non-negators look like negators. Check these
before coding; when the token is not negating here, use `Excluded` +
`not_a_negation`:

- `lo` as the dative pronoun 'to him' (`yesh lo` 'he has', `nixnas lo
  ba-einayim` 'got into his eyes') and inside `shelo` 'his'. Only `lo`/`loʔ`
  as the negative particle 'no/not' is a negator.
- `al` as the preposition 'on/about' (`al ha-cipor` 'on the bird', `sim al
  ze` 'put it on this'). Only `al` as the negative-imperative particle
  ('don't') is a negator.
- `af` as the noun 'nose' (body-part talk), rather than 'not any/none'.
- `dai`/`maspik` ('enough', 'stop') when used non-negatively, for example
  counting or praising.

""",
    "Spanish": """### Known false-positive readings (Spanish)

Check these before coding; when the token is not negating here, use
`Excluded` + `not_a_negation`:

- `no ?` as an echo question: the child repeats an adult's `no` with rising
  intonation to ask about it. The child is querying the adult's negation,
  not producing one.
- `ni` as a disfluency or repair fragment (`ni [/] niñito`), not the
  negative conjunction `ni ... ni ...`.
- `no` inside quoted, read-aloud, or role-played material where the child
  performs someone else's words (see also the `mimicry` flag).

""",
    "Tagalog": """### Known false-positive readings (Tagalog)

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

""",
}

TRAPS_ADDON = """4. **Answers to questions: classify the question's move, not its syntax.**
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

"""

UNCODED_SECTION = """### Uncoded vs Excluded

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

"""

MIMICRY_ADDON = (
    " Transcripts often mark imitation explicitly on the child's line"
    " (`[+ IMIT]`, `[+ IMI]`, `[=! imitates]`): treat a target line carrying"
    " such a marker as mimicry unless context clearly shows the child is doing"
    " more than echoing. An exact echo of the immediately preceding adult turn"
    " with nothing added is mimicry even without a marker."
)

NAN_CROSSREF = """
When judging `not_a_negation`, check the known false-positive readings
section above; those patterns are the most common source of
`not_a_negation` = `Yes`.

"""

DECIDE_SECTION = """## Decide First, Then Write

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

"""

OUTPUT_CONTRACT = """## Output Contract

Return exactly this JSON shape (note the key order: `comments` before
`bloom_label`, then `certain`, then `flags`):

```json
{
  "schema_version": "bloom_v4",
  "predictions": [
    {
      "record_id": "__RID__",
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

"""

NEW_EXAMPLES = """Example R:

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

"""


def sub_once(pattern: str, repl: str, text: str, name: str, fname: str, flags=0) -> str:
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != 1:
        raise SystemExit(f"{fname}: edit {name!r} matched {n} times (expected 1)")
    return new


def replace_section(text: str, header: str, replacement: str, fname: str) -> str:
    """Replace a whole section (header line through just before the next
    ##/### header) with `replacement` (which must include its own header)."""
    pattern = rf"(?ms)^{re.escape(header)}\n.*?(?=^#{{2,3}} )"
    return sub_once(pattern, replacement.replace("\\", "\\\\"), text, header, fname)


def build(fname: str, language: str, rid: str) -> str:
    text = (V3 / fname).read_text(encoding="utf-8")

    # 1. Version strings and cross-references.
    text = text.replace("# Bloom v3 ", "# Bloom v4 ")
    text = text.replace("`p003", "`p004")
    text = text.replace("v3/Bloom_coding_policy_v3.md", "v4/Bloom_coding_policy_v4.md")
    text = text.replace("v3/bloom_v3_output.schema.json", "v4/bloom_v4_output.schema.json")
    text = text.replace("bloom_v3", "bloom_v4")

    # 2. Task instruction mentions the certainty judgment.
    text = sub_once(
        re.escape("assign one Bloom-style label and six metalinguistic flags"),
        "assign one Bloom-style label, a `certain` judgment, and six\nmetalinguistic flags",
        text,
        "task-instruction certainty",
        fname,
    )

    # 3. Allowed labels section gains `certain`.
    text = replace_section(text, "## Allowed Output Labels", ALLOWED_LABELS_SECTION, fname)

    # 4. Step 0 inserted before the Nonpossession rule.
    text = sub_once(
        r"(?m)^Choose `Nonpossession` when",
        STEP_ZERO + "Choose `Nonpossession` when",
        text,
        "step-0 insertion",
        fname,
    )

    # 5. Nonexistence tightened (entity absence, not failed actions).
    text = sub_once(
        r"(?ms)^(Choose `Nonexistence`.*?\.)\n\n",
        lambda m: m.group(1) + NONEXISTENCE_ADDON + "\n\n",
        text,
        "nonexistence addon",
        fname,
    )

    # 6. Cross-reference at the end of the negator-notes section, if present.
    if f"### {language} negator notes" in text:
        text = sub_once(
            re.escape("Always confirm against context and uptake before committing to a label.")
            + r"\n",
            "Always confirm against context and uptake before committing to a label.\n"
            + NOTES_CROSSREF.rstrip("\n")
            + "\n",
            text,
            "negator-notes crossref",
            fname,
        )

    # 7. Per-language false-positive section, right before the uptake section.
    text = sub_once(
        r"(?m)^### Use the participants as your guide$",
        FALSE_POSITIVE_SECTIONS[language].rstrip("\n")
        + "\n\n### Use the participants as your guide",
        text,
        "false-positive section",
        fname,
    )

    # 8. Traps 4-5 appended to the Rejection-vs-Denial section.
    text = sub_once(
        re.escape("Three traps to avoid:"),
        "Five traps to avoid:",
        text,
        "trap count",
        fname,
    )
    text = sub_once(
        r"(?m)^### Negative imperatives",
        TRAPS_ADDON.rstrip("\n") + "\n\n### Negative imperatives",
        text,
        "traps 4-5",
        fname,
    )

    # 9. Uncoded-vs-Excluded strengthened.
    text = replace_section(text, "### Uncoded vs Excluded", UNCODED_SECTION, fname)

    # 10. Mimicry flag learns the imitation markers.
    text = sub_once(
        re.escape("communicative act. If `Yes`, set `bloom_label` to `Excluded`."),
        "communicative act. If `Yes`, set `bloom_label` to `Excluded`." + MIMICRY_ADDON,
        text,
        "mimicry addon",
        fname,
    )

    # 11. not_a_negation cross-reference, appended to the Flag Rules section.
    text = sub_once(
        r"(?m)^## Decide First, Then Write$",
        NAN_CROSSREF.rstrip("\n") + "\n\n## Decide First, Then Write",
        text,
        "not-a-negation crossref",
        fname,
    )

    # 12. Decide-first section gains evidence citation + certainty.
    text = replace_section(text, "## Decide First, Then Write", DECIDE_SECTION, fname)

    # 13. Output contract gains `certain`.
    text = replace_section(
        text, "## Output Contract", OUTPUT_CONTRACT.replace("__RID__", rid), fname
    )

    # 14. New worked examples R-W (English wording in all variants; see
    # CHANGES_FROM_V3.md for the translation decision).
    text = sub_once(
        r"(?m)^## Batch Input$",
        NEW_EXAMPLES.rstrip("\n") + "\n\n## Batch Input",
        text,
        "examples R-W",
        fname,
    )

    return text


def main() -> int:
    for fname, (language, rid) in FILES.items():
        out_name = fname.replace("bloom_v3_", "bloom_v4_")
        out_path = V4 / out_name
        out_path.write_text(build(fname, language, rid), encoding="utf-8")
        print(f"wrote {out_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
