#!/usr/bin/env python3
"""Summarize the frozen multilingual Gemma/Qwen production-pair results."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path


LLM_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = LLM_DIR / "v5" / "results" / "multilingual_production_pair"
SPLIT_STEM = "dev_train_promptpair_v5"
LANGUAGES = ("german", "hebrew", "spanish", "tagalog")
LABELS = (
    "Rejection",
    "Denial",
    "Nonexistence",
    "Excluded",
    "Nonpossession",
    "Uncoded",
)
EXPECTED_CONFIGS = {
    "gemma_full_b1_t0": ("gemma4:31b", "full", 1),
    "qwen_condensed_b5_t0": ("qwen3.6:35b-a3b", "condensed", 5),
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def collapsed(label: str) -> str:
    return "Nonexistence" if label == "Nonpossession" else label


def exact_sign_pvalue(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / (2**n)
    return min(1.0, 2 * tail)


def config_from_prompt(prompt_version: str) -> str | None:
    if re.search(r"-full-b1-rdefault-t0$", prompt_version):
        return "gemma_full_b1_t0"
    if re.search(r"-condensed-b5-rdefault-t0$", prompt_version):
        return "qwen_condensed_b5_t0"
    return None


def subset_name(value: str) -> str:
    return {
        "double_coded_consensus": "consensus",
        "single_human_label": "single_human_label",
    }.get(value, value)


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prediction_files = sorted(RESULTS_DIR.glob(f"{SPLIT_STEM}_*_predictions.jsonl"))
    run_rows: list[dict] = []
    prediction_maps: dict[tuple[str, str], dict[str, dict]] = {}
    sample_maps: dict[str, dict[str, dict]] = {}
    issues: list[str] = []

    for language in LANGUAGES:
        sample_path = (
            LLM_DIR / "splits" / language / f"{SPLIT_STEM}.jsonl"
        )
        manifest_path = (
            LLM_DIR / "splits" / language / f"{SPLIT_STEM}_manifest.json"
        )
        sample = read_jsonl(sample_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sample_maps[language] = {row["record_id"]: row for row in sample}
        if len(sample) != manifest["selected_n"]:
            issues.append(
                f"{language}: sample has {len(sample)} rows; "
                f"manifest says {manifest['selected_n']}."
            )

    for prediction_path in prediction_files:
        raw_path = prediction_path.with_name(
            prediction_path.name.replace("_predictions.jsonl", "_raw_responses.jsonl")
        )
        if not raw_path.exists():
            issues.append(f"{prediction_path.name}: missing raw responses.")
            continue
        predictions = read_jsonl(prediction_path)
        raw_batches = read_jsonl(raw_path)
        if not raw_batches:
            issues.append(f"{raw_path.name}: empty raw responses.")
            continue
        meta = raw_batches[0]
        prompt_version = str(meta.get("prompt_version", ""))
        model = str(meta.get("model", ""))
        config = config_from_prompt(prompt_version)
        language_code = re.search(r"p005y-([a-z]{2})-", prompt_version)
        code_to_language = {"de": "german", "he": "hebrew", "es": "spanish", "tl": "tagalog"}
        language = code_to_language.get(language_code.group(1) if language_code else "")
        if language is None or config is None:
            issues.append(f"{prediction_path.name}: unrecognized prompt version {prompt_version}.")
            continue
        expected_model, prompt_arm, batch_size = EXPECTED_CONFIGS[config]
        if model != expected_model:
            issues.append(
                f"{prediction_path.name}: model {model} does not match {expected_model}."
            )
        samples = sample_maps[language]
        pred_by_id = {row["record_id"]: row for row in predictions}
        if len(pred_by_id) != len(predictions):
            issues.append(f"{prediction_path.name}: duplicate prediction IDs.")
        missing = sorted(set(samples) - set(pred_by_id))
        unexpected = sorted(set(pred_by_id) - set(samples))
        raw_ids = [
            record_id
            for batch in raw_batches
            for record_id in batch.get("record_ids", [])
        ]
        if missing or unexpected:
            issues.append(
                f"{prediction_path.name}: missing={len(missing)}, "
                f"unexpected={len(unexpected)}."
            )
        if Counter(raw_ids) != Counter(pred_by_id):
            issues.append(f"{prediction_path.name}: raw/prediction ID coverage differs.")
        prediction_maps[(language, config)] = pred_by_id

        subset_values = sorted(
            {
                samples[record_id]["evaluation_subset"]
                for record_id in pred_by_id
                if record_id in samples
            }
        )
        for subset_value in subset_values:
            ids = [
                record_id
                for record_id, sample in samples.items()
                if sample["evaluation_subset"] == subset_value
                and record_id in pred_by_id
            ]
            if not ids:
                continue
            exact_ok = [
                pred_by_id[record_id]["bloom_label"]
                == samples[record_id]["sampling_label"]
                for record_id in ids
            ]
            collapsed_ok = [
                collapsed(pred_by_id[record_id]["bloom_label"])
                == collapsed(samples[record_id]["sampling_label"])
                for record_id in ids
            ]
            certain_yes = sum(
                pred_by_id[record_id].get("certain") == "Yes" for record_id in ids
            )
            row = {
                "language": language,
                "config": config,
                "model": model,
                "prompt_arm": prompt_arm,
                "batch_size": batch_size,
                "reasoning": "default",
                "temperature": 0,
                "prompt_version": prompt_version,
                "evaluation_subset": subset_name(subset_value),
                "n": len(ids),
                "exact_correct": sum(exact_ok),
                "exact_accuracy": sum(exact_ok) / len(ids),
                "collapsed_correct": sum(collapsed_ok),
                "collapsed_accuracy": sum(collapsed_ok) / len(ids),
                "certain_yes_n": certain_yes,
                "certain_yes_rate": certain_yes / len(ids),
                "prediction_file": prediction_path.name,
            }
            for label in LABELS:
                class_ids = [
                    record_id
                    for record_id in ids
                    if samples[record_id]["sampling_label"] == label
                ]
                correct = sum(
                    pred_by_id[record_id]["bloom_label"] == label
                    for record_id in class_ids
                )
                key = label.lower()
                row[f"{key}_n"] = len(class_ids)
                row[f"{key}_correct"] = correct
                row[f"{key}_accuracy"] = (
                    correct / len(class_ids) if class_ids else ""
                )
            run_rows.append(row)

    paired_rows: list[dict] = []
    for language in LANGUAGES:
        left = prediction_maps.get((language, "gemma_full_b1_t0"))
        right = prediction_maps.get((language, "qwen_condensed_b5_t0"))
        if left is None or right is None:
            continue
        samples = sample_maps[language]
        for subset_value in ("double_coded_consensus", "single_human_label"):
            ids = [
                record_id
                for record_id, sample in samples.items()
                if sample["evaluation_subset"] == subset_value
                and record_id in left
                and record_id in right
            ]
            if not ids:
                continue
            gemma = [
                left[record_id]["bloom_label"] == samples[record_id]["sampling_label"]
                for record_id in ids
            ]
            qwen = [
                right[record_id]["bloom_label"] == samples[record_id]["sampling_label"]
                for record_id in ids
            ]
            gemma_only = sum(a and not b for a, b in zip(gemma, qwen))
            qwen_only = sum(b and not a for a, b in zip(gemma, qwen))
            paired_rows.append(
                {
                    "language": language,
                    "evaluation_subset": subset_name(subset_value),
                    "n": len(ids),
                    "gemma_correct": sum(gemma),
                    "gemma_accuracy": sum(gemma) / len(ids),
                    "qwen_correct": sum(qwen),
                    "qwen_accuracy": sum(qwen) / len(ids),
                    "gemma_only_correct": gemma_only,
                    "qwen_only_correct": qwen_only,
                    "exact_sign_pvalue": exact_sign_pvalue(
                        gemma_only, qwen_only
                    ),
                }
            )

    expected_runs = {
        (language, config)
        for language in LANGUAGES
        for config in EXPECTED_CONFIGS
    }
    missing_runs = sorted(expected_runs - set(prediction_maps))
    for language, config in missing_runs:
        issues.append(f"missing run: {language} {config}")

    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(RESULTS_DIR / "summary.csv", run_rows)
    write_csv(RESULTS_DIR / "paired_summary.csv", paired_rows)
    status = {
        "expected_runs": len(expected_runs),
        "completed_runs": len(prediction_maps),
        "summary_rows": len(run_rows),
        "paired_rows": len(paired_rows),
        "issues": issues,
    }
    (RESULTS_DIR / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
