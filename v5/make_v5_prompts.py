#!/usr/bin/env python3
"""Generate bloom_v5 policy, schema, and prompts from frozen v4 artifacts.

v5 is deliberately conservative: it strengthens the ordered decision process
for error classes that remained robust in the full Gemma v4 run, while leaving
the disputed v4 rules for ability, directives, plan questions, negative
imperatives, and exact echoes unchanged.

Run from anywhere:
    python3 v5/make_v5_prompts.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

V4 = Path(__file__).resolve().parent.parent / "v4"
V5 = Path(__file__).resolve().parent

FILES = {
    "bloom_v4_english_prompt.md": "English",
    "bloom_v4_german_prompt.md": "German",
    "bloom_v4_german_prompt_english_examples.md": "German",
    "bloom_v4_hebrew_prompt.md": "Hebrew",
    "bloom_v4_hebrew_prompt_english_examples.md": "Hebrew",
    "bloom_v4_spanish_prompt.md": "Spanish",
    "bloom_v4_spanish_prompt_english_examples.md": "Spanish",
    "bloom_v4_tagalog_prompt.md": "Tagalog",
    "bloom_v4_tagalog_prompt_english_examples.md": "Tagalog",
}

EXACT_TARGET_SECTION = """### Align and interpret the target occurrence

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

"""

ORDERED_LABEL_SECTION = """### Choose the label in this order

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

"""

MOVE_TEST = """Before the five traps, perform a **literal-content / live-move
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

"""

UNCODED_SECTION = """### Uncoded vs Excluded

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
all, and only together with a licensing flag: `singing`, `mimicry`, or
`not_a_negation` = `Yes`. Never use `Excluded` for a real negation that is
merely ambiguous or unintelligible.

"""

FLAG_PREFLIGHT = """### Mechanical flag preflight

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

"""

DECIDE_SECTION = """## Decide First, Then Write

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

"""

NEW_EXAMPLES = """Example X:

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

"""

def sub_once(pattern: str, repl, text: str, name: str, fname: str, flags=0) -> str:
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != 1:
        raise SystemExit(f"{fname}: edit {name!r} matched {n} times (expected 1)")
    return new


def replace_section(text: str, header: str, replacement: str, fname: str) -> str:
    pattern = rf"(?ms)^{re.escape(header)}\n.*?(?=^#{{2,3}} )"
    return sub_once(pattern, lambda _: replacement, text, header, fname)


def build_prompt(fname: str, language: str) -> str:
    text = (V4 / fname).read_text(encoding="utf-8")

    text = text.replace("# Bloom v4 ", "# Bloom v5 ", 1)
    text = text.replace("Prompt version: `p004", "Prompt version: `p005", 1)
    text = text.replace(
        "v4/Bloom_coding_policy_v4.md", "v5/Bloom_coding_policy_v5.md"
    )
    text = text.replace(
        "v4/bloom_v4_output.schema.json", "v5/bloom_v5_output.schema.json"
    )
    text = text.replace("`bloom_v4`", "`bloom_v5`")
    text = text.replace('"schema_version": "bloom_v4"', '"schema_version": "bloom_v5"')

    text = sub_once(
        r"(?m)^Choose `Nonpossession` when.*?^Choose `Denial`.*?\n\n(?=### )",
        ORDERED_LABEL_SECTION,
        text,
        "ordered labels",
        fname,
        flags=re.DOTALL | re.MULTILINE,
    )
    text = sub_once(
        r"(?m)^### Choose the label in this order$",
        EXACT_TARGET_SECTION + "### Choose the label in this order",
        text,
        "exact target section",
        fname,
    )
    text = sub_once(
        r"(?m)^Five traps to avoid:$",
        MOVE_TEST + "Five traps to avoid:",
        text,
        "live-move test",
        fname,
    )
    text = replace_section(text, "### Uncoded vs Excluded", UNCODED_SECTION, fname)
    text = sub_once(
        r"(?m)^## Flag Rules$",
        FLAG_PREFLIGHT + "## Flag Rules",
        text,
        "flag preflight",
        fname,
    )
    text = replace_section(text, "## Decide First, Then Write", DECIDE_SECTION, fname)
    text = sub_once(
        r"(?m)^## Batch Input$",
        NEW_EXAMPLES + "## Batch Input",
        text,
        "examples X-AA",
        fname,
    )
    return text


def build_policy() -> str:
    text = (V4 / "Bloom_coding_policy_v4.md").read_text(encoding="utf-8")
    text = text.replace("`bloom_v4`", "`bloom_v5`")
    text = text.replace(
        "Supersedes `bloom_v3` (`v3/Bloom_coding_policy_v3.md`). What changed and why\n"
        "is documented separately in `v4/CHANGES_FROM_V3.md`",
        "Supersedes `bloom_v4` (`v4/Bloom_coding_policy_v4.md`). What changed and why\n"
        "is documented separately in `v5/CHANGES_FROM_V4.md`",
    )
    text = text.replace("Since v4 the policy is\nexplicitly multilingual", "The policy is multilingual")
    text = re.sub(r"\s*\(new in\s+v4\)", "", text)
    text = re.sub(r"\s*\(strengthened in\s+v4\)", "", text)
    text = text.replace("## Masked-negator variant (new in v4)", "## Masked-negator variant")
    text = text.replace("schema (`bloom_v4`)", "schema (`bloom_v5`)")
    text = text.replace("prompt versions `p004m*`", "prompt versions `p005m*`")
    text = text.replace('"schema_version": "bloom_v4"', '"schema_version": "bloom_v5"')

    policy_addon = """### Mandatory label order

After establishing that the indexed target occurrence is a genuine negator,
test labels in this order: `Nonpossession`, `Nonexistence`, `Rejection`,
`Denial`, then `Uncoded`. Dedicated possession/existence labels override
ordinary factual Denial. Denial is the residual content label, not the default
for every declarative-looking negative sentence.

### Target occurrence alignment and contextual reconstruction

Use `negator_index_in_utterance` to identify which occurrence is being coded.
Interpret it using the transcription, CHAT annotations, surrounding
utterance, and discourse context. A production may be incomplete,
phonologically approximate, misspelled, or imperfectly transcribed; use its
best-supported intended meaning rather than requiring a literal surface
reading. Do not transfer the interpretation of another occurrence to the
indexed target, and do not use `not_a_negation` merely because the
transcription is imperfect. Put unresolved interpretive doubt in `certain` =
`No` and `comments`.

### Literal content versus live discourse move

State both (a) the literal negative proposition and (b) what the child is
doing with it in the current exchange. A location, preference, intention, or
other declarative-looking form is `Rejection` when it is the child's move for
vetoing or replacing a concrete placement, object choice, turn, or course of
action currently in play. Activity alone is insufficient: the context must
show a specific thing/action being opposed. If only truth is at issue, use
`Denial` unless a dedicated possession/existence label applies.

### Missing referent is not missing function

`Uncoded` is licensed by an unrecoverable **function**, not merely an unnamed
referent or incomplete prejacent. Constructions such as `none left`, `no
more`, `all gone`, and Tagalog `wala na` identify `Nonexistence` even when the
entity is implicit. A preceding question can supply the missing possession,
existence, offer, or fact under discussion.

### Mechanical flag preflight

Before interpreting propositional content, scan the indexed target line for
singing/song context, imitation markers or an exact contentless adult echo,
and known false-positive readings. Apply `Excluded` with the corresponding
licensing flag before analyzing what the lyric or echoed sentence would mean
as an independent assertion.

"""
    text = sub_once(
        r"(?m)^### Interlocutor uptake$",
        policy_addon + "### Interlocutor uptake",
        text,
        "policy v5 rules",
        "Bloom_coding_policy_v5.md",
    )
    return text


def build_schema() -> str:
    schema = json.loads((V4 / "bloom_v4_output.schema.json").read_text())
    schema["$id"] = "bloom_v5_output.schema.json"
    schema["title"] = "Bloom v5 LLM Coding Output"
    schema["description"] = (
        "Strict output schema for multilingual Bloom negation coding, policy "
        "bloom_v5. The output structure is unchanged from bloom_v4; only the "
        "schema version is bumped so v5 runs remain traceable."
    )
    schema["properties"]["schema_version"]["const"] = "bloom_v5"
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    V5.mkdir(parents=True, exist_ok=True)
    for fname, language in FILES.items():
        out = V5 / fname.replace("bloom_v4_", "bloom_v5_")
        out.write_text(build_prompt(fname, language), encoding="utf-8")
        print(f"wrote {out.name}")
    (V5 / "Bloom_coding_policy_v5.md").write_text(build_policy(), encoding="utf-8")
    print("wrote Bloom_coding_policy_v5.md")
    (V5 / "bloom_v5_output.schema.json").write_text(build_schema(), encoding="utf-8")
    print("wrote bloom_v5_output.schema.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
