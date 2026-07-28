#!/usr/bin/env python3
"""Build a deterministic, label-stratified English v5 prompt-test split.

The source remains dev_train, the only split authorized for prompt iteration.
Human/evaluation fields remain in the saved split for scoring but are stripped
by run_bloom_coding.py before records are sent to a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


LLM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SPLIT = LLM_DIR / "splits" / "english" / "dev_train.jsonl"
DEFAULT_REFERENCE = (
    LLM_DIR / "splits" / "english" / "dev_train_human_reference.jsonl"
)
DEFAULT_INSPECTED = LLM_DIR / "splits" / "english" / "inspected_rows.txt"
DEFAULT_OUTPUT_DIR = LLM_DIR / "splits" / "english"
OUTPUT_STEM = "dev_train_prompttest_v5"

# Oversample the two difficult discourse labels and retain every available
# double-coded consensus example from rare categories.
DEFAULT_QUOTAS = {
    "Rejection": 80,
    "Denial": 80,
    "Nonexistence": 50,
    "Excluded": 30,
    "Nonpossession": 10,
    "Uncoded": 10,
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def canonical_label(value: object) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    return {
        "rejection": "Rejection",
        "denial": "Denial",
        "nonexistence": "Nonexistence",
        "nonexistance": "Nonexistence",
        "nonpossession": "Nonpossession",
        "nonposession": "Nonpossession",
        "excluded": "Excluded",
        "uncoded": "Uncoded",
    }.get(key)


def inspected_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def stable_rank(seed: str, record_id: str) -> str:
    return hashlib.sha256(f"{seed}:{record_id}".encode()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--inspected", type=Path, default=DEFAULT_INSPECTED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--seed", default="bloom-v5-prompt-experiment-2026-07-27")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing generated split, reference, and manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir
    split_out = output_dir / f"{OUTPUT_STEM}.jsonl"
    reference_out = output_dir / f"{OUTPUT_STEM}_human_reference.jsonl"
    manifest_out = output_dir / f"{OUTPUT_STEM}_manifest.json"
    outputs = [split_out, reference_out, manifest_out]

    existing = [path.exists() for path in outputs]
    if all(existing) and not args.overwrite:
        print(f"Reusing existing prompt-test split: {split_out}")
        return 0
    if any(existing) and not args.overwrite:
        raise SystemExit(
            "Prompt-test outputs are only partially present. "
            "Use --overwrite after inspecting them."
        )

    rows = read_jsonl(args.split)
    references = read_jsonl(args.reference)
    excluded = inspected_ids(args.inspected)
    by_label: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        first = canonical_label(row.get("bloom_1"))
        second = canonical_label(row.get("bloom_2"))
        if (
            first is not None
            and first == second
            and row["record_id"] not in excluded
        ):
            by_label[first].append(row)

    selected: list[dict] = []
    selected_counts: Counter[str] = Counter()
    for label, quota in DEFAULT_QUOTAS.items():
        candidates = sorted(
            by_label.get(label, []),
            key=lambda row: stable_rank(args.seed, row["record_id"]),
        )
        chosen = candidates[:quota]
        selected.extend(chosen)
        selected_counts[label] = len(chosen)

    # Preserve source order so batching behaves like a real transcript run.
    source_position = {row["record_id"]: index for index, row in enumerate(rows)}
    selected.sort(key=lambda row: source_position[row["record_id"]])
    selected_ids = {row["record_id"] for row in selected}
    selected_references = [
        row for row in references if row["record_id"] in selected_ids
    ]
    if len(selected_references) != len(selected):
        raise SystemExit("Selected split and human reference counts do not match.")

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(split_out, selected)
    write_jsonl(reference_out, selected_references)
    manifest = {
        "schema_version": "v5_prompt_experiment_split_v1",
        "source_split": str(args.split),
        "source_reference": str(args.reference),
        "inspected_ids_excluded": str(args.inspected),
        "seed": args.seed,
        "requested_quotas": DEFAULT_QUOTAS,
        "selected_counts": dict(selected_counts),
        "n_records": len(selected),
        "record_ids": [row["record_id"] for row in selected],
        "note": (
            "This is a class-enriched prompt diagnostic, not a population-"
            "weighted accuracy sample. Add any rows manually inspected during "
            "error analysis to splits/english/inspected_rows.txt."
        ),
    }
    manifest_out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {key: value for key, value in manifest.items() if key != "record_ids"},
            indent=2,
        )
    )
    print(f"Wrote: {split_out}")
    print(f"Wrote: {reference_out}")
    print(f"Wrote: {manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
