#!/usr/bin/env python3
"""Summarize completed v5 prompt experiments against human consensus."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path


LLM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = LLM_DIR / "v5" / "results" / "prompt_experiments"
DEFAULT_SPLIT = (
    LLM_DIR / "splits" / "english" / "dev_train_prompttest_v5.jsonl"
)


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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


def collapsed_label(value: object) -> str | None:
    label = canonical_label(value)
    return "Nonexistence" if label == "Nonpossession" else label


def mean(values: list[bool]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(value: float | None) -> float | None:
    return round(100 * value, 3) if value is not None else None


def exact_sign_p(wins: int, losses: int) -> float | None:
    n = wins + losses
    if n == 0:
        return None
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Summary CSV path (default: <results-dir>/summary.csv).",
    )
    return parser.parse_args()


def read_run_log(results_dir: Path, prefix: str) -> dict:
    """Recover the final run summary and retry count from the companion log."""
    log_path = results_dir / "logs" / f"{prefix}.log"
    if not log_path.exists():
        return {}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    starts = [match.start() + 1 for match in re.finditer(r'\n\{\n  "split":', text)]
    summary = {}
    if starts:
        try:
            summary = json.loads(text[starts[-1] :])
        except json.JSONDecodeError:
            pass
    summary["retry_count"] = text.count("Retrying batch")
    return summary


def main() -> int:
    args = parse_args()
    output_path = args.output or args.results_dir / "summary.csv"
    source = read_jsonl(args.split)
    human_exact: dict[str, str] = {}
    human_collapsed: dict[str, str] = {}
    for row in source:
        first = canonical_label(row.get("bloom_1"))
        second = canonical_label(row.get("bloom_2"))
        if first is not None and first == second:
            human_exact[row["record_id"]] = first
            human_collapsed[row["record_id"]] = collapsed_label(first) or first

    runs: list[dict] = []
    correctness: dict[str, dict[str, bool]] = {}
    for prediction_path in sorted(args.results_dir.glob("*_predictions.jsonl")):
        prefix = prediction_path.name.removesuffix("_predictions.jsonl")
        raw_path = prediction_path.with_name(f"{prefix}_raw_responses.jsonl")
        if not raw_path.exists():
            print(f"Skipping {prediction_path.name}: missing raw responses.")
            continue
        predictions = read_jsonl(prediction_path)
        raw = read_jsonl(raw_path)
        if not raw:
            print(f"Skipping {prediction_path.name}: empty raw responses.")
            continue

        meta = raw[0]
        by_id = {row["record_id"]: row for row in predictions}
        ids = [record_id for record_id in by_id if record_id in human_exact]
        if not ids:
            print(
                f"Skipping {prediction_path.name}: no IDs overlap the scoring split."
            )
            continue
        exact_ok = [
            canonical_label(by_id[record_id].get("bloom_label"))
            == human_exact[record_id]
            for record_id in ids
        ]
        collapsed_ok = {
            record_id: (
                collapsed_label(by_id[record_id].get("bloom_label"))
                == human_collapsed[record_id]
            )
            for record_id in ids
        }
        correctness[prefix] = collapsed_ok
        by_human: dict[str, list[bool]] = defaultdict(list)
        for record_id, ok in collapsed_ok.items():
            by_human[human_collapsed[record_id]].append(ok)

        certain_yes = [
            str(by_id[record_id].get("certain", "")).strip().lower() == "yes"
            for record_id in ids
        ]
        certain_yes_ok = [
            collapsed_ok[record_id]
            for record_id in ids
            if str(by_id[record_id].get("certain", "")).strip().lower() == "yes"
        ]
        log_summary = read_run_log(args.results_dir, prefix)
        elapsed_seconds = log_summary.get("elapsed_seconds")
        batch_sizes = sorted({len(batch.get("record_ids", [])) for batch in raw})
        decoding = meta.get("decoding_options") or {}
        run = {
            "run_prefix": prefix,
            "model": meta.get("model"),
            "prompt_version": meta.get("prompt_version"),
            "prompt_path": meta.get("prompt_path"),
            "reasoning_effort": meta.get("reasoning_effort", "default"),
            "temperature": decoding.get("temperature"),
            "seed": decoding.get("seed"),
            "top_p": decoding.get("top_p"),
            "top_k": decoding.get("top_k"),
            "min_p": decoding.get("min_p"),
            "batch_sizes": ",".join(map(str, batch_sizes)),
            "n": len(ids),
            "rejection_n": len(by_human["Rejection"]),
            "denial_n": len(by_human["Denial"]),
            "nonexistence_n": len(by_human["Nonexistence"]),
            "excluded_n": len(by_human["Excluded"]),
            "uncoded_n": len(by_human["Uncoded"]),
            "exact_accuracy_pct": pct(mean(exact_ok)),
            "collapsed_accuracy_pct": pct(mean(list(collapsed_ok.values()))),
            "rejection_accuracy_pct": pct(mean(by_human["Rejection"])),
            "denial_accuracy_pct": pct(mean(by_human["Denial"])),
            "nonexistence_accuracy_pct": pct(mean(by_human["Nonexistence"])),
            "excluded_accuracy_pct": pct(mean(by_human["Excluded"])),
            "uncoded_accuracy_pct": pct(mean(by_human["Uncoded"])),
            "certain_yes_pct": pct(mean(certain_yes)),
            "certain_yes_accuracy_pct": pct(mean(certain_yes_ok)),
            "elapsed_seconds": (
                round(float(elapsed_seconds), 2)
                if elapsed_seconds is not None
                else None
            ),
            "seconds_per_record": (
                round(float(elapsed_seconds) / len(ids), 3)
                if elapsed_seconds is not None
                else None
            ),
            "retry_count": log_summary.get("retry_count"),
            "is_model_baseline": False,
            "delta_vs_model_baseline_pp": None,
            "wins_vs_model_baseline": None,
            "losses_vs_model_baseline": None,
            "exact_sign_p_vs_model_baseline": None,
        }
        runs.append(run)

    baselines = {
        run["model"]: run
        for run in runs
        if "p005x-full-b5-rdefault-t0" in str(run["prompt_version"])
    }
    for run in runs:
        baseline = baselines.get(run["model"])
        if baseline is None:
            continue
        if baseline["run_prefix"] == run["run_prefix"]:
            run["is_model_baseline"] = True
            run["delta_vs_model_baseline_pp"] = 0.0
            continue
        run["delta_vs_model_baseline_pp"] = round(
            float(run["collapsed_accuracy_pct"])
            - float(baseline["collapsed_accuracy_pct"]),
            3,
        )
        current = correctness[run["run_prefix"]]
        reference = correctness[baseline["run_prefix"]]
        shared = current.keys() & reference.keys()
        wins = sum(current[item] and not reference[item] for item in shared)
        losses = sum(reference[item] and not current[item] for item in shared)
        run["wins_vs_model_baseline"] = wins
        run["losses_vs_model_baseline"] = losses
        p_value = exact_sign_p(wins, losses)
        run["exact_sign_p_vs_model_baseline"] = (
            round(p_value, 8) if p_value is not None else None
        )

    if not runs:
        raise SystemExit(f"No complete prediction/raw pairs in {args.results_dir}")

    runs.sort(
        key=lambda row: (
            str(row["model"]),
            -float(row["collapsed_accuracy_pct"] or 0),
            str(row["prompt_version"]),
        )
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(runs[0]))
        writer.writeheader()
        writer.writerows(runs)

    print(
        "MODEL\tPROMPT VERSION\tN\tCOLLAPSED ACC\tREJECTION\tDENIAL\t"
        "WINS/LOSSES VS MODEL BASELINE"
    )
    for run in runs:
        wins_losses = (
            "-"
            if run["wins_vs_model_baseline"] is None
            else f"{run['wins_vs_model_baseline']}/{run['losses_vs_model_baseline']}"
        )
        print(
            f"{run['model']}\t{run['prompt_version']}\t{run['n']}\t"
            f"{run['collapsed_accuracy_pct']}\t"
            f"{run['rejection_accuracy_pct']}\t"
            f"{run['denial_accuracy_pct']}\t{wins_losses}"
        )
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
