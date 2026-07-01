#!/usr/bin/env python3
"""Shared per-language configuration for the LLM negation-coding pipeline.

The English pipeline (``build_english_llm_dataset.py`` +
``create_english_llm_splits.py``) is the reference implementation. The
generalized scripts ``build_llm_dataset.py`` and ``create_llm_splits.py`` read
the same kind of master + per-coder workbooks for the remaining languages, with
the per-language quirks captured here.

Structural differences from English captured below:
- German/Hebrew/Spanish masters have a single ``Transcript`` sheet (no
  First/Second half split, no ``Half`` column).
- They have no ``exclusion`` column, so there is no "RED ... TT5" drop step.
- Coder workbooks use a mix of spaced ("Not a negation?") and R-style dotted
  ("Not.a.negation?") headers; the readers match headers case- and
  separator-insensitively (see ``canon`` in the builder).
- Bloom labels in the coder sheets contain spelling/case variants
  (Nonposession, Nonexistance, lowercase denial/excluded, ...) that are
  normalized to the canonical six labels (see ``BLOOM_CANON``).
- German has three coder workbooks (PZ, MP, AR); per project decision
  (2026-06-25) the canonical IRR pair is PZ + MP.

Tagalog (added 2026-07-01) is built as two separate corpora that share the
language name "Tagalog" and are combined for LLM runs by
``combine_tagalog_splits.py``:
- ``tagalog_mpi``: standard master + two fully-aligned coder workbooks. The
  master's Transcript sheet has no header row, so ``context_workbook`` points
  context/age reading at HJ's copy (identical content, with headers). Child
  ages are blank in the ``@ID:`` lines and instead come from
  ``Tagalog_participant_info.xlsx`` (``age_source`` type ``participant_info``).
- ``tagalog_new``: no separate master exists. LM's current-full export doubles
  as the master (its Code sheet is the full candidate list); HJ's export is
  row-aligned to the *first* rows of LM's Code sheet only, so
  ``allow_missing_coder_rows`` treats absent coder rows as uncoded rather than
  as alignment mismatches. Ages are encoded in the transcript filename
  (``DS_020105.cha`` = 2;01.05; ``age_source`` type ``filename``).
- Both carry ``irr_bloom_collapse`` mapping Nonpossession -> Nonexistence:
  the coders differ in whether Nonpossession is used at all (new corpus:
  HJ 27x vs LM 1x), so the two labels are treated as one category in IRR
  comparisons (project decision 2026-07-01). Labels stored in outputs stay
  uncollapsed.
"""

from __future__ import annotations

from pathlib import Path

LLM_DIR = Path(__file__).resolve().parents[1]
ROOT = LLM_DIR.parents[1] if LLM_DIR.parent.name == "Data" else LLM_DIR.parent
TRANSCRIPTS = ROOT / "Data" / "Transcripts"
DATASET_DIR = LLM_DIR / "datasets"
SPLITS_DIR = LLM_DIR / "splits"

CONTEXT_SIZE = 20

# Canonical Bloom labels and the (lowercased) spelling/case variants observed in
# the human coder sheets. Anything not in this map is kept verbatim and reported
# in the dataset summary under `unmapped_bloom_labels` so new variants surface.
CANONICAL_BLOOM = [
    "Nonexistence",
    "Rejection",
    "Denial",
    "Nonpossession",
    "Uncoded",
    "Excluded",
]
BLOOM_CANON = {
    "nonexistence": "Nonexistence",
    "nonexistance": "Nonexistence",
    "rejection": "Rejection",
    "denial": "Denial",
    "nonpossession": "Nonpossession",
    "nonposession": "Nonpossession",
    "uncoded": "Uncoded",
    "excluded": "Excluded",
}

# Each language: master workbook, the ordered coder pair (initials + workbook),
# the transcript sheet layout as (half, sheet_name) pairs (half is None when the
# language has no First/Second-half split), and an optional pre-output exclusion
# (column, value) filter.
LANGUAGES = {
    "english": {
        "name": "English",
        "prefix": "eng",
        "master": TRANSCRIPTS / "English" / "2024-03-04_negation_coding_bloom_choi.xlsx",
        "coders": [
            ("EB", TRANSCRIPTS / "English" / "2024-03-04_negation_coding_bloom_choi_EB.xlsx"),
            ("WP", TRANSCRIPTS / "English" / "2024-03-04_negation_coding_bloom_choi_WP.xlsx"),
        ],
        "transcript_sheets": [
            (1, "Transcript - First half"),
            (2, "Transcript - Second half"),
        ],
        "exclusion": ("exclusion", "RED: INCLUDED AS TT5 FOR SYNTACTIC CODING"),
    },
    "german": {
        "name": "German",
        "prefix": "ger",
        "master": TRANSCRIPTS / "German" / "2023-09-28_NEW_negation_coding_bloom_choi.xlsx",
        "coders": [
            ("PZ", TRANSCRIPTS / "German" / "2023-09-28_NEW_negation_coding_bloom_choi_PZ.xlsx"),
            ("MP", TRANSCRIPTS / "German" / "2023-10-18_negation_coding_bloom_choi_MP.xlsx"),
        ],
        "transcript_sheets": [(None, "Transcript")],
        "exclusion": None,
    },
    "hebrew": {
        "name": "Hebrew",
        "prefix": "heb",
        "master": TRANSCRIPTS / "Hebrew" / "2023-12-06_NEW_negation_coding_bloom_choi.xlsx",
        "coders": [
            ("LL", TRANSCRIPTS / "Hebrew" / "2024-02-12_NEW_negation_coding_bloom_choi_LL.xlsx"),
            ("YS", TRANSCRIPTS / "Hebrew" / "2024-02-12_NEW_negation_coding_bloom_choi_YS.xlsx"),
        ],
        "transcript_sheets": [(None, "Transcript")],
        "exclusion": None,
    },
    "spanish": {
        "name": "Spanish",
        "prefix": "spa",
        "master": TRANSCRIPTS / "Spanish" / "2023-10-12_NEW_negation_coding_bloom_choi.xlsx",
        "coders": [
            ("AP", TRANSCRIPTS / "Spanish" / "2024-02-15_NEW_negation_coding_bloom_choi_AP.xlsx"),
            ("JEC", TRANSCRIPTS / "Spanish" / "2024-02-15_NEW_negation_coding_bloom_choi_JEC.xlsx"),
        ],
        "transcript_sheets": [(None, "Transcript")],
        "exclusion": None,
    },
    "tagalog_mpi": {
        "name": "Tagalog",
        "corpus": "MPI",
        "prefix": "tgm",
        "master": TRANSCRIPTS / "Tagalog-MPI" / "2023-09-27_NEW_negation_coding_bloom_choi.xlsx",
        "coders": [
            ("HJ", TRANSCRIPTS / "Tagalog-MPI" / "2023-09-27_negation_coding_bloom_choi_HJ.xlsx"),
            ("LM", TRANSCRIPTS / "Tagalog-MPI" / "2024-02-15_NEW_negation_coding_bloom_choi_LM.xlsx"),
        ],
        "transcript_sheets": [(None, "Transcript")],
        # Master's Transcript sheet is headerless; HJ's copy has headers and
        # identical content, so context windows and ages read from it.
        "context_workbook": TRANSCRIPTS / "Tagalog-MPI" / "2023-09-27_negation_coding_bloom_choi_HJ.xlsx",
        "exclusion": None,
        "age_source": {
            "type": "participant_info",
            "path": TRANSCRIPTS / "Tagalog-MPI" / "Tagalog_participant_info.xlsx",
            # Code/Transcript sheets use ids like '/transcript01.cha'; the
            # participant sheet keys rows by bare transcript number.
            "id_pattern": r"transcript0*(\d+)",
            "id_column": "transcript_no",
            "age_column": "age_child",
        },
        "irr_bloom_collapse": {"Nonpossession": "Nonexistence"},
    },
    "tagalog_new": {
        "name": "Tagalog",
        "corpus": "new_corpus",
        "prefix": "tgn",
        # LM's current-full export doubles as the master: its Code sheet is the
        # candidate list and its Transcript sheet covers all imported files.
        "master": TRANSCRIPTS / "Tagalog-new_corpus" / "2026-02-25_bloom-choi_LM_current-full.xlsx",
        "coders": [
            ("HJ", TRANSCRIPTS / "Tagalog-new_corpus" / "2026-02-25_bloom-choi_HJ_current-full.xlsx"),
            ("LM", TRANSCRIPTS / "Tagalog-new_corpus" / "2026-02-25_bloom-choi_LM_current-full.xlsx"),
        ],
        "transcript_sheets": [(None, "Transcript")],
        "exclusion": None,
        # HJ's Code sheet covers only the first rows of the master's; missing
        # rows mean HJ has not coded that far, not misalignment.
        "allow_missing_coder_rows": True,
        "age_source": {"type": "filename"},
        "irr_bloom_collapse": {"Nonpossession": "Nonexistence"},
    },
}

# The two Tagalog corpora are split separately (each gets its own transcript-
# level split) but are concatenated per split for LLM runs; see
# combine_tagalog_splits.py, which writes splits/tagalog/.
TAGALOG_LANGUAGES = ["tagalog_mpi", "tagalog_new"]
COMBINED_TAGALOG_SLUG = "tagalog"

# Languages the generalized scripts build by default. English keeps its own
# dedicated, already-validated scripts as the source of truth, so it is excluded
# here to avoid implying byte-parity, but its config is retained above for
# reference and future unification.
DEFAULT_LANGUAGES = ["german", "hebrew", "spanish"]
