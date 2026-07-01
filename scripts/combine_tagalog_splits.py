#!/usr/bin/env python3
"""Combine the per-corpus Tagalog splits into one runnable splits/tagalog/.

The two Tagalog corpora (``tagalog_mpi``, ``tagalog_new``) are split
separately so each split is balanced *within* its corpus, but LLM runs treat
Tagalog as a single language: this script concatenates the per-corpus files
for each split into ``splits/tagalog/``. Records keep their ``corpus`` field
and per-corpus record-id prefixes (``tgm_``/``tgn_``), so results can be
evaluated combined or per-corpus later.

Within each combined split the records are shuffled with a fixed seed. Run
commands use ``--limit N`` (a prefix of the file), so without shuffling a
limit-100 run would never reach the second corpus; the deterministic shuffle
makes any prefix a corpus mix while staying reproducible.

Usage:
    python3 combine_tagalog_splits.py
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter

from _pipeline_config import (
    COMBINED_TAGALOG_SLUG,
    ROOT,
    SPLITS_DIR,
    TAGALOG_LANGUAGES,
)

SHUFFLE_SEED = 20260701
SPLIT_NAMES = [
    "dev_train",
    "dev_check_1",
    "dev_check_2",
    "test_lockbox",
    "uncoded_by_neither",
]


def read_jsonl(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def write_jsonl(path, records):
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def csv_row(record):
    return {
        "record_id": record["record_id"],
        "split": record.get("split"),
        "language": record["language"],
        "corpus": record.get("corpus"),
        "source_row": record["source"]["source_row"],
        "transcript_id": record["transcript_id"],
        "half": record.get("half"),
        "line": record.get("line"),
        "speaker": record.get("speaker"),
        "child_id": record.get("child_id"),
        "child_age_months": record.get("child_age_months"),
        "child_age_raw": record.get("child_age_raw"),
        "target_negator": record.get("target_negator"),
        "target_utterance": record.get("target_utterance"),
        "negator_index_in_utterance": record.get("negator_index_in_utterance"),
        "negators_in_utterance": record.get("negators_in_utterance"),
        "coded_by_1": record.get("coded_by_1"),
        "coded_by_2": record.get("coded_by_2"),
        "context_before_json": json.dumps(record.get("context_before", []), ensure_ascii=False),
        "context_after_json": json.dumps(record.get("context_after", []), ensure_ascii=False),
    }


def write_csv(path, records):
    if not records:
        return
    fieldnames = list(csv_row(records[0]).keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(csv_row(record))


def irr_quick_stats(records):
    pairs = [
        (r["bloom_1_irr"], r["bloom_2_irr"])
        for r in records
        if r.get("bloom_1_irr") is not None and r.get("bloom_2_irr") is not None
    ]
    if not pairs:
        return {"n_overlap_bloom": 0, "bloom_exact_agreement": None}
    agreement = sum(1 for a, b in pairs if a == b) / len(pairs)
    return {
        "n_overlap_bloom": len(pairs),
        "bloom_exact_agreement": round(agreement, 4),
    }


def main():
    out_dir = SPLITS_DIR / COMBINED_TAGALOG_SLUG
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SHUFFLE_SEED)

    summary = {
        "combined_from": TAGALOG_LANGUAGES,
        "shuffle_seed": SHUFFLE_SEED,
        "note": (
            "Records shuffled deterministically within each split so that "
            "--limit N run prefixes mix both corpora. Evaluate per corpus via "
            "the 'corpus' field or the tgm_/tgn_ record-id prefixes."
        ),
        "splits": {},
    }

    for split_name in SPLIT_NAMES:
        records = []
        references = []
        for slug in TAGALOG_LANGUAGES:
            records.extend(read_jsonl(SPLITS_DIR / slug / f"{split_name}.jsonl"))
            references.extend(
                read_jsonl(SPLITS_DIR / slug / f"{split_name}_human_reference.jsonl")
            )
        rng.shuffle(records)
        order = {record["record_id"]: i for i, record in enumerate(records)}
        references.sort(key=lambda ref: order[ref["record_id"]])

        write_jsonl(out_dir / f"{split_name}.jsonl", records)
        write_csv(out_dir / f"{split_name}.csv", records)
        write_jsonl(out_dir / f"{split_name}_human_reference.jsonl", references)

        by_corpus = Counter(record.get("corpus") for record in records)
        summary["splits"][split_name] = {
            "n_rows": len(records),
            "by_corpus": dict(by_corpus),
            **irr_quick_stats(records),
            "per_corpus_irr": {
                corpus: irr_quick_stats(
                    [r for r in records if r.get("corpus") == corpus]
                )
                for corpus in sorted(c for c in by_corpus if c)
            },
        }

    (out_dir / "split_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Wrote combined splits to {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
