#!/usr/bin/env python3
"""Derive the masked-negator prompt variants from the bloom_v4 prompts.

For each `bloom_v4_*_prompt*.md` this writes `*_masked.md` with three
anchored edits (each asserted to match exactly once):

1. Title suffixed with "(Masked Negator Variant)" and prompt version
   `p004*` -> `p004m*`.
2. A masked-variant instruction block appended to the System / Task
   Instruction section.
3. The `target_negator` batch-input bullet notes the field is `[MASKED]`.

Run alongside `make_v4_prompts.py`; pairs with splits built by
`scripts/build_masked_splits.py` into `splits/<language>_masked/`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

V4 = Path(__file__).resolve().parent

MASKED_BLOCK = """**Masked-negator variant.** In this run the negator token itself is hidden:
in each record, `target_negator` is the string `[MASKED]`, and every
occurrence of that negator in `target_utterance` has been replaced by
`[MASKED]`. Everything else - context before and after, speaker, indices -
is unchanged. Code the communicative function of the masked negation from
the utterance frame and the discourse context alone. The examples below show
unmasked negators because they teach the category distinctions; in your
input the target token is always `[MASKED]`.

Records whose negator a human screener judged not to be a real negation, a
repetition of a previous negator token, or a foreign-language negator were
removed from this variant in advance — all three judgments require seeing
the token. Therefore **always set `repetition` = `No`,
`not_a_negation` = `No`, and `foreign_language_negation` = `No`**, and skip
Step 0 below (the false-positive check has already been done for you); never
output `Excluded` with `not_a_negation` = `Yes`. Judge the remaining flags
(`singing`, `mimicry`, `tag_question`) from the utterance frame and
surrounding lines as usual.

"""


def sub_once(pattern: str, repl, text: str, name: str, fname: str) -> str:
    new, n = re.subn(pattern, repl, text)
    if n != 1:
        raise SystemExit(f"{fname}: edit {name!r} matched {n} times (expected 1)")
    return new


def main() -> int:
    prompts = sorted(
        p
        for p in V4.glob("bloom_v4_*prompt*.md")
        if not p.stem.endswith("_masked")
    )
    if len(prompts) != 9:
        raise SystemExit(f"expected 9 v4 prompts, found {len(prompts)}")
    for path in prompts:
        text = path.read_text(encoding="utf-8")
        text = sub_once(
            r"(?m)^(# Bloom v4 .* Negation Coding Prompt)$",
            r"\1 (Masked Negator Variant)",
            text,
            "title",
            path.name,
        )
        text = sub_once(
            r"Prompt version: `p004",
            "Prompt version: `p004m",
            text,
            "prompt version",
            path.name,
        )
        text = sub_once(
            r"(?m)^## Allowed Output Labels$",
            MASKED_BLOCK.rstrip("\n") + "\n\n## Allowed Output Labels",
            text,
            "masked block",
            path.name,
        )
        text = sub_once(
            r"(?m)^- `target_negator`$",
            "- `target_negator`: always the string `[MASKED]` in this variant",
            text,
            "batch-input negator bullet",
            path.name,
        )
        out = path.with_name(path.stem + "_masked.md")
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
