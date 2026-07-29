#!/usr/bin/env python3
"""Build the frozen dev_train sample for the multilingual production pair.

German, Hebrew, and Spanish receive 250 uninspected rows on which both human
coders supplied the same exact Bloom label. Their quotas are the closest
feasible per-language rendering of the English 246-row diagnostic mix.

Tagalog has fewer than 250 eligible consensus rows. Its sample therefore keeps
every eligible exact-consensus row and every eligible row with exactly one
human Bloom label. The manifest and copied records mark those two evaluation
subsets explicitly; disagreement rows are never selected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


LLM_DIR = Path(__file__).resolve().parents[1]
OUTPUT_STEM = "dev_train_promptpair_v5"
LANGUAGES = ("german", "hebrew", "spanish", "tagalog")
LABELS = (
    "Rejection",
    "Denial",
    "Nonexistence",
    "Excluded",
    "Nonpossession",
    "Uncoded",
)

# Each row sums to 250 and is feasible in that language's uninspected,
# exact-consensus dev_train pool. The allocations minimize distortion from
# the English diagnostic mix subject to each language's rare-class limits.
CONSENSUS_QUOTAS = {
    "german": {
        "Rejection": 82,
        "Denial": 82,
        "Nonexistence": 51,
        "Excluded": 29,
        "Nonpossession": 6,
        "Uncoded": 0,
    },
    "hebrew": {
        "Rejection": 83,
        "Denial": 82,
        "Nonexistence": 52,
        "Excluded": 29,
        "Nonpossession": 3,
        "Uncoded": 1,
    },
    "spanish": {
        "Rejection": 90,
        "Denial": 90,
        "Nonexistence": 56,
        "Excluded": 14,
        "Nonpossession": 0,
        "Uncoded": 0,
    },
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
    return {
        "rejection": "Rejection",
        "denial": "Denial",
        "nonexistence": "Nonexistence",
        "nonexistance": "Nonexistence",
        "nonpossession": "Nonpossession",
        "nonposession": "Nonpossession",
        "excluded": "Excluded",
        "uncoded": "Uncoded",
    }.get(str(value).strip().lower())


def inspected_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def stable_rank(seed: str, language: str, label: str, record_id: str) -> str:
    value = f"{seed}:{language}:{label}:{record_id}"
    return hashlib.sha256(value.encode()).hexdigest()


def portable_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(LLM_DIR))
    except ValueError:
        return str(path)


def classify(row: dict) -> tuple[str, str | None]:
    first = canonical_label(row.get("bloom_1"))
    second = canonical_label(row.get("bloom_2"))
    supplied = [label for label in (first, second) if label is not None]
    if len(supplied) == 2 and supplied[0] == supplied[1]:
        return "double_coded_consensus", supplied[0]
    if len(supplied) == 1:
        return "single_human_label", supplied[0]
    if len(supplied) == 2:
        return "double_coded_disagreement", None
    return "no_human_label", None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        default="bloom-v5-multilingual-production-pair-2026-07-29",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace complete existing sample artifacts after validation.",
    )
    return parser.parse_args()


def build_language(language: str, seed: str, overwrite: bool) -> dict:
    split_dir = LLM_DIR / "splits" / language
    source_path = split_dir / "dev_train.jsonl"
    reference_path = split_dir / "dev_train_human_reference.jsonl"
    inspected_path = split_dir / "inspected_rows.txt"
    split_out = split_dir / f"{OUTPUT_STEM}.jsonl"
    reference_out = split_dir / f"{OUTPUT_STEM}_human_reference.jsonl"
    manifest_out = split_dir / f"{OUTPUT_STEM}_manifest.json"
    outputs = (split_out, reference_out, manifest_out)

    existing = [path.exists() for path in outputs]
    if all(existing) and not overwrite:
        manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
        print(f"Reusing {language}: {manifest_out}")
        return manifest
    if any(existing) and not overwrite:
        raise SystemExit(
            f"{language}: sample outputs are partially present; inspect them "
            "and use --overwrite to replace all three."
        )

    rows = read_jsonl(source_path)
    references = read_jsonl(reference_path)
    reference_by_id = {row["record_id"]: row for row in references}
    excluded = inspected_ids(inspected_path)
    source_position = {row["record_id"]: i for i, row in enumerate(rows)}
    eligible_by_group: dict[str, list[dict]] = defaultdict(list)
    available_counts: Counter[str] = Counter()

    for row in rows:
        record_id = row["record_id"]
        if record_id in excluded:
            continue
        group, label = classify(row)
        available_counts[f"{group}:{label or 'NA'}"] += 1
        annotated = dict(row)
        annotated["evaluation_subset"] = group
        annotated["sampling_label"] = label
        eligible_by_group[group].append(annotated)

    if language == "tagalog":
        selected = (
            eligible_by_group["double_coded_consensus"]
            + eligible_by_group["single_human_label"]
        )
        requested_n = 250
        selection_note = (
            "All eligible exact-consensus and exactly-one-human-label rows "
            "were retained. Double-coded disagreements and rows without a "
            "usable Bloom label were excluded."
        )
    else:
        selected = []
        quotas = CONSENSUS_QUOTAS[language]
        consensus_by_label: dict[str, list[dict]] = defaultdict(list)
        for row in eligible_by_group["double_coded_consensus"]:
            consensus_by_label[row["sampling_label"]].append(row)
        for label in LABELS:
            quota = quotas[label]
            candidates = sorted(
                consensus_by_label[label],
                key=lambda row: stable_rank(seed, language, label, row["record_id"]),
            )
            if len(candidates) < quota:
                raise SystemExit(
                    f"{language}: need {quota} {label} consensus rows, "
                    f"found {len(candidates)}."
                )
            selected.extend(candidates[:quota])
        requested_n = 250
        selection_note = (
            "Deterministic exact-consensus stratified sample using the "
            "language-specific quota closest to the English diagnostic mix."
        )

    selected.sort(key=lambda row: source_position[row["record_id"]])
    selected_ids = [row["record_id"] for row in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise SystemExit(f"{language}: duplicate record IDs selected.")
    selected_references = []
    for row in selected:
        reference = dict(reference_by_id[row["record_id"]])
        reference["evaluation_subset"] = row["evaluation_subset"]
        reference["sampling_label"] = row["sampling_label"]
        selected_references.append(reference)

    selected_counts = Counter(
        f"{row['evaluation_subset']}:{row['sampling_label']}" for row in selected
    )
    manifest = {
        "schema_version": "v5_multilingual_production_pair_sample_v1",
        "language": language,
        "source_split": portable_path(source_path),
        "source_reference": portable_path(reference_path),
        "inspected_ids_excluded": portable_path(inspected_path),
        "seed": seed,
        "requested_n": requested_n,
        "selected_n": len(selected),
        "shortfall": requested_n - len(selected),
        "consensus_quotas": CONSENSUS_QUOTAS.get(language),
        "available_counts": dict(sorted(available_counts.items())),
        "selected_counts": dict(sorted(selected_counts.items())),
        "selection_note": selection_note,
        "record_ids": selected_ids,
        "consensus_record_ids": [
            row["record_id"]
            for row in selected
            if row["evaluation_subset"] == "double_coded_consensus"
        ],
        "single_human_label_record_ids": [
            row["record_id"]
            for row in selected
            if row["evaluation_subset"] == "single_human_label"
        ],
    }

    write_jsonl(split_out, selected)
    write_jsonl(reference_out, selected_references)
    manifest_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"{language}: selected {len(selected)}/{requested_n}; "
        f"shortfall={manifest['shortfall']}"
    )
    return manifest


def main() -> int:
    args = parse_args()
    manifests = [
        build_language(language, args.seed, args.overwrite)
        for language in LANGUAGES
    ]
    print(
        json.dumps(
            {
                manifest["language"]: {
                    "selected_n": manifest["selected_n"],
                    "shortfall": manifest["shortfall"],
                    "selected_counts": manifest["selected_counts"],
                }
                for manifest in manifests
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
