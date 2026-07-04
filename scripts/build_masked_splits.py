#!/usr/bin/env python3
"""Build masked-negator split variants for the v4 masked evaluation arm.

For each language split directory (`splits/<language>/`), writes
`splits/<language>_masked/` in which:

1. **Pre-filtered rows.** Any record where *either* human coder marked
   `not_a_negation` = Yes, `repetition` = Yes, or
   `foreign_language_negation` = Yes is dropped: all three judgments require
   seeing the negator token, which the masked model cannot.
2. **Masked negator.** `target_negator` is replaced by `[MASKED]`, and every
   occurrence of that negator in `target_utterance` is replaced by
   `[MASKED]`. All occurrences are masked (not just the indexed one) so an
   unmasked copy of the same word cannot leak the masked token; each record
   masks only its own negator lexeme, so a different negator in the same
   utterance stays visible. Context lines and all other fields are unchanged.

Matching is CHAT-transcription-aware: tokens are compared after stripping
parenthesized elisions (`nich(t)` -> `nicht`, `(hin)di` -> `hindi`),
`@...` suffixes, `<`/`>` grouping, surrounding punctuation, romanization
glottals/pharyngeals (`loʔ` -> `lo`), and combining diacritics; a token like
`lab[:wala]` also matches via its `[: ...]` correction. Multiword negators
(`uh uh`, `para nada`) are matched as token n-grams. If token matching fails,
a raw case-insensitive substring replacement is attempted; records that still
cannot be masked are dropped and listed in the manifest (an unmaskable record
would otherwise leak its negator).

Outputs per split: `<split>.jsonl`, `<split>_human_reference.jsonl` (filtered
to kept records), and a shared `masking_manifest.json` with per-split counts.

Usage:
    python3 scripts/build_masked_splits.py [--languages english german ...]
                                           [--splits dev_train ...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

LLM_DIR = Path(__file__).resolve().parent.parent
SPLITS_DIR = LLM_DIR / "splits"

DEFAULT_LANGUAGES = ["english", "german", "hebrew", "spanish", "tagalog"]
MASK = "[MASKED]"

# Letters that survive isalnum() but are transcription artifacts that differ
# between the negator inventory form and the utterance form.
STRIP_LETTERS = {"ʔ", "ʕ"}  # ʔ, ʕ

YES = "Yes"


def normalize(form: str) -> str:
    """Reduce a token or negator to a comparison key."""
    form = unicodedata.normalize("NFD", form.casefold())
    return "".join(
        ch
        for ch in form
        if ch.isalnum() and not unicodedata.combining(ch) and ch not in STRIP_LETTERS
    )


def token_candidates(token: str) -> set[str]:
    """Normalized comparison keys a single whitespace token can match under."""
    candidates = set()
    base = token
    # A [: correction] inside or after the surface form is a candidate on its
    # own (e.g. `lab[:wala]` should match negator `wala`).
    for correction in re.findall(r"\[:\s*([^\]]+?)\s*\]", token):
        candidates.add(normalize(correction))
    # Drop bracketed material, grouping angle brackets, parenthesized
    # elisions, and @-suffixes from the surface form.
    base = re.sub(r"\[[^\]]*\]", "", base)
    base = base.replace("<", "").replace(">", "")
    for variant in (base, base.replace("(", "").replace(")", "")):
        variant = re.sub(r"@\S*$", "", variant)
        variant = variant.strip("&+-=!?.,;:\"'`^ ")
        if variant:
            candidates.add(normalize(variant))
    candidates.discard("")
    return candidates


def mask_utterance(utterance: str, negator: str) -> tuple[str, int]:
    """Replace every occurrence of `negator` in `utterance` with MASK.

    Returns the masked utterance and the number of maskings applied.
    """
    negator_keys = [normalize(part) for part in negator.split()]
    negator_keys = [k for k in negator_keys if k]
    if not negator_keys:
        return utterance, 0
    n = len(negator_keys)
    # A multiword negator may surface as one joined token (`all gone` is
    # transcribed `all_gone`), so also match the joined key on single tokens.
    joined_key = normalize(negator)

    tokens = utterance.split(" ")
    keys = [token_candidates(tok) for tok in tokens]

    # First pass: which token indices carry the negator?
    to_mask: set[int] = set()
    drop: set[int] = set()
    hits = 0
    i = 0
    while i < len(tokens):
        if joined_key in keys[i]:
            to_mask.add(i)
            hits += 1
            i += 1
            continue
        window = keys[i : i + n]
        if (
            n > 1
            and len(window) == n
            and all(negator_keys[j] in window[j] for j in range(n))
        ):
            to_mask.add(i)
            drop.update(range(i + 1, i + n))
            hits += 1
            i += n
        else:
            i += 1

    if not hits:
        # Fallback: raw case-insensitive substring replacement.
        pattern = re.compile(re.escape(negator), re.IGNORECASE)
        masked, count = pattern.subn(MASK, utterance)
        return (masked, count) if count else (utterance, 0)

    # CHAT corrections: in `surface [: correction]`, masking a token inside
    # the correction must also mask the surface token it corrects, otherwise
    # the child's rendition of the negator stays visible (`diba [: hindi
    # ba]?` must not keep `diba`).
    group_start = None
    for i, token in enumerate(tokens):
        if token.startswith("[:"):
            group_start = i
        if group_start is not None:
            if to_mask & {group_start, i} and i in to_mask and group_start <= i:
                for j in range(group_start - 1, -1, -1):
                    if j not in drop and not tokens[j].startswith("["):
                        to_mask.add(j)
                        break
            if token.endswith("]") or token.rstrip(".,!?;:").endswith("]"):
                group_start = None

    # Rebuild, preserving sentence punctuation around masked tokens.
    out = []
    for i, token in enumerate(tokens):
        if i in drop:
            continue
        if i in to_mask:
            # Preserve sentence punctuation only; elision parentheses,
            # quotes, and bracket content belong to the masked token.
            suffix = re.search(r"[.,!?;:]*$", token).group(0)
            out.append(MASK + suffix)
        else:
            out.append(token)
    return " ".join(out), hits


def coder_flag_yes(coder: dict | None, flag: str) -> bool:
    if not coder:
        return False
    flags = coder.get("flags") or {}
    return flags.get(flag) == YES


def process_split(lang_dir: Path, out_dir: Path, split: str) -> dict:
    records = [
        json.loads(line)
        for line in (lang_dir / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    href_path = lang_dir / f"{split}_human_reference.jsonl"
    href = {}
    if href_path.exists():
        for line in href_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                href[row["record_id"]] = row

    kept, masked_rows, dropped_flagged, dropped_unmaskable = [], [], [], []
    for record in records:
        ref = href.get(record["record_id"], {})
        if any(
            coder_flag_yes(ref.get(coder), flag)
            for coder in ("coder_1", "coder_2")
            for flag in ("not_a_negation", "repetition", "foreign_language_negation")
        ):
            dropped_flagged.append(record["record_id"])
            continue
        masked_utt, hits = mask_utterance(
            record["target_utterance"], record["target_negator"]
        )
        if hits == 0:
            dropped_unmaskable.append(record["record_id"])
            continue
        out = dict(record)
        out["target_negator"] = MASK
        out["target_utterance"] = masked_utt
        kept.append(out)
        masked_rows.append(record["record_id"])

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
        for record in kept:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    if href:
        kept_ids = {record["record_id"] for record in kept}
        with (out_dir / f"{split}_human_reference.jsonl").open(
            "w", encoding="utf-8"
        ) as handle:
            for row in href.values():
                if row["record_id"] in kept_ids:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "input_records": len(records),
        "kept": len(kept),
        "dropped_human_flagged": len(dropped_flagged),
        "dropped_unmaskable": dropped_unmaskable,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--languages", nargs="+", default=DEFAULT_LANGUAGES)
    parser.add_argument(
        "--splits",
        nargs="+",
        default=None,
        help="Split names; default: every *.jsonl in the language dir that is "
        "not a human_reference file.",
    )
    args = parser.parse_args()

    for language in args.languages:
        lang_dir = SPLITS_DIR / language
        if not lang_dir.is_dir():
            print(f"skip {language}: {lang_dir} not found", file=sys.stderr)
            continue
        out_dir = SPLITS_DIR / f"{language}_masked"
        splits = args.splits or sorted(
            p.stem
            for p in lang_dir.glob("*.jsonl")
            if not p.stem.endswith("_human_reference")
        )
        manifest = {"language": language, "mask": MASK, "splits": {}}
        for split in splits:
            summary = process_split(lang_dir, out_dir, split)
            manifest["splits"][split] = summary
            print(
                f"{language}/{split}: kept {summary['kept']}/{summary['input_records']}"
                f" (dropped {summary['dropped_human_flagged']} human-flagged,"
                f" {len(summary['dropped_unmaskable'])} unmaskable)"
            )
        (out_dir / "masking_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
