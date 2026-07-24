#!/usr/bin/env python3
"""Derive optional masked-negator prompt variants from bloom_v5 prompts."""

from __future__ import annotations

import re
import sys
from pathlib import Path

V5 = Path(__file__).resolve().parent

MASKED_BLOCK = """**Masked-negator variant.** The target lexeme is hidden:
`target_negator` is `[MASKED]`, and its occurrences in `target_utterance`
are `[MASKED]`. Code from the utterance frame and discourse context.

Human pre-screening already removed rows marked `not_a_negation`,
`repetition`, or `foreign_language_negation`. Therefore always set those
three flags to `No`, skip Step 0 and the exact-lexeme/homograph checks, and
do not emit `Excluded` via `not_a_negation`. Continue to judge `singing`,
`mimicry`, and `tag_question` from the visible context.

Use `negator_index_in_utterance` only to align the masked slot with its
record; do not try to reconstruct the hidden lexeme.

"""

MASKED_TARGET_SECTION = """### Locate the masked target slot

Use `negator_index_in_utterance` to align this record with the appropriate
masked slot. The lexeme and its homograph status were pre-screened and are
not available in this arm; do not try to reconstruct them.

"""

MASKED_STEP_ZERO = """**Masked pre-screening.** Records requiring a visible
lexeme to identify `not_a_negation`, `repetition`, or
`foreign_language_negation` were removed before this arm. Do not repeat Step
0 from the unmasked prompt. Continue to detect singing and mimicry from the
visible transcript context.

"""

MASKED_FLAG_PREFLIGHT = """### Mechanical flag preflight

Before interpreting propositional content, scan the visible transcript for
the two exclusion cues that remain judgeable in this arm:

1. If the target is in a line marked or contextually identified as singing
   or song lyrics, choose `Excluded` + `singing` = `Yes`.
2. If the target line has an imitation marker (`[+ IMIT]`, `[+ IMI]`,
   `[=! imitates]`) or is an exact, contentless echo of the immediately
   preceding adult line, choose `Excluded` + `mimicry` = `Yes`.

Do not first assign the label that the sung or imitated sentence would have
had as an independent child assertion.

"""

MASKED_DECIDE_SECTION = """## Decide First, Then Write

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

"""

MASKED_FIXED_FLAGS = """`repetition`: Always `No` in this variant; rows
requiring a visible target lexeme to judge repetition were removed before
prompting.

`not_a_negation`: Always `No` in this variant; false-positive candidate
negators were removed before prompting.

"""


def sub_once(pattern: str, repl, text: str, name: str, fname: str) -> str:
    new, n = re.subn(pattern, repl, text)
    if n != 1:
        raise SystemExit(f"{fname}: edit {name!r} matched {n} times (expected 1)")
    return new


def main() -> int:
    prompts = sorted(
        p
        for p in V5.glob("bloom_v5_*prompt*.md")
        if not p.stem.endswith("_masked")
    )
    if len(prompts) != 9:
        raise SystemExit(f"expected 9 v5 prompts, found {len(prompts)}")
    for path in prompts:
        text = path.read_text(encoding="utf-8")
        text = sub_once(
            r"(?m)^(# Bloom v5 .* Negation Coding Prompt)$",
            r"\1 (Masked Negator Variant)",
            text,
            "title",
            path.name,
        )
        text = sub_once(
            r"Prompt version: `p005",
            "Prompt version: `p005m",
            text,
            "prompt version",
            path.name,
        )
        text = sub_once(
            r"(?m)^## Allowed Output Labels$",
            MASKED_BLOCK + "## Allowed Output Labels",
            text,
            "masked block",
            path.name,
        )
        text = sub_once(
            r"(?m)^- `target_negator`$",
            "- `target_negator`: always `[MASKED]` in this variant",
            text,
            "target bullet",
            path.name,
        )
        text = sub_once(
            r"(?ms)^### Align and interpret the target occurrence\n.*?(?=^### )",
            MASKED_TARGET_SECTION,
            text,
            "masked target section",
            path.name,
        )
        text = sub_once(
            r"(?ms)^\*\*Step 0 .*?(?=^### Locate the masked target slot)",
            MASKED_STEP_ZERO,
            text,
            "masked Step 0",
            path.name,
        )
        text = sub_once(
            r"(?ms)^### Known false-positive readings.*?(?=^### )",
            "",
            text,
            "remove visible-lexeme false positives",
            path.name,
        )
        if "Hebrew target-occurrence safeguard" in text:
            text = sub_once(
                r"(?ms)^\*\*Hebrew target-occurrence safeguard\.\*\*.*?(?=^### )",
                "",
                text,
                "remove Hebrew visible-lexeme safeguard",
                path.name,
            )
        text = sub_once(
            r"(?ms)^### Mechanical flag preflight\n.*?(?=^## Flag Rules)",
            MASKED_FLAG_PREFLIGHT,
            text,
            "masked flag preflight",
            path.name,
        )
        text = sub_once(
            r"(?ms)^## Decide First, Then Write\n.*?(?=^## Output Contract)",
            MASKED_DECIDE_SECTION,
            text,
            "masked decision process",
            path.name,
        )
        text = sub_once(
            r"(?ms)^`foreign_language_negation`:.*?(?=^`singing`:)",
            "`foreign_language_negation`: Always `No` in this variant; such "
            "rows were removed before prompting.\n\n",
            text,
            "masked foreign-language flag",
            path.name,
        )
        text = sub_once(
            r"(?ms)^`repetition`:.*?(?=^## Decide First, Then Write)",
            MASKED_FIXED_FLAGS,
            text,
            "masked repetition and not-a-negation flags",
            path.name,
        )
        text = text.replace(
            "and only together with a licensing flag: `singing`, `mimicry`, or\n"
            "`not_a_negation` = `Yes`.",
            "and only together with a licensing flag still judgeable in this\n"
            "arm: `singing` or `mimicry` = `Yes`.",
        )
        out = path.with_name(path.stem + "_masked.md")
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
