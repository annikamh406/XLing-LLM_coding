#!/usr/bin/env python3
"""Render frozen non-English condensed prompts from the English v5 core.

All calibration examples and general decision rules remain byte-identical to
the English condensed prompt. Only the task language and a compact reviewed
locale appendix vary.
"""

from __future__ import annotations

from pathlib import Path


LLM_DIR = Path(__file__).resolve().parents[1]
V5_DIR = LLM_DIR / "v5"
SOURCE = V5_DIR / "bloom_v5_english_prompt_condensed.md"

FALSE_POSITIVE_BLOCK = """Common English false positives include `no` inside `know`, `gone` used simply
for leaving or in `gone where?`, and `uh uh` used as hesitation. Do not assign
the semantic label that a lyric or imitation would have received as an
independent child assertion."""

LOCALES = {
    "german": {
        "name": "German",
        "code": "de",
        "appendix": """## German locale appendix

- Treat CHAT spellings and child/dialect forms such as `nee`, `ne`,
  `nich`, and `net` as possible realizations of `nein`/`nicht`; reconstruct
  phonologically approximate or partial productions from context.
- Frequent targets include `nein`/`nee`/`ne`, `nicht` and its variants,
  inflected `kein`, `nichts`/`nix`, `nie`, `niemand`, `ohne`, `weg`, `alle`,
  `fertig`, and candidate uses of `doch`.
- Check lexical ambiguity before coding: `alle` may mean the quantifier
  “all/everyone” rather than completive “all gone/empty”; `doch` is often an
  affirmative/emphatic particle; `weg` and `fertig` may simply describe
  movement/completion; `ohne` may be a fragment; `na` is not `nein`; and a
  string match for `nie` inside `Knie` is not negation.
- Use context to distinguish `kein X`/absence from possessive `ich habe kein
  X`. A specific negative command with `nicht` or `kein` is `Rejection`;
  a general rule remains `Denial`.
""",
    },
    "hebrew": {
        "name": "Hebrew",
        "code": "he",
        "appendix": """## Hebrew locale appendix

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
""",
    },
    "spanish": {
        "name": "Spanish",
        "code": "es",
        "appendix": """## Spanish locale appendix

- Frequent targets include `no`, `nada`, `nadie`, `ninguno`/`ningún`/
  `ninguna`, `nunca`, `tampoco`, `sin`, and negative-conjunction `ni`.
  Interpret repairs, reductions, and child pronunciations through the CHAT
  annotations and discourse context.
- Check ambiguity before coding: rising-intonation echo `no?` may query an
  adult's negation; `ni` may be a repair fragment (`ni [/] niñito`); quoted,
  read-aloud, or role-played `no` may be mimicry; and string matches inside
  words such as `nota` or `mano` are not negation.
- `no hay X` and absent `nada`/`nadie`/`ninguno` often mark
  `Nonexistence`; `no tengo X` or possessive `sin X` mark
  `Nonpossession`; agreement with a prior negative via `nunca` or `tampoco`
  is generally `Denial`.
- A specific negative command uses `no` plus a present-subjunctive verb and
  is `Rejection`; a detached rule or norm remains `Denial`.
""",
    },
    "tagalog": {
        "name": "Tagalog",
        "code": "tl",
        "appendix": """## Tagalog locale appendix

- Frequent targets include `hindi` (often `di` or `'di`), existential and
  possessive `wala`/`walang`/`wala nang`, prohibitive `huwag`/`wag`,
  `ayaw`/`ayoko`, `aywan`/`ewan`, `bawal`, and completive `ubos`.
  Reconstruct child pronunciations, contractions, and CHAT repairs from
  context.
- Check ambiguity before coding: `di` may occur inside `dito`/`diyan`, `wag`
  inside `tawag`, `wala` inside frozen `walang anuman`, and `ewan` may be a
  filler shrug. Noncommunicative negator sound-play is not a content label.
- `wala na`/`ubos na` often marks `Nonexistence`; `wala akong X` marks
  `Nonpossession`; `ayaw` can reject an offered or impending thing.
- `huwag`/`wag` stopping a specific action is `Rejection`, while a general
  norm with `bawal` can be `Denial`. English `no`/`not`/`don't` and Bisaya
  `dili` are foreign-language negators but are not automatically excluded.
""",
    },
}


def render(language: str, config: dict[str, str], source: str) -> str:
    name = config["name"]
    code = config["code"]
    text = source.replace(
        "# Bloom v5 English Negation Coding — Condensed Prompt",
        f"# Bloom v5 {name} Negation Coding — Condensed Prompt",
        1,
    )
    text = text.replace(
        "Prompt version family: `p005c`.",
        f"Prompt version family: `p005c-{code}-engex`.",
        1,
    )
    text = text.replace(
        "Code each target negator in an English child-caregiver transcript.",
        f"Code each target negator in a {name} child-caregiver transcript.",
        1,
    )
    locale_block = (
        "Run the locale-specific ambiguity checks below before assigning a "
        "semantic label. Do not assign the semantic label that a lyric or "
        "imitation would have received as an independent child assertion."
        "\n\n"
        + config["appendix"].strip()
    )
    if FALSE_POSITIVE_BLOCK not in text:
        raise SystemExit("English false-positive block changed; refusing to render.")
    text = text.replace(FALSE_POSITIVE_BLOCK, locale_block, 1)
    if "## Calibration examples" not in text:
        raise SystemExit("Calibration examples missing from rendered prompt.")
    return text


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    for language, config in LOCALES.items():
        output = (
            V5_DIR
            / f"bloom_v5_{language}_prompt_condensed_english_examples.md"
        )
        output.write_text(render(language, config, source), encoding="utf-8")
        print(f"Wrote {output.relative_to(LLM_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
